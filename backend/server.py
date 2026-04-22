from fastapi import FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import shutil, os

from database import Base, engine, SessionLocal
from models import User, Event

import firebase_admin
from firebase_admin import credentials, messaging

if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)

app = FastAPI()

Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("images", exist_ok=True)
TOKEN_FILE = "fcm_token.txt"


def load_token():
    if not os.path.exists(TOKEN_FILE):
        return None

    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
        token = f.read().strip()

    return token or None


def save_token_to_file(token):
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(token)


FCM_TOKEN = load_token()


def get_risk_info(risk):
    if risk <= 30:
        return "LOW"
    elif risk <= 70:
        return "MEDIUM"
    else:
        return "HIGH"


def send_push(token, title, body):
    if not token:
        print("PUSH SKIPPED: token is empty")
        return

    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    channel_id="helmet_alerts",
                    icon="launcher_icon",
                    color="#FF9800",
                    sound="default",
                    default_sound=True,
                    default_vibrate_timings=True,
                    priority="high",
                    visibility="public",
                ),
            ),
            apns=messaging.APNSConfig(
                headers={
                    "apns-priority": "10",
                },
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound="default",
                        badge=1,
                    ),
                ),
            ),
            token=token,
        )

        response = messaging.send(message)
        print("PUSH SENT:", response)

    except Exception as e:
        print("PUSH ERROR:", e)


@app.post("/token")
def save_token(data: dict):
    global FCM_TOKEN
    FCM_TOKEN = data.get("token")
    if FCM_TOKEN:
        save_token_to_file(FCM_TOKEN)
    print("NEW TOKEN:", FCM_TOKEN)
    return {"ok": True}


@app.post("/test_push")
def test_push():
    send_push(
        FCM_TOKEN,
        "Helmet Safety",
        "Test notification",
    )
    return {"ok": bool(FCM_TOKEN)}


@app.post("/event")
async def receive_event(
    file: UploadFile = File(...),
    event_id: str = Form(...),
    duration: float = Form(...),
    zone: int = Form(...),
    risk: int = Form(...),
    timestamp: str = Form(...),
):
    db = SessionLocal()

    try:
        path = f"images/{event_id}.jpg"

        with open(path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        event = Event(
            event_id=event_id,
            name=None,
            time=timestamp,
            duration=duration,
            zone=zone,
            risk=risk,
            image=f"/images/{event_id}.jpg",
            status="In Process",
        )

        db.add(event)
        db.commit()

        try:
            risk_text = get_risk_info(risk)

            send_push(
                FCM_TOKEN,
                "Helmet Safety",
                f"{risk_text} risk - {int(duration)} sec",
            )
        except Exception as e:
            print("PUSH ERROR:", e)

        return {"ok": True}

    except Exception as e:
        print("EVENT ERROR:", e)
        return {"ok": False}

    finally:
        db.close()


@app.get("/events")
def get_events():
    db = SessionLocal()

    data = (
        db.query(Event)
        .filter(Event.status == "In Process")
        .order_by(Event.event_id.desc())
        .all()
    )

    result = [e.__dict__ for e in data]
    for r in result:
        r.pop("_sa_instance_state", None)

    db.close()
    return result


@app.get("/history")
def history():
    db = SessionLocal()

    data = (
        db.query(Event)
        .filter(Event.status == "Resolved")
        .order_by(Event.event_id.desc())
        .all()
    )

    result = [e.__dict__ for e in data]
    for r in result:
        r.pop("_sa_instance_state", None)

    db.close()
    return result


@app.post("/resolve/{event_id}")
def resolve(event_id: str):
    db = SessionLocal()

    event = db.query(Event).filter(Event.event_id == event_id).first()

    if event:
        event.status = "Resolved"
        db.commit()

    db.close()
    return {"ok": True}


@app.post("/update_name")
def update_name(data: dict):
    db = SessionLocal()

    event = db.query(Event).filter(Event.event_id == data["event_id"]).first()

    if event:
        new_name = data.get("name") or "Unknown"
        old_name = event.name
        changed = old_name != new_name

        event.name = new_name
        db.commit()
        db.close()

        if changed and new_name != "Unknown":
            send_push(
                FCM_TOKEN,
                "Person identified",
                f"{new_name} detected in helmet safety event",
            )

        return {"ok": True, "changed": changed, "name": new_name}

    db.close()
    return {"ok": False}


@app.post("/register")
def register(data: dict):
    db = SessionLocal()

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return {"status": "error"}

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        db.close()
        return {"status": "exists"}

    user = User(email=email, password=password)

    db.add(user)
    db.commit()
    db.close()

    return {"status": "ok"}


@app.post("/login")
def login(data: dict):
    db = SessionLocal()

    user = (
        db.query(User)
        .filter(
            User.email == data["email"],
            User.password == data["password"],
        )
        .first()
    )

    db.close()

    if user:
        return {"status": "ok"}
    return {"status": "error"}


@app.delete("/event/{event_id}")
def delete_event(event_id: str):
    db = SessionLocal()

    event = db.query(Event).filter(Event.event_id == event_id).first()

    if not event:
        db.close()
        return {"ok": False}

    try:
        file_path = event.image.replace("/images/", "images/")
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        print("FILE DELETE ERROR:", e)

    db.delete(event)
    db.commit()
    db.close()

    return {"ok": True}


@app.get("/stats")
def stats():
    db = SessionLocal()

    total = db.query(Event).count()
    active = db.query(Event).filter(Event.status == "In Process").count()
    resolved = db.query(Event).filter(Event.status == "Resolved").count()

    risks = db.query(Event.risk).all()
    avg_risk = sum(r[0] for r in risks) / len(risks) if risks else 0

    db.close()

    return {
        "total": total,
        "active": active,
        "resolved": resolved,
        "avg_risk": int(avg_risk),
    }


app.mount("/images", StaticFiles(directory="images"), name="images")

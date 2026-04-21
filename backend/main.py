from fastapi import FastAPI
from database import Base, engine, SessionLocal
from models import Event

app = FastAPI()

Base.metadata.create_all(bind=engine)


@app.get("/events")
def get_events():
    db = SessionLocal()
    data = db.query(Event).filter(Event.status == "In Process").all()
    db.close()
    return data


@app.get("/history")
def history():
    db = SessionLocal()
    data = db.query(Event).filter(Event.status == "Resolved").all()
    db.close()
    return data


@app.post("/resolve/{event_id}")
def resolve(event_id: str):
    db = SessionLocal()
    event = db.query(Event).filter(Event.event_id == event_id).first()
    event.status = "Resolved"
    db.commit()
    db.close()
    return {"status": "ok"}
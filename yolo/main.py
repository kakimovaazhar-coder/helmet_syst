import cv2
import time
import os
import math
import threading
import requests
from ultralytics import YOLO

SERVER = os.environ.get("HELMET_SERVER_URL", "http://172.20.10.8:8000")

NO_HELMET_TIME = 15
AUTO_CLOSE_TIME = 3

FRAME_SIZE = (320, 240)
CONF_TH = 0.6

STABLE_FRAMES = 2
MISS_TTL = 6
MATCH_DIST = 150

ZONE_WEIGHTS = {1: 1.0, 2: 1.2, 3: 1.5, 4: 2.0}

daily_violations = {}

model = YOLO("best.pt")
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

os.makedirs("violations", exist_ok=True)

people = {}
stable_ids = {}
next_pid = 1


def center(box):
    x1, y1, x2, y2 = box
    return ((x1 + x2) // 2, (y1 + y2) // 2)


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def get_zone(x, y, w, h):
    if x < w // 2 and y < h // 2:
        return 1
    elif x >= w // 2 and y < h // 2:
        return 2
    elif x < w // 2 and y >= h // 2:
        return 3
    else:
        return 4


def match_person(box, now):
    global next_pid
    c = center(box)

    best_pid = None
    best_dist = 9999

    for pid, p in people.items():
        if now - p["last_update"] > MISS_TTL:
            continue

        d = distance(c, p["center"])
        if d < best_dist:
            best_dist = d
            best_pid = pid

    if best_pid and best_dist < MATCH_DIST:
        p = people[best_pid]
        p["center"] = c
        p["bbox"] = box
        p["last_update"] = now
        return best_pid, p

    pid = next_pid
    next_pid += 1

    people[pid] = {
        "center": c,
        "bbox": box,
        "start": None,
        "sent": False,
        "event_id": None,
        "zone": 1,
        "last_update": now,
        "active": False,
        "last_label": None,
        "label_count": 0,
    }

    return pid, people[pid]


def send_event(filename, data):
    def task():
        try:
            with open(filename, "rb") as f:
                requests.post(
                    f"{SERVER}/event",
                    files={"file": f},
                    data=data,
                    timeout=2,
                )
        except:
            print("API ERROR")

    threading.Thread(target=task, daemon=True).start()


def close_event(event_id):
    def task():
        try:
            requests.post(f"{SERVER}/resolve/{event_id}", timeout=2)
        except:
            print("CLOSE ERROR")

    threading.Thread(target=task, daemon=True).start()


prev_time = time.time()

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.resize(frame, FRAME_SIZE)
    now = time.time()

    results = model.track(
        frame,
        persist=True,
        conf=CONF_TH,
        imgsz=320,
        tracker="bytetrack.yaml",
        verbose=False,
    )

    if results[0].boxes.id is not None:
        boxes = results[0].boxes.xyxy.cpu().numpy()
        ids = results[0].boxes.id.cpu().numpy()
        classes = results[0].boxes.cls.cpu().numpy()
        confs = results[0].boxes.conf.cpu().numpy()

        for box, tid, cls, conf in zip(boxes, ids, classes, confs):
            if conf < CONF_TH:
                continue

            x1, y1, x2, y2 = map(int, box)

            color = (0, 255, 0) if cls == 0 else (0, 0, 255)

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                frame,
                f"ID {int(tid)}",
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2,
            )

            stable_ids[tid] = stable_ids.get(tid, 0) + 1
            is_stable = stable_ids[tid] >= STABLE_FRAMES

            if not is_stable:
                continue

            pid, person = match_person((x1, y1, x2, y2), now)

            raw_label = "helmet" if cls == 0 else "no_helmet"

            if person["last_label"] == raw_label:
                person["label_count"] += 1
            else:
                person["label_count"] = 0
                person["last_label"] = raw_label

            if person["label_count"] < 2:
                continue

            label = raw_label

            cx, cy = center((x1, y1, x2, y2))
            zone = get_zone(cx, cy, FRAME_SIZE[0], FRAME_SIZE[1])
            person["zone"] = zone

            if label == "no_helmet":
                if person["start"] is None:
                    person["start"] = now

                duration = now - person["start"]

                if duration > NO_HELMET_TIME and not person["sent"]:
                    print(f"INCIDENT PID {pid}")

                    event_id = str(int(time.time()))
                    filename = f"violations/{event_id}.jpg"

                    cv2.imwrite(filename, frame)

                    today = time.strftime("%Y-%m-%d")

                    if today not in daily_violations:
                        daily_violations[today] = 0

                    daily_violations[today] += 1
                    daily_count = daily_violations[today]

                    risk = duration * ZONE_WEIGHTS[zone] + daily_count * 4

                    if daily_count > 5:
                        risk += 15

                    risk = min(int(risk), 100)

                    data = {
                        "event_id": event_id,
                        "duration": duration,
                        "zone": zone,
                        "risk": risk,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    }

                    send_event(filename, data)

                    person["sent"] = True
                    person["event_id"] = event_id
                    person["active"] = True

            else:
                if person["sent"] and person["active"]:
                    print(f"CLOSED PID {pid}")
                    close_event(person["event_id"])

                person["start"] = None
                person["sent"] = False
                person["active"] = False

    for pid, person in list(people.items()):
        if now - person["last_update"] > AUTO_CLOSE_TIME:
            if person.get("sent") and person.get("active"):
                print(f"AUTO CLOSE PID {pid}")
                close_event(person["event_id"])

            del people[pid]

    current_time = time.time()
    fps = 1 / (current_time - prev_time)
    prev_time = current_time

    cv2.putText(
        frame,
        f"FPS: {int(fps)}",
        (10, 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2,
    )

    cv2.imshow("Helmet System", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()

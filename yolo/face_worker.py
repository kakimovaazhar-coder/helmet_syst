import os
import time

import cv2
import numpy as np
import requests
from deepface import DeepFace

SERVER = os.environ.get("HELMET_SERVER_URL", "http://172.20.10.8:8000")
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
IMAGE_DIRS = [
    os.environ.get("HELMET_EVENT_IMAGE_DIR", ""),
    os.path.join(BASE_DIR, "backend", "images"),
    os.path.join(BASE_DIR, "yolo", "violations"),
]

POLL_INTERVAL = 3
REQUEST_TIMEOUT = 4
MAX_FACE_CHECKS_PER_LOOP = 3
MAX_FACES_PER_IMAGE = 4
MAX_UNKNOWN_ATTEMPTS = 3
MAX_IMAGE_WIDTH = 900
FACE_MARGIN = 0.28
FACE_SIZE = 224
FACE_THRESHOLD = 0.7
MODEL_NAME = "Facenet512"
DETECTOR_BACKEND = os.environ.get("HELMET_FACE_DETECTOR", "opencv")

session = requests.Session()
updated_events = set()
attempts = {}


def extract_name(identity):
    parts = str(identity).replace("\\", "/").split("/")
    if len(parts) >= 2:
        return parts[-2]
    return "Unknown"


def find_event_image(image_path):
    filename = image_path.split("/")[-1]

    for directory in IMAGE_DIRS:
        if not directory:
            continue

        path = os.path.join(directory, filename)
        if os.path.exists(path):
            return path

    return None


def crop_face_from_area(img, area):
    height, width = img.shape[:2]

    x = int(area.get("x", 0))
    y = int(area.get("y", 0))
    w = int(area.get("w", 0))
    h = int(area.get("h", 0))

    if w <= 0 or h <= 0:
        return None

    margin_x = int(w * FACE_MARGIN)
    margin_y = int(h * FACE_MARGIN)

    x1 = max(0, x - margin_x)
    y1 = max(0, y - margin_y)
    x2 = min(width, x + w + margin_x)
    y2 = min(height, y + h + margin_y)

    crop = img[y1:y2, x1:x2]
    if crop.size == 0:
        return None

    return cv2.resize(crop, (FACE_SIZE, FACE_SIZE))


def recognize_face(path):
    img = cv2.imread(path)
    if img is None:
        print("IMAGE READ ERROR:", path)
        return "Unknown"

    height, width = img.shape[:2]
    if width > MAX_IMAGE_WIDTH:
        scale = MAX_IMAGE_WIDTH / width
        img = cv2.resize(img, (MAX_IMAGE_WIDTH, int(height * scale)))

    faces = DeepFace.extract_faces(
        img_path=img,
        enforce_detection=False,
        detector_backend=DETECTOR_BACKEND,
        align=True,
    )

    if not faces:
        print("NO FACE:", path)
        return "Unknown"

    faces = sorted(
        faces,
        key=lambda item: item.get("facial_area", {}).get("w", 0)
        * item.get("facial_area", {}).get("h", 0),
        reverse=True,
    )[:MAX_FACES_PER_IMAGE]

    print(f"FACES FOUND: {len(faces)} in {os.path.basename(path)}")

    matches = []

    for face in faces:
        area = face.get("facial_area", {})
        face_img = crop_face_from_area(img, area)

        if face_img is None:
            face_img = face.get("face")

        if face_img is None:
            continue

        if face_img.dtype != np.uint8:
            face_img = np.clip(face_img * 255, 0, 255).astype(np.uint8)

        if len(face_img.shape) == 3 and face_img.shape[2] == 3:
            face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)

        if face_img.shape[0] != FACE_SIZE or face_img.shape[1] != FACE_SIZE:
            face_img = cv2.resize(face_img, (FACE_SIZE, FACE_SIZE))

        if face_img.size == 0:
            continue

        result = DeepFace.find(
            img_path=face_img,
            db_path="faces",
            enforce_detection=False,
            detector_backend="skip",
            align=False,
            model_name=MODEL_NAME,
            silent=True,
        )

        if not result or len(result[0]) == 0:
            continue

        best = result[0].sort_values(by="distance").iloc[0]
        dist = float(best["distance"])

        if dist < FACE_THRESHOLD:
            matches.append((extract_name(best["identity"]), dist))

    if not matches:
        return "Unknown"

    names = []
    for name, _ in sorted(matches, key=lambda item: item[1]):
        if name != "Unknown" and name not in names:
            names.append(name)

    if not names:
        return "Unknown"

    return ", ".join(names)


def send_name(event_id, name):
    res = session.post(
        f"{SERVER}/update_name",
        json={
            "event_id": event_id,
            "name": name,
        },
        timeout=REQUEST_TIMEOUT,
    )

    if res.status_code != 200:
        print("POST ERROR:", res.status_code, res.text)
        return False

    data = res.json()
    print("UPDATED:", event_id, name, data)
    return data.get("ok") is True


while True:
    try:
        res = session.get(f"{SERVER}/events", timeout=REQUEST_TIMEOUT)

        print("STATUS:", res.status_code)

        if res.status_code != 200:
            print("SERVER ERROR:", res.text)
            time.sleep(POLL_INTERVAL)
            continue

        if not res.text.strip():
            print("EMPTY RESPONSE")
            time.sleep(POLL_INTERVAL)
            continue

        events = res.json()

    except Exception as e:
        print("REQUEST ERROR:", e)
        time.sleep(POLL_INTERVAL)
        continue

    checks_done = 0

    for event in events:
        event_id = event.get("event_id")
        if not event_id or event_id in updated_events:
            continue

        if event.get("name") is not None:
            updated_events.add(event_id)
            continue

        if checks_done >= MAX_FACE_CHECKS_PER_LOOP:
            break

        path = find_event_image(event["image"])

        if not path:
            print("FILE NOT FOUND:", event["image"])
            continue

        checks_done += 1

        try:
            name = recognize_face(path)
        except Exception as err:
            print("FACE ERROR:", err)
            name = "Unknown"

        if name == "Unknown":
            attempts[event_id] = attempts.get(event_id, 0) + 1
            print(
                f"UNKNOWN: {event_id} "
                f"attempt {attempts[event_id]}/{MAX_UNKNOWN_ATTEMPTS}"
            )

            if attempts[event_id] < MAX_UNKNOWN_ATTEMPTS:
                continue

        try:
            if send_name(event_id, name):
                updated_events.add(event_id)
        except Exception as err:
            print("POST ERROR:", err)

    time.sleep(POLL_INTERVAL)

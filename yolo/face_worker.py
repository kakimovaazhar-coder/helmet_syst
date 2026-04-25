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
MAX_FACES_PER_IMAGE = int(os.environ.get("HELMET_MAX_FACES_PER_IMAGE", "4"))
MAX_UNKNOWN_ATTEMPTS = 3
MAX_IMAGE_WIDTH = 900
FACE_MARGIN = 0.28
FACE_SIZE = 224
FACE_THRESHOLD = float(os.environ.get("HELMET_FACE_THRESHOLD", "0.68"))
FACE_CLOSE_THRESHOLD = float(os.environ.get("HELMET_FACE_CLOSE_THRESHOLD", "0.72"))
MIN_MATCHES_FOR_NAME = int(os.environ.get("HELMET_FACE_MIN_MATCHES", "1"))
NAME_GAP = float(os.environ.get("HELMET_FACE_NAME_GAP", "0.025"))
VERY_GOOD_MATCH = float(os.environ.get("HELMET_FACE_VERY_GOOD", "0.48"))
TOP_MATCHES_PER_NAME = int(os.environ.get("HELMET_FACE_TOP_MATCHES", "5"))
MODEL_NAME = "Facenet512"
DETECTOR_BACKEND = os.environ.get("HELMET_FACE_DETECTOR", "opencv")
FACE_DB_PATH = os.environ.get("HELMET_FACE_DB", os.path.join(os.path.dirname(__file__), "faces"))
REBUILD_FACE_CACHE = os.environ.get("HELMET_FACE_REBUILD_CACHE", "0") != "0"

session = requests.Session()
updated_events = set()
attempts = {}


def clear_face_cache():
    if not REBUILD_FACE_CACHE:
        return

    if not os.path.isdir(FACE_DB_PATH):
        print("FACE DB NOT FOUND:", FACE_DB_PATH)
        return

    removed = 0
    for filename in os.listdir(FACE_DB_PATH):
        lower = filename.lower()
        if lower.startswith("ds_model_") and lower.endswith(".pkl"):
            try:
                os.remove(os.path.join(FACE_DB_PATH, filename))
                removed += 1
            except OSError as err:
                print("CACHE REMOVE ERROR:", filename, err)

    if removed:
        print(f"FACE CACHE CLEARED: {removed} file(s)")


clear_face_cache()
print("FACE DB:", FACE_DB_PATH)


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


def face_priority(img, face):
    height, width = img.shape[:2]
    area = face.get("facial_area", {})

    x = int(area.get("x", 0))
    y = int(area.get("y", 0))
    w = int(area.get("w", 0))
    h = int(area.get("h", 0))

    face_center_x = x + w / 2
    face_center_y = y + h / 2
    frame_center_x = width / 2
    frame_center_y = height / 2

    center_dist = abs(face_center_x - frame_center_x) + abs(face_center_y - frame_center_y)
    face_size = w * h

    return (center_dist, -face_size)


def choose_name(matches):
    if not matches:
        return None

    by_name = {}

    for name, dist in matches:
        if name == "Unknown":
            continue

        by_name.setdefault(name, []).append(dist)

    if not by_name:
        return None

    ranked = []
    for name, distances in by_name.items():
        distances = sorted(distances)
        top = distances[:TOP_MATCHES_PER_NAME]
        unique_top = []
        for dist in top:
            if not unique_top or abs(dist - unique_top[-1]) > 0.015:
                unique_top.append(dist)

        close_count = len([dist for dist in unique_top if dist <= FACE_CLOSE_THRESHOLD])
        # Favor the best honest match first and use the average of distinct close matches
        # only as a small stabilizer, so one person does not win just because they have more photos.
        score = unique_top[0] * 0.85 + (sum(unique_top) / len(unique_top)) * 0.15
        ranked.append((name, score, unique_top[0], close_count, len(unique_top)))

    ranked.sort(key=lambda item: item[1])
    best_name, best_score, best_dist, close_count, total_count = ranked[0]

    print(
        "FACE MATCH:",
        best_name,
        f"score={best_score:.3f}",
        f"best={best_dist:.3f}",
        f"close={close_count}",
        f"total={total_count}",
    )

    if best_score > FACE_THRESHOLD:
        return None

    if close_count < MIN_MATCHES_FOR_NAME and best_dist > VERY_GOOD_MATCH:
        return None

    if len(ranked) > 1:
        second_name, second_score, second_dist, _, _ = ranked[1]
        print(
            "SECOND MATCH:",
            second_name,
            f"score={second_score:.3f}",
            f"best={second_dist:.3f}",
        )

        if second_score - best_score < NAME_GAP:
            return None

    return best_name


def add_deepface_matches(matches, face_img):
    if face_img is None or face_img.size == 0:
        return

    if face_img.dtype != np.uint8:
        face_img = np.clip(face_img * 255, 0, 255).astype(np.uint8)

    if face_img.shape[0] != FACE_SIZE or face_img.shape[1] != FACE_SIZE:
        face_img = cv2.resize(face_img, (FACE_SIZE, FACE_SIZE))

    result = DeepFace.find(
        img_path=face_img,
        db_path=FACE_DB_PATH,
        enforce_detection=False,
        detector_backend="skip",
        align=False,
        model_name=MODEL_NAME,
        silent=True,
    )

    if not result or len(result[0]) == 0:
        return

    candidates = result[0].sort_values(by="distance").head(8)

    for _, candidate in candidates.iterrows():
        matches.append(
            (
                extract_name(candidate["identity"]),
                float(candidate["distance"]),
            )
        )


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

    faces = sorted(faces, key=lambda item: face_priority(img, item))[
        :MAX_FACES_PER_IMAGE
    ]

    print(f"FACES FOUND: {len(faces)} in {os.path.basename(path)}")

    matches = []

    for face in faces:
        # DeepFace already aligned this face; use it first for better side-angle matching.
        before = len(matches)
        add_deepface_matches(matches, face.get("face"))

        area = face.get("facial_area", {})
        face_img = crop_face_from_area(img, area)
        if face_img is not None:
            face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)

        # If the aligned face was too tight or detector alignment failed, try a wider crop too.
        if len(matches) == before:
            add_deepface_matches(matches, face_img)

    name = choose_name(matches)
    if not name:
        return "Unknown"

    return name


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

            # Do not lock the event forever as Unknown.
            # Keep retrying on future loops in case the cache, thresholds, or face database changed.
            attempts[event_id] = MAX_UNKNOWN_ATTEMPTS
            continue

        try:
            if send_name(event_id, name):
                updated_events.add(event_id)
        except Exception as err:
            print("POST ERROR:", err)

    time.sleep(POLL_INTERVAL)

import argparse
import math
import os
import threading
import time

import cv2
import requests
from ultralytics import YOLO


ZONE_WEIGHTS = {1: 1.0, 2: 1.2, 3: 1.5, 4: 2.0}


# center of person in frame
def center(box):
    x1, y1, x2, y2 = box
    return ((x1 + x2) // 2, (y1 + y2) // 2)


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def get_zone(x, y, w, h):
    if x < w // 2 and y < h // 2:
        return 1
    if x >= w // 2 and y < h // 2:
        return 2
    if x < w // 2 and y >= h // 2:
        return 3
    return 4


class UsbCamera:
    # simple usb camera
    def __init__(self, source, frame_size):
        self.cap = cv2.VideoCapture(source)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.frame_size = frame_size

    def read(self):
        ok, frame = self.cap.read()
        if not ok:
            return None
        return cv2.resize(frame, self.frame_size)

    def close(self):
        self.cap.release()


class PiCamera:
    # raspberry ribbon camera
    def __init__(self, frame_size, color_mode):
        from picamera2 import Picamera2

        self.frame_size = frame_size
        self.color_mode = color_mode
        self.camera = Picamera2()
        config = self.camera.create_preview_configuration(
            main={"size": frame_size, "format": "RGB888"}
        )
        self.camera.configure(config)
        self.camera.start()
        time.sleep(1)

    def read(self):
        frame = self.camera.capture_array()
        if self.color_mode == "rgb":
            return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        return frame

    def close(self):
        self.camera.stop()


class ActiveBuzzer:
    # active buzzer with short beeps
    def __init__(self, pin, enabled, interval, duration, on_time, off_time):
        self.pin = pin
        self.enabled = enabled
        self.interval = interval
        self.duration = duration
        self.on_time = on_time
        self.off_time = off_time
        self.last_started = 0
        self.playing = False
        self.lock = threading.Lock()
        self.device = None

        if not self.enabled:
            return

        try:
            from gpiozero import OutputDevice

            self.device = OutputDevice(pin, active_high=True, initial_value=False)
            print(f"BUZZER READY GPIO{pin}")
        except Exception as err:
            self.enabled = False
            print("BUZZER DISABLED:", err)

    def start_if_needed(self, should_alert, now):
        if not self.enabled or not should_alert:
            return

        if now - self.last_started < self.interval:
            return

        with self.lock:
            if self.playing:
                return
            self.playing = True
            self.last_started = now

        threading.Thread(target=self._play, daemon=True).start()

    def _play(self):
        end_time = time.time() + self.duration

        try:
            while time.time() < end_time:
                self.device.on()
                time.sleep(self.on_time)
                self.device.off()
                time.sleep(self.off_time)
        finally:
            if self.device:
                self.device.off()
            with self.lock:
                self.playing = False

    def close(self):
        if self.device:
            self.device.off()
            self.device.close()


class Detector:
    def __init__(self, args):
        self.server = args.server.rstrip("/")
        self.model = YOLO(args.model)
        self.frame_size = (args.width, args.height)
        self.no_helmet_time = args.no_helmet_time
        self.auto_close_time = args.auto_close_time
        self.conf = args.conf
        self.no_helmet_class = args.no_helmet_class
        self.imgsz = args.imgsz
        self.miss_ttl = args.miss_ttl
        self.match_dist = args.match_dist
        self.preview = args.preview
        self.debug_detections = args.debug_detections
        self.last_debug_print = 0
        self.violations_dir = args.violations_dir
        self.people = {}
        self.next_pid = 1
        self.daily_violations = {}
        self.buzzer = ActiveBuzzer(
            pin=args.buzzer_pin,
            enabled=not args.no_buzzer,
            interval=args.buzzer_interval,
            duration=args.buzzer_duration,
            on_time=args.buzzer_on_time,
            off_time=args.buzzer_off_time,
        )

        os.makedirs(self.violations_dir, exist_ok=True)

        # choose camera type here
        if args.camera_backend == "picamera2":
            self.camera = PiCamera(self.frame_size, args.camera_color)
        else:
            self.camera = UsbCamera(args.camera, self.frame_size)

    def match_person(self, box, now):
        # keep the same person between frames
        c = center(box)
        best_pid = None
        best_dist = 9999

        for pid, person in self.people.items():
            if now - person["last_update"] > self.miss_ttl:
                continue

            d = distance(c, person["center"])
            if d < best_dist:
                best_dist = d
                best_pid = pid

        if best_pid and best_dist < self.match_dist:
            person = self.people[best_pid]
            person["center"] = c
            person["bbox"] = box
            person["last_update"] = now
            return best_pid, person

        pid = self.next_pid
        self.next_pid += 1

        self.people[pid] = {
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

        return pid, self.people[pid]

    def post_event(self, filename, data):
        # send violation to laptop server
        def task():
            try:
                with open(filename, "rb") as f:
                    requests.post(
                        f"{self.server}/event",
                        files={"file": f},
                        data=data,
                        timeout=4,
                    )
            except Exception as err:
                print("API ERROR:", err)

        threading.Thread(target=task, daemon=True).start()

    def close_event(self, event_id):
        # close event when helmet is back or person is gone
        def task():
            try:
                requests.post(f"{self.server}/resolve/{event_id}", timeout=4)
            except Exception as err:
                print("CLOSE ERROR:", err)

        threading.Thread(target=task, daemon=True).start()

    def send_violation(self, frame, pid, person, duration):
        # called after no-helmet delay
        event_id = str(int(time.time()))
        filename = os.path.join(self.violations_dir, f"{event_id}.jpg")
        cv2.imwrite(filename, frame)

        today = time.strftime("%Y-%m-%d")
        if today not in self.daily_violations:
            self.daily_violations[today] = 0

        self.daily_violations[today] += 1
        daily_count = self.daily_violations[today]

        risk = duration * ZONE_WEIGHTS[person["zone"]] + daily_count * 4
        if daily_count > 5:
            risk += 15

        risk = min(int(risk), 100)

        data = {
            "event_id": event_id,
            "duration": duration,
            "zone": person["zone"],
            "risk": risk,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        print(f"INCIDENT PID {pid}")
        self.post_event(filename, data)
        person["sent"] = True
        person["event_id"] = event_id
        person["active"] = True

    def handle_detection(self, frame, box, cls, conf, now):
        # logic for one detected person
        if conf < self.conf:
            return

        x1, y1, x2, y2 = map(int, box)
        pid, person = self.match_person((x1, y1, x2, y2), now)
        class_id = int(cls)
        raw_label = "no_helmet" if class_id == self.no_helmet_class else "helmet"

        if self.debug_detections and now - self.last_debug_print > 1:
            print(
                f"DETECTED {raw_label} "
                f"class={class_id} conf={conf:.2f} pid={pid}"
            )
            self.last_debug_print = now

        if person["last_label"] == raw_label:
            person["label_count"] += 1
        else:
            person["label_count"] = 0
            person["last_label"] = raw_label

        if person["label_count"] < 2:
            return

        cx, cy = center((x1, y1, x2, y2))
        person["zone"] = get_zone(cx, cy, self.frame_size[0], self.frame_size[1])

        if raw_label == "no_helmet":
            if person["start"] is None:
                person["start"] = now

            duration = now - person["start"]
            if duration > self.no_helmet_time and not person["sent"]:
                self.send_violation(frame, pid, person, duration)
        else:
            if person["sent"] and person["active"]:
                print(f"CLOSED PID {pid}")
                self.close_event(person["event_id"])

            person["start"] = None
            person["sent"] = False
            person["active"] = False

        if self.preview:
            color = (0, 255, 0) if raw_label == "helmet" else (0, 0, 255)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                frame,
                f"PID {pid}",
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2,
            )

    def has_active_no_helmet(self, now):
        # buzzer waits for the same no-helmet delay
        for person in self.people.values():
            if now - person["last_update"] > self.miss_ttl:
                continue
            if person["last_label"] != "no_helmet":
                continue
            if person["label_count"] < 2:
                continue
            if person["start"] is None:
                continue
            if now - person["start"] < self.no_helmet_time:
                continue
            return True
        return False

    def cleanup_people(self, now):
        # remove people lost by camera
        for pid, person in list(self.people.items()):
            if now - person["last_update"] > self.auto_close_time:
                if person.get("sent") and person.get("active"):
                    print(f"AUTO CLOSE PID {pid}")
                    self.close_event(person["event_id"])
                del self.people[pid]

    def run(self):
        # main camera loop
        prev_time = time.time()

        try:
            while True:
                frame = self.camera.read()
                if frame is None:
                    print("CAMERA READ ERROR")
                    time.sleep(1)
                    continue

                now = time.time()
                results = self.model.predict(
                    frame,
                    conf=self.conf,
                    imgsz=self.imgsz,
                    verbose=False,
                )

                if results and results[0].boxes is not None:
                    boxes = results[0].boxes.xyxy.cpu().numpy()
                    classes = results[0].boxes.cls.cpu().numpy()
                    confs = results[0].boxes.conf.cpu().numpy()

                    for box, cls, conf in zip(boxes, classes, confs):
                        self.handle_detection(frame, box, cls, conf, now)

                self.cleanup_people(now)
                self.buzzer.start_if_needed(self.has_active_no_helmet(now), now)

                if self.preview:
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

        finally:
            self.camera.close()
            self.buzzer.close()
            if self.preview:
                cv2.destroyAllWindows()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--server",
        default=os.environ.get("HELMET_SERVER_URL", "http://172.20.10.8:8000"),
    )
    parser.add_argument("--model", default=os.environ.get("HELMET_MODEL", "best.pt"))
    parser.add_argument(
        "--camera-backend",
        choices=["opencv", "picamera2"],
        default="opencv",
    )
    parser.add_argument("--camera-color", choices=["rgb", "bgr"], default="rgb")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--height", type=int, default=240)
    parser.add_argument("--imgsz", type=int, default=320)
    parser.add_argument("--conf", type=float, default=0.6)
    parser.add_argument("--no-helmet-class", type=int, default=1)
    parser.add_argument("--no-helmet-time", type=float, default=15)
    parser.add_argument("--auto-close-time", type=float, default=3)
    parser.add_argument("--miss-ttl", type=float, default=6)
    parser.add_argument("--match-dist", type=float, default=150)
    parser.add_argument("--violations-dir", default="violations")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--debug-detections", action="store_true")
    parser.add_argument("--no-buzzer", action="store_true")
    parser.add_argument("--buzzer-pin", type=int, default=17)
    parser.add_argument("--buzzer-interval", type=float, default=60)
    parser.add_argument("--buzzer-duration", type=float, default=3)
    parser.add_argument("--buzzer-on-time", type=float, default=0.04)
    parser.add_argument("--buzzer-off-time", type=float, default=0.35)
    return parser.parse_args()


if __name__ == "__main__":
    Detector(parse_args()).run()

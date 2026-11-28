import ctypes
import json
import math
import os
import statistics
import time
from collections import deque
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

import cv2
import mediapipe as mp
from pynput.mouse import Button, Controller
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


CAMERA_INDEX = 0
NOSE_TIP_INDEX = 1
HORIZONTAL_RANGE = 0.18
VERTICAL_RANGE = 0.18
CURSOR_SPEED = 0.55
MIN_CUTOFF = 1.2
BETA = 0.04
KALMAN_VELOCITY_DECAY_SECONDS = 0.2
KALMAN_VELOCITY_DEADBAND = 0.005
CURSOR_DEADBAND_PIXELS = 10
BLINK_DURATION = 0.06
BLINK_REFRACTORY = 0.8
MOUTH_OPEN_THRESHOLD = 0.65
MOUTH_CLOSE_THRESHOLD = 0.35
DWELL_RADIUS = 18
DWELL_SELECTION_SECONDS = 5.0
MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "face_landmarker.task"
API_BASE_URL = os.environ.get("MOTIONEASE_API_URL", "http://127.0.0.1:5000")


class OneEuroFilter:
    def __init__(self, min_cutoff=MIN_CUTOFF, beta=BETA, derivative_cutoff=1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.derivative_cutoff = derivative_cutoff
        self.previous_value = None
        self.previous_derivative = 0.0
        self.previous_time = None

    @staticmethod
    def _alpha(cutoff, elapsed):
        smoothing = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + smoothing / elapsed)

    def __call__(self, value, timestamp):
        if self.previous_value is None:
            self.previous_value = value
            self.previous_time = timestamp
            return value

        elapsed = max(timestamp - self.previous_time, 1e-6)
        derivative = (value - self.previous_value) / elapsed
        derivative_alpha = self._alpha(self.derivative_cutoff, elapsed)
        filtered_derivative = (
            derivative_alpha * derivative
            + (1.0 - derivative_alpha) * self.previous_derivative
        )

        cutoff = self.min_cutoff + self.beta * abs(filtered_derivative)
        value_alpha = self._alpha(cutoff, elapsed)
        filtered_value = (
            value_alpha * value + (1.0 - value_alpha) * self.previous_value
        )

        self.previous_value = filtered_value
        self.previous_derivative = filtered_derivative
        self.previous_time = timestamp
        return filtered_value

    def reset(self):
        self.previous_value = None
        self.previous_derivative = 0.0
        self.previous_time = None


class AdaptiveKalmanFilter:
    def __init__(self, process_noise=2.0, measurement_noise=0.0025):
        self.process_noise = process_noise
        self.measurement_noise = measurement_noise
        self.position = None
        self.velocity = 0.0
        self.p00 = 1.0
        self.p01 = 0.0
        self.p10 = 0.0
        self.p11 = 1.0
        self.previous_time = None

    def __call__(self, measurement, timestamp):
        if self.position is None:
            self.position = measurement
            self.previous_time = timestamp
            return measurement

        elapsed = min(max(timestamp - self.previous_time, 1e-4), 0.2)
        predicted_position = self.position + elapsed * self.velocity
        predicted_p00 = (
            self.p00
            + elapsed * (self.p01 + self.p10)
            + elapsed * elapsed * self.p11
            + self.process_noise * elapsed**4 / 4.0
        )
        predicted_p01 = (
            self.p01 + elapsed * self.p11 + self.process_noise * elapsed**3 / 2.0
        )
        predicted_p10 = (
            self.p10 + elapsed * self.p11 + self.process_noise * elapsed**3 / 2.0
        )
        predicted_p11 = self.p11 + self.process_noise * elapsed**2

        residual = measurement - predicted_position
        adaptive_noise = self.measurement_noise / (
            1.0 + min(abs(residual) * 20.0, 8.0)
        )
        innovation_variance = predicted_p00 + adaptive_noise
        gain_position = predicted_p00 / innovation_variance
        gain_velocity = predicted_p10 / innovation_variance

        self.position = predicted_position + gain_position * residual
        self.velocity += gain_velocity * residual
        self.velocity *= math.exp(-elapsed / KALMAN_VELOCITY_DECAY_SECONDS)
        if abs(self.velocity) < KALMAN_VELOCITY_DEADBAND:
            self.velocity = 0.0
        self.p00 = (1.0 - gain_position) * predicted_p00
        self.p01 = (1.0 - gain_position) * predicted_p01
        self.p10 = predicted_p10 - gain_velocity * predicted_p00
        self.p11 = predicted_p11 - gain_velocity * predicted_p01
        self.previous_time = timestamp
        return self.position

    def reset(self):
        self.position = None
        self.velocity = 0.0
        self.p00 = 1.0
        self.p01 = 0.0
        self.p10 = 0.0
        self.p11 = 1.0
        self.previous_time = None


def eye_aspect_ratio(landmarks, indices):
    points = [(landmarks[index].x, landmarks[index].y) for index in indices]

    def distance(first, second):
        return math.hypot(first[0] - second[0], first[1] - second[1])

    horizontal = distance(points[0], points[3])
    if horizontal == 0:
        return 0.0
    vertical = distance(points[1], points[5]) + distance(points[2], points[4])
    return vertical / (2.0 * horizontal)


class BlinkDetector:
    def __init__(self, refractory_period=BLINK_REFRACTORY):
        self.open_measurements = deque(maxlen=30)
        self.closed_since = None
        self.is_closed = False
        self.fired = False
        self.last_blink = float("-inf")
        self.refractory_period = refractory_period

    def update(self, aspect_ratio, timestamp):
        baseline = (
            statistics.median(self.open_measurements)
            if self.open_measurements
            else 0.28
        )
        close_threshold = max(0.12, baseline * 0.65)
        open_threshold = close_threshold * 1.25

        if not self.is_closed and aspect_ratio <= close_threshold:
            self.is_closed = True
            self.closed_since = timestamp
            self.fired = False
        elif self.is_closed and aspect_ratio >= open_threshold:
            self.is_closed = False
            self.closed_since = None
            self.fired = False
            self.open_measurements.append(aspect_ratio)
        elif not self.is_closed and aspect_ratio >= open_threshold:
            self.open_measurements.append(aspect_ratio)

        if (
            self.is_closed
            and not self.fired
            and self.closed_since is not None
            and timestamp - self.closed_since >= BLINK_DURATION
            and timestamp - self.last_blink >= self.refractory_period
        ):
            self.fired = True
            self.last_blink = timestamp
            return True
        return False


class DwellClickController:
    def __init__(
        self,
        radius=DWELL_RADIUS,
        minimum=DWELL_SELECTION_SECONDS,
        maximum=DWELL_SELECTION_SECONDS,
    ):
        self.radius = radius
        self.minimum = minimum
        self.maximum = maximum
        self.previous_position = None
        self.previous_time = None
        self.recent_speeds = deque()
        self.anchor = None
        self.started_at = None
        self.duration = minimum
        self.last_click_position = None

    def update(self, position, timestamp):
        speed = 0.0
        if self.previous_position is not None and self.previous_time is not None:
            elapsed = max(timestamp - self.previous_time, 1e-4)
            speed = math.dist(position, self.previous_position) / elapsed
        self.previous_position = position
        self.previous_time = timestamp

        self.recent_speeds.append((timestamp, speed))
        while self.recent_speeds and timestamp - self.recent_speeds[0][0] > 0.3:
            self.recent_speeds.popleft()

        if (
            self.last_click_position is not None
            and math.dist(position, self.last_click_position) > self.radius * 2
        ):
            self.last_click_position = None

        if self.last_click_position is not None:
            return None, 1.0

        if self.anchor is None or math.dist(position, self.anchor) > self.radius:
            self.anchor = position
            self.started_at = timestamp
            entry_speed = max((item[1] for item in self.recent_speeds), default=0.0)
            self.duration = min(
                self.maximum, max(self.minimum, self.minimum + entry_speed / 500.0)
            )
            return None, 0.0

        if self.started_at is None:
            self.started_at = timestamp
        progress = min(1.0, (timestamp - self.started_at) / self.duration)
        if progress >= 1.0:
            self.last_click_position = position
            self.anchor = None
            self.started_at = None
            return position, 1.0
        return None, progress

    def reset(self):
        self.previous_position = None
        self.previous_time = None
        self.recent_speeds.clear()
        self.anchor = None
        self.started_at = None
        self.last_click_position = None


def get_blendshape_score(blendshapes, name):
    for category in blendshapes:
        if category.category_name == name:
            return category.score
    return 0.0


def dispatch_gesture(name, mouse, fallback_button, fallback_count=1):
    request = Request(
        f"{API_BASE_URL}/api/interaction/events",
        data=json.dumps({"gesture": name}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=0.25) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not result.get("handled"):
            print(
                f"MotionEase did not handle {name}: "
                f"{result.get('error', 'Gesture was not handled')}",
                flush=True,
            )
    except URLError as error:
        reason = error.reason
        connection_refused = isinstance(reason, ConnectionRefusedError) or (
            getattr(reason, "winerror", None) == 10061
        )
        if not connection_refused:
            print(
                f"Could not confirm {name} with MotionEase ({error}); "
                "skipping local fallback to avoid duplicate input.",
                flush=True,
            )
            return
        print(
            f"MotionEase backend is unavailable ({error}); "
            "performing the local gesture action.",
            flush=True,
        )
        mouse.click(fallback_button, fallback_count)
    except TimeoutError as error:
        print(
            f"Could not confirm {name} with MotionEase ({error}); "
            "skipping local fallback to avoid duplicate input.",
            flush=True,
        )
    except json.JSONDecodeError as error:
        print(
            f"MotionEase returned an invalid response for {name} ({error}); "
            "skipping local fallback to avoid duplicate input.",
            flush=True,
        )


class MouthGestureDetector:
    def __init__(self, hold_duration=0.2, cooldown=1.0):
        self.hold_duration = hold_duration
        self.cooldown = cooldown
        self.is_open = False
        self.open_since = None
        self.last_click = float("-inf")

    def update(self, open_score, timestamp):
        if not self.is_open and open_score >= MOUTH_OPEN_THRESHOLD:
            self.is_open = True
            self.open_since = timestamp
            return False

        if self.is_open and open_score <= MOUTH_CLOSE_THRESHOLD:
            should_click = (
                self.open_since is not None
                and timestamp - self.open_since >= self.hold_duration
                and timestamp - self.last_click >= self.cooldown
            )
            self.is_open = False
            self.open_since = None
            if should_click:
                self.last_click = timestamp
                return True
        return False

    def cancel(self):
        self.is_open = False
        self.open_since = None


def get_screen_size():
    if hasattr(ctypes, "windll"):
        user32 = ctypes.windll.user32
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)

    import tkinter

    root = tkinter.Tk()
    root.withdraw()
    size = root.winfo_screenwidth(), root.winfo_screenheight()
    root.destroy()
    return size


def map_head_position(value, neutral, movement_range, cursor_anchor=0.5):
    normalized = cursor_anchor + CURSOR_SPEED * (value - neutral) / movement_range
    return min(max(normalized, 0.0), 1.0)


def stabilize_cursor_position(position, previous_position):
    if (
        previous_position is not None
        and math.dist(position, previous_position) < CURSOR_DEADBAND_PIXELS
    ):
        return previous_position
    return position


def main():
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(f"Face Landmarker model is missing: {MODEL_PATH}")

    camera = cv2.VideoCapture(CAMERA_INDEX)
    if not camera.isOpened():
        raise RuntimeError(
            f"Could not open webcam {CAMERA_INDEX}. Check camera access and try again."
        )

    screen_width, screen_height = get_screen_size()
    mouse = Controller()
    landmarker_options = vision.FaceLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1,
        min_face_detection_confidence=0.6,
        min_face_presence_confidence=0.6,
        min_tracking_confidence=0.6,
        output_face_blendshapes=True,
    )
    landmarker = vision.FaceLandmarker.create_from_options(landmarker_options)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    kalman_x = AdaptiveKalmanFilter()
    kalman_y = AdaptiveKalmanFilter()
    x_filter = OneEuroFilter()
    y_filter = OneEuroFilter()
    left_blink = BlinkDetector()
    right_blink = BlinkDetector()
    mouth_gesture = MouthGestureDetector()
    dwell = DwellClickController()
    neutral_position = None
    cursor_anchor = (0.5, 0.5)
    stable_cursor_position = None
    dwell_enabled = False

    try:
        while camera.isOpened():
            success, frame = camera.read()
            if not success:
                raise RuntimeError("Could not read a frame from the webcam.")

            frame = cv2.flip(frame, 1)
            frame_height, frame_width = frame.shape[:2]
            lab_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            lightness, channel_a, channel_b = cv2.split(lab_frame)
            enhanced_lightness = clahe.apply(lightness)
            enhanced_frame = cv2.merge((enhanced_lightness, channel_a, channel_b))
            frame = cv2.cvtColor(enhanced_frame, cv2.COLOR_LAB2BGR)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            result = landmarker.detect_for_video(image, int(time.monotonic() * 1000))

            if result.face_landmarks:
                landmarks = result.face_landmarks[0]
                nose = landmarks[NOSE_TIP_INDEX]
                nose_x, nose_y = nose.x, nose.y
                now = time.monotonic()

                if neutral_position is None:
                    neutral_position = nose_x, nose_y

                cv2.circle(
                    frame,
                    (int(nose_x * frame_width), int(nose_y * frame_height)),
                    5,
                    (0, 255, 0),
                    -1,
                )

                target_x = map_head_position(
                    nose_x, neutral_position[0], HORIZONTAL_RANGE, cursor_anchor[0]
                )
                target_y = map_head_position(
                    nose_y, neutral_position[1], VERTICAL_RANGE, cursor_anchor[1]
                )
                kalman_target_x = kalman_x(target_x, now)
                kalman_target_y = kalman_y(target_y, now)
                smooth_x = x_filter(kalman_target_x, now)
                smooth_y = y_filter(kalman_target_y, now)
                target_cursor_position = (
                    round(smooth_x * (screen_width - 1)),
                    round(smooth_y * (screen_height - 1)),
                )
                stable_cursor_position = stabilize_cursor_position(
                    target_cursor_position, stable_cursor_position
                )
                cursor_x, cursor_y = stable_cursor_position
                mouse.position = stable_cursor_position

                left_ear = eye_aspect_ratio(landmarks, (33, 160, 158, 133, 153, 144))
                right_ear = eye_aspect_ratio(
                    landmarks, (362, 385, 387, 263, 373, 380)
                )
                if left_blink.update(left_ear, now):
                    dispatch_gesture("left_blink", mouse, Button.left, 1)
                if right_blink.update(right_ear, now):
                    dispatch_gesture("right_blink", mouse, Button.left, 2)

                blendshapes = (
                    result.face_blendshapes[0] if result.face_blendshapes else []
                )
                mouth_open_score = get_blendshape_score(blendshapes, "jawOpen")
                if mouth_gesture.update(mouth_open_score, now):
                    dispatch_gesture("mouth_open", mouse, Button.right, 1)

                dwell_click, dwell_progress = (None, 0.0)
                if dwell_enabled:
                    dwell_click, dwell_progress = dwell.update((cursor_x, cursor_y), now)
                    if dwell_click is not None:
                        dispatch_gesture("dwell", mouse, Button.left, 1)
                else:
                    dwell.reset()

                status = "Head tracking active"
            else:
                status = "Face not detected - move into camera view"
                dwell.reset()
                left_blink = BlinkDetector()
                right_blink = BlinkDetector()
                mouth_gesture.cancel()

            cv2.putText(
                frame,
                f"{status} | Dwell: {'ON' if dwell_enabled else 'OFF'}",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0) if result.face_landmarks else (0, 165, 255),
                2,
            )
            cv2.putText(
                frame,
                "C: re-center | D: dwell click | Q: quit",
                (20, frame_height - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                1,
            )
            if dwell_enabled and result.face_landmarks and dwell_progress > 0:
                cv2.rectangle(
                    frame,
                    (20, 55),
                    (220, 70),
                    (90, 90, 90),
                    -1,
                )
                cv2.rectangle(
                    frame,
                    (20, 55),
                    (20 + round(200 * dwell_progress), 70),
                    (0, 220, 0),
                    -1,
                )
            cv2.imshow("MotionEase Head-Controlled Cursor", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("d"):
                dwell_enabled = not dwell_enabled
                dwell.reset()
            if key == ord("c") and result.face_landmarks:
                neutral_position = nose_x, nose_y
                cursor_position = mouse.position
                cursor_anchor = (
                    cursor_position[0] / (screen_width - 1),
                    cursor_position[1] / (screen_height - 1),
                )
                kalman_x.reset()
                kalman_y.reset()
                x_filter.reset()
                y_filter.reset()
    finally:
        camera.release()
        landmarker.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

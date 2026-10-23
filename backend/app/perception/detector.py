import base64
import logging
import math
import os
import time
import urllib.request
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

# Optional imports for YOLO & MediaPipe
try:
    from ultralytics import YOLO
    _YOLO_AVAILABLE = True
except (ImportError, OSError, Exception) as e:
    _YOLO_AVAILABLE = False

try:
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision
    _MEDIAPIPE_AVAILABLE = True
except ImportError:
    _MEDIAPIPE_AVAILABLE = False

logger = logging.getLogger("companion.perception")
logger.setLevel(logging.INFO)

GESTURE_TASK_URL = "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/latest/gesture_recognizer.task"


class PerceptionEngine:
    """
    Perception Engine for Real-Time Multimodal AI Companion.
    Integrates YOLOv8 for Person Presence Detection and MediaPipe Tasks
    for Face and Hand Gesture Tracking.
    """

    def __init__(self, yolo_model_name: str = "yolov8n.pt"):
        self.yolo_model = None
        self.gesture_recognizer = None
        self.is_initialized = False

        self._init_models(yolo_model_name)

    def _ensure_gesture_model(self) -> Optional[str]:
        """Ensure the MediaPipe gesture_recognizer.task model file is downloaded."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        backend_root = os.path.dirname(os.path.dirname(base_dir))
        
        # Candidate lookup locations in priority order
        candidates = [
            os.path.join(backend_root, "models", "gesture_recognizer.task"),
            os.path.join(backend_root, "gesture_recognizer.task"),
            os.path.join(base_dir, "gesture_recognizer.task"),
        ]
        for p in candidates:
            if os.path.exists(p):
                return p

        # Default download target: backend/models/
        target_path = os.path.join(backend_root, "models", "gesture_recognizer.task")
        try:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            logger.info(f"Downloading MediaPipe gesture_recognizer.task to {target_path}...")
            urllib.request.urlretrieve(GESTURE_TASK_URL, target_path)
            logger.info("gesture_recognizer.task downloaded successfully.")
            return target_path
        except Exception as e:
            logger.error(f"Failed to download gesture_recognizer.task: {e}")
            return None

    def _init_models(self, yolo_model_name: str):
        """Initialize YOLOv8 and MediaPipe models."""
        try:
            # 1. Initialize YOLOv8
            if _YOLO_AVAILABLE:
                backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                candidates = [
                    os.path.join(backend_root, "models", yolo_model_name),
                    os.path.join(backend_root, yolo_model_name),
                    yolo_model_name,
                ]
                resolved_yolo = yolo_model_name
                for c in candidates:
                    if os.path.exists(c):
                        resolved_yolo = c
                        break
                logger.info(f"Loading YOLOv8 model: {resolved_yolo}...")
                self.yolo_model = YOLO(resolved_yolo)
                logger.info("YOLOv8 initialized successfully.")
            else:
                logger.warning("Ultralytics YOLO not installed. Person detection will be disabled.")

            # 2. Initialize MediaPipe Tasks GestureRecognizer
            if _MEDIAPIPE_AVAILABLE:
                task_path = self._ensure_gesture_model()
                if task_path:
                    logger.info("Initializing MediaPipe GestureRecognizer...")
                    base_options = mp_python.BaseOptions(model_asset_path=task_path)
                    options = mp_vision.GestureRecognizerOptions(
                        base_options=base_options,
                        num_hands=2,
                        min_hand_detection_confidence=0.55,
                        min_hand_presence_confidence=0.55,
                        min_tracking_confidence=0.55,
                    )
                    self.gesture_recognizer = mp_vision.GestureRecognizer.create_from_options(options)
                    logger.info("MediaPipe GestureRecognizer initialized successfully.")
                else:
                    logger.warning("Gesture model file could not be loaded.")
            else:
                logger.warning("MediaPipe not installed. Gesture & face tracking will be disabled.")

            self.is_initialized = True
        except Exception as e:
            logger.error(f"Error initializing perception models: {e}", exc_info=True)

    def decode_image(self, frame_data: Any) -> Optional[np.ndarray]:
        """Decode frame data from either raw bytes or a base64 encoded string."""
        try:
            if isinstance(frame_data, str):
                if "," in frame_data:
                    frame_data = frame_data.split(",", 1)[1]
                image_bytes = base64.b64decode(frame_data)
            elif isinstance(frame_data, bytes):
                image_bytes = frame_data
            else:
                return None

            np_arr = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            return image
        except Exception as e:
            logger.error(f"Error decoding image frame: {e}")
            return None

    def _normalize_gesture_name(self, raw_gesture: str) -> Tuple[str, Optional[str]]:
        """
        Normalize MediaPipe gesture category names to application events.
        MediaPipe Built-in Gestures:
          'Open_Palm', 'Closed_Fist', 'Pointing_Up', 'Thumb_Up', 'Thumb_Down', 'Victory', 'ILoveYou', 'None'
        """
        lower = raw_gesture.lower().replace(" ", "_")
        if "open_palm" in lower or "palm" in lower:
            return "open_palm", "pause"
        elif "victory" in lower or "peace" in lower:
            return "victory", "greeting"
        elif "thumb_up" in lower or "thumbs_up" in lower:
            return "thumbs_up", "like"
        elif "pointing_up" in lower or "pointing" in lower:
            return "pointing_up", "pointing"
        elif "closed_fist" in lower or "fist" in lower:
            return "fist", "stop"
        elif "iloveyou" in lower:
            return "victory", "greeting"
        return "unknown", None

    def process_frame(self, frame_data: Any) -> Dict[str, Any]:
        """
        Process a single video frame with YOLOv8 and MediaPipe.
        Returns structured detection and tracking data with normalized [0, 1] coordinates.
        """
        start_time = time.time()
        image = self.decode_image(frame_data)

        if image is None:
            return {
                "user_present": False,
                "persons": [],
                "faces": [],
                "hands": [],
                "gesture_event": None,
                "inference_time_ms": 0,
            }

        h, w, _ = image.shape
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        persons = []
        user_present = False

        gaze_x, gaze_y = 0.0, 0.0

        # --- 1. YOLOv8 Presence Detection ---
        if self.yolo_model is not None:
            try:
                results = self.yolo_model(rgb_image, classes=[0], verbose=False, conf=0.35)
                for r in results:
                    boxes = r.boxes
                    for box in boxes:
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        conf = float(box.conf[0])
                        norm_box = [
                            round(x1 / w, 4),
                            round(y1 / h, 4),
                            round(x2 / w, 4),
                            round(y2 / h, 4),
                        ]
                        
                        # Added for gaze tracking
                        x_center = (x1 + x2) / 2
                        y_center = (y1 + y2) / 2
                        gaze_x = (x_center / w) * 2 - 1
                        gaze_y = (y_center / h) * 2 - 1

                        persons.append({
                            "bbox": norm_box,
                            "confidence": round(conf, 2),
                            "label": "person",
                        })
                user_present = len(persons) > 0
            except Exception as e:
                logger.error(f"YOLO inference error: {e}")

        # --- 2. MediaPipe Hand & Gesture Detection ---
        hands = []
        gesture_event = None

        if self.gesture_recognizer is not None:
            try:
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
                recognition_result = self.gesture_recognizer.recognize(mp_image)

                if recognition_result.hand_landmarks:
                    for idx, hand_lms in enumerate(recognition_result.hand_landmarks):
                        # Determine handedness
                        handedness_label = "Right"
                        if recognition_result.handedness and idx < len(recognition_result.handedness):
                            handedness_label = recognition_result.handedness[idx][0].category_name

                        # Determine recognized gesture and score
                        raw_gesture = "None"
                        gesture_score = 0.0
                        if recognition_result.gestures and idx < len(recognition_result.gestures):
                            top_g = recognition_result.gestures[idx][0]
                            raw_gesture = top_g.category_name
                            gesture_score = float(top_g.score)

                        # Filter out low-confidence gesture classifications
                        if gesture_score >= 0.48 and raw_gesture != "None":
                            gesture, event = self._normalize_gesture_name(raw_gesture)
                        else:
                            gesture = "unknown"
                            event = None

                        if event and not gesture_event:
                            gesture_event = event

                        # Extract 21 normalized landmarks [[x, y, z], ...]
                        landmarks_data = [
                            [round(lm.x, 4), round(lm.y, 4), round(lm.z, 4)]
                            for lm in hand_lms
                        ]

                        # Calculate hand bounding box
                        xs = [lm.x for lm in hand_lms]
                        ys = [lm.y for lm in hand_lms]
                        hand_box = [
                            round(max(0.0, min(xs) - 0.02), 4),
                            round(max(0.0, min(ys) - 0.02), 4),
                            round(min(1.0, max(xs) + 0.02), 4),
                            round(min(1.0, max(ys) + 0.02), 4),
                        ]

                        hands.append({
                            "handedness": handedness_label,
                            "gesture": gesture,
                            "raw_gesture": raw_gesture,
                            "score": round(gesture_score, 2),
                            "event": event,
                            "bbox": hand_box,
                            "landmarks": landmarks_data,
                        })
            except Exception as e:
                logger.error(f"MediaPipe Gesture recognition error: {e}")

        inference_time = round((time.time() - start_time) * 1000, 1)

        return {
            "user_present": user_present or len(hands) > 0,
            "persons": persons,
            "faces": [],
            "hands": hands,
            "gesture_event": gesture_event,
            "inference_time_ms": inference_time,
            "timestamp": time.time(),
            "gaze_x": round(gaze_x, 4),
            "gaze_y": round(gaze_y, 4),
        }


# Singleton instance
_engine_instance: Optional[PerceptionEngine] = None


def get_perception_engine() -> PerceptionEngine:
    """Get or create singleton PerceptionEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = PerceptionEngine()
    return _engine_instance

"""
Perception pipeline module (YOLOv8 Presence Detection & MediaPipe Gesture Tracking).
"""
from .detector import PerceptionEngine, get_perception_engine

__all__ = ["PerceptionEngine", "get_perception_engine"]

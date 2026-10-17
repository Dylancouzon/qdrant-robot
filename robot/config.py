"""Shared paths and configurable perception settings for the robot and its tools."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# On the Jetson, tools/jetson.py sets ROBOT_SHARED; on the Mac everything stays in the repo.
SHARED = Path(os.environ.get("ROBOT_SHARED", ROOT))
MODELS = SHARED / "models"

# Pixel sizes refer to a1280-pixel source width and scale with the camera frame.
OBJECT_MIN_SIDE = 120  # current green-capped foreground bottle measures126-127px
DETECT_LOW = 0.10  # detections that can continue an existing track
DETECT_HIGH = 0.25  # detections that can start a new track
DISPLAY_CONFIDENCE = 0.25  # confidence required to admit an unknown teaching focus

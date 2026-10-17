"""Shared paths and configurable perception settings for the robot and its tools."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# On the Jetson, tools/jetson.py sets ROBOT_SHARED; on the Mac everything stays in the repo.
SHARED = Path(os.environ.get("ROBOT_SHARED", ROOT))
MODELS = SHARED / "models"

# Worn items and people retain the stricter detector admission used for person association.
BODY = frozenset({"person", "face", "t-shirt", "lanyard", "badge", "hat", "glasses"})

# Pixel sizes refer to a1280-pixel source width and scale with the camera frame.
OBJECT_MIN_SIDE = 120  # current green-capped foreground bottle measures126-127px
DETECT_LOW = 0.10  # detections that can continue an existing track
DETECT_HIGH = 0.25  # body detections that can start a new track
DISPLAY_CONFIDENCE = 0.25  # body confidence required for fresh person association
OBJECT_CONFIDENCE = 0.15  # object proposals, focus, and fresh crop queries

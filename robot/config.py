"""Paths shared by the robot and its tools: the repo, models, and on-disk memory."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# On the Jetson, tools/jetson.py sets ROBOT_SHARED; on the Mac everything stays in the repo.
SHARED = Path(os.environ.get("ROBOT_SHARED", ROOT))
MODELS = SHARED / "models"

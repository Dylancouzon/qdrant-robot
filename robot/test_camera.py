"""FileCamera capture stamps: a still advances like a live camera, a video keeps frame stamps."""
import time

import cv2
import numpy as np

from robot.camera import FileCamera


def test_still_stamp_advances(tmp_path):
    cv2.imwrite(str(tmp_path / "a.png"), np.zeros((8, 8, 3), np.uint8))
    camera = FileCamera(tmp_path / "a.png")
    first = camera.latest()[1]
    time.sleep(0.01)
    assert camera.latest()[1] > first


def test_video_stamp_follows_frames(tmp_path):
    path = tmp_path / "v.avi"
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (8, 8))
    for _ in range(5):
        out.write(np.zeros((8, 8, 3), np.uint8))
    out.release()
    camera = FileCamera(path)
    first = camera.latest()[1]
    time.sleep(0.01)  # under one frame (0.1 s)
    assert camera.latest()[1] == first
    camera.close()

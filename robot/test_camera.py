"""FileCamera capture stamps: a still advances like a live camera, a video keeps frame stamps."""
import time
import threading
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from robot.camera import Camera, FileCamera
from robot.main import Robot


def test_mounted_live_capture_keeps_upright_pixels():
    camera = Camera.__new__(Camera)
    camera._lock, camera._stop = threading.Lock(), threading.Event()
    source = np.zeros((720, 1280, 3), np.uint8)
    source[:360, :640] = (17, 61, 203)

    def read():
        camera._stop.set()
        return True, source

    camera.cap = SimpleNamespace(read=read)
    camera._run()
    frame, stamp = camera.latest()
    assert stamp > 0
    assert tuple(frame[100, 100]) == (17, 61, 203)
    assert tuple(frame[600, 1100]) == (0, 0, 0)


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


@pytest.mark.parametrize("failure", ["seek", "decode"])
def test_failed_video_stays_failed_for_every_reader(tmp_path, failure):
    camera = FileCamera()
    released = []
    camera._cap = SimpleNamespace(set=lambda *args: failure != "seek",
                                  read=lambda: (False, None),
                                  release=lambda: released.append(True))
    camera._frame = np.zeros((8, 8, 3), np.uint8)
    camera._fps, camera._count, camera._index = 10, 100, 0
    camera._start, camera._anchor = time.monotonic() - 1, time.time() - 1
    with pytest.raises(RuntimeError, match=f"cannot {failure}") as first:
        camera.latest()  # the watcher or speech-start handler reads the failure first
    with pytest.raises(RuntimeError) as again:
        camera.latest()
    assert again.value is first.value and released == [True]
    robot = Robot.__new__(Robot)
    robot.camera, robot.closing, robot.detect_failed = camera, threading.Event(), None
    robot._detect()
    assert robot.detect_failed is first.value
    cv2.imwrite(str(tmp_path / "new.png"), np.zeros((8, 8, 3), np.uint8))
    camera.show(tmp_path / "new.png")
    assert camera.latest()[0] is not None, "showing a new source clears the error"

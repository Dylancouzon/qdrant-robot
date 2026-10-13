"""Newest BGR frames from the upright USB camera or stored-orientation image/video fixtures."""
import math
import threading
import time
from pathlib import Path

import cv2
import numpy as np

DEVICE = "/dev/video0"
CAPTURE = (1920, 1080)  # scaled to SIZE, which averages out grain (D167)
SIZE = (1280, 720)
ROTATE = cv2.ROTATE_180  # the camera is mounted upside down (STATE.md, Robot facts)


class Camera:
    def __init__(self, device: str = DEVICE):
        self.cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAPTURE[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE[1])
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not self.cap.isOpened():
            raise RuntimeError(f"cannot open {device}")
        self._frame: np.ndarray | None = None
        self._stamp = 0.0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="camera", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.05)
                continue
            frame = cv2.rotate(cv2.resize(frame, SIZE, interpolation=cv2.INTER_LINEAR), ROTATE)
            with self._lock:
                self._frame, self._stamp = frame, time.time()

    def latest(self) -> tuple[np.ndarray | None, float]:
        """The newest frame and its capture time (None before the first frame)."""
        with self._lock:
            return self._frame, self._stamp

    def close(self) -> None:
        self._stop.set()
        self._thread.join()
        self.cap.release()


class FileCamera:
    """Still images or constant-rate fixture videos, in their stored orientation.

    The caller owns this source across Robot restarts and closes it afterwards.
    Indexed seeking requires a captured-file backend with accurate frame positions.
    """

    def __init__(self, path: Path | None = None):
        self._lock = threading.Lock()
        self._cap = None
        self._frame = None
        self._stamp = time.time()
        if path is not None:
            self.show(path)

    def _release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def show(self, path: Path) -> None:
        with self._lock:
            self._release()
            self._frame = None
            self._stamp = time.time()
            frame = cv2.imread(str(path))
            if frame is not None:
                self._frame = frame
                return
            cap = cv2.VideoCapture(str(path))
            try:
                cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 0)
                fps = cap.get(cv2.CAP_PROP_FPS)
                count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                if (not cap.isOpened() or not math.isfinite(fps) or fps <= 0
                        or not math.isfinite(count) or count < 1 or not count.is_integer()):
                    raise ValueError(f"invalid fixture video: {path}")
                ok, frame = cap.read()
                if not ok or frame is None:
                    raise ValueError(f"cannot decode fixture video: {path}")
            except Exception:
                cap.release()
                raise
            self._cap, self._frame = cap, frame
            self._fps, self._count, self._index = fps, int(count), 0
            self._start = time.monotonic()
            self._anchor = self._stamp = time.time()

    def latest(self) -> tuple[np.ndarray | None, float]:
        with self._lock:
            if self._cap is None and self._frame is not None:
                self._stamp = time.time()  # a still: a live camera repeating an unchanged scene
            if self._cap is not None:
                due = min(int(max(0, time.monotonic() - self._start) * self._fps),
                          self._count - 1)
                if due > self._index:
                    if (due != self._index + 1
                            and not self._cap.set(cv2.CAP_PROP_POS_FRAMES, due)):
                        self._release()
                        raise RuntimeError(f"cannot seek fixture frame {due}")
                    ok, frame = self._cap.read()
                    if not ok or frame is None:
                        self._release()
                        raise RuntimeError(f"cannot decode fixture frame {due}")
                    self._frame, self._index = frame, due
                    self._stamp = self._anchor + due / self._fps
            return self._frame, self._stamp

    def close(self) -> None:
        with self._lock:
            self._release()


if __name__ == "__main__":
    cam = Camera()
    time.sleep(2)
    start, n, last = time.time(), 0, 0.0
    while time.time() - start < 5:
        frame, stamp = cam.latest()
        if stamp != last:
            n, last = n + 1, stamp
        time.sleep(0.002)
    assert frame is not None and frame.shape[:2] == (SIZE[1], SIZE[0]), frame
    cam.close()
    print(f"capture ok: {n / 5:.1f} fps, mean brightness {frame.mean():.0f}")
    cv2.imwrite("/tmp/camera-selftest.jpg", frame)

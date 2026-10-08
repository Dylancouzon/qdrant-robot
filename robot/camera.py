"""Camera source: a thread keeps only the newest frame (upright, BGR), from the USB camera or
from a fixture image for scripted sessions.
"""
import threading
import time
from pathlib import Path

import cv2
import numpy as np

DEVICE = "/dev/video0"
SIZE = (1280, 720)
ROTATE = cv2.ROTATE_180  # the camera is mounted upside down (STATE.md, Robot facts)


class Camera:
    def __init__(self, device: str = DEVICE):
        self.cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, SIZE[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, SIZE[1])
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
            frame = cv2.rotate(frame, ROTATE)
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
    """A fixture image standing in for the camera; `show` changes what it sees."""

    def __init__(self, path: Path | None = None):
        self._frame = cv2.imread(str(path)) if path else None
        self._stamp = time.time()

    def show(self, path: Path) -> None:
        self._frame, self._stamp = cv2.imread(str(path)), time.time()

    def latest(self) -> tuple[np.ndarray | None, float]:
        return self._frame, self._stamp


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

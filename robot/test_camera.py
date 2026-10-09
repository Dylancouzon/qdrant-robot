"""Fixture video pacing, pixel identity, switching, and native capture lifetime."""
import threading
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
import pytest

from robot import camera


@pytest.fixture
def video(tmp_path):
    path = tmp_path / "frames.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (32, 24))
    assert writer.isOpened()
    for i in range(12):
        frame = np.full((24, 32, 3), i * 18, np.uint8)
        frame[:8, :8] = (0, 255, 0)
        writer.write(frame)
    writer.release()
    cap = cv2.VideoCapture(str(path))
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
    cap.release()
    assert len(frames) == 12
    return path, frames


@pytest.fixture
def clock(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(camera.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(camera.time, "time", lambda: 1000 + now[0])
    return now


def test_pace_hold_and_seek_pixels(video, clock):
    path, frames = video
    source = camera.FileCamera(path)
    try:
        for elapsed, index in [(0, 0), (0.09, 0), (0.11, 1), (0.85, 8), (1.15, 11),
                               (50, 11)]:
            clock[0] = elapsed
            frame, stamp = source.latest()
            assert np.array_equal(frame, frames[index])
            assert stamp == pytest.approx(1000 + index / 10)
        assert source.latest()[0][0, 0, 1] > 200  # stored orientation
    finally:
        source.close()


def test_switch_and_release(video, clock, tmp_path):
    path, frames = video
    still = tmp_path / "still.png"
    image = np.full((24, 32, 3), 77, np.uint8)
    assert cv2.imwrite(str(still), image)
    source = camera.FileCamera()
    assert source.latest()[0] is None
    source.show(path)
    cap = source._cap
    clock[0] = 0.5
    source.show(still)
    assert not cap.isOpened()
    assert np.array_equal(source.latest()[0], image)
    assert source.latest()[1] == 1000.5
    source.show(path)
    assert np.array_equal(source.latest()[0], frames[0])
    cap = source._cap
    source.close()
    source.close()
    assert not cap.isOpened()


@pytest.mark.parametrize("property,value", [(cv2.CAP_PROP_FPS, 0),
    (cv2.CAP_PROP_FPS, float("nan")), (cv2.CAP_PROP_FRAME_COUNT, float("inf")),
    (cv2.CAP_PROP_FRAME_COUNT, 0), (cv2.CAP_PROP_FRAME_COUNT, 1.5)])
def test_invalid_metadata_releases(video, monkeypatch, property, value):
    path, _ = video
    native = cv2.VideoCapture(str(path))

    class Capture:
        def set(self, key, value):
            return native.set(key, value)

        def get(self, key):
            return value if key == property else native.get(key)

        def isOpened(self):
            return native.isOpened()

        def release(self):
            native.release()

    monkeypatch.setattr(camera.cv2, "VideoCapture", lambda _: Capture())
    with pytest.raises(ValueError, match="invalid fixture"):
        camera.FileCamera(path)
    assert not native.isOpened()


def test_missing_and_failed_decode(video, clock, monkeypatch, tmp_path):
    with pytest.raises(ValueError):
        camera.FileCamera(tmp_path / "missing.avi")
    path, _ = video
    native = cv2.VideoCapture(str(path))

    class Capture:
        def set(self, key, value):
            return native.set(key, value)

        def get(self, key):
            return native.get(key)

        def isOpened(self):
            return native.isOpened()

        def read(self):
            return native.read() if clock[0] == 0 else (False, None)

        def release(self):
            native.release()

    monkeypatch.setattr(camera.cv2, "VideoCapture", lambda _: Capture())
    source = camera.FileCamera(path)
    clock[0] = 0.11
    with pytest.raises(RuntimeError, match="cannot decode"):
        source.latest()
    assert not native.isOpened()
    assert native.open(str(path))
    with pytest.raises(ValueError, match="cannot decode"):
        camera.FileCamera(path)
    assert not native.isOpened()


def test_concurrent_switch_waits_for_decode(video, clock, monkeypatch, tmp_path):
    path, frames = video
    still = tmp_path / "still.png"
    image = np.full((24, 32, 3), 77, np.uint8)
    assert cv2.imwrite(str(still), image)
    entered, unblock, switching = threading.Event(), threading.Event(), threading.Event()
    native = cv2.VideoCapture(str(path))

    class Capture:
        def set(self, key, value):
            return native.set(key, value)

        def get(self, key):
            return native.get(key)

        def isOpened(self):
            return native.isOpened()

        def read(self):
            if clock[0] > 0:
                entered.set()
                assert unblock.wait(2)
                assert native.isOpened()
            return native.read()

        def release(self):
            native.release()

    def switch():
        switching.set()
        source.show(still)

    monkeypatch.setattr(camera.cv2, "VideoCapture", lambda _: Capture())
    source = camera.FileCamera(path)
    clock[0] = 0.11
    with ThreadPoolExecutor(3) as pool:
        reading = pool.submit(source.latest)
        assert entered.wait(2)
        changing = pool.submit(switch)
        assert switching.wait(2)
        another = pool.submit(source.latest)
        assert native.isOpened() and not changing.done()
        unblock.set()
        assert np.array_equal(reading.result(timeout=2)[0], frames[1])
        changing.result(timeout=2)
        other_frame, _ = another.result(timeout=2)
        assert any(np.array_equal(other_frame, f) for f in (frames[1], image))
    assert np.array_equal(source.latest()[0], image)
    assert not native.isOpened()
    source.close()

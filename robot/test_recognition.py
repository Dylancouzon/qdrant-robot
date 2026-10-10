"""Bounded model-owner lifecycle and source-coordinate mapping, with no model sessions."""
import threading
import time
from types import SimpleNamespace

import numpy as np

from robot.faces import Faces
from robot.recognition import Recognition


def test_priority_latest_slot_and_pause_drains_producer():
    entered, release = threading.Event(), threading.Event()
    seen = []
    def preview(value, epoch):
        if value == 1:
            entered.set()
            assert release.wait(2)
        seen.append(value)
    owner = Recognition(preview, faces=object(), crops=lambda x: x)
    try:
        owner.submit((1,))
        assert entered.wait(2)
        owner.submit((2,))
        owner.submit((3,))
        caller = threading.Thread(target=lambda: owner.call(lambda f, c: seen.append("priority")))
        caller.start()
        deadline = time.monotonic() + 2
        while not owner.requests and time.monotonic() < deadline:
            threading.Event().wait(.001)
        release.set()
        caller.join(2)
        owner.pause()
        assert seen[:2] == [1, "priority"] and 2 not in seen
        before = list(seen)
        owner.submit((4,))
        owner.call(lambda f, c: seen.append("turn"))
        assert seen == [*before, "turn"], "pause drains preview; conversation still works"
    finally:
        release.set()
        owner.close()
    assert not owner.thread.is_alive()


def test_gallery_invalidation_rejects_inflight_publication():
    entered, release = threading.Event(), threading.Event()
    published = []
    def preview(value, epoch):
        entered.set()
        assert release.wait(2)
        if epoch == owner.epoch:
            published.append(value)
    owner = Recognition(preview, faces=object(), crops=lambda x: x)
    try:
        owner.submit((1,))
        assert entered.wait(2)
        caller = threading.Thread(target=lambda: owner.call(lambda f, c: None, mutate=True))
        caller.start()
        deadline = time.monotonic() + 2
        while owner.epoch == 0 and time.monotonic() < deadline:
            threading.Event().wait(.001)
        release.set()
        caller.join(2)
        assert owner.epoch == 1 and published == []
    finally:
        release.set()
        owner.close()


def test_yunet_640_maps_bounds_and_landmarks_to_source():
    faces = Faces.__new__(Faces)
    row = np.array([[10, 20, 30, 40, *range(10), .9]], np.float32)
    sizes = []
    faces.detector = SimpleNamespace(setInputSize=lambda size: sizes.append(size),
                                    detect=lambda image: (None, row.copy()))
    result = faces.detect(np.zeros((720, 1280, 3), np.uint8))
    assert sizes == [(640, 360)]
    np.testing.assert_array_equal(result[0, :14], row[0, :14] * 2)
    assert result[0, 14] == row[0, 14]

"""The booth view with a fake source (every box kind, the strip, the panel): token check,
JPEG parts, the rate cap, one viewer, close."""
import http.client
import socket
import time
import urllib.error
import urllib.request

import numpy as np
import pytest

from robot.view import Screen, View

TOKEN = "s3cret"


def parts(conn: http.client.HTTPResponse, seconds: float) -> list[bytes]:
    """The JPEG parts a stream sends in `seconds` (fewer if it ends)."""
    jpgs, end = [], time.monotonic() + seconds
    while time.monotonic() < end and (line := conn.readline()):
        if line.startswith(b"Content-Length:"):
            size = int(line.split(b":")[1])
            conn.readline()  # the blank line before the body
            jpgs.append(conn.read(size))
    return jpgs


def test_view() -> None:
    frame = np.zeros((720, 1280, 3), np.uint8)
    screen = Screen([(0, 0, 400, 700, "", "person"), (100, 100, 300, 300, "???", "focus"),
                     (500, 100, 600, 200, "Dylan's mug", "known"),
                     (700, 100, 800, 200, "", "other"),
                     (900, 100, 1000, 200, "Dylan's phone?", "guess")], "Thinking",
                    [(time.time(), "Remembered: Dylan's mug")],
                    {"shards": ["things", "memory"], "ms": 3.2,
                     "hits": [("Dylan's mug", 0.91), ("seen: a mug", None)]})
    view = View(lambda: (frame, screen), 0, TOKEN, fps=20)
    url = f"http://127.0.0.1:{view.port}/"
    try:
        for bad in ("", "?token=wrong"):
            with pytest.raises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(url + bad, timeout=5)
            assert e.value.code == 403
        first = urllib.request.urlopen(f"{url}?token={TOKEN}", timeout=5)
        assert first.headers["Content-Type"].startswith("multipart/x-mixed-replace")
        jpgs = parts(first, 1.0)
        assert jpgs[0][:2] == b"\xff\xd8" and jpgs[0][-2:] == b"\xff\xd9", "a whole JPEG"
        assert 10 <= len(jpgs) <= 22, f"{len(jpgs)} parts in 1 s at a 20 fps cap"
        second = urllib.request.urlopen(f"{url}?token={TOKEN}", timeout=5)
        assert parts(second, 0.3), "a second viewer streams"
        first.read()  # returns at the end of the stream (else times out): the first is replaced
    finally:
        view.close()
    with pytest.raises(ConnectionRefusedError):
        socket.create_connection(("127.0.0.1", view.port), timeout=2)


def test_live_state_preserves_stream_and_real_text():
    import json
    screen = Screen(status="Thinking", transcript=[{"question": "Where is it?", "answer": "I see"}],
                    evidence={"memory_ids": [17], "knowledge": ["An actual stored fact"]})
    view = View(lambda: (np.zeros((60, 100, 3), np.uint8), screen), 0, TOKEN, fps=5)
    url = f"http://127.0.0.1:{view.port}"
    try:
        stream = urllib.request.urlopen(f"{url}/?token={TOKEN}", timeout=2)
        with pytest.raises(urllib.error.HTTPError) as denied:
            urllib.request.urlopen(f"{url}/state?token=wrong", timeout=2)
        assert denied.value.code == 403
        with urllib.request.urlopen(f"{url}/state?token={TOKEN}", timeout=2) as response:
            state = json.load(response)
        assert state["transcript"] == screen.transcript
        assert state["evidence"] == screen.evidence and state["status"] == "Thinking"
        assert b"Content-Length:" in stream.read(120), "state requests keep MJPEG alive"
        stream.close()
    finally:
        view.close()

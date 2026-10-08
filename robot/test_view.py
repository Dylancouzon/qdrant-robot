"""The booth view with a fake source: token check, JPEG parts, the rate cap, one viewer, close."""
import http.client
import socket
import time
import urllib.error
import urllib.request

import numpy as np
import pytest

from robot.view import View

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
    view = View(lambda: (frame, [(100, 100, 300, 300, "cup")]), 0, TOKEN, fps=20)
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

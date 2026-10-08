"""Booth video view: an MJPEG stream of the camera with the boxes and labels of the tracks in view,
behind a token. It draws object labels only, never names, and never writes a frame to disk.
"""
import hmac
import threading
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import cv2
import numpy as np

Box = tuple[int, int, int, int, str]  # x1, y1, x2, y2 in frame pixels, label
Source = Callable[[], tuple[np.ndarray | None, list[Box]]]
COLOR = (0, 200, 255)  # BGR
BOUNDARY = b"frame"


def draw(frame: np.ndarray, boxes: list[Box], width: int) -> bytes:
    """The frame scaled down to `width` with its boxes and labels, as JPEG bytes."""
    scale = min(1.0, width / frame.shape[1])
    img = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    for x1, y1, x2, y2, label in boxes:
        x1, y1, x2, y2 = (round(v * scale) for v in (x1, y1, x2, y2))
        cv2.rectangle(img, (x1, y1), (x2, y2), COLOR, 2)
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
        top = max(y1, th + 8)
        cv2.rectangle(img, (x1, top - th - 8), (x1 + tw + 8, top), COLOR, -1)
        cv2.putText(img, label, (x1 + 4, top - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1,
                    cv2.LINE_AA)
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()


class _Handler(BaseHTTPRequestHandler):
    server: "_Server"

    def do_GET(self) -> None:  # noqa: N802 (http.server's name)
        view = self.server.view
        given = parse_qs(urlparse(self.path).query).get("token", [""])[0]
        if not hmac.compare_digest(given.encode(), view.token):
            self.send_error(403)
            return
        self.send_response(200)
        self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={BOUNDARY.decode()}")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        with view.lock:  # a new viewer replaces the last one
            view.viewer += 1
            me = view.viewer
        due = time.monotonic()
        while not view.stopped.is_set() and view.viewer == me:
            frame, boxes = view.source()
            if frame is not None:
                jpg = draw(frame, boxes, view.width)
                try:
                    self.wfile.write(b"--%s\r\nContent-Type: image/jpeg\r\nContent-Length: %d"
                                     b"\r\n\r\n%s\r\n" % (BOUNDARY, len(jpg), jpg))
                except OSError:  # the viewer left
                    return
            due = max(due + 1 / view.fps, time.monotonic())
            view.stopped.wait(due - time.monotonic())

    def log_message(self, *args) -> None:
        pass  # the request line carries the token: never log it


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    view: "View"


class View:
    """Serve `source()` as MJPEG on http://host:port/?token=TOKEN at most `fps` frames a second.
    `source` returns the newest frame and the boxes of the tracks in view on that frame."""

    def __init__(self, source: Source, port: int, token: str, host: str = "127.0.0.1",
                 fps: float = 10, width: int = 960):
        if not token:
            raise ValueError("the view needs a token")
        self.source, self.token, self.fps, self.width = source, token.encode(), fps, width
        self.lock, self.viewer, self.stopped = threading.Lock(), 0, threading.Event()
        self.server = _Server((host, port), _Handler)
        self.server.view = self
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, name="view", daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.stopped.set()  # ends the stream within one frame
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

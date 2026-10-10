"""Booth video view: an MJPEG stream of the camera behind a token, with the focus object, named
objects, source-linked face matches, a status strip with memory events, and a memory panel. It
never writes a frame to disk.
"""
import hmac
import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import cv2
import numpy as np

# x1, y1, x2, y2 in frame pixels, label, kind: known, guess, focus, or other
Box = tuple[int, int, int, int, str, str]
BOUNDARY = b"frame"
EVENT_S = 6.0  # how long a memory event stays on the strip
HINT = "Say: Track this as my ..."
FONT, SMALL = cv2.FONT_HERSHEY_SIMPLEX, 0.5
WHITE, BLACK, ORANGE = (255, 255, 255), (0, 0, 0), (0, 140, 255)  # BGR
STYLE = {"known": ((80, 200, 60), 2), "guess": (ORANGE, 1), "focus": (ORANGE, 4),
         "other": ((150, 150, 150), 1)}  # kind -> color, thickness


@dataclass
class Screen:
    """What the view draws over a frame. `memory`: {"shards": [names], "hits": [(text, score
    or None)], "ms": query time} of the last search, or None."""
    boxes: list[Box] = field(default_factory=list)
    status: str = ""  # Listening, Hearing you, Thinking, or Speaking
    events: list[tuple[float, str]] = field(default_factory=list)  # (time.time(), text)
    memory: dict | None = None
    transcript: list[dict] = field(default_factory=list)  # transient, bounded by the Robot
    evidence: dict = field(default_factory=dict)  # supplied to the current answer
    control: dict = field(default_factory=dict)
    ignored_items: list[dict] = field(default_factory=list)
    valid: Callable[[], bool] | None = field(default=None, repr=False, compare=False)
    source: tuple = field(default=(), repr=False, compare=False)  # exact selection for retries


Source = Callable[..., tuple[np.ndarray | None, Screen]]


def _label(img: np.ndarray, text: str, x: int, y: int, color: tuple, scale: float = 0.6) -> None:
    """`text` on a filled tag of `color` with its bottom-left corner at (x, y)."""
    (tw, th), _ = cv2.getTextSize(text, FONT, scale, 1)
    x = max(0, min(x, img.shape[1] - tw - 8))
    y = max(y, th + 8)
    cv2.rectangle(img, (x, y - th - 8), (x + tw + 8, y), color, -1)
    cv2.putText(img, text, (x + 4, y - 5), FONT, scale, BLACK, 1, cv2.LINE_AA)


def _box(img: np.ndarray, box: Box, scale: float) -> None:
    x1, y1, x2, y2 = (round(v * scale) for v in box[:4])
    label, kind = box[4:]
    color, thick = STYLE[kind]
    cv2.rectangle(img, (x1, y1), (x2, y2), color, thick)
    if label:
        _label(img, label, x1, y1, color)
    if kind == "focus":
        _label(img, HINT, x1, min(img.shape[0] - 4, y2 + 24), WHITE, SMALL)


def _lines(img: np.ndarray, lines: list[str], x: int, y: int) -> None:
    """White lines of small text on a darkened panel from (x, y) down."""
    h = 20 * len(lines) + 8
    w = max(cv2.getTextSize(t, FONT, SMALL, 1)[0][0] for t in lines) + 16
    img[y:y + h, x:x + w] //= 3
    for k, t in enumerate(lines):
        cv2.putText(img, t, (x + 8, y + 20 * k + 20), FONT, SMALL, WHITE, 1, cv2.LINE_AA)


def _memory(memory: dict) -> list[str]:
    head = f"Qdrant Edge: {', '.join(memory['shards'])}  {memory['ms']:.1f} ms"
    return [head, *(f"{'  -- ' if score is None else f'{score:.2f}'}  {text[:48]}"
                    for text, score in memory["hits"][:3])]


def draw(frame: np.ndarray, screen: Screen, width: int, now: float) -> bytes:
    """The frame scaled down to `width` with `screen` drawn over it, as JPEG bytes; events
    older than EVENT_S at `now` are left out."""
    scale = min(1.0, width / frame.shape[1])
    img = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    for box in screen.boxes:
        _box(img, box, scale)
    events = [text for t, text in screen.events if now - t < EVENT_S][-2:]
    strip = "   ".join([screen.status, *events]).strip()
    if strip:
        _lines(img, [strip], 0, 0)
    if screen.memory:
        lines = _memory(screen.memory)
        _lines(img, lines, 0, img.shape[0] - 20 * len(lines) - 8)
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()


class _Handler(BaseHTTPRequestHandler):
    server: "_Server"

    def do_GET(self) -> None:  # noqa: N802 (http.server's name)
        view = self.server.view
        given = parse_qs(urlparse(self.path).query).get("token", [""])[0]
        if not hmac.compare_digest(given.encode(), view.token):
            self.send_error(403)
            return
        if urlparse(self.path).path == "/state":
            _, screen = view.state()
            data = json.dumps({"status": screen.status, "transcript": screen.transcript,
                               "evidence": screen.evidence, "memory": screen.memory,
                               "control": screen.control,
                               "ignored_items": screen.ignored_items}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self._stream(view)

    def _stream(self, view):
        self.send_response(200)
        self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={BOUNDARY.decode()}")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        with view.lock:  # a new viewer replaces the last one
            view.viewer += 1
            me = view.viewer
        view.wake()
        def cancelled():
            return view.stopped.is_set() or view.viewer != me
        due = time.monotonic()
        while not cancelled():
            due = max(due, time.monotonic()) + 1 / view.fps
            previous = None
            while not cancelled():
                frame, screen = view.source(deadline=due, cancel=cancelled)
                selected = screen.source or (id(frame),)
                if cancelled() or frame is None or selected == previous:
                    break
                previous = selected
                jpg = draw(frame, screen, view.width, time.time())
                with view.lock:  # viewer ownership and the source commit are checked together
                    valid = not cancelled() and (not screen.valid or screen.valid())
                if valid and not cancelled():
                    try:
                        self.wfile.write(b"--%s\r\nContent-Type: image/jpeg\r\nContent-Length: %d"
                                         b"\r\n\r\n%s\r\n" % (BOUNDARY, len(jpg), jpg))
                    except OSError:  # the viewer left
                        return
                    break
                if time.monotonic() >= due:
                    break
            if cancelled():
                break
            view.stopped.wait(max(0, due - time.monotonic()))

    def do_POST(self) -> None:  # noqa: N802
        view = self.server.view
        parsed = urlparse(self.path)
        token = parse_qs(parsed.query).get("token", [""])[0]
        origin = f"http://127.0.0.1:{view.port}"
        if not hmac.compare_digest(token.encode(), view.token) or \
                self.headers.get("Host") != origin.removeprefix("http://") or \
                self.headers.get("Origin") != origin:
            self.send_error(403)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4096 or parsed.path not in ("/ignore", "/restore"):
                raise ValueError
            data = json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            self.send_error(400)
            return
        accepted = view.action and view.action(parsed.path[1:], data)
        self.send_response(202 if accepted else 409)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args) -> None:
        pass  # the request line carries the token: never log it


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    view: "View"


class View:
    """Serve `source()` as MJPEG on http://host:port/?token=TOKEN at most `fps` frames a second.
    `source` returns the newest frame and what to draw over it."""

    def __init__(self, source: Source, port: int, token: str, host: str = "127.0.0.1",
                 fps: float = 15, width: int = 960, action=None, state=None, wake=lambda: None):
        if not token:
            raise ValueError("the view needs a token")
        self.action = action
        self.state = state or source
        self.wake = wake
        self.source, self.token, self.fps, self.width = source, token.encode(), fps, width
        self.lock, self.viewer, self.stopped = threading.Lock(), 0, threading.Event()
        self.server = _Server((host, port), _Handler)
        self.server.view = self
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, name="view", daemon=True)
        self.thread.start()

    def close(self) -> None:
        with self.lock:
            self.stopped.set()  # ends the stream within one frame
        self.wake()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

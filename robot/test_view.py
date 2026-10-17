"""The booth view with a fake source (every box kind, the strip, the panel): token check,
JPEG parts, the rate cap, one viewer, close."""
import http.client
import socket
import threading
import time
import urllib.error
import urllib.request

import numpy as np
import pytest

from robot.view import Screen, View, draw

TOKEN = "s3cret"


def test_retrieval_evidence_stays_out_of_the_camera_image():
    frame = np.zeros((200, 320, 3), np.uint8)
    memory = {"shards": ["seen"], "ms": 12.3, "hits": [("A stored fact", .9)]}
    assert draw(frame, Screen(memory=memory), 320, 0) == draw(frame, Screen(), 320, 0)


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
    screen = Screen([(100, 100, 300, 300, "???", "focus"),
                     (500, 100, 600, 200, "Dylan's mug", "known"),
                     (700, 100, 800, 200, "", "other"),
                     (900, 100, 1000, 200, "Dylan's phone?", "guess")], "Thinking",
                    [(time.time(), "Remembered: Dylan's mug")],
                    {"shards": ["things", "memory"], "ms": 3.2,
                     "hits": [("Dylan's mug", 0.91), ("seen: a mug", None)]})
    view = View(lambda **kw: (frame, screen), 0, TOKEN, fps=20)
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
    view = View(lambda **kw: (np.zeros((60, 100, 3), np.uint8), screen), 0, TOKEN, fps=5)
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


def test_authenticated_item_actions_and_state_publication():
    import json
    calls, displays = [], []
    screen = Screen(control={"session": "test"}, ignored_items=[{"id": "p", "title": "Cup"}])
    view = View(lambda **kw: (displays.append(1), screen), 0, TOKEN,
                action=lambda action, data: calls.append((action, data)) or data.get("valid"),
                state=lambda **kw: (None, screen))
    conn = http.client.HTTPConnection("127.0.0.1", view.port, timeout=2)
    try:
        conn.request("GET", f"/state?token={TOKEN}")
        state = json.loads(conn.getresponse().read())
        assert not displays and state["ignored_items"][0]["title"] == "Cup"
        for token, origin, code in (("wrong", f"http://127.0.0.1:{view.port}", 403),
                                    (TOKEN, "https://evil.test", 403),
                                    (TOKEN, f"http://127.0.0.1:{view.port}", 202)):
            conn.request("POST", f"/ignore?token={token}", json.dumps({"valid": True}),
                         {"Origin": origin})
            response = conn.getresponse()
            assert response.status == code
            response.read()
        assert calls == [("ignore", {"valid": True})]
    finally:
        conn.close()
        view.close()


def test_one_stream_deadline_includes_source_work_and_encoding(monkeypatch):
    from robot import view as module
    original = module.draw
    def slow_draw(*args):
        time.sleep(.025)
        return original(*args)
    def source(**kw):
        time.sleep(.025)
        return np.zeros((40, 80, 3), np.uint8), Screen()
    monkeypatch.setattr(module, "draw", slow_draw)
    view = View(source, 0, TOKEN, fps=10)
    try:
        conn = urllib.request.urlopen(f"http://127.0.0.1:{view.port}/?token={TOKEN}", timeout=2)
        assert 9 <= len(parts(conn, 1)) <= 12, "source work and encoding share the 10Hz deadline"
        conn.close()
    finally:
        view.close()


def test_final_validation_discards_encoded_frame(monkeypatch):
    from robot import view as module
    entered, release = threading.Event(), threading.Event()
    calls = []
    original = module.draw
    def source(**kw):
        index = len(calls)
        calls.append(time.monotonic())
        return np.full((40, 80, 3), 50 if index == 0 else 150, np.uint8), \
            Screen(valid=lambda **kw: index > 0)
    def draw(*args):
        if len(calls) == 1:
            entered.set()
            assert release.wait(2)
        return original(*args)
    monkeypatch.setattr(module, "draw", draw)
    view = View(source, 0, TOKEN, fps=2)
    try:
        conn = urllib.request.urlopen(f"http://127.0.0.1:{view.port}/?token={TOKEN}", timeout=2)
        assert entered.wait(1)
        release.set()
        jpg = parts(conn, .3)[0]
        decoded = module.cv2.imdecode(np.frombuffer(jpg, np.uint8), module.cv2.IMREAD_COLOR)
        assert decoded.mean() == 150, "the rejected encoded frame is never sent"
        assert calls[1] - calls[0] < .25, "a different source retries before the 500ms deadline"
        assert calls[2] - calls[0] >= .45, "successful emission ends retries and retains the cap"
        conn.close()
    finally:
        release.set()
        view.close()


def test_multiple_rejections_then_no_input_stops_retries_and_closes(monkeypatch):
    from robot import view as module
    waiting = threading.Event()
    calls, draws = [], []
    original = module.draw
    def source(**kw):
        index = len(calls)
        calls.append(time.monotonic())
        if index < 2:
            return np.zeros((40, 80, 3), np.uint8), Screen(valid=lambda **kw: False)
        if index >= 3:
            waiting.set()
        return None, Screen()
    def draw(*args):
        draws.append(1)
        return original(*args)
    monkeypatch.setattr(module, "draw", draw)
    view = View(source, 0, TOKEN, fps=5)
    try:
        conn = urllib.request.urlopen(f"http://127.0.0.1:{view.port}/?token={TOKEN}", timeout=2)
        assert waiting.wait(1)
        assert len(calls) == 4 and len(draws) == 2
        assert calls[2]-calls[0] < .1
        assert calls[3]-calls[0] >= .19, "empty input ends retries until the pacing deadline"
        view.close()
        assert conn.read() == b"" and len(calls) == 4
    finally:
        if not view.stopped.is_set():
            view.close()


def test_unchanged_rejected_source_is_encoded_once_per_period(monkeypatch):
    from robot import view as module
    frame = np.zeros((40, 80, 3), np.uint8)
    draws = []
    original = module.draw
    def draw(*args):
        draws.append(time.monotonic())
        return original(*args)
    monkeypatch.setattr(module, "draw", draw)
    view = View(lambda **kw: (frame, Screen(valid=lambda **kw: False)), 0, TOKEN, fps=5)
    try:
        conn = urllib.request.urlopen(f"http://127.0.0.1:{view.port}/?token={TOKEN}", timeout=2)
        time.sleep(.45)
        view.close()
        assert conn.read() == b"" and 2 <= len(draws) <= 3
        assert all(b-a >= .19 for a,b in zip(draws,draws[1:], strict=False))
    finally:
        if not view.stopped.is_set():
            view.close()


def test_viewer_replacement_during_encoding_does_not_consume_old_viewer(monkeypatch):
    from robot import view as module
    entered, release = threading.Event(), threading.Event()
    consumed, calls = [], []
    original = module.draw
    def source(**kw):
        index = len(calls)
        calls.append(index)
        return np.full((40, 80, 3), 50 if index == 0 else 150, np.uint8), \
            Screen(valid=lambda **kw: consumed.append(index) or True)
    def draw(frame, *args):
        if frame.mean() == 50:
            entered.set()
            assert release.wait(2)
        return original(frame, *args)
    monkeypatch.setattr(module, "draw", draw)
    view = View(source, 0, TOKEN, fps=5)
    url = f"http://127.0.0.1:{view.port}/?token={TOKEN}"
    try:
        first = urllib.request.urlopen(url, timeout=2)
        assert entered.wait(1)
        second = urllib.request.urlopen(url, timeout=2)
        release.set()
        assert first.read() == b""
        assert parts(second, .1) and 0 not in consumed
        view.close()
        second.read()
    finally:
        release.set()
        if not view.stopped.is_set():
            view.close()


@pytest.mark.parametrize("fps", [10, 15])
@pytest.mark.parametrize("offset", [.075, .008, .041])
def test_completion_phase_and_encoding_margin_on_actual_stream(monkeypatch, fps, offset):
    import json
    from robot import view as module
    origin, published = [], [-1]
    condition = threading.Condition()
    frames = [np.full((40, 80, 3), i, np.uint8) for i in range(20)]
    original = module.draw
    def wake():
        with condition:
            condition.notify_all()
    def source(deadline, cancel):
        with condition:
            now = time.monotonic()
            if not origin:
                origin.append(now)
            index = int(np.floor((now-origin[0]-offset)/.133))+1
            while index <= published[0] and not cancel() and now < deadline:
                completion = origin[0]+offset+index*.133
                condition.wait(timeout=max(0, min(completion, deadline)-now))
                now = time.monotonic()
                index = int(np.floor((now-origin[0]-offset)/.133))+1
        def valid():
            published[0] = index
            return True
        return frames[index], Screen(source=(index,), valid=valid)
    def draw(frame, *args):
        time.sleep(.005 if int(frame.mean()) % 2 else .007)
        return original(frame, *args)
    monkeypatch.setattr(module, "draw", draw)
    view = View(source, 0, TOKEN, fps=fps, wake=wake)
    changes = []
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{view.port}/?token={TOKEN}",
                                    timeout=2) as conn:
            end = time.monotonic()+1
            while time.monotonic() < end:
                line = conn.readline()
                assert line, "the authenticated stream remains live"
                if line.startswith(b"Content-Length:"):
                    size = int(line.split(b":")[1])
                    conn.readline()
                    jpg = conn.read(size)
                    received = time.monotonic()
                    image = module.cv2.imdecode(np.frombuffer(jpg, np.uint8),
                                               module.cv2.IMREAD_COLOR)
                    index = round(float(image.mean()))
                    if not changes or changes[-1][0] != index:
                        changes.append((index, received))
        holds = [b[1]-a[1] for a,b in zip(changes, changes[1:], strict=False)]
        assert len(holds) >= 5
        maximum = max(holds)
        print(json.dumps({"fps": fps, "completion_ms": 133, "offset_ms": 1000*offset,
                          "encoding_ms": [5, 7], "max_received_hold_ms": 1000*maximum,
                          "hold_margin_ms": 200-1000*maximum}))
        assert all(b[0] > a[0] for a,b in zip(changes, changes[1:], strict=False))
        assert fps == 10 or maximum < .2, "selected 66.7ms presentation leaves encoding margin"
    finally:
        view.close()


def test_viewer_replacement_cannot_interleave_with_final_source_commit():
    entered, release, second_source = threading.Event(), threading.Event(), threading.Event()
    calls, ownership = [], []
    def source(**kw):
        index = len(calls)
        calls.append(index)
        if index:
            second_source.set()
        def valid():
            before = view.viewer
            if index == 0:
                entered.set()
                assert release.wait(2)
            ownership.append((before, view.viewer))
            return True
        return np.zeros((40, 80, 3), np.uint8), Screen(valid=valid)
    view = View(source, 0, TOKEN, fps=5)
    url = f"http://127.0.0.1:{view.port}/?token={TOKEN}"
    try:
        first = urllib.request.urlopen(url, timeout=2)
        assert entered.wait(1)
        second = urllib.request.urlopen(url, timeout=2)
        assert not second_source.wait(.02) and view.viewer == 1
        release.set()
        assert second_source.wait(1) and parts(second, .1)
        assert all(before == after for before, after in ownership)
        assert ownership[0] == (1, 1) and ownership[-1] == (2, 2)
        first.read()
        view.close()
        second.read()
    finally:
        release.set()
        if not view.stopped.is_set():
            view.close()


def test_viewer_replacement_and_close_cancel_waiting_without_consuming():
    condition, entered = threading.Condition(), threading.Event()
    consumed = []
    def wake():
        with condition:
            condition.notify_all()
    def source(deadline, cancel):
        with condition:
            entered.set()
            condition.wait_for(cancel, timeout=max(0, deadline-time.monotonic()))
        return np.zeros((40, 80, 3), np.uint8), Screen(valid=lambda: consumed.append(1) or True)
    view = View(source, 0, TOKEN, fps=1, wake=wake)
    url = f"http://127.0.0.1:{view.port}/?token={TOKEN}"
    try:
        first = urllib.request.urlopen(url, timeout=2)
        assert entered.wait(1)
        entered.clear()
        second = urllib.request.urlopen(url, timeout=2)
        assert first.read() == b"" and entered.wait(1)
        view.close()
        assert second.read() == b"" and not consumed
    finally:
        if not view.stopped.is_set():
            view.close()


def test_settings_endpoint_validates_and_publishes_live_settings(tmp_path, monkeypatch):
    import io
    import json
    from email.message import Message
    from types import SimpleNamespace
    from robot.main import Robot
    from robot import main
    from robot.settings import DEFAULTS, Settings
    from robot.view import _Handler
    config = Settings(tmp_path / "settings.json")
    monkeypatch.setattr(main, "settings", config)
    robot = Robot.__new__(Robot)
    view = SimpleNamespace(port=8090, token=TOKEN.encode(), action=robot._control,
        state=lambda: (None, Screen(settings=config.snapshot(), window={"active": False})))
    handler = _Handler.__new__(_Handler)
    handler.server = SimpleNamespace(view=view)
    replies = []
    handler.send_response = replies.append
    handler.send_error = replies.append
    handler.send_header = lambda *args: None
    handler.end_headers = lambda: None
    def post(token, data, code):
        body = json.dumps(data).encode()
        handler.path = f"/settings?token={token}"
        handler.headers = Message()
        handler.headers["Origin"] = "http://127.0.0.1:8090"
        handler.headers["Host"] = "127.0.0.1:8090"
        handler.headers["Content-Length"] = str(len(body))
        handler.rfile = io.BytesIO(body)
        handler.do_POST()
        assert replies[-1] == code
    post("wrong", {"name": "match", "value": .9}, 403)
    post(TOKEN, {"name": "match", "value": .9}, 202)
    post(TOKEN, {"name": "match", "value": .1}, 400)
    post(TOKEN, {"name": "missing", "value": .9}, 400)
    post(TOKEN, [], 400)
    handler.path = f"/state?token={TOKEN}"
    handler.wfile = io.BytesIO()
    handler.do_GET()
    state = json.loads(handler.wfile.getvalue())
    assert state["settings"]["match"] == .9 and not state["window"]["active"]
    assert Settings(config.path).match == .9
    post(TOKEN, {"reset": True}, 202)
    assert config.snapshot() == DEFAULTS



def test_memory_and_thumbnail_routes():
    import io
    import json
    import uuid
    from types import SimpleNamespace
    from robot.view import _Handler
    ident = str(uuid.uuid4())
    objects = [{"id": ident, "label": "Ana's mouse", "owner_label": "Ana",
                "views": [{"id": ident, "time": 1, "source": "taught"}],
                "last_seen": None, "sightings": 0}]
    looked_up = []
    view = SimpleNamespace(token=TOKEN.encode(), memory=lambda: objects,
        memory_map=lambda: {"nodes": objects},
        thumb=lambda value: looked_up.append(value) or (
            b"\xff\xd8saved" if value == ident else None))
    handler = _Handler.__new__(_Handler)
    handler.server = SimpleNamespace(view=view)
    codes, headers = [], {}
    handler.send_response = codes.append
    handler.send_error = codes.append
    handler.send_header = lambda key, value: headers.update({key: value})
    handler.end_headers = lambda: None
    def get(path):
        handler.path, handler.wfile = path, io.BytesIO()
        handler.do_GET()
        return codes[-1], handler.wfile.getvalue()
    code, data = get(f"/memory?token={TOKEN}")
    assert code == 200 and json.loads(data) == objects
    code, data = get(f"/memory_map?token={TOKEN}")
    assert code == 200 and json.loads(data) == {"nodes": objects}
    assert get("/memory_map")[0] == 403
    assert get(f"/thumb?token={TOKEN}&view={ident}") == (200, b"\xff\xd8saved")
    assert headers["Content-Type"] == "image/jpeg"
    assert get(f"/thumb?token={TOKEN}&view={uuid.uuid4()}")[0] == 404
    before = len(looked_up)
    for value in ("../../secret.jpg", ""):
        assert get(f"/thumb?token={TOKEN}&view={value}")[0] == 404
    assert len(looked_up) == before, "Path-like IDs never reach the thumbnail lookup"
    assert get("/memory")[0] == 403
    assert get(f"/thumb?view={ident}")[0] == 403


@pytest.mark.parametrize("action", ["forget_object", "remove_view", "stop_head", "resume_head"])
def test_control_post_routes(action):
    import io
    from types import SimpleNamespace
    from robot.view import _Handler
    calls = []
    handler = _Handler.__new__(_Handler)
    handler.server = SimpleNamespace(view=SimpleNamespace(
        port=8090, token=TOKEN.encode(),
        action=lambda name, data: calls.append((name, data)) or False))
    handler.path = f"/{action}?token={TOKEN}"
    handler.headers = {"Host": "127.0.0.1:8090", "Origin": "http://127.0.0.1:8090",
                       "Content-Length": "2"}
    handler.rfile = io.BytesIO(b"{}")
    codes = []
    handler.send_response = codes.append
    handler.send_header = lambda *args: None
    handler.end_headers = lambda: None
    handler.do_POST()
    assert calls == [(action, {})] and codes == [409]

"""Exercise the session lifecycle, owned cleanup, and the page proxy without a Jetson."""
import io
import signal
import subprocess
import sys
import threading
import time
import types
from pathlib import Path
import pytest

import talk


def wait_until(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    pytest.fail("Session did not reach the expected state")


@pytest.fixture
def session(monkeypatch):
    commands = []
    popen = subprocess.Popen
    warm = threading.Event()

    def remote(script):
        commands.append(script)
        if script.startswith("readlink"):
            return f"{talk.BASE}/releases/test-release"
        if "systemctl stop" in script:
            return ""
        if "journalctl" in script:
            # Journal output can include the previous invocation during cold start.
            return "active\nlistening"
        raise AssertionError(script)

    def launch(args, **kwargs):
        if args[0] == "ssh":
            return popen([sys.executable, "-c", "import time; time.sleep(30)"], **kwargs)
        raise AssertionError(args)

    monkeypatch.setattr(talk, "remote", remote)
    monkeypatch.setattr(talk, "command", lambda args, **_: commands.append(args) or "")
    monkeypatch.setattr(talk.subprocess, "Popen", launch)
    instance = talk.Session("test-release")
    def open_view(path):
        assert path == "/state"
        commands.append("probe view")
        if not warm.is_set():
            raise ConnectionRefusedError("The new view server is still warming up")
        return types.SimpleNamespace(close=lambda: None), types.SimpleNamespace(status=200)
    monkeypatch.setattr(instance, "open_view", open_view)
    yield instance, commands, warm
    instance.stop()
    if instance.worker:
        instance.worker.join(5)


def test_old_listening_log_cannot_publish_an_unreachable_video(session):
    instance, commands, warm = session
    instance.start()
    wait_until(lambda: "probe view" in commands or instance.snapshot()["view_ready"])
    assert not instance.snapshot()["view_ready"], "old logs cannot prove endpoint readiness"
    warm.set()
    wait_until(lambda: instance.snapshot()["view_ready"])


def test_stop_during_endpoint_probe_cannot_show_the_video(session, monkeypatch):
    instance, _, _ = session
    entered, release, closed = threading.Event(), threading.Event(), threading.Event()
    def open_view(path):
        entered.set()
        assert release.wait(2)
        return types.SimpleNamespace(close=closed.set), types.SimpleNamespace(status=200)
    monkeypatch.setattr(instance, "open_view", open_view)
    instance.start()
    assert entered.wait(2)
    instance.stop()
    release.set()
    instance.worker.join(5)
    assert closed.is_set() and not instance.worker.is_alive()
    assert not instance.snapshot()["view_ready"] and instance.snapshot()["phase"] == "Idle"


def test_stop_during_warmup_never_shows_the_view(session):
    instance, commands, _ = session
    instance.start()
    wait_until(lambda: instance.snapshot()["phase"].startswith("Warming"))
    assert not instance.snapshot()["view_ready"]
    instance.stop()
    instance.worker.join(5)
    assert not instance.worker.is_alive()
    assert instance.snapshot()["phase"] == "Idle"
    assert any("systemctl stop qr-robot" in c for c in commands if isinstance(c, str))


def test_repeated_start_stop_reaps_before_next_start(session):
    instance, commands, warm = session
    warm.set()
    for _ in range(2):
        instance.start()
        wait_until(lambda: instance.snapshot()["phase"] == "Listening")
        first_worker = instance.worker
        instance.start()
        assert instance.worker is first_worker
        instance.stop()
        first_worker.join(5)
        assert not first_worker.is_alive()
        assert instance.snapshot()["phase"] == "Idle"
    starts = [c for c in commands if isinstance(c, list)]
    assert len(starts) == 2 and starts[0][2:4] == ["run", "robot"]
    assert sum("systemctl stop" in c for c in commands if isinstance(c, str)) == 2


def test_reap_kills_stalled_native_child():
    child = subprocess.Popen([sys.executable, "-u", "-c",
                              "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); "
                              "print('ready',flush=True); time.sleep(30)"], stdout=subprocess.PIPE)
    assert child.stdout.readline() == b"ready\n"
    talk.reap(child)
    assert child.returncode == -signal.SIGKILL
    child.stdout.close()


def test_listener_failure_reports_error_and_leaves_the_robot_alone(session, monkeypatch):
    instance, commands, _ = session
    original = talk.remote
    monkeypatch.setattr(talk, "remote", lambda script: "failed\nmodel error" if
                        "journalctl" in script else original(script))
    instance.start()
    wait_until(lambda: not instance.snapshot()["active"])
    assert "Jetson session stopped" in instance.snapshot()["error"]
    assert not any("systemctl stop" in c for c in commands if isinstance(c, str))


def test_losing_the_tunnel_or_page_never_stops_the_robot(session):
    instance, commands, warm = session
    warm.set()
    instance.start()
    wait_until(lambda: instance.snapshot()["phase"] == "Listening")
    instance.stopped.set()  # what the page does on exit: detach
    instance.worker.join(5)
    assert not instance.snapshot()["active"] and instance.unit is None
    assert not any("systemctl stop" in c for c in commands if isinstance(c, str))


def test_start_attaches_to_a_running_robot_without_starting_another(session, monkeypatch):
    instance, commands, warm = session
    warm.set()
    original = talk.remote

    def running(script):
        if script.startswith("readlink"):
            return f"{talk.BASE}/releases/test-release\n{talk.UNIT}"
        if "systemctl show" in script and "Environment" in script:
            return "HOME=/home/qdrant ROBOT_RELEASE=test-release ROBOT_VIEW_TOKEN=abc123"
        return original(script)

    monkeypatch.setattr(talk, "remote", running)
    instance.start()
    wait_until(lambda: instance.snapshot()["phase"] == "Listening")
    assert instance.view_token == "abc123"
    assert not [c for c in commands if isinstance(c, list)], "no second robot started"


def test_failed_cleanup_blocks_start_until_stop_retry(session, monkeypatch):
    instance, _, warm = session
    warm.set()
    original = talk.remote

    def fail_stop(script):
        if "systemctl stop" in script:
            raise RuntimeError("SSH connection lost")
        return original(script)

    monkeypatch.setattr(talk, "remote", fail_stop)
    instance.start()
    wait_until(lambda: instance.snapshot()["phase"] == "Listening")
    instance.stop()
    instance.worker.join(5)
    assert instance.unit and instance.snapshot()["active"]
    worker = instance.worker
    instance.start()
    assert instance.worker is worker
    monkeypatch.setattr(talk, "remote", original)
    instance.stop()
    instance.worker.join(5)
    assert instance.unit is None and not instance.snapshot()["active"]


def test_collected_remote_unit_is_safe_to_clean(monkeypatch):
    instance = talk.Session("test-release")
    instance.unit = "qr-robot.service"
    scripts = []

    def remote(script):
        scripts.append(script)
        # Execute only the cleanup shell against a fake systemctl with absent-unit behavior.
        prefix = 'systemctl() { echo not-found; }; sudo() { return 99; }; '
        result = subprocess.run(["bash", "-c", prefix + script], capture_output=True)
        assert result.returncode == 0
        return ""

    monkeypatch.setattr(talk, "remote", remote)
    assert instance.cleanup_remote() == ""
    assert instance.unit is None and "LoadState" in scripts[0]


@pytest.mark.parametrize("host,origin,token,code", [
    ("127.0.0.1:8765", "http://127.0.0.1:8765", "secret", 200),
    ("evil.test", "http://127.0.0.1:8765", "secret", 403),
    ("127.0.0.1:8765", "https://evil.test", "secret", 403),
    ("127.0.0.1:8765", "http://127.0.0.1:8765", "wrong", 403),
    ("127.0.0.1:8765", "", "secret", 403),
])
def test_control_requires_local_host_origin_and_token(host, origin, token, code):
    from email.message import Message
    handler = talk.Handler.__new__(talk.Handler)
    handler.origin, handler.token = "http://127.0.0.1:8765", "secret"
    handler.path = "/start"
    handler.headers = Message()
    handler.headers["Host"], handler.headers["Origin"] = host, origin
    handler.headers["X-Session-Token"] = token
    calls, replies = [], []
    handler.session = types.SimpleNamespace(start=lambda: calls.append("start"),
                                            stop=lambda: None)
    handler.reply = lambda *args: replies.append(args)
    handler.do_POST()
    assert replies[0][0] == code
    assert calls == (["start"] if code == 200 else [])


def test_view_proxy_keeps_remote_token_server_side():
    import http.client
    from http.server import ThreadingHTTPServer
    from robot.view import Screen, View
    view = View(lambda **kw: (None, Screen(status="Thinking",
                                          transcript=[{"answer": "A real reply"}])),
                0, "test-only-view-token")
    session = talk.Session("test-release")
    session.view_port, session.view_token = view.port, "test-only-view-token"
    session.update(view_ready=True)
    talk.Handler.session, talk.Handler.token = session, "local-page-token"
    server = ThreadingHTTPServer(("127.0.0.1", 0), talk.Handler)
    talk.Handler.origin = f"http://127.0.0.1:{server.server_port}"
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=2)
    try:
        connection.request("GET", "/")
        page = connection.getresponse()
        assert "SameSite=Strict" in page.headers["Set-Cookie"]
        assert b"test-only-view-token" not in page.read()
        connection.request("GET", "/robot")
        denied = connection.getresponse()
        assert denied.status == 403
        denied.read()
        connection.request("GET", "/robot", headers={"Cookie": "edgy=local-page-token"})
        state = connection.getresponse()
        assert state.status == 200 and b"A real reply" in state.read()
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        worker.join(2)
        view.close()


def test_workflow_view_token_uses_stdin_and_inherited_environment(monkeypatch):
    import jetson
    calls = []
    monkeypatch.setenv("ROBOT_VIEW_TOKEN", "test-only-secret")
    monkeypatch.setattr(jetson, "remote", lambda script, **_: calls.append(script) or 0)
    assert jetson.run("live-mac-test", ["-m", "robot.main", "--camera-file", "x"], False) == 0
    assert "--preserve-env=ROBOT_VIEW_TOKEN" in calls[0]
    assert "--setenv=ROBOT_VIEW_TOKEN" in calls[0] and "test-only-secret" not in calls[0]
    monkeypatch.undo()
    monkeypatch.setenv("ROBOT_VIEW_TOKEN", "test-only-secret")
    run_calls = []
    monkeypatch.setattr(jetson.subprocess, "run", lambda args, **kw:
                        run_calls.append((args, kw)) or types.SimpleNamespace(returncode=0))
    assert jetson.remote("echo harmless") == 0
    args, kw = run_calls[0]
    assert "test-only-secret" in kw["input"]
    assert all("test-only-secret" not in arg for arg in args)


@pytest.mark.parametrize("path", ["/ignore", "/mute", "/volume", "/settings", "/stop_head",
                                  "/forget_object", "/remove_view"])
def test_item_proxy_requires_cookie_and_forwards_bounded_body(path):
    from email.message import Message
    handler = talk.Handler.__new__(talk.Handler)
    handler.origin, handler.token = "http://127.0.0.1:8765", "secret"
    handler.path = path
    handler.headers = Message()
    for key, value in {"Host": "127.0.0.1:8765", "Origin": handler.origin,
                       "X-Session-Token": "secret", "Content-Length": "2"}.items():
        handler.headers[key] = value
    handler.rfile = io.BytesIO(b"{}")
    replies, forwarded = [], []
    handler.reply = lambda *args: replies.append(args)
    handler.session = types.SimpleNamespace(open_view=lambda path, body: (
        types.SimpleNamespace(close=lambda: None),
        types.SimpleNamespace(status=202)))
    handler.do_POST()
    assert replies[-1][0] == 403
    handler.headers["Cookie"] = "edgy=secret"
    handler.session.open_view = lambda path, body: (forwarded.append((path, body)) or
        types.SimpleNamespace(close=lambda: None), types.SimpleNamespace(status=202))
    handler.do_POST()
    assert replies[-1][0] == 202 and forwarded == [(path, b"{}")]


def test_page_edits_item_lists_in_place_and_offers_no_spoken_ignore():
    page = (Path(talk.__file__).parent / "talk.html").read_text()
    options = page[page.index("function options("):page.index("function items(")]
    assert "replaceChildren" not in options, "a rebuilt list closes an open dropdown"
    assert "Ignore chairs" not in page and "Do not track that" in page


def test_robot_launch_uses_its_own_audio_and_forwards_only_the_view(session):
    instance, commands, warm = session
    warm.set()
    instance.start()
    wait_until(lambda: instance.snapshot()["phase"] == "Listening")
    instance.stop()
    instance.worker.join(5)
    assert [c for c in commands if isinstance(c, list)][0][-2:] == ["-m", "robot.main"]
    assert talk.robot_args("clip.avi") == ["-m", "robot.main", "--camera-file", "clip.avi"]


@pytest.mark.parametrize("camera,calibration,expected", [
    ("/existing/private/fixture.avi", None,
     ["--camera-file", "/existing/private/fixture.avi"]),
    (None, "/existing/servo-mounted.json", ["--servo-calibration", "/existing/servo-mounted.json"]),
    ("fixture.avi", "servo.json",
     ["--camera-file", "fixture.avi", "--servo-calibration", "servo.json"]),
])
def test_explicit_camera_and_calibration_forwarded_through_workflow(
        monkeypatch, camera, calibration, expected):
    instance = talk.Session("release", camera, calibration)
    commands = []
    monkeypatch.setattr(talk, "remote", lambda script: f"{talk.BASE}/releases/release")
    monkeypatch.setattr(talk, "command", lambda args, env=None: commands.append(args))
    monkeypatch.setattr(talk.subprocess, "Popen", lambda *args, **kwargs: (
        (_ for _ in ()).throw(RuntimeError("fake tunnel end"))))
    monkeypatch.setattr(instance, "cleanup_remote", lambda: "")
    instance.run()
    assert commands[0][-len(expected):] == expected


@pytest.mark.parametrize("path", ["/memory", "/memory_map", "/thumb?view=saved"])
def test_memory_proxy_cookie_and_forwarding(path):
    from email.message import Message
    handler = talk.Handler.__new__(talk.Handler)
    handler.origin, handler.token = "http://127.0.0.1:8765", "secret"
    handler.path = path
    handler.headers = Message()
    handler.headers["Host"] = "127.0.0.1:8765"
    replies, forwarded = [], []
    handler.reply = lambda *args: replies.append(args)
    handler.session = types.SimpleNamespace(open_view=lambda value: (
        forwarded.append(value) or types.SimpleNamespace(close=lambda: None),
        types.SimpleNamespace(status=404, headers={"Content-Type": "image/jpeg"},
                              read=lambda: b"missing")))
    handler.do_GET()
    assert replies[-1][0] == 403 and not forwarded
    handler.headers["Cookie"] = "edgy=secret"
    handler.do_GET()
    assert forwarded == [path] and replies[-1] == (404, b"missing", "image/jpeg")


def test_brand_font_is_served_locally():
    from email.message import Message
    handler = talk.Handler.__new__(talk.Handler)
    handler.origin = "http://127.0.0.1:8765"
    handler.path = "/mona-sans.woff2"
    handler.headers = Message()
    handler.headers["Host"] = "127.0.0.1:8765"
    replies = []
    handler.reply = lambda *args: replies.append(args)
    handler.do_GET()
    code, font, kind = replies[0]
    assert code == 200 and kind == "font/woff2" and font.startswith(b"wOF2")

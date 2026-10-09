"""Exercise Mac audio framing and owned session cleanup without microphone capture."""
import io
import signal
import socket
import struct
import subprocess
import sys
import threading
import time
import types

import numpy as np
import pytest

import talk


def test_fragmented_frames_preserve_phrase_order():
    left, right = socket.socketpair()
    phrases = [np.array([1, -2, 3], dtype="<i2"), np.array([4, -5], dtype="<i2")]

    def send():
        for pcm in phrases:
            packet = struct.pack("<I", pcm.nbytes) + pcm.tobytes()
            for byte in packet:
                right.sendall(bytes([byte]))
        right.close()

    sender = threading.Thread(target=send)
    sender.start()
    with left:
        for expected in phrases:
            np.testing.assert_array_equal(talk.frame(left), expected)
        with pytest.raises(EOFError):
            talk.frame(left)
    sender.join()


@pytest.mark.parametrize("size", [0, 3, talk.MAX_FRAME + 2])
def test_invalid_header_is_rejected_before_payload(size):
    left, right = socket.socketpair()
    with left, right:
        right.sendall(struct.pack("<I", size))
        with pytest.raises(ValueError):
            talk.frame(left)


@pytest.mark.parametrize("packet", [b"\x04", struct.pack("<I", 4) + b"\x00\x00"])
def test_partial_eof(packet):
    left, right = socket.socketpair()
    with left:
        right.sendall(packet)
        right.close()
        with pytest.raises(EOFError):
            talk.frame(left)


def peer_audio(right, phrases, sent):
    with right:
        for pcm in phrases:
            right.sendall(struct.pack("<I", pcm.nbytes) + pcm.tobytes())
        for _ in range(3):
            data = bytearray()
            while len(data) < talk.CHUNK * 2:
                data.extend(right.recv(talk.CHUNK * 2 - len(data)))
            sent.append(bytes(data))


def native(monkeypatch, muted=False):
    """Fake PortAudio devices; the production audio loop still uses a real socket."""
    opened, played, sent = [], [], []
    playing = threading.Event()
    left, right = socket.socketpair()

    class Stream:
        latency = 0.02

        def __init__(self, **kwargs):
            self.config = kwargs
            self.closed = self.aborted = False
            opened.append(self)

        def start(self):
            pass

        def read(self, count):
            playing.wait(1)
            time.sleep(0.02)
            return np.full((count, 1), 1000, np.int16), False

        def write(self, pcm):
            played.append(pcm.copy())
            playing.set()

        def abort(self):
            self.aborted = True

        def close(self):
            self.closed = True

    devices = [{"name": talk.INPUT, "max_input_channels": 1, "max_output_channels": 0},
               {"name": talk.OUTPUT, "max_input_channels": 0, "max_output_channels": 2}]
    sd = types.SimpleNamespace(query_devices=lambda: devices,
                               check_input_settings=lambda **_: None,
                               check_output_settings=lambda **_: None,
                               InputStream=Stream, OutputStream=Stream, PortAudioError=RuntimeError)
    monkeypatch.setitem(sys.modules, "sounddevice", sd)
    monkeypatch.setattr(signal, "signal", lambda *_: None)
    monkeypatch.setattr(sys, "stdin", io.StringIO("mute\n" if muted else ""))
    phrases = [np.full(240, 200, np.int16), np.full(240, 300, np.int16)]

    thread = threading.Thread(target=peer_audio, args=(right, phrases, sent))
    thread.start()
    with pytest.raises((RuntimeError, BrokenPipeError)):
        talk.NativeAudio(left.detach()).run()
    thread.join(2)
    assert not thread.is_alive()
    assert [s.config["device"] for s in opened] == [1, 0]
    assert all(s.closed and s.aborted for s in opened)
    for actual, expected in zip(played, phrases, strict=True):
        np.testing.assert_array_equal(actual, expected)
    return sent


def test_playback_tail_sends_silence_and_releases_streams(monkeypatch):
    assert native(monkeypatch) == [bytes(talk.CHUNK * 2)] * 3


def test_manual_mute_sends_silence(monkeypatch):
    monkeypatch.setattr(talk, "TAIL_S", 0)
    assert native(monkeypatch, muted=True) == [bytes(talk.CHUNK * 2)] * 3


def wait_until(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    pytest.fail("Session did not reach the expected state")


def session_report(warm):
    report = "active\nwaiting for a client on port 7070"
    return report + "\nlistening" if warm.is_set() else report


@pytest.fixture
def session(monkeypatch):
    commands, peers = [], []
    popen = subprocess.Popen
    warm = threading.Event()

    def remote(script):
        commands.append(script)
        if script.startswith("readlink"):
            return f"{talk.BASE}/releases/{talk.RELEASE}"
        if "systemctl stop" in script:
            return ""
        if "journalctl" in script:
            return session_report(warm)
        raise AssertionError(script)

    def launch(args, **kwargs):
        if args[0] == "ssh":
            return popen([sys.executable, "-c", "import time; time.sleep(30)"], **kwargs)
        assert "--audio-fd" in args
        return popen([sys.executable, "-u", "-c",
                      'import time; print(\'{"phase":"Listening"}\', flush=True); time.sleep(30)'],
                     **kwargs)

    def connect(*_, **__):
        with socket.create_server(("127.0.0.1", 0)) as listener:
            left = socket.socket()
            left.connect(listener.getsockname())
            right, _ = listener.accept()
        peers.append(right)
        return left

    monkeypatch.setattr(talk, "remote", remote)
    monkeypatch.setattr(talk, "command", lambda args: commands.append(args) or "")
    monkeypatch.setattr(talk.subprocess, "Popen", launch)
    monkeypatch.setattr(talk.socket, "create_connection", connect)
    instance = talk.Session()
    yield instance, commands, warm
    instance.stop()
    if instance.worker:
        instance.worker.join(5)
    for peer in peers:
        peer.close()


def test_stop_during_warmup_never_opens_audio(session):
    instance, commands, _ = session
    instance.start()
    wait_until(lambda: instance.snapshot()["phase"].startswith("Warming"))
    assert instance.child is None
    instance.stop()
    instance.worker.join(5)
    assert not instance.worker.is_alive()
    assert instance.snapshot()["phase"] == "Idle"
    assert any("systemctl stop qr-live-mac-" in c for c in commands if isinstance(c, str))


def test_repeated_start_stop_reaps_before_next_start(session):
    instance, commands, warm = session
    warm.set()
    children = []
    for _ in range(2):
        instance.start()
        wait_until(lambda: instance.snapshot()["phase"] == "Listening")
        children.append(instance.child)
        first_worker = instance.worker
        instance.start()
        assert instance.worker is first_worker
        instance.mute()
        assert instance.snapshot()["muted"]
        instance.stop()
        first_worker.join(5)
        assert not first_worker.is_alive()
        assert instance.snapshot()["phase"] == "Idle"
    assert all(child.poll() is not None for child in children)
    starts = [c for c in commands if isinstance(c, list)]
    assert len(starts) == 2 and starts[0][3] != starts[1][3]
    assert sum("systemctl stop" in c for c in commands if isinstance(c, str)) == 2


def test_reap_kills_stalled_native_child():
    child = subprocess.Popen([sys.executable, "-u", "-c",
                              "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); "
                              "print('ready',flush=True); time.sleep(30)"], stdout=subprocess.PIPE)
    assert child.stdout.readline() == b"ready\n"
    talk.reap(child)
    assert child.returncode == -signal.SIGKILL
    child.stdout.close()


def test_tail_expires_and_input_resumes(monkeypatch):
    monkeypatch.setattr(talk, "TAIL_S", 0)
    sent = native(monkeypatch)
    assert any(np.frombuffer(block, np.int16).any() for block in sent)


def test_listener_failure_reports_error_and_reaps_owned_unit(session, monkeypatch):
    instance, commands, _ = session
    original = talk.remote
    monkeypatch.setattr(talk, "remote", lambda script: "failed\nmodel error" if
                        "journalctl" in script else original(script))
    instance.start()
    wait_until(lambda: not instance.snapshot()["active"])
    assert "Jetson session stopped" in instance.snapshot()["error"]
    assert instance.unit is None
    assert any("systemctl stop" in c for c in commands if isinstance(c, str))


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
    instance = talk.Session()
    instance.unit = "qr-live-mac-test.service"
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
                                            mute=lambda: None, stop=lambda: None)
    handler.reply = lambda *args: replies.append(args)
    handler.do_POST()
    assert replies[0][0] == code
    assert calls == (["start"] if code == 200 else [])

#!/usr/bin/env python3
"""Loopback monitor and controls for the robot. The robot hears and speaks through its own USB
audio on the Jetson; `--mac-audio` uses MacBook audio instead, for remote development. All
robot models run on the Jetson."""
import argparse
import contextlib
import http.client
import os
import json
import secrets
import signal
import socket
import struct
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
BASE = "/home/qdrant/qdrant-robot"
INPUT, OUTPUT = "MacBook Pro Microphone", "MacBook Pro Speakers"
RATE_IN, RATE_OUT, CHUNK = 16000, 24000, 1280
MAX_FRAME = RATE_OUT * 2 * 30  # At most 30 seconds of mono PCM per phrase.
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
       "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=2"]


def frame(conn: socket.socket) -> np.ndarray:
    """Read one bounded phrase, including fragmented headers and payloads."""
    def exact(size):
        data = bytearray()
        while len(data) < size:
            part = conn.recv(size - len(data))
            if not part:
                raise EOFError("Robot audio connection closed")
            data.extend(part)
        return data
    size, = struct.unpack("<I", exact(4))
    if not 0 < size <= MAX_FRAME or size % 2:
        raise ValueError(f"Invalid robot audio frame size: {size}")
    return np.frombuffer(exact(size), dtype="<i2")


def devices(sd, microphone=True) -> tuple[int | None, int]:
    found = sd.query_devices()
    chosen = []
    for name, direction in ((INPUT, "input"), (OUTPUT, "output")):
        if direction == "input" and not microphone:
            chosen.append(None)
            continue
        matches = [i for i, d in enumerate(found)
                   if d["name"] == name and d[f"max_{direction}_channels"] > 0]
        if len(matches) != 1:
            raise RuntimeError(f"Expected one {name}; found {len(matches)}")
        chosen.append(matches[0])
    if microphone:
        sd.check_input_settings(device=chosen[0], channels=1, dtype="int16", samplerate=RATE_IN)
    sd.check_output_settings(device=chosen[1], channels=1, dtype="int16", samplerate=RATE_OUT)
    return tuple(chosen)


class NativeAudio:
    """Capture and play one connected stream; the parent can reap native stalls."""

    def __init__(self, fd, microphone=True):
        import sounddevice as sd
        self.sd = sd
        self.microphone = microphone
        self.conn = socket.socket(fileno=fd)
        self.stopped = threading.Event()
        self.failure = ""
        self.streams = []
        self.receiver = None

    @staticmethod
    def emit(**state):
        sys.stdout.write(json.dumps(state) + "\n")
        sys.stdout.flush()

    def halt(self, *_):
        self.stopped.set()
        with contextlib.suppress(OSError):
            self.conn.shutdown(socket.SHUT_RDWR)

    def answers(self):
        out = self.streams[0]
        try:
            while not self.stopped.is_set():
                pcm = frame(self.conn)
                out.write(pcm)
        except (OSError, EOFError, ValueError, self.sd.PortAudioError) as exc:
            if not self.stopped.is_set():
                self.failure = str(exc)
            self.halt()

    def capture(self, mic):
        while not self.stopped.is_set():
            data, overflow = mic.read(CHUNK)
            if overflow:
                raise RuntimeError("Microphone overflow; stop and restart the session")
            self.conn.sendall(data.tobytes())  # the robot silences its own voice and mute
        if self.failure:
            raise RuntimeError(self.failure)

    def silence(self):
        while not self.stopped.wait(CHUNK / RATE_IN):
            self.conn.sendall(bytes(CHUNK * 2))
        if self.failure:
            raise RuntimeError(self.failure)

    def run(self):
        signal.signal(signal.SIGTERM, self.halt)
        try:
            self.emit(phase="Opening MacBook audio")
            incoming, outgoing = devices(self.sd, self.microphone)
            if self.stopped.is_set():
                return
            out = self.sd.OutputStream(device=outgoing, samplerate=RATE_OUT,
                                       channels=1, dtype="int16")
            self.streams.append(out)
            out.start()
            if self.microphone:
                mic = self.sd.InputStream(device=incoming, samplerate=RATE_IN, channels=1,
                                         dtype="int16", blocksize=CHUNK)
                self.streams.append(mic)
                mic.start()
            self.emit(phase="Listening")
            self.receiver = threading.Thread(target=self.answers, daemon=True)
            self.receiver.start()
            self.capture(mic) if self.microphone else self.silence()
        finally:
            self.halt()
            for stream in reversed(self.streams):
                with contextlib.suppress(Exception):
                    stream.abort()
                    stream.close()
            if self.receiver:
                self.receiver.join(2)
            self.conn.close()


def robot_args(mac_audio: bool, camera_file: str | None) -> list[str]:
    """The `robot.main` arguments: its own USB audio, or a Mac client on port 7070."""
    return ["-m", "robot.main", *(["--listen", "7070"] if mac_audio else []),
            *(["--camera-file", camera_file] if camera_file else [])]


def command(args: list[str], env=None) -> str:
    result = subprocess.run(args, capture_output=True, text=True, timeout=30, env=env)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip()[-1500:])
    return result.stdout.strip()


def remote(script: str) -> str:
    return command([*SSH, "robot", script])


def reap(process: subprocess.Popen | None) -> None:
    if process is None:
        return
    if process.poll() is None:
        with contextlib.suppress(ProcessLookupError):
            process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError):
            process.kill()
        process.wait(timeout=2)


class Session:
    """Own one remote session and tunnel, and keep the page reusable after cleanup."""

    def __init__(self, release: str, camera_file: str | None = None, mac_audio: bool = False):
        self.release = release
        self.camera_file, self.mac_audio = camera_file, mac_audio
        self.view_port = self.view_token = None
        self.lock = threading.Lock()
        self.stopped = threading.Event()
        self.worker = None
        self.child = self.reader = self.unit = None
        self.state = dict(phase="Idle", active=False, error="", view_ready=False,
                          microphone=not (mac_audio and camera_file))

    def update(self, **state):
        with self.lock:
            self.state.update(state)

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    def start(self):
        with self.lock:
            if self.state["active"] or (self.worker and self.worker.is_alive()):
                return
            self.stopped.clear()
            self.state.update(phase="Connecting", active=True, error="")
            self.worker = threading.Thread(target=self.run, daemon=True)
            self.worker.start()

    def stop(self):
        self.stopped.set()
        self.update(view_ready=False)
        if self.worker and self.worker.is_alive():
            self.update(phase="Stopping")
        elif self.unit:
            self.update(phase="Stopping")
            self.worker = threading.Thread(target=self.retry_stop, daemon=True)
            self.worker.start()

    def report(self):
        report = remote(f"systemctl is-active {self.unit}; "
                        f"journalctl -u {self.unit} -o cat --no-pager -n 30")
        if not report or report.splitlines()[0] != "active":
            raise RuntimeError(f"Jetson session stopped: {report[-1500:]}")
        return report.splitlines()

    def connect(self, tunnel, port):
        self.update(phase="Waiting for Jetson audio")
        while not self.stopped.wait(0.2):
            if tunnel.poll() is not None:
                message = tunnel.stderr.read().decode().strip()
                raise RuntimeError(message or "SSH tunnel closed")
            if "waiting for a client on port 7070" in self.report():
                try:
                    return socket.create_connection(("127.0.0.1", port), timeout=2)
                except OSError:
                    continue
        return None

    def listen(self, conn):
        """Wait for the robot to warm up, then watch it. With `conn` (Mac audio), the MacBook
        audio child runs meanwhile."""
        if conn:
            conn.settimeout(None)
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.update(phase="Warming up Jetson; microphone off")
        while not self.stopped.wait(0.5):
            if "listening" in self.report():
                break
        if self.stopped.is_set():
            return
        self.update(view_ready=True)
        if conn:
            return self.run_native(conn)
        self.update(phase="Listening")
        while not self.stopped.wait(2):
            self.report()  # raises when the Jetson session stops

    def run_native(self, conn):
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                                  "--audio-fd", str(conn.fileno()),
                                  *(["--no-microphone"] if self.camera_file else [])],
                                 pass_fds=(conn.fileno(),), stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
        with self.lock:
            self.child = child

        def updates():
            for line in child.stdout:
                self.update(**json.loads(line))

        self.reader = threading.Thread(target=updates, daemon=True)
        self.reader.start()
        while not self.stopped.wait(0.1):
            if child.poll() is not None:
                message = child.stderr.read().strip()[-1500:]
                raise RuntimeError(message or "Robot audio disconnected")

    def open_view(self, path, body=None):
        with self.lock:
            if self.stopped.is_set() or not self.state["view_ready"]:
                raise RuntimeError("Camera session is idle")
            port, token = self.view_port, self.view_token
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        try:
            connection.request("POST" if body is not None else "GET",
                               f"{path}?token={token}", body=body,
                               headers={"Host": "127.0.0.1:8090",
                                        "Origin": "http://127.0.0.1:8090",
                                        "Content-Type": "application/json"})
            response = connection.getresponse()
            if response.status not in (200, 202, 409):
                raise RuntimeError("Jetson view is unavailable")
            return connection, response
        except Exception:
            connection.close()
            raise

    def cleanup_remote(self):
        error = ""
        if self.unit:
            try:
                remote(f'load=$(systemctl show {self.unit} -p LoadState --value); '
                       f'[ "$load" = not-found ] || sudo systemctl stop {self.unit} || '
                       f'[ "$(systemctl show {self.unit} -p LoadState --value)" = not-found ]')
                self.unit = None
            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                error = f"Could not stop owned {self.unit}: {exc}. Select Stop to retry."
        return error

    def retry_stop(self):
        error = self.cleanup_remote()
        self.update(phase="Error" if error else "Idle", active=bool(self.unit), error=error)

    def cleanup_local(self, conn, tunnel):
        if conn:
            with contextlib.suppress(OSError):
                conn.shutdown(socket.SHUT_RDWR)
        reap(self.child)
        if self.reader:
            self.reader.join(2)
        if self.child:
            self.child.stdout.close()
            self.child.stderr.close()
        self.child = self.reader = None
        if conn:
            conn.close()
        reap(tunnel)
        if tunnel:
            tunnel.stderr.close()

    def run(self):
        name = f"live-mac-{secrets.token_hex(6)}"
        tunnel = conn = None
        error = ""
        try:
            status = remote(f"readlink -f {BASE}/current; "
                            "systemctl list-units 'qr-*' --state=active --no-legend --plain")
            if status.splitlines() != [f"{BASE}/releases/{self.release}"]:
                raise RuntimeError(f"Jetson must be idle on release {self.release}. "
                                   f"Received: {status}")
            if self.stopped.is_set():
                return
            self.unit = f"qr-{name}.service"
            self.view_token = secrets.token_hex(32)
            command([sys.executable, str(ROOT / "tools/jetson.py"), "run", name,
                     "--", *robot_args(self.mac_audio, self.camera_file)],
                    env={**os.environ, "ROBOT_VIEW_TOKEN": self.view_token})
            with socket.socket() as reserve, socket.socket() as video_reserve:
                reserve.bind(("127.0.0.1", 0))
                video_reserve.bind(("127.0.0.1", 0))
                port, self.view_port = reserve.getsockname()[1], video_reserve.getsockname()[1]
            tunnel = subprocess.Popen([*SSH, "-N", "-o", "ExitOnForwardFailure=yes",
                                       *(["-L", f"127.0.0.1:{port}:127.0.0.1:7070"]
                                         if self.mac_audio else []),
                                       "-L", f"127.0.0.1:{self.view_port}:127.0.0.1:8090", "robot"],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            conn = self.connect(tunnel, port) if self.mac_audio else None
            if conn or not self.mac_audio:
                self.listen(conn)
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            if not self.stopped.is_set():
                error = str(exc)
        finally:
            self.update(phase="Stopping", view_ready=False)
            self.view_port = self.view_token = None
            self.cleanup_local(conn, tunnel)
            cleanup_error = self.cleanup_remote()
            error = "\n".join(filter(None, (error, cleanup_error)))
            self.update(phase="Error" if error else "Idle", active=bool(self.unit), error=error)


class Handler(BaseHTTPRequestHandler):
    session = None
    token = origin = ""

    def reply(self, code, data, kind="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Cache-Control", "no-store")
        if kind.startswith("text/html"):
            self.send_header("Set-Cookie", f"edgy={self.token}; HttpOnly; SameSite=Strict; Path=/")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def allowed(self):
        return (self.headers.get("Host") == self.origin.removeprefix("http://") and
                self.headers.get("Origin", self.origin) == self.origin)

    def do_GET(self):
        if not self.allowed():
            self.reply(403, b"Forbidden")
        elif self.path == "/":
            page = Path(__file__).with_suffix(".html").read_text().replace("TOKEN", self.token)
            self.reply(200, page.encode(), "text/html; charset=utf-8")
        elif self.path in ("/camera", "/robot"):
            cookie = SimpleCookie(self.headers.get("Cookie", "")).get("edgy")
            if cookie is None or not secrets.compare_digest(cookie.value, self.token):
                self.reply(403, b"Forbidden")
                return
            self.proxy_view()
        elif self.path == "/status":
            self.reply(200, json.dumps(self.session.snapshot()).encode())
        else:
            self.reply(404, b"Not found")

    def proxy_view(self):
        connection = None
        try:
            path = "/state" if self.path == "/robot" else "/"
            connection, response = self.session.open_view(path)
            if self.path == "/robot":
                self.reply(200, response.read())
                return
            self.send_response(200)
            self.send_header("Content-Type", response.headers["Content-Type"])
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            while not self.session.stopped.is_set() and (data := response.read1(65536)):
                self.wfile.write(data)
                self.wfile.flush()
        except (OSError, RuntimeError, http.client.HTTPException):
            if connection is None:
                self.reply(503, b"View unavailable; start a session first")
        finally:
            if connection:
                connection.close()

    def do_POST(self):
        if (not self.allowed() or self.headers.get("Origin") != self.origin or
                self.headers.get("X-Session-Token") != self.token):
            self.reply(403, b"Forbidden")
            return
        if self.path in ("/ignore", "/restore", "/mute", "/volume"):
            cookie = SimpleCookie(self.headers.get("Cookie", "")).get("edgy")
            if cookie is None or not secrets.compare_digest(cookie.value, self.token):
                self.reply(403, b"Forbidden")
                return
            connection = None
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 4096:
                    self.reply(400, b"Invalid action")
                    return
                connection, response = self.session.open_view(self.path, self.rfile.read(length))
                self.reply(response.status, b"{}")
            except (ValueError, OSError, RuntimeError, http.client.HTTPException):
                self.reply(503, b"View unavailable")
            finally:
                if connection:
                    connection.close()
            return
        if self.path not in ("/start", "/stop"):
            self.reply(404, b"Not found")
            return
        controls = {"/start": self.session.start, "/stop": self.session.stop}
        controls[self.path]()
        self.reply(200, b"{}")

    def log_message(self, *_):
        pass


def serve(port: int, release: str, camera_file: str | None = None,
          mac_audio: bool = False) -> None:
    session = Session(release, camera_file, mac_audio)
    token = secrets.token_urlsafe(32)
    Handler.session = session
    Handler.token = token
    origin = Handler.origin = f"http://127.0.0.1:{port}"

    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        print(f"Robot monitor: {origin} (nothing runs until Start)", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            session.stop()
            if session.worker:
                session.worker.join(65)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765, help="loopback control page port")
    parser.add_argument("--release", help="exact Jetson release printed by tools/jetson.py deploy")
    parser.add_argument("--audio-fd", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--no-microphone", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--camera-file", help="existing Jetson recorded camera fixture path")
    parser.add_argument("--mac-audio", action="store_true",
                        help="use MacBook audio, not the Jetson's USB audio (remote development)")
    args = parser.parse_args()
    if args.audio_fd is not None:
        NativeAudio(args.audio_fd, not args.no_microphone).run()
    else:
        if not args.release:
            parser.error("--release is required for the deployed interface release")
        serve(args.port, args.release, args.camera_file, args.mac_audio)

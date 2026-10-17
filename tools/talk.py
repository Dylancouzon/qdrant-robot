#!/usr/bin/env python3
"""Monitor and controls for the robot. The robot is a Jetson-owned unit (`qr-robot`) that hears
and speaks through its own USB audio. Start attaches to it, or starts it. Closing this page or
losing the tunnel leaves it running; only Stop stops it. The Mac serves the page on loopback
through an SSH tunnel; `--on-robot` serves it from the Jetson to the network behind a key."""
import argparse
import contextlib
import http.client
import ipaddress
import os
import json
import secrets
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent.parent
BASE = "/home/qdrant/qdrant-robot"
NAME = "robot"
UNIT = f"qr-{NAME}.service"
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
       "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=2"]
LOCAL = False  # --on-robot: run commands here and reach the view without a tunnel
HOTSPOT = "l6-hotspot"  # the robot's own WPA2 network (SSID l6-robot, 10.42.0.1)
WIFI_CHECK_S, WIFI_MISSES = 30, 4  # raise the hotspot 90 to 120 s after Wi-Fi drops


def robot_args(camera_file: str | None, servo_calibration: str | None = None) -> list[str]:
    """The `robot.main` arguments; the robot uses its own USB audio."""
    return ["-m", "robot.main", *(["--camera-file", camera_file] if camera_file else []),
            *(["--servo-calibration", servo_calibration] if servo_calibration else [])]


def command(args: list[str], env=None) -> str:
    result = subprocess.run(args, capture_output=True, text=True, timeout=30, env=env)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip()[-1500:])
    return result.stdout.strip()


def remote(script: str) -> str:
    return command(["bash", "-c", script] if LOCAL else [*SSH, "robot", script])


def watch_wifi(down: int) -> int:
    """One Wi-Fi check: returns the new count of consecutive checks without a connection.
    The hotspot also counts as connected; it stays up until reboot or `nmcli con up <wifi>`."""
    try:
        states = command(["nmcli", "-t", "-f", "TYPE,STATE", "dev"]).splitlines()
    except (OSError, RuntimeError, subprocess.SubprocessError):
        return down  # an unknown state never raises the hotspot
    if "wifi:connected" in states:
        return 0
    if down + 1 < WIFI_MISSES:
        return down + 1
    try:
        command(["sudo", "-n", "nmcli", "--wait", "25", "con", "up", HOTSPOT])
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"Could not raise {HOTSPOT}: {exc}", flush=True)  # retried after another loss
    return 0


def keep_reachable() -> None:
    down = 0
    while True:
        time.sleep(WIFI_CHECK_S)
        down = watch_wifi(down)


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
    """Attach this page to the robot unit through one tunnel; the unit outlives the session."""

    def __init__(self, release: str | None, camera_file: str | None = None,
                 servo_calibration: str | None = None):
        self.release = release  # None follows the deployed `current` release
        self.follow = release is None
        self.camera_file = camera_file
        self.servo_calibration = servo_calibration
        self.view_port = self.view_token = None
        self.lock = threading.Lock()
        self.stopped = threading.Event()   # this session ends
        self.shutdown = threading.Event()  # and the robot stops too (Stop)
        self.worker = None
        self.unit = None
        self.state = dict(phase="Idle", active=False, error="", view_ready=False)

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
            self.shutdown.clear()
            self.state.update(phase="Connecting", active=True, error="")
            self.worker = threading.Thread(target=self.run, daemon=True)
            self.worker.start()

    def stop(self):
        self.shutdown.set()
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

    def listen(self, tunnel):
        """Wait for the robot to warm up, then watch it and the tunnel until Stop."""
        self.update(phase="Warming up Jetson; microphone off")
        ready = False
        while not self.stopped.wait(0.5 if not ready else 2):
            if tunnel is not None and tunnel.poll() is not None:
                raise RuntimeError(tunnel.stderr.read().decode().strip() or "SSH tunnel closed")
            self.report()  # raises when the Jetson session stops; old logs cannot prove readiness
            if not ready:
                try:
                    connection, response = self.open_view("/state")
                    ready = response.status == 200
                    connection.close()
                except (OSError, RuntimeError, http.client.HTTPException):
                    continue
            if ready:
                with self.lock:
                    if self.stopped.is_set():
                        return
                    self.state.update(view_ready=True, phase="Listening")

    def open_view(self, path, body=None):
        with self.lock:
            if self.stopped.is_set() or not self.view_port or not self.view_token:
                raise RuntimeError("Camera session is idle")
            port, token = self.view_port, self.view_token
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        try:
            connection.request("POST" if body is not None else "GET",
                               f"{path}{'&' if '?' in path else '?'}token={token}", body=body,
                               headers={"Host": "127.0.0.1:8090",
                                        "Origin": "http://127.0.0.1:8090",
                                        "Content-Type": "application/json"})
            response = connection.getresponse()
            if response.status not in (200, 202, 404, 409):
                raise RuntimeError("Jetson view is unavailable")
            return connection, response
        except Exception:
            connection.close()
            raise

    def attach_token(self):
        """The view token and release of the running robot, from its unit environment."""
        env = dict(item.partition("=")[::2] for item in
                   remote(f"systemctl show {UNIT} -p Environment --value").split())
        if env.get("ROBOT_RELEASE") != self.release or not env.get("ROBOT_VIEW_TOKEN"):
            raise RuntimeError(f"The running robot is not release {self.release} with a view. "
                               "Select Stop on the page that started it, or stop it on the Jetson.")
        return env["ROBOT_VIEW_TOKEN"]

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

    def cleanup_local(self, tunnel):
        reap(tunnel)
        if tunnel:
            tunnel.stderr.close()

    def run(self):
        tunnel = None
        error = ""
        try:
            status = remote(f"readlink -f {BASE}/current; systemctl list-units 'qr-*' "
                            "--state=active --no-legend --plain | awk '{print $1}'").splitlines()
            running = status[1:]
            if self.follow:
                self.release = status[0].rsplit("/", 1)[-1]
            if status[:1] != [f"{BASE}/releases/{self.release}"] or running not in ([], [UNIT]):
                raise RuntimeError(f"Jetson must run no job but {UNIT}, on release "
                                   f"{self.release}. Received: {status}")
            if self.stopped.is_set():
                return
            self.unit = UNIT
            if running:
                self.view_token = self.attach_token()
            else:
                self.view_token = secrets.token_hex(32)
                command([sys.executable, str(ROOT / "tools/jetson.py"), "run", NAME,
                         "--", *robot_args(self.camera_file, self.servo_calibration)],
                        env={**os.environ, "ROBOT_VIEW_TOKEN": self.view_token})
            if LOCAL:
                self.view_port = 8090
            else:
                with socket.socket() as reserve:
                    reserve.bind(("127.0.0.1", 0))
                    self.view_port = reserve.getsockname()[1]
                tunnel = subprocess.Popen([*SSH, "-N", "-o", "ExitOnForwardFailure=yes", "-L",
                                           f"127.0.0.1:{self.view_port}:127.0.0.1:8090", "robot"],
                                          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            self.listen(tunnel)
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            if not self.stopped.is_set():
                error = str(exc)
        finally:
            self.update(phase="Stopping", view_ready=False)
            self.view_port = self.view_token = None
            self.cleanup_local(tunnel)
            cleanup_error = self.cleanup_remote() if self.shutdown.is_set() else ""
            if not cleanup_error:
                self.unit = None  # detached: the robot keeps running
            error = "\n".join(filter(None, (error, cleanup_error)))
            self.update(phase="Error" if error else "Idle", active=bool(self.unit), error=error)


class Handler(BaseHTTPRequestHandler):
    session = None
    token = origin = ""
    lan = False  # --on-robot: any IP or .local host; the page needs ?key= or the cookie

    def reply(self, code, data, kind="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Cache-Control", "no-store")
        if kind.startswith("text/html"):
            self.send_header("Set-Cookie", f"edgy={self.token}; HttpOnly; SameSite=Strict; Path=/")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def allowed(self) -> str:
        """The request's page origin when Host and Origin are trusted, else ''."""
        origin = self.origin
        if self.lan:
            host = self.headers.get("Host", "")
            name = host.rsplit(":", 1)[0].strip("[]")
            try:
                ipaddress.ip_address(name)  # IP literals and mDNS names resist DNS rebinding
            except ValueError:
                if name != "localhost" and not name.endswith(".local"):
                    return ""
            origin = f"http://{host}"
        if (self.headers.get("Host") == origin.removeprefix("http://") and
                self.headers.get("Origin", origin) == origin):
            return origin
        return ""

    def cookie_ok(self):
        cookie = SimpleCookie(self.headers.get("Cookie", "")).get("edgy")
        return cookie is not None and secrets.compare_digest(cookie.value, self.token)

    def do_GET(self):
        if not self.allowed():
            self.reply(403, b"Forbidden")
        elif self.path.split("?", 1)[0] == "/":
            key = parse_qs(urlsplit(self.path).query).get("key", [""])[0]
            if self.lan and not (self.cookie_ok() or secrets.compare_digest(key, self.token)):
                self.reply(403, b"Open the monitor link with ?key= from shared/monitor-key",
                           "text/plain")
                return
            page = Path(__file__).with_suffix(".html").read_text().replace("TOKEN", self.token)
            self.reply(200, page.encode(), "text/html; charset=utf-8")
        elif self.path == "/mona-sans.woff2":
            self.reply(200, (ROOT / "tools/assets/mona-sans-latin.woff2").read_bytes(),
                       "font/woff2")
        elif self.path.split("?", 1)[0] in (
                "/camera", "/robot", "/memory", "/memory_map", "/thumb"):
            if not self.cookie_ok():
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
            path = "/state" if self.path == "/robot" else (
                "/" if self.path == "/camera" else self.path)
            connection, response = self.session.open_view(path)
            if self.path != "/camera":
                self.reply(response.status, response.read(), response.headers["Content-Type"])
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
        origin = self.allowed()
        if (not origin or self.headers.get("Origin") != origin or
                self.headers.get("X-Session-Token") != self.token):
            self.reply(403, b"Forbidden")
            return
        if self.path in ("/ignore", "/restore", "/mute", "/volume", "/settings", "/stop_head",
                         "/resume_head", "/forget_object", "/remove_view"):
            if not self.cookie_ok():
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


def monitor_key() -> str:
    """The robot page key: one per robot, kept across restarts so a saved link keeps working."""
    path = Path(BASE) / "shared/monitor-key"
    with (contextlib.suppress(FileExistsError),
          os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as f):
        f.write(secrets.token_urlsafe(24))
    return path.read_text().strip()


def serve(port: int, release: str | None, camera_file: str | None = None,
          servo_calibration: str | None = None, on_robot: bool = False) -> None:
    global LOCAL
    LOCAL = Handler.lan = on_robot
    session = Session(release, camera_file, servo_calibration)
    Handler.session = session
    Handler.token = monitor_key() if on_robot else secrets.token_urlsafe(32)
    origin = Handler.origin = f"http://127.0.0.1:{port}"
    if on_robot:
        threading.Thread(target=keep_reachable, daemon=True).start()
        origin = f"http://{socket.gethostname()}.local:{port}/?key=<shared/monitor-key>"

    with ThreadingHTTPServer(("0.0.0.0" if on_robot else "127.0.0.1", port), Handler) as server:
        print(f"Robot monitor: {origin} (nothing runs until Start)", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            session.stopped.set()  # detach: the robot keeps running
            if session.worker:
                session.worker.join(65)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765, help="control page port")
    parser.add_argument("--release", help="exact Jetson release printed by tools/jetson.py deploy")
    parser.add_argument("--on-robot", action="store_true",
                        help="run on the Jetson: serve the network, follow `current`, keep Wi-Fi")
    parser.add_argument("--camera-file", help="existing Jetson recorded camera fixture path")
    parser.add_argument("--servo-calibration",
                        help="existing Jetson mounted servo calibration path")
    args = parser.parse_args()
    if not args.release and not args.on_robot:
        parser.error("--release is required for the deployed interface release")
    serve(args.port, args.release, args.camera_file, args.servo_calibration, args.on_robot)

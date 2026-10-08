#!/usr/bin/env python3
"""The one Mac-to-Jetson workflow: deploy a release, run a named job on it, collect results.

    tools/jetson.py deploy                     copy the source as releases/<hash>, build its venv
    tools/jetson.py run NAME [--wait] -- ARGS  run python ARGS as unit qr-NAME in the release
    tools/jetson.py collect                    copy shared/results/ into bench/results/
    tools/jetson.py rollback                   point `current` back at `previous`
"""
import argparse
import hashlib
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST = "robot"
BASE = "/home/qdrant/qdrant-robot"
# Lead bookkeeping and reference material never ship to the robot.
NOT_SHIPPED = ("STATE.md", "DECISIONS.md", "CLAUDE.md", "research/", "reviews/", "gates/",
               "bench/results/", "refs/", ".claude/")


def sh(*cmd: str, **kw) -> str:
    return subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, text=True,
                          **kw).stdout.strip()


def remote(script: str, check: bool = True) -> int:
    """Run a bash script on the robot, streaming its output."""
    return subprocess.run(["ssh", HOST, "bash -se"], input=script, text=True,
                          check=check).returncode


def shipped() -> list[str]:
    files = sh("git", "ls-files", "--cached", "--others", "--exclude-standard").splitlines()
    return sorted(f for f in files if not f.startswith(NOT_SHIPPED) and (ROOT / f).is_file())


def digest(files: list[str], root: Path = ROOT) -> str:
    """Release ID: a hash over the paths and contents of the shipped files."""
    h = hashlib.sha256()
    for f in files:
        h.update(f.encode() + b"\0" + (root / f).read_bytes() + b"\0")
    return h.hexdigest()[:12]


def deploy() -> None:
    files = shipped()
    release = digest(files)
    lock = digest(["pyproject.toml", "uv.lock"])
    rel = f"{BASE}/releases/{release}"
    sh("ssh", HOST, f"mkdir -p {rel}")
    sh("rsync", "-a", "--files-from=-", ".", f"{HOST}:{rel}/", input="\n".join(files))
    # One venv per dependency set; system site-packages expose the apt TensorRT bindings.
    remote(f"""set -euo pipefail
export PATH=$HOME/.local/bin:/usr/local/cuda/bin:$PATH
cd {rel}
venv={BASE}/shared/venvs/{lock}
[ -x $venv/bin/python ] || uv venv -q --python /usr/bin/python3.12 --system-site-packages $venv
UV_PROJECT_ENVIRONMENT=$venv uv sync -q --frozen --no-install-project
ln -sfn $venv .venv
{{ echo "release {release}"; cat /etc/nv_tegra_release | head -1; uname -r
   nvcc --version | tail -2; dpkg-query -W 'tensorrt' 'libcudnn9-cuda-13' 'cuda-toolkit-13-2'
   uv pip freeze --python $venv/bin/python; }} > ENV.txt 2>&1
cd {BASE}
[ "$(readlink current || true)" = releases/{release} ] || {{
  [ -L current ] && ln -sfn "$(readlink current)" previous; ln -sfn releases/{release} current; }}
echo deployed {release}""")


def run(name: str, cmd: list[str], wait: bool) -> int:
    """Run CMD as a transient unit qr-NAME with tegrastats logged next to its results."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
        raise SystemExit(f"job name must be lowercase letters, digits, and dashes: {name!r}")
    unit = f"qr-{name}"
    job = shlex.join(cmd)
    log = f"{BASE}/shared/results/{name}.tegrastats"
    body = (f"tegrastats --interval 1000 --logfile {log} & t=$!; "
            f".venv/bin/python -u {job}; rc=$?; kill $t; exit $rc")
    flags = "--wait --pipe" if wait else "--no-block"
    return remote(f"""set -eu
mkdir -p {BASE}/shared/results {BASE}/shared/models
rel=$(readlink -f {BASE}/current)  # resolved once: a concurrent deploy cannot split provenance
sudo systemctl reset-failed {unit} 2>/dev/null || true
sudo systemd-run --unit={unit} {flags} --collect --uid=qdrant --gid=qdrant \\
  --working-directory="$rel" --setenv=HOME=/home/qdrant \\
  --setenv=ROBOT_SHARED={BASE}/shared --setenv=PYTHONUNBUFFERED=1 \\
  --setenv=ROBOT_RELEASE="$(basename "$rel")" \\
  -p StartLimitBurst=3 bash -c {shlex.quote(body)}
{'' if wait else f'echo "started {unit}; logs: journalctl -u {unit}"'}""", check=False)


def collect() -> None:
    (ROOT / "bench/results").mkdir(parents=True, exist_ok=True)
    sh("rsync", "-a", f"{HOST}:{BASE}/shared/results/", "bench/results/")


def rollback() -> None:
    remote(f"cd {BASE} && ln -sfn \"$(readlink previous)\" current && readlink current")


def selftest(tmp: Path) -> None:
    (tmp / "a").write_text("1")
    first = digest(["a"], tmp)
    (tmp / "a").write_text("2")
    assert digest(["a"], tmp) != first, "content change must change the release ID"
    assert not any(f.startswith(NOT_SHIPPED) for f in shipped())
    print("selftest ok")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for c in ("deploy", "collect", "rollback", "selftest"):
        sub.add_parser(c)
    r = sub.add_parser("run")
    r.add_argument("name")
    r.add_argument("--wait", action="store_true", help="stream output and wait for the exit code")
    r.add_argument("job", nargs="+", help="after --: script.py args")
    a = p.parse_args()
    if a.cmd == "run":
        sys.exit(run(a.name, a.job, a.wait))
    if a.cmd == "selftest":
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            selftest(Path(d))
        sys.exit(0)
    {"deploy": deploy, "collect": collect, "rollback": rollback}[a.cmd]()

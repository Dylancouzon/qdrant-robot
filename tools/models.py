#!/usr/bin/env python3
"""Fetch and verify the pinned model files in models.json (revision-pinned URLs, sha256, license).

    python -m tools.models [path-prefix ...]   download missing files under $ROBOT_SHARED/models
                                               (or ./models on the Mac), then verify every checksum
"""
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

from robot.config import MODELS, ROOT


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 22):
            h.update(chunk)
    return h.hexdigest()


def main(prefixes: list[str]) -> int:
    bad = 0
    for m in json.loads((ROOT / "models.json").read_text()):
        if prefixes and not m["path"].startswith(tuple(prefixes)):
            continue
        dest = MODELS / m["path"]
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_suffix(dest.suffix + ".part")
            try:
                urllib.request.urlretrieve(m["url"], tmp)
                if sha256(tmp) == m["sha256"]:
                    tmp.rename(dest)
            finally:
                tmp.unlink(missing_ok=True)  # a failed or corrupt download never blocks a retry
        ok = dest.exists() and sha256(dest) == m["sha256"]
        bad += not ok
        print(f"{'ok ' if ok else 'BAD'} {m['path']} ({m['license']})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

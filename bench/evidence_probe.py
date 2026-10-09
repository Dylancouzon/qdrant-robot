"""F0 development diagnostic. Run through tools/jetson.py's named GPU-locked unit.

Both arms generate with Brain.answer; original logged code answers are reference data only.
Times measure standalone generation. They establish no integrated latency or headroom.
"""

import copy
import hashlib
import json
import os
import platform
import re
import socket
import sys
import time
from pathlib import Path

from robot import brain
from robot.config import ROOT, SHARED

MANIFEST = ROOT / "eval/dev/evidence-probe.jsonl"
BLOCK = re.compile(r"(?:Memories|The visitor told you|Facts):\n- .*?\n\n", re.S)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def evidence(text):
    return BLOCK.findall(text)


def replace(text, blocks):
    """Change evidence only, keeping the logged lead, notes, and question byte-identical."""
    clean = BLOCK.sub("", text)
    offset = len(brain.EVIDENCE) if clean.startswith(brain.EVIDENCE) else 0
    return clean[:offset] + "".join(blocks) + clean[offset:]


def validate_sources(sources, steps):
    for source in sources:
        if source["step"] != steps[source["id"]]:
            raise ValueError("source transcript mismatch")
        if (
            hashlib.sha256(json.dumps(source["step"], sort_keys=True).encode()).hexdigest()
            != source["sha256"]
        ):
            raise ValueError("source step hash mismatch")
        if source.get("frame") and digest(ROOT / source["frame"]) != source["frame_sha256"]:
            raise ValueError("source image hash mismatch")


def load(path=MANIFEST):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines()]
    if len(rows) != 24 or len({r["id"] for r in rows}) != 24:
        raise ValueError("manifest requires 24 unique questions")
    for r in rows:
        cases = ROOT / r["cases"]
        if not r["cases"].startswith("eval/dev/") or digest(cases) != r["cases_sha256"]:
            raise ValueError("invalid development cases hash")
        steps = {
            s["id"]: s
            for line in cases.read_text().splitlines()
            for s in json.loads(line)["steps"]
            if "id" in s
        }
        if steps[r["id"]]["say"] != r["question"] or steps[r["id"]]["rubric"] != r["rubric"]:
            raise ValueError("question or rubric mismatch")
        validate_sources(r["sources"], steps)
        if digest(ROOT / r["frame"]) != r["frame_sha256"]:
            raise ValueError("current frame hash mismatch")
        if (
            hashlib.sha256(json.dumps(r["original_prompt"], sort_keys=True).encode()).hexdigest()
            != r["original_prompt_sha256"]
        ):
            raise ValueError("logged history hash mismatch")
        text = r["original_prompt"][-1]["content"][-1]["text"]
        if evidence(text) != r["original_evidence"] or not text.endswith(
            "Visitor: " + r["question"]
        ):
            raise ValueError("logged prompt mismatch")
        if any(evidence(block) != [block] for block in r["sufficient_evidence"]):
            raise ValueError("invalid sufficient evidence block")
        if not r["verification"] or not r["cause_tags"]:
            raise ValueError("missing provenance")
    return rows


def messages(row, arm, image=None):
    msgs = copy.deepcopy(row["original_prompt"])
    text = msgs[-1]["content"][-1]["text"]
    if arm == "sufficient":
        text = replace(text, row["sufficient_evidence"])
    msgs[-1]["content"] = ([image] if row["image_present"] else []) + [
        {"type": "text", "text": text}
    ]
    return [{"role": "system", "content": row["system"]}, *msgs]


def run():
    import cv2

    rows = load()
    if platform.machine() != "aarch64" or not os.environ.get("ROBOT_RELEASE"):
        raise RuntimeError("run on Jetson via tools/jetson.py run")
    socket.setdefaulttimeout(60)
    settings = {
        "context": 2048,
        "image_max_tokens": 256,
        "max_tokens": brain.MAX_TOKENS,
        "max_sentences": brain.MAX_SENTENCES,
        "temperature": 0,
        "repeat_penalty": 1.15,
    }
    if brain.MAX_TOKENS != 64 or brain.MAX_SENTENCES != 1:
        raise RuntimeError("production generation limits changed")
    out = (
        SHARED
        / "results"
        / f"{time.strftime('%Y-%m-%d')}-bakeoff-evidence-probe-{int(time.time())}.jsonl"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    weights, projector, _ = brain.MODELS["qwen3vl-2b"]
    meta = {
        "machine": socket.gethostname(),
        "release": os.environ["ROBOT_RELEASE"],
        "model": "qwen3vl-2b",
        "runtime_sha256": digest(brain.SERVER),
        "model_sha256": digest(brain.GGUF / weights),
        "projector_sha256": digest(brain.GGUF / projector),
        "manifest_sha256": digest(MANIFEST),
        "runner_sha256": digest(__file__),
        "brain_sha256": digest(brain.__file__),
        "settings": settings,
        "server_args": brain.server_args("qwen3vl-2b"),
        "command": [sys.executable, *sys.argv],
        "sample_count": 24,
        "arm_count": 48,
        "measurement": "standalone forced-generative oracle evidence diagnostic",
        "cases": "eval/dev/evidence-probe.jsonl",
        "variants": ["original", "sufficient"],
        "env_sha256": digest(ROOT / "ENV.txt"),
        "python": platform.python_version(),
        "tegrastats": os.environ.get("ROBOT_TEGRASTATS"),
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with out.open("x") as stream:

        def write(row):
            stream.write(json.dumps(row) + "\n")
            stream.flush()
            if stream.tell() > 20 * 2**20:
                raise RuntimeError("result disk budget exceeded")

        write({"header": "evidence_probe", **meta})
        b = brain.Brain("qwen3vl-2b")
        try:
            count = 0
            for row in rows:
                frame = cv2.imread(str(ROOT / row["frame"]))
                if frame is None:
                    raise ValueError("unreadable frame")
                image = brain.jpeg(frame) if row["image_present"] else None
                for arm in ("original", "sufficient"):
                    start = time.monotonic()
                    answer = "".join(b.answer(messages(row, arm, image)))
                    if not answer.strip():
                        raise ValueError("empty generation")
                    write(
                        {
                            "id": f"{row['id']}-{arm}",
                            "step": row["id"],
                            "original_question_id": row["id"],
                            "variant": arm,
                            "arm": arm,
                            "rubric": row["rubric"],
                            "heard": row["question"],
                            "answer": answer,
                            "generation_s": time.monotonic() - start,
                            "prompt_tokens": None,
                            "prompt_tokens_note": (
                                "unavailable: sentence cap closes Brain.answer before final usage"
                            ),
                            "cause_tags": row["cause_tags"],
                            "oracle_upper_bound": row["oracle_upper_bound"],
                        }
                    )
                    count += 1
                    print(f"{count}/48 {arm}/{row['id']}", flush=True)
        finally:
            b.close()
        write({"summary": "brain_bakeoff", "complete": True, "n": count, "n_expected": 48, **meta})
    print(out, flush=True)


if __name__ == "__main__":
    run()

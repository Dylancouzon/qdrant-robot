#!/usr/bin/env python3
"""Prepare the independent F0c video and evidence frames without loading models."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "build/f0c-sources"
OUT = ROOT / "eval/challenge-20261009"
ENTRIES = [
    "book/batch-20/35",
    "bottle/batch-3/14",
    "book/batch-6/16",
    "bottle/batch-40/29",
    "book/batch-31/44",
    "bottle/batch-7/24",
]
BASE = "https://storage.googleapis.com/objectron"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command):
    print(" ".join(command), flush=True)
    proc = subprocess.Popen(command, start_new_session=True)
    try:
        code = proc.wait(timeout=300)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
        raise RuntimeError("Process group watchdog expired; output is incomplete") from None
    if code:
        raise RuntimeError(f"Command failed with status {code}; output is incomplete")


def acquire():
    CACHE.mkdir(parents=True, exist_ok=True)
    for entry in ENTRIES:
        path = CACHE / (entry.replace("/", "-") + ".MOV")
        if path.exists():
            continue
        url = f"{BASE}/videos/{entry}/video.MOV"
        head = subprocess.check_output(
            [
                "curl",
                "--fail",
                "--head",
                "--connect-timeout",
                "10",
                "--max-time",
                "30",
                "--silent",
                url,
            ],
            timeout=45,
        ).decode()
        sizes = [
            int(x.split(":", 1)[1])
            for x in head.splitlines()
            if x.lower().startswith("content-length:")
        ]
        if not sizes:
            raise RuntimeError(f"Missing source size: {entry}")
        current = sum(p.stat().st_size for p in CACHE.rglob("*") if p.is_file())
        if current + sizes[-1] > 300_000_000:
            raise RuntimeError("Raw cache budget would be exceeded")
        partial = Path(str(path) + ".incomplete")
        run(
            [
                "curl",
                "--fail",
                "--connect-timeout",
                "10",
                "--max-time",
                "120",
                "--progress-bar",
                url,
                "-o",
                str(partial),
            ]
        )
        if partial.stat().st_size != sizes[-1]:
            raise RuntimeError(f"Incomplete download: {entry}")
        partial.rename(path)


def prepare():
    previous = OUT / "sources.json"
    if previous.exists():
        for source in json.loads(previous.read_text())["sources"]:
            if digest(ROOT / source["raw_path"]) != source["raw_sha256"]:
                raise RuntimeError(f"Changed frozen source: {source['id']}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "keyframes").mkdir(exist_ok=True)
    sources, frames = [], []
    version = subprocess.check_output(["ffmpeg", "-version"], text=True, timeout=30).splitlines()[0]
    for i, entry in enumerate(ENTRIES):
        name = entry.replace("/", "-")
        raw = CACHE / (name + ".MOV")
        start = (i // 2) * 600 + (180 if i % 2 else 0)
        end = (i // 2 + 1) * 600 if i % 2 else start + 180
        probe = json.loads(
            subprocess.check_output(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_streams",
                    "-show_format",
                    "-of",
                    "json",
                    str(raw),
                ],
                timeout=45,
            )
        )
        n = int(probe["streams"][0]["nb_frames"])
        pts = json.loads(
            subprocess.check_output(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "frame=best_effort_timestamp_time",
                    "-of",
                    "json",
                    str(raw),
                ],
                timeout=45,
            )
        )["frames"]
        times = [x["best_effort_timestamp_time"] for x in pts]
        assert len(times) == n
        final = (n - 1) // 2 * 2
        partial = OUT / (name + ".avi.incomplete")
        command = [
            "ffmpeg",
            "-y",
            "-v",
            "warning",
            "-noautorotate",
            "-i",
            str(raw),
            "-an",
            "-vf",
            "select=not(mod(n\\,2)),setpts=N/(15*TB),transpose=clock,scale=480:640",
            "-r",
            "15",
            "-c:v",
            "mjpeg",
            "-q:v",
            "5",
            "-threads",
            "1",
            "-pix_fmt",
            "yuvj420p",
            "-map_metadata",
            "-1",
            "-fflags",
            "+bitexact",
            "-flags:v",
            "+bitexact",
            "-f",
            "avi",
            str(partial),
        ]
        run(command)
        assert partial.stat().st_size < 15_000_000
        fixture = OUT / (name + ".avi")
        partial.rename(fixture)
        cap = cv2.VideoCapture(str(raw))
        for raw_index in sorted({0, n // 4 // 2 * 2, n // 2 // 2 * 2, final}):
            cap.set(cv2.CAP_PROP_POS_FRAMES, raw_index)
            ok, frame = cap.read()
            assert ok
            frame = cv2.resize(frame, (480, 640), interpolation=cv2.INTER_LINEAR)
            path = OUT / "keyframes" / f"{name}-{raw_index:03}.png"
            cv2.imwrite(str(path), frame)
            frames.append(
                {
                    "id": f"{name}-raw-{raw_index}",
                    "source_id": entry,
                    "raw_frame_index": raw_index,
                    "raw_time_s": float(times[raw_index]),
                    "raw_pts_s": times[raw_index],
                    "fixture_frame_index": raw_index // 2,
                    "fixture_time_s": raw_index / 30,
                    "path": str(path.relative_to(ROOT)),
                    "sha256": digest(path),
                    "decoded_rgb_sha256": hashlib.sha256(
                        cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).tobytes()
                    ).hexdigest(),
                }
            )
        cap.release()
        sources.append(
            {
                "id": entry,
                "dataset": "Objectron v1 test index",
                "url": f"{BASE}/videos/{entry}/video.MOV",
                "raw_path": str(raw.relative_to(ROOT)),
                "raw_bytes": raw.stat().st_size,
                "raw_sha256": digest(raw),
                "whole_capture_group": entry,
                "object_id": None,
                "participant_id": None,
                "group_limit": (
                    "Capture ID only; cross-capture object and participant identity unavailable."
                ),
                "split": "challenge only; all Objectron excluded from future training",
                "show_at_s": start,
                "end_at_s_exclusive": end,
                "raw_frame_count": n,
                "raw_fps": 30,
                "raw_duration_s": float(probe["format"]["duration"]),
                "raw_frame_pts_s": times,
                "fixture": str(fixture.relative_to(ROOT)),
                "fixture_bytes": fixture.stat().st_size,
                "fixture_sha256": digest(fixture),
                "fixture_fps": 15,
                "fixture_frame_count": final // 2 + 1,
                "sampled_raw_frames": {"start": 0, "end_inclusive": final, "step": 2},
                "held_raw_frame": final,
                "held_interval_s": [start + (final // 2 + 1) / 15, end],
                "orientation": (
                    "Explicit transpose=clock from stored pixels; rotation metadata removed."
                ),
                "conversion_command": command,
            }
        )
    (OUT / "sources.json").write_text(
        json.dumps(
            {
                "sources": sources,
                "ffmpeg": version,
                "primary_repository": "https://github.com/google-research-datasets/Objectron",
                "license": "C-UDA-1.0",
                "license_url": "https://raw.githubusercontent.com/google-research-datasets/Objectron/master/LICENSE",
                "index_urls": {
                    c: f"{BASE}/v1/index/{c}_annotations_test" for c in ("book", "bottle")
                },
                "annotation_origin": (
                    "Evaluator manually inspected decoded frames; "
                    "no Objectron automatic annotations used for answers."
                ),
            },
            indent=2,
        )
        + "\n"
    )
    (OUT / "frame-evidence.jsonl").write_text("".join(json.dumps(x) + "\n" for x in frames))
    verify()


def check_manifest(folder=OUT):
    visits_path = folder / "visits.jsonl"
    if not visits_path.exists():
        return
    visits = [json.loads(line) for line in visits_path.read_text().splitlines()]
    rubrics = [json.loads(line) for line in (folder / "rubrics.jsonl").read_text().splitlines()]
    assert len(visits) == 3 and len(rubrics) == 48
    scored, utterances, shows = [], {}, {}
    for index, visit in enumerate(visits):
        assert visit["start_at_s"] == index * 600 and visit["duration_s"] == 600
        assert visit["continuous_process"] and not visit["restart"]
        steps = visit["steps"]
        assert len({step["id"] for step in steps}) == len(steps)
        for step in steps:
            assert ("show" in step) != ("say" in step)
            if "show" in step:
                shown = (folder / step["show"]).resolve()
                assert shown.is_relative_to(folder.resolve()) and shown.is_file()
                assert not step["scored"]
                shows[step["source_id"]] = step["at_s"]
            else:
                assert step["say"]
                utterances[step["id"]] = step
        times = [step["at_s"] for step in steps]
        assert times == sorted(times)
        assert all(index * 600 <= t < (index + 1) * 600 for t in times)
        questions = [step for step in steps if step["scored"]]
        assert len(questions) == 16
        assert any(
            s["category"] == "older_observation" and s["at_s"] >= index * 600 + 550
            for s in questions
        )
        scored.extend(step["id"] for step in questions)
    assert len(set(scored)) == 48
    assert set(scored) == {r["id"] for r in rubrics}
    source_map = {s["id"]: s for s in json.loads((folder / "sources.json").read_text())["sources"]}
    for rubric in rubrics:
        assert rubric["reviewer_only"] and rubric["rubric"] and rubric["expected_facts"]
        for evidence in rubric["evidence"]:
            question_time = utterances[rubric["id"]]["at_s"]
            if "raw_frame_index" in evidence:
                source = source_map[evidence["source_id"]]
                assert shows[source["id"]] < question_time
                assert evidence["schedule_evidence_interval_s"][0] < question_time
                assert evidence["raw_frame_index"] == 2 * evidence["fixture_frame_index"]
                assert (
                    evidence["raw_pts_interval_s"][0]
                    == source["raw_frame_pts_s"][evidence["raw_frame_index"]]
                )
                assert (folder / "keyframes" / evidence["keyframe"]).exists()
            else:
                source_step = utterances[evidence["source_id"]]
                assert source_step["at_s"] == evidence["at_s"]
                if evidence["evidence_type"] == "general fictional statement":
                    assert not source_step["scored"] and source_step["at_s"] < question_time
                    assert (
                        hashlib.sha256(source_step["say"].encode()).hexdigest()
                        == evidence["utterance_sha256"]
                    )
                else:
                    assert evidence["source_id"] == rubric["id"]
                    assert rubric["category"] in {"plain_chat", "absent_evidence"}
                    assert evidence["evidence_type"] == (
                        "request itself"
                        if rubric["category"] == "plain_chat"
                        else "absence within this entire frozen source/schedule set"
                    )
    for source in source_map.values():
        assert digest(ROOT / source["fixture"]) == source["fixture_sha256"]
    print("PASS: 48 sourced rubrics; three absolute 600-second schedules; pinned fixture hashes")


def verify():
    check_manifest()
    samples, identities, sources = [], [], json.loads((OUT / "sources.json").read_text())["sources"]
    for source in sources:
        assert digest(ROOT / source["raw_path"]) == source["raw_sha256"]
        cap = cv2.VideoCapture(str(ROOT / source["fixture"]))
        assert cap.isOpened() and cap.get(cv2.CAP_PROP_FPS) == 15
        assert int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) == source["fixture_frame_count"]
        for raw_index in (0, source["held_raw_frame"]):
            raw_path = OUT / "keyframes" / (source["id"].replace("/", "-") + f"-{raw_index:03}.png")
            raw = cv2.imread(str(raw_path))
            k = raw_index // 2
            cap.set(cv2.CAP_PROP_POS_FRAMES, k)
            ok, frame = cap.read()
            assert ok and frame.shape == raw.shape
            error = float(np.abs(frame.astype(float) - raw.astype(float)).mean())
            assert error < 6, (source["id"], k, error)
            path = OUT / "keyframes" / (source["id"].replace("/", "-") + f"-fixture-{k:03}.png")
            cv2.imwrite(str(path), frame)
            samples.append(
                {
                    "fixture_frame_index": k,
                    "fixture_time_s": k / 15,
                    "source_id": source["id"],
                    "raw_frame_index": raw_index,
                    "mean_absolute_pixel_error": error,
                    "path": str(path.relative_to(ROOT)),
                    "sha256": digest(path),
                    "decoded_rgb_sha256": hashlib.sha256(
                        cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).tobytes()
                    ).hexdigest(),
                }
            )
        cap.release()
        oracle = cv2.VideoCapture(str(ROOT / source["fixture"]))
        hashes = []
        while True:
            ok, frame = oracle.read()
            if not ok:
                break
            hashes.append(hashlib.sha256(frame.tobytes()).hexdigest())
        oracle.release()
        assert len(hashes) == source["fixture_frame_count"]
        indexed = cv2.VideoCapture(str(ROOT / source["fixture"]))
        # Reverse order defeats accidental sequential decoder reuse.
        for k in reversed(range(len(hashes))):
            indexed.set(cv2.CAP_PROP_POS_FRAMES, k)
            ok, frame = indexed.read()
            assert ok and hashlib.sha256(frame.tobytes()).hexdigest() == hashes[k]
        indexed.release()
        identities.append(
            {
                "source_id": source["id"],
                "indexed_vs_sequential_matches": len(hashes),
                "frame_pixel_sha256": hashes,
            }
        )
    (OUT / "decode-check.json").write_text(
        json.dumps({"samples": samples, "indexed_identity": identities}, indent=2) + "\n"
    )
    sheet = np.full((700, 6 * 240, 3), 255, np.uint8)
    for i, source in enumerate(sources):
        name = source["id"].replace("/", "-")
        for row, k in enumerate((0, source["held_raw_frame"])):
            frame = cv2.imread(str(OUT / "keyframes" / f"{name}-{k:03}.png"))
            sheet[row * 350 + 25 : row * 350 + 345, i * 240 : (i + 1) * 240] = cv2.resize(
                frame, (240, 320)
            )
            cv2.putText(
                sheet,
                f"{name} raw{k}",
                (i * 240 + 2, row * 350 + 17),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                (0, 0, 0),
                1,
            )
    cv2.imwrite(str(OUT / "contact-sheet.jpg"), sheet)
    tracked = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    assert tracked < 60_000_000
    print(f"PASS: six complete upright MJPG AVI clips at15fps; folder {tracked} bytes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["acquire", "prepare", "verify"])
    globals()[parser.parse_args().action]()

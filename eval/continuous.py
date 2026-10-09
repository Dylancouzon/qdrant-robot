"""Absolute audio schedules through one Robot, with a separate process watchdog.

python -m eval.continuous visits.jsonl --audio audio-dir --output run.jsonl
"""

import argparse
import dataclasses
import hashlib
import json
import math
import os
import platform
import queue
import signal
import subprocess
import sys
import time
import wave
from pathlib import Path

RATE = 16000
CHUNK = 1280
LATENESS = 0.5
TOLERANCE = 0.25
ENDPOINT = 1.5
TIMEOUTS = {"startup": 180.0, "source": 10.0, "schedule": 10.0, "cleanup": 60.0}


def emit(path, row):
    with path.open("a") as f:
        f.write(json.dumps(row, default=str) + "\n")
        f.flush()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def source_input(st, cases, previous_end):
    at = st["at_s"]
    rel = Path(st["show"])
    target = (cases.parent / rel).resolve()
    hold = st["hold_final_frame_until_s"]
    if (
        rel.is_absolute()
        or not target.is_relative_to(cases.parent.resolve())
        or not target.is_file()
        or st["scored"] is not False
        or not isinstance(st.get("source_id"), str)
        or not st["source_id"]
        or not number(hold)
        or not at < hold <= previous_end
    ):
        raise ValueError("invalid source path or hold")
    return {"path": str(target), "sha256": digest(target)}


def speech_input(st, audio):
    sid, at = st["id"], st["at_s"]
    if not isinstance(st["say"], str) or not st["say"].strip():
        raise ValueError("invalid speech")
    path = audio / f"{sid}.wav"
    with wave.open(str(path), "rb") as f:
        if (f.getframerate(), f.getnchannels(), f.getsampwidth(), f.getcomptype()) != (
            RATE,
            1,
            2,
            "NONE",
        ) or f.getnframes() == 0:
            raise ValueError("audio must be nonempty 16k mono signed16 PCM")
        raw = f.readframes(f.getnframes())
        if len(raw) != f.getnframes() * 2:
            raise ValueError("truncated WAV")
    return raw, dict(
        path=str(path),
        sha256=digest(path),
        samples=len(raw) // 2,
        end_at_s=at + len(raw) / (2 * RATE),
    )


def validate_timeline(steps, previous_end):
    for i, step in enumerate(steps):
        if i and step["at_s"] < steps[i - 1]["at_s"]:
            raise ValueError("unordered steps")
        if "say" in step:
            next_event = steps[i + 1]["at_s"] if i + 1 < len(steps) else previous_end
            next_say = next((s["at_s"] for s in steps[i + 1 :] if "say" in s), previous_end)
            if step["end_at_s"] > next_event or step["end_at_s"] + ENDPOINT > next_say:
                raise ValueError("speech or endpoint silence overlaps next input")
        else:
            next_show = next((s["at_s"] for s in steps[i + 1 :] if "show" in s), previous_end)
            if step["hold_final_frame_until_s"] != next_show:
                raise ValueError("source hold must end at the next source or schedule end")


def preflight(cases, audio):
    """Validate only input schedules and PCM; no answer or rubric imports."""
    visits = [json.loads(line) for line in cases.read_text().splitlines() if line.strip()]
    if not visits:
        raise ValueError("empty schedule")
    ids, steps, wavs, previous_end = set(), [], {}, 0.0
    for visit in visits:
        vid, start, duration = visit["id"], visit["start_at_s"], visit["duration_s"]
        if (
            not isinstance(vid, str)
            or not vid
            or vid in ids
            or not number(start)
            or not number(duration)
            or start < previous_end
            or duration <= 0
            or visit.get("continuous_process") is not True
            or visit.get("restart") is not False
        ):
            raise ValueError("invalid or overlapping visit")
        ids.add(vid)
        previous_end = start + duration
        previous_at = start
        for st in visit["steps"]:
            sid, at = st["id"], st["at_s"]
            if (
                not isinstance(sid, str)
                or not sid
                or Path(sid).name != sid
                or sid in ids
                or not number(at)
                or not previous_at <= at < previous_end
                or ("say" in st) == ("show" in st)
                or not isinstance(st.get("scored"), bool)
            ):
                raise ValueError("invalid step")
            ids.add(sid)
            previous_at = at
            step = {**st, "visit_id": vid}
            if "show" in st:
                step.update(source_input(st, cases, previous_end))
            else:
                raw, info = speech_input(st, audio)
                wavs[sid] = raw
                step.update(info)
            steps.append(step)
    validate_timeline(steps, previous_end)
    return visits, steps, wavs, previous_end


def counts(visits, steps):
    says = [s for s in steps if "say" in s]
    return {
        "visits": len(visits), "show": len(steps) - len(says),
        "scored": sum(s["scored"] for s in says), "auxiliary": sum(not s["scored"] for s in says),
    }


def resources(root):
    """Linux process-tree counters; unavailable counters stay explicit on other hosts."""
    if not Path("/proc/meminfo").exists():
        return {"unavailable": "Linux /proc counters unavailable"}
    mem = dict(
        line.replace(":", "").split()[:2] for line in Path("/proc/meminfo").read_text().splitlines()
    )
    vm = dict(line.split() for line in Path("/proc/vmstat").read_text().splitlines())
    records = {}
    for directory in Path("/proc").glob("[0-9]*"):
        try:
            stat = (directory / "stat").read_text().rsplit(")", 1)[1].split()
            status = dict(
                line.split(":", 1)
                for line in (directory / "status").read_text().splitlines()
                if ":" in line
            )
            records[int(directory.name)] = {
                "ppid": int(stat[1]), "major_faults": int(stat[9]),
                "rss_kb": int(status.get("VmRSS", "0 kB").split()[0]),
                "swap_kb": int(status.get("VmSwap", "0 kB").split()[0]),
            }
        except (OSError, ValueError, IndexError):
            continue
    tree = {root}
    while True:
        expanded = tree | {pid for pid, row in records.items() if row["ppid"] in tree}
        if expanded == tree:
            break
        tree = expanded
    return {
        "mem_available_kb": int(mem["MemAvailable"]),
        "allocated_swap_kb": int(mem["SwapTotal"]) - int(mem["SwapFree"]),
        "pswpin": int(vm["pswpin"]), "pswpout": int(vm["pswpout"]),
        "processes": {pid: records[pid] for pid in tree if pid in records},
    }


def resource_delta(before, after):
    if "unavailable" in after:
        return after
    return {
        "pswpin": after["pswpin"] - before.get("pswpin", 0),
        "pswpout": after["pswpout"] - before.get("pswpout", 0), "major_faults": {
            pid: p["major_faults"] - before.get("processes", {}).get(pid, {}).get("major_faults", 0)
            for pid, p in after["processes"].items()
        },
    }


def queues(robot):
    return {
        name: {"depth": q.qsize(), "unfinished": q.unfinished_tasks}
        for name, q in (("lines", robot.lines), ("jobs", robot.jobs), ("mouth", robot.speaker.q))
    }


def pending(robot, collected):
    return (
        robot.speaking
        or robot.lines.unfinished_tasks
        or robot.asked != collected
        or robot.speaker.q.unfinished_tasks
    )


def evidence(robot, turn, sources, transcripts):
    started = time.monotonic()
    payloads = robot.memory.points(set(turn.memories) | {turn.frame_id})
    mappings = []
    for p in payloads:
        stamp = p.get("ts", p.get("first_seen"))
        matches = [
            s["source_id"]
            for s in sources
            if stamp is not None and s["actual_wall"] <= stamp < s["until_wall"]
        ]
        statements = [sid for sid, texts in transcripts.items() if p.get("said") in texts]
        mappings.append(
            {
                "runtime_id": p["id"], "capture_wall": stamp, "source_ids": matches,
                "statement_step_ids": statements,
                "mapping": "matched" if len(matches) == 1 else "missing_or_ambiguous",
            }
        )
    return {
        "payloads": payloads, "source_mappings": mappings, "retrieved_statements": [
            {"text": text, "step_ids": [sid for sid, texts in transcripts.items() if text in texts]}
            for text in turn.told
        ],
        "mapping_s": time.monotonic() - started,
    }


class Scheduler:
    def __init__(self, visits, steps, wavs, duration, robot, camera, output, clock=time):
        import numpy as np

        self.np = np
        self.visits = visits
        self.steps = steps
        self.wavs = wavs
        self.duration = duration
        self.robot = robot
        self.camera = camera
        self.output = output
        self.clock = clock
        (self.origin, self.wall) = (self.clock.monotonic(), self.clock.time())
        (self.intervals, self.turns, self.transcripts, self.sources, self.finished) = (
            {},
            {},
            {},
            [],
            set(),
        )
        (self.index, self.sample_count, self.active, self.position, self.collected) = (
            0,
            0,
            None,
            0,
            0,
        )
        self.total_samples = round(self.duration * RATE)
        (self.next_report, self.detect_at, self.last_detections) = (0.0, 0.0, self.robot.detections)
        (self.chunk_count, self.failed) = (0, 0)
        self.expected = counts(self.visits, self.steps)
        self.probe_due, self.probed_hold = math.inf, False
        self.last_resources = resources(os.getpid())
        self.pending_at, self.pending_signature = None, None
        emit(
            self.output,
            {
                "type": "anchor", "monotonic": self.origin, "wall": self.wall,
                "duration_s": self.duration,
            },
        )

    def phase(self, name):
        emit(self.output, {"type": "phase", "phase": name})

    def finalize(self, sid):
        if sid in self.finished:
            return
        st = next((s for s in self.steps if s["id"] == sid))
        found = self.turns[sid]
        good = (
            len(found) == 1
            and bool(found[0]["question"].strip())
            and bool(found[0]["answer"].strip())
        )
        self.failed += not good
        self.finished.add(sid)
        emit(
            self.output,
            {
                "type": "utterance", "id": sid, "visit_id": st["visit_id"], "scored": st["scored"],
                "category": st.get("category"), "ok": good,
                "failure": None if good else "split_or_missing_transcript_or_empty_answer",
                "split": len(found), "heard": " | ".join((t["question"] for t in found)),
                "answer": found[-1]["answer"] if found else "", "input": self.intervals[sid],
                "turns": found,
            },
        )

    def drain(self):
        while True:
            try:
                turn = self.robot.turns.get_nowait()
            except queue.Empty:
                return
            found = [
                sid
                for (sid, interval) in self.intervals.items()
                if interval["start_wall"] - TOLERANCE
                <= turn.speech_start
                <= interval["end_wall"] + TOLERANCE
                and interval["start_wall"] - TOLERANCE
                <= turn.speech_end
                <= interval["end_wall"] + TOLERANCE
                and (turn.speech_start <= turn.speech_end)
            ]
            if len(found) != 1 or found[0] in self.finished:
                emit(self.output, {"type": "unmatched_turn", "turn": dataclasses.asdict(turn)})
                raise RuntimeError("ambiguous, unmatched, or late finalized turn")
            sid = found[0]
            row = dataclasses.asdict(turn)
            self.transcripts[sid].append(turn.question)
            row.update(
                evidence(self.robot, turn, self.sources, self.transcripts),
                resources=resources(os.getpid()),
                queues=queues(self.robot),
                prompt_text_chars=len(json.dumps(turn.prompt)),
                history_text_chars=len(json.dumps(self.robot.history)),
                prompt_tokens=None,
                prompt_tokens_unavailable=(
                    "Turn.prompt omits encoded images; sentence stops can omit final token usage"
                ),
            )
            self.turns[sid].append(row)
            self.collected += 1
            emit(self.output, {"type": "turn", "id": sid, **row})

    def probe(self, kind):
        started = self.clock.monotonic()
        frame, stamp = self.camera.latest()
        if frame is None:
            raise RuntimeError("scheduled source has no frame")
        emit(
            self.output,
            {
                "type": "source_probe", "source_id": self.sources[-1]["source_id"], "kind": kind,
                "capture_wall": stamp, "elapsed_s": started - self.origin,
                "sha256": hashlib.sha256(frame.tobytes()).hexdigest(), "shape": list(frame.shape),
                "probe_s": self.clock.monotonic() - started,
            },
        )

    def report(self, now):
        required = {thread.name: thread.is_alive() for thread in self.robot.threads}
        if any(
            (
                not required.get(name, False)
                for name in ("_watch", "_detect", "_transcribe", "_work")
            )
        ):
            raise RuntimeError("required Robot thread died")
        if self.robot.detect_failed or self.robot.brain.proc.poll() is not None:
            raise RuntimeError("detector or llama-server failed")
        if self.robot.detections != self.last_detections or not self.sources:
            (self.last_detections, self.detect_at) = (self.robot.detections, now)
        elif now - self.detect_at >= TIMEOUTS["schedule"]:
            raise RuntimeError("detector stalled with source available")
        state = queues(self.robot)
        signature = (self.robot.asked, self.collected,
                     state["lines"]["unfinished"], state["mouth"]["unfinished"])
        blocked = pending(self.robot, self.collected) and not self.robot.speaking
        if not blocked or signature != self.pending_signature:
            self.pending_at = now
        elif now - self.pending_at >= TIMEOUTS["schedule"]:
            raise RuntimeError("pending turn work stalled")
        self.pending_signature = signature
        if now >= self.probe_due and not self.probed_hold:
            self.probe("final_hold")
            self.probed_hold = True
        measured = resources(os.getpid())
        delta = resource_delta(self.last_resources, measured)
        self.last_resources = measured
        emit(
            self.output,
            {
                "type": "progress", "phase": "schedule", "elapsed_s": now,
                "audio_end_s": self.sample_count / RATE, "chunks": self.chunk_count,
                "events": self.index, "turns": self.collected, "finished": len(self.finished),
                "required_threads": required, "detections": self.robot.detections,
                "queues": queues(self.robot), "resources": measured, "resource_delta": delta,
                "activity": "active" if self.active or blocked else "idle",
            },
        )
        self.next_report = now + 1.0

    def submit(self, now):
        st = self.steps[self.index]
        event_due = st["at_s"]
        late = now - event_due
        if late > LATENESS:
            raise RuntimeError(f"event {st['id']} late by {late:.3f}s")
        if "show" in st:
            self.phase("source")
            self.camera.show(Path(st["path"]))
            actual = self.clock.monotonic() - self.origin
            self.sources.append(
                {
                    "id": st["id"], "source_id": st["source_id"], "actual_wall": self.wall + now,
                    "path": st["path"], "sha256": st["sha256"],
                    "until_wall": self.wall + st["hold_final_frame_until_s"],
                }
            )
            self.probe("switch")
            self.probe_due = actual + (getattr(self.camera, "_count", 1) - 1) / getattr(
                self.camera, "_fps", 1
            )
            self.probed_hold = False
            self.phase("schedule")
            late = self.clock.monotonic() - self.origin - event_due
            if late > LATENESS:
                raise RuntimeError("source switch exceeded allowed lateness")
        else:
            if pending(self.robot, self.collected):
                raise RuntimeError("pending work at next utterance")
            for sid in self.intervals:
                self.finalize(sid)
            (self.active, self.position) = (st["id"], 0)
            self.intervals[self.active] = {
                "start_wall": self.wall + now, "end_wall": self.wall + now,
                "due_start_s": event_due, "path": st["path"], "sha256": st["sha256"],
            }
            (self.turns[self.active], self.transcripts[self.active]) = ([], [])
        emit(
            self.output,
            {
                "type": "event", "id": st["id"], "visit_id": st["visit_id"], "due_s": event_due,
                "actual_s": self.clock.monotonic() - self.origin, "lateness_s": late,
                "source": self.sources[-1] if "show" in st else None,
            },
        )
        self.index += 1

    def feed(self, n, audio_due, now):
        late = now - audio_due
        if late > LATENESS:
            raise RuntimeError(f"audio chunk late by {late:.3f}s")
        if self.active is None:
            chunk = self.np.zeros(n, self.np.float32)
        else:
            chunk = (
                self.np.frombuffer(
                    self.wavs[self.active], dtype="<i2", count=n, offset=self.position * 2
                ).astype(self.np.float32)
                / 32768
            )
            self.position += n
            actual_wall = self.wall + now
            if self.position == n:
                self.intervals[self.active]["start_wall"] = actual_wall - n / RATE
            self.intervals[self.active]["end_wall"] = actual_wall
        self.robot.hear(chunk)
        self.chunk_count += 1
        self.sample_count += n
        emit(
            self.output,
            {
                "type": "audio", "id": self.active, "samples": n, "due_end_s": audio_due,
                "actual_end_s": now, "lateness_s": late, "chunk": self.chunk_count,
            },
        )
        if self.active is not None and self.position == len(self.wavs[self.active]) // 2:
            emit(self.output, {"type": "input_interval", "id": self.active,
                               **self.intervals[self.active]})
            self.active = None

    def run(self):
        self.phase("schedule")
        while self.sample_count < self.total_samples or self.index < len(self.steps):
            now = self.clock.monotonic() - self.origin
            self.drain()
            if now >= self.next_report:
                self.report(now)
            event_due = self.steps[self.index]["at_s"] if self.index < len(self.steps) else math.inf
            boundary = min(event_due, self.duration)
            n = min(CHUNK, max(0, round(boundary * RATE) - self.sample_count))
            if self.active is not None:
                n = min(n, len(self.wavs[self.active]) // 2 - self.position)
            audio_due = (self.sample_count + n) / RATE if n else math.inf
            due = min(event_due, audio_due, self.next_report)
            if due > now:
                self.clock.sleep(due - now)
                continue
            if event_due < audio_due and event_due <= now:
                self.submit(now)
                continue
            if audio_due <= now:
                self.feed(n, audio_due, now)
        remaining = self.duration - (self.clock.monotonic() - self.origin)
        self.clock.sleep(max(0, remaining))  # Preserve durations between adjacent audio samples.
        self.drain()
        self.report(self.clock.monotonic() - self.origin)
        if pending(self.robot, self.collected):
            raise RuntimeError("pending work at schedule end")
        for sid in self.intervals:
            self.finalize(sid)
        if (
            self.index != len(self.steps)
            or len(self.finished) != self.expected["scored"] + self.expected["auxiliary"]
        ):
            raise RuntimeError("missing scheduled input")
        return {
            "counts": self.expected, "elapsed_s": self.clock.monotonic() - self.origin,
            "event_ids": [s["id"] for s in self.steps], "utterance_ids": list(self.intervals),
            "visit_ids": [v["id"] for v in self.visits], "failed_steps": self.failed,
            "chunks": self.chunk_count, "samples": self.sample_count,
        }


def evaluate(visits, steps, wavs, duration, robot, camera, output, clock=time):
    """Single scheduler owns hear(), turn collection, and source mapping."""
    return Scheduler(visits, steps, wavs, duration, robot, camera, output, clock).run()


def run_paths(output):
    root = Path(os.environ.get("ROBOT_SHARED", output.parent)) / "sessions" / output.stem
    return root / "audio", root / "memory"


def worker(cases, audio, output, model):
    emit(output, {"type": "phase", "phase": "startup"})
    started, before = time.monotonic(), resources(os.getpid())
    try:
        visits, steps, wavs, duration = preflight(cases, audio)
        from robot.brain import SYSTEM, server_args
        from robot.camera import FileCamera
        from robot.main import Robot

        emit(output, {"type": "runtime", "system": SYSTEM, "server_args": server_args(model)})
        camera = FileCamera()
        audio_dir, memory_dir = run_paths(output)
        robot = Robot(
            camera,
            audio_dir,
            memory=memory_dir,
            model=model,
            wake_word=False,
        )
        measured = resources(os.getpid())
        emit(
            output,
            {
                "type": "startup", "elapsed_s": time.monotonic() - started, "resources": measured,
                "resource_delta": resource_delta(before, measured),
            },
        )
        result = evaluate(visits, steps, wavs, duration, robot, camera, output)
        emit(output, {"type": "phase", "phase": "cleanup", "resources": resources(os.getpid())})
        robot.close()
        camera.close()
        emit(
            output,
            {
                "type": "completion_ready",
                **result,
                "audio_dir": str(audio_dir.resolve()), "memory_dir": str(memory_dir.resolve()),
            },
        )
        return 0
    except Exception as exc:
        emit(output, {"type": "error", "error": repr(exc)})
        return 2


class Journal:
    """Read only complete flushed rows, retaining completion evidence rather than telemetry."""

    def __init__(self, output):
        self.output, self.cursor = output, 0
        self.events, self.utterances, self.ready, self.error = [], [], None, False
        self.phase = "startup"
        self.phase_at = self.progress_at = time.monotonic()

    def read(self):
        with self.output.open() as f:
            f.seek(self.cursor)
            while True:
                offset, line = f.tell(), f.readline()
                if not line or not line.endswith("\n"):
                    self.cursor = offset
                    return
                row = json.loads(line)
                self.cursor = f.tell()
                kind = row.get("type")
                if kind == "event":
                    self.events.append(row["id"])
                elif kind == "utterance":
                    self.utterances.append(row["id"])
                elif kind == "error":
                    self.error = True
                elif kind == "phase":
                    self.phase, self.phase_at = row["phase"], time.monotonic()
                elif kind == "progress":
                    self.progress_at = time.monotonic()
                elif kind == "completion_ready":
                    self.ready = row

    def valid(self, expected, duration, event_ids, utterance_ids, visit_ids):
        return (
            self.ready is not None
            and self.ready["counts"] == expected
            and self.ready["elapsed_s"] >= duration
            and not self.error
            and self.ready["event_ids"] == self.events == event_ids
            and self.ready["utterance_ids"] == self.utterances == utterance_ids
            and self.ready["visit_ids"] == visit_ids
        )


def kill_group(proc):
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except PermissionError:
        # macOS can return EPERM when an exited group contains only orphan zombies.
        listing = subprocess.run(
            ["ps", "-axo", "pgid=,stat="], capture_output=True, text=True, check=True, timeout=2
        )
        if any(
            int(parts[0]) == proc.pid and not parts[1].startswith("Z")
            for line in listing.stdout.splitlines()
            if len(parts := line.split()) == 2
        ):
            raise
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        return False
    return True


def supervise(
    command, output, expected, duration, event_ids, utterance_ids, visit_ids, timeouts=None
):
    """Only this process publishes completion after successful worker teardown."""
    limits, journal = timeouts or TIMEOUTS, Journal(output)
    proc = subprocess.Popen(command, start_new_session=True)
    error, cleanup_attempted = None, False
    try:
        while proc.poll() is None:
            journal.read()
            since = (
                max(journal.phase_at, journal.progress_at)
                if journal.phase == "schedule"
                else journal.phase_at
            )
            if time.monotonic() - since > limits[journal.phase]:
                error = f"{journal.phase} progress timeout"
                break
            time.sleep(0.05)
        journal.read()  # Include final rows flushed immediately before process exit.
        if error is None and proc.returncode != 0:
            error = f"worker exited {proc.returncode}"
        try:
            os.killpg(proc.pid, 0)
        except ProcessLookupError:
            pass
        else:
            error = error or "worker left live process-group descendants"
        cleanup_attempted = True
        if not kill_group(proc):
            error = "worker reaping timed out after SIGKILL; outer named-unit recovery required"
        if error is None and not journal.valid(
            expected, duration, event_ids, utterance_ids, visit_ids
        ):
            error = "invalid completion-ready counts, duration, or event evidence"
        if error:
            emit(output, {"type": "error", "error": error, "supervisor": True})
            return 2
        emit(
            output,
            {
                "summary": "continuous", "completed": True,
                **journal.ready,
                "type": "completion", "worker_exit": 0,
            },
        )
        return int(journal.ready["failed_steps"] > 0)
    finally:
        if not cleanup_attempted and not kill_group(proc):
            emit(output, {"type": "error", "supervisor": True,
                          "error": "worker reaping timed out; outer named-unit recovery required"})


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cases", type=Path)
    ap.add_argument("--audio", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--model", default="qwen3vl-2b")
    ap.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.worker:
        return worker(args.cases, args.audio, args.output, args.model)
    visits, steps, _, duration = preflight(args.cases, args.audio)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Run-owned memory and audio paths must be fresh too.
    audio_dir, memory_dir = run_paths(args.output)
    for path in (args.output, audio_dir.parent):
        if path.exists():
            raise ValueError(f"run path already exists: {path}")
    emit(
        args.output,
        {
            "type": "metadata", "cases": str(args.cases), "sha256": digest(args.cases),
            "model": args.model, "machine": platform.node(), "command": sys.argv,
            "release": os.environ.get("ROBOT_RELEASE"), "expected": counts(visits, steps),
            "duration_s": duration, "audio_dir": str(audio_dir.resolve()),
            "memory_dir": str(memory_dir.resolve()), "lateness_s": LATENESS,
            "association_tolerance_s": TOLERANCE, "tegrastats": os.environ.get("ROBOT_TEGRASTATS"),
            "resources": resources(os.getpid()),
        },
    )
    return supervise(
        [
            sys.executable,
            "-m",
            "eval.continuous",
            str(args.cases),
            "--audio",
            str(args.audio),
            "--output",
            str(args.output),
            "--model",
            args.model,
            "--worker",
        ],
        args.output,
        counts(visits, steps),
        duration,
        [s["id"] for s in steps],
        [s["id"] for s in steps if "say" in s],
        [v["id"] for v in visits],
    )


if __name__ == "__main__":
    sys.exit(main())

"""Inject worker failures into the full Jetson robot with isolated test memories.

Run through tools/jetson.py run worker-failure -- -m bench.worker_failure --revision SHA.
"""
import argparse
import faulthandler
import gc
import json
import os
import platform
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np

from robot.brain import MODEL
from robot.camera import FileCamera
from robot.config import SHARED
from robot.main import Robot
from robot.head import Head, SimMotor
from robot import audio
from robot.tts import RATE


class FaultMotor(SimMotor):
    fault = False

    def read(self, now):
        if self.fault:
            raise RuntimeError("There is no status packet!")
        return super().read(now)


def wait_for(check, label):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(.05)
    raise AssertionError(label)


def head_trial(robot):
    wait_for(lambda: robot.detections > 3, "initial detection")
    robot.head.motor.fault = True
    wait_for(lambda: bool(robot.head.error), "injected motor fault")
    assert not robot.head.fatal_error and robot.head.release_confirmed
    goals, detected = list(robot.head.motor.goals), robot.detections
    wait_for(lambda: robot.detections > detected + 3 and
             robot.view_taken >= robot.head.valid_after, "post-fault detection")
    robot.ask("Look left.")
    warning = robot.next_turn(timeout=60)
    assert warning.answer == robot.head.warning, warning.answer
    assert warning.audio_s > 0
    assert robot.head.motor.goals == goals and robot.head.view_angle is None
    robot.check_health()
    return {"turns": [{"question": warning.question, "answer": warning.answer,
                       "audio_s": warning.audio_s, "wav": warning.wav}],
            "release_confirmed": True, "post_fault_detection": True,
            "motor_goals_after_fault": 0, "view_angle": None, "input": "oracle text"}


def play_checked(pcm, completed, errors):
    try:
        audio.aplay(audio.SPEAKER, RATE)(pcm)
        completed.append(len(pcm))
    except (OSError, subprocess.SubprocessError) as error:
        errors.append(str(error))
        raise


def trial(arm: str, memory: Path, out: Path) -> dict:
    camera = FileCamera()
    head = Head(FaultMotor()) if arm == "head" else None
    playback, playback_errors = [], []
    robot = Robot(camera, out / arm, memory=memory, wake_word=False, head=head,
                  play=(lambda pcm: play_checked(pcm, playback, playback_errors))
                  if arm == "head" else None)
    row = {"arm": arm}
    injected = RuntimeError(f"injected {arm} failure")

    def fail(*args):
        raise injected

    try:
        camera.show(Path("eval/dev/live/closet-cat-center.jpg" if arm == "head" else
                         "eval/dev/live/closet-night.jpg"))
        if arm == "head":
            row.update(head_trial(robot))
            robot.speaker.q.join()
            assert playback and not playback_errors, playback_errors
            row.update(speaker_phrases=len(playback), playback_errors=playback_errors)
        elif arm == "healthy":
            robot.ask("What is Qdrant Edge?")
            turn = robot.next_turn()
            assert turn.answer and turn.audio_s > 0, "healthy robot produced no speech"
            row["answer"], row["audio_s"] = turn.answer, turn.audio_s
        else:
            robot.recognition.pause()
            robot.jobs.join()
            robot.check_health()
            faulthandler.dump_traceback_later(30, exit=True)
            started = time.monotonic()
            if arm == "transcribe":
                robot.scribe = fail
                now = time.time()
                robot.lines.put((np.zeros(1600, np.float32), now, now, now,
                                 camera.latest(), None, None))
            else:
                robot._look = fail
                robot.jobs.put(("look", camera.latest()))
            try:
                robot.next_turn(timeout=5)
            except RuntimeError as error:
                assert error.__cause__ is injected, repr(error)
                row["reported"] = str(error)
            else:
                raise AssertionError("worker failure was not reported")
            row["report_s"] = time.monotonic() - started
    finally:
        started = time.monotonic()
        try:
            robot.close()
        except RuntimeError as error:
            if error.__cause__ is not injected:
                raise
            row["close_reported"] = str(error)
        finally:
            camera.close()
            faulthandler.cancel_dump_traceback_later()
        row["close_s"] = time.monotonic() - started
    assert all(not thread.is_alive() for thread in robot.threads)
    assert not robot.recognition.thread.is_alive() and not robot.speaker.thread.is_alive()
    assert robot.brain.proc.poll() is not None
    assert robot.lines.unfinished_tasks == robot.jobs.unfinished_tasks == 0
    row["ok"] = True
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--arm", choices=("healthy", "transcribe", "work", "head"))
    args = parser.parse_args()
    stamp = f"{time.strftime('%Y-%m-%d')}-worker-failure-{int(time.time())}"
    out = SHARED / "sessions" / stamp
    result = SHARED / "results" / f"{stamp}.jsonl"
    head = {"summary": "worker_failure", "revision": args.revision,
            "machine": platform.node(), "release": os.environ.get("ROBOT_RELEASE"),
            "tegrastats": os.environ.get("ROBOT_TEGRASTATS"), "model": MODEL,
            "python": platform.python_version(), "command": "python -m bench.worker_failure "
            f"--revision {args.revision}" + (f" --arm {args.arm}" if args.arm else ""),
            "complete": False}
    result.write_text(json.dumps(head) + "\n")
    arms = [args.arm] if args.arm else ("healthy", "transcribe", "work", "head")
    with tempfile.TemporaryDirectory() as memory:
        for arm in arms:
            row = trial(arm, Path(memory), out)
            with result.open("a") as file:
                file.write(json.dumps(row) + "\n")
            print(json.dumps(row), flush=True)
            gc.collect()  # release model sessions before reopening the same test shards
    with result.open("a") as file:
        file.write(json.dumps({**head, "complete": True, "n": len(arms)}) + "\n")
    print(f"results: {result}", flush=True)


if __name__ == "__main__":
    main()

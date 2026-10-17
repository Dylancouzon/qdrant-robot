"""Exercise full Jetson models with a camera rendered from a finite-speed simulated head.

Use only development portraits. This makes no serial connection and moves no hardware.
"""
import argparse
import contextlib
import json
import os
import platform
import subprocess
import threading
import time
from collections import Counter, deque
from pathlib import Path

import cv2
import numpy as np

from robot.config import ROOT, SHARED
from robot.head import Head, SimMotor
from robot.main import Robot
from robot.detect import CONFIRM, Detector, Tracker


def load(path):
    image = cv2.imread(str(path))
    if image is None:
        raise RuntimeError(f"Cannot read development fixture: {path}")
    return cv2.resize(image, (1280, 720))


class TurningCamera:
    """A cylindrical 60-degree view; every source pixel depends on measured simulated yaw."""
    def __init__(self, head, center, left, right):
        self.head = head
        self.center, self.left, self.right = center, left, right
        self.bearing, self.hidden = 0., False
        self.lock = threading.Lock()
        self.frames = []

    def latest(self):
        with self.lock:
            panorama = np.zeros((720, 5120, 3), np.uint8)
            panorama[:, 960:2240] = self.left
            panorama[:, 2880:4160] = self.right
            shift = round(self.bearing * 1280 / 60)
            if not self.hidden:
                panorama[:, 1920 + shift:3200 + shift] = self.center
            angle = self.head.angle
            start = round(1920 + angle * 1280 / 60)
            frame = panorama[:, start:start + 1280].copy()
            stamp = time.time()
            self.frames.append((stamp, angle))
            return frame, stamp

    def set_center(self, frame, bearing=0.):
        with self.lock:
            self.center, self.bearing = frame, bearing


def pair(known, unknown):
    frame = np.zeros((720, 1280, 3), np.uint8)
    frame[180:540, 160:800] = cv2.resize(known, (640, 360))
    frame[216:504, 728:1240] = cv2.resize(unknown, (512, 288))
    return frame


def person_admission(frame):
    """Compare identical raw and JPEG pixels at the unchanged detector admission threshold."""
    detector = Detector()
    result = {}
    try:
        encoded = cv2.imencode(".jpg", frame)[1]
        for mode, image in (("raw", frame), ("jpeg", cv2.imdecode(encoded, cv2.IMREAD_COLOR))):
            detections, tracker = detector(image), Tracker()
            for _ in range(CONFIRM):
                tracker.update(detections, 1280, time.time())
            result[mode] = {"person_scores": [d.conf for d in detections if d.label == "person"],
                            "admitted_people": sum(t[2] == "person" for t in tracker.scored())}
    finally:
        detector.close()
    return result


def until(predicate, timeout, label):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if result := predicate():
            return result
        time.sleep(.1)
    raise RuntimeError(f"Timed out: {label}")


def converse(robot, text):
    robot.ask(text)
    turn = robot.next_turn(timeout=90)
    robot.jobs.join()
    robot.check_health()
    print(json.dumps({"question": text, "answer": turn.answer,
                      "visitor": turn.visitor, "angle": turn.view_angle,
                      "head": head_state(robot.head)}), flush=True)
    return turn


def head_state(head):
    return {name: getattr(head, name) for name in (
        "angle", "goal", "moving", "halt", "paused", "inspecting", "following", "error",
        "generation", "settled")}


def compare_streaming_description(robot, turn):
    """Measure the unused image-only streaming alternative on the identical retained source."""
    look = next(look for look in robot.looked if look.taken == turn.looked)
    robot.ui_thinking = True
    robot.jobs.join()
    request = [{"role": "user", "content": [look.image, {
        "type": "text", "text": "Describe what you see in one short sentence."}]}]
    started, first, parts = time.time(), None, []
    try:
        for delta in robot.brain.answer(request):
            first = first if first is not None else time.time() - started
            parts.append(delta)
    finally:
        robot.ready, robot.ui_thinking = None, False
    return {"source_time": look.taken, "view_angle": turn.view_angle,
            "caption": turn.visual_caption, "caption_s": turn.caption_s,
            "isolated_stream": "".join(parts), "first_stream_token_s": first,
            "stream_s": time.time() - started}


def trace_following(robot, report):
    """Keep a bounded trace at the existing following boundary, without changing its decisions."""
    follow, preview = robot._follow_face, robot.recognition.preview
    counts, samples = Counter(), deque(maxlen=2048)
    report["following_diagnostics"] = {"counts": counts, "samples": samples}
    def observe(selected, width, taken, generation=None):
        reason = follow(selected, width, taken, generation)
        counts[reason] += 1
        motor = robot.head.motor
        samples.append({"age_ms": round(1000 * (time.time() - taken), 1),
                        "source_time": taken,
                        "face_error": ((selected.box[0] + selected.box[2]) / (2 * width) - .5)
                        if selected else None,
                        "encoder_position": getattr(motor, "position", None),
                        "encoder_goal": getattr(motor, "target", None),
                        "feedback": getattr(motor, "status", None),
                        "progress_age_s": time.monotonic() - motor.progress
                        if hasattr(motor, "progress") else None,
                        "name": selected.name if selected else None, "reason": reason,
                        "head": head_state(robot.head), "tracks": [
                            row for row in robot.tracker.scored() if row[2] == "person"]})
        return reason
    def frame(*args):
        counts["preview"] += 1
        counts["expired at preview"] += time.time() - args[1] > .75
        return preview(*args)
    robot._follow_face, robot.recognition.preview = observe, frame


def baseline_choice(release, known, two):
    code = """
import json, sys, tempfile
import cv2
from pathlib import Path
from robot.faces import Faces
from robot.people import People, face
faces = Faces()
with tempfile.TemporaryDirectory() as folder:
    people = People(Path(folder))
    known = face(faces, cv2.imread(sys.argv[1]))
    assert known is not None
    assert people.enroll('Dylan', [known[0], known[0]], 1.)
    chosen = face(faces, cv2.imread(sys.argv[2]))
    matched = people.identify(chosen[0]) if chosen else None
    print(json.dumps({'selected_known': bool(matched),
                      'selected_name': matched[0] if matched else None}))
    people.shard.close()
"""
    result = subprocess.run([str(release / ".venv/bin/python"), "-c", code, str(known), str(two)],
                            cwd=release, env={**os.environ, "PYTHONPATH": str(release)},
                            check=True, capture_output=True, text=True)
    return json.loads(result.stdout.splitlines()[-1])


def run(robot, camera, known, two):
    turns = []
    turns.append(converse(robot, "Remember me, my name is Dylan."))
    turns.append(converse(robot, "Yes."))
    dylan = robot.people.person("Dylan")
    assert dylan, "Consented enrollment failed"
    camera.set_center(two)
    time.sleep(2)
    turns.append(introduction := converse(robot, "My name is Sam."))
    assert introduction.visitor != dylan["visitor"] and not introduction.selection_error
    assert robot.people.person("Sam") is None, "Introduction alone enrolled a face"
    turns.append(converse(robot, "Yes."))
    sam = robot.people.person("Sam")
    assert sam and sam["visitor"] == introduction.visitor
    # The turn is logged before the return finishes; join above waits for the worker as well.
    before = robot.detections
    began = time.time()
    until(lambda: abs(robot.head.angle) > 8, 18, "following moves toward selected Sam")
    time.sleep(3)
    def centered():
        frame, _ = camera.latest()
        selected, error = robot.recognition.call(lambda f, c: robot._select_face(f, frame))
        return selected and not error and selected.name == "Sam" and not robot.head.moving and \
            abs((selected.box[0] + selected.box[2]) / 2560 - .5) <= .065
    until(centered, 15, "selected Sam reaches the central camera band")
    following = {"seconds": time.time() - began, "angle": robot.head.angle,
                 "detection_fps": (robot.detections - before) / (time.time() - began)}
    camera.set_center(pair(load(ROOT / "eval/faces/scenes/dev-p06-enroll-a.jpg"), known))
    until(lambda: robot.head.angle < -3 and centered(), 20,
          "Sam stays selected after position swap")
    assert robot.current_visitor == sam["visitor"]
    crossed = robot.head.angle
    camera.set_center(known)
    time.sleep(1)
    assert abs(robot.head.angle - crossed) < .2, "Dylan cannot take over when Sam leaves"
    camera.set_center(two)
    until(centered, 20, "fresh recognition reacquires Sam")
    robot._control("stop_head", {})
    time.sleep(.4)
    held = robot.head.angle
    camera.hidden = True
    time.sleep(.6)
    assert abs(robot.head.angle - held) < .2 and not robot.head.following
    camera.hidden = False
    camera.set_center(two)
    turns.append(converse(robot, "Talk to Sam."))
    before_frame = len(camera.frames)
    turns.append(right := converse(robot, "What is on your right?"))
    assert abs(right.view_angle - 45) < .2
    assert any(stamp == right.looked and abs(angle - 45) < .2
               for stamp, angle in camera.frames[before_frame:])
    assert "stop" in right.answer.lower() or "sign" in right.answer.lower(), right.answer
    right_compare = compare_streaming_description(robot, right)
    turns.append(left := converse(robot, "What is on your left?"))
    assert abs(left.view_angle + 45) < .2
    assert "cat" in left.answer.lower(), left.answer
    left_compare = compare_streaming_description(robot, left)
    turns.append(converse(robot, "Forget me."))
    turns.append(deleted := converse(robot, "Yes."))
    assert deleted.deleted and robot.people.person("Sam") is None
    assert robot.people.person("Dylan") and not robot.head.following
    assert all(abs(goal) <= 70 for goal in robot.head.motor.goals)
    return {"following": following, "description_comparison": {
        "right": right_compare, "left": left_compare}, "turns": [
        {"question": t.question, "answer": t.answer, "visitor": t.visitor,
         "view_angle": t.view_angle, "looked": t.looked,
         "caption": t.visual_caption, "caption_s": t.caption_s,
         "detection_fps": t.detect_fps, "identity": t.identity,
         "first_text_s": t.first_token - t.speech_end if t.first_token else None,
         "speech_ready_s": t.first_audio - t.speech_end if t.first_audio else None}
        for t in turns], "goals": robot.head.motor.goals}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()
    known = load(ROOT / "eval/faces/scenes/dev-p05-enroll-a.jpg")
    unknown = load(ROOT / "eval/faces/scenes/dev-p06-enroll-a.jpg")
    two = pair(known, unknown)
    result = {"machine": platform.node(), "python": platform.python_version(),
              "release": ROOT.name, "input": "oracle text; rotating development photo panorama",
              "motor": "simulated, 20 degrees/s, +/-70 degrees", "hardware_motion": False,
              "tegrastats": os.environ.get("ROBOT_TEGRASTATS"), "status": "failed"}
    output = SHARED / "results" / f"2026-10-16-head-sim-{int(time.time())}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    folder = SHARED / "experiments" / f"head-sim-{int(time.time())}"
    folder.mkdir(parents=True, exist_ok=False)
    try:
        known_path, two_path = folder / "known.jpg", folder / "pair.jpg"
        cv2.imwrite(str(known_path), known)
        cv2.imwrite(str(two_path), two)
        robot = None
        try:
            if args.baseline:
                result["baseline_release"] = args.baseline.name
                result["baseline"] = baseline_choice(args.baseline, known_path, two_path)
            result["person_admission"] = person_admission(two)
            head = Head(SimMotor())
            camera = TurningCamera(head, known, load(ROOT / "eval/dev/live/closet-cat-center.jpg"),
                                   load(ROOT / "eval/dev/live/closet-stopsign-center.jpg"))
            robot = Robot(camera, folder / "session", folder / "memory", play=lambda pcm: None,
                          wake_word=False, head=head)
            trace_following(robot, result)
            result.update(run(robot, camera, known, two))
            result["status"] = "passed"
        except Exception as error:
            result["error"] = f"{type(error).__name__}: {error}"
            raise
        finally:
            if robot is not None:
                result["final_head"] = head_state(robot.head)
                result["goals"] = list(robot.head.motor.goals)
                with contextlib.suppress(Exception):
                    robot.close()
            if "following_diagnostics" in result:
                result["following_diagnostics"]["samples"] = list(
                    result["following_diagnostics"]["samples"])
            turns_file = folder / "session/turns.jsonl"
            if turns_file.exists() and "turns" not in result:
                keys = ("question", "answer", "visitor", "looked", "view_angle", "caption_s",
                        "visual_caption", "selection_error", "verbatim", "kind")
                result["turns"] = [{key: row.get(key) for key in keys} for row in (
                    json.loads(line) for line in turns_file.read_text().splitlines())]
            output.write_text(json.dumps(result, indent=2) + "\n")
            print(f"result: {output}", flush=True)
    finally:
        print(f"session evidence: {folder}", flush=True)


if __name__ == "__main__":
    main()

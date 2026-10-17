"""Multi-person handover, ownership, consent, and deletion through real robot turns and Edge."""
import queue
import threading
import time
import base64
from types import SimpleNamespace

import numpy as np
import pytest
import cv2

from robot import main
from robot.detect import CONFIRM, Detection
from robot.main import Turn
from robot.people import DIM
from robot.head import Head, SimMotor
from robot.test_things import GOLD, close_robot, open_robot
from robot.text_embed import DIM as TEXT_DIM


def speaking_robot(root):
    robot = open_robot(root)
    robot.turns, robot.ready = queue.Queue(), None
    robot.last_frame, robot.exchanges, robot.detections = None, 0, 0
    robot.stream = None
    robot.embed = lambda texts: np.eye(TEXT_DIM, dtype=np.float32)[[0] * len(texts)]
    robot.knowledge = SimpleNamespace(search=lambda q: [])
    robot.route = lambda q: "social"
    robot.brain = SimpleNamespace(prefill=lambda m: None,
                                  answer=lambda m, **k: (t for t in ["Okay."]))
    robot.voice = SimpleNamespace(say=lambda text: np.zeros(160, np.float32))
    robot.speaker = SimpleNamespace(play=lambda pcm: None, playing=lambda *a: False)
    return robot


def answer(robot, text, frame):
    stamp = time.time()
    turn = Turn(question=text, speech_start=stamp, speech_end=stamp, line=stamp,
                target=robot.focus.focus if robot.focus else None)
    robot._turn(turn, (frame, stamp))
    return turn


def test_unknown_introduction_beside_known_visitor_and_owner_handover(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "SETTLE_S", 0)
    vectors = np.eye(DIM, dtype=np.float32)
    source_faces = {}
    monkeypatch.setattr(main, "located_faces", lambda faces, frame: source_faces[id(frame)])
    robot = speaking_robot(tmp_path)
    try:
        assert robot.people.enroll("Dylan", [vectors[0], vectors[0]], time.time())
        frame = np.zeros((720, 1280, 3), np.uint8)
        frame[300:600, 850:1050] = GOLD
        source_faces[id(frame)] = [(vectors[0], 120, (250, 80, 370, 200)),
                                   (vectors[1], 120, (900, 80, 1020, 200))]
        detections = [Detection("person", .9, (150, 50, 500, 700)),
                      Detection("person", .9, (800, 50, 1150, 700)),
                      Detection("phone", .9, (850, 300, 1050, 600))]
        for _ in range(CONFIRM):
            robot._track(frame, detections, time.time())
        robot.focus.focus = next(i for i, (label, _) in robot.view[1].items() if label == "phone")
        assert "Dylan" in answer(robot, "What is my name?", frame).answer
        dylan = robot.current_visitor
        introduced = answer(robot, "My name is Sam.", frame)
        sam = introduced.visitor
        assert sam != dylan and "Sam" in introduced.answer
        assert robot.people.person("Sam") is None, "An introduction never enrolls a face"
        assert robot.people.person("Dylan")["visitor"] == dylan
        named = answer(robot, "This is my phone.", frame)
        assert named.answer.startswith("Got it")
        assert robot.things.named(sam, "phone", []) and not robot.things.named(dylan, "phone", [])
        answer(robot, "Remember me, I am Sam.", frame)
        assert robot.asking
        assert "Sam" in answer(robot, "Yes.", frame).answer
        assert robot.people.person("Sam")["visitor"] == sam
        assert answer(robot, "Forget my phone.", frame).answer.startswith("Should I")
        assert robot.deleting
        assert answer(robot, "Talk to Dylan.", frame).answer == "I am talking to Dylan now."
        assert robot.current_visitor == dylan and robot.deleting is None
        answer(robot, "Yes.", frame)
        assert robot.things.named(sam, "phone", []), "A handover cancels the pending deletion"
        assert answer(robot, "Talk to Sam.", frame).visitor == sam
        assert answer(robot, "Forget me.", frame).answer.startswith("Should I")
        deleted = answer(robot, "Yes.", frame)
        assert deleted.deleted and robot.people.person("Sam") is None
        assert not robot.things.objects(sam) and robot.people.person("Dylan")
        assert not robot.head.following
    finally:
        close_robot(robot)


def test_ambiguous_introduction_and_spoken_name_never_authorize_identity(tmp_path, monkeypatch):
    robot = speaking_robot(tmp_path)
    vectors = np.eye(DIM, dtype=np.float32)
    frame = np.zeros((720, 1280, 3), np.uint8)
    monkeypatch.setattr(main, "located_faces", lambda f, image: [
        (vectors[0], 120, (100, 100, 220, 220)),
        (vectors[1], 120, (800, 100, 920, 220))])
    try:
        robot.head.request("stop")
        before = robot.current_visitor
        introduced = answer(robot, "I am Sam.", frame)
        assert introduced.selection_error and not introduced.keep
        assert robot.current_visitor == before and not robot.asking
        selected = answer(robot, "Talk to Sam.", frame)
        assert selected.selection_error and robot.people.person("Sam") is None
        assert not robot.head.following, "An unverified name cannot re-enable following"
        assert not robot.memory.told(np.eye(TEXT_DIM)[0], time.time() + 1)
    finally:
        close_robot(robot)


def test_fresh_verified_face_follows_without_admitted_body_tracks(tmp_path, monkeypatch):
    robot = speaking_robot(tmp_path)
    robot.head = Head(SimMotor())
    vector = np.eye(DIM, dtype=np.float32)[0]
    frame = np.zeros((720, 1280, 3), np.uint8)
    monkeypatch.setattr(main, "located_faces", lambda f, image: [
        (vector, 64, (950, 284, 1014, 368))])
    try:
        robot.people.enroll("Sam", [vector, vector], time.time())
        robot.face = vector
        robot.current_visitor = robot.people.person("Sam")["visitor"]
        robot.head.start()
        time.sleep(.2)
        taken = time.time()
        robot._track(frame, [], taken)
        robot._preview(frame, taken, [], {}, robot.session_id, {}, robot.recognition.epoch)
        assert not robot.tracker.scored() and robot.head.goal > 0
        robot.head.request("stop")
        time.sleep(.1)
        held = robot.head.goal
        robot._preview(frame, taken - 1, [], {}, robot.session_id, {}, robot.recognition.epoch)
        assert robot.head.goal == held, "An expired source cannot restart following"
    finally:
        robot.head.close()
        close_robot(robot)


def test_lost_face_without_body_track_preserves_owner_and_blocks_deletion(tmp_path, monkeypatch):
    robot = speaking_robot(tmp_path)
    vector = np.eye(DIM, dtype=np.float32)[0]
    visible = [True]
    frame = np.zeros((720, 1280, 3), np.uint8)
    monkeypatch.setattr(main, "located_faces", lambda f, image: [
        (vector, 64, (950, 284, 1014, 368))] if visible[0] else [])
    try:
        robot.people.enroll("Sam", [vector, vector], time.time())
        first = answer(robot, "What is my name?", frame)
        owner = first.visitor
        assert robot.face is not None and robot.face_track is None
        visible[0] = False
        lost = answer(robot, "Forget me.", frame)
        assert lost.selection_error and not lost.keep
        assert robot.current_visitor == owner and robot.deleting is None
        answer(robot, "Yes.", frame)
        assert robot.people.person("Sam")["visitor"] == owner
        visible[0] = True
        assert answer(robot, "Forget me.", frame).answer.startswith("Should I")
        assert answer(robot, "Yes.", frame).deleted and robot.people.person("Sam") is None
    finally:
        close_robot(robot)


@pytest.mark.parametrize("caption", [None, "", "A description with no requested structure."])
def test_malformed_inspection_caption_has_no_conversation_fallback(tmp_path, caption):
    robot = speaking_robot(tmp_path)
    seen = []
    def describe(image, cancel):
        seen.append(image)
        return caption
    def forbidden(*args, **kwargs):
        raise AssertionError("Inspection must not use conversational inference or retrieval")
    robot.brain.caption, robot.brain.answer, robot.brain.prefill = describe, forbidden, forbidden
    robot.knowledge.search = forbidden
    frame = np.full((720, 1280, 3), 120, np.uint8)
    stamp = time.time()
    turn = Turn(question="What is on your right?", speech_start=stamp, line=stamp,
                visitor=robot.current_visitor, view_angle=45.)
    try:
        robot._inspection_turn(turn, (frame, stamp), (frame, stamp))
        assert len(seen) == 1 and "could not describe" in turn.answer
        assert turn.visual_caption == (caption or "") and turn.looked == stamp
        assert robot.looked[-1].frame is frame
    finally:
        close_robot(robot)


def test_foreground_inspection_cancels_when_stop_arrives(tmp_path):
    from robot.head import Interrupted
    robot = speaking_robot(tmp_path)
    def caption(image, cancel):
        robot.head.request("stop")
        assert cancel()
        return None
    robot.brain.caption = caption
    stamp = time.time()
    frame = np.zeros((720, 1280, 3), np.uint8)
    turn = Turn(question="What is on your left?", visitor=robot.current_visitor,
                motion=robot.head.request("left"))
    try:
        with pytest.raises(Interrupted):
            robot._inspection_turn(turn, (frame, stamp), (frame, stamp))
        assert not robot.head.following and not robot.looked and not turn.frame_id
    finally:
        close_robot(robot)


@pytest.mark.parametrize("start, side, angle, color", [
    (0., "right", 45., 210), (0., "left", -45., 30),
    (-60., "left", -45., 30), (-45., "left", -45., 30), (60., "left", -45., 30),
])
def test_inspection_uses_settled_view_and_returns_before_following(
        tmp_path, monkeypatch, start, side, angle, color):
    from bench.head_sim import TurningCamera
    robot = speaking_robot(tmp_path)
    motor = SimMotor(angle=start, speed=40)
    motor.limit = 60
    head = Head(motor)
    robot.head = head
    robot.knowledge.search = lambda q: [(1., "An unrelated knowledge answer.")]
    requests = []
    def caption(image, cancel):
        requests.append(main.brain.caption_messages(image))
        assert not cancel()
        data = image["image_url"]["url"].split(",", 1)[1]
        decoded = cv2.imdecode(np.frombuffer(base64.b64decode(data), np.uint8), cv2.IMREAD_COLOR)
        assert abs(int(decoded[decoded.shape[0] // 2, decoded.shape[1] // 2, 0]) - color) <= 1
        return "Main object: a test object. Around it: the room."
    robot.brain.caption = caption
    robot.history = [{"role": "user", "content": "Talk to Sam."},
                     {"role": "assistant", "content": "I am Edgy, a small robot."}]
    center = np.full((720, 1280, 3), 100, np.uint8)
    camera = TurningCamera(head, center, np.full_like(center, 30), np.full_like(center, 210))
    robot.camera = camera
    vector = np.eye(DIM, dtype=np.float32)[0]
    monkeypatch.setattr(main, "located_faces", lambda f, frame: [
        (vector, 120, (500, 100, 620, 220))] if frame[360, 640, 0] == 100 else [])
    stopped, failures = threading.Event(), []
    def detect():
        try:
            while not stopped.wait(.03):
                frame, taken = camera.latest()
                detections = [Detection("person", .9, (400, 50, 800, 700))] \
                    if frame[360, 640, 0] == 100 else []
                robot._track(frame, detections, taken)
        except Exception as error:
            failures.append(error)
    worker = threading.Thread(target=detect)
    head.start()
    worker.start()
    try:
        time.sleep(.2)
        robot.asking = "Sam", 1, [vector]
        turn = answer(robot, f"What is on your {side}?", camera.latest()[0])
        assert not turn.selection_error and turn.view_angle == angle
        assert not turn.verbatim and "unrelated" not in turn.answer
        assert turn.caption == "demand" and turn.visual_caption.startswith("Main object:")
        assert robot.asking is None and robot.people.person("Sam") is None
        assert len(requests) == 1 and len(requests[0]) == 1
        assert requests[0][0]["role"] == "user"
        assert turn.prompt == main.prompt_text(requests[0])
        assert any(stamp == turn.looked and yaw == angle for stamp, yaw in camera.frames)
        assert robot.looked[-1].frame[360, 640, 0] == color
        assert head.angle == start and not head.inspecting and head.following
        assert all(abs(goal) <= 60 for goal in motor.goals)
        assert not failures
    finally:
        stopped.set()
        worker.join()
        head.close()
        close_robot(robot)


def test_inspection_without_source_keeps_camera_error_and_never_uses_center(tmp_path):
    robot = speaking_robot(tmp_path)
    frame = np.zeros((720, 1280, 3), np.uint8)
    robot._look((frame, time.time()))
    robot.brain.answer = lambda *args, **kwargs: pytest.fail("Center view reached the brain")
    try:
        turn = answer(robot, "What is on your left?", None)
        assert turn.answer == "I need a camera image before turning."
        assert not turn.keep and turn.selection_error and not turn.prompt
    finally:
        close_robot(robot)


def test_wake_rejected_queued_command_cannot_override_later_stop(tmp_path):
    robot = speaking_robot(tmp_path)
    robot.wake_word, robot.last_line = True, 0
    frame = np.zeros((720, 1280, 3), np.uint8)
    turn = Turn(question="Look right.", speech_start=time.time())
    try:
        robot._motion_request(turn)
        assert turn.motion == -1
        stop = robot.head.request("stop")
        robot.last_line = turn.speech_start
        robot._turn(turn, (frame, time.time()))
        assert turn.kind == "background" and robot.head.generation == stop
        assert not robot.head.following
    finally:
        close_robot(robot)


def test_recall_keeps_other_angles_but_does_not_claim_visible_labels_missing(tmp_path):
    robot = speaking_robot(tmp_path)
    frame = np.zeros((720, 1280, 3), np.uint8)
    robot.head.angle = 3
    stamp = time.time()
    try:
        from robot.things import DIM as OBJECT_DIM
        vectors = np.eye(OBJECT_DIM, dtype=np.float32)[[0]]
        ident = robot.things.name(robot.conversation_visitor, "book", ["book"], vectors,
                                  [frame[:12, :20]])
        robot.memory.sighting("book", "left", stamp - 1, named=ident, view_angle=0)
        _, lines = robot._recall(Turn(question="What did you see?", speech_start=stamp), frame)
        assert any("book" in line for line in lines)
        robot.view = frame, {1: ("book", (10, 10, 100, 100))}
        _, lines = robot._recall(Turn(question="What did you see?", speech_start=stamp), frame)
        assert not any("book" in line and "not in view" in line for line in lines)
        robot.head = Head(SimMotor())
        robot.head.moving = True
        robot.view = frame, {}
        _, lines = robot._recall(Turn(question="What did you see?", speech_start=stamp), frame)
        assert not any("not in view" in line for line in lines)
        robot.head.close()
    finally:
        close_robot(robot)


@pytest.mark.parametrize('interrupted,stop_after', [(False, False), (True, False), (True, True)])
def test_thermal_inspection_warning_uses_speech_without_stopping_conversation(
        tmp_path, monkeypatch, interrupted, stop_after):
    from robot.head import Interrupted
    robot = speaking_robot(tmp_path)
    motor = SimMotor()
    robot.head = Head(motor)
    robot.head.tick(time.time())
    spoken = []
    robot.voice.say = lambda text: (spoken.append(text) or np.zeros(160, np.float32))
    robot.brain.answer = lambda m, **k: (t for t in ([] if k.get('prior') else ['Okay.']))
    monkeypatch.setattr(main, 'located_faces', lambda *args: [])
    def overheat():
        motor.cooling, motor.thermal_latched = True, False
        motor.cooldown_until = time.monotonic() + 180
        motor.target = motor.angle
        robot.head.tick(time.time())
    frame = np.zeros((720, 1280, 3), np.uint8)
    if interrupted:
        def inspect(turn, shot):
            turn.caption, turn.visual_caption, turn.caption_s = 'demand', 'A cancelled view.', .2
            turn.delivered, turn.looked, turn.view_angle = True, time.time(), -45.
            overheat()
            if stop_after:
                robot.head.request('stop')
            raise Interrupted('Head movement was cancelled.')
        robot._inspect = inspect
    else:
        overheat()
    try:
        turn = answer(robot, 'What is on your left?', frame)
        assert robot.head.cooling and not robot.head.error
        robot.check_health()
        if stop_after:
            assert not spoken and not robot.head.following
        else:
            assert 'Head motor cooling' in turn.answer and spoken
            assert not turn.keep and not turn.frame_id and not turn.visual_caption
            assert not turn.caption and not turn.caption_s and not turn.delivered
        spoken.clear()
        ordinary = answer(robot, 'How are you?', frame)
        assert ordinary.answer == 'Okay.' and spoken
        robot.check_health()
        assert motor.goals == [0.]
    finally:
        close_robot(robot)

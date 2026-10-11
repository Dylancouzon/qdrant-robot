"""Measure object drawing against a previous Focus implementation, or receive live MJPEG.

Run paired checks on the Mac with --baseline PATH. Run --live on the Jetson through tools/jetson.py.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import numpy as np

from robot import focus as F
from robot.config import SHARED
from robot.detect import Detection, Tracker


def motion(module):
    rows = {}
    for speed in (0, 5, 20, 40, 80):
        focus, errors = module.Focus(1280, 720), []
        for k in range(20):
            x = 400 + (4 if k % 2 else -4) if speed == 0 else 100 + speed * k
            track = module.Track(1, (x, 200, x + 180, 380), 'phone', .9)
            focus.update(10 + k / 15, [track], [])
            errors.append((focus.geometry([track])[1][0] - x) ** 2)
        rows[str(speed)] = {'rms_px': math.sqrt(sum(errors[5:]) / len(errors[5:])),
                            'final_lag_px': x - focus.geometry([track])[1][0]}
    return rows


def recorded(module, path):
    tracker, focus = Tracker(), module.Focus(1280, 720)
    counts = {'frames': 0, 'carried_boxes': 0, 'selected_without_outline': 0}
    for line in path.read_text().splitlines():
        row = json.loads(line)
        if 'dets' not in row:
            continue
        taken = row['t']
        # This clip was already used for development. Keep the comparison within its first half.
        if taken > 45:
            break
        tracker.update([Detection(d[0], d[1], tuple(d[2:])) for d in row['dets']], 1280, taken)
        tracks = [module.Track(*t) for t in tracker.scored()]
        focus.update(taken, tracks, [t.box for t in tracks if t.label == 'person'])
        boxes = focus.boxes(tracks, [])
        if hasattr(focus, 'carried'):
            carried = focus.carried(tracks, taken, taken)
            boxes += list(carried.values())
            counts['carried_boxes'] += len(carried)
        counts['frames'] += 1
        counts['selected_without_outline'] += bool(focus.focus and not any(
            b[5] == 'focus' for b in boxes))
    return counts


def paired(baseline_path, clip):
    spec = importlib.util.spec_from_file_location('baseline_focus', baseline_path)
    baseline = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = baseline
    spec.loader.exec_module(baseline)
    before, after = motion(baseline), motion(F)
    assert after['0']['rms_px'] <= before['0']['rms_px'] + .1
    assert all(after[str(s)]['final_lag_px'] <= before[str(s)]['final_lag_px']
               for s in (5, 20, 40, 80))
    return {'input': 'deterministic trajectories and existing development detections',
            'baseline_sha256': hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
            'motion': {'baseline': before, 'candidate': after},
            'clip': str(clip), 'clip_sha256': hashlib.sha256(clip.read_bytes()).hexdigest(),
            'recorded': {'baseline': recorded(baseline, clip), 'candidate': recorded(F, clip)}}



def watch(url, stop, encoded, received, errors):
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            while not stop.is_set():
                if response.readline().strip() != b'--frame':
                    continue
                headers = {}
                while line := response.readline().strip():
                    key, value = line.split(b':', 1)
                    headers[key.lower()] = value.strip()
                jpeg = response.read(int(headers[b'content-length']))
                row = dict(encoded[hashlib.sha256(jpeg).hexdigest()])
                row['received'] = time.time()
                received.append(row)
    except Exception as error:
        if not stop.is_set():
            errors.append(repr(error))

def live(seconds):
    from robot import main, view
    from robot.camera import Camera
    camera, robot = Camera(), None
    encoded, received, errors, rejected = {}, [], [], []
    original = view.draw
    stop = threading.Event()
    def draw(frame, screen, width, now):
        jpeg = original(frame, screen, width, now)
        encoded[hashlib.sha256(jpeg).hexdigest()] = {
            'capture': screen.source[0], 'boxes': screen.boxes, 'encoded': now}
        return jpeg
    os.environ['ROBOT_VIEW_TOKEN'] = 'overlay-bench'
    viewer = None
    with tempfile.TemporaryDirectory(dir=SHARED) as temp:
        try:
            time.sleep(2)
            frame = camera.latest()[0]
            light = float(frame.mean()) if frame is not None else 0
            assert light >= 20, f'Camera unavailable or too dark: {light}'
            robot = main.Robot(camera, Path(temp) / 'audio', memory=Path(temp) / 'memory',
                               play=lambda pcm: None, wake_word=False)
            valid = robot._publication_valid
            def publication(*args):
                accepted = valid(*args)
                if not accepted:
                    rejected.append(time.time())
                return accepted
            robot._publication_valid = publication
            view.draw = draw
            viewer = threading.Thread(target=watch, args=(
                f'http://127.0.0.1:{robot.video.port}/?token=overlay-bench',
                stop, encoded, received, errors), daemon=True)
            viewer.start()
            start, detections = time.time(), robot.detections
            robot.ask('What is Qdrant Edge?')
            turn = robot.turns.get(timeout=90)
            while time.time() - start < seconds:
                time.sleep(.1)
            elapsed = time.time() - start
            assert not robot.detect_failed and not errors and len(received) >= 20, errors
            lags = [r['received'] - r['capture'] for r in received]
            intervals = np.diff([r['received'] for r in received])
            return {'input': 'fresh live camera and one oracle-text turn; isolated empty memory',
                    'brightness': light, 'seconds': elapsed, 'received_jpegs': len(received),
                    'rejected_publications': len(rejected),
                    'source_lag_p50_ms': 1000*float(np.median(lags)),
                    'source_lag_p95_ms': 1000*float(np.percentile(lags, 95)),
                    'received_interval_p95_ms': 1000*float(np.percentile(intervals, 95)),
                    'detector_fps': (robot.detections-detections)/elapsed,
                    'face_identity': 'No enrolled gallery; identity transitions covered by tests.',
                    'answer': turn.answer, 'complete': True}
        finally:
            stop.set()
            if robot:
                robot.close()
            if viewer:
                viewer.join(timeout=6)
            camera.close()
            view.draw = original


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--clip', type=Path,
                        default=Path('bench/results/2026-10-08-clip-1791487472.jsonl'))
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--seconds', type=float, default=15)
    args = parser.parse_args()
    if args.live == bool(args.baseline):
        parser.error('Choose --baseline PATH or --live.')
    result = live(args.seconds) if args.live else paired(args.baseline, args.clip)
    result |= {'what': 'bounded overlay continuity', 'machine': platform.node(),
               'release': os.environ.get('ROBOT_RELEASE'),
               'tegrastats': os.environ.get('ROBOT_TEGRASTATS'),
               'revision': subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True,
                                          text=True).stdout.strip(),
               'source_sha256': {p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
                                 for p in ('robot/focus.py', 'robot/main.py', 'bench/overlay.py')},
               'command': 'python -m bench.overlay ' + ' '.join(sys.argv[1:]),
               'python': sys.version, 'numpy': np.__version__}
    out = SHARED / 'results' if args.live else Path('bench/results')
    out.mkdir(parents=True, exist_ok=True)
    path = out / f'{time.strftime("%Y-%m-%d")}-overlay-{int(time.time())}.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()

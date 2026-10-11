"""Compare runtime box crops with YOLOE masks on the external D145 cup video.

    .venv/bin/python bench/crop_arms.py
"""
import hashlib
import json
import platform
import shlex
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from robot.config import DETECT_LOW, OBJECT_MIN_SIDE  # noqa: E402
from robot.detect import INPUT, MODEL, iou, letterbox  # noqa: E402
from robot.settings import DEFAULTS, settings  # noqa: E402
from robot.things import DIM, Crops, add_vectors, cut  # noqa: E402

settings.values = dict(DEFAULTS)  # benches measure the shipped defaults, never a live file
MATCH = DEFAULTS["match"]


def taught_gallery(vectors):
    """The runtime's taught gallery from the naming turn's shots."""
    return add_vectors(np.empty((0, DIM), np.float32), np.asarray(vectors))

DATA = ROOT / 'build/reconciliation-20261010/worktrees/mac-audio-interface/build'
ARMS = ('box', 'masked')


def frames(path):
    """Decode every frame, failing on missing input."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f'Cannot open {path}')
    try:
        index = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            yield index, frame
            index += 1
    finally:
        cap.release()


def detect(session, frame):
    blob, scale, left, top = letterbox(frame)
    out, protos = session.run(['output0', 'output1'], {'images': blob})
    rows = out[0][out[0, :, 4] >= DETECT_LOW]
    h, w = frame.shape[:2]
    boxes = np.clip((rows[:, :4] - [left, top, left, top]) / scale,
                    0, [w, h, w, h]).round().astype(int)
    return rows, boxes, protos[0], (scale, left, top)


def mask(coef, protos, box, scale, left, top, shape) -> np.ndarray:
    """Return the dilated segmentation mask inside an original-frame box."""
    logits = coef @ protos.reshape(32, -1)
    probability = (1 / (1 + np.exp(-np.clip(logits, -80, 80)))).reshape(protos.shape[1:])
    probability = cv2.resize(probability, (INPUT[1], INPUT[0]))
    h, w = shape[:2]
    probability = probability[top:top + round(h * scale), left:left + round(w * scale)]
    probability = cv2.resize(probability, (w, h))
    x1, y1, x2, y2 = box
    inside = (probability[y1:y2, x1:x2] > 0.5).astype(np.uint8)
    return cv2.dilate(inside, np.ones((7, 7), np.uint8)).astype(bool)


def crops(frame, row, box, protos, geometry):
    plain = cut(frame, tuple(box)).copy()
    masked = plain.copy()
    foreground = mask(row[6:], protos, box, *geometry, frame.shape)
    masked[~foreground] = 114
    return {'box': plain, 'masked': masked}, float(foreground.mean())


def percentiles(scores, levels):
    return {f'p{p}': float(np.percentile(scores, p)) if scores else None for p in levels}


def teach(session, encoder, protocol):
    """Build each gallery from the three runtime teaching shots."""
    shots = {arm: [] for arm in ARMS}
    teaching = []
    for index, frame in frames(DATA / 'd145/cup/cup-frame0-held.avi'):
        if index > 20:
            break
        if index not in (0, 10, 20):
            continue
        rows, boxes, protos, geometry = detect(session, frame)
        overlap = iou(boxes, np.array([protocol['boxes']['0']]))[:, 0]
        if not len(overlap) or overlap.max() < protocol['physical_overlap_min']:
            raise RuntimeError(f'Teaching detection missing at frame {index}')
        best = int(overlap.argmax())
        pair, fill = crops(frame, rows[best], boxes[best], protos, geometry)
        if min(pair['box'].shape[:2]) < OBJECT_MIN_SIDE:
            raise RuntimeError(f'Teaching crop too small at frame {index}')
        teaching.append({'frame': index, 'box': boxes[best].tolist(), 'iou': float(overlap[best]),
                         'mask_fill': fill})
        for arm in ARMS:
            shots[arm].append(pair[arm])
    assert all(len(values) == 3 for values in shots.values())
    return {arm: taught_gallery(encoder(shots[arm])) for arm in ARMS}, teaching


def classify(found, pair, values, record, counts, scores, examples, output, run, index):
    """Classify one cup frame and save the first four hits and misses per arm."""
    for arm in ARMS:
        score = values[arm] if found else None
        cause = 'no_detection' if not found else (
            'small' if min(pair[arm].shape[:2]) < OBJECT_MIN_SIDE else (
                'hit' if score >= MATCH else 'under_threshold'))
        counts[arm][cause] += 1
        if score is not None:
            scores[arm].append(score)
        record['arms'][arm] = {'cause': cause, 'score': score}
        category = 'hit' if cause == 'hit' else 'miss'
        if found and examples[arm][category] < 4:
            path = output / f'{run}-{arm}-{category}-{index:03}.jpg'
            assert cv2.imwrite(str(path), pair[arm])
            examples[arm][category] += 1


def score_pairs(pairs, encoder, galleries):
    vectors = encoder([p[arm] for p in pairs for arm in ARMS])
    return [{arm: float(np.max(vectors[2 * i + j] @ galleries[arm].T))
             for j, arm in enumerate(ARMS)} for i in range(len(pairs))]

def score_negatives(frame, rows, boxes, protos, geometry, indices, source, sink,
                    encoder, galleries, negatives, negative_sources):
    pairs, kept = [], []
    for i in indices:
        if min(boxes[i, 2:] - boxes[i, :2]) <= 0:
            raise RuntimeError(f'Empty negative box in {source}')
        pair, _ = crops(frame, rows[i], boxes[i], protos, geometry)
        pairs.append(pair)
        kept.append(int(i))
    # Bound encoder batches even if a frame has many detections.
    for start in range(0, len(pairs), 16):
        values_batch = score_pairs(pairs[start:start + 16], encoder, galleries)
        for i, values in zip(kept[start:start + 16], values_batch, strict=True):
            for arm in ARMS:
                negatives[arm].append(values[arm])
            negative_sources[source.split(':')[0]] += 1
            sink.write(json.dumps({'type': 'negative', 'source': source,
                                   'box': boxes[i].tolist(), 'scores': values}) + '\n')


def _mask_selftest():
    """The mask splits a box at a known prototype edge."""
    _, scale, left, top = letterbox(np.zeros((720, 1280, 3), np.uint8))
    protos = np.zeros((32, 96, 160), np.float32)
    protos[0] = -10
    protos[0, :, 80:] = 10
    coef = np.zeros(32, np.float32)
    coef[0] = 1
    known = mask(coef, protos, (600, 100, 680, 200), scale, left, top, (720, 1280))
    expected = np.zeros((100, 80), bool)
    expected[:, 37:] = True  # x=640 boundary, dilated three original pixels
    assert known.dtype == bool and np.array_equal(known, expected)
    assert not mask(-coef, np.abs(protos), (10, 10, 30, 30), scale, left, top,
                    (720, 1280)).any()


def main():
    run = str(int(time.time()))
    output = ROOT / 'build/crop-arms'
    output.mkdir(parents=True, exist_ok=True)
    protocol = json.loads((DATA / 'd145/cup/protocol.json').read_text())
    session = ort.InferenceSession(str(MODEL), providers=['CPUExecutionProvider'])
    encoder = Crops()
    assert encoder.sess.get_providers() == ['CPUExecutionProvider']
    galleries, teaching = teach(session, encoder, protocol)
    counts = {arm: Counter() for arm in ARMS}
    scores = {arm: [] for arm in ARMS}
    negatives = {arm: [] for arm in ARMS}
    examples = {arm: Counter() for arm in ARMS}
    negative_sources = Counter()
    total = 0

    with (output / f'{run}.jsonl').open('w') as sink:
        for index, frame in frames(DATA / 'd140/external/cup-batch-5-3.avi'):
            total += 1
            reference = np.array([protocol['boxes'][str(index)]])
            rows, boxes, protos, geometry = detect(session, frame)
            overlap = iou(boxes, reference)[:, 0]
            best = int(overlap.argmax()) if len(overlap) else None
            found = best is not None and overlap[best] >= protocol['physical_overlap_min']
            record = {'type': 'cup', 'frame': index, 'reference': reference[0].tolist(),
                      'box': boxes[best].tolist() if best is not None else None,
                      'iou': float(overlap[best]) if best is not None else 0, 'arms': {}}
            if found:
                pair, fill = crops(frame, rows[best], boxes[best], protos, geometry)
                values = score_pairs([pair], encoder, galleries)[0]
                record['mask_fill'] = fill
            classify(found, pair if found else None, values if found else None, record,
                     counts, scores, examples, output, run, index)
            sink.write(json.dumps(record) + '\n')
            score_negatives(frame, rows, boxes, protos, geometry, np.flatnonzero(overlap < 0.1),
                            f'video:{index}', sink, encoder, galleries, negatives, negative_sources)
            if index % 30 == 0:
                print(f'Processed {index + 1}/360 frames', flush=True)
        assert total == 360, total
        paths = sorted((DATA / 'd140/negatives').glob('*.jpg'))
        if not paths:
            raise RuntimeError('No negative images found')
        for path in paths:
            frame = cv2.imread(str(path))
            if frame is None:
                raise RuntimeError(f'Cannot decode {path}')
            rows, boxes, protos, geometry = detect(session, frame)
            score_negatives(frame, rows, boxes, protos, geometry, range(len(rows)),
                            f'image:{path.name}', sink, encoder, galleries, negatives,
                            negative_sources)
    result = {
        'code_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'working_tree_diff': subprocess.check_output(
            ['git', 'diff', '--', 'robot/detect.py', 'bench/crop_arms.py'], text=True),
        'source_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                          for name in ('bench/crop_arms.py', 'robot/detect.py', 'robot/things.py')},
        'model_sha256': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in (MODEL, ROOT / 'models/dinov2-small/model.onnx')},
        'machine': {'label': 'E', 'hostname': platform.node(), 'platform': platform.platform()},
        'versions': {'python': platform.python_version(), 'onnxruntime': ort.__version__,
                     'numpy': np.__version__, 'opencv': cv2.__version__},
        'command': shlex.join([sys.executable, *sys.argv]), 'frames': total,
        'limits': {'match': MATCH, 'detect_low': DETECT_LOW, 'min_side': OBJECT_MIN_SIDE,
                   'iou': protocol['physical_overlap_min'], 'negative_iou': 0.1},
        'teaching': teaching, 'negative_sources': dict(negative_sources),
        'rows': str((output / f'{run}.jsonl').relative_to(ROOT)), 'arms': {}}
    for arm in ARMS:
        n = negatives[arm]
        detected = total - counts[arm]['no_detection']
        result['arms'][arm] = {
            'causes': {c: counts[arm][c]
                       for c in ('no_detection', 'small', 'under_threshold', 'hit')},
            'hit_fraction_all': counts[arm]['hit'] / total,
            'hit_fraction_detected': counts[arm]['hit'] / detected if detected else None,
            'cup_scores': percentiles(scores[arm], (10, 50, 90)),
            'negatives_scored': len(n), 'false_matches': sum(s >= MATCH for s in n),
            'negative_max': max(n) if n else None, 'negative_scores': percentiles(n, (99,)),
            'examples': dict(examples[arm]), 'gallery_views': len(galleries[arm])}
    target = ROOT / f'bench/results/2026-10-11-crop-arms-{run}.json'
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(target)
    print(json.dumps(result['arms'], indent=2))


if __name__ == '__main__':
    _mask_selftest()
    main()

"""Object detection and tracking: YOLOE-26n with a fixed booth vocabulary (end-to-end, no NMS) on
TensorRT, and an IoU tracker that reports when a track is confirmed, moves region, or leaves.

    python -m robot.detect     self-check (the tracker; the detector too when its model exists)
"""
import ast
import ctypes
import itertools
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from robot.config import MODELS, ROOT

MODEL = MODELS / "detector/yoloe-26n-booth-384x640.onnx"  # recipe: research/detector.md
INPUT = (384, 640)  # height, width: the 16:9 camera frame letterboxed with little padding
LOW, HIGH = 0.1, 0.25  # every detection above LOW continues a track; only HIGH starts one
MATCH_IOU = 0.3
SAME = 0.7  # IoU above which two detections in one frame are one object
CONFIRM = 3  # frames a track needs before it is reported, so one-frame blips never are
MAX_MISSED = 15  # about one second at 15 fps before a lost track is dropped


@dataclass
class Detection:
    label: str
    conf: float
    box: tuple[int, int, int, int]  # x1, y1, x2, y2 in frame pixels


@dataclass
class Sighting:
    """A confirmed track that is new, moved to another region, or gone from view."""
    track: int
    label: str
    region: str
    seen: float  # when the track last matched a detection
    gone: bool = False


def region(box: tuple[int, int, int, int], width: int) -> str:
    """Left, center, or right third of the frame, by the box center."""
    return ("left", "center", "right")[min(2, int(3 * (box[0] + box[2]) / 2 / width))]


def letterbox(frame: np.ndarray) -> tuple[np.ndarray, float, int, int]:
    """The model input (1, 3, H, W) float32 RGB, the scale, and the left and top padding."""
    h, w = frame.shape[:2]
    scale = min(INPUT[0] / h, INPUT[1] / w)
    nh, nw = round(h * scale), round(w * scale)
    top, left = (INPUT[0] - nh) // 2, (INPUT[1] - nw) // 2
    img = cv2.copyMakeBorder(cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR),
                             top, INPUT[0] - nh - top, left, INPUT[1] - nw - left,
                             cv2.BORDER_CONSTANT, value=(114, 114, 114))
    blob = cv2.dnn.blobFromImage(img, 1 / 255, swapRB=True)
    return blob, scale, left, top


class _TensorRT:
    """A TensorRT engine with buffers from libcudart (JetPack 7 has no torch or cuda-python)."""

    def __init__(self, engine: Path):
        import tensorrt as trt
        self.rt = ctypes.CDLL("libcudart.so")
        self.engine = trt.Runtime(trt.Logger(trt.Logger.WARNING)).deserialize_cuda_engine(
            engine.read_bytes())
        self.ctx = self.engine.create_execution_context()
        self.stream = ctypes.c_void_p()
        self._check(self.rt.cudaStreamCreate(ctypes.byref(self.stream)))
        self.host, self.device = {}, {}
        for i in range(self.engine.num_io_tensors):
            name = self.engine.get_tensor_name(i)
            self.host[name] = np.empty(tuple(self.engine.get_tensor_shape(name)),
                                       trt.nptype(self.engine.get_tensor_dtype(name)))
            ptr = ctypes.c_void_p()
            self._check(self.rt.cudaMalloc(ctypes.byref(ptr), ctypes.c_size_t(
                self.host[name].nbytes)))
            self.device[name] = ptr
            self.ctx.set_tensor_address(name, ptr.value)
        self.input = self.engine.get_tensor_name(0)

    @staticmethod
    def _check(err: int) -> None:
        if err:
            raise RuntimeError(f"CUDA error {err}")

    def _copy(self, name: str, to_device: bool) -> None:
        host, dev = self.host[name].ctypes.data_as(ctypes.c_void_p), self.device[name]
        src, dst, kind = (host, dev, 1) if to_device else (dev, host, 2)  # cudaMemcpyKind
        self._check(self.rt.cudaMemcpyAsync(dst, src, ctypes.c_size_t(self.host[name].nbytes),
                                            kind, self.stream))

    def __call__(self, blob: np.ndarray) -> np.ndarray:
        self.host[self.input][...] = blob
        self._copy(self.input, True)
        self.ctx.execute_async_v3(self.stream.value)
        self._copy("output0", False)
        self._check(self.rt.cudaStreamSynchronize(self.stream))
        return self.host["output0"]

    def close(self) -> None:
        """Free the device buffers and the stream (an in-process restart makes a new engine)."""
        del self.ctx, self.engine
        for ptr in self.device.values():
            self._check(self.rt.cudaFree(ptr))
        self._check(self.rt.cudaStreamDestroy(self.stream))


class Detector:
    """TensorRT when an engine built by trtexec sits next to the ONNX (`<name>.fp16.engine`,
    recipe in research/detector.md); else onnxruntime on CUDA, or on the CPU on the Mac."""

    def __init__(self, model: Path = MODEL):
        import onnxruntime as ort
        engine = model.with_suffix(".fp16.engine")
        wanted = ["CUDAExecutionProvider"] * (not engine.exists()) + ["CPUExecutionProvider"]
        sess = ort.InferenceSession(str(model), providers=[
            p for p in wanted if p in ort.get_available_providers()])
        self.names = ast.literal_eval(sess.get_modelmeta().custom_metadata_map["names"])
        self.run = _TensorRT(engine) if engine.exists() else (
            lambda blob: sess.run(["output0"], {"images": blob})[0])

    def __call__(self, frame: np.ndarray) -> list[Detection]:
        blob, scale, left, top = letterbox(frame)
        out = self.run(blob)[0, :, :6]  # x1, y1, x2, y2, score, class (end-to-end head)
        out = out[out[:, 4] >= LOW]
        h, w = frame.shape[:2]
        xy = (out[:, :4] - [left, top, left, top]) / scale
        xy = np.clip(xy, 0, [w, h, w, h]).round().astype(int)
        return [Detection(self.names[int(c)], float(s), tuple(b.tolist()))
                for b, s, c in zip(xy, out[:, 4], out[:, 5], strict=True)]

    def close(self) -> None:
        if isinstance(self.run, _TensorRT):
            self.run.close()


def iou(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Pairwise IoU of boxes a (N, 4) and b (M, 4)."""
    lt = np.maximum(a[:, None, :2], b[None, :, :2])
    rb = np.minimum(a[:, None, 2:], b[None, :, 2:])
    inter = np.prod(np.clip(rb - lt, 0, None), axis=2)
    area = lambda x: np.prod(x[:, 2:] - x[:, :2], axis=1)  # noqa: E731
    return inter / (area(a)[:, None] + area(b)[None, :] - inter + 1e-9)


@dataclass
class _Track:
    id: int
    det: Detection
    region: str
    seen: float
    hits: int = 1
    missed: int = 0
    reported: str | None = None  # the region when last reported


def distinct(dets: list[Detection]) -> list[Detection]:
    """Class-agnostic NMS: the best of overlapping synonyms ("teddy bear" and "plush toy" on
    one bear), so one object never starts two tracks."""
    kept: list[Detection] = []
    for d in sorted(dets, key=lambda d: -d.conf):
        if not kept or iou(np.array([d.box]), np.array([k.box for k in kept])).max() < SAME:
            kept.append(d)
    return kept


class Tracker:
    """ByteTrack's two-stage matching without motion prediction (ponytail: objects on a booth
    table barely move; add a Kalman filter if fast motion switches IDs). Greedy by IoU, class
    agnostic, so a label that flickers between synonyms keeps its track."""

    def __init__(self):
        self.tracks: list[_Track] = []
        self.ids = itertools.count(1)

    @staticmethod
    def _match(tracks: list[_Track], dets: list[Detection]) -> list[tuple[_Track, Detection]]:
        if not tracks or not dets:
            return []
        m = iou(np.array([t.det.box for t in tracks]), np.array([d.box for d in dets]))
        rows, cols = np.nonzero(m >= MATCH_IOU)
        pairs, used_t, used_d = [], set(), set()
        for k in np.argsort(-m[rows, cols], kind="stable"):  # best overlap first
            i, j = int(rows[k]), int(cols[k])
            if i not in used_t and j not in used_d:
                used_t.add(i)
                used_d.add(j)
                pairs.append((tracks[i], dets[j]))
        return pairs

    def update(self, dets: list[Detection], width: int, now: float) -> list[Sighting]:
        """Feed one frame's detections at time `now`; returns the sightings to remember: a
        track confirmed, moved to another region, or gone (unmatched for MAX_MISSED frames)."""
        dets = distinct(dets)
        high = [d for d in dets if d.conf >= HIGH]
        first = self._match(self.tracks, high)
        taken = {id(x) for pair in first for x in pair}
        rest = [t for t in self.tracks if id(t) not in taken]
        pairs = first + self._match(rest, [d for d in dets if d.conf < HIGH])
        for t in self.tracks:
            t.missed += 1
        for t, d in pairs:
            t.det, t.region, t.seen, t.hits, t.missed = d, region(d.box, width), now, t.hits + 1, 0
        gone = [Sighting(t.id, t.det.label, t.region, t.seen, gone=True) for t in self.tracks
                if t.missed > MAX_MISSED and t.reported]
        self.tracks = [t for t in self.tracks if t.missed <= MAX_MISSED] + [
            _Track(next(self.ids), d, region(d.box, width), now) for d in high
            if id(d) not in taken]
        return gone + [self._report(t) for t in self.tracks
                       if t.missed == 0 and t.hits >= CONFIRM and t.reported != t.region]

    def in_view(self) -> set[int]:
        """Ids of the tracks the last frame matched."""
        return {t.id for t in self.tracks if t.missed == 0}

    @staticmethod
    def _report(t: _Track) -> Sighting:
        t.reported = t.region
        return Sighting(t.id, t.det.label, t.region, t.seen)


def _selftest() -> None:
    assert region((0, 0, 100, 100), 1280) == "left"
    assert region((600, 0, 700, 100), 1280) == "center"
    assert region((1200, 0, 1280, 100), 1280) == "right"
    t, w = Tracker(), 1280
    cup = Detection("cup", 0.8, (100, 100, 200, 200))
    mug = Detection("mug", 0.7, (102, 100, 202, 200))  # a synonym box on the same cup
    assert t.update([cup, mug], w, 1) == [] and t.update([cup], w, 2) == []  # not confirmed
    assert len(t.tracks) == 1, "overlapping synonyms are one object"
    [s] = t.update([cup], w, 3)
    assert (s.track, s.label, s.region, s.seen, s.gone) == (1, "cup", "left", 3, False)
    assert t.update([cup], w, 4) == []  # unchanged: reported once
    faint = Detection("mug", 0.15, (110, 100, 210, 200))  # low score: continues the track
    assert t.update([faint], w, 5) == [], "a label flicker is not a new sighting"
    for x in range(150, 400, 50):  # the cup slides into the center third, frame by frame
        assert t.update([Detection("cup", 0.8, (x, 100, x + 100, 200))], w, 6) == []
    [s] = t.update([Detection("cup", 0.8, (400, 100, 500, 200))], w, 7)
    assert (s.track, s.region, s.gone) == (1, "center", False) and len(t.tracks) == 1, s
    assert t.in_view() == {1}
    for k in range(MAX_MISSED):
        assert t.update([], w, 8 + k) == [] and t.in_view() == set()
    [s] = t.update([], w, 99)
    assert (s.track, s.region, s.seen, s.gone) == (1, "center", 7, True), "gone, last seen at 7"
    assert t.tracks == []
    for _ in range(CONFIRM):
        assert t.update([Detection("x", 0.2, (0, 0, 9, 9))], w, 100) == []
    assert t.tracks == [], "a low-score detection never starts a track"
    for _ in range(CONFIRM - 1):
        t.update([cup], w, 101)
    for _ in range(MAX_MISSED + 1):
        assert t.update([], w, 102) == [], "an unconfirmed track leaves without a sighting"
    blob, scale, left, top = letterbox(np.zeros((720, 1280, 3), np.uint8))
    assert blob.shape == (1, 3, *INPUT) and (scale, left, top) == (0.5, 0, 12)
    if MODEL.exists():  # the Mac has no model unless it was exported there
        detect = Detector()
        dets = detect(cv2.imread(str(ROOT / "eval/dev/live/closet-stopsign-center.jpg")))
        assert any(d.label == "stop sign" and d.conf > 0.5 for d in dets), dets
        backend = "tensorrt" if isinstance(detect.run, _TensorRT) else "onnxruntime"
        print(f"detector ok ({backend}): "
              f"{[(d.label, round(d.conf, 2)) for d in dets[:5]]}")
    print("selftest ok")


if __name__ == "__main__":
    _selftest()

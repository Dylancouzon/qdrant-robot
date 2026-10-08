"""Object detection and tracking: YOLOE-26n with a fixed booth vocabulary (end-to-end, no NMS) on
TensorRT, and an IoU tracker that reports new and changed tracks with label, region, and crop.

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
CONFIRM = 3  # frames a track needs before it is reported, so one-frame blips never are
MAX_MISSED = 15  # about one second at 15 fps before a lost track is dropped


@dataclass
class Detection:
    label: str
    conf: float
    box: tuple[int, int, int, int]  # x1, y1, x2, y2 in frame pixels


@dataclass
class Sighting:
    """A confirmed track that is new, or whose label or region changed."""
    track: int
    label: str
    conf: float
    box: tuple[int, int, int, int]
    region: str
    crop: np.ndarray


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
    hits: int = 1
    missed: int = 0
    reported: tuple[str, str] | None = None  # (label, region) when last reported


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

    def update(self, dets: list[Detection], frame: np.ndarray) -> list[Sighting]:
        """Feed one frame's detections; returns the sightings to remember."""
        width = frame.shape[1]
        high = [d for d in dets if d.conf >= HIGH]
        first = self._match(self.tracks, high)
        taken = {id(x) for pair in first for x in pair}
        rest = [t for t in self.tracks if id(t) not in taken]
        pairs = first + self._match(rest, [d for d in dets if d.conf < HIGH])
        for t in self.tracks:
            t.missed += 1
        for t, d in pairs:
            t.det, t.region, t.hits, t.missed = d, region(d.box, width), t.hits + 1, 0
        self.tracks = [t for t in self.tracks if t.missed <= MAX_MISSED] + [
            _Track(next(self.ids), d, region(d.box, width)) for d in high
            if id(d) not in taken]
        return [self._report(t, frame) for t in self.tracks
                if t.missed == 0 and t.hits >= CONFIRM and t.reported != (t.det.label, t.region)]

    @staticmethod
    def _report(t: _Track, frame: np.ndarray) -> Sighting:
        t.reported = (t.det.label, t.region)
        x1, y1, x2, y2 = t.det.box
        return Sighting(t.id, t.det.label, t.det.conf, t.det.box, t.region,
                        frame[y1:y2, x1:x2].copy())


def _selftest() -> None:
    frame = np.zeros((720, 1280, 3), np.uint8)
    assert region((0, 0, 100, 100), 1280) == "left"
    assert region((600, 0, 700, 100), 1280) == "center"
    assert region((1200, 0, 1280, 100), 1280) == "right"
    cup = Detection("cup", 0.8, (100, 100, 200, 200))
    t = Tracker()
    assert t.update([cup], frame) == [] and t.update([cup], frame) == []  # not yet confirmed
    [s] = t.update([cup], frame)
    assert (s.track, s.label, s.region, s.crop.shape) == (1, "cup", "left", (100, 100, 3))
    assert t.update([cup], frame) == []  # unchanged: reported once
    faint = Detection("mug", 0.15, (110, 100, 210, 200))  # low score, synonym: same track
    [s] = t.update([faint], frame)
    assert (s.track, s.label) == (1, "mug")
    moved = Detection("mug", 0.9, (500, 100, 610, 200))  # no overlap: a new track
    for _ in range(CONFIRM - 1):
        assert t.update([moved], frame) == []
    [s] = t.update([moved], frame)
    assert (s.track, s.region) == (2, "center")
    for _ in range(MAX_MISSED + 1):
        t.update([], frame)
    assert t.tracks == [], "lost tracks are dropped"
    for _ in range(CONFIRM):
        assert t.update([Detection("x", 0.2, (0, 0, 9, 9))], frame) == []
    assert t.tracks == [], "a low-score detection never starts a track"
    blob, scale, left, top = letterbox(frame)
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

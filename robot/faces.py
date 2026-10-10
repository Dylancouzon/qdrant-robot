"""Face vectors: YuNet finds faces and five landmarks, a similarity warp puts each face on the
ArcFace 112x112 template, and insightface w600k_r50 turns it into a unit vector (cosine).

    python -m robot.faces   self-check on public LFW photos (needs models/faces and eval/faces/lfw)
"""
import cv2
import numpy as np
import onnxruntime as ort

from robot.config import MODELS, ROOT

DETECTOR = MODELS / "faces/yunet_2023mar.onnx"
EMBEDDER = MODELS / "faces/w600k_r50.onnx"  # chosen in bench/faces_bakeoff.py
MIN_SCORE = 0.6  # YuNet's own default
# Landmarks (eyes, nose tip, mouth corners) of the 112x112 ArcFace template the embedders
# were trained on.
TEMPLATE = np.array([[38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366],
                     [41.5493, 92.3655], [70.7299, 92.2041]], np.float32)


def align(bgr: np.ndarray, landmarks: np.ndarray) -> np.ndarray:
    """112x112 BGR crop with the five `landmarks` (5x2, image pixels) moved onto TEMPLATE."""
    m, _ = cv2.estimateAffinePartial2D(landmarks.astype(np.float32), TEMPLATE, method=cv2.LMEDS)
    return cv2.warpAffine(bgr, m, (112, 112), borderMode=cv2.BORDER_REPLICATE)


class Faces:
    """`mean` and `scale` normalize RGB pixels as the embedder was trained: (x - mean) * scale."""

    def __init__(self, embedder=EMBEDDER, mean: float = 127.5, scale: float = 1 / 127.5):
        self.detector = cv2.FaceDetectorYN.create(str(DETECTOR), "", (320, 320), MIN_SCORE)
        self.session = ort.InferenceSession(str(embedder), providers=[
            p for p in ("CUDAExecutionProvider", "CPUExecutionProvider")
            if p in ort.get_available_providers()])
        self.input = self.session.get_inputs()[0].name
        self.mean, self.scale = mean, scale

    def detect(self, bgr: np.ndarray) -> np.ndarray:
        """One row per face, largest first: x, y, w, h, five landmarks as (x, y), score."""
        scale = min(1.0, 640 / bgr.shape[1])
        image = cv2.resize(bgr, None, fx=scale, fy=scale) if scale < 1 else bgr
        self.detector.setInputSize((image.shape[1], image.shape[0]))
        faces = self.detector.detect(image)[1]
        if faces is None:
            return np.zeros((0, 15), np.float32)
        faces[:, :14] /= scale  # source bounds and landmarks; alignment uses full-resolution pixels
        return faces[np.argsort(-faces[:, 2] * faces[:, 3])]

    def embed(self, crops: list[np.ndarray]) -> np.ndarray:
        """Unit vectors, one row per aligned 112x112 BGR crop."""
        x = (np.stack(crops)[..., ::-1].astype(np.float32) - self.mean) * self.scale
        v = self.session.run(None, {self.input: x.transpose(0, 3, 1, 2)})[0]
        return v / np.linalg.norm(v, axis=1, keepdims=True)

    def vectors(self, bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Detections (as `detect`) and one unit vector per face."""
        faces = self.detect(bgr)
        if not len(faces):
            return faces, np.zeros((0, 512), np.float32)
        return faces, self.embed([align(bgr, f[4:14].reshape(5, 2)) for f in faces])


def _selftest() -> None:
    """Public LFW photos (no team member): two photos of one person score well above a third
    person, and every photo has one confident face."""
    lfw = ROOT / "eval/faces/lfw/lfw"
    faces = Faces()
    found = [faces.vectors(cv2.imread(str(lfw / f"{n}/{n}_{k:04d}.jpg")))
             for n, k in [("Colin_Powell", 1), ("Colin_Powell", 2), ("Tony_Blair", 1)]]
    assert all(f[0, 14] > 0.9 for f, _ in found), found
    v = np.stack([x[0] for _, x in found])  # LFW centers the subject; the largest face is theirs
    same, other = float(v[0] @ v[1]), float(v[0] @ v[2])
    assert same > 0.4 > other, (same, other)
    print(f"selftest ok (same person {same:.3f}, other person {other:.3f})")


if __name__ == "__main__":
    _selftest()

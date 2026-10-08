"""Text vectors with bge-small-en-v1.5 (384-d, CLS pooling, unit length), on the GPU when present.

The same model and preprocessing embed the knowledge shard on the Mac and queries on the robot.
"""
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

from robot.config import MODELS

DIM = 384
MAX_TOKENS = 128  # questions and short facts; longer text is truncated


class TextEmbedder:
    def __init__(self):
        d = MODELS / "bge-small"
        self.tok = Tokenizer.from_file(str(d / "tokenizer.json"))
        self.tok.enable_truncation(MAX_TOKENS)
        self.tok.enable_padding()
        providers = [p for p in ("CUDAExecutionProvider", "CPUExecutionProvider")
                     if p in ort.get_available_providers()]
        self.sess = ort.InferenceSession(str(d / "model.onnx"), providers=providers)

    def __call__(self, texts: list[str]) -> np.ndarray:
        enc = self.tok.encode_batch(texts)
        ids = np.array([e.ids for e in enc], np.int64)
        mask = np.array([e.attention_mask for e in enc], np.int64)
        hidden = self.sess.run(None, {"input_ids": ids, "attention_mask": mask,
                                      "token_type_ids": np.zeros_like(ids)})[0]
        cls = hidden[:, 0]
        return cls / np.linalg.norm(cls, axis=1, keepdims=True)


if __name__ == "__main__":
    e = TextEmbedder()
    v = e(["What is Qdrant Edge?", "Tell me about Qdrant Edge.", "What color is the sky?"])
    assert v.shape == (3, DIM) and np.allclose(np.linalg.norm(v, axis=1), 1, atol=1e-4)
    assert v[0] @ v[1] > v[0] @ v[2] + 0.1, "paraphrases must be closer than unrelated text"
    print("selftest ok", round(float(v[0] @ v[1]), 3), round(float(v[0] @ v[2]), 3))

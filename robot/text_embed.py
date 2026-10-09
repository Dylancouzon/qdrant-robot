"""Text vectors with bge-small-en-v1.5 (384-d, CLS pooling, unit length), on the GPU when present.

The same model and preprocessing embed the knowledge shard on the Mac and queries on the robot.
"""
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

from robot.config import MODELS

DIM = 384
MAX_TOKENS = 128  # includes special tokens


class TextEmbedder:
    def __init__(self):
        d = MODELS / "bge-small"
        self.tok = Tokenizer.from_file(str(d / "tokenizer.json"))
        self.tok.enable_truncation(MAX_TOKENS)
        self.tok.enable_padding()
        cuda = "CUDAExecutionProvider" in ort.get_available_providers()
        providers = ([("CUDAExecutionProvider", {"arena_extend_strategy": "kSameAsRequested"})]
                     if cuda else ["CPUExecutionProvider"])
        self.sess = ort.InferenceSession(str(d / "model.onnx"), providers=providers)

    def units(self, text: str) -> list[dict]:
        """Lossless character spans whose independently encoded text fits BGE."""
        # Clone tokenizer settings, not the model/session. Offset encoding must not truncate.
        tok = Tokenizer.from_str(self.tok.to_str())
        tok.no_truncation()
        tok.no_padding()
        offsets = tok.encode(text, add_special_tokens=False).offsets
        if not offsets:
            return []
        units, start, cursor = [], 0, 0
        while cursor < len(offsets):
            stop = min(cursor + MAX_TOKENS - 2, len(offsets))
            end = len(text) if stop == len(offsets) else offsets[stop][0]
            while len(tok.encode(text[start:end]).ids) > MAX_TOKENS:
                stop -= 1
                if stop <= cursor:
                    raise ValueError("A source token cannot fit the BGE input limit")
                end = offsets[stop][0]
            units.append({"start": start, "end": end, "text": text[start:end],
                          "tokens": len(tok.encode(text[start:end]).ids)})
            start, cursor = end, stop
        return units

    def embed_units(self, text: str) -> tuple[list[dict], np.ndarray]:
        """Embed all units in bounded batches with the existing inference session."""
        units = self.units(text)
        vectors = [self([u["text"] for u in units[i:i + 8]])
                   for i in range(0, len(units), 8)]
        return units, np.concatenate(vectors) if vectors else np.empty((0, DIM), np.float32)

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

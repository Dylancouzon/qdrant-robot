"""Lossless BGE unit splitting without another inference session."""

from tokenizers import Tokenizer, models, pre_tokenizers, processors

from robot.text_embed import MAX_TOKENS, TextEmbedder


def test_units_preserve_overflow_and_characters():
    embedder = TextEmbedder.__new__(TextEmbedder)
    tok = Tokenizer(models.WordLevel({"[UNK]": 0, "[CLS]": 1, "[SEP]": 2}, unk_token="[UNK]"))
    tok.pre_tokenizer = pre_tokenizers.Whitespace()
    tok.post_processor = processors.TemplateProcessing(
        single="[CLS] $A [SEP]", special_tokens=[("[CLS]", 1), ("[SEP]", 2)]
    )
    tok.enable_truncation(MAX_TOKENS)
    tok.enable_padding()
    embedder.tok = tok
    text = "  " + "café umbrella. " * 180 + "最後  "
    units = embedder.units(text)
    assert len(units) > 1 and "".join(u["text"] for u in units) == text
    assert all(
        u["tokens"] <= MAX_TOKENS and text[u["start"] : u["end"]] == u["text"] for u in units
    )
    assert embedder.units("") == []
    assert embedder.units("   ") == []

#!/usr/bin/env python3
"""Brain and prompt bake-off for evidence use, on the Mac: replays the prompts the robot built
in logged replays (same history, evidence lines, and fixture frame) through one brain under
several prompt shapes, then judges each shape with eval/judge.py (three votes, cached).

    .venv/bin/python -m bench.brain_bakeoff qwen3vl-2b [A,B,C,...]   (Homebrew llama-server)

Code answers (identity, named objects, verbatim facts) stay as logged: v1 keeps them in code.
"""
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from robot import brain
from robot.memory import about_now

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "bench/results"
SETS = {  # name: (cases, logged replay whose prompts are replayed)
    "m2": ("eval/dev/m2.jsonl", "2026-10-08-replay-1791512728.jsonl"),  # retrieval into the brain
    "visitor": ("eval/dev/visitor.jsonl", "2026-10-08-replay-1791513005.jsonl"),
    # Spent one-time probes, logged before v1 (memories as code-era lines): relative only.
    "m2b": ("eval/probes/m2b.jsonl", "2026-10-08-replay-1791479641.jsonl"),
    "m2c": ("eval/probes/m2c.jsonl", "2026-10-08-replay-1791484406.jsonl"),
}
EVIDENCE = ("Memories", "The visitor told you")  # Facts are knowledge, not memories
PAST_NOTE = brain.PAST.strip()
CITE = re.compile(r"\s*\[\d+\]")
DEMOS = (  # H: counterfactual demonstrations, where only the memory gives the answer
    "\nExamples of answering from memory, even when it sounds unusual:\n"
    "Memories: 2 minutes ago: a purple banana on the table. Visitor: What color was the "
    "banana? Edgy: It was purple, two minutes ago.\n"
    "The visitor told you: 1 minute ago: I live on the Moon. Visitor: Where do I live? "
    "Edgy: You told me you live on the Moon.\n"
    "Memories: 30 seconds ago: penguin in the center. Visitor: What was in front of you? "
    "Edgy: A penguin, 30 seconds ago.")


def parse(text: str) -> tuple[list[tuple[str, list[str]]], str, str]:
    """A logged user text as (blocks of (title, lines), notes, question): the inverse of
    brain.messages."""
    *blocks, tail = text.split("\n\n")
    notes, question = tail.rsplit("Visitor: ", 1)
    return [(b.split(":\n- ", 1)[0], b.split(":\n- ", 1)[1].split("\n- ")) for b in blocks], \
        notes, question


def render(blocks: list[tuple[str, list[str]]]) -> str:
    return "".join(f"{t}:\n- " + "\n- ".join(lines) + "\n\n" for t, lines in blocks)


def short(line: str) -> str:
    """A caption line cut to its main object (variant E)."""
    return re.split(r"\.?\s*\n?Around it:", line)[0]


def shape(variant: str, system: str, text: str, image: dict | None) -> tuple[str, dict, str]:
    """The system prompt, the final user message, and an assistant prefill for a variant."""
    blocks, notes, question = parse(text)
    ev = [(t, ls) for t, ls in blocks if t in EVIDENCE]
    other = [(t, ls) for t, ls in blocks if t not in EVIDENCE]
    img = [image] if image else []
    tail = f"{notes}Visitor: {question}"
    prefill = ""
    lead = "Answer from these memories; if one answers the question, use it.\n\n"
    if variant == "B" and ev:  # evidence before the image: the robot could not prefill it
        content = [{"type": "text", "text": lead + render(blocks)}, *img,
                   {"type": "text", "text": tail}]
    elif variant == "I" and ev:  # B's words after the image, so the prefilled prefix holds
        content = [*img, {"type": "text", "text": lead + text}]
    elif variant == "D" and ev:
        lines = [f"[{k}] {t == EVIDENCE[1] and 'the visitor told you ' or ''}"
                 f"{re.sub(r'^\d+\. ', '', line)}"
                 for k, (t, line) in enumerate(((t, x) for t, ls in ev for x in ls), 1)]
        content = [*img, {"type": "text", "text": render(other) + "Numbered memories:\n"
                          + "\n".join(lines) + "\nIf a numbered memory answers the question, "
                          "answer from it and end with its number, like [2].\n\n" + tail}]
    elif variant == "E" and ev:
        cut = [(t, [short(x) for x in (ls[-2:] if t == EVIDENCE[0] else ls[:1])]) for t, ls in ev]
        content = [*img, {"type": "text", "text": render(cut + other) + tail}]
    elif variant == "F" and ev:
        said = [re.sub(r"^\d+\. ", "", short(x)) for t, ls in ev for x in ls
                if t == EVIDENCE[0]] + [f"the visitor told you {x}" for t, ls in ev
                                        if t == EVIDENCE[1] for x in ls]
        content = [*img, {"type": "text", "text": render(other) + "Your memory says: "
                          + "; ".join(said) + ". Answer from your memory.\n\n" + tail}]
    elif variant == "G" and ev:
        text = notes + render(other + ev) + f"Visitor: {question}"
        content = [*img, {"type": "text", "text": text}]
    else:  # A, H, and every variant without memory lines: the robot's own shape
        content = [*img, {"type": "text", "text": text}]
        prefill = "From my memory," if variant == "C" and ev else ""
    return system + (DEMOS if variant == "H" else ""), {"role": "user", "content": content}, prefill


def frames(cases: Path) -> dict[str, Path]:
    """Each spoken step's fixture frame: the last one shown before it."""
    out, shown = {}, None
    for session in map(json.loads, cases.read_text().splitlines()):
        for st in session["steps"]:
            shown = cases.parent / st["show"] if "show" in st else shown
            if "say" in st:
                out[st["id"]] = shown
    return out


def serve(model: str) -> subprocess.Popen:
    args = ["llama-server", *brain.server_args(model)[1:]]
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(600):
        try:
            urllib.request.urlopen(f"{brain.URL}/health", timeout=1).read()
            return proc
        except OSError:
            time.sleep(0.5)
    raise RuntimeError("llama-server did not become healthy")


def decode_speed() -> float:
    body = {"prompt": "Tell a long story about a robot at a conference.", "n_predict": 128,
            "ignore_eos": True, "temperature": 0}
    req = urllib.request.Request(f"{brain.URL}/completion", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)["timings"]["predicted_per_second"]


def replay(model: str, variants: list[str], run: str) -> list[Path]:
    import cv2
    b = brain.Brain.__new__(brain.Brain)  # the robot's answer path, on a server started here
    proc = serve(model)
    try:
        speed = decode_speed()
        system = json.loads((OUT / SETS["m2"][1]).read_text().splitlines()[-1])["system"]
        written = []
        for name, (cases, logged) in SETS.items():
            pics = frames(ROOT / cases)
            steps = {st["id"]: st for line in (ROOT / cases).read_text().splitlines()
                     for st in json.loads(line)["steps"] if "say" in st}
            rows = [r for r in map(json.loads, (OUT / logged).read_text().splitlines())
                    if "id" in r]
            out = []
            for v in variants:
                for r in rows:
                    text = r["prompt"][-1]["content"][-1]["text"]
                    code = r["verbatim"] and name in ("m2", "visitor")  # v1 keeps these in code
                    ev = any(t in EVIDENCE for t, _ in parse(text)[0])
                    answer, raw, tokens, ms = r["answer"], None, None, None
                    if not code:
                        past = PAST_NOTE in text
                        sees = about_now(r["heard"]) or (r["kind"] == "sight" and not past)
                        image = brain.jpeg(cv2.imread(str(pics[r["id"]]))) if sees else None
                        sys_, user, prefill = shape(v, system, text, image)
                        t0 = time.time()
                        msgs = [{"role": "system", "content": sys_}, *r["prompt"][:-1], user]
                        raw = prefill + "".join(b.answer(msgs, prior=prefill))
                        ms = round(1000 * (time.time() - t0))
                        tokens = b.tokens(raw) if raw else 0
                        answer = CITE.sub("", raw).strip()
                    out.append({"id": f"{v}/{r['id']}", "variant": v, "step": r["id"],
                                "heard": r["heard"], "answer": answer,
                                "raw": raw, "code": code,
                                "evidence_lines": ev, "evidence_ok": r["evidence_ok"],
                                "needs_evidence": bool(steps[r["id"]].get("evidence")),
                                "expect_any": steps[r["id"]]["expect_any"],
                                "evidence_text": text if ev else "", "tokens": tokens, "ms": ms})
                print(f"{model} {name} {v}: {sum(not x['code'] for x in out[-len(rows):])} "
                      "brain answers", flush=True)
            path = OUT / f"2026-10-08-bakeoff-{model}-{name}-{run}.jsonl"
            weights, mmproj, _ = brain.MODELS[model]
            summary = {"summary": "brain_bakeoff", "model": model, "set": name, "cases": cases,
                       "replayed": logged, "variants": variants, "machine": "mac-m5pro",
                       "llama_cpp": "homebrew 0.6.0 build 11429 d81235049 (Metal)",
                       "decode_tok_s": round(speed, 1), "max_tokens": brain.MAX_TOKENS,
                       "image_max_tokens": 256, "context": 2048,
                       "gguf_mb": round(sum((brain.GGUF / f).stat().st_size
                                            for f in (weights, mmproj)) / 2**20),
                       "revision": subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                                  capture_output=True, text=True).stdout.strip(),
                       "command": " ".join(sys.argv)}
            path.write_text("".join(json.dumps(x) + "\n" for x in out + [summary]))
            written.append(path)
        return written
    finally:
        proc.terminate()
        proc.wait(timeout=30)


def judge(path: Path, chunk: int = 80) -> None:
    """eval/judge.py on `path`, with the rubrics re-keyed to the variant-prefixed ids. Growing
    prefixes of the file are judged in turn, so each judge call gets at most `chunk` answers
    that are not in its cache yet."""
    lines = [x for x in path.read_text().splitlines() if '"id"' in x]
    rows = list(map(json.loads, lines))
    cases = ROOT / json.loads(path.read_text().splitlines()[-1])["cases"]
    rubric = {st["id"]: st["rubric"] for line in cases.read_text().splitlines()
              for st in json.loads(line)["steps"] if "say" in st}
    with tempfile.TemporaryDirectory() as tmp:
        steps = Path(tmp) / "cases.jsonl"
        steps.write_text(json.dumps({"steps": [{"id": r["id"], "say": "", "rubric":
                                                rubric[r["step"]]} for r in rows]}) + "\n")
        for end in range(chunk, len(rows) + chunk, chunk):
            part = path if end >= len(rows) else Path(tmp) / "part.jsonl"
            if part != path:
                part.write_text("\n".join(lines[:end]) + "\n")
            subprocess.run([sys.executable, str(ROOT / "eval/judge.py"), str(part), str(steps)],
                           stdout=subprocess.DEVNULL)


def table(paths: list[Path]) -> None:
    """One line per brain, set, and variant from judged bake-off files: judged correct (code
    answers included), brain answers correct, answerable-from-evidence correct, evidence use
    (an expected word that is in the evidence is in the answer), wrong-memory failures
    (memory lines present but not needed, judged FAIL), plain chat (no memory lines) correct,
    and mean output tokens."""
    print("model set variant | all | brain | evidence | use | wrong-mem | plain | tokens | "
          "tok/s MB")
    for path in paths:
        rows = [r for r in map(json.loads, path.read_text().splitlines()) if "id" in r]
        meta = json.loads(path.read_text().splitlines()[-1])
        verdict = {j["id"]: j["pass"] for j in map(json.loads, path.with_suffix(
            ".judged.jsonl").read_text().splitlines())}
        for v in meta["variants"]:
            vs = [r for r in rows if r["variant"] == v]
            br = [r for r in vs if not r["code"]]
            ans = [r for r in br if r["needs_evidence"] and r["evidence_ok"]]
            words = [(r, [k for k in r["expect_any"] if k in r["evidence_text"].lower()])
                     for r in ans]
            use = [any(k in r["answer"].lower() for k in ks) for r, ks in words if ks]
            wrong = [r for r in br if r["evidence_lines"] and not r["needs_evidence"]]
            plain = [r for r in br if not r["evidence_lines"]]
            def ok(rs: list[dict], verdict: dict = verdict) -> str:
                return f"{sum(verdict[r['id']] for r in rs)}/{len(rs)}"
            print(f"{meta['model']} {meta['set']} {v} | {ok(vs)} | {ok(br)} | {ok(ans)} | "
                  f"{sum(use)}/{len(use)} | {sum(not verdict[r['id']] for r in wrong)}/"
                  f"{len(wrong)} | {ok(plain)} | "
                  f"{sum(r['tokens'] for r in br) / max(len(br), 1):.1f} | "
                  f"{meta['decode_tok_s']} {meta['gguf_mb']}")


if __name__ == "__main__":
    text = ("Memories:\n- 1. 5 seconds ago: Main object: clock\nAround it: chair.\n- 2. 4 "
            "seconds ago: clock in the center\n\nThe visitor told you:\n- 9 seconds ago: I'm Ana"
            "\n\n" + brain.PAST + "Visitor: What was it?")
    blocks, notes, q = parse(text)
    assert [t for t, _ in blocks] == list(EVIDENCE) and notes == brain.PAST and q == "What was it?"
    assert render(blocks) + notes + "Visitor: " + q == text, "parse inverts render"
    assert short(blocks[0][1][0]) == "1. 5 seconds ago: Main object: clock"
    d = shape("D", "S", text, None)[1]["content"][-1]["text"]
    assert "[1] 5 seconds ago: Main object: clock" in d and "[3] the visitor told you 9" in d
    assert shape("C", "S", text, None)[2] == "From my memory,"
    assert shape("C", "S", "Visitor: Hi?", None)[2] == "", "no memory lines: no prefill"
    assert shape("H", "S", text, None)[0].startswith("S\nExamples")
    img = {"type": "image_url"}
    assert shape("I", "S", text, img)[1]["content"][0] == img, "I keeps the image first"
    assert shape("B", "S", text, img)[1]["content"][1] == img
    print("selftest ok")
    if sys.argv[1:2] == ["judge"]:
        for p in sys.argv[2:]:
            judge(Path(p))
    elif sys.argv[1:2] == ["table"]:
        table([Path(p) for p in sys.argv[2:]])
    elif sys.argv[1:]:
        variants = list(sys.argv[2] if len(sys.argv) > 2 else "ABCDEFGH")
        print(*replay(sys.argv[1], variants, str(int(time.time()))), sep="\n")

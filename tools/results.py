#!/usr/bin/env python3
"""Read replay and brain bake-off evidence offline, one line per run and variant.

    python3 tools/results.py --cases eval/dev/m2.jsonl --limit 6
    python3 tools/results.py bench/results/<run>.jsonl [--json]

Judged answers, keyword checks, and retrieval checks stay separate. No models are imported.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def by_id(rows: list[dict], source: Path) -> dict:
    out = {r["id"]: r for r in rows}
    if len(out) != len(rows):
        raise ValueError(f"duplicate IDs in {source}")
    return out


def matched_judgments(path: Path, rows: list[dict]) -> dict:
    """Accept only verdicts for these exact transcripts and answers, never stale sidecars."""
    raw = by_id(rows, path)
    sidecar = path.with_suffix(".judged.jsonl")
    judged = by_id(records(sidecar), sidecar) if sidecar.exists() else {}
    for ident, j in judged.items():
        r = raw.get(ident)
        if (r is None or type(j.get("pass")) is not bool
                or (j.get("visitor"), j.get("robot")) != (r.get("heard"), r.get("answer"))):
            raise ValueError(f"unmatched judgment {ident} in {sidecar}")
    return judged


def fraction(rows: list[dict], key: str) -> str:
    measured = [r[key] for r in rows if type(r.get(key)) is bool]
    return f"{sum(measured)}/{len(measured)}" if measured else "unmeasured"


def mode(meta: dict) -> str:
    if meta.get("summary") == "brain_bakeoff":
        return "logged-prompts"
    if meta.get("oracle") is True:
        return "oracle"
    return {"audio": "synthetic", "audio-real": "recorded-voice"}.get(
        meta.get("audio"), "unknown")


def report(path: Path) -> list[dict]:
    data = records(path)
    rows = [r for r in data if "id" in r]
    summaries = [r for r in data if "summary" in r]
    if len(summaries) > 1:
        raise ValueError(f"multiple summaries in {path}")
    meta = summaries[0] if summaries else {}
    if meta.get("summary", "replay") not in ("replay", "brain_bakeoff"):
        raise ValueError(f"unsupported result format in {path}")
    if any(not {"id", "heard", "answer"} <= r.keys() for r in rows):
        raise ValueError(f"unsupported answer rows in {path}")
    if not meta and (not rows or len(rows) != len(data)):
        raise ValueError(f"unsupported or empty result in {path}")
    complete = (bool(meta) and data[-1] == meta and meta.get("n", len(rows)) == len(rows)
                and meta.get("n_expected", len(rows)) == len(rows))
    judged = matched_judgments(path, rows)
    variants = list(dict.fromkeys(r.get("variant", "-") for r in rows)) or ["-"]
    if "variants" in meta and set(variants) != set(meta["variants"]):
        complete = False
    out = []
    for variant in variants:
        rs = [r for r in rows if r.get("variant", "-") == variant]
        js = [judged[r["id"]] for r in rs if r["id"] in judged]
        out.append({"file": str(path), "kind": meta.get("summary", "unknown"),
                    "machine": meta.get("machine", "unknown"),
                    "release": meta.get("release") or "unknown",
                    "revision": meta.get("revision", "unknown"),
                    "model": meta.get("model", "unknown"), "mode": mode(meta),
                    "cases": meta.get("cases", "unknown"), "variant": variant,
                    "replayed": meta.get("replayed"), "llama_cpp": meta.get("llama_cpp"),
                    "run": "complete" if complete else "incomplete", "n": len(rs),
                    "expected_n": meta.get("n_expected"),
                    "judging": ("unjudged" if not js else
                                "complete" if len(js) == len(rs) else "partial"),
                    "judged": fraction(js, "pass"), "judged_n": len(js),
                    "unjudged_n": len(rs) - len(js), "keyword": fraction(rs, "ok"),
                    "retrieval": fraction(rs, "evidence_ok"),
                    "first_audio_p50_s": meta.get("first_audio_p50_s"),
                    "tegrastats": meta.get("tegrastats"),
                    "context": meta.get("context"), "max_tokens": meta.get("max_tokens")})
    return out


def compact(r: dict) -> str:
    audio = r["first_audio_p50_s"]
    latency = f" synthesized-p50={audio:.3f}s" if audio is not None else ""
    return (f"{Path(r['file']).name} | {r['machine']} release={r['release']} "
            f"rev={r['revision']} {r['model']} {r['mode']} {r['cases']} "
            f"variant={r['variant']} | {r['run']} n={r['n']} "
            f"judged={r['judged']} ({r['judging']}, missing={r['unjudged_n']}) "
            f"keyword={r['keyword']} retrieval={r['retrieval']}{latency}")


def raw_paths(inputs: list[Path]) -> list[Path]:
    paths = set()
    for p in inputs:
        if p.is_dir():
            paths.update(p.glob("*-replay-[0-9]*.jsonl"))
            paths.update(p.glob("*bakeoff*.jsonl"))
        else:
            paths.add(p)
    return sorted((p for p in paths if ".judged." not in p.name), key=run_order)


def run_order(path: Path) -> tuple[int, str]:
    """Replay and bake-off filenames end in the run's Unix timestamp, not its model name."""
    stamp = re.search(r"-(\d{10})$", path.stem)
    return (int(stamp[1]) if stamp else 0, str(path))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="*", type=Path, help="raw JSONL files or result directories")
    for field in ("cases", "model", "machine", "release"):
        ap.add_argument(f"--{field}", help=f"exact {field} filter")
    ap.add_argument("--limit", type=int, default=20, help="latest run IDs, 0 for all")
    ap.add_argument("--json", action="store_true", help="compact JSONL to stdout")
    args = ap.parse_args()
    if args.limit < 0:
        ap.error("--limit must be non-negative")
    reports, errors = [], []
    for path in raw_paths(args.paths or [ROOT / "bench/results"]):
        try:
            rs = report(path)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(f"ERROR {path}: {exc}")
            continue
        if all(getattr(args, k) is None or rs[0][k] == getattr(args, k)
               for k in ("cases", "model", "machine", "release")):
            reports.append(rs)
    for rs in reports[-args.limit:] if args.limit else reports:
        for r in rs:
            print(json.dumps(r) if args.json else compact(r))
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

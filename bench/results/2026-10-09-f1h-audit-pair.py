"""Compare two completed offline F1h audits without evaluating or changing fixtures."""

import argparse
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text())


def lines(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines()]


def pair(baseline, candidate, baseline_raw, candidate_raw):
    a, b = read(baseline), read(candidate)
    assert a["model"] == b["model"]
    assert a["implementation_hashes"]["models.json"] == b["implementation_hashes"]["models.json"]
    ar, br = lines(baseline_raw), lines(candidate_raw)
    assert ar[-1]["system"] == br[-1]["system"]
    at, bt = a["turn_scores"], b["turn_scores"]
    assert [r["id"] for r in at] == [r["id"] for r in bt]
    changes = {}
    for metric in ("judged", "joint"):
        changes[metric] = {
            "wins": [y["id"] for x, y in zip(at, bt, strict=True) if not x[metric] and y[metric]],
            "losses": [y["id"] for x, y in zip(at, bt, strict=True) if x[metric] and not y[metric]],
        }
    routes = []
    for x, y in zip(ar[:-1], br[:-1], strict=True):
        if x["verbatim"] != y["verbatim"]:
            routes.append(
                {
                    "id": y["id"],
                    "baseline_verbatim": x["verbatim"],
                    "candidate_verbatim": y["verbatim"],
                    "candidate_observation_sources": [
                        e["source_id"] for e in y.get("events", []) if e["kind"] == "observation"
                    ],
                    "baseline_answer": x["answer"],
                    "candidate_answer": y["answer"],
                }
            )
    return {
        "baseline": a,
        "candidate": b,
        "paired_changes": changes,
        "changed_routes": routes,
        "candidate_code_receipt_matches": {
            k: hashlib.sha256(Path(k).read_bytes()).hexdigest() == v
            for k, v in b["implementation_hashes"].items()
            if Path(k).is_file()
        },
        "raw_evidence": {"baseline": ar[-1]["evidence"], "candidate": br[-1]["evidence"]},
        "detection_fps": {
            label: {"median": r[-1]["detect_fps_p50"], "minimum": r[-1]["detect_fps_min"]}
            for label, r in (("baseline", ar), ("candidate", br))
        },
        "first_synth_p50_change_s": b["warm_first_synth"]["p50"] - a["warm_first_synth"]["p50"],
        "conclusion_scope": (
            "Development oracle pair only. Instrumentation differs. "
            "No adoption, physical audible latency, or safety acceptance."
        ),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("baseline", "candidate", "baseline_raw", "candidate_raw"):
        parser.add_argument(name)
    args = parser.parse_args()
    print(
        json.dumps(
            pair(args.baseline, args.candidate, args.baseline_raw, args.candidate_raw), indent=2
        )
    )

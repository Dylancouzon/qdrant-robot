"""Combine the frozen M2 and visitor offline audits; no model or evaluation imports."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location("audit", ROOT / "2026-10-09-f1h-audit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
pairs = {
    name: json.loads((ROOT / f"2026-10-09-f1h-audit-{name}-pair.json").read_text())
    for name in ("m2", "visitor")
}
result = {"workloads": pairs, "aggregate": {}, "fixed_visitor_outcomes": {}}
for arm in ("baseline", "candidate"):
    scores = {
        metric: sum(p[arm]["scores"][metric] for p in pairs.values())
        for metric in ("n", "judged", "singleturn", "speech", "joint")
    }
    times = {
        metric: [] for metric in ("first_synth", "synthesis_completion", "estimated_playback_end")
    }
    for workload, p in pairs.items():
        cold = p[arm]["cold_ids"]
        receipt = audit.rows(p[arm]["receipt"])
        raw = audit.rows(ROOT / Path(receipt[-1]["result"]).name)[:-1]
        turns = audit.rows(ROOT / f"2026-10-09-f1h-{workload}-{arm}-all-turns.jsonl")
        for r, t in zip(raw, turns, strict=True):
            if r["id"] in cold:
                continue
            times["first_synth"].append(t["first_audio"] - t["speech_end"])
            times["synthesis_completion"].append(t["done"] - t["speech_end"])
            times["estimated_playback_end"].append(
                max(t["done"], t["first_audio"] + t["audio_s"]) - t["speech_end"]
            )
    result["aggregate"][arm] = {
        "scores": scores,
        "warm": {
            k: {"n": len(v), "p50": audit.percentile(v, 0.5), "p95": audit.percentile(v, 0.95)}
            for k, v in times.items()
        },
    }
    visitor_receipt = audit.rows(pairs["visitor"][arm]["receipt"])
    raw_path = ROOT / Path(visitor_receipt[-1]["result"]).name
    raw = {r["id"]: r for r in audit.rows(raw_path)[:-1]}
    judged = {r["id"]: r for r in audit.rows(raw_path.with_suffix(".judged.jsonl"))}
    ids = (
        "visitor-enroll",
        "visitor-consent",
        "visitor-stranger-know",
        "visitor-stranger-name",
        "visitor-return",
        "visitor-forget",
        "visitor-forgotten",
        "visitor-restart-who",
    )
    result["fixed_visitor_outcomes"][arm] = {
        identity: {
            "answer": raw[identity]["answer"],
            "identity": raw[identity]["identity"],
            "judged": judged[identity]["pass"],
        }
        for identity in ids
    }
    assert all(judged[i]["pass"] for i in ids)
    for identity in (
        "visitor-stranger-know",
        "visitor-stranger-name",
        "visitor-forgotten",
        "visitor-restart-who",
    ):
        assert raw[identity]["identity"]["claimed"] is None
    for identity in ("visitor-forgotten", "visitor-restart-who"):
        assert raw[identity]["identity"]["scores"] == []
baseline, candidate = result["aggregate"]["baseline"], result["aggregate"]["candidate"]
delta = candidate["warm"]["first_synth"]["p50"] - baseline["warm"]["first_synth"]["p50"]
result["prototype_selection"] = {
    "aggregate_judged_gain": candidate["scores"]["judged"] > baseline["scores"]["judged"],
    "no_category_judged_loss": all(
        p["candidate"]["categories"][k]["judged"] >= v["judged"]
        for p in pairs.values()
        for k, v in p["baseline"]["categories"].items()
    ),
    "warm_first_synth_p50_change_s": delta,
    "warm_p50_regression_within_0_2s": delta <= 0.2,
    "qualification_scope": (
        "Frozen development oracle pair only; no adoption. Recorded audio, "
        "strict smoke/native lifecycle, volume, and remaining safety gates are pending."
    ),
    "deletion_scope": (
        "Post-delete and post-restart recognition scores are empty; "
        "independent disk-level deletion is not established by these logs."
    ),
}
result["prototype_selection"]["passes_frozen_95_turn_criterion"] = all(
    result["prototype_selection"][k]
    for k in ("aggregate_judged_gain", "no_category_judged_loss", "warm_p50_regression_within_0_2s")
)
print(json.dumps(result, indent=2))

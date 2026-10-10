# Experiment index

Main contains the accepted Qwen/UI runtime from `011f522` and the reviewed planning work from `26fed40`. Rejected runtime trees are historical Git parents only. Read this index and [STATE](../STATE.md) before opening a detailed record. J means measured on the Jetson, E means measured elsewhere, and U means unverified.

## Current and pending work

| Topic | Outcome | Read next |
| --- | --- | --- |
| Accepted robot and UI | D147 preview accepted as good enough. Main preserves its source byte-for-byte. | [UI guide](mac-audio-interface.md), [D147 audit](../bench/results/2026-10-10-d147-box-continuity.json). |
| Intent, Location, and Owner | Planning only. Seven development sessions contain 30 spoken turns. Owner comes from the named introducer; location comes from the UI. | [Complete plan](answer-evidence.md). |
| Same-owner duplicate objects and crop backgrounds | D148 grouping policy and background masking remain undecided. Named-owner requirements are selected for a future build. | [Known gaps](edge-cases.md#next-session-object-recognition-discussion). |
| Acceptance | Physical audio, held-out quality, sustained detection, headroom, no paging, and M4 remain unqualified. | [Current status](../STATE.md). |

## Completed avenues

| Avenue | Measured outcome and disposition | Evidence |
| --- | --- | --- |
| Model-driven memory tools | Qwen3-VL-2B called memory on 10/13 current-sight questions (J). Preserve code retrieval. | D21; [routing audit](answer-evidence.md#earlier-tests-and-limits). |
| Sufficient-source diagnostic | Answers improved from 14/24 to 21/24 (J). This controlled upper bound supports evidence work. | D87; archived `overnight-2026-10-09`, `bench/results/2026-10-09-bakeoff-evidence-probe-1791527749{,.judged}.jsonl`. |
| Calibrated semantic retrieval | Controlled answers improved from 22/32 to 30/32 (J). Integrated qualification remained necessary. | D103; archived overnight source and its paired-event results. |
| Generative evidence integration | Recorded-audio answers fell from 42/47 to 39/47; joint text/speech fell from 39 to 36 (J). Reject adoption. | D108–D110; [exact aggregate](../bench/results/2026-10-09-f1i-audio-audit.json). |
| Granite with SmolVLM observer | Integrated oracle answers scored 26/47 judged (J). The prototype remained unadopted. | D112–D113; archived overnight and `p2-observer-dialogue` records. |
| Plain versus code-owned tool-result evidence | Both arms scored 21/39 judged (J). Two wins and two losses supplied no aggregate gain. Reject adoption. | D114; [summary](../bench/results/2026-10-09-p2-evidence-role-summary.json). |
| WSL Gemma preparation and prompts | Checkpoint archive verifies. Three BF16 prompts tie at 7/12 (E). Original quantizer exit is unavailable; keep the unchanged prompt. | [Checkpoint receipt](../bench/results/2026-10-10-wsl-checkpoint-validation.json), [prompt receipt](../bench/results/2026-10-10-wsl-gemma-prompt-screen.json). |
| Native Gemma AWQ on official TensorRT | Build exits 0 in 751.99 s (J). Initialization exits 1 before any answer. Required base weights exceed total board memory. | [Findings](jetson-trt.md), [native exits](../bench/results/2026-10-10-jetson-gemma-awq-native.json), [blocked stages](../bench/results/2026-10-10-jetson-gemma-awq-native.jsonl). |
| Detector, names, and drawing | D140–D147 repairs became the accepted UI checkpoint. Earlier filter and tracking failures remain archived. | [Short outcome table](lessons.md#detection-repair-outcomes), [historical lessons](archive/lessons-2026-10-10.md). |

## Retrieve an exact historical record

The [head manifest](archive/experiment-heads-20261010.json) gives every original commit and archive tag. Branches can retire without losing their snapshots. The ours-strategy merge preserves their history while keeping the accepted tree.

```sh
git show archive/2026-10-10/overnight-2026-10-09:research/answer-path.md
git show archive/2026-10-10/p2-observer-dialogue:STATE.md
git show archive/2026-10-10/jetson-trt-testing:STATE.md
git show archive/2026-10-10/overnight-2026-10-09:bench/results/2026-10-09-replay-1791561551.jsonl > /tmp/robot-historical-replay.jsonl
python3 tools/results.py /tmp/robot-historical-replay.jsonl
```

Use an exact raw replay or brain-bake-off path with `tools/results.py`. Read custom aggregate JSON directly. Keyword checks, judged answers, completion footers, and native exits describe different outcomes. Broad discovery can encounter legacy unsupported speech summaries; those errors remain errors.

Private inputs, answers, scripts, logs, media, and telemetry stay ignored under `build/reconciliation-20261010/worktrees/<original-name>/`. Before removal, every moved file was checked by SHA256 and every symlink by its target. Original manifests and the complete recovery bundle remain in that ignored directory. Canonical private build aliases retain existing evidence paths when no root artifact conflicts.

Jetson artifacts stay in `shared/experiments/p2-trt-edge/native-20261010`. Production memories, closed backups, current release `7f67670fa91e`, and rollback `6781adbb7189` remain unchanged. The live Mac preview is paused.

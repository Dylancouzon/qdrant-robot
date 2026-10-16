# Saved measurements

Keep result bytes, judgments, failure records, and resource traces. Historical results are evidence, rather than current operating instructions. [STATE.md](../../STATE.md) owns current status; the [experiment ledger](../../research/experiment-ledger.md) indexes outcomes and rejected approaches.

| Family | How to read it |
| --- | --- |
| `*replay-*.jsonl` and matching `.judged.jsonl` | Use [tools/results.py](../../tools/results.py). Filter by fixture, model, machine, or release. |
| Brain bake-off JSONL | Use the same reader. Keep variants and cached judgments separate. |
| Conversation, exchange, and dialogue-regression protocols and analyses | Read [conversation](../../research/conversation.md) and its [trial report](../../research/archive/conversation-trials-2026-10-15.md). |
| `*ui*`, `*memory-map*`, `*overlay*`, `*view*`, and delivery records | Read [interface checks](../../research/archive/interface-checks-2026-10-16.md) and [booth behavior](../../research/booth-ux.md). |
| Crop, gallery, camera, and detector records | Read [objects](../../research/objects.md), [same-object](../../research/same-object.md), and [detector](../../research/detector.md). |
| Speech, runtime, memory, and model comparisons | Read [stack](../../research/stack.md) and [lessons](../../research/lessons.md). |
| `.tegrastats`, `.paging`, `.vmstat`, `.free`, and other resource samples | Match the exact filename recorded by the run. Separate whole-run and response-overlapping counters. |
| Other component JSON/JSONL | Use the named [benchmark](../README.md) and the corresponding ledger row. The replay reader intentionally rejects unsupported formats. |

```sh
python3 tools/results.py --limit 6
rg --files bench/results | sort
```

The second command lists every retained artifact without loading it. Older evidence that left the working tree remains in [archive tags](../../research/archive/README.md#evidence-from-earlier-archive-tags). Private raw journals and audio stay in ignored `build/` or on the Jetson. Collection can restore raw copies over locally enriched files; reconcile those copies before staging.

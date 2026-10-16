# Review receipts

Dated files preserve the review scope, findings, verdict, and source tree when available. Read [workflow gates](../research/workflow.md#gates) before running another review. A historical PASS covers its recorded tree and scope.

| Family | Purpose |
| --- | --- |
| `*-design.md` | Design alternatives, simplicity, and measurement plan. |
| `*-review.md` | Completed task review and blocking findings. |
| `*-milestone.md` | Whole-milestone acceptance review. |
| Other dated review files | Named specialist reviews and retained findings. |

```sh
rg --files reviews | sort
rg -n 'VERDICT:|^<!-- tree:' reviews
```

These commands index all receipts and verdicts without loading bulk logs. `.log` files remain ignored. The [experiment ledger](../research/experiment-ledger.md) ties reviews to outcomes; [current gaps](../research/edge-cases.md) retain unresolved findings. Missing old artifact paths can refer to [archive tags](../research/archive/README.md#evidence-from-earlier-archive-tags). Preserve original verdict text.

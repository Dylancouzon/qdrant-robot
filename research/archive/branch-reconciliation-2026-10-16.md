# Branch reconciliation, 2026-10-16

Dylan reported the robot assembled and requested reconciliation of every branch while preserving commit history.

## Integrated histories

| Branch | Previous tip | Disposition |
| --- | --- | --- |
| `main` | `23d143043ad9f389a24483000a085996a11737ec` | Fast-forwarded through the conversation commits before the enclosure merge. |
| `spike/conversation-context` | `132979aab149f3e9ce54125163d5290b624ef02a` | All 11 commits after the previous main remain in history. |
| `codex/robot-enclosure` | `3f05c957f6c5b55a14518227ac6676f573f3d09a` | A merge commit retains all 23 commits unique to this history. |
| `spike/first-start-video` | `e1114cf` | Already included in the previous main. |
| `spike/overlay-continuity` | `318466c` | Already included in the previous main. |

The shared servo transport, CLI, regression checks, and hardware guide retain the conversation branch versions. Enclosure CAD and generated print outputs retain the enclosure branch versions. H1 through H7 remain in DECISIONS.md. Enclosure lessons now follow the current experiment ledger format. Earlier fit concerns remain in the linked enclosure archive. Assembly is complete on Dylan's report; mounted calibration, power, motion, cooling, and acoustics still need qualification.

## Local print session

The enclosure worktree contained an uncommitted Bambu Studio save of `output/bambu/White.3mf`. The exact file is preserved as [assembly-white.3mf](../../hardware/enclosure/assembly-white.3mf), separately from generated outputs. Its SHA256 is `e3f1b65b2ac10931eae153a66da8e3ce86d6802f4415b671161750ce386c05d0`. ZIP validation passed. The saved session enables supports, rearranges the four objects across three plates, and contains no sliced G-code. Generated slice estimates describe the original projects.

## Cleanup and verification

Retire branches only after their tips are ancestors of the integrated main. Preserve ignored enclosure build evidence, reference files, and review logs under `build/branch-reconciliation/enclosure-local/` before removing its worktree. The robot deployment and hardware are unchanged by this task. Host checks establish integration consistency; mounted acceptance remains open.

The integration [task review](../../reviews/20261016-183938-4814-review.md) and [documentation follow-up](../../reviews/20261016-184517-11003-review.md) passed without blocking findings. Full deterministic checks passed in 242.88 seconds (E). The enclosure viewer harness and printability self-test also passed.

The follow-up noted a reporting distinction: the generated preview totals rounded plate weights to 488 g, while their unrounded sum is 488.815 g. `preview.py:parts_table` explicitly sums rounded rows. Slice reports preserve the original values; this integration retains the generator and its historical outputs.

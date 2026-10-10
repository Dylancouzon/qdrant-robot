# State

Updated 2026-10-10. Dylan made the Jetson available and requested a separate testing branch. Branch creation and read-only reconciliation are complete. Engine building and inference have not started.

## Active task and Git

Worktree: `/Users/dylanc/orca/workspaces/qdrant-robot/jetson-trt-testing`. Branch: `spike/jetson-trt-testing`, based on reviewed native adapter `0e5a4846ba5f612d08e28f1f55c5794ff555cea3` from `spike/p2-trt-edge`. The local and remote base hashes match. Orca records this worktree as its child. Setup hooks were skipped, and no agent was launched.

Acceptance for this setup: a separate checkout, exact reviewed base, preserved WSL receipts, and verified current Jetson ownership. These checks pass. Only records change. Standing project approval permits scoped commit and push. Use per-command `git -c core.hooksPath=/dev/null` for this records-only task; retain the configured `tools/githooks` setting. No code, full-suite, or review gate is needed for these records.

Changed paths: STATE.md, research/lessons.md, and four copied WSL receipts under bench/results. Main and existing worktrees retain their source and tasks. This historical prototype branch is not an approved full Robot deployment. Never deploy the rejected F1 root branch.

## Preserved product

Protected UI: `/Users/dylanc/orca/workspaces/qdrant-robot/mac-audio-interface`, branch `spike/mac-audio-interface`, clean at `011f52207596098afd2b2cd38e1a16c613f605fa`. Its STATE remains authoritative for D147 acceptance, completed hygiene, and parked D148 recognition proposals.

Current Jetson release is `7f67670fa91e`; previous release is `6781adbb7189`. Preserve both releases, production memories, backups, settings, and the Mac preview. The testing branch introduces no product adoption or main merge.

## WSL evidence

Read [lessons](research/lessons.md) and the coordinator's D116-D119, D117, D133, and D136 before engine work. The current coordinator is `/Users/dylanc/Documents/GitHub/qdrant-robot`. Its selected brief is `research/p2-briefs/trt-edge.md`; its reviewed native runtime receipts are under bench/results.

[Original completion](bench/results/2026-10-10-wsl-d136-completion.md) and [native status](bench/results/2026-10-09-wsl-d136-status.json) preserve the collected quantizer's native exit as unavailable. Later [byte validation and packaging](bench/results/2026-10-10-wsl-checkpoint-validation.json) each exit 0 (E). All 2,433 base tensors and 50 assistant tensors have finite float elements. Quantization does not need repetition.

Verified archive: `/Users/dylanc/Documents/GitHub/qdrant-robot/build/p2/inputs/trt-transfer/gemma4-e2b-int4-awq-20261010.tar`. Size is 8,437,452,800 bytes; SHA256 is `aaf6b5170b427700b048e969d052e0cd8d40a11068e87782e35936c9974c4697`. Private logs, raw answers, inputs, and judge votes remain under the coordinator's ignored build/p2 directories.

[WSL prompt screening](bench/results/2026-10-10-wsl-gemma-prompt-screen.json) completes 36/36 answers, native exit 0 (E). Each of three prompts scores 7/12 with the same five failures. Keep the unchanged prompt. Text smoke passes; the clock-image answer invents objects and fails. This BF16 Transformers reference establishes no AWQ/native quality, Jetson speed, or memory fit.

## Jetson reconciliation and next work

Read-only check at 2026-10-10T14:25:12Z: alias `robot`, boot `09b4bb27-f975-441c-9d00-7af446ec7de6`. No running qr unit appeared in system or user inventories. No GPU lock holder appeared. The protected STATE's former live unit `qr-live-mac-0c66822ccc30` is now collected: LoadState=not-found, inactive/dead, MainPID=0, and empty InvocationID. Its historical native exit is unavailable from this probe; default zero fields prove no success.

Disk has 101 GiB free (J). RAM has 6,040 MiB available, and 68 MiB swap is allocated (J). These idle snapshots establish no turn headroom or paging result. Existing isolated environment and checkpoint directories remain at `/home/qdrant/qdrant-robot/shared/experiments/p2-trt-edge`. No owned test unit or transfer runs.

Next scope: stage and verify the existing archive in the isolated experiment directory, then build native engines on the Jetson. Follow D117's official checkpoint-backed placement and existing wheel. Run text, image, and frozen packet checks before measuring speed, memory, and paging. Use named units, the existing GPU lock, and tegrastats. Preserve native exits and logs. Use temporary memories and the existing tools/jetson.py workflow for any subsequent Robot integration.

Exact next command from this worktree: `git status --short --branch`. Then read the coordinator's `build/p2/logs/wsl-validation-20261010/direct-engine-builder.md` and inspect the installed builder before launching any transfer or build.

Unresolved: native AWQ engine building, faithful vision, answer quality, cancellation, context accounting, speed, integrated headroom, and active paging (U). All CLAUDE targets remain open at acceptance scale. This setup produces no new model performance result.

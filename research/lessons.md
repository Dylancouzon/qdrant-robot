# Lessons and evidence index

Updated 2026-10-10 after accepted-source consolidation into main. Use the [experiment index](experiments.md) for outcomes and archived evidence. Read [STATE.md](../STATE.md) first. Detailed experiment history is preserved in the [historical lessons archive](archive/lessons-2026-10-10.md); decisions remain in [DECISIONS.md](../DECISIONS.md). Numbers marked J were measured on our Jetson, E elsewhere, and U remain unverified.

## Find the current behavior

| Topic | Current guide | Decisions and results |
| --- | --- | --- |
| Live camera, audio, labels, and controls | [Mac interface](mac-audio-interface.md) | D124-D147; [final box checkpoint](../bench/results/2026-10-10-d147-box-continuity.json) |
| Object selection and visual memory | [Booth behavior](booth-ux.md) | D140-D142, D144-D147 |
| Detector and TensorRT export | [Detector](detector.md) | D139, D146; [default qualification](../bench/results/2026-10-10-d146-detector-default.json) |
| Source evidence and answers | [Intent and session plan](answer-evidence.md), [Grounding](grounding.md) | D75, D87-D110; archived controlled comparisons |
| Faces, consent, and deletion | [Faces](faces.md), [identity design](m3-design.md) | D45, D56, D143 |
| Speech, wake word, and model memory | [Runtime stack](stack.md), [wake word](wakeword.md) | D24, D65-D76 |
| Deployment and recovery | [Project instructions](../CLAUDE.md), [STATE.md](../STATE.md) | `tools/jetson.py` and named units |
| Known unqualified behavior | [Edge cases](edge-cases.md), [STATE.md](../STATE.md) | Keep limits separate from measured passes |

## Detection repair outcomes

| Task | Outcome | Audit |
| --- | --- | --- |
| D140 | Retain accepted names through weak queries and verify the current crop before item Ignore. | [Names and crop safety](../bench/results/2026-10-10-d140-detection.json) |
| D141 | Keep at most three diverse views through verified explicit reteaching. | [Object views](../bench/results/2026-10-10-d141-multiview.json) |
| D142 | Reuse one crop vector for at most one global query after a weak preferred match. | [Name reacquisition](../bench/results/2026-10-10-d142-reacquisition.json) |
| D143 | Deliver completed face sources through one owner and validate each JPEG before emission. | [Completed-source delivery](../bench/results/2026-10-10-d143-face-delivery.json) |
| D144 | Suppress a retained name when current descriptor and detector evidence both contradict it. | [False-name suppression](../bench/results/2026-10-10-d144-phone-recovery.json) |
| D145 | Bound negative-vector continuity by queried misses and run Restore through the existing owner. | [Ignore and Restore](../bench/results/2026-10-10-d145-ignore-continuity.json) |
| D146 | Adopt the measured YOLOE-26S detector as the development default, with nano fallback. | [Detector default](../bench/results/2026-10-10-d146-detector-default.json) |
| D147 | Repair drawing geometry and selected `???` styling; Dylan accepts the live checkpoint as good enough. | [Box continuity](../bench/results/2026-10-10-d147-box-continuity.json) |

## Detection repair: what worked

- Compare the repo with the actual live release before editing. For the final D147 style fix, restore accepted release `6781` first and retain broader undeployed changes privately. Only that final fix leaves main, face, and voice code byte-identical to `6781`. Compared with pre-D147 HEAD `47f6eff`, D147 also includes face-outline filtering and drawing-admission changes.
- Test received video, including grey and unknown boxes. Recognition coverage and fresh timestamps do not establish smoothness. D147 changed the artificial phone drawing step from 102.753 px to 36 px (J); user feedback qualified the final preview only as good enough.
- Compare consecutive raw centers when deciding to snap drawing coordinates. Comparing raw position with a lagging smoothed rectangle creates artificial jumps during ordinary motion. Drawing coordinates must never authorize crops, selection, identity, or writes.
- Keep selected `???` styling through matched confidence dips after source admission. Rechecking teaching eligibility on every rendered frame changed the same focus between orange and grey. The final one-condition fix passes 54 Focus tests on Mac (E) and Jetson (J). Actual missing detections and expired size grace can still hide outlines.
- Publish fresh detector sources through the existing serial Recognition owner and latest slot. D143 removes redundant preview pacing; final View validation still checks source, session, gallery, track epoch, and viewer ownership. Keep JPEG and socket work outside locks.
- Keep object views bounded and explicitly verified. D141 retains at most three diverse vectors per point; fresh exact-name matching permits view merging. A mismatch replaces the old physical instance. Six views gave little additional phone benefit and lacked same-kind false-positive qualification.
- Reuse the current crop vector when a weak preferred match needs one global query. D142 adds no embedding and at most one query. Descriptor and detector confidence jointly guard retained names in D144; saved confidence never authorizes a fresh memory write.
- Item Ignore already uses negative example multivectors in Edge. D145 counts actual queried misses, retaining a matched preference through two and releasing on the third. Skipped queries do not advance this count. Restore runs through the existing serial owner with current mutation guards.

Dylan selects Owner from the named introducer and UI-set Location for the next build. Two same-name objects within one owner can still lose recognition. D148's shared-object grouping policy remains undecided. The selected payload requirements remain unimplemented; see the [session plan](answer-evidence.md).

## Routes to avoid repeating

| Route | Outcome and reason | Evidence |
| --- | --- | --- |
| Coordinate median and stock Kalman filters | Rejected. Median added 35-50 px phone lag; stock Kalman worsened chair geometry (E). | D147; private `build/d147/filter-comparison.json` |
| Standard gated Kalman | Rejected. Ordinary motion was rejected for roughly three seconds, with drift and invalid extents (E). | D147; private `gated-filter-comparison.json` |
| Lucas-Kanade drawing prototype | Rejected. Features transferred to background or face; phone extra lag reached 429 px and zero overlap (E). Rotated rectangle envelopes also expanded. | D147; private `lk-readiness.json`; preserved counsel reviews |
| Blindly copying the reference tracker | Unqualified. The reference also uses YOLOE-11L prompt-free, persistent BoT-SORT, and one-miss visibility; current runtime uses 26S TensorRT. Tracker choice alone does not explain the difference. | Read-only reference `cfc0dd2`; D147 |
| Nano for the held-phone fixture | Missing proposal. Existing 26S supplied it and became the D146 default (J). | Detector guide and D146 audit |
| One-scene tuning or perfect-stability claims | Rejected. Changed cup viewpoints reached 121/164 (73.78%) (J); same-kind phone false-positive coverage and sustained performance remain open. | D141, D145; external cup audit |
| Planning and filter loops before a small fix | Poor scope control. Dylan accepted the existing live behavior and requested only `???` blinking repair. Preserve that baseline and stop at the requested checkpoint. | D147 and the archived session lessons |

The earlier one-voice and generative-routing prototypes remain rejected. Source sufficiency improved controlled retrieval, but later integrated audio comparisons lost answer quality. Read the grounding guide and D75/D87-D110 before reopening them; preparation and review counts are not product gains.

## Testing and provenance

Use `python3 tools/results.py` for supported replay and brain-bake-off JSONL files. Custom aggregate audits, such as the D140-D147 JSON reports, must be read directly. Keep each release, variant, workload, and input mode separate. Keyword matches differ from judged answer correctness. A completion footer differs from a native zero exit and from acceptance.

Keep original native failures. D147 recorded baseline and candidate remain native 1 even where received-video inspection explains a provenance boundary. Test source pixels before adopting image tracking: drawn JPEG overlays can create false feature stability. The 202-frame clean PNG fixture captured only 6.73 fps (J) because of encoding overhead; it establishes neither integrated performance nor normal 15 fps dropout behavior.

Media, consenting-face data, recognition vectors, transcripts, private adapters, and raw diagnostic copies remain ignored. Public audits contain numerical outcomes, source hashes, commands, and limitations. Keep the closed memory backup and rollback release until a new live version passes.

## Machine and environment pitfalls

- Use the shared Python 3.12 environment at `/Users/dylanc/Documents/GitHub/qdrant-robot/.venv`; the protected worktree has an ignored `.venv` link. System Python 3.9 lacks required modules and newer APIs. Use explicit workdirs and `VIRTUAL_ENV` with `uv run --active --no-project`.
- Jetson alias is `robot`. It runs JetPack 7, TensorRT, and OpenCV 5, with no installed Torch or Ultralytics. Jetson-specific engines build on the Jetson through the existing named-unit/GPU-lock/tegrastats workflow. Use `grep` remotely because `rg` is absent.
- Reach the WSL2 RTX 3080 box with `ssh dylan@192.168.1.74`; its project is `/home/dylan/qdrant-robot-box`. GPU jobs must use `/home/dylan/qdrant-robot-box/gpu.lock`. Preserve other owners' jobs and Docker/Ollama services; the lock coordinates only participants that use it.
- The Mac preview requires the exact current release. Stop its owned live session, replace only the owned idle local server, refresh the original tab, and restore the session. A second MJPEG subscriber replaces the first. Do not infer smoothness from screenshots.
- Gate index cleanup fails when bookkeeping is partially staged between HEAD and the working file. Stage complete reconciled files or leave the entire file unstaged; never bypass the required hook. This is a tooling pitfall, not detection work.
- Preserve native failures caused by startup, teardown, codec differences, or network loss. The same encoded video can decode to different pixels across OpenCV versions; verify pixels with the deployed decoder. Never retry a quality failure unchanged.

## Separate WSL checkpoint preparation

The other session completed AWQ checkpoint validation and packaging. Preserve [its status receipt](../bench/results/2026-10-09-wsl-d136-status.json). The [validation JSON](/Users/dylanc/Documents/GitHub/qdrant-robot/bench/results/2026-10-10-wsl-checkpoint-validation.json) exists only in the root worktree at that absolute path; do not copy it into this branch. The original quantizer native exit remains unavailable; later validation and packaging preserve native 0. The verified 8,437,452,800-byte archive has SHA256 `aaf6b5170b427700b048e969d052e0cd8d40a11068e87782e35936c9974c4697` (E). Native Jetson engines later build with exit 0, but initialization exits 1 for CUDA allocation failure before answers. Read [native findings](jetson-trt.md). Successful inference and integrated fit remain unqualified.

The completed-job watcher was removed after its private history was saved. Direct checkpoint input is supported by D117; another ONNX export or repeated quantization is unnecessary. Keep WSL export/engine qualification separate from the accepted detection checkpoint. Full machine and recovery notes remain in the historical archive and STATE.md.

Background inside rectangular recognition crops remains present. The reference uses segmentation masking before embedding. This is a parked recognition proposal under D148; read [known gaps](edge-cases.md#next-session-object-recognition-discussion) before changing preprocessing or stored vectors.

## Intent and evidence planning, 2026-10-10

Both requested Luna reports recommend reusing the existing BGE question embedding. Compare explicit rules and independent similarity scores first. A linear multi-label head is a fallback after unseen-paraphrase failures. All parser overhead and quality gains remain U. Keep actions and ownership checks in code. Read the [complete seven-session plan](answer-evidence.md) before implementation.

The current category router returns one label, but separate sighting rules already handle some combined questions. Audit all executed answer paths before blaming one component. Prior controlled evidence gains did not survive recorded-audio qualification; D108 rejects that integration. D21 raw Gemma tool fields contain zero calls in four memory questions; its one/four figure is the keyword pass count. Preserve the decision history and distinguish these fields.

Named sightings store frame thirds and time, without semantic place. A parser cannot supply a missing place or fix current-match precedence by itself. Future isolated tests must override shared knowledge and brain log defaults as well as the robot memory root. The replay convenience wrapper deploys implicitly, so it cannot run this isolated comparison unchanged. The planning decision below authorizes no runtime, fixture, schema, or deployment change.

Dylan now requires Location and Owner payloads, with UI location entry and owner-aware chat wording. Capture location with each observation; bind owner to the named introducer. Your phone requires a current-speaker match. A different speaker hears Ana's phone. Current name-only object keys must change before two owners can each retain a phone. Preserve unowned records and D148 ambiguity limits. This is a planning requirement; implementation remains deferred.

## Repository consolidation

Keep main's executable tree identical to accepted 011f522. The ours-strategy history merge retains rejected experiment parents without adopting their code. Archive tags and a verified full Git bundle preserve all original heads. The compact experiment index replaces branch-by-branch context loading. Exact sanitized receipts remain in main; larger historical snapshots remain in Git.

Before removing worktrees, move ignored evidence into canonical build/reconciliation-20261010 and verify each file hash and symlink target. Preserve the canonical environment, secret file, reference clones, remote releases, production stores, and closed backups. Pause the owned preview gracefully. Keep this active session checkout until handback; retire its experimental branch after detaching at main.

## Gemma budget clarification, 2026-10-10

The original handoff is intent parsing and tool calling optimization in research/answer-evidence.md. Dylan rejects the invented Qwen TensorRT comparison as its replacement. He separately authorizes Gemma experiments with CPU Kokoro, accepts 24 tok/s if answer quality improves substantially, and asks to use WSL whenever compatible. This session covers only the Gemma experiment. Intent/tool work remains the next step for a later session. No quality gain or target change is established.

Budget Gemma together with detection, face and object encoders, retrieval, Edge, ASR, VAD, TTS, camera, history, and the 500 MB reserve. CPU/GPU placement alone does not reduce unified RAM. Native D117 weights already exceed physical memory; unchanged retries remain rejected. Historical replacement-brain allowance is roughly 2.3-2.5 GB (estimate from older component exercises, not current 26S acceptance).

The current Google-linked [LiteRT model card](https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm) reports 24.2 tok/s and 2,739 MB process CPU memory on Orin (E, another board). It describes 0.8 GB text working weights plus 1.12 GB mapped embeddings and on-demand modality encoders. Those weights and process RSS do not establish total active unified-memory use. Mapped pages still occupy RAM or require storage reads; measure cold/warm and sustained multimodal turns with every robot component active. Current JetPack compatibility remains unverified here.

LiteRT 0.18.0 requires its configured cache directory to exist before Engine construction. The first WSL smoke exited one before generation; create that isolated directory before the one infrastructure retry. Preserve the original receipt separately.

The WSL LiteRT GPU request selected Mesa llvmpipe software Vulkan rather than RTX 3080. Corrected GPU smoke initialized then exited signal 11 before answers. CUDA availability does not establish LiteRT WebGPU acceleration on WSL. Keep the native failure and use CPU for compatible WSL screening; Jetson has an actual NVIDIA Vulkan ICD.


## Gemma LiteRT preliminary result, 2026-10-10

The pinned full multimodal LiteRT 0.18.0 bundle runs on our Jetson NVIDIA Vulkan device. Standalone short-reply median is 29.69 tok/s (J). The frozen Jetson GPU screen scores nine of 12, versus fresh WSL Qwen seven of 12 (E): two net wins miss the frozen three-win rule. WSL CPU Gemma scores six of 12 (E), with different replies. Keep backend results separate; compatible CPU screening cannot predict GPU answers exactly.

Stop before adaptation or integrated replay when the preliminary quality rule fails. Preserve the executable candidate and failure receipts instead of lowering the rule or tuning the frozen prompt. CPU Kokoro/full-stack fit, speech latency, stranger safeguards, and sustained paging remain unqualified. Standalone Jetson jobs each wrote two system swap pages, including during generation; system counters establish activity but not process attribution. See the Gemma LiteRT result decision, [topic report](gemma-fit.md), and [sanitized audit](../bench/results/2026-10-10-gemma-litert-screen.json).

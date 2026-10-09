# Compare architectures for a sustained robot visit

Superseded before dispatch. Dylan rejected this testing-first plan and requested selected model/runtime/quantization decisions followed by implementation. Keep this record for its prior evidence and rejected preparation path; do not execute its dispatch commands.

P2, 2026-10-09. Dylan authorizes concurrent experiments on separate branches. F1j implementation is paused. Its reviewed contract remains evidence, rather than the next build. J means measured on our Jetson, E elsewhere, and U unverified. All proposed gains are U.

## Decision to make

Choose between a persistent conversational VLM and separate vision/event and text-dialogue roles. Compare both against deployed cd60. The question is whether either architecture produces a large sustained capability gain on one 8 GB Jetson. Neighbor counts, prompt wording, and a larger model alone do not answer this question.

The lead owns the shared workload, release workflow, scoring, STATE.md, DECISIONS.md, and deployment. Builders implement independently after their design gate. Concurrent work never means concurrent GPU benchmarks on one machine. The fixed outcomes remain: all deployed models on Jetson, Qdrant Edge in-process, source-backed answers, consent, actual deletion, rollback, and reproducibility.

## What the history establishes

| Evidence | Result | Consequence for this plan |
| --- | --- | --- |
| Continuous cd60 baseline, D96 (J) | 10/48 judged: sight6/12, older0/9, topic0/9, correction0/6, absence1/6, chat3/6. First synthesis2.291s p50. | The main test must include a continuous visit, scene changes, references, and corrections. Small oracle gains cannot select an architecture. |
| Sufficient-evidence diagnostic, D87 (J) | Same2B14/24→21/24, seven wins/zero losses; only three sufficient-arm failures. | Source coverage and delivery need separate attribution. Bigger brains and training are not established remedies. |
| F1f controlled retrieval, D103 (J) | 22/32→30/32, driven by older0/8→8/8. | Retrieval can work in controlled conditions; repeat neither its calibration nor its fixture preparation. |
| F1h oracle then F1i recorded audio, D107/D108 (J) | M2 38/74→42/74, visitor16/21 both; recorded audio42/47→39/47, zero wins/three losses. | Retire the assumption that opening generative routing establishes deployed improvement. Preserve reliable authority during architectural comparison. |
| Qwen3.5 in shared multimodal loop, D27 (J) | 24/39 versus Qwen-VL32/39; first synthesis2.55s versus1.81s. Prefix reuse failed. | Reject another drop-in replacement. A text-only role after a separate observer is a changed hypothesis, with this prior risk retained. |
| Model capacity, D66/D68 (J), F1h diagnostic (E) | Integrated4B about190MB available; recentWSL2B8/12 versus4B7/12. | No generic4B/model sweep. Reopen capacity only with a changed workload and measured memory intervention. |
| Conversation architecture, D27/D77 | Scene changes remove assistant messages; history holds four exchanges. No4K/8K sustained result. | Test dialogue continuity and context as architectural variables.2K/64 is the baseline, rather than a permanent restriction. |
| Timing diagnosis, F1i (J) | Strict90s smoke passed;0.428s report/resource scan overlapped worst delayed audio. | Process separation tests model roles/resource contention, rather than claiming an established GIL failure. Match evaluator instrumentation. |

Continuous output has four scored and five auxiliary split utterances. Generated audio checks passed all72 transcripts within0.35WER, but strict speech54/72 preserves split failures. System paging remains unattributed. These results establish neither physical audible latency nor no-paging safety. Compact history cannot parse the continuous format; use the independently reviewed D96 operations/scoring artifacts, without changing the reader now.

## Two primary branches

### P2-C: persistent conversational VLM

Hypothesis: the shared VLM can support a sustained visit if conversational state survives visual changes and the prompt permits useful answers. The changed assumption is that visual cache invalidation must discard assistant dialogue. Keep one resident Qwen3-VL-2B, current-view inference, the existing detector/voice stack, and reliable authority. Separate dialogue history from current visual state. Replace the four-exchange cap with complete-turn retention governed by the rendered token budget. Mark historical visual claims by source/time; generated claims never become observed facts. Visitor changes still clear restricted dialogue.

Compare current history handling with persistent source-aware dialogue on identical scene-change histories. First hold2K/64/256 fixed to attribute continuity. Then test4K context/128 output/up to three sentences, with the corresponding unchanged-history4K/128 control. Three sentences and4K/128 are U test settings, rather than selected production limits. Preserve exact token accounting and use complete-turn truncation. Update the system sentence instruction and streaming stop together for the three-sentence arm; caption stopping remains separate from spoken-answer stopping. Do not add summaries or training to make the result pass.

The cheap diagnostic uses all existing D87 packets and the chronological continuous dialogue trace, with current/past visual controls. Include necessary images and their roles; a text-only trace cannot qualify VLM sight. The WSL result ranks quality hypotheses. The Jetson next loads the full stack and exercises4K/128 across sustained turns. Measure actual paging, prefill, completion, first synthesis, stale-scene claims, and headroom. No KV estimate can qualify the context increase.

Reject continuity if paired follow-up/correction quality does not improve or stale-scene claims increase. Reject4K if it adds no quality or violates the active resource floor. Do not try8K simply because4K fails. A memory intervention requires its own measured comparison and gate.

### P2-E: independent observer and text assistant

Hypothesis: separating visual observation from conversational generation can produce a coherent source-backed assistant and reduce image-prefill/GPU contention. This changes model roles and event production, rather than source-span counts. The observer creates time-stamped, source-linked visual events independently of user questions. The text role receives dialogue and Edge evidence; it requests a fresh observation when current evidence is stale. It never treats a historical caption as current sight. Retrieval and actions remain in code; this is not another model-tool-routing test.

First use the existing Qwen3-VL-2B as both role baselines, scheduled serially, so the role comparison does not depend on a new model. Defer the already installed Qwen3.5-2B text-role comparison until the single-model observer loop passes the quality screen. Then compare on identical text/history/evidence, requiring at least three additional judged/joint wins out of24 D87 packets and no capability loss before any second-model residency work. If the24-case ceiling leaves fewer than three possible wins, keep the single-model design and stop this model comparison without expanding fixtures. Keep2K/64 controls, then use4K/128 for the sustained capability screen. Do not force a second model if the existing model's text role wins. No broad family sweep or automatic4B trial belongs to P2.

Freeze the observer's evidence interface before implementation: source ID, kind, capture/speech times, visitor scope, complete authority/hash, uncertainty, and any existing retained-image link. Observation records and dialogue statements remain separate; updates retain their original source facts. Do not generate episode summaries or infer identity from track labels. Measure event completeness at scene changes as well as answer quality. Source omissions invalidate a claim about the text model's capacity.

Keep detector sightings frame-free under D54. Reuse existing permitted turn frames when available; do not create per-track face images or copied crop archives. Any broader image-retention policy requires a separate privacy/schema design gate. The first observer remains the existing VLM; a better vision model is eligible only if a paired perception result identifies its need.

Freeze the first observer schedule before code. Use the existing scene-change predicate and pinned threshold on detector camera samples, at most one admitted observation per second. Hold exactly one pending observation: the newest changed frame replaces older pending work. An observation is fresh for two seconds and only while the existing scene-change predicate still matches its source frame. A current-sight question with stale evidence requests one fresh speech-start-frame observation before its answer. Every event records capture/start/end times, canceled/replaced reason, age at use, and missed scene changes. Speech has priority: close an active background observation stream at speech start, discard incomplete text, and never wait for queued background observations. Foreground inspection and its answer serialize through the same resident VLM; detection, ASR, and TTS remain active. The one-second admission and two-second freshness bounds are U fixed experiment settings. Reject the route if transient-scene omissions or refresh stalls erase its gain; do not tune failed cases.

Independent observations create frame-free source points in the existing Edge shard with caption authority, frame digest, capture time, detected-label/track links, visitor boundary, and existing confirmed named-object/person owner links. They store no new image file. Detector/person/face presence makes the whole event visitor-restricted; only verified person-free scenes may be shared. Unknown scope stays restricted. Generated descriptions retain model-observation uncertainty. Confirmed owner links require existing consent/identity or named-object matches; track IDs alone never establish identity or ownership. Use the existing retention time/point caps for these points. Before insertion, serialize scope/owner validation with current visitor state and deletion; late or canceled observations cannot recreate deleted facts.

Extend existing forget/ignore selection to include these point IDs before running the existing deletion operation. Person forgetting removes its owner-linked observations and the restricted observations of the current visitor boundary. Object forgetting removes observations linked to that named object and observations mentioning its kind under the existing vocabulary matcher. Ignoring a kind excludes/deletes its observation records under current behavior. Deleting a mixed observation removes the whole point, never a text summary that retains the forgotten fact. Pending writes for deleted owners/kinds are rejected. Prove deletion after restart, shared-versus-restricted retrieval, unknown visitors, and late-write cancellation with generic fixtures before remote quality runs. The branch schema/API gate must verify these fields and filters against installed Edge stubs. No provisional implementation can skip these ownership checks.

Test two Jetson layouts only for a quality-qualified role design: one residentVLM scheduled between observer/dialogue, and separate resident observer/text models if the measured budget permits them. If dual residency violates the resource floor, reject that layout. Test unload/reload only if the alternate text model first passes its quality criterion and the design gate identifies a credible integrated latency benefit. All switches close native resources and preserve Edge in the owning robot process. Separate model servers do not imply a second memory service. OS reconfiguration is outside the first experiment.

Reject the split design if the observer loses required facts, the text role adds unsupported claims, current sight becomes stale, or role scheduling erases its quality/latency benefit. Reject dual residency on measured resource failure; a WSL fit does not justify Jetson adoption.

## Shared experiment ladder

1. The lead freezes one diagnostic manifest from existing development material before outputs: all24 D87 cases, the complete63-utterance continuous chronology, and existing current/past/absence/visitor controls. Preserve images, transcript provenance, source authority, rubric hashes, and input order. Builders receive interfaces and generic examples, never expected answers or held-out data. Read no selected failure to invent a special rule.
2. Freeze input treatments explicitly. Recorded actual ASR and clean scripted text are separate modes; neither replaces audio acceptance. Fixed-packet role tests use identical source facts and history bytes; these diagnose interpretation only. Separately run a chronological loop where each candidate consumes its own prior replies and stores its own source-backed events. Observers receive only frames available before the answer cutoff, with no future fixture frame or expected fact. This closed loop tests continuity and event production; its branches can create different facts/history, reported as bundle behavior. Score stored, selected, delivered, and sufficient evidence separately from answers.
3. Run cheap WSL quality screens and Mac checks. Score all preselected inputs with one cached three-vote judge and independent source review. Record cold/warm, model/runtime/input hashes, output length, token limits, and unsupported claims. Do not interpret WSL latency as Jetson latency. The WSL chronological screen requires at least five additional judged and joint answers on the48-question trace, gains in at least two weak families, and zero per-family/current-sight/privacy losses before Jetson qualification. Fixed-packet wins alone cannot advance a route. The D87 packets diagnose adequate-evidence interpretation; they are not a separate mandatory preparation project. Stop a weak route on evidence and retain its negative result.
4. Each quality-qualified branch gets an exclusive Jetson resource/short integrated check. Keep all components active and record tegrastats, process-tree memory, active paging, detector cadence, queue depth, and native completion. Use the existing deployment/run/collect workflow, immutable releases, named units, fresh owned memory, and bounded logs. Lead serializes these jobs and restorescd60 between trials.
5. Run the unchanged1,800-second continuous development schedule once per materially different qualified architecture, with matched instrumentation and exact source/audio pacing. Run one matchedcd60 control once, and use the historical baseline as context. Score all48 questions, auxiliary failures, and joint speech. No oracle result can skip this step.
6. Run unchanged recorded-audio M2/visitor and identity/deletion/restart controls on the selected candidate. Keep strict90s source/scheduling smoke. Review, integrate one winning path, delete replaced production code, and commit/push. Preserve rejected branches and evidence; never merge both prototypes as product switches.

The diagnostic runner must reuse generation/scoring and the qualified continuous harness. Add only the interface needed for the two branches; do not build another benchmark framework. Existing continuous data is development after use. Subsequent held-out acceptance needs a fresh source freeze, which follows architectural selection rather than delaying it.

## What counts as moving the needle

P2's architectural selection floor is U and deliberately larger than a one-to-four-answer oracle gain: at least20 percentage points in judged and joint correctness on the48-question continuous workload. This means at least10 additional correct answers against the matched control, with gains in at least two formerly weak families: older observations, topic references, corrections, absence, and conversation. Require no per-family judged/joint loss on this workload, no current-sight loss in the regression suites, and zero new false identity or privacy/deletion failures. Publish every win and loss.

Require warm first-synthesized-audio p50 regression of at most0.2s versus the matched control; report p95, completion, output length, endpointing, and ASR separately. Require p95 first-synthesis regression of at most0.4s, which detects observation-refresh tails hidden by the median. Prefer lower latency if quality ties. Resource qualification requires at least500MB active headroom and no runtime-attributed active paging; unattributed system paging leaves safety unresolved and prevents adoption claims. Do not disable swap to manufacture a result. If telemetry cannot attribute paging, keep a prototype selection explicitly separate from adoption and resolve attribution before release.

The interim gain remains far below90% and never completes the project. Final targets remain90% per held-out capability,1.2/2.0s physical audible p50/p95,15fps detection,30tok/s,500MB headroom/no active paging, and Edge10ms p99. Physical acceptance waits for connected audio hardware. If neither architecture clears the large-gain floor, preserve the results, ask Astra for the next architecture-level counsel, and choose a new route from attributed failures. Do not return automatically to neighbor tuning.

## Concurrency and repository hygiene

Use two isolated git worktrees on spike/p2-conversation and spike/p2-observer-dialogue. Both start from the same verified baseline runtime, rather than rejected038 runtime at the current branch. The lead verified core runtime, voice/perception modules, dependencies, and model manifest at4d73264 against immutablecd60; every inspected hash matches. Record those bindings in bench/results/2026-10-09-p2-baseline-bindings.json before dispatch. Carry the qualified evaluation tooling without changing baseline behavior. The coordinator remains on spike/overnight-2026-10-09.

P2-C owns only its worktree's conversation/prompt path and related checks. P2-E owns only its worktree's observer/dialogue scheduling/interface and related checks. Shared files may differ across isolated prototypes; the lead reviews every diff and resolves interfaces before integration. No worker edits rootSTATE/DECISIONS, another branch, deployment links, shared memory, judge cache, models, credentials, or machine configuration. Each branch follows CLAUDE/AGENTS and enables tools/githooks. Each architectural design passes its gate before code; each task gets review/checks before commit. Concurrent builders are authorized by Dylan for this P2 experiment; no nested delegation.

One WSL GPU lease and one Jetson GPU lease exist, owned by the lead. Builders develop and test locally in parallel; WSL/Jetson jobs run in a lead-published queue. Do not modify another project's services or Docker containers. Named jobs bind host, directory, source release, PID/unit, exact command, start time, log, and collection path in rootSTATE before launch. Worker reports include diff, checks, failures, evidence, running jobs, and exact next command.

Disk estimate: each branch reuses models; code/worktree copies below200MB, diagnostics/results/WAVs below300MB per run (U). No new bulk model download is planned. Progress comes from completed packets/turns and unit logs. Existing command startup/stall/cleanup/reaping watchdogs protect native operations; healthy research has no execution deadline. Preserve interrupted results, inspect process ownership, diagnose once, and retry only infrastructure failures. Stop for OOM, throttling, disk failure, broken fixed outcomes, or absent progress; preserve kernel/native logs before cleanup.

## First dispatch after design approval

The lead freezes diagnostic inputs and creates both worktrees from4d73264. Start two minimal single-model loops first, with actual paired answers as the first checkpoint. P2-C receives D27/D72/D75/D77/D96/D109-D110, allowed paths, continuity/stale-image interfaces, Mac/WSL diagnostic checks, and stop conditions. P2-E receives D21/D24/D27/D54/D61/D66/D68/D87/D96/D109-D110, source/privacy interfaces, role quality/resource checks, and stop conditions. Start the smallest runnable branch loops. Each builder must show the lead actual paired answers before adding an enabler or expanding a fixture.

Sources: DECISIONS.md D21/D27/D54/D61/D66/D68/D72-D83/D87/D96/D103-D110; research/lessons.md, grounding.md, brain-capacity.md, stack.md, continuous-eval.md; robot/main.py, brain.py, memory.py; tools/jetson.py; bench/results/2026-10-09-f0f-operations.jsonl; D87 raw2026-10-09-bakeoff-evidence-probe-1791527749.jsonl; F1h raw2026-10-09-replay-{1791556237,1791556929}.jsonl; F1i raw2026-10-09-replay-1791561551.jsonl and audited sidecars. F1j contract and manifest remain preserved under D110.

Astra counsel GO WITH CHANGES: reviews/20261009-125614-99907-design.md. Required scheduling, observation ownership/deletion, closed-loop comparison, numerical advancement, and deferred residency changes are incorporated. The context arm explicitly replaces four-exchange history retention and updates sentence instructions/stops together.

## Exact dispatch commands

Both worktrees already exist from4d73264. Check their hooks before launch:

```sh
git -C build/p2/conversation config core.hooksPath tools/githooks
git -C build/p2/observer-dialogue config core.hooksPath tools/githooks
```

Run each command in a separate supervised Mac terminal. Claude's installed CLI confirms the Opus alias, print mode, and permission mode. Its stdin reads the concrete builder brief; no shell interpolation is required.

```sh
cd /Users/dylanc/Documents/GitHub/qdrant-robot/build/p2/conversation
claude --model opus --name P2-C --permission-mode bypassPermissions --print < /Users/dylanc/Documents/GitHub/qdrant-robot/research/p2-briefs/conversation.md > /Users/dylanc/Documents/GitHub/qdrant-robot/build/p2/logs/conversation.log 2>&1
```

```sh
cd /Users/dylanc/Documents/GitHub/qdrant-robot/build/p2/observer-dialogue
claude --model opus --name P2-E --permission-mode bypassPermissions --print < /Users/dylanc/Documents/GitHub/qdrant-robot/research/p2-briefs/observer-dialogue.md > /Users/dylanc/Documents/GitHub/qdrant-robot/build/p2/logs/observer-dialogue.log 2>&1
```

The lead records PID/session, start time, exact command, and logs before leaving a launched session. Builders stop before models or remote work. These tasks produce local runnable loops while the lead materializes input files. The frozen source-membership recipe is build/p2/inputs/manifest.json; fixed packets and chronological input paths are listed there. Scoring rubrics remain lead-only. Preserve the recipe alongside executed inputs before any quality run. Output patterns are bench/results/2026-10-09-p2-{c,e}-*.jsonl, with owned speech/judge sidecars. No quality test starts with only a recipe.

Coordinator next commands after builders report:

```sh
git -C build/p2/conversation diff --stat
git -C build/p2/observer-dialogue diff --stat
```

Read both diffs, run their stated checks, and inspect paired answers before adding another model or layout. The concrete briefs preserve allowed paths, fixed interfaces, machine ownership, acceptance, and stop/report conditions.

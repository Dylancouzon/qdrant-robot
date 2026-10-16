# Decisions

The decisions that bind the current design. Each entry: date, decision, why, rejected alternatives, evidence. Three lines or fewer. Add an entry only when a task changes the design or a rule, or for each counted held-out use; reviews, receipts, and status go elsewhere.

The full history (D1 to D148 and the 2026-10-10 session entries) is in [research/archive/decisions-2026-10-10.md](research/archive/decisions-2026-10-10.md). Evidence paths that are no longer on main are in tag `archive/2026-10-10/pre-cleanup` (`git show archive/2026-10-10/pre-cleanup:<path>`). Every avenue tried, with its outcome, is in [research/lessons.md](research/lessons.md).

## Scope and process

**D1–D5 2026-10-07: Product scope.** Reach the reachy-edge-memory capabilities on the Jetson alone, with our own architecture. Answer quality first, then speed. No servos or arms. Off-the-shelf models first; train only on a measured miss.

**D6 2026-10-07: Pin qdrant-edge-py 0.8.0.** Verify capabilities against its `.pyi` stubs. Fusion over prefetches works; `query_batch` and `Memory` placement are on master only.

**D7 2026-10-07: Reference revisions.** `refs/reachy-edge-memory` at a3d8fbe; `refs/qdrant-edge-memory-robot` at cfc0dd2.

**D17 2026-10-07: Light safety net.** The pre-commit hook blocks only failing deterministic checks and reminds about missing reviews. Rejected: review-to-tree binding that blocks commits, command guards, CI audits.

**D40/D71 2026-10-08: Breadth first.** Every feature end to end, then tune. Edge-case review findings go to `research/edge-cases.md`; only main-flow failures and fixed-outcome risks block. Reopen when a logged case actually happens or risks a fixed outcome.

**D76/D77 2026-10-09: Raise the ceiling; challenge decisions with evidence.** Targets are a floor. Before reopening an approach, read its ledger row, name what changed, and define a paired comparison.

**D83 2026-10-09: No execution deadlines.** Stop on evidence or resource limits, never on elapsed time.

**D149 2026-10-10: Lean records.** Dylan: process records crowded out product work (19 of the last 30 commits were receipts). One STATE rewrite and at most one decision per task; no receipt-only commits; the ledger in `research/lessons.md` keeps every avenue. Rejected: deleting history (it stays in the archive and the tag).

## Robot and machines

**D18/D20/D31 2026-10-07/08: Robot OS.** Keep `memory-robot-clock.service`; docker, snapd, ModemManager, nvargus, bluetooth, and others are disabled (about 300 MB). MAXN_SUPER power mode 2 via the Super bootloader. Backups: `backups/robot-20261008`.

**D75 2026-10-09: The WSL 3080 box runs bake-offs.** `ssh dylan@192.168.1.74`, llama.cpp 9c2e0e4 with `orin.patch`, matches Jetson answers 63/93. Acceptance numbers stay on the Jetson.

## Brain and answers

**D21 2026-10-08: Retrieval in code every turn; no model tool calls.** 2B models called a memory tool on 10–12 of 13 current-sight questions. Code retrieval scored 20/21.

**D27/D35 + Gemma full stack 2026-10-08/10: Qwen3-VL-2B on llama.cpp with CUDA Kokoro.** It beat Qwen3-VL-4B (37 vs 41/47), Qwen3.5-2B, Granite+SmolVLM (26/47), and Gemma LiteRT (31 vs 39/47 recorded, 4.9 s first audio). The 4B leaves 190 MB and swaps (D66, D68).

**D28/D39/D72 2026-10-08: Generation limits.** 2,048-token context, 256 image tokens, 64 output tokens with a one-sentence cap, `--cache-ram 0 -ub 256`. 512 image tokens gave no gain within noise.

**D25/D27 2026-10-08: Recall uses captions, not stored frames.** Each stored frame gets a caption written from that frame alone. A question matching a knowledge fact at 0.93 or more gets the fact verbatim.

**D75/D108 2026-10-09: Code answers stay for ordinary memory questions.** Two integrated attempts to route retrieval into the brain lost (38 vs 44/74; 39 vs 42/47 recorded audio). The saved alternate is `research/archive/one-voice.patch`.

**D150 2026-10-10: Recall of unnamed objects shown earlier uses RAM captions.** Each exchange keeps its frame in RAM for the conversation window; the idle worker captions one frame per view, and a past or combined question about something shown is answered from the selected frame's caption (code answer, or one Memories line beside the present image). Nothing new persists (D127 holds). Paired J runs: recorded 39 to 41/47, recall sessions 8 to 13/15, first audio 1.45 to 1.41 s p50; B (labeled earlier image) 38/47 and 10/15 rejected. `research/recall.md`.

**D66 2026-10-08: Pause decode at the first phrase.** Synthesize, then resume with the text so far. First audio 0.73 vs 0.94 s p50 with identical answers.

## Voice

**D24/D38 2026-10-08: Silero VAD and Parakeet TDT 0.6B v2 int8 on CPU.** 0.8% WER, 0.22 s per line. Hangover 0.35 s, 0.7 s after 4 s of speech. Rejected: Moonshine (heard "Qdrant" as "current").

**D65 2026-10-08: Wake phrase "Hey Edgy".** Spotted in the Parakeet transcript with aliases, then a 20 s follow-up window. A trained openWakeWord model only if this misses.

## Memory, identity, and objects

**D36 2026-10-08: The Edge query target is met.** p99 0.47–0.49 ms at 1,000 points and 1,000 queries per kind on the Jetson, against 10 ms.

**D51/D54/D56 2026-10-08: Retention.** 12 h window plus hard caps; sightings keep label, region, and times without frames. Protected: enrollment and named-object evidence.

**D45/D50 2026-10-08: Faces.** YuNet, then insightface w600k_r50; a claim needs two enrolled shots at 0.328. Zero false identities on 4,113 strangers. One Edge point per person with a MaxSim multivector.

**D49/D60/D68/D69/D70 2026-10-08: Identity rules.** A told name answers only for the same visitor (face match or the 20 s no-face window); none after a restart. A name is not consent; the robot offers face enrollment once. Only first-person statements are scoped to the visitor.

**D64/D141/D142 2026-10-08/10: Named objects.** DINOv2-small crops as a MaxSim multivector in their own shard, threshold 0.822, at most three diverse views. A weak preferred match may run one global query with the same crop vector.

**D127/D128/D130 2026-10-09: Visual memory.** Only named or explicitly tracked objects persist. Ignore rules persist across restart. Explicit names such as "Dylan's smartphone" are kept apart from detector categories.

**D144/D145 2026-10-10: Name safety and Ignore.** A retained name is dropped when both the current descriptor and the detector contradict it. An ignored item stays hidden through two failed queries and is released on the third. Restore runs directly through the serial owner.

## Perception and interface

**D146 2026-10-10: YOLOE-26s TensorRT is the detector default** at 384x640 FP16, with YOLOE-26n as fallback. 26s detects the held phone that 26n misses.

**D67/D136/D147 2026-10-08/10: Focus and boxes.** One unknown focus for teaching. Display smoothing never authorizes crops, writes, or identity. Dylan accepted release 7f67670fa91e as good enough; coordinate filters and optical flow were rejected.

**D143 2026-10-10: Face results publish when recognition completes,** with detector-paced admission through one serial owner.

**D151 2026-10-10: Ignore is a UI action on a held offer** (Dylan: UI only, items stay a few seconds after leaving view). Spoken ignore is removed. Each eligible object track keeps an offer (a copied crop, never a person track) for 8 s after its last source; Ignore persists only if that offer is still current. Supersedes the live-track check of D136/D140 for Ignore only.

**D152 2026-10-10: The robot hears and speaks through its own USB audio** (card `Device`; its microphone beat the camera microphone by about 3 dB, J). It runs as the Jetson unit `qr-robot`, which the Mac page attaches to and never stops on disconnect. Input is silenced while a phrase is queued or playing and for 0.3 s after (no barge-in). The volume slider sets the USB mixer and is saved in `shared/`. Supersedes the Mac audio path of D122–D126.

**D153 2026-10-10: Booth interaction timing and two-step teaching** (Dylan's live session). Follow-ups need no wake phrase for 60 s after an answer ends (supersedes D65's 20 s; the page says "Say 'Hey Edgy'" once it lapses). Ignore offers last 30 s after their last eligible view (supersedes D151's 8 s). A nameless "Track this" pins the focus track and epoch from speech start and asks "What should I call it?"; a lost pin fails closed and person views never enter object memory. Volume is a UI control only.

**D154 2026-10-11: Named-object views come from a teaching window.** After a naming turn, the robot adds views from the taught track while the tracker keeps its id (17 viewpoint videos, E: 530/816 later-view hits vs 397 fixed, 435 simulated confirmation; masking worse). Voice confirmation stays secondary; masking is not adopted. Recognition thresholds and timing are UI settings (Dylan). Refines D64/D141; `bench/results/2026-10-11-gallery-1791694947.json`.

**D155 2026-10-11: Named objects belong to a visitor.** One point per (visitor id, name); a visitor id is stable for a conversation and stored on an enrolled person, so promotion moves nothing. The same owner's reteach always appends (Dylan). Labels read "Ana's mouse"; "Ana's X" resolves only through an enrolled Ana. "Forget me" deletes evidence, then objects, then the person. The old things shard was backed up and replaced. Edge things.score p99 2.29 ms at 200 objects x 24 views (J). Supersedes D148's same-name half.

**D156 2026-10-11: The robot asks about near matches by voice.** A current visitor's object that stays just under the threshold for `ask_delay_s` on the focused track gets "Is this your mouse?" only in a conversation blank (`ask_blank_s`), at most `ask_max` per conversation, 60 s apart, once per track. "Yes" adds the view as `confirmed`; anything else is a normal turn. Settings live on the page (Dylan).

**D122–D126 2026-10-09: Mac interface.** `tools/talk.py` serves a loopback page with Start, Mute, and Stop over native audio and SSH. All models stay on the Jetson.

## Pending requirements

**D148 2026-10-10: Same-name objects and crop backgrounds are parked.** Two objects with one name can leave neither recognized; crops keep background pixels. The policy is undecided.

**Owner and location 2026-10-10 (Dylan): Bind places and people to object evidence.** A UI-set location on each sighting; an owner from the named introducer on the named object. Not built yet; see `research/owner-location.md`.

**D157 2026-10-11: Keep the demo UI compact.** Dylan approved Live, Memory, and Settings tabs, three-view carousels, sliders, visible commands, and readable evidence. Conversation follows replies with a normal scrollbar. Transient evidence resolves once per turn from stored source links; technical retrieval details stay expandable.

**D158 2026-10-11: Put the robot view first.** Dylan requested fewer labels and a stronger Qdrant theme. The camera takes most of Live; camera, conversation, and speaker headings are visually removed. Use the official logo, palette, and locally served Mona Sans; preserve accessible control names and the ordinary transcript scrollbar. Refines D157.

**D159 2026-10-11: Object drawing bridges detection gaps for at most 200 ms.** Dylan approved bounded persistence after renewed live blinking. Reuse the last admitted box, clear overlapping replacements and suppression, and check capture and wall time again at publication. Measured movement raises the shared object/face drawing blend; face names still need exact-source recognition. Supersedes D147's immediate missing-object hide; E development focus gaps 111 to 102/675, unchanged small jitter, 40 px/frame lag 74 to zero.

**D160 2026-10-12: The 30 tok/s decode target is soft.** Dylan: the current 29.1 tok/s (J) is fine live, and conversation quality matters more. No work trades answer quality for decode speed; the quantization bake-off stopped before quality runs. Physical latency by loopback is parked for the same reason (latency feels good live); M4 still requires that measurement.

**D161 2026-10-12: A missed face continues a conversation on the same person track.** With a held face and no face on the speech-start frame, the conversation goes on only while the largest person track is the one seen with that face, within CONVERSATION_S; the turn keeps the previous visitor id so "forget me" still reaches it. A different face still ends it; identity answers still need a face. Refines D60/D70.

**D162 2026-10-12: Voice deletions ask first.** "Forget me" and "forget my X" resolve what to delete, then ask "Should I forget ...? Say yes or no."; only a yes from the same visitor within CONVERSATION_S deletes, and anything else is a normal turn. Memory-tab buttons stay immediate. A knowledge fact answers "What can you do?". Command set v2 stops here (Dylan: demo scope).

**D163 2026-10-12: "Is this the same thing?" is answered in code from held-object crops.** Each answered turn keeps the focused object's crops in RAM; a yes/no comparison scores them by DINOv2 MaxSim against every earlier held object of the same kind (UI setting `same`, 0.86, in-sample on 27 dev pairs: false same 0/15, false different 1/12, E), and answers name the earlier object. Different kinds get "No. Earlier you showed me ...". FileCamera stamps stills with the current time, so replays exercise the focus like a live camera. Dev replay 44/47 keyword, evidence 5/5 (J); `same-apples-2` now answers no.

**D164 2026-10-12: Retention keeps named-object evidence; "Ignore that" by voice; no place in the persona.** `Robot._retain` never evicts a named object's naming turns or its newest matched sighting, as D51 required (live: a phone named 30 h earlier had lost its last-seen time). A short "Ignore that" ignores the focused object through the camera card's code path. The persona says "built by Qdrant" and names no booth, because the robot runs in different settings (Dylan). Dev replay 44/47 keyword, evidence 5/5, first audio p50 1.47 s (J); the prompt change flipped bus-red-2 to pass and long-question-1 to a miss.

**D165 2026-10-12: The live chat clears only when a voice deletion runs.** `Turn.keep` controls storage only; `Turn.deleted` (a yes to a deletion question) or `hiding` clears the chat and the turn's retrieved statements. When the follow-up window closes, the chat shows "Conversation closed. Say "Hey Edgy" to talk again." (Dylan: otherwise the robot seems to ignore a returning visitor).

**D166 2026-10-12: End a line after 0.6 s of silence, not 0.35 s.** Dylan: real questions split at natural pauses, and the added delay is acceptable. On 47 of his recorded lines with inserted pauses (E), 0.6 s pauses split 80% at 0.35 s and 12% at 0.6 s, for about +270 ms per turn; Smart Turn v3.2 and a transcript word check were rejected (no separation, or a circular gain). Supersedes the 0.35 s value in D24/D38.

**D167 2026-10-12: Capture 1080p MJPG and scale to 1280x720.** The taught microphone's green box blinked because grain kept its detector score near the 0.25 start gate. Scaling 1080p down lifts its detected frames from about 62% (eight 720p clips) to 98%, longest gap one frame, for +0.33 CPU cores (J). Camera controls, temporal filters, YOLOE-26m, larger inputs, and tracker constants were rejected (lessons, Perception).

**D168 2026-10-12: Crop vectors use DINOv3 ViT-S/16 (DINOv3 License, Dylan approved).** Viewpoint benchmark recognized views at matched false matches: 257 to 456 (10 false), 534 to 607 (116 false) (E); `Crops` 17.2 vs 15.6 ms for one crop, +21 MB RSS (J). Thresholds sit at the DINOv2 operating points; the migration keeps visitor records and Ignore rules and deletes the old shard, so objects are re-taught. Supersedes D57/D64's encoder.

**D169 2026-10-12: Same-object answers compare by score, never by detector label.** Live, a taught white controller (labels "book", "camera") was compared with the corner keyboard. `Focus.target` prefers a held object over a focus that is not held; `_same_answer` scores every earlier hold and the visitor's named objects by MaxSim and says so when nothing is earlier; "am", "can", "still", and "one" mark comparison questions. A color veto was measured and parked (Dylan): DINOv3's shape bias also shows in recognition. Supersedes D163's label gate.

**D170 2026-10-12: Tracked objects decide whether the view changed.** A held object that moves keeps its track but changes the pixels, so the robot dropped its own answers every turn (D27). The view counts as changed when the set of non-person tracks differs; the pixel difference decides only when neither view has tracks. Settings files keep only values that differ from the defaults.

**D171 2026-10-15: Keep startup context small and the architecture stable.** Dylan: most remaining work is cleanup and refinement. CLAUDE.md keeps guardrails and targets; STATE.md keeps live status; research/lessons.md and research/README.md index detailed workflow, current architecture, and the complete experiment ledger. Load relevant sections on demand.


**D172 2026-10-15: Show retrieved evidence beside a Qdrant Edge search map.** Dylan requested a shared 70/30 retrieval panel beneath the camera, full-height conversation, and a cleaner Memory tab. A pinned command bubble rotates examples without headings or extra controls. The map shows displayed retrieval entries; preparation and speech-ready timers keep their measurement limits. Visitor IDs govern card groups, and confirmed forgetting invalidates cached cards. Refines D157 and D158.

**D173 2026-10-16: Show stored personal memories as stable points with real object links.** Dylan requested a centered `Say` tip, creation pulses, and colored recall. Bounded metadata snapshots use actual Edge IDs, source links, storage creation times, and separate recall IDs. The shared 70/30 panel and full-height conversation remain; this supersedes D172's search-flow map.

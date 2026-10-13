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

**H1 2026-10-11: Dylan authorizes a rotating camera head.** This supersedes D61's no-motor requirement for head yaw only. Concept A keeps the Jetson and one speaker in the stationary body, uses removable press-fit component installation, and reserves the owned 7.4 V STS3215; final fit, power, and motion remain U.

**H2 2026-10-11: Use the tapered neutral-white enclosure.** This supersedes H1 appearance only. A 22 mm base roll softens the body without increasing its envelope; separate rear and port covers preserve service access. The modeled envelope is 148.6 × 127.2 × 236 mm (E); physical retention, powered coupling, and cooling remain U.

**H3 2026-10-11: Use removable speaker and audio retaining keys.** Speaker service removes its key through the right opening. The flatter audio housing, tray, and key leave rearward as one module after the speaker key is removed. Jetson and camera clips await verified contact regions; printed retention and thermal behavior remain U.

**H4 2026-10-12: Use the simplified nine-part enclosure.** This supersedes H2 construction and H3. One shell prints on its roof over a base plate with loose pockets; a hub holds both bearings, and the servo drives the head shaft directly. Fasteners are M2 and M3 screws into nut pockets; camera on M2 screws (Dylan). Printability is scored by `hardware/printcheck.py`; physical fit remains U.

**H5 2026-10-13: Power the servo at 5 V from a Jetson USB-A port (Dylan).** A USB-A to 5.5 × 2.1 mm barrel cable feeds the SO-ARM100 bus servo adapter, the LeRobot setup for 7.4 V STS3215. This removes the servo regulator from H4. Software limits torque and acceleration; USB port current stays U until the first powered test.

**H6 2026-10-13: Route the camera cable through the neck gap (Dylan).** The cable leaves a hole in the rear of the head floor, crosses the neck gap behind the hub, and enters the body through a smooth roof hole to a Jetson USB port. A slack loop inside the body absorbs the ±80° turn. This replaces the external loop; Dylan chose it over a hollow shaft with gears.

# Intent and evidence testing plan

The parser hypothesis is refuted for the current development set: none of the eight recorded misses is an evidence-selection error ([recall.md](recall.md)). The owner and location requirements and the session designs remain current.

Keep the accepted Qwen runtime and test independent live, history, and knowledge selection before changing the prompt or model. Compare rules with similarity scores from the existing BGE question embedding. Consider a trained classifier only after those options fail unseen paraphrases. This session produces a plan and source audit only.

All proposed parser costs and quality gains are U. J means measured on our Jetson, E means measured elsewhere, and U means unverified. The accepted source is `011f522`; the protected deployed release is `7f67670fa91e`.

## What the current code does

`robot/route.py` votes over five neighboring example vectors and returns one category. `Robot._turn()` also uses separate past/now rules, statement retrieval, and deterministic answer paths. `sighting_query()` already handles some combined questions. The category router alone does not represent multiple evidence requirements.

The image reaches generation for current-sight questions or explicit present references. Past questions can retrieve observations. A combined question can receive both through existing rules, but the generated past instruction and earlier code answers can still suppress one part. Measure this behavior before assigning its cause to the router.

Identity, consent, teaching, deletion, and ignore remain code-owned. The parser selects evidence and describes references. It never authorizes a mutation or establishes object ownership.

## Earlier tests and limits

| Evidence | Recorded result | Consequence |
| --- | --- | --- |
| D21, tool-enabled Qwen3-VL-2B | Memory calls on 10/13 current-sight questions (J). | Model-driven routing failed this workload. |
| D21, tool-enabled Qwen3.5-2B | Memory calls on 12/13 current-sight questions (J). | A second small-model decode needs a changed hypothesis. |
| D21, code-retrieved Qwen3-VL-2B | Keyword checks passed 20/21 (J), including 13/13 sight questions. | Preserve code retrieval. These early heuristics do not establish judged acceptance. |
| D62 | Rules and embedding routing were proposed. The classification-prefix cost was recorded as 0.2–0.3 s (U historical estimate). | The proposed replacement was not implemented. Measure overhead against today's runtime. |
| D87, sufficient-source diagnostic | Judged answers improved from 14/24 to 21/24 (J). | Evidence sufficiency can raise quality. This forced-generation result is an upper bound. |
| D103, controlled retrieval | Judged answers improved from 22/32 to 30/32 (J). | Controlled evidence gains need integrated qualification. |
| D108, recorded-audio integration | Judged answers fell from 42/47 to 39/47; joint text/speech fell from 39 to 36 (J). | Reject the prior prototype. Routing, source quality, and integration are separate questions. |
| D113–D114, Granite source-role work | Two schema-valid proposals retained unsupported detail. Both corrected comparison arms scored 21/39 judged (J). | Valid structured output does not establish source use or answer quality. |

D21's Gemma sentence reports one memory call in four questions. The underlying `tool` fields contain zero calls in four questions. One of four passed the keyword check. Preserve the historical decision and use the raw-field distinction in future comparisons.

The early tool-enabled files contain 20 questions; the code-retrieved file contains 21. They lack independent judged sidecars. They support the routing warning, not a paired improvement estimate for today's product.

## Parser options

| Option | Work added after the existing embedding | Main tradeoff | Proposed order |
| --- | --- | --- | --- |
| Explicit temporal and reference rules | Small text checks. | Easy to inspect; paraphrases and negation scope can fail. | Include as the cheap baseline. |
| Independent similarity scores plus rules | Dot products against cached examples. | Reuses BGE; similarity is not calibrated probability. | Screen first against the accepted single-category router. |
| Multi-label linear classifier on BGE | A small weight matrix. Training runs on the Mac. | Needs labeled development data; handles source labels without extracting entity slots. | Use if similarity misses unseen phrasing. |
| SetFit or another fine-tuned encoder | A separate encoder pass, unless replacing BGE. | More training, runtime integration, and memory. Replacing BGE can also change retrieval vectors. | Defer until fixed BGE features fail. |
| Constrained JSON from the existing Qwen | Another generation pass before retrieval. | Rich slots, but extra decode and historical routing failures. Grammar constrains form. | Keep as a measured fallback. |
| Dedicated small intent LLM | Another model and inference path. | Adds residency and integration without established gains here. | Defer until cheaper options fail. |

Semantic Router supplies routing infrastructure, but this small in-process comparison can use existing NumPy operations. A library would still need the same multi-label, temporal, and uncertainty rules. Avoid adding a dependency before it supplies a measured benefit.

BGE-small has an MIT license. SetFit has an Apache-2.0 license; each encoder also needs its own license and revision check. The initial candidates reuse installed assets. This plan adds no quantization, export, model download, or inference runtime.

## Natural evidence selection

Use independent `live`, `history`, and `knowledge` requirements. Preserve the requested entity, temporal constraint, visitor scope, and any resolved reference. Resolve “it” only when the recent exchange supplies one clear object. An unresolved reference triggers a short question.

| Visitor asks | Required evidence | Expected distinction |
| --- | --- | --- |
| “What do you see right now?” | Live frame. | Describe the current scene. |
| “Where did you last see my phone?” | Latest verified named-phone sighting. | State the recorded place and time. |
| “Do you see my phone now, and where did you last see it?” | Live frame and named-phone history. | Answer both parts with separate time references. |
| “Is this the same phone I showed you before?” | Current crop and stored named-object evidence. | Verify the physical instance before claiming ownership. |
| “Where is my phone?” | Current verified match and latest recorded sighting. | Prefer a verified current match; otherwise report the last recorded observation. |
| “Does it need a server?” after a Qdrant Edge question | Knowledge and the clear prior subject. | Keep the room image out of the factual answer. |

Retrieving both sources can resolve an ordinary question without requiring a “camera or memory” mode choice. An unseen object does not prove absence. A stored sighting does not prove its current location. Negative instructions such as “Do not forget my phone” must never reach deletion.

## Requested location and owner payloads

Dylan requests a UI-set Location and an Owner for objects introduced by a named person. These fields are selected requirements for the future build. The UI implementation remains deferred.

| Payload | Stored value | Capture rule |
| --- | --- | --- |
| `location` | A nullable place label, such as “demo table”. | Copy the UI's active robot/camera location into each sighting at capture time. |
| `owner` | A nullable named-person key, such as “Ana”. | Bind the verified object introduction to the named speaker in that session. |

Store owner on the named-object record and its linked observations. A name explicitly given in the current conversation can establish the speaker. A previously enrolled person requires the existing verified identity path. This field adds no face enrollment or consent shortcut. Unknown, conflicting, or forgotten speaker identity leaves owner empty.

Location names where the robot observed the object. It does not establish the object's present location after it leaves view. Later UI location changes affect new observations. Earlier sightings retain their original location and capture time. A location change during a continuing track must preserve a new observation rather than overwrite the earlier place.

Resolve object references before retrieval. “My phone” selects the current speaker's verified object association. “Ana's phone” explicitly selects Ana's object. The answer says “your phone” when the current speaker matches the saved owner. It says “Ana's phone” to a different or unnamed speaker asking about Ana's object.

An unnamed visitor can retain an object association within the same verified introduction session. The robot can say “your phone” from that session evidence while the Owner payload stays empty. This association does not identify a later visitor or survive restart as a personal claim. Ask whose phone is meant when neither named identity nor verified session evidence resolves the reference.

Use owner and object label together when selecting a named object. Ana's phone and Dylan's phone must remain separate despite their shared label. The current object store keys records by name alone, so payload additions also require a reviewed lookup and storage change. Existing unowned records remain unowned. Do not assign them to the current visitor.

Existing visitor deletion must remove owner-linked retained evidence and named-object associations. Object deletion must affect only the selected owner's object. Retain restart and pending-write checks. Multiple people with the same name, and multiple same-name objects within one owner, require explicit ambiguity handling. D148's same-owner grouping policy remains undecided.

## Complete development sessions

These are seven proposed sessions with 30 spoken turns. They are development checks, not held-out acceptance. Start each session with a fresh isolated memory root. Keep the complete session history. Existing replay waits for answer playback, then its one-second reaction interval; preserve those waits.

### Similar teddy bears: four turns

| Step | Frame or action | Exact visitor line | Required answer or source |
| --- | --- | --- | --- |
| 1 | `images/m2-teddy-white.jpg` | “What is this?” | A white teddy bear with a red scarf and red hat. |
| 2 | `images/m2-teddy-brown.jpg` | “And what about this one?” | A brown teddy bear with a green hat. |
| 3 | `live/closet-night.jpg` | “Which teddy bear did I show you first?” | The first bear, from `m2-similar-teddy-1`. |
| 4 | Same room. | “What was the second bear wearing on its head?” | A green hat, from `m2-similar-teddy-2`. |

### Conversation eviction: six turns

Use `live/closet-night.jpg` throughout.

| Step | Exact visitor line | Required answer or source |
| --- | --- | --- |
| 1 | “My favorite color is green.” | Acknowledge the statement. |
| 2 | “Can you tell me a short joke?” | A short joke. |
| 3 | “How many legs does a spider have?” | Eight. |
| 4 | “What is two plus three?” | Five. |
| 5 | “What do you see right now?” | Describe the current room. |
| 6 | “What is my favorite color?” | Green, from `m2-evict-color-1`, outside the four-exchange window. |

### Forget and restart: five turns

| Step | Frame or action | Exact visitor line | Required answer or source |
| --- | --- | --- | --- |
| 1 | `images/m2-phone-gold.jpg` | “This is my phone.” | Confirm verified enrollment before testing deletion. |
| 2 | `live/closet-night.jpg` | “Forget my phone.” | Delete the named association and linked retained evidence. |
| 3 | Same room. | “Do you remember my phone?” | Report the forgotten association. |
| 4 | `images/m2-phone-gold.jpg` | “Is this my phone?” | Describe the phone without claiming saved ownership. |
| 5 | Show the room; restart with the same isolated memory. | “Where is my phone?” | The forgotten association remains unavailable. |

Verify deletion in storage, including images and pending writes. If teaching fails, record that failure. An empty store cannot prove successful deletion.

### Absent memory: one turn

Show `live/closet-night.jpg` with fresh memory. Ask “What did I show you yesterday?” Require uncertainty without an invented object.

### Seeded Qdrant memory: four turns

Load the shipped knowledge snapshot into an isolated knowledge directory. Seed these synthetic development statements through the ordinary statement-memory path. Record source IDs and timestamps. The facts describe the fixture project, Cedar.

| Proposed source ID | Exact stored statement |
| --- | --- |
| `cedar-name` | “Our Qdrant demo is called Cedar.” |
| `cedar-memory` | “Cedar remembers named object sightings.” |
| `cedar-runtime` | “Cedar runs locally on the Jetson using Qdrant Edge.” |
| `cedar-unrelated` | “The booth opens at noon.” |

Show the room throughout. These setup statements add no spoken test turns.

| Step | Exact visitor line | Required answer or source |
| --- | --- | --- |
| 1 | “What is Qdrant Edge?” | Use the shipped knowledge fact and record its actual point ID. |
| 2 | “Does it need a server?” | Resolve “it” to Qdrant Edge and use the shipped server fact. |
| 3 | “What does Cedar remember?” | Named object sightings, from `cedar-memory`. |
| 4 | “Where does Cedar run?” | Locally on the Jetson, from `cedar-runtime`. |

The unrelated booth statement must not displace the requested fact. Keep fixture facts in Qdrant Edge, outside the system prompt and scoring instructions.

### Named phone, current scene, and last sighting: six turns

Create a verified named gold-phone gallery in isolated storage with `owner: Ana`. Establish Ana as the named current speaker through the ordinary session/identity path. Prepare two linked sightings: `phone-workbench` at anchor time minus 20 minutes, and `phone-table` at anchor time minus five minutes. Capture their UI-set locations as “workbench” and “demo table”, with source provenance. Initially show `images/m2-phone-black.jpg`, a different physical phone.

| Step | Exact visitor line | Required answer or source |
| --- | --- | --- |
| 1 | “What do you see right now?” | Describe the current black phone. |
| 2 | “Do you see my phone now?” | Do not call the different phone the named gold phone. |
| 3 | “Where did you last see my phone?” | The demo table, from `phone-table`; distinguish last recorded from current. |
| 4 | “When did you last see my phone?” | The `phone-table` timestamp, including elapsed session time. |
| 5 | “Do you see my phone now, and where did you last see it?” | Current match uncertainty plus the last recorded demo-table sighting. |
| 6 | Show `images/m2-phone-gold.jpg`. “Is this the same phone I showed you before?” | Verify the crop against the stored gallery before claiming identity. |

The gold-phone return can create a newer sighting. Score its actual capture timestamp. Do not retain the older expected last-seen time after a verified resighting.

The accepted sighting payload has frame thirds and timestamps, but no semantic place field. Existing named-object answers also prioritize current matching over explicit past requests. These are prerequisites for full place/time recall. A parser-only result cannot claim to close them. Until place capture and evidence delivery exist, record the “where” steps as blocked or failed, never fabricate location text.

### Owner-aware references: four turns

Seed verified gold and black phone galleries under Ana and Dylan respectively. Give Ana's gold phone the last sighting `ana-phone-table`. Show Dylan's black phone at the UI-set “workbench” throughout. Establish each named speaker through the ordinary session/identity path before their turns. The seed and speaker state must stay outside the scoring prompt.

| Step | Named speaker | Exact visitor line | Required answer or source |
| --- | --- | --- | --- |
| 1 | Ana. | “Where is my phone?” | “Your phone” refers to Ana's gold phone, last seen at the demo table. |
| 2 | Ana. | “Where is Dylan's phone?” | “Dylan's phone” refers to the verified current black phone at the workbench. |
| 3 | Switch to Dylan. | “Where is Ana's phone?” | “Ana's phone” refers to the last gold-phone sighting, `ana-phone-table`. |
| 4 | Dylan. | “Where is my phone?” | “Your phone” refers to the verified current black phone. |

The owner fixture verifies reference binding and answer wording. It does not establish face-recognition accuracy. Add unknown-speaker, duplicate-name, and owner-specific deletion contrasts to the local routing/storage checks before integrated qualification.

## Efficient execution in a later session

Qualify location capture and owner-aware storage as a separate change before measuring parser gains on those sessions. Keep those fields identical in both parser arms. Record unsupported baseline capabilities explicitly. A gain from adding owner or location evidence counts toward that feature, rather than intent-parser quality.

1. Run the accepted baseline first. Freeze all question text, images, seeds, rubric, and source IDs before candidate testing.
2. Screen source selection on cached embeddings locally. Compare the accepted router, explicit rules, and independent similarity scores. Include temporal contrasts, combined questions, pronouns, negation, and unrelated questions.
3. Calibrate examples and thresholds on development data. Validate on separate unseen paraphrases. Keep final held-out fixtures sealed.
4. Add a linear multi-label head only if the simple candidates miss the required distinctions. Train on development data only.
5. Take at most one selected parser to the paired Jetson session comparison. Keep Qwen, SYSTEM, sampling, 2,048-token context, 256 image tokens, and 64 output tokens unchanged.
6. Run the 30-turn screen with both oracle transcripts and audio early. Use an existing recorded voice subset when available. Report synthetic and recorded inputs separately.
7. Inspect source selection, entity binding, action arguments, execution, answer correctness, and independently transcribed speech separately. Count code answers separately from generated answers.
8. Test evidence assembly as a separate intervention only when routing is correct and source sufficiency still fails. Preserve D109 authority and bounds.
9. Run existing full regression packets once after a judged gain with no capability loss. A development gain permits qualification, not adoption.

The proposed incremental parser budget is 5 ms p95 and 5 MiB additional resident memory after the existing embedding (U engineering limits). Report embedding time separately. Measure complete warm turns, cold startup, first token, first synthesis, decode, RAM, swap activity, detector rate, and tegrastats. Physical audible latency needs an acoustic measurement.

Require zero unintended mutations and zero false ownership claims in the screen. Both clauses of combined questions must pass. Preserve every failed answer, exact native exit, missing judgment, incomplete run, and failed setup. Do not retry quality failures unchanged. Final per-capability and sustained acceptance targets remain open.

## Isolation and unresolved prerequisites

Use the existing staging/run/collect workflow with an explicit experiment directory, named units, and `shared/gpu.lock`. Preserve current and previous release links. The existing replay convenience wrapper deploys implicitly; do not use it unchanged for this isolated comparison.

A fresh robot memory root alone is insufficient. `Knowledge()` defaults to shared production memory, and `brain.LOG` defaults to a shared server log. Future staging must isolate knowledge, statement/object stores, generated audio, caches, pending writes, and logs. Shared model files remain read-only. Keep private packets, transcripts, answers, and telemetry ignored.

Before execution, resolve real phone enrollment, location capture, owner-aware lookup, combined code-answer delivery, and current/history timestamp binding. Pin seed hashes and record test-clock behavior. Verify installed Edge stubs before any schema integration. Run the design gate before architecture or schema implementation. This plan authorizes neither runtime changes nor product adoption.

## Sources

- Local source: `robot/route.py`, `robot/main.py`, `robot/memory.py`, `robot/things.py`, `robot/knowledge.py`, and `robot/brain.py`, at accepted source `011f522`.
- Complete existing scripts: `eval/dev/m2.jsonl` and `eval/dev/sessions.jsonl`. Their original prompts remain unchanged.
- D21 raw files: `bench/results/2026-10-08-brain-qwen3vl-2b-text-1791432411.jsonl`, `2026-10-08-brain-qwen35-2b-text-1791432466.jsonl`, `2026-10-08-brain-gemma4-e2b-text-1791432356.jsonl`, and `2026-10-08-brain-qwen3vl-2b-text-1791433913.jsonl`.
- Historical integration: D87, D103, D108–D110, and D113–D114 in [DECISIONS.md](../DECISIONS.md). D110's detailed contract remains in the coordinator's `research/answer-path.md`.
- [Named-object reference](https://github.com/Dylancouzon/qdrant-edge-memory-robot), locally inspected at `cfc0dd2c5bb540f08149213c43bd33ba2d0c27f9`.
- [BGE-small model card](https://huggingface.co/BAAI/bge-small-en-v1.5) and [similarity operations](https://www.sbert.net/docs/package_reference/util/similarity.html).
- [Independent multi-label classifiers](https://scikit-learn.org/stable/modules/generated/sklearn.multiclass.OneVsRestClassifier.html).
- [SetFit multi-label guide](https://github.com/huggingface/setfit/blob/main/docs/source/en/how_to/multilabel.mdx), [SetFit paper](https://arxiv.org/abs/2209.11055), and [license](https://github.com/huggingface/setfit/blob/main/LICENSE).
- [llama.cpp grammar documentation](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md). Verify support in our pinned build before implementation.
- [Semantic Router source](https://github.com/aurelio-labs/semantic-router). A dependency offers no measured advantage in this plan.
- Two requested Luna researchers: `/root/intent_rules_embeddings` and `/root/intent_small_models`. Both used primary web sources after Firecrawl reported exhausted credits. Neither changed files or ran inference.

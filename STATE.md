# State

Updated 2026-10-10. D143 face delivery passes development qualification and passes Sol task review; the final metadata review also passes before the commit. Continue this overnight session after each checkpoint. Dylan authorizes incremental detection repair, recordings, external video, one implementation worker, and one read-only reviewer.

## Workspace and ownership

Work only in /Users/dylanc/orca/workspaces/qdrant-robot/mac-audio-interface, branch spike/mac-audio-interface. The root worktree holds private recordings and the shared Python environment. Read CLAUDE.md, research/lessons.md, research/mac-audio-interface.md, and D64, D131, D134-D143 before reopening alternatives. Lead owns STATE, DECISIONS, configuration, remote jobs, integration, audits, and git. One worker edits scoped code; the reviewer stays read-only. No nested agents. Repo autonomy supersedes global restrictions. Do not merge main.

Skills already applied: Orca CLI and qdrant-advisor. Official Edge0.8 docs/stubs verified; no query_batch. Firecrawl has zero credits. Use official direct-source/web fallback without new spending. Keep media, biometrics, transcripts, vectors, and private adapters ignored.

## User acceptance

Unknown ??? assignments change at most once per three seconds, including loss/reappearance. Known labels stay smooth through normal motion. Multiple vectors per Qdrant Edge point support viewpoint changes. Reject false object claims. Preserve consent, zero stranger identity claims, fresh source/write/action authority, true deletion, restart-safe Ignore/Restore, and rollback.

## Git checkpoints

D14081c66e2, D14169a6944, and D142564b612 are committed and pushed. D140 stabilizes unknown assignments/object labels and verifies exact-current Ignore crops; Restore works before the first frame. S motion84% to93.33%, restored75.33% to90.67%; moving Ignore fails. Idle controls pass all11checks/reset/reopen/cleanup. Fullchecks and Sol76875 PASS.

D141 keeps at most three diverse object vectors. Fresh exact-name MATCH permits merging; an existing-point mismatch stores the current crop alone. Preserve aliases/deletion links. Three actual below-SURE misses remove green; skips preserve continuity. Worker/peer78pass, Sol24860 PASS, fullhook native0. D142 adds at most one global Edge query using the existing vector after weak preferred matches. Strong aliases, budgets, authority, and duplicate abstention remain. Worker/peer86pass, Sol37425 PASS, fullhook native0.

Uncommitted D143 product paths: robot/{main,view,recognition,test_things,test_view,test_recognition}.py, bench/view_bench.py, tools/test_talk.py. Lead bookkeeping: STATE, DECISIONS, research/lessons.md, public D143 audit, Astra44892/2286/42741 verdicts, Sol87044/94180 verdicts. Commit accepted source only after final PASS and required hook. No private evidence enters git.

## Accepted D143 build

One completed positive/negative face record precedes crop work. Existing Condition wakes presentation; completed/active/latest ordering retains exact source pixels. View uses one15fps deadline for waiting, JPEG, retry, and pacing. Retry only changed selections. State is non-consuming. Existing View.lock makes final viewer validation/source commit/close atomic. Encoding/socket writes stay unlocked; canceled viewers exit promptly.

Selected B removes redundant preview_due initialization/reset/timer. Each already15Hz detector frame submits to the same serial recognition owner/latest replacement slot. Priority, crop3/s, models, thresholds, consent/deletion, source/session/gallery/gap/person/rendered epochs, monotonic and equal-source authority remain. Current-record pointer guard remains. No identity follows a moving track.

Frozen source a7bb11203aa9: mainSHA bfbfc587e6b71e6be878efc4bb95946b2bcfa776a367a8b27e4bec7493d8fd48; test_things af66a2db00931ab8460a37eb5097a21aebce92a96f5c61f46cd1bb67a1b9a2dc; View706eb81c and Recognitionc272471b unchanged from V4. Private v5-runtime.patch/code-sha/deployed-sha preserve26module hashes and29module/caller/original-adapter remote verification. Lead read every runtime/caller/test diff.

Worker88scoped tests pass55.19s/native0; peer10targeted pass4.47s/sourcePASS. Oldtimer restoration fails the new actualRobot/Recognition regression on the missed current frame. Twelve jittered15Hz sources retain priority, one latest slot, source/session/gallery, and crop3/s. Required fullchecks pass81.01s/native0, build/d140/d143-v5-fullchecks.log. Prior V4 worker112+41 and peer112 checks pass. Viewer cancellation mutation measured1007.61ms versus0.353ms fixed at1fps(E).

## Actual Jetson qualification

Original immutable adapter build/d140/d143_face_stream_check.py SHAe512e97a2b7a1833b8eae70233be59edac2b42018843446e96c0bdfd9e633ff6; protocol5972b8b60fbc8742d973e6bcdc0b8f5caad5df43a4d50b65f9724fa5cf6a64bc. Same N/floor120/person20s/phone14s/background14s/same joke/copied consenting memory/zero production writes. One actual authenticated production MJPEG subscriber pairs successful sends with received bodies FIFO. State stays non-consuming; QA uses actual received JPEGs at fixed offsets. Failure receipts precede bounded cleanup.

Candidate passes all23frozen checks/native0/completedTrue(J). Person259unique named captures versus180baseline,95.57%named fraction. Conversation133unique named captures/14.3156namedfps versus8.305baseline,96.38%fraction. All853sends received, pending0/errors0. Allphase source/detection cadence exceeds90%baseline; every200ms age/hold check passes. Worst receive197.763ms and held196.412ms. Background knownlabels0. Peer recomputes unique captures with zero duplicates, matching provenance, and all12QA hashes. Lead views correctly placed received face boxes. This is short development evidence, not broad acceptance.

Resources:76tegra rows, peakRAM6156/7485MB,58.5C, postactiveMemAvailable1.219GB(J). Startup+run paging40in606out. Full125svmstat excludes boot-average row; conversation8KiBin4out over10whole one-second intervals is system-wide, without process/isolated-turn attribution. No-paging remains unmet. Detection14.92–14.98fps does not meet sustained15floor.

Evidence: bench/results/2026-10-10-d143-face-delivery.json, private build/d140/stream-detector-n/{summary,samples,events,journal,qa,tegra}, v5patch/hashes/fullchecks and d143-detector-paging.txt. tools/results.py cannot parse custom aggregate detection JSON; compact exact fields.

## Rejected alternatives and learning

All four earlier D143 candidates fail fixed qualification. V1b993 person179 versus180, holds228/260/334ms. V2d62a person180=180, holds200.64/211.78/227.28ms. V37193 nonwaiting15 person171/conversation67/7.09namedfps, background212.87mshold/conversation200.486msreceive. V4d76a waiting15 person181/conversation86/9.57namedfps, but person202.91mshold/200.118msreceive andconversation305.76mshold. Preserve native1 receipts, source releases, patches, and all counsel decisions.

Astra42741 GO WITH CHANGES97.56s selects observational diagnosis after V3/V4 failures. Frozen wrapperf0126ff0/e512 on V4 produces2.757MB/zero drops/errors and687send/receive/guard joins, retaining native1 quality. Local guard/exception/fullHTTP accounting checks pass; overhead0.0455ms worker/0.0283ms peer(E). Temporary hooks ended with the process; wrapper remains ignored evidence.

Diagnostic finds one anonymous-background pointer rejection and no backward-source rejection, so guard removal has no measured known benefit. A fresh7.24ms-oldphone frame was skipped98.01ms after the owner finished89.32ms; next admission166.29ms produces212.293mshold. Warm ownerbusy52.4%person/49.7%conversation, p95service65.18/59.51ms andmedianqueue0.5ms support B. Person233.48ms/conversation81.17ms service tails remain. Prior305msgap did not recur and remains unexplained. Do not generalize snapshots or rejection counts into lost unique sources. D13915Hz failure used superseded publication; current completion-waiting architecture changes the comparison. No further planning gate preceded the smallest measured fix.

## Next command and running jobs

Sol87044 PASS163.17s/native0/tree00cc65bcdc23e50402c986fff31e8b8ea8cac0fd. No blockers; recorded source/23actualchecks/853receipts/259+133unique captures/all12QA verified. Its socket tests hit sandboxPermissionError; recorded nativechecks remain valid. Command tools/gate.py review --model gpt-6.1-sol with build/d140/d143-task-review-brief.txt. Log build/d140/d143-task-review-launch.log and reviews/20261010-054037-87044-review.md.log. Runtime is frozen. Optional benchmetadata fixed: removedinitialfps_cap10 andrecordsconstructedview.fps withunchangedphase/order. BenchSHA477584ac1865bfec9ed6b12ad1878258336f621c6df285d99613ebd8c8dd72aa; Ruff/AST/whitespace pass, all26runtime/testhashes equalacceptedB. Leadreadtwo-line delta. Final Sol94180 PASS120.76s/native0/treea841e046c80ad84fbcaffe3de6c02ef05c0f6523, session66914 finished. Verdict reviews/20261010-054647-94180-review.md, launchlog build/d140/d143-metadata-review-launch.log. Nextcommand: stage intended source/audit/verdicts, review index, required hook commit, push, then nextphonegap. Continue the phone gap after D143 is reviewed and committed.

Jetson currenta7bb11203aa9, previous67330062799b fallback. No owned GPU jobs. qr-d143-stream-detector-n completednative0, formerPID393426/invocation0faf5d8d47dd4dd2a792d175133bb2b3/start05:34:10EDT; shared/sessions/d143-stream-detector-n-20261010 and shared/results/d143-stream-detector-n-20261010-053410.tegrastats. Fullchecks63278, deploy40156, collect97366, vmstat68946 finished. Diagnostic qr-d143-stream-trace-n terminalnative1, invocation72c7b9f6133b4d7bb5d0368bbf0842c6; private stream-trace-n and completedvmstat72391 preserved. GPU jobs/deploys use only tools/jetson.py with gpu.lock/named units/tegra. Narrow collection avoids full shards/raw media.

## Next detection gaps

Default N cannot naturally bind the held phone. S remains unadopted: D142 movement92.67% passes, but named Ignore target is unavailable at fixed1.6s return due duplicate old-phone/face/new-phone tracks. Keep safe duplicate abstention and measure continuous recovery. Floor120 excludes109–119px phones. Queued Ignore can expire behind caption work. Do not relax action freshness or tune one scene. Existing corrected private runtime adapter d141_runtime_check.py SHAd88a13ae fails honestly; original emptyStopIteration false-native0 is audited failure. Public D141/D142 receipts preserve outcomes.

Independent Objectron cup/batch-5/3 descriptor comparison: cup92/142 allarms, phone7/15replacement,10/15three,11/15six. Threecap is selected. Zero same-kindphone negatives are admitted: the blackphone fixture is an audio recorder, and goldphone misses confidence0.2012. Cup top-down enrollment, true distinct-phone false positives, and model/floor/control qualification remain open. Annotation category/timestamps are wrong; verified indexed geometry is authoritative. Protocol740a05d7/adaptercdc617ef and media/license/QA stay private. Temporary Edge collection costs2.1GB; collect narrowly.

## Protected machine state

Jetson alias robot, boot09b4bb27-f975-441c-9d00-7af446ec7de6, about95GB free. Preserve rejected d76a,7193,d62a,b993 and prior eb6da2f9f1fd,3a3f7f93181e,cc8b526812e5,08ff2193ddc7. Production shards remain untouched. Closed224-file backup shared/backups/2026-10-10-before-d140.tar.gz SHAbf4ff898131cad2ae1ac0b5af1fc2a40061d3f07ece8f40c42f91a3bc0b267f1 retained.

Owned live/audio stopped. Macpreview15522 Idle/mic-off8765 expectscc8b; reconcile release before originalChrome1202942045 browser handoff. Other session owns WSL p2-trt-quantize-native-retry.service invocationb9ec1e261ba04407938c9be35eec3f1d PID128539, gpu.lock, Docker/Ollama, Orcaautomation8acb5818-1970-4f5f-9a6f-b3af454595e3. Leave them alone. Owned caffeinate65618 and unrelated36781 remain. Claude/Codex auth pass; usage unavailable. Hooks tools/githooks. Python3.12 via ignored .venv symlink. Jetson lacks rg; use grep remotely.

## Open final targets

Physical audible1.2s p50/2.0s p95,90%correct per capability with zero stranger identities,30tok/s decode,15fps sustained detection while talking, Edge10ms p99 at acceptance scale,500MB minimum headroom aiming1GB, and no turn paging remain unmet. M4 offline cold start, persistence/deletion, held-out acceptance, and eight-hour active run remain open. Continue the next measured detection gap after each accepted task.

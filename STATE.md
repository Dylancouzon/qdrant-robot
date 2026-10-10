# State

Updated 2026-10-10. D140 is active: rebuild smooth detection and recognition after Dylan rejected D139 live behavior. Dylan authorizes overnight work, one implementation worker, an independent reviewer, recordings, and a fresh external video after decent results. Prior pause and no-full-suite restrictions are superseded by this task.

## Active task and acceptance

Work in /Users/dylanc/orca/workspaces/qdrant-robot/mac-audio-interface, branch spike/mac-audio-interface, starting 30639f5 (product 609b425). Initial tree is clean. Preserve prior learning and failed evidence; delete replaced runtime paths. No main merge yet.

The ??? target changes at most once per three seconds, including loss/reappearance. Known object labels remain stable through ordinary motion and brief weak detections. Store distinct views as several vectors per Qdrant Edge point. Reject ambiguous and false object matches. Keep consent, fresh identity checks, real deletion, persistent Ignore/Restore, and source-linked writes.

Run paired recordings on Jetson, the existing phone teaching/motion/Ignore/reset/Restore adapter, person/background/conversation replay, targeted checks, then independent review. Add one external video after existing results improve. Require measured coverage, name continuity, focus transitions, false claims, frame age/cadence, RAM, swap, and resource logs. Preserve failures; do not substitute heuristic or native exit for quality.

## Ownership and changed paths

Lead owns status, decisions, configuration, deployment, services, acceptance, and commits. One builder owns scoped runtime/tests; reviewer is read-only. No nested agents. Read D64 and D134-D140 before reopening alternatives.

First checkpoint changes robot/{focus,main,test_focus,test_things}.py and current-policy fixtures test_{people,sightings,speak}.py. .gitignore ignores the .venv symlink. Lead read every diff. Sol41450 FIX led to exact current-crop Ignore verification; Sol53747 PASS approved that repair. Sol63548 PASS approved Restore before first post-reset frame. Final Sol76875 PASS239.84s/native0/treee314513d approves frozen test-only repairs. Full deterministic checks pass native0/45.37s; independent peer36pass/1preexisting skip29.96s. No threshold/model changes. First checkpoint is ready to commit with required hook checks.

## Machines and jobs

Jetson alias robot; boot09b4bb27-f975-441c-9d00-7af446ec7de6. Current repaired prototype3a3f7f93181e; retain fallbackcc8b526812e5,08ff2193ddc7 and prototypec3266cb71ba9. Owned qr-d140-ignore-idle stopped after Restore focusNone killed_worker and cleanup hung. Invocationbf2eb12b363e4b16bfe6f806583461b1,start02:19:57EDT,releasea049ed8b85cf. No completionfooter, interruptedcleanup. Journal build/d140/ignore-current/idle-failed-journal.log and tegrastats preserved. No active qr/model jobs or llama-server after owned stop. Owned live session and audio worker are stopped. Mac preview serverPID15522 remains Idle/mic-off on8765 and expectscc8b; reconcile its release before restarting. Closed production224-file backup shared/backups/2026-10-10-before-d140.tar.gz SHAbf4ff898131cad2ae1ac0b5af1fc2a40061d3f07ece8f40c42f91a3bc0b267f1 is retained.96GB free. Use tools/jetson.py deploy/run/collect/rollback, named units, shared/gpu.lock, and tegrastats.

Recordings remain private at root /Users/dylanc/Documents/GitHub/qdrant-robot/build/p2/recordings and remote shared/sessions: d136-background (300 frames), d136-person (450), d139-iphone-moving (225), upright1280x720/15fps. Reuse d139_runtime_check.py and d139_face_pair_check.py, corrected hold-then-continuation. Temporary memories only. Production backup224 files and D139 replay-altered shards are preserved; do not restore stale shards over later user actions.

WSL completion-only watcher is separate. SSH dylan@192.168.1.74 reports same active p2-trt-quantize-native-retry.service invocation b9ec1e261ba04407938c9be35eec3f1d, MainPID128539, provisional Result success/ExecMainStatus0. Preserve quantizer, gpu.lock, Docker/Ollama, and automation8acb5818-1970-4f5f-9a6f-b3af454595e3. Another session owns exports/engines.

Owned caffeinate65618 remains active; do not stop. Claude/Codex authentication pass; remaining usage unavailable. Hooks tools/githooks. Mac Python3.12: /Users/dylanc/Documents/GitHub/qdrant-robot/.venv/bin/python. Use this interpreter through ignored branch .venv symlink.

## Evidence and limits

Prior scoped D139 PASS approves only repairs that Dylan now rejects in live use. Phone N/S paired runs fail; face delivery prototypes fail cadence. Prior exact receipts and rejected releases remain in D139 records. tools/results.py cannot read legacy re-ID format; inspect its exact summary. Firecrawl has no credits; use direct official skill fetch and web fallback without new spending.

All final targets remain open: audible1.2s p50/2.0s p95; correctness90% per capability, zero stranger identity claims; decode30tok/s; detection15fps while talking; Edge10ms p99;500MB headroom, aim1GB, no turn paging; M4 offline/restart/deletion/eight-hour active run.

## Paired recording job

Baseline source cc8b526812e5 uses existing larger S detector through unchanged adapter, to isolate focus/name changes from model coverage. Command: .venv/bin/python tools/jetson.py run d140-baseline-s -- /home/qdrant/qdrant-robot/shared/sessions/d139_runtime_check.py --model s --learning. Completed baseline native1; physical teaching/Ignore/Restore persistence pass, motion84%, restored75.33%, Ignore-hidden42/47 and45/50 fail. Collected ignored build/d140/baseline-s and public bench/results/2026-10-10-d140-detection.json. Unit qr-d140-baseline-s; release current cc8b; log journalctl -u qr-d140-baseline-s and shared/results/d140-baseline-s-*.tegrastats. Adapter writes private shared/sessions/d139-runtime-d140-baseline-s-* with temporary memories only. Estimate below100MB disk, progress samples/events and journal, duration about3minutes. On stall inspect owned unit/journal before one infrastructure retry; stop only that owned unit if stalled. No quality retry. Lead will collect narrow private outputs after terminal exit.

First candidate c3266cb71ba9 and failed-control a049ed8b85cf remain retained; repaired 3a3f7f93181e is current; cc8b526812e5 fallback is preserved. Completed qr-d140-hysteresis-s invocation2d43cbf21819487bbe84868485ba98f1, start02:04:49EDT, native1 qualityfailure. Motion93.33%, Restore90.67% pass, Ignore-return/reset fail. Sol41450 review completed210.83s/FIX: normal.9 detection plus retained name lets Ignore reuse prior saved descriptors after actualqueryscore0. Worker fixes fresh selected-crop authority, then reviewer retests. Completed qr-d140-ignore-current on a049ed8b85cf, invocation6d24dae12ae74bd2be46f945460f3dfb, started02:16:06EDT, native1: physical teaching passes but Ignore expires84us before embedding; prototype remains unadopted.

## External recording

After the first paired gain, select official Objectron cup/batch-5/3, first test-index video absent the prior eight cup IDs. URL https://storage.googleapis.com/objectron/videos/cup/batch-5/3/video.MOV, immutable generation1603947585755153,26,382,374 bytes. Computational use licenseC-UDA1.0 saved privately. Downloaded native0 and decoded five samples. Frozen build/d140/external/video.MOV SHA49748f1c5065c91665d64585723fc44e24ce35dfe2b4c688708a8a7a2cb19d74; manifest.json records360frames/30.004fps, autorotated1440x1920, OpenCV5.0.0 and source generation. Participant/physical-object IDs unavailable; video-ID split only. Estimate26MB raw plus100MB derivative/output; progress curl bytes, stalled recovery preservespartial and retries one diagnosed infrastructure error. Derived1280x720/30fps/360frame MJPG cup-batch-5-3.avi SHAf5cfd0249df4e1d8bc96d8148178f53e308173c444dd416e7a6d740a1f76e17a preserves one-to-one raw frame indices with orientation90,0.375scale and370px black pillarboxes; rawPTS unmeasured. Annotation protobuf/source schema saved privately. Full source and frame/decoder mapping are frozen before recognition measurements; no model tuning on this independentvideo.

## Next command

Stage reviewed source/tests, learning, aggregate receipts, and four review verdicts. Commit: VIRTUAL_ENV=/Users/dylanc/Documents/GitHub/qdrant-robot/.venv ORT_DISABLE_TELEMETRY=1 git commit -m 'Stabilize object labels and verify current Ignore crops' -m 'Co-Authored-By: Codex <noreply@openai.com>'. Push only spike/mac-audio-interface after hook PASS. First attempted commit created nothing because five obsolete fixtures failed; faithful repairs now pass every required check.

No source/gate/Jetson jobs run. Worker and reviewer are idle. Next incremental task: bounded diverse views from explicit same-name reteaching, with false-positive and independent external-cup measurements. Run a selected design gate before changing gallery semantics. Existing Things.name replaces three nearby views; existing runtime adapter is phone-specific and bench/reid fixes eight old cup IDs, so neither measures independent cup viewpoint coverage. Use a narrow derivative of existing adapters for that missing measurement. Carry moving Ignore, queued controls after teaching, source-face blinking, detector coverage, and paging gaps. Keep N default until S qualifies. Production memories remain untouched.

# WSL completion receipt, 2026-10-10

The exact D119 retry is terminal. Historical journals match boot `5f4af7d6-879e-48eb-979a-45e715f1d626`, unit `p2-trt-quantize-native-retry.service`, and invocation `b9ec1e261ba04407938c9be35eec3f1d`.

The process logged a saved checkpoint at 05:55:39.849602 EDT. Systemd recorded terminal resource accounting at 05:57:52.220730 EDT. Historical native Result, ExecMainCode, ExecMainStatus, and exit timestamp are unavailable. The collected unit's default success/zero fields do not establish native success. `job_final_exit` records `unavailable`.

Completed source/log flow implies 128 activation batches and 128 search batches, with zero NaN skip warnings. Final local counters were not captured. The last direct counter was 67/128 with zero skips. One resmooth workaround warning concerns layers. Checkpoint tensor finiteness, loading, downstream export, engines, inference, and Jetson qualification remain U.

The checkpoint contains eight files totaling 8,247,602,428 bytes. Streaming SHA256 and stable file metadata cover every file. `model.safetensors` contains 8,215,397,598 bytes; SHA256 is `e8f3d7a40d07df8dc278bd0af7c022b072570fb7874464761468e5535a7b66d4`. WSL unit lifetime peaks were 19,361,898,496 RAM bytes and 107,425,792 swap bytes (E).

[The status receipt](2026-10-09-wsl-d136-status.json) contains the complete inventory, hashes, provenance, counts, limits, and native-status evidence. Original logs, full invocation journals, installed source, and selected receipts remain private in root ignored `build/p2/logs/wsl-completion-20261010`.

The protected UI has active D144 work and overlapping record edits. WSL changes remain narrowly scoped and unstaged there. Caffeinate 65618 remains because that work retains it. The completed automation is removed, with its result history preserved. Records received JSON and whitespace validation; no tests or review gate ran.

Dylan will start another session for subsequent export, engines, and Jetson qualification. This completion-only session stops after this handoff.

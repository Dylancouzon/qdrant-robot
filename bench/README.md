# Exploratory benchmark map

These scripts preserve reproducible experiments. They do not replace [acceptance](../eval/README.md). Use the [lessons index](../research/lessons.md) before reopening an approach. Run Jetson jobs through `tools/jetson.py`; keep private inputs and scratch work ignored.

| Question | Scripts |
| --- | --- |
| Brain evidence use, conversation, and prefix reuse | [brain_bakeoff.py](brain_bakeoff.py), [conversation.py](conversation.py), [prefix_cache.py](prefix_cache.py) |
| Speech input, pauses, and microphone loopback | [asr_bench.py](asr_bench.py), [endpoint_arms.py](endpoint_arms.py), [mic_loopback.py](mic_loopback.py) |
| Speech output and generation contention | [tts_bench.py](tts_bench.py), [tts_contention.py](tts_contention.py), [first_phrase.py](first_phrase.py) |
| Edge latency and retrieval thresholds | [edge_bench.py](edge_bench.py), [calibrate_retrieval.py](calibrate_retrieval.py) |
| Crop encoders, gallery policies, and recognition | [embed_arms.py](embed_arms.py), [gallery.py](gallery.py), [reid.py](reid.py), [crop_arms.py](crop_arms.py), [crop_cost.py](crop_cost.py) |
| Same-object and color comparisons | [same_pairs.py](same_pairs.py), [color_pairs.py](color_pairs.py) |
| Camera quality, detections, and recorded sightings | [camera_settings.py](camera_settings.py), [detect_stability.py](detect_stability.py), [clip_sightings.py](clip_sightings.py) |
| Focus, overlays, and live delivery | [focus_clip.py](focus_clip.py), [overlay.py](overlay.py), [view_bench.py](view_bench.py), [view_lag.py](view_lag.py) |
| Active visitor and bounded head movement | [head_sim.py](head_sim.py) uses real models and simulated yaw; [servo_runtime.py](servo_runtime.py) qualifies the loose USB servo. |
| Face models and consented identity | [faces_bakeoff.py](faces_bakeoff.py), [people_bench.py](people_bench.py) |
| Component RAM, idle soak, and worker failures | [memory_budget.py](memory_budget.py), [soak.py](soak.py), [worker_failure.py](worker_failure.py) |

[Saved results](results/README.md) retain measurements. [judge-cache.jsonl](judge-cache.jsonl) holds cached verdicts. Script names describe experiments; dated results establish which model, input, and release were measured. In particular, old crop-cost records can refer to DINOv2 even though DINOv3 is current.

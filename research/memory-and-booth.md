# Robot memory designs and booth lessons

As of 2026-10-07.

## Summary

- Open LLMs fail at time arithmetic over memories. In ReMEmbR (robot navigation memory), open models scored 0.11 to 0.36 on descriptive questions against 0.58 to 0.65 for GPT-4o, with temporal errors of 4.5 to 18.7 s. Test temporal handling; do not assume current small models fail the same way. Resolve "at 2 pm", "last", and "first" in code with filters and `OrderBy`, not in the model.
- Duplicate memories dilute retrieval. Gate writes on change (compare to the last stored frame, not the previous frame) and deduplicate on write.
- Retrieval should return evidence (the frame, the time) with every answer, and say "not found" when the top score is low.
- Booth Wi-Fi fails under crowds. The demo must not need it. A visible "Wi-Fi off" moment proves the point.
- Rehearse a demo until it succeeds three times in a row; freeze code before the event.
- Faces are special-category data under GDPR. Giving a name is not informed consent: ask explicitly before storing a face, offer "forget me" (delete by filter, show the count), show signage, keep no audio. Get Qdrant legal review before an EU event.

## Reference design: reachy-edge-memory (read-only in `refs/`)

- Three shards: `memory` (conversation that left the LLM context, bge-small vectors; frames with a SigLIP 2 vector plus a text vector), `people` (one point per person, face shots as a multivector, MaxSim), `knowledge` (facts with several question phrasings as a multivector, shipped as a snapshot).
- The LLM reaches old conversation only through a `remember` tool.
- Frames are stored when the objects in view change or when asked to look.
- Models (all on a laptop over HTTP): Gemma 4 E2B (LiteRT), Whisper (laptop) or Moonshine-tiny (robot), SigLIP 2, bge-small, YOLO26n, YuNet, HSFace, Inflect-Nano TTS. About 11,000 lines of Python.

## Booth hardware lessons

- ReSpeaker XVF3800 USB: 4 mics, DOA, beamforming, echo cancellation; works over USB on Linux; DOA readable with pyusb (VID 0x2886, PID 0x001A). Far-field still degrades in loud halls.
- Close-talk mic about 10 cm from the mouth gave the best results in a mobile voice-control study.
- Show the robot's memory on a separate screen; serve it as a web page from the headless Jetson.

## Sources

- https://arxiv.org/html/2409.13682v1 (ReMEmbR)
- https://arxiv.org/html/2602.09255v2 (OmniMem)
- https://generalrobots.substack.com/p/nailing-the-demo
- https://wiki.seeedstudio.com/respeaker_xvf3800_python_sdk/
- https://www.edpb.europa.eu/sites/default/files/files/file1/edpb_guidelines_201903_video_devices_en_0.pdf
- https://ipvm.com/reports/ico-conference

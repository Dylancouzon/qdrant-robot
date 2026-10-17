# Settled architecture

The robot sees, listens, talks, and remembers on one Jetson Orin Nano Super 8 GB. It is a conference-booth showcase. Qdrant Edge stores memory inside the robot process. Keep this architecture stable during cleanup. Reopen a choice for a measured failure or Dylan's request.

## Runtime


`DECISIONS.md` lists every binding choice. In short: Qwen3-VL-2B on llama.cpp with retrieval in code and code-owned actions and identity; YOLOE-26s TensorRT with tracking; DINOv3-small named-object multivectors; YuNet and w600k_r50 faces; Silero VAD, Parakeet int8, and Kokoro on CUDA with a first-phrase decode pause; 2,048-token context, 256 image tokens, and 64 output tokens. Generated captions retain their source evidence; a generated statement alone never counts as an observed fact. Use the current implementation for refinement and regression work.

## Visitor behavior


Raise the capability ceiling for perception, sustained conversation, useful retrieval, and fluid interaction on one 8 GB Jetson (D76). Qdrant Edge is central to how the assistant remembers and uses evidence.

| Visitor says | Answered from |
| --- | --- |
| "What do you see?" | The camera, now |
| "What did I show you?", "Where is my phone?" | Stored captions, detector sightings, and named-object crop vectors |
| "What did we talk about?" | The conversation window and retrieved statements from Qdrant Edge |
| "Do you remember me?" | Face match against people (one point per person, face shots as a multivector, MaxSim) |
| "What is Qdrant Edge?" | A knowledge shard that ships as a snapshot (facts with question phrasings as a multivector) |

Priority when goals conflict: good answers, then fast answers, then camera fps, then search latency. Give the generative model as much memory as the rest allows. [Head control](servo.md) shares one active visitor with conversation and ownership. Finite-speed simulation passes the functional scenario. The serial runtime uses explicit mounted calibration. Watched ±60° travel at 40°/s passed; transient temperature feedback and prolonged loaded power remain open. A Wikipedia shard is an add-on after M4.

## Hardware and machines


- **Robot:** Jetson Orin Nano Super 8 GB, NVMe, USB camera (Arducam IMX291, about 100°), and a USB speaker with microphone (ALSA card `Device`, connected 2026-10-10). Never run the course robot's hotspot setup over the active Wi-Fi link.
- **Allowed additions:** anything the Jetson drives over USB, I2C, SPI, or GPIO. D175 and D176 implement shared visitor selection and bounded head control. The STS3215 runtime and loose-servo helper share one checked transport. Arms remain outside scope.
- **Mac:** development, tests, data preparation, and training. **WSL 3080 box:** bake-offs and heavy preparation. Build Jetson engines on the Jetson; measure every acceptance number on the Jetson.
- Access details and pitfalls are in [the machine notes](experiment-ledger.md#machines).

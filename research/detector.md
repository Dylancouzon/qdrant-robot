# Detector and tracker (M2.D spike)

Development default updated 2026-10-10 (D146). Historical tables below were measured on 2026-10-08 with nano models (MAXN_SUPER where marked, otherwise 15W; TensorRT 10.16.2, onnxruntime-gpu 1.24.0). Labels: J measured here, E measured elsewhere, U unverified. Raw historical results: `bench/results/2026-10-08-detect-*.jsonl` and `detect-*.tegrastats`.

## Summary

- Default: YOLOE-26s with the same fixed 50-word booth vocabulary, end-to-end export at 384x640, and TensorRT FP16 backend (`robot/detect.py`). It supplies the proposal needed to teach the held phone, which nano misses. D145 reaches 91.51% named phone movement and 92.46% Restore coverage. (J) Keep YOLOE-26n as the fallback.
- Scope: [D146's phone replay](../bench/results/2026-10-10-d146-detector-default.json) passes all 12 checks, with 91.43% named movement coverage and 91.47% Restore coverage. Conversation face naming is 88.10%, with a 453.8 ms held-source interval; smoothness and paging remain open. The external cup reaches 73.78% across changed viewpoints, with zero wrong cup overlays. These development results establish no general detection or distinct-instance false-positive acceptance. (J)
- Backend: raw TensorRT (A) over onnxruntime with the TensorRT provider (B). Same speed, 340 MB less RAM, and no six-minute engine build inside the robot process. (J)
- MAXN_SUPER: at 15 fps with llama-server decoding, the detector keeps 15.0 fps and LLM decode drops from 34.6 to 31.7 tok/s (8%), above the 30 tok/s target. At 15W the drop was 23.2 to 20.6 (11%). Unthrottled at 15W, decode halved (23.3 to 11.9). Run detection at camera rate, never flat out. (J)
- YOLOE prompt-free (4,585 built-in tags) is rejected: scene tags ("laundry room", "biology laboratory") outrank the objects, it misses the teddy bears and apples in our closet frames, and it costs 18.6 ms of GPU per frame. (J)
- Live camera (15W): capture 15.2 fps, detection and tracking 15.0 fps (every frame), 8.5 ms p50 per frame, 29 sightings in 30 s of a static lit scene. (J) After the MAXN_SUPER reboot, OpenCV cannot open `/dev/video0` ("can't be used to capture by name"), while `v4l2-ctl` streams 1280x720 MJPG at 26.7 fps: no live run in MAXN_SUPER yet.

## Backends (YOLO26n 384x640, 9 camera frames 1280x720 cycled, 30 s, alone on the GPU)

| Backend | Precision | fps | Detect p50 / p99 (incl. pre and post) | MemAvailable drop | Label |
| --- | --- | --- | --- | --- | --- |
| (A) TensorRT engine, Python API, libcudart buffers | FP16 | 128.6 | 7.15 / 7.77 ms | 195 MB | J |
| (B) ORT TensorRT provider, engine cached | FP16 | 130.9 | 7.03 / 7.56 ms | 535 MB | J |
| (B) ORT TensorRT provider, first run (builds in process, 382 s) | FP16 | 129.2 | 7.10 / 7.64 ms | 1,538 MB | J |
| (B) ORT CUDA provider | FP32 | 55.9 | 17.26 / 18.17 ms | 614 MB | J |

trtexec GPU compute per frame: YOLO26n 4.33 ms, YOLOE-26n booth 5.07 ms, YOLOE-26n prompt-free 18.6 ms. (J) INT8 (C) was not needed: FP16 runs more than seven times faster than the 15 fps target.

## Models (TensorRT FP16, 384x640)

| Model | fps alone | Detect p50 | 15 fps with LLM: detect p50, LLM tok/s | Label |
| --- | --- | --- | --- | --- |
| YOLO26n (COCO-80) | 128.6 | 7.15 ms | 13.0 ms, 20.9 (from 23.2) | J |
| YOLOE-26n booth vocabulary | 114.2 | 7.92 ms | 13.9 ms, 20.6 (from 23.2) | J |
| YOLOE-26n prompt-free | 13.1 (tracker-bound) | 23.2 ms | not run | J |
| YOLO26n, MAXN_SUPER | 146.4 | 6.09 ms | 12.2 ms, 32.2 (from 34.5) | J |
| YOLOE-26n booth vocabulary, MAXN_SUPER | 130.8 | 6.74 ms | 12.8 ms, 31.7 (from 34.6) | J |

Rows without a mode are 15W. MAXN_SUPER runs: peak tj 66.3 °C, RAM peak 3,233 MB, no swap growth (`detect-super.tegrastats`).

The tracker takes 0.6 to 0.8 ms p50. With prompt-free, 300 detections a frame push it to 52 ms. Tracking adds no GPU work.

## Labels on fixture frames (score 0.25 or more, top six)

| Frame | YOLO26n | YOLOE booth | YOLOE prompt-free |
| --- | --- | --- | --- |
| closet-stopsign-center (photo held up) | stop sign 0.95 | stop sign 0.84, bottle, sign, chair | stop sign 0.84, megaphone, electric chair, chessboard |
| closet-teddy-center | teddy bear 0.80, 0.77, keyboard | teddy bear 0.86, 0.83, plush toy 0.63, bottle | laundry room, biology laboratory, laundromat (no teddy) |
| closet-apples-center | apple x4 | apple x3, bottle, keyboard | biology laboratory, laundry room (no apple) |
| closet-cat-center | cat 0.71 | cat 0.75, dog 0.61, bottle | cat 0.75, animal, electric chair |
| closet-moto-center (chopper trike photo) | nothing | bottle, bicycle 0.43 | biology laboratory, chemistry lab |
| closet-night (no shown object) | nothing | bottle 0.58, keyboard, chair: all real objects in the room | server room, cowbell, caldron |

On the 25 COCO frames, YOLO26n and YOLOE booth agree on people, cars, apples, cats, teddy bears, and stop signs; YOLOE booth has no bus, zebra, or airplane because they are not in its vocabulary. (J) Every frame: `labels` in the JSONL results.

Gotcha: an FP16 engine rounds the class index for vocabularies over 2,048 classes (prompt-free returned "humidifier" for person). Keep `/model.23/Cast` and `/model.23/Concat_5` in FP32 (`--precisionConstraints=obey --layerPrecisions=... --layerOutputTypes=...`) if a large vocabulary ever returns. The first prompt-free result file (`...yoloe-pf-tensorrt-1791461221`) has this bug. (J)

## Default export recipe (Mac; the Jetson has no sm_87 torch)

Use the pinned S checkpoint from `models.json`. Run `python -m tools.models detector/yoloe-26s-seg.pt` before export. Its source is [Ultralytics assets v8.4.0](https://github.com/ultralytics/assets/releases/download/v8.4.0/yoloe-26s-seg.pt). The Mac-only text encoder `mobileclip2_b.ts` comes from the same release; its checksum is recorded below. Put both files in a scratch directory.

The recorded D139 export used Python 3.12.13, Ultralytics 8.4.174, torch 2.14.1, torchvision 0.29.1, ONNX 1.23.2, onnxslim 0.1.98, and opset 18. CLIP resolved to commit `7ffa84b3bfa40c42ecc1c77147a855e69cb2dd40`. Pin these export dependencies:

```sh
uv run --no-project --python 3.12.13 \
  --with ultralytics==8.4.174 --with torch==2.14.1 --with torchvision==0.29.1 \
  --with onnx==1.23.2 --with onnxslim==0.1.98 \
  --with 'clip @ git+https://github.com/ultralytics/CLIP.git@7ffa84b3bfa40c42ecc1c77147a855e69cb2dd40' \
  python export.py
```

In `export.py`, use the ordered VOCAB from the historical recipe below:

```python
from pathlib import Path
from ultralytics import YOLO

VOCAB = "person,face,badge,lanyard,sticker,plush toy,teddy bear,mug,cup,bottle,phone,laptop,keyboard,computer mouse,headphones,backpack,bag,hat,glasses,book,pen,t-shirt,chair,apple,banana,orange,cat,dog,motorcycle,bicycle,car,stop sign,monitor,camera,microphone,box,potted plant,toy,ball,umbrella,watch,keys,wallet,scissors,remote control,clock,lamp,photo,poster,sign".split(",")
model = YOLO("yoloe-26s-seg.pt")
model.set_classes(VOCAB)
exported = Path(model.export(format="onnx", imgsz=(384, 640), simplify=True,
                             end2end=True, opset=18))
exported.rename("yoloe-26s-booth-384x640.onnx")
```

`set_classes` runs the text encoder once on the Mac. The exported ONNX contains the vocabulary embeddings. Input is RGB float32 divided by 255, shaped `(1, 3, 384, 640)`, with linear resize and letterbox padding 114. Outputs are `(1, 300, 38)` and `(1, 32, 96, 160)`. The runtime reads box coordinates, confidence, and class from the first six detection columns; it ignores segmentation outputs. Preprocessing, tracking, thresholds, and the crop-size floor remain unchanged.

Copy the ONNX to `shared/models/detector/`. Build its engine on the Jetson while holding the existing GPU lock:

```sh
trtexec --onnx=yoloe-26s-booth-384x640.onnx --saveEngine=yoloe-26s-booth-384x640.fp16.engine --fp16 --memPoolSize=workspace:1024
```

Recorded D139 artifacts:

| File | SHA256 |
| --- | --- |
| `yoloe-26s-seg.pt` | `48f24206bc8680d60cbbfa296b0140da849669b9515058b72f5a945142df0654` |
| `mobileclip2_b.ts` | `35d7f213e4d75f38514e4656ad3cb91158bd33e3805d8ac349f23b186f66982f` |
| `yoloe-26s-booth-384x640.onnx` | `edbad6fd9657c55dafee3b73902b188311c13ec2c03600c521cf9128b06d84c4` |
| `yoloe-26s-booth-384x640.fp16.engine` | `52d40436be6b16df5ab26d83a9b1611b08ce20222734f5aafb10169d5ecde086` |

The export embeds a date, so a fresh export has another checksum. Record and qualify its ONNX and engine hashes. The hashes above identify the existing measured artifacts, rather than byte-identical output from every installation. License: AGPL-3.0, approved for the detector.

For nano fallback, use `Detector(MODELS / "detector/yoloe-26n-booth-384x640.onnx")` or restore the retained N release. Preserve its ONNX and FP16 engine. The historical recipe and calibration below remain specific to N.

## Historical nano export recipe

1. In a scratch directory: `uv run --python 3.12 --with ultralytics==8.4.174 --with onnx --with onnxslim python`, then `m = YOLO("yoloe-26n-seg.pt"); m.set_classes(VOCAB); m.export(format="onnx", imgsz=(384, 640), simplify=True, end2end=True)`. `set_classes` runs the MobileCLIP2 text encoder once on the Mac; the ONNX keeps only the vocabulary embeddings. YOLO26n: `YOLO("yolo26n.pt").export(...)` with the same arguments.
2. VOCAB (50): person, face, badge, lanyard, sticker, plush toy, teddy bear, mug, cup, bottle, phone, laptop, keyboard, computer mouse, headphones, backpack, bag, hat, glasses, book, pen, t-shirt, chair, apple, banana, orange, cat, dog, motorcycle, bicycle, car, stop sign, monitor, camera, microphone, box, potted plant, toy, ball, umbrella, watch, keys, wallet, scissors, remote control, clock, lamp, photo, poster, sign.
3. Copy to `shared/models/detector/yoloe-26n-booth-384x640.onnx` (sha256 `d827f596ae40ae2cb39c60dd7098180801c859a498b74fd5f6ae5c3c93b1c12f`; the export embeds a date, so a re-export has another hash).
4. On the Jetson, holding the GPU lock: `trtexec --onnx=yoloe-26n-booth-384x640.onnx --saveEngine=yoloe-26n-booth-384x640.fp16.engine --fp16 --memPoolSize=workspace:1024` (about six minutes; the prompt-free build peaked at 1.5 GB RSS).

Inputs: `yoloe-26n-seg.pt` and `yolo26n.pt` are in `models.json`. The text encoder `mobileclip2_b.ts` (Mac only) comes from the same release, sha256 `35d7f213e4d75f38514e4656ad3cb91158bd33e3805d8ac349f23b186f66982f`. License: AGPL-3.0 (approved by Dylan for the detector).

## Open questions for integration

- Region: the left, center, or right third of the upright frame, as the robot sees it.
- Choose the vocabulary from booth fixtures; tune it on dev frames only. Synonym pairs (teddy bear and plush toy, cup and mug) produce two labels on one object; the tracker is class-agnostic, so they stay one track.
- The 11% decode loss at 15 fps is the remaining contention. Running detection at a lower rate while the LLM generates would recover most of it, at the cost of the "15 fps while talking" target. (U)

## Sources

- https://docs.ultralytics.com/models/yoloe/
- https://docs.ultralytics.com/models/yolo26/
- https://github.com/ultralytics/assets/releases/tag/v8.4.0

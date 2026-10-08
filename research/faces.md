# Faces: detection, embedding, licenses, thresholds

As of 2026-10-08 (researcher). Labels: J measured on an Orin Nano, E measured elsewhere, U unverified.

## Summary

- Detector: YuNet (MIT weights), faces about 10 to 300 px, 2.59 ms on an Orin Nano CPU at 160x120 (J, OpenCV Zoo, older JetPack). SCRFD-2.5G is more accurate on WIDER hard (77.87 vs 70.8 to 75.0, E) but its weights are insightface non-commercial.
- Permissive embedders: SFace (MobileFaceNet, Apache 2.0; 5.09 ms CUDA FP16, 20 ms CPU on an Orin Nano at 150x150, J from OpenCV Zoo) and HSFace (Vec2Face iResNet50, MIT; LFW 98.87, CFP-FP 88.97, E; trained from WebFace-derived data). The reference demo used YuNet plus HSFace: genuine about 0.49, impostor about 0.00 cosine on a small gallery (E).
- Non-commercial or unclear: insightface w600k_mbf (IJB-C TAR@1e-4 95.02) and w600k_r50 (97.12): non-commercial, commercial license for sale. EdgeFace-S (95.63): CC BY-NC-SA on Hugging Face, BSD-3 on GitHub (ask Idiap). AdaFace R18 (94.99), GhostFaceNet (94.94): MIT code, weights without a stated license. Most face training sets (WebFace, MS1M, WIDER FACE) are research-only: Qdrant legal should review before a public booth.
- False identities grow with the gallery: FPIR is about N times FMR (NIST); MaxSim over K shots makes N times K comparisons. 20 people with 10 shots and 1,000 stranger probes need a per-comparison FMR below about 5e-6. Calibrate on our own impostor scores; no public number covers our camera.
- Max vs mean: on IJB-A, mean pooling beat max at low FAR (53.0 vs 46.4 TAR at FAR 0.001, E, 2016 CNN); rank-1 tied. No clean study of shot count found.
- Quality gates (U): face size, landmark pose, blur, agreement across frames. ISO/IEC 39794-5 asks for 90 px between the eyes (E), which a wide camera rarely gives.

## Sources

- https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet
- https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface
- https://raw.githubusercontent.com/opencv/opencv_zoo/main/benchmark/README.md
- https://github.com/deepinsight/insightface/tree/master/model_zoo
- https://www.insightface.ai/en/solutions/face-recognition-licensing
- https://arxiv.org/html/2307.01838v2 and https://huggingface.co/Idiap/EdgeFace-XXS
- https://github.com/mk-minchul/AdaFace, https://github.com/HamadYA/GhostFaceNets, https://github.com/HaiyuWu/Vec2Face
- https://pages.nist.gov/frvt/reports/demographics/implications_for_1N.pdf
- https://arxiv.org/pdf/1603.07057 (Table 1)
- refs/reachy-edge-memory/emulator/face.py and face_memory.py

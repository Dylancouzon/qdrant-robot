# Enclosure build log

This records the 2026-10-11 construction sequence. Current instructions live in [README](README.md), [casing assembly](CASING_ASSEMBLY.md), and [retention constraints](RETENTION_BRIEF.md).

1. Replaced the rounded-box shell with the user's tapered neutral-white silhouette. Selected the 22 mm base roll; 24 mm failed the expanded port reservation. A shared slope-aware cavity fixed invalid panel booleans. Exact bounds exclude cached tessellation.
2. Kept separate rear/right covers, the removable roof bridge, manual bearing joint, and external camera cable. Added actual visor baffle and blind decorative recess. Removed the loose drive coupon from installed assembly; its separate tooth test remains.
3. Added speaker housing/tray capture with one removable rear frame and shell receivers. Corrected neighboring clearance and validated its rear/right release route.
4. Rejected upright audio retention because its upper stop crossed the servo and its receiver crossed the speaker. Selected flatter audio and complete-module service. Corrected the tray USB cut, structural docking lands, and actual held-tool release access.
5. Regenerated the final casing, retention coupons, and integrated viewer. Results: casing 665, joint 286, integrated assembly 368, and retention 182 checks pass (E). Nine coupon meshes pass closure and bed checks.
6. Packaged 57 individual P1S projects. All slice without warnings. Rewriting thumbnail relationships with prefixed OPC tags caused native import failures. Restoring the default relationship namespace repaired the archives; packaging now checks final native geometry import.
7. Abandoned the unfinished combined project. Delivery uses 38 Required and 19 Optional STL files, then White/Black folders. All 57 STL, native projects, and generic 3MF sources pass native parser geometry import. GUI inspection remains unverified. No print was sent.

## Evidence

- [Rejected upright audio](retention-evidence/audio-attempt.json), [orientation comparison](retention-evidence/audio-orientation-screen.json), and [initial flatter-audio failures](retention-evidence/flatter-audio-initial.json) preserve failed receipts. They are excluded from print manifests.
- [Current retention checks](output/retention/checks.json), [coupon mesh checks](output/retention/coupon-mesh-checks.json), [casing checks](output/casing/checks.json), [joint checks](output/joint/checks.json), and [integrated checks](output/assembly/checks.json) record current CAD evidence.
- [P1S slicing and hash report](output/bambu/slice-checks.json) records delivered sources and projects. Detailed native CLI logs remain in `build/hardware-layout/bambu/`.
- Repository review receipts remain in `reviews/`; the final task review is `20261011-172531-4699-review.md`.

Physical contacts, holding strength, cable movement, cooling, acoustics, and powered coupling remain U. Jetson and camera retention await contact measurements.

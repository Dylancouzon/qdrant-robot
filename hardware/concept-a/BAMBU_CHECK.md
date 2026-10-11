# Power-exit trial slicing check

Observed in Bambu Studio on the Mac, 2026-10-11 (E). The imported trial measures 22.85 × 60 × 33.5 mm. Its flat floor rests on the bed. Bambu shows no open-edge warning. The complete model slices successfully.

| Setting | Observed value |
| --- | --- |
| Printer | Bambu Lab P1S |
| Nozzle | 0.4 mm |
| Filament | Bambu PLA Basic |
| Layer height | 0.2 mm |
| Wall loops | Three |
| Supports | Disabled |
| Estimated filament | 9.02 g |
| Estimated total time | 23 minutes, 29 seconds |

`output/power-exit-trial-p1s.3mf` saves the inspected geometry and these settings. The process preset inherits `0.20mm Standard @BBL X1C`. Its saved printer and filament settings specify P1S. Recheck the selected filament and plate before printing. The estimate includes preparation time and remains a slicer estimate.

`output/power-exit-trial.3mf` contains the same geometry with millimeter units. Use this file with another slicer or profile. Bambu displays a geometry-only import notice because this generic file contains no Bambu settings.

The bearing and camera coupons were regenerated with welded indexed meshes. Both now import without open-edge warnings and slice successfully with the same settings. Bambu confirms 152 × 36 × 6 mm for the bearing coupon and 44 × 36 × 10 mm for the camera coupon. Their estimated total times are 27 minutes, two seconds, and 20 minutes, 14 seconds, respectively.

Physical printing, installed plug fit, adjacent USB clearance, and final casing integration remain U. The trial is ready for a physical fit test. No print was sent.

## Complete casing and joint prototype

Bambu Studio 02.08.02.61 sliced all 44 individual casing, joint, cradle, and gauge projects through its official CLI (E). Each uses the saved native P1S profile, PLA, a 0.4 mm nozzle, 0.2 mm layers, three walls, and automatic tree supports. All returned success with empty warning messages. Exported object bounds and triangle counts match their source meshes. No print was sent.

[The slicing report](output/bambu/slice-checks.json) records each source hash, project hash, estimate, and result. [The P1S projects](output/bambu/) preserve the print orientations and saved settings. Inspect each project's supports before physical printing. Native UI inspection of these new projects remains incomplete because the app control returned `noWindowsAvailable` and `timeoutReached` after opening the front-shell project. CLI slicing does not establish safe support removal or physical retention.

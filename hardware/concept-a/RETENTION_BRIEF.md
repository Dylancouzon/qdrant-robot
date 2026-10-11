# Removable electronics retention

Speaker and audio use removable press-in keys with rigid stops and releasable detents. Their housing and cradle capture passes 182 bounded CAD checks (E). Actual contacts, force, flex, wear, and material life remain U. Jetson and camera have no completed positive retainers.

Preserve the tapered shell, optical clearance, airflow reservations, and service panels. Positive X points toward Jetson connectors; positive Y points rearward; positive Z points upward.

## Contact constraints

| Component | Current basis | Required measurement |
| --- | --- | --- |
| Jetson | Full standing envelope: 90.5 × 35 × 103 mm. User reports an 11 mm plastic edge thickness and 10 mm inward grip depth opposite connectors. Proposed strip spans X−52.75 to X−42.75. | Actual strip Y datum and usable Z length. Keep the full electronics, fan, and outlet envelopes. |
| Speaker | Reference housing: 100 × 21 × 45 mm. Hooks capture provisional solid corners with 0.2 mm gaps. | Actual housing and safe perimeter contacts. Exclude diaphragm, terminals, acoustic opening, and cable exit. |
| Audio | Flat reference housing: 53 × 23.5 × 14.6 mm, centered at (−27, −40, 88). | Safe housing corners, microphone openings, and USB direction. Preserve the separate USB reservation. |
| Camera | Reference board: 37 × 37 × 1.6 mm; holder diameter: 26 mm. Current frame is a gauge. | Explicit safe PCB contact lands. Preserve optics, focus travel, heatsink, connectors, and cable pocket. |

## Current construction and service

The speaker rear frame captures its housing and tray. Two floor receivers capture its feet. Rigid roofs and shoulders carry loads; a right-foot detent prevents withdrawal.

The audio housing, tray, and key form one removable module. Its opposed corner stops capture the housing; two docking feet capture the module to front-wall receivers. The shelf rises 4.45 mm for the flatter housing. Structural pocket lands are 2.4 mm thick; release hooks engage 0.6 mm.

Install the speaker housing/tray, then the audio module with the speaker key absent. Install the speaker key afterward, followed by Jetson and bus. Follow the exact [installation and service sequence](CASING_ASSEMBLY.md#electronics-retention-service), including tool access and support of loose housings.

Keep the prototype unpowered. Release checks require body access, bus removal, Jetson/fan/tray removal, and disconnected audio USB. The speaker key travels 18 mm rearward, then 140 mm through the right opening. Audio release uses two blunt 2 mm shafts, a 0.5 mm press/lift, and held release through the first 5.5 mm rear travel. The complete module withdraws 200 mm rearward and unclips outside.

## Verification and coupons

[Speaker checks](output/retention/speaker-checks.json) pass 64 checks; [audio checks](output/retention/audio-checks.json) pass 118. Checks cover zero nominal penetration, housing and cradle capture, finite translation, bounded lift/tilt, actual tool access, removal, reverse insertion, and installed joint clearance. Sampled paths and bounded escape tests do not prove every possible motion or printed strength.

Nine coupons are listed in the [shared manifest](output/retention/coupon-manifest.json) and [Jetson manifest](output/retention/jetson-coupon-manifest.json). Use [Optional print files](output/Print-files/README.md). Speaker receiver clearances are 0.1, 0.2, 0.3, and 0.4 mm. The Jetson coupon tests only the reported 11 mm thickness and 10 mm depth; its arbitrary 8 mm length defines no installed contact.

Print coupons in the intended material. Inspect supports, then test release and 20 insertion/removal cycles. Reject cracks, permanent deformation, trapped parts, or contact with populated electronics. Test warm material behavior before approving retention.

Run `build/hardware-layout/venv/bin/python hardware/concept-a/check_retention.py` after source changes. Development decisions and rejected evidence remain in [the build log](BUILD_LOG.md).

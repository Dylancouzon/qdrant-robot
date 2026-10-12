# Measurements

Parts sit in loose pockets with clearance, so reference sizes cover most of the design. Measured values are from Dylan (2026-10-12); others are labeled with their source.

## Camera

- Board: 38 × 38 mm.
- Mounting holes: four, each centered 4 mm from its corner point. That puts each center 2.83 mm from both edges, so the holes are 32.3 mm apart in both directions. Use 2.6 mm holes for M2 screws to absorb the error.
- Front: the lens holder is 15 mm in diameter, centered, and 23 mm tall from the board. Other parts are 3 mm tall or less.
- Back: a 6 mm heatsink, and a 4 mm connector on the opposite side, plus room for the cable.

## Speaker

- Housing: 100 × 45 × 21 mm (length × height × depth). This matches the Waveshare reference.

## STS3215 horn and case (online sources, U until checked on the part)

- Horn: four holes of 2.5 mm, on a square at ±4.95 mm from the shaft (14 mm circle), and an M3 × 6 center screw. Sellers list M3 horn screws. Source: [mimic-arm STS3215 fit block](https://github.com/Barbodmz/mimic-arm/pull/7), measured from the SO-ARM100 STEP model.
- Case: 45.4 × 24.8 × 28.8 mm without the output, per the same model. The servo sits in a pocket; it needs no screws.

## Taken from references

Jetson 103 × 90.5 × 35 mm, USB audio case 53 × 23.5 × 14.6 mm, the power plug and USB plug sizes in `hardware/DESIGN_REQUIREMENTS.md`, and standard M2 and M3 nuts. The first coupon print checks the nut pockets and the horn holes.

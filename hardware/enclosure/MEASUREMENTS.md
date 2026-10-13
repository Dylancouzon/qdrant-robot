# Measurements

Parts sit in loose pockets with clearance, so reference sizes cover most of the design. Measured values are from Dylan (2026-10-12); others are labeled with their source.

## Camera

- Board: 38 × 38 mm.
- Mounting holes: four, each centered 4 mm from its corner point. That puts each center 2.83 mm from both edges, so the holes are 32.3 mm apart in both directions. Use 2.6 mm holes for M2 screws to absorb the error.
- Front: the lens holder is 15 mm in diameter, centered, and 23 mm tall from the board. Other parts are 3 mm tall or less.
- Back: a 6 mm heatsink, and a 4 mm connector on the opposite side, plus room for the cable.
- Cable (U): a USB-A plug overmold of about 16 × 9 mm with 4.5 mm cable. It passes a 17 × 10 mm hole in the head floor and one in the roof, 32 mm from the yaw axis. At ±80° the cable needs 32.2 mm more length than at yaw 0 (E).

## Jetson

- Envelope: 103 × 90.5 × 34.77 mm. The carrier board is 100 × 79 × 1.57 mm, and the I/O connectors run along a 100 mm edge (O, NVIDIA).
- Tray: a flat black plastic tray under the board overhangs it by about 11.5 mm on the edge opposite the I/O (E, derived from 90.5 − 79), and about 1.5 mm on each short end (E, derived from 103 − 100).
- Strip (Dylan, 2026-10-13): the flat tray and board are 11 mm thick, and the edge opposite the connectors has 10 mm of plastic to grab. The 11 mm is U while Dylan measures it. It is the constant `JETSON_STRIP_T` in `geometry.py`, and the slot derives from it.
- Sources: the [Carrier Board Specification SP-11324-001 v1.3](https://developer.nvidia.com/downloads/assets/embedded/secure/jetson/orin_nano/docs/jetson_orin_nano_devkit_carrier_board_specification_sp.pdf) (Figures 4-1 and 4-2) and the [Super Developer Kit datasheet](https://dam-cdn.nvd.orangelogic.com/AssetLink/2ug686w80406gxf6q8uv7r3l7265m2n8.pdf).
- Heights above the board top: USB-A stacks and the RJ45 stand 16.7 mm (O) along the I/O edge, about 20 mm deep (E). The heatsink and fan top is about 25 mm (E).
- Heatsink: about 58 × 39 mm footprint near the board center (E, about ±4 mm). The reservation is 47 mm along X and 66 mm along Z.
- Split of the 11 mm plus the 24 mm above it: tray and feet about 7.6 mm (E), then the board, then components.

## Servo adapter board (Dylan, 2026-10-13)

- Board: 42 × 32 × 13 mm, standing on a long edge in a 13 mm wide pocket (the band holds 17 mm).
- Servo connector: top face, one corner.
- Barrel power jack: near one end of a long edge. It takes a 5.5 × 2.1 mm plug about 10 mm across and 40 mm long with strain relief. The jack is U for position, so the plug zone is 14 × 40 mm above the board's -X end.
- USB data port: position unknown, so each short end keeps 20 mm of plug room (U). Dylan has angled USB cables.

## Speaker

- Housing: 100 × 45 × 21 mm (length × height × depth). This matches the Waveshare reference.

## STS3215 horn and case (online sources, U until checked on the part)

- Horn: four holes of 2.5 mm, on a square at ±4.95 mm from the shaft (14 mm circle), and an M3 × 6 center screw. Sellers list M3 horn screws. Source: [mimic-arm STS3215 fit block](https://github.com/Barbodmz/mimic-arm/pull/7), measured from the SO-ARM100 STEP model.
- Case: 45.4 × 24.8 × 28.8 mm without the output, per the same model. The servo sits in a pocket; it needs no screws.

## Taken from references

USB audio case 53 × 23.5 × 14.6 mm, the power plug and USB plug sizes in `hardware/DESIGN_REQUIREMENTS.md`, and standard M2 and M3 nuts. The first coupon print checks the nut pockets and the horn holes.

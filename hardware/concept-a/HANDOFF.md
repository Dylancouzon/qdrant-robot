# Enclosure handoff

The current unpowered prototype measures 148.6 × 127.2 × 236 mm. It uses a tapered white body, a 22 mm base roll, and a black visor, grille, and neck cover.

Start with [print files](output/Print-files/README.md) and [the offline viewer](output/assembly/robot-viewer.html). Delivery contains 38 required pieces and 19 optional tests, organized by White and Black. Native P1S projects retain print settings. Geometry import passes; GUI inspection remains unverified.

Speaker and audio keys have bounded CAD capture and service checks. Jetson and camera remain location gauges. Read [requirements](../DESIGN_REQUIREMENTS.md) for owned hardware and [retention constraints](RETENTION_BRIEF.md) before modifying contacts.

Next: obtain the Jetson plastic-strip Y datum and usable Z length, and identify safe camera PCB lands. Print panel and retention coupons; test release, support removal, and 20 retention cycles before installing electronics. Physical retention, cables, cooling, acoustics, and powered motion remain U.

Follow [casing assembly](CASING_ASSEMBLY.md) and [joint assembly](JOINT_ASSEMBLY.md). Keep the camera cable external and the servo separate. Identify the bus adapter and supply before powered design.

Work in `/Users/dylanc/.codex/worktrees/robot-enclosure/qdrant-robot`, branch `codex/robot-enclosure`. Preserve the separate runtime checkout. [README](README.md) contains regeneration commands; [build log](BUILD_LOG.md) preserves development evidence. No purchase, print, powered test, or deployment occurred.

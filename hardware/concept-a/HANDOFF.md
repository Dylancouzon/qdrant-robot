# Enclosure handoff: tapered revision

Complete robot bounds are 148.6 × 127.2 × 236 mm. The 152 × 130 mm figures used by the generator are raw construction section limits.

The current revision follows the user’s tapered rounded reference with a neutral white body, black visor and raised black speaker grille. The finished body measures 148.6 × 127.2 × 160 mm and narrows toward 128 × 110 mm shoulder construction sections. The 22 mm base roll gives visibly softer lower corners without growing the footprint. The head is 116 × 80 × 56 mm; overall height 236 mm. The 24 mm base-roll trial failed the one mm port buffer, so 22 mm is the selected limit.

## Read only what the next task needs

1. Read [design requirements](../DESIGN_REQUIREMENTS.md) for owned hardware, measured cables, appearance preferences, and unresolved dimensions.
2. Compare [the approved concept](output/exterior-concept.png) with [the current CAD preview](output/assembly/robot-preview.png).
3. Read [the current design](README.md) and [refinement brief](REFINEMENT_BRIEF.md). Open assembly instructions only when changing their interfaces.

Worktree: `/Users/dylanc/.codex/worktrees/robot-enclosure/qdrant-robot`. Branch: `codex/robot-enclosure`. Preserve the separate runtime checkout.

## Reusable work and its limits

The current casing passes 582 CAD checks and exports 18 functional casing/support pieces plus 5 gauges. The unchanged joint passes 286 checks and exports 23 parts/coupons. All generic 3MF meshes are closed, use millimeters, fit the P1S bed and match independent CAD extrema. All 46 current P1S projects slice successfully without warnings. Source and project hashes match the final meshes. The integrated assembly report supplies its current count and checks.


The removable roof bridge admits the preassembled bearing joint. Retained keys connect its tower and head flange. CAD checks cover yaw clearance, gear teeth, stops, component reservations, and assembly admission. Read [casing assembly](CASING_ASSEMBLY.md) and [joint assembly](JOINT_ASSEMBLY.md) for dimensions and installation order.

The joint supports manual movement. The servo housing gauge and hand-held drive gear remain separate coupons and are excluded from the installed assembly. The joint tooth-mesh check retains the drive coupon at its temporary test position. Installed servo retention and powered horn coupling require actual mounting measurements. The power-exit trial remains separate from the casing. Component cradles require verified safe contact lands and physical retention.

Physical fits, bearing race contact, support removal, cable movement, thermal behavior, and acoustics remain U. Native inspection of the new P1S projects remains incomplete. Keep the camera cable outside the manual joint until complete connector admission is designed. Identify the owned bus-servo adapter before specifying power wiring.

## Physical follow-up

Confirm component support lands, servo ears and horn hardware, bearing race contacts, installed connector shapes, actual fan direction and practical camera cable bends. Print panel-fit coupons and interface gauges before the complete enclosure. Complete powered retention and cable routing from those measurements. Compare open and enclosed operation under the same workload before thermal approval.

Use [the README regeneration instructions](README.md#checks-and-regeneration). The CAD environment is `build/hardware-layout/venv/bin/python`. The complete STEP and offline triangle viewer are in `output/assembly/`. The P1S projects are in `output/bambu/`.

Read generated manifests and review logs only for a specific question. Old packaging plans live in `research/archive/`. Keep requirements in their existing file and update this handoff instead of adding session transcripts. No hardware purchase, print, powered-motion test, or robot deployment occurred in this task.

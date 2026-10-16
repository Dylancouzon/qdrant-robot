# Object owners and physical location

Object ownership works in the current runtime. UI-set physical locations remain a parked proposal. See [objects](objects.md#owners) for the implemented owner rules.

## Current ownership

Each named object carries a visitor ID in `owner`, its spoken `name`, and a normalized `key`. The same visitor can reteach an object; different visitors can use the same name. A told name or consented face enrollment updates the visitor's display identity. The Memory tab groups by visitor ID. "Forget me" removes linked objects and evidence. D154 and D155 implement the owner separation proposed under D148.

## Parked location proposal

Dylan requested physical location labels on 2026-10-10. A future UI location setting would be copied into each sighting at capture time. Later changes would affect only new observations. The location would describe where the robot saw an object, rather than its current whereabouts.

This location field and control need their own scoped design review. Existing owner scoping and consent rules remain intact. Servo motor control and voice commands take priority. The earlier proposal remains in [answer-evidence.md](archive/answer-evidence.md).

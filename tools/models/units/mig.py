"""MiG-29 (9-13) Fulcrum-C (actor MIG) from "Mig 29 (9-13)" by Rifeor (CC-BY-4.0,
sketchfab.com/3d-models/mig-29-9-13-2c8a8f454fa04a8b914aa9a227f67bbe).
Real size: 17.32 m long, 11.36 m span. The source is 899k triangles: the cockpit interior, landing gear,
wheel wells and fasteners are dropped (gear up, in flight) and every part decimated to the budget."""

import _aircraft as A
import convert
from lib import join

SOURCE = "mig_29_9-13.glb"
DROP = ("cabin", "chassis", "niche", "fasteners")
BUDGET = 22000
# Player colour: the twin fins.
TEAM = lambda c: c.y < -5.0 and c.z > 2.1


def build(wreck=False):
    parts = A.load_parts(SOURCE, lambda n: n[1], drop=lambda n: any(d in x for x in n for d in DROP))
    total = sum(A.tris(o) for o in parts.values())
    for o in parts.values():
        convert.decimate(o, max(200, int(BUDGET * A.tris(o) / total)))
    hull = join(*parts.values())
    hull.name = "hull"
    parts = {"hull": hull}
    A.place(parts, front="-Y", length=17.32)
    A.team_faces(hull, TEAM, shade=0.4 if wreck else 0.9)
    print("hull", A.tris(hull))
    if wreck:
        A.wreck_jet(hull, 2.5, -4.0)
    return hull


FINISH = {"flat": False, "keep": A.JET_KEEP}
PREVIEW = {"distance": 28, "target_z": 1.5}

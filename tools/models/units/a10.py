"""A-10C Thunderbolt II (actor A10) from "A-10 Thunderbolt II" by AIRMAN Magazine (CC-BY-4.0,
sketchfab.com/3d-models/a-10-thunderbolt-ii-9521ff6ba5d448958ea45a89e94ab23d).
Real size: 16.26 m long, 17.53 m span. Fixed wing: one node, no clips."""

import _aircraft as A
import convert

SOURCE = "a-10_thunderbolt_ii.glb"
# Player colour: the twin fins.
TEAM = lambda c: abs(c.x) > 2.85 and c.y < -5.8 and c.z > 1.4


def build(wreck=False):
    parts = A.load_parts(SOURCE, lambda n: "hull")
    A.place(parts, front="+Y", length=16.26)
    hull = parts["hull"]
    convert.decimate(hull, 22000)
    A.team_faces(hull, TEAM, shade=0.4 if wreck else 0.9)
    print("hull", A.tris(hull))
    if wreck:
        A.wreck_jet(hull, 3.5, -4.0)
    return hull


FINISH = {"flat": False, "keep": A.JET_KEEP}
PREVIEW = {"distance": 30, "target_z": 1.5}

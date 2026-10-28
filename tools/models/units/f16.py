"""F-16C Fighting Falcon (actor F16) from "F-16 jet" by RickSlash (CC-BY-4.0,
sketchfab.com/3d-models/f-16-jet-69c32a15b8e24d6ebf276b76dde3ab95).
Real size: 15.06 m long, 9.96 m span. Fixed wing: one node, no clips."""

import _aircraft as A

SOURCE = "f-16_jet.glb"
# Player colour: the fin.
TEAM = lambda c: abs(c.x) < 0.3 and c.y < -4.0 and c.z > 2.6


def build(wreck=False):
    parts = A.load_parts(SOURCE, lambda n: "hull")
    A.place(parts, front="-Y", length=15.06)
    hull = parts["hull"]
    A.team_faces(hull, TEAM, shade=0.4 if wreck else 0.9)
    print("hull", A.tris(hull))
    if wreck:
        A.wreck_jet(hull, 2.0, -3.5)
    return hull


FINISH = {"flat": False, "keep": A.JET_KEEP}
PREVIEW = {"distance": 26, "target_z": 1.5}

"""Su-25 Frogfoot (actor FROG) from "Su-25" by mamont nikita (CC-BY-4.0,
sketchfab.com/3d-models/su-25-88b71eb848cf4418a95dff497c07cefc).
Real size: 15.33 m long, 14.36 m span. Fixed wing: one node, no clips."""

import _aircraft as A

SOURCE = "su-25.glb"
# Player colour: the fin.
TEAM = lambda c: abs(c.x) < 0.3 and c.y < -4.0 and c.z > 2.6


def build(wreck=False):
    parts = A.load_parts(SOURCE, lambda n: "hull")
    A.place(parts, front="-Y", length=15.33)
    hull = parts["hull"]
    A.team_faces(hull, TEAM, shade=0.4 if wreck else 0.9)
    print("hull", A.tris(hull))
    if wreck:
        A.wreck_jet(hull, 3.0, -3.5)
    return hull


FINISH = {"flat": False, "keep": A.JET_KEEP}
PREVIEW = {"distance": 28, "target_z": 1.5}

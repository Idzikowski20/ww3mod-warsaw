"""AH-64D Apache Longbow (actor HELI) from "Boeing AH-64D Apache Combat Helicopter" by Muhamad Mirza
Arrafi (CC-BY-4.0, sketchfab.com/3d-models/boeing-ah-64d-apache-combat-helicopter-c3b58008c46b45048fdd7dd283a3c8c8).
Real size: 17.73 m long with the rotors turning, four-blade 14.63 m main rotor, four-blade scissor tail
rotor on the left of the fin, Longbow radar on the (fixed) mast. The source has the rotors fused into the
body: they are cut out by connected piece (blades, hub, grips) and position."""

import math
import _aircraft as A
import convert

SOURCE = "boeing_ah-64d_apache_combat_helicopter.glb"
HUB = (0.0, 1.88)          # main rotor axis (x, y) after placing
TAIL = (-7.5, 2.96)        # tail rotor hub (y, z)


def _rotor(lo, hi):
    c = (lo + hi) / 2
    return (max(hi - lo) > 5 and lo[2] > 3.2) or \
        (math.hypot(c[0] - HUB[0], c[1] - HUB[1]) < 1.1 and lo[2] > 3.1 and hi[2] < 3.8)


def _tail(lo, hi):
    c = (lo + hi) / 2
    return hi[0] < -0.3 and math.hypot(c[1] - TAIL[0], c[2] - TAIL[1]) < 1.3


def build(wreck=False):
    # Decal / Alpha materials are alpha-cut overlays (black where see-through): the engine draws opaque.
    parts = A.load_parts(SOURCE, lambda n: "hull", drop=lambda n: n[0] in ("object_2", "object_4", "object_5"))
    A.place(parts, front="-X", length=17.73)
    hull = parts["hull"]
    parts.update(A.split_islands(hull, {"rotor": _rotor, "tail_rotor": _tail}))
    rotor, tail = parts["rotor"], parts["tail_rotor"]
    A.paint(hull, "glass", (0.08, 0.1, 0.11))
    # Player colour: the stabilator and a band round the tail boom.
    A.team_faces(hull, lambda c: (c.y < -7.1 and abs(c.x) > 0.3 and c.z < 1.3) or (-5.5 < c.y < -4.7 and c.z > 0.8),
                 shade=0.4 if wreck else 0.9)
    A.place(parts, "+Y", body=("hull",))     # centre on the fuselage, not on the rotor disc
    A.axis_pivot(rotor, (0, 0, 1))
    A.flatten_rotor(rotor, 1.0)
    A.axis_pivot(tail, (-1, 0, 0), hub="bbox", axis=(-1, 0, 0))
    convert.parent(rotor, hull)
    convert.parent(tail, hull)
    for o in parts.values():
        print(o.name, A.tris(o))
    if wreck:
        A.wreck_rotor(rotor, keep_blades=(1, 2), blades=4, droop=0.8, hub_r=1.0)
        A.break_tail(hull, tail, -3.0, rot=(12, 0, -20))
    else:
        A.spin([(rotor, 1, 1), (tail, 4, 1)])
    return hull


FINISH = {"flat": False, "keep": A.HELI_KEEP, "export_options": A.NLA}
PREVIEW = {"distance": 32, "target_z": 1.5}

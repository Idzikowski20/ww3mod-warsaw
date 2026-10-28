"""Mi-26 "Halo" (actor HALO) from "Mi-26" by dannzjs (CC-BY-4.0,
sketchfab.com/3d-models/mi-26-272597d721e74a45914f7ffb846dda2a).
Real size: 40.03 m long with the rotors turning, eight-blade 32 m main rotor, five-blade tail rotor on the
right of the fin. The source has the rotors fused into the body: they are cut out by connected piece."""

import math
import _aircraft as A
import convert

SOURCE = "mi-26.glb"
HUB_Y = 4.17               # main rotor axis (x = 0) after placing
TAIL = (-16.5, 9.8)        # tail rotor hub (y, z)


def _rotor(lo, hi):
    c = (lo + hi) / 2
    return (max(hi - lo) > 8 and lo[2] > 6.4) or (math.hypot(c[0], c[1] - HUB_Y) < 1.5 and lo[2] > 8.5)


def _tail(lo, hi):
    c = (lo + hi) / 2
    return lo[0] > 0.9 and math.hypot(c[1] - TAIL[0], c[2] - TAIL[1]) < 3.6


# Player colour: a band round the tail boom and the horizontal stabilisers (placed coordinates, before centring).
TEAM = lambda c: (-8.0 < c.y < -6.5 and c.z > 4.5) or (-13.6 < c.y < -11.3 and abs(c.x) > 0.6 and c.z > 6.4)


def build(wreck=False):
    parts = A.load_parts(SOURCE, lambda n: "hull")
    A.place(parts, front="+X", length=40.03)
    hull = parts["hull"]
    parts.update(A.split_islands(hull, {"rotor": _rotor, "tail_rotor": _tail}))
    rotor, tail = parts["rotor"], parts["tail_rotor"]
    convert.decimate(hull, 17000)
    for o in parts.values():
        A.brighten(o, 1.15)       # the source paint is very dark
        # material_0 is a detail sheet with alpha cut-outs (bands, markings) laid over the camouflage:
        # opaque it bakes as pale slabs, so it takes the camouflage's grey-green instead.
        A.paint(o, "material_0", (0.27, 0.29, 0.25))
    A.team_faces(hull, TEAM, shade=0.4 if wreck else 0.9)
    A.place(parts, "+Y", body=("hull",))
    A.axis_pivot(rotor, (0, 0, 1))
    A.flatten_rotor(rotor, 2.0)
    A.axis_pivot(tail, (1, 0, 0), hub="bbox", axis=(1, 0, 0))
    convert.parent(rotor, hull)
    convert.parent(tail, hull)
    for o in parts.values():
        print(o.name, A.tris(o))
    if wreck:
        A.wreck_rotor(rotor, keep_blades=(1, 2, 5), blades=8, droop=2.0, hub_r=2.0)
        A.break_tail(hull, tail, -9.0, rot=(10, 0, 18))
    else:
        A.spin([(rotor, 1, -1), (tail, 4, 1)])
    return hull


FINISH = {"flat": False, "keep": A.HELI_KEEP, "export_options": A.NLA}
PREVIEW = {"distance": 72, "target_z": 4.0}

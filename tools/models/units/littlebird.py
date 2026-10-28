"""MH-6 Little Bird from "Helicopters MH-6 Little Bird" by mario low poly (CC-BY-4.0,
sketchfab.com/3d-models/helicopters-mh-6-little-bird-69cb05db3fc3483cb729734262abf28e).
Real size: main rotor 8.33 m across (five blades), two-blade tail rotor. The source has the rotors as
separate objects ("helice 1", "helice 2"); they become the "rotor" and "tail_rotor" nodes."""

import _aircraft as A
import convert

SOURCE = "helicopters_mh-6_little_bird.glb"


def build(wreck=False):
    parts = A.load_parts(SOURCE, lambda n: "rotor" if any("helice 1" in x for x in n)
                         else "tail_rotor" if any("helice 2" in x for x in n) else "hull")
    A.place(parts, front="-Y", rotor_diameter=8.33, body=("hull",))
    hull, rotor, tail = parts["hull"], parts["rotor"], parts["tail_rotor"]
    convert.decimate(hull, 17000)
    convert.decimate(rotor, 1800)
    A.axis_pivot(rotor, (0, 0, 1))
    A.axis_pivot(tail, (1, 0, 0), axis=(1, 0, 0))
    convert.parent(rotor, hull)
    convert.parent(tail, hull)
    A.paint(hull, "vidrio", (0.1, 0.13, 0.15))
    # Player colour: the tail boom and the T-tail stabiliser.
    A.team_faces(hull, lambda c: (-3.0 < c.y < -0.9 and abs(c.x) < 0.25 and 1.5 < c.z < 2.0)
                 or (c.y < -3.5 and c.z > 2.4), shade=0.4 if wreck else 0.9)
    for o in parts.values():
        print(o.name, A.tris(o))
    if wreck:
        A.wreck_rotor(rotor, keep_blades=(0, 2), blades=5, droop=0.9, hub_r=0.35)
        A.break_tail(hull, tail, -1.4)
    else:
        A.spin([(rotor, 1, 1), (tail, 3, 1)])
    return hull


FINISH = {"flat": False, "keep": A.HELI_KEEP,
          "export_options": A.NLA}
PREVIEW = {"distance": 19, "target_z": 1.2}

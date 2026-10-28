"""Mi-28N Havoc (actor MI28) from "Mi-28N Havoc" by Rukh3D (CC-BY-4.0,
sketchfab.com/3d-models/mi-28n-havoc-3e80c95bbadf46abbafba9d9a08afc68).
Real size: five-blade 17.2 m main rotor, four-blade X tail rotor on the left of the fin. The source is
skinned with two animations: the posed mesh is frozen; rotor and tail rotor are its own meshes."""

import _aircraft as A
import convert

SOURCE = "mi-28n_havoc.glb"
# Player colour: a band round the tail boom and the stabiliser.
TEAM = lambda c: (-5.0 < c.y < -3.9) or (c.y < -7.9 and c.x < -0.4)


def build(wreck=False):
    parts = A.load_parts(SOURCE, lambda n: "rotor" if n[0] == "object_16" else "tail_rotor" if n[0] == "object_18"
                         else "hull", drop=lambda n: n[0] == "icosphere")
    A.place(parts, front="-Y", rotor_diameter=17.2, body=("hull",))
    hull, rotor, tail = parts["hull"], parts["rotor"], parts["tail_rotor"]
    convert.decimate(hull, 22000)
    for o in parts.values():
        A.brighten(o, 1.4)       # the source paint is near black (a metallic PBR base)
    A.team_faces(hull, TEAM, shade=0.4 if wreck else 0.9)
    A.axis_pivot(rotor, (0, 0, 1))
    A.flatten_rotor(rotor, 0.9)
    A.axis_pivot(tail, (1, 0, 0), hub="bbox", axis=(1, 0, 0))
    convert.parent(rotor, hull)
    convert.parent(tail, hull)
    for o in parts.values():
        print(o.name, A.tris(o))
    if wreck:
        A.wreck_rotor(rotor, keep_blades=(1, 4), blades=5, droop=1.2, hub_r=0.8)
        A.break_tail(hull, tail, -4.0, rot=(10, 0, -20))
    else:
        A.spin([(rotor, 1, -1), (tail, 4, 1)])
    return hull


FINISH = {"flat": False, "keep": A.HELI_KEEP, "export_options": A.NLA}
PREVIEW = {"distance": 36, "target_z": 2.0}

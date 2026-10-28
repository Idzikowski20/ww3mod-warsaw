"""Mi-24 Hind (actor HIND) from "Mi-24 Hind" by Duane's Mind (CC-BY-4.0,
sketchfab.com/3d-models/mi-24-hind-004d68143e1a4df88e136dbc0a05f181).
Real size: five-blade 17.3 m main rotor, three-blade tail rotor. The source's rotors are separate objects
(Top_Rotor, Tail_Rotor); its one animation (wheels and rotor) is ignored, the mesh frozen as posed."""

import _aircraft as A
import convert

SOURCE = "mi-24_hind.glb"
# Player colour: a band round the tail boom and the horizontal stabilisers.
TEAM = lambda c: (-4.2 < c.y < -2.8) or (-7.2 < c.y < -6.2 and abs(c.x) > 0.4)


def build(wreck=False):
    parts = A.load_parts(SOURCE, lambda n: "rotor" if "top_rotor" in n else "tail_rotor" if "tail_rotor" in n
                         else "hull")
    A.place(parts, front="-Y", rotor_diameter=17.3, body=("hull",))
    hull, rotor, tail = parts["hull"], parts["rotor"], parts["tail_rotor"]
    A.team_faces(hull, TEAM, shade=0.4 if wreck else 0.9)
    A.axis_pivot(rotor, (0, 0, 1))
    A.axis_pivot(tail, (-1, 0, 0))
    convert.parent(rotor, hull)
    convert.parent(tail, hull)
    for o in parts.values():
        print(o.name, A.tris(o))
    if wreck:
        A.wreck_rotor(rotor, keep_blades=(0, 3), blades=5, droop=1.2, hub_r=0.8)
        A.break_tail(hull, tail, -4.5, rot=(10, 0, 20))
    else:
        A.spin([(rotor, 1, -1), (tail, 4, 1)])
    return hull


FINISH = {"flat": False, "keep": A.HELI_KEEP, "export_options": A.NLA}
PREVIEW = {"distance": 34, "target_z": 2.0}

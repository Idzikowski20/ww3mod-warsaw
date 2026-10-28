"""Where the gun is, from a unit model: prints the Turreted Offset and Armament LocalOffset (WDist
forward,right,up) that put the turret pivot and the muzzle where the model has them, so shells and muzzle
flashes leave the barrel tip.

    python tools/models/muzzle.py t90.glb [scale]

Model frame (glTF): +X right, +Y up, front -Z; the actor centre is the model origin. A node "turret" is
the turret pivot; the muzzle is the forward-most point of the "barrel" node's geometry, on its axis.
One metre of model at Scale s is s * 1024 / 8 WDist (8 m cells).
"""

import json
import os
import struct
import sys

MODELS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "mods", "ww3mod", "bits", "models")


def nodes(path):
    with open(path, "rb") as f:
        data = f.read()
    length = struct.unpack("<I", data[12:16])[0]
    gltf = json.loads(data[20:20 + length])
    out = {}
    for n in gltf["nodes"]:
        lo = hi = None
        if "mesh" in n:
            for p in gltf["meshes"][n["mesh"]]["primitives"]:
                if gltf["materials"][p["material"]]["name"].startswith("outline"):
                    continue
                a = gltf["accessors"][p["attributes"]["POSITION"]]
                lo = a["min"] if lo is None else [min(x, y) for x, y in zip(lo, a["min"])]
                hi = a["max"] if hi is None else [max(x, y) for x, y in zip(hi, a["max"])]
        out[n.get("name", "")] = (n.get("translation", [0, 0, 0]), lo, hi)
    return out


def offsets(model, scale=2.0):
    """(turret Offset, armament LocalOffset) as WDist (forward, right, up), or None without turret/barrel."""
    n = nodes(os.path.join(MODELS, model))
    if "turret" not in n or "barrel" not in n:
        return None
    k = scale * 1024 / 8
    t = n["turret"][0]
    b, lo, _ = n["barrel"]
    turret = (round(-t[2] * k), round(t[0] * k), round(t[1] * k))
    muzzle = (round((-b[2] - lo[2]) * k), round(b[0] * k), round(b[1] * k))
    return turret, muzzle


if __name__ == "__main__":
    model = sys.argv[1]
    o = offsets(model, float(sys.argv[2]) if len(sys.argv) > 2 else 2.0)
    if o is None:
        sys.exit(f"{model}: no turret/barrel nodes")
    print("Turreted:\n\tOffset: {},{},{}".format(*o[0]))
    print("Armament:\n\tLocalOffset: {},{},{}".format(*o[1]))

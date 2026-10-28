"""Renders facade styles in background Blender and records their sizes for build_city.py.

Usage: blender -b -P render_facades.py -- <out dir> [style ...]   (no styles = all)
Writes <out dir>/<style>_upper.png, <style>_ground.png and merges sizes into <out dir>/styles.json.
"""
import json
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(HERE, "blender_facades.py"), encoding="utf-8").read())


def enable_gpu():
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for backend in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
        try:
            prefs.compute_device_type = backend
        except TypeError:
            continue
        prefs.get_devices()
        gpus = [d for d in prefs.devices if d.type != "CPU"]
        if gpus:
            for d in prefs.devices:
                d.use = d.type != "CPU"
            print("render devices:", backend, [d.name for d in gpus], flush=True)
            return
    print("render devices: CPU only", flush=True)


args = sys.argv[sys.argv.index("--") + 1:]
out_dir, names = args[0], args[1:] or list(STYLES)
enable_gpu()

manifest_path = os.path.join(out_dir, "styles.json")
os.makedirs(out_dir, exist_ok=True)
manifest = json.load(open(manifest_path)) if os.path.exists(manifest_path) else {}
for name in names:
    info = render_style(name, out_dir)
    manifest[name] = {"width": info["width"], "upper": info["upper"], "ground": info["ground"]}
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=1)
    print("rendered", name, flush=True)

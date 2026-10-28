"""Builds the unit models: every module in units/ (not _helpers) exports <name>.glb and <name>-wreck.glb into
mods/ww3mod/bits/models/, with a preview render beside each in WORKSPACE/m4-refs/previews/.

    blender --background --factory-startup --python tools/models/build.py -- [unit ...]
"""

import importlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path[:0] = [HERE, os.path.join(HERE, "units")]

import lib  # noqa: E402

OUT = os.path.join(ROOT, "mods", "ww3mod", "bits", "models")
PREVIEWS = os.path.join(ROOT, "WORKSPACE", "m4-refs", "previews")

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
names = args or sorted(f[:-3] for f in os.listdir(os.path.join(HERE, "units"))
                       if f.endswith(".py") and not f.startswith("_"))
os.makedirs(OUT, exist_ok=True)
os.makedirs(PREVIEWS, exist_ok=True)

for name in names:
    module = importlib.import_module(name)
    # A unit module defines build(wreck); optional: WRECK = False (no wreck model), FINISH = {...} extra
    # lib.finish() arguments (keep, flat, texture_size, outline_width), PREVIEW = {...} camera.
    for wreck in (False, True) if getattr(module, "WRECK", True) else (False,):
        suffix = "-wreck" if wreck else ""
        lib.reset()
        module.build(wreck=wreck)
        glb = os.path.join(OUT, name + suffix + ".glb")
        lib.finish(glb, wreck=wreck, **getattr(module, "FINISH", {}))
        lib.render_preview(glb, os.path.join(PREVIEWS, name + suffix + ".png"), yaw=215,
                           **getattr(module, "PREVIEW", {}))
        print("built", name + suffix)

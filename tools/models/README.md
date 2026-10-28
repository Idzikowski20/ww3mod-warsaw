# Unit models (M4)

3D models for WW3MOD units, built by Blender scripts into `mods/ww3mod/bits/models/<name>.glb` and
drawn by the engine's glTF renderer (`engine/OpenRA.Game/Graphics/Mesh.cs`, trait
`WithMeshBody` in `engine/OpenRA.Mods.Common/Traits/Render/WithMeshBody.cs`).

## Build

From the repository root (Git Bash):

    "/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --factory-startup --python tools/models/build.py -- <unit> [<unit> ...]

Each unit is `tools/models/units/<unit>.py`. The build writes `<unit>.glb` and `<unit>-wreck.glb` to
`mods/ww3mod/bits/models/` and a preview of each to `WORKSPACE/m4-refs/previews/<unit>[-wreck].png`.
The preview is lit exactly as the game shader lights it (albedo × (0.55 + 0.55·n·L)), on a dark ground.

**Viewing a preview:** the Read tool caches images by path. Copy the PNG to a new unique name
(e.g. `previews/<unit>_v3.png`) before reading it, or you will see the old render.

## A unit module

    import convert                       # downloaded-model helpers (load, normalize, decimate, split, pivot, parent, recolor)
    from lib import box, cyl, extrude, prism, sphere, mat   # primitives for hand-built parts

    def build(wreck=False):
        ...                              # leave the scene holding the model; return the root object

    FINISH = {"flat": False}             # lib.finish() options; see below
    WRECK = True                         # False: no -wreck model (infantry, props)
    PREVIEW = {"distance": 13}           # render_preview() camera options

`lib.finish(path, keep=("hull", "turret", "barrel"), texture_size=1024, flat=True, wreck=False,
outline_width=0.0, export_options=None)`:

- **keep** — object names that survive as glTF nodes. Every other object is merged into its nearest kept
  ancestor (or `keep[0]` when it has none). One draw call per kept node, so keep only what moves.
- **flat** — `True` flat-shades (hand-built boxes); downloaded models want `False` (keep their normals).
- **texture_size** — the one atlas baked for the whole model: 1024 vehicles/aircraft, 512 infantry/props.
- **wreck** — set by build.py for the `-wreck` pass: the bake burns the colours (soot, rust). The module's
  `build(wreck=True)` should also break the shape (turret off its ring and skewed, gun drooping, rotor
  blades bent or missing).
- **export_options** — extra glTF exporter arguments, e.g. `{"export_animation_mode": "NLA_TRACKS"}`.

The bake (`lib.bake`) gives every model the same look: the source texture (or the material colour)
weathered with grime, rain streaks, AO in crevices, worn edges, and dust/mud rising from the ground.

## Conventions the engine relies on

- Metres, Z up, **front of the unit along +Y**, origin on the ground under the centre.
- Real-world size (`convert.normalize(..., length=<real length in m>)`). The rules scale it (`Scale: 2`).
- A turret is a node named `turret` parented to `hull`, its gun a node named `barrel` parented to the turret,
  pivots at the turret ring centre and the gun trunnion (`convert.pivot`). Turrets turn about +Z.
- Material named `team…` = player colour (flat colour multiplied by the player colour, not baked).
  Material named `outline…` = the outline shell (added by finish; do not create it yourself).
- Every model shows some player colour: e.g. side stripes + a roof panel (vehicles), a tail band or fin
  (aircraft), a helmet band or armband (infantry), a panel or flag (defences).
- Animations: glTF clips named `idle`, `move`, `attack` (seconds, looping; attack plays once per shot).
  Rigid node animation only — no skinning. Author per-object actions, push each to an NLA track named
  after the clip, and export with `export_options={"export_animation_mode": "NLA_TRACKS"}`.
- Triangle budgets before the outline (which doubles them): vehicle/aircraft ≤ 25k, defence ≤ 15k,
  infantry figure incl. weapon ≤ 5k.

## Sources and licences

Downloaded sources are in `WORKSPACE/m4-refs/sources/`; their author/licence table is
`WORKSPACE/m4-refs/SOURCES.tsv`. Only CC-BY / CC0 may be used. Every unit module's docstring names its
source, author, licence and URL, and those go to `CREDITS.md`.
**Not usable:** `m1151_hmmwv_lras3.glb` and `m4_carabine.glb` (CC-BY-NC), `fim-92_stinger.glb`
(Sketchfab Standard). Use `humvee_transport.glb`, `m4_carbine.glb`, `fim-92_stinger_v2.glb` instead.

Reference pictures of each unit (the in-game cameos, real-vehicle photos): `WORKSPACE/m4-refs/icons2/<name>icon-0000.png`.

## Wiring into the game

`mods/ww3mod/rules/models-3d.yaml` gives each actor its model, merged over its definition:

    t90:
        WithMeshBody:
            Model: t90.glb
            Scale: 2
            TurretNodes:
                turret: primary          # node: Turreted trait name
    t90.husk:
        WithMeshBody:
            Model: t90-wreck.glb
            Scale: 2

Actor keys are case-sensitive and must match the definition exactly (`HELI`, `E1.america`, `t90.husk`).

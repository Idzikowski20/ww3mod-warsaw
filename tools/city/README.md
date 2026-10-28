# Generated city map (`city-ww3`)

The main skirmish map (`mod.yaml` → `MainMap`) is built on your machine from 3D kits that cannot be
redistributed, so the map folder `mods/ww3mod/maps/city-ww3/` is git-ignored. Without it the game starts
on its usual map.

You need Blender 5.2 and Python 3 with numpy and Pillow, plus:

- **iCity** glTF exports (`City_Exports/…_unpacked_joined_GLTF/*.gltf`) — paid addon, keep local;
- **`abandoned city.blend`** — the Geometry Nodes generator of ruined high-rises.

## Build

```bash
B="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
OUT=<tiles dir>
for spec in "11 1.0" "23 1.0" "37 0.6" "53 0.6"; do set -- $spec
  "$B" -b "<abandoned city.blend>" -P blender_city_tiles.py -- abandoned "$OUT" $1 76 $2
done
"$B" -b -P blender_city_tiles.py -- icity "<City_Exports dir>" "$OUT"
python build_city_map.py "$OUT" ../../mods/ww3mod/maps/warsaw-srodmiescie-ww3 ../../mods/ww3mod/maps/city-ww3
```

`blender_city_tiles.py` bakes each detailed wall module onto a 12-triangle box (Cycles diffuse colour) and
keeps the generator's instances as instances. `build_city_map.py` lays out the 4 × 4 grid of 256 m blocks
(iCity in the centre, abandoned tiles around, open corner lots for bases), the avenues, the blocking
raster and the texture atlas. File formats are described at the top of each script.

## Credits

Zoning after Curtis Holt's City Scatter Tool (credit required when sharing derivative work). City kits:
iCity; abandoned-city generator as supplied by the project owner.

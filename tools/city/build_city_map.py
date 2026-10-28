"""Assembles the generated city map (mods/ww3mod/maps/city-ww3) from the tiles blender_city_tiles.py exported.

Layout, 1024 m square (128 x 128 cells of 8 m plus a border cell): a 4 x 4 grid of 256 m blocks, after
Curtis Holt's City Scatter zoning (dense centre, older and emptier outwards):
  - centre 2 x 2: the iCity block (perimeter blocks, streets, parking), turned and mirrored per block,
    plus its tower once;
  - the 8 edge blocks: one city block each, cut from the abandoned-city tiles (each tile is a 900 m city
    of 4 x 4 blocks on a 228 m road grid), stretched across to 256 m, with random quarter turns and mirrors;
  - the 4 corners: open lots for the players' bases, where the spawns are.
14 m avenues with kerbs and centre dashes run between the blocks.

Writes into the map folder: scene.mesh (WSCN v2, read by CityScene.cs) and scene_atlas.png, streets.mesh
(ground only) and surfaces.png (copied from the Warsaw map), map.bin (Rock under buildings, Road on the
avenues), map.yaml, rules.yaml and map.png. Cells under roofs block movement; the roof heights go into
the scene file for the camera's collision.

scene.mesh, little endian:
  "WSCN" u32 version=2
  u32 meshCount, u32 vertexTotal; per mesh u32 firstVertex, u32 vertexCount (unindexed triangles)
  vertexTotal x (f32 x, y, z, nx, ny, nz, u, v, rect x, y, w, h)      mesh-local, rect in atlas UV
  u32 modelCount; per model f32 min[3], max[3] (world px around its origin), u32 batchCount,
      per batch u32 mesh, u32 firstInstance, u32 instanceCount
  u32 instanceTotal; per instance 12 f32: the rows of a 3x4 matrix, mesh -> model, world px
  u32 placementCount; per placement u32 model, f32 x, z (world px), yaw (rad), mirror (+-1)
  u32 cellsWide, cellsHigh; f32 height per cell (world px, -inf where open)

Usage: python build_city_map.py <tiles dir> <Warsaw map dir (for surfaces.png)> <out map dir>
"""
import hashlib
import json
import math
import os
import random
import shutil
import struct
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "warsaw"))
import build_streets as bs  # noqa: E402

CELL_M, TILE_PX = 8.0, 24
PX_PER_M = TILE_PX / CELL_M
CELLS, BORDER = 128, 1
SIDE = CELLS + 2 * BORDER
BLOCK_M, GRID = 256.0, 4
BLOCK_PX = BLOCK_M * PX_PER_M
LO, HI = BORDER * TILE_PX, BORDER * TILE_PX + CELLS * TILE_PX
AVENUE_M = 14.0
SEED = 2026
GEN_BLOCKS_M = (-336.0, -114.0, 114.0, 336.0)   # block centres of the generator's 228 m road grid (tile metres)
GEN_HALF_M = 114.0                              # half the road spacing: instances nearer their block are kept
GEN_STRETCH = BLOCK_M / 228.0                   # generator blocks widened to the map's (storeys keep 3 m)

ABANDONED = ["abandoned_11"]   # more variants: export them and list them here
CENTRE = {(1, 1): (0.0, 1.0), (2, 1): (0.0, -1.0), (1, 2): (math.pi, -1.0), (2, 2): (math.pi, 1.0)}
CORNERS = [(0, 0), (3, 0), (0, 3), (3, 3)]

ROOF_UP, ROOF_MIN_M, ROOF_COVER = 0.7, 2.5, 0.3   # up-facing, above this height, this share of a cell blocks it
ROCK, CLEAR, ROAD_TILES = 216, 255, (227, 228)
SLOT, COLOUR_CELL, ATLAS_W = 512, 8, 8192


def block_centre(i, j):
    return LO + (i + 0.5) * BLOCK_PX, LO + (j + 0.5) * BLOCK_PX


# --- Tiles ----------------------------------------------------------------------------------------
def bounds(pos, first, count, inst_mesh, inst):
    """World box of a model: every instance's mesh box corners, transformed."""
    lo_m = np.array([pos[f:f + c].min(axis=0) for f, c in zip(first, count)])
    hi_m = np.array([pos[f:f + c].max(axis=0) for f, c in zip(first, count)])
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    for k in range(8):
        corner = np.where([(k >> i) & 1 for i in range(3)], hi_m, lo_m)[inst_mesh]
        w = np.einsum("nij,nj->ni", inst[:, :, :3], corner) + inst[:, :, 3]
        lo, hi = np.minimum(lo, w.min(axis=0)), np.maximum(hi, w.max(axis=0))
    return lo, hi


def clip_square(tri, attrs, half):
    """Sutherland-Hodgman clip of triangles (n, 3, 3 xyz) to |x|, |z| <= half, carrying per-vertex attrs
    (n, 3, k) along; returns the pieces as triangles."""
    out_t, out_a = [], []
    for t, a in zip(tri, attrs):
        poly = [np.concatenate([t[i], a[i]]) for i in range(3)]
        for axis, sign in ((0, 1), (0, -1), (2, 1), (2, -1)):
            if not poly:
                break
            res = []
            for i, p in enumerate(poly):
                q = poly[(i + 1) % len(poly)]
                dp, dq = half - sign * p[axis], half - sign * q[axis]
                if dp >= 0:
                    res.append(p)
                if (dp >= 0) != (dq >= 0):
                    res.append(p + (q - p) * (dp / (dp - dq)))
            poly = res
        for i in range(1, len(poly) - 1):
            for v in (poly[0], poly[i], poly[i + 1]):
                out_t.append(v[:3])
                out_a.append(v[3:])
    return np.array(out_t, np.float32).reshape(-1, 3), np.array(out_a, np.float32).reshape(-1, attrs.shape[-1])


def load_window(tile, name, cx, cz, rnd):
    """One generator block centred at (cx, cz) tile metres as a model: its instances (the ground's eight
    stacked copies reduced to one, clipped to the avenues' edge) recentred and stretched to BLOCK_M."""
    d, meta = tile
    stretch = np.diag([GEN_STRETCH, 1.0, GEN_STRETCH])
    t = d["inst_mat"][:, :, 3]
    ground = int(np.argmax(d["mesh_count"]))
    keep = (np.abs(t[:, 0] - cx) < GEN_HALF_M) & (np.abs(t[:, 2] - cz) < GEN_HALF_M) & (d["inst_mesh"] != ground)
    inst = d["inst_mat"][keep].astype(np.float64)
    inst[:, :, 3] -= [cx, 0.0, cz]
    inst = np.einsum("ij,njk->nik", stretch, inst)
    inst_mesh = d["inst_mesh"][keep]

    # The ground: first copy, in tile metres, clipped to the block plus its sidewalks.
    g = d["inst_mat"][np.nonzero(d["inst_mesh"] == ground)[0][0]].astype(np.float64)
    f, c = d["mesh_first"][ground], d["mesh_count"][ground]
    p = d["pos"][f:f + c] @ g[:, :3].T + g[:, 3] - [cx, 0.0, cz]
    n = d["nrm"][f:f + c] @ g[:, :3].T
    attrs = np.hstack([n, d["uv"][f:f + c], d["mat"][f:f + c, None]]).reshape(-1, 3, 6)
    half = (BLOCK_M - AVENUE_M) / 2 / GEN_STRETCH
    gp, ga = clip_square(p.reshape(-1, 3, 3), attrs, half)
    gp = gp @ stretch.T
    pos = np.concatenate([d["pos"], gp]).astype(np.float32)
    nrm = np.concatenate([d["nrm"], ga[:, :3]]).astype(np.float32)
    uv = np.concatenate([d["uv"], ga[:, 3:5]]).astype(np.float32)
    mat = np.concatenate([d["mat"], np.rint(ga[:, 5]).astype(np.int32)])
    first = np.append(d["mesh_first"], len(d["pos"]))
    count = np.append(d["mesh_count"], len(gp))
    inst_mesh = np.append(inst_mesh, len(first) - 1).astype(np.int32)
    inst = np.concatenate([inst, np.hstack([np.eye(3), np.zeros((3, 1))])[None]])
    lo, hi = bounds(pos, first, count, inst_mesh, inst)
    return {"name": name, "pos": pos, "nrm": nrm, "uv": uv, "mat": mat, "first": first, "count": count,
            "inst_mesh": inst_mesh, "inst": (inst * PX_PER_M).astype(np.float32), "materials": meta["materials"],
            "lo": lo * PX_PER_M, "hi": hi * PX_PER_M, "dir": meta["dir"]}


def load_tile(tiles, name):
    d = dict(np.load(os.path.join(tiles, name + ".npz")))
    with open(os.path.join(tiles, name + ".json")) as f:
        meta = json.load(f)
    meta["dir"] = tiles
    return d, meta


def load_model(tiles, name, shift=(0.0, 0.0)):
    """A tile's meshes and instances, with instance matrices in world px around the model origin."""
    d = np.load(os.path.join(tiles, name + ".npz"))
    with open(os.path.join(tiles, name + ".json")) as f:
        meta = json.load(f)
    inst = d["inst_mat"].astype(np.float64)
    inst[:, 0, 3] -= shift[0]
    inst[:, 2, 3] -= shift[1]
    inst *= PX_PER_M
    lo = (np.array(meta["min"]) - [shift[0], 0, shift[1]]) * PX_PER_M
    hi = (np.array(meta["max"]) - [shift[0], 0, shift[1]]) * PX_PER_M
    return {"name": name, "pos": d["pos"], "nrm": d["nrm"], "uv": d["uv"], "mat": d["mat"],
            "first": d["mesh_first"], "count": d["mesh_count"], "inst_mesh": d["inst_mesh"],
            "inst": inst.astype(np.float32), "materials": meta["materials"], "lo": lo, "hi": hi, "dir": tiles}


class Atlas:
    """Base-colour images in SLOT x SLOT cells (deduplicated by content), flat colours in small cells."""

    def __init__(self):
        self.images, self.image_slot, self.colours = [], {}, {}

    def add(self, tiles, material):
        if material["image"]:
            path = os.path.join(tiles, material["image"])
            with open(path, "rb") as f:
                key = (hashlib.md5(f.read()).hexdigest(), bool(material["alpha"]))
            if key not in self.image_slot:
                self.image_slot[key] = len(self.images)
                self.images.append((path, key[1]))
            return ("image", self.image_slot[key])
        c = tuple(int(round(min(max(x, 0.0), 1.0) * 255)) for x in material["color"])
        self.colours.setdefault(c, len(self.colours))
        return ("colour", self.colours[c])

    def layout(self):
        per_slot = (SLOT // COLOUR_CELL) ** 2
        self.colour_slots = -(-len(self.colours) // per_slot)
        slots = len(self.images) + self.colour_slots
        cols = ATLAS_W // SLOT
        rows = -(-slots // cols)
        self.height = 1 << max(rows * SLOT - 1, 1).bit_length()
        assert self.height <= 16384, f"{slots} atlas slots do not fit"

    def slot_xy(self, k):
        cols = ATLAS_W // SLOT
        return (k % cols) * SLOT, (k // cols) * SLOT

    def rect(self, ref):
        """(x, y, w, h) in atlas UV, and whether the UVs should be pinned to the cell centre."""
        kind, k = ref
        if kind == "image":
            x, y = self.slot_xy(k)
            return (x / ATLAS_W, y / self.height, SLOT / ATLAS_W, SLOT / self.height), False
        per_row = SLOT // COLOUR_CELL
        slot = len(self.images) + k // (per_row * per_row)
        sx, sy = self.slot_xy(slot)
        r = k % (per_row * per_row)
        x, y = sx + (r % per_row) * COLOUR_CELL, sy + (r // per_row) * COLOUR_CELL
        return (x / ATLAS_W, y / self.height, COLOUR_CELL / ATLAS_W, COLOUR_CELL / self.height), True

    def save(self, path):
        img = Image.new("RGBA", (ATLAS_W, self.height), (0, 0, 0, 255))
        for k, (src, alpha) in enumerate(self.images):
            tile = Image.open(src).convert("RGBA").resize((SLOT, SLOT), Image.LANCZOS)
            if not alpha:
                tile.putalpha(255)
            img.paste(tile, self.slot_xy(k))
        per_row = SLOT // COLOUR_CELL
        for c, k in self.colours.items():
            slot = len(self.images) + k // (per_row * per_row)
            sx, sy = self.slot_xy(slot)
            r = k % (per_row * per_row)
            img.paste((*c, 255), (sx + (r % per_row) * COLOUR_CELL, sy + (r // per_row) * COLOUR_CELL,
                                  sx + (r % per_row + 1) * COLOUR_CELL, sy + (r // per_row + 1) * COLOUR_CELL))
        img.save(path)


# --- Blocking ---------------------------------------------------------------------------------------
def roof_samples(model):
    """Points (x, z world px around the model origin) with the roof area (m^2) and top height (px) they
    stand for: up-facing triangles above ROOF_MIN_M, big ones sampled every 2 m."""
    xs, zs, areas, tops = [], [], [], []
    pos = model["pos"]
    for mesh in range(len(model["first"])):
        sel = model["inst_mesh"] == mesh
        if not sel.any():
            continue
        f, c = model["first"][mesh], model["count"][mesh]
        tri = pos[f:f + c].reshape(-1, 3, 3).astype(np.float64)
        m = model["inst"][sel].astype(np.float64)
        w = np.einsum("nij,tkj->ntki", m[:, :, :3], tri) + m[:, None, None, :, 3]   # (inst, tri, 3, xyz) px
        e1, e2 = w[:, :, 1] - w[:, :, 0], w[:, :, 2] - w[:, :, 0]
        n = np.cross(e1, e2)
        length = np.linalg.norm(n, axis=-1)
        area = length / 2 / PX_PER_M ** 2
        up = np.abs(n[..., 1]) > ROOF_UP * np.maximum(length, 1e-9)
        top = w[..., 1].max(axis=-1)
        keep = up & (top > ROOF_MIN_M * PX_PER_M) & (area > 0.2)
        if not keep.any():
            continue
        w, area, top = w[keep], area[keep], top[keep]
        small = area <= 8.0
        cen = w[small].mean(axis=1)
        xs.append(cen[:, 0])
        zs.append(cen[:, 2])
        areas.append(area[small])
        tops.append(top[small])
        for t, a, h in zip(w[~small], area[~small], top[~small]):
            k = int(math.ceil(math.sqrt(a) / 2.0))
            uu, vv = np.meshgrid((np.arange(k) + 0.5) / k, (np.arange(k) + 0.5) / k)
            inside = uu + vv <= 1.0
            if not inside.any():
                inside[0, 0] = True
            u, v = uu[inside], vv[inside]
            p = t[0] + u[:, None] * (t[1] - t[0]) + v[:, None] * (t[2] - t[0])
            xs.append(p[:, 0])
            zs.append(p[:, 2])
            areas.append(np.full(len(u), a / len(u)))
            tops.append(np.full(len(u), h))
    return np.concatenate(xs), np.concatenate(zs), np.concatenate(areas), np.concatenate(tops)


def place(x, z, px, pz, yaw, mirror):
    """Model-local px -> world px (scene.vert's placement)."""
    x = x * mirror
    c, s = math.cos(yaw), math.sin(yaw)
    return c * x + s * z + px, -s * x + c * z + pz


# --- Ground -----------------------------------------------------------------------------------------
def avenues():
    """Avenue centre lines (world px) on the block boundaries, none through the iCity centre."""
    lines = []
    for k in range(1, GRID):
        v = LO + k * BLOCK_PX
        spans = [(LO, HI)] if k != 2 else [(LO, LO + BLOCK_PX), (LO + 3 * BLOCK_PX, HI)]
        for a, b in spans:
            lines.append([(v, a), (v, b)])
            lines.append([(a, v), (b, v)])
    return lines


def build_ground():
    bs.LO, bs.HI = LO, HI
    g = bs.Ground()
    g.polygon([(LO, LO), (HI, LO), (HI, HI), (LO, HI)], "slabs")
    for i, j in CORNERS:
        x, z = block_centre(i, j)
        h = BLOCK_PX / 2 - AVENUE_M / 2 * PX_PER_M
        g.polygon([(x - h, z - h), (x + h, z - h), (x + h, z + h), (x - h, z + h)], "soil")
    lines = avenues()
    junctions = [(LO + a * BLOCK_PX, LO + b * BLOCK_PX) for a in range(GRID + 1) for b in range(GRID + 1)]
    hash_ = bs.Hash(junctions, 64 * PX_PER_M)
    for line in lines:
        g.ribbon(line, AVENUE_M, "asphalt")
    for line in lines:
        bs.kerbs(g, line, AVENUE_M / 2, 0.0, hash_)
        bs.dashes(g, line, [0.0], hash_)
    return g, lines


# --- Writing ----------------------------------------------------------------------------------------
def write_scene(path, models, atlas, placements, heights):
    verts, mesh_ranges, model_rows, inst_rows = [], [], [], []
    base = inst_base = 0
    for model in models:
        refs = [atlas.rect(atlas.add(model["dir"], m)) for m in model["materials"]]
        rect = np.array([r for r, _ in refs], np.float32)[model["mat"]]
        pinned = np.array([p for _, p in refs], bool)[model["mat"]]
        uv = model["uv"].copy()
        uv[pinned] = 0.5
        verts.append(np.hstack([model["pos"] * 1.0, model["nrm"], uv, rect]).astype("<f4"))
        mesh_offset = len(mesh_ranges)
        for f, c in zip(model["first"], model["count"]):
            mesh_ranges.append((base + int(f), int(c)))
        base += len(model["pos"])
        order = np.argsort(model["inst_mesh"], kind="stable")
        meshes = model["inst_mesh"][order]
        batches = []
        for mesh in np.unique(meshes):
            idx = np.nonzero(meshes == mesh)[0]
            batches.append((mesh_offset + int(mesh), inst_base + int(idx[0]), len(idx)))
        inst_rows.append(model["inst"][order].reshape(-1, 12).astype("<f4"))
        inst_base += len(order)
        model_rows.append((model["lo"], model["hi"], batches))
    with open(path, "wb") as f:
        f.write(b"WSCN" + struct.pack("<III", 2, len(mesh_ranges), base))
        for first, count in mesh_ranges:
            f.write(struct.pack("<II", first, count))
        for v in verts:
            f.write(v.tobytes())
        f.write(struct.pack("<I", len(model_rows)))
        for lo, hi, batches in model_rows:
            f.write(struct.pack("<6fI", *lo, *hi, len(batches)))
            for b in batches:
                f.write(struct.pack("<III", *b))
        f.write(struct.pack("<I", inst_base))
        for rows in inst_rows:
            f.write(rows.tobytes())
        f.write(struct.pack("<I", len(placements)))
        for p in placements:
            f.write(struct.pack("<I4f", *p))
        f.write(struct.pack("<II", SIDE, SIDE))
        f.write(heights.astype("<f4").tobytes())
    return base, inst_base


def write_bin(path, blocked, road):
    with open(path, "wb") as f:
        f.write(struct.pack("<BHHIII", 2, SIDE, SIDE, 17, 0, 17 + 3 * SIDE * SIDE))
        for x in range(SIDE):
            for y in range(SIDE):
                if blocked[y, x]:
                    f.write(struct.pack("<HB", ROCK, 0))
                elif road[y, x]:
                    f.write(struct.pack("<HB", ROAD_TILES[(x + y) & 1], 0))
                else:
                    f.write(struct.pack("<HB", CLEAR, (x * 7 + y * 13) % 16))
        f.write(b"\0" * (3 * SIDE * SIDE))


MAP_YAML = """MapFormat: 12

RequiresMod: ww3mod

Title: Ruined City WW3

Author: Idzikowski20 (city kits: iCity; abandoned-city generator; zoning after Curtis Holt's City Scatter Tool)

Tileset: TEMPERAT

MapSize: {side},{side}

Bounds: {b},{b},{cells},{cells}

Visibility: Lobby

Categories: Conquest

Rules: rules.yaml

Players:
	PlayerReference@Neutral:
		Name: Neutral
		OwnsWorld: True
		NonCombatant: True
		Faction: Random
	PlayerReference@Creeps:
		Name: Creeps
		NonCombatant: True
		Faction: Random
		Enemies: Multi0, Multi1, Multi2, Multi3
"""

RULES_YAML = """World:
	LuaScript:
	MapBuildRadius:
		AllyBuildRadiusCheckboxEnabled: True
	MapOptions:
		ShortGameCheckboxEnabled: True
		TechLevelDropdownVisible: True
		FogCheckboxVisible: True
		ExploredMapCheckboxVisible: True
		CratesCheckboxVisible: True
		StartingUnitsDropdownVisible: True
		StartingCashDropdownVisible: True
	# Generated city (tools/city/build_city_map.py): textured models in scene.mesh, ground in streets.mesh.
	CityMap:
		Meshes:
		Ground:
		Facades:
		Roofs:
"""


def write_yaml(path, spawns):
    lines = [MAP_YAML.format(side=SIDE, b=BORDER, cells=CELLS)]
    for k in range(4):
        lines.append(f"\tPlayerReference@Multi{k}:\n\t\tName: Multi{k}\n\t\tPlayable: True\n\t\tFaction: Random\n\t\tEnemies: Creeps\n")
    lines.append("\nActors:\n")
    for n, (x, y) in enumerate(spawns):
        lines.append(f"\tActor{n}: mpspawn\n\t\tOwner: Neutral\n\t\tLocation: {x},{y}\n")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(lines))


def main():
    tiles, warsaw_dir, map_dir = sys.argv[1:4]
    os.makedirs(map_dir, exist_ok=True)
    rnd = random.Random(SEED)

    block = load_model(tiles, "icity_block")
    centre = ((block["lo"][0] + block["hi"][0]) / 2 / PX_PER_M, (block["lo"][2] + block["hi"][2]) / 2 / PX_PER_M)
    block = load_model(tiles, "icity_block", centre)
    tower = load_model(tiles, "icity_tower", centre)
    models = [block, tower]
    placements = []
    for (i, j), (yaw, mirror) in CENTRE.items():
        placements.append((0, *block_centre(i, j), yaw, mirror))
    placements.append((1, *block_centre(1, 1), *CENTRE[(1, 1)]))

    abandoned = [load_tile(tiles, n) for n in ABANDONED]
    for i in range(GRID):
        for j in range(GRID):
            if (i, j) in CENTRE or (i, j) in CORNERS:
                continue
            k = rnd.randrange(len(abandoned))
            bx, bz = rnd.choice(GEN_BLOCKS_M), rnd.choice(GEN_BLOCKS_M)
            models.append(load_window(abandoned[k], f"{ABANDONED[k]}@{bx:+.0f},{bz:+.0f}", bx, bz, rnd))
            placements.append((len(models) - 1, *block_centre(i, j), rnd.randrange(4) * math.pi / 2,
                               rnd.choice((1.0, -1.0))))
    for m in models:
        print(f"{m['name']}: {len(m['first'])} meshes, {len(m['inst_mesh']):,} instances, "
              f"bounds {np.round(m['lo'] / PX_PER_M).tolist()} .. {np.round(m['hi'] / PX_PER_M).tolist()} m", flush=True)


    print("blocking ...", flush=True)
    cover = np.zeros((SIDE, SIDE))
    heights = np.full((SIDE, SIDE), -np.inf)
    samples = {}
    for model, px, pz, yaw, mirror in placements:
        if model not in samples:
            samples[model] = roof_samples(models[model])
        x, z, area, top = samples[model]
        wx, wz = place(x, z, px, pz, yaw, mirror)
        cx = np.clip((wx // TILE_PX).astype(int), 0, SIDE - 1)
        cy = np.clip((wz // TILE_PX).astype(int), 0, SIDE - 1)
        np.add.at(cover, (cy, cx), area)
        np.maximum.at(heights, (cy, cx), top)
    blocked = cover >= ROOF_COVER * CELL_M * CELL_M
    blocked[[0, -1], :] = blocked[:, [0, -1]] = False
    heights[~blocked] = -np.inf

    road = np.zeros((SIDE, SIDE), bool)
    centres = (np.arange(SIDE) + 0.5) * TILE_PX
    for line in avenues():
        (x0, z0), (x1, z1) = line
        half = AVENUE_M / 2 * PX_PER_M
        xs = (centres >= min(x0, x1) - half) & (centres <= max(x0, x1) + half)
        zs = (centres >= min(z0, z1) - half) & (centres <= max(z0, z1) + half)
        road |= zs[:, None] & xs[None, :]

    print("atlas and scene ...", flush=True)
    atlas = Atlas()
    for m in models:
        for mat in m["materials"]:
            atlas.add(m["dir"], mat)
    atlas.layout()
    vertex_total, instance_total = write_scene(os.path.join(map_dir, "scene.mesh"), models, atlas, placements,
                                               np.where(blocked, heights, -np.inf).astype(np.float32))
    atlas.save(os.path.join(map_dir, "scene_atlas.png"))

    print("ground ...", flush=True)
    ground, _ = build_ground()
    bs.write(os.path.join(map_dir, "streets.mesh"), ground, [], [], [bs.SURFACE_SIZE[n] for n in bs.SURFACES])
    shutil.copyfile(os.path.join(warsaw_dir, "surfaces.png"), os.path.join(map_dir, "surfaces.png"))

    spawns = [tuple(int(v // TILE_PX) for v in block_centre(i, j)) for i, j in CORNERS]
    assert not any(blocked[y, x] for x, y in spawns), spawns
    write_bin(os.path.join(map_dir, "map.bin"), blocked, road)
    write_yaml(os.path.join(map_dir, "map.yaml"), spawns)
    with open(os.path.join(map_dir, "rules.yaml"), "w", encoding="utf-8", newline="\n") as f:
        f.write(RULES_YAML)

    preview = np.zeros((CELLS, CELLS, 3), np.uint8)
    inner = (slice(BORDER, SIDE - BORDER),) * 2
    preview[:] = (112, 110, 104)
    preview[road[inner]] = (64, 64, 66)
    preview[blocked[inner]] = (150, 138, 120)
    for i, j in CORNERS:
        x, z = (int((v - LO) // TILE_PX) for v in block_centre(i, j))
        preview[z - 14:z + 15, x - 14:x + 15] = (96, 84, 66)
    Image.fromarray(preview).save(os.path.join(map_dir, "map.png"))

    drawn = sum(int(models[m]["count"][models[m]["inst_mesh"]].sum()) // 3 for m, *_ in placements)
    print(f"done: {len(placements)} placements, {vertex_total:,} vertices, {instance_total:,} instances, "
          f"{drawn:,} triangles if all drawn, atlas {len(atlas.images)} images + {len(atlas.colours)} colours "
          f"({ATLAS_W}x{atlas.height}), {int(blocked.sum())} blocked cells, spawns {spawns}", flush=True)


if __name__ == "__main__":
    main()

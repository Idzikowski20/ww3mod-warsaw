"""Downloads the GUGiK orthophoto of the map square (2048 m around PKiN) at 0.5 m per pixel.

GUGiK WMS (verified 2026-10-27): HighResolution layer `Raster`, WMS 1.3.0, EPSG:2180 with the axis order
north,east in BBOX. 2048 px requests time out, so the square is fetched as 4x4 tiles of 1024 px and stitched.

Usage: python fetch_ortho.py <out.png>
"""
import io
import sys
import time
import urllib.request

from PIL import Image

from build_city import E_MIN, N_MAX, SIZE_M

URL = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/HighResolution"
TILES = 4
TILE_PX = 1024


def fetch(min_e, min_n, max_e, max_n):
    query = ("SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0&LAYERS=Raster&STYLES=&CRS=EPSG:2180"
             f"&BBOX={min_n},{min_e},{max_n},{max_e}&WIDTH={TILE_PX}&HEIGHT={TILE_PX}&FORMAT=image/jpeg")
    for attempt in range(5):
        try:
            req = urllib.request.Request(f"{URL}?{query}", headers={"User-Agent": "ww3mod-warsaw map builder"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            return Image.open(io.BytesIO(data)).convert("RGB")
        except Exception as ex:  # network or a WMS error page that is not an image
            print(f"    retry {attempt + 1}: {ex}", flush=True)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("tile failed after 5 attempts")


def main():
    out = Image.new("RGB", (TILES * TILE_PX, TILES * TILE_PX))
    step = SIZE_M / TILES
    for row in range(TILES):
        for col in range(TILES):
            min_e = E_MIN + col * step
            max_n = N_MAX - row * step
            print(f"  tile {row},{col}", flush=True)
            out.paste(fetch(min_e, max_n - step, min_e + step, max_n), (col * TILE_PX, row * TILE_PX))
    out.save(sys.argv[1])
    print("saved", sys.argv[1])


if __name__ == "__main__":
    main()

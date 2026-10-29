"""
Overture buildings API (FastAPI).
GET /buildings?minx=&miny=&maxx=&maxy=  ->  GeoJSON FeatureCollection

Same method as the AMALI footprint scripts: overturemaps.record_batch_reader("building", bbox=...).
"""
import json
import math

import overturemaps
import shapely
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

MAX_BBOX_KM2 = 400  # server-side safety limit (the web page has its own limit)

app = FastAPI(title="Overture buildings API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


def bbox_km2(minx, miny, maxx, maxy):
    lat = math.radians((miny + maxy) / 2)
    return abs(maxx - minx) * 111.32 * math.cos(lat) * abs(maxy - miny) * 110.57


def table_to_geojson(table):
    """Convert an Overture pyarrow table to a GeoJSON FeatureCollection (dict)."""
    cols = set(table.column_names)
    geoms = shapely.from_wkb(table.column("geometry").to_pylist())
    def col(name):
        return table.column(name).to_pylist() if name in cols else [None] * table.num_rows
    ids, heights, floors, classes = col("id"), col("height"), col("num_floors"), col("class")
    features = []
    for g, i, h, f, c in zip(geoms, ids, heights, floors, classes):
        if g is None or g.is_empty:
            continue
        features.append({
            "type": "Feature",
            "properties": {"id": i, "height": h, "num_floors": f, "class": c},
            "geometry": json.loads(shapely.to_geojson(shapely.set_precision(g, 1e-7))),
        })
    return {"type": "FeatureCollection", "features": features}


@app.get("/")
def health():
    return {"status": "ok"}


@app.get("/buildings")
def buildings(minx: float, miny: float, maxx: float, maxy: float):
    if not (-180 <= minx < maxx <= 180 and -90 <= miny < maxy <= 90):
        raise HTTPException(400, "Invalid bbox")
    if bbox_km2(minx, miny, maxx, maxy) > MAX_BBOX_KM2:
        raise HTTPException(400, f"Bounding box larger than {MAX_BBOX_KM2} km2")
    reader = overturemaps.record_batch_reader("building", bbox=(minx, miny, maxx, maxy))
    if reader is None:
        return {"type": "FeatureCollection", "features": []}
    return table_to_geojson(reader.read_all())

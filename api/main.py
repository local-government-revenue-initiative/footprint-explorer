"""
Overture buildings API (FastAPI).
GET /buildings?minx=&miny=&maxx=&maxy=  ->  GeoJSON FeatureCollection

Same method as the AMALI footprint scripts: overturemaps.record_batch_reader("building", bbox=...).
"""
import json
import math

import pyarrow as pa
import shapely
from overturemaps.core import _prepare_query
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

MAX_BBOX_KM2 = 400  # server-side safety limit (the web page has its own limit)

pa.set_cpu_count(1)
pa.set_io_thread_count(4)

app = FastAPI(title="Overture buildings API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


def bbox_km2(minx, miny, maxx, maxy):
    lat = math.radians((miny + maxy) / 2)
    return abs(maxx - minx) * 111.32 * math.cos(lat) * abs(maxy - miny) * 110.57


COLUMNS = ["id", "height", "num_floors", "class", "geometry"]


def batch_to_features(batch):
    """Convert one pyarrow RecordBatch to a list of GeoJSON features."""
    cols = set(batch.schema.names)
    geoms = shapely.from_wkb(batch.column("geometry").to_pylist())
    def col(name):
        return batch.column(name).to_pylist() if name in cols else [None] * batch.num_rows
    ids, heights, floors, classes = col("id"), col("height"), col("num_floors"), col("class")
    out = []
    for g, i, h, f, c in zip(geoms, ids, heights, floors, classes):
        if g is None or g.is_empty:
            continue
        out.append({
            "type": "Feature",
            "properties": {"id": i, "height": h, "num_floors": f, "class": c},
            "geometry": json.loads(shapely.to_geojson(shapely.set_precision(g, 1e-7))),
        })
    return out


def stream_features(dataset, filter_expr):
    """Read the dataset batch by batch, only the needed columns, to keep memory low."""
    features = []
    batches = dataset.to_batches(
        filter=filter_expr,
        columns=COLUMNS,
        use_threads=False,
        batch_size=8192,
        batch_readahead=1,
        fragment_readahead=1,
    )
    for batch in batches:
        if batch.num_rows:
            features.extend(batch_to_features(batch))
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
    # stac=True: use the Overture STAC index to open only the files that intersect the bbox
    # (instead of scanning the metadata of every building file, which exhausts a 512 MB instance).
    prepared = _prepare_query("building", bbox=(minx, miny, maxx, maxy), stac=True)
    if prepared is None:
        return {"type": "FeatureCollection", "features": []}
    dataset, filter_expr = prepared
    return stream_features(dataset, filter_expr)

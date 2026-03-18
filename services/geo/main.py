from datetime import datetime, timezone
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient
from pymongo.database import Database

from config import settings
from verification import level1_speed_check, level3_gap_penalty, update_trust_score


def get_db() -> Database:
    client = MongoClient(settings.mongodb_uri)
    return client[settings.mongodb_db]


app = FastAPI(title="Geo Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LocationUpdateBody(BaseModel):
    courier_id: str
    lat: float
    lon: float
    source: str = "gps"
    timestamp: datetime | None = None


class LocationResponse(BaseModel):
    lat: float
    lon: float
    geo_trust_score: float
    verified: bool


@app.on_event("startup")
async def startup():
    db = get_db()
    db["locations"].create_index([("courier_id", 1), ("timestamp", -1)])
    db["courier_trust"].create_index("courier_id", unique=True)


@app.post("/location")
async def report_location(body: LocationUpdateBody):
    db = get_db()
    ts = body.timestamp or datetime.now(timezone.utc)
    coll = db["locations"]
    trust_coll = db["courier_trust"]
    prev = coll.find_one(
        {"courier_id": body.courier_id},
        sort=[("timestamp", -1)],
        projection={"lat": 1, "lon": 1, "timestamp": 1},
    )
    prev_ts = prev["timestamp"] if prev else None
    prev_lat = prev.get("lat") if prev else None
    prev_lon = prev.get("lon") if prev else None
    speed_ok, speed_kmh = level1_speed_check(
        body.lat, body.lon, ts, prev_lat, prev_lon, prev_ts
    )
    gap_penalty = level3_gap_penalty(prev_ts, ts)
    trust_doc = trust_coll.find_one({"courier_id": body.courier_id})
    current_trust = trust_doc["score"] if trust_doc else 1.0
    new_trust = update_trust_score(current_trust, speed_ok, gap_penalty, multi_source_ok=True)
    trust_coll.update_one(
        {"courier_id": body.courier_id},
        {"$set": {"courier_id": body.courier_id, "score": new_trust, "updated_at": ts}},
        upsert=True,
    )
    coll.insert_one({
        "courier_id": body.courier_id,
        "lat": body.lat,
        "lon": body.lon,
        "source": body.source,
        "timestamp": ts,
        "speed_kmh": speed_kmh,
        "accepted": speed_ok,
        "verified": speed_ok,
    })
    return {
        "accepted": speed_ok,
        "geo_trust_score": new_trust,
        "speed_kmh": speed_kmh,
    }


@app.get("/location/{courier_id}")
async def get_verified_location(courier_id: str):
    db = get_db()
    loc = db["locations"].find_one(
        {"courier_id": courier_id, "accepted": True},
        sort=[("timestamp", -1)],
        projection={"lat": 1, "lon": 1, "timestamp": 1},
    )
    trust_doc = db["courier_trust"].find_one({"courier_id": courier_id})
    score = trust_doc["score"] if trust_doc else 1.0
    if not loc:
        return {"lat": None, "lon": None, "geo_trust_score": score, "verified": False}
    return {
        "lat": loc["lat"],
        "lon": loc["lon"],
        "geo_trust_score": score,
        "verified": True,
    }


class BatchRequest(BaseModel):
    courier_ids: list[str]


@app.post("/location/batch")
async def get_verified_locations_batch(body: BatchRequest):
    courier_ids = body.courier_ids
    db = get_db()
    result = {}
    for cid in courier_ids:
        loc = db["locations"].find_one(
            {"courier_id": cid, "accepted": True},
            sort=[("timestamp", -1)],
            projection={"lat": 1, "lon": 1},
        )
        trust_doc = db["courier_trust"].find_one({"courier_id": cid})
        score = trust_doc["score"] if trust_doc else 1.0
        result[cid] = {
            "lat": loc["lat"] if loc else None,
            "lon": loc["lon"] if loc else None,
            "geo_trust_score": score,
            "verified": loc is not None,
        }
    return result


@app.get("/health")
async def health():
    return {"status": "ok"}

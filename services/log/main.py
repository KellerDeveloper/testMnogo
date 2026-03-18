import json
from datetime import datetime
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from clickhouse_driver import Client

from config import settings
from db import get_client, init_schema


app = FastAPI(title="Decision Log Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    try:
        client = get_client()
        init_schema(client)
        try:
            client.execute("ALTER TABLE dispatch_decisions MODIFY COLUMN assigned_to String")
        except Exception:
            pass
    except Exception:
        pass


def _serialize(obj):
    if isinstance(obj, dict):
        return json.dumps(obj, default=str)
    return str(obj) if obj is not None else ""


@app.post("/decisions", status_code=201)
async def create_decision(body: dict):
    client = get_client()
    decision_id = body.get("decision_id")
    order_id = body.get("order_id")
    ts = body.get("timestamp")
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    assigned_to = body.get("assigned_to")
    carrier_type = body.get("carrier_type", "")
    assignment_source = body.get("assignment_source", "")
    algorithm_version = body.get("algorithm_version", "")
    scores = body.get("scores") or {}
    winner_score = float(body.get("winner_score", 0))
    reason_summary = body.get("reason_summary", "")
    factors = body.get("factors") or []
    context_snapshot = body.get("context_snapshot") or {}
    override_info = body.get("override_info")
    operator_id = ""
    override_reason = ""
    if override_info and isinstance(override_info, dict):
        operator_id = override_info.get("operator_id", "")
        override_reason = override_info.get("override_reason", "")
    client.execute(
        """
        INSERT INTO dispatch_decisions (
            decision_id, order_id, timestamp, assigned_to, carrier_type,
            assignment_source, algorithm_version, scores, winner_score,
            reason_summary, factors, context_snapshot, override_info,
            operator_id, override_reason
        ) VALUES
        """,
        [(
            decision_id, order_id, ts, assigned_to, carrier_type,
            assignment_source, algorithm_version, _serialize(scores), winner_score,
            reason_summary, _serialize(factors), _serialize(context_snapshot), _serialize(override_info),
            operator_id, override_reason,
        )],
    )
    return {"decision_id": decision_id, "order_id": order_id}


@app.get("/decisions")
async def list_decisions(
    kitchen_id: UUID | None = Query(None),
    order_id: UUID | None = Query(None),
    courier_id: UUID | None = Query(None),
    assignment_source: str | None = Query(None),
    from_ts: datetime | None = Query(None),
    to_ts: datetime | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    client = get_client()
    q = "SELECT decision_id, order_id, timestamp, assigned_to, carrier_type, assignment_source, algorithm_version, winner_score, reason_summary FROM dispatch_decisions WHERE 1=1"
    params: dict[str, object] = {}
    if order_id:
        q += " AND order_id = %(order_id)s"
        params["order_id"] = str(order_id)
    if assignment_source:
        q += " AND assignment_source = %(assignment_source)s"
        params["assignment_source"] = assignment_source
    if from_ts:
        q += " AND timestamp >= %(from_ts)s"
        params["from_ts"] = from_ts
    if to_ts:
        q += " AND timestamp <= %(to_ts)s"
        params["to_ts"] = to_ts
    if courier_id:
        q += " AND assigned_to = %(courier_id)s"
        params["courier_id"] = str(courier_id)
    q += " ORDER BY timestamp DESC LIMIT %(limit)s OFFSET %(offset)s"
    params["limit"] = limit
    params["offset"] = offset
    rows = client.execute(q, params)
    keys = ["decision_id", "order_id", "timestamp", "assigned_to", "carrier_type", "assignment_source", "algorithm_version", "winner_score", "reason_summary"]
    items = [dict(zip(keys, row)) for row in rows]
    for i in items:
        if i.get("timestamp"):
            i["timestamp"] = i["timestamp"].isoformat() if hasattr(i["timestamp"], "isoformat") else str(i["timestamp"])
    return {"items": items}


@app.get("/decisions/{decision_id}")
async def get_decision(decision_id: UUID):
    client = get_client()
    rows = client.execute(
        "SELECT decision_id, order_id, timestamp, assigned_to, carrier_type, assignment_source, algorithm_version, scores, winner_score, reason_summary, factors, context_snapshot, override_info FROM dispatch_decisions WHERE decision_id = %(decision_id)s",
        {"decision_id": str(decision_id)},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Decision not found")
    row = rows[0]
    keys = ["decision_id", "order_id", "timestamp", "assigned_to", "carrier_type", "assignment_source", "algorithm_version", "scores", "winner_score", "reason_summary", "factors", "context_snapshot", "override_info"]
    out = dict(zip(keys, row))
    if out.get("timestamp"):
        out["timestamp"] = out["timestamp"].isoformat() if hasattr(out["timestamp"], "isoformat") else str(out["timestamp"])
    for k in ("scores", "factors", "context_snapshot", "override_info"):
        if isinstance(out.get(k), str):
            try:
                out[k] = json.loads(out[k])
            except Exception:
                pass
    return out


@app.get("/decisions/analytics/override_rate")
async def override_rate(kitchen_id: UUID | None = Query(None), from_ts: datetime | None = Query(None), to_ts: datetime | None = Query(None)):
    client = get_client()
    q = "SELECT countIf(assignment_source = 'manual_override') AS overrides, count() AS total FROM dispatch_decisions WHERE 1=1"
    params: dict[str, object] = {}
    if from_ts:
        q += " AND timestamp >= %(from_ts)s"
        params["from_ts"] = from_ts
    if to_ts:
        q += " AND timestamp <= %(to_ts)s"
        params["to_ts"] = to_ts
    rows = client.execute(q, params)
    if not rows:
        return {"override_rate": 0.0, "overrides": 0, "total": 0}
    overrides, total = rows[0]
    rate = overrides / total if total else 0.0
    alert = rate > settings.override_alert_threshold
    return {"override_rate": rate, "overrides": overrides, "total": total, "alert": alert}


@app.get("/health")
async def health():
    return {"status": "ok"}

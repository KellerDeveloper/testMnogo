from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import settings

app = FastAPI(title="Notification Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AssignmentNotifyBody(BaseModel):
    order_id: str
    assigned_to: str
    carrier_type: str
    reason_summary: str = ""


@app.post("/notify/assignment")
async def notify_assignment(body: AssignmentNotifyBody):
    # In production: send push via FCM/APNs to assigned_to device
    # and/or broadcast to kitchen WebSocket
    if settings.push_enabled:
        pass  # push to body.assigned_to
    return {"sent": not settings.push_enabled, "order_id": body.order_id, "assigned_to": body.assigned_to}


@app.get("/health")
async def health():
    return {"status": "ok"}

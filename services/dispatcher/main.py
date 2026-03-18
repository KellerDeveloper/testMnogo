from fastapi import FastAPI

from config import settings

app = FastAPI(title="Dispatcher Service")


@app.get("/health")
async def health():
    return {"status": "ok", "shadow_mode": settings.shadow_mode}


# Worker is started separately: python -m worker or via uvicorn worker:run_worker
# For all-in-one we could run worker in background here

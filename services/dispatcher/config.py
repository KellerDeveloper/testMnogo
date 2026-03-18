from pathlib import Path
import sys

_P = Path(__file__).resolve()
REPO_ROOT = _P.parents[2] if len(_P.parents) >= 3 else _P.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379/0"
    rabbitmq_url: str = "amqp://dispatcher:dispatcher@localhost:5672/"
    order_exchange: str = "order_events"
    dispatch_exchange: str = "dispatch_events"
    order_lock_ttl: int = 30
    order_service_url: str = "http://localhost:8000"
    courier_service_url: str = "http://localhost:8001"
    geo_service_url: str = "http://localhost:8002"
    config_service_url: str = "http://localhost:8003"
    log_service_url: str = "http://localhost:8004"
    notification_service_url: str = "http://localhost:8005"
    gateway3pl_url: str = "http://localhost:8006"
    shadow_mode: bool = False  # If True, only log decision, do not assign

    class Config:
        env_file = ".env"


settings = Settings()

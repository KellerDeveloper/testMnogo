from pathlib import Path
import sys

_P = Path(__file__).resolve()
REPO_ROOT = _P.parents[2] if len(_P.parents) >= 3 else _P.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "dispatcher"
    max_speed_kmh: float = 60.0
    gap_penalty_minutes: int = 2
    trust_recovery_rate: float = 0.05
    trust_penalty_rate: float = 0.15

    class Config:
        env_file = ".env"


settings = Settings()

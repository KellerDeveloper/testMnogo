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
    # Для “московских реалий” мы делаем антифрод более терпимым к редким точкам:
    # при временных проблемах с навигацией/связью координаты могут прийти с задержкой,
    # а вычисленная скорость/разрыв времени не всегда отражают реальное перемещение.
    max_speed_kmh: float = 90.0
    gap_penalty_minutes: int = 5
    trust_recovery_rate: float = 0.05
    trust_penalty_rate: float = 0.15

    class Config:
        env_file = ".env"


settings = Settings()

from pathlib import Path
import sys

_P = Path(__file__).resolve()
REPO_ROOT = _P.parents[2] if len(_P.parents) >= 3 else _P.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # FCM/APNs would go here
    push_enabled: bool = False
    fcm_key: str = ""

    class Config:
        env_file = ".env"


settings = Settings()

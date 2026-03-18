from pathlib import Path
import sys

_P = Path(__file__).resolve()
REPO_ROOT = _P.parents[2] if len(_P.parents) >= 3 else _P.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = ""
    postgres_db: str = "postgres"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    class Config:
        env_file = (REPO_ROOT / ".env") if (REPO_ROOT / ".env").exists() else ".env"


settings = Settings()

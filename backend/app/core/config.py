"""Configuracion centralizada del backend, leida desde variables de entorno.

Las variables se documentan en /.env.example (raiz del repo). En desarrollo,
copia ese archivo a /.env (nunca versionado) y completa los valores reales.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> sube 3 niveles hasta la raiz del repo,
# independiente del directorio de trabajo desde el que se ejecute el proceso.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILE = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    """Variables de entorno del backend."""

    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "auto_cusco"
    db_user: str = "auto_cusco_app"
    db_password: str = ""

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuracion (cacheada) para toda la vida del proceso."""
    return Settings()

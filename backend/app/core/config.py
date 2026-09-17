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

# Las pruebas `postgres` y los scripts de medicion escriben filas unicas (configuracion
# de MOWA MES, supervisores, Speech original): solo corren contra una base con este
# sufijo, nunca contra la que se usa para trabajar. Ver docs/testing.md, seccion 4.
SUFIJO_BASE_PRUEBAS = "_test"


class Settings(BaseSettings):
    """Variables de entorno del backend."""

    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "auto_cusco"
    db_user: str = "auto_cusco_app"
    db_password: str = ""

    # Origenes del frontend permitidos por CORS, separados por coma. Vacio = sin CORS.
    cors_origenes: str = ""

    @property
    def origenes_cors(self) -> list[str]:
        return [origen.strip() for origen in self.cors_origenes.split(",") if origen.strip()]

    @property
    def database_url(self) -> str:
        # La contrasena se inserta sin codificar: `@` y `%XX` la corrompen.
        # Ver docs/setup.md, seccion 6.1 (solucion de fondo: URL.create).
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


def exigir_base_de_pruebas(settings: Settings) -> str | None:
    """None si `settings` apunta a una base de pruebas; si no, el motivo para no seguir."""
    if settings.db_name.endswith(SUFIJO_BASE_PRUEBAS):
        return None
    return (
        f"La base configurada es '{settings.db_name}', que no termina en "
        f"'{SUFIJO_BASE_PRUEBAS}'. Las pruebas postgres y los scripts de medicion escriben "
        "filas que se usan al trabajar en la app: apunta DB_NAME a la base de pruebas "
        "(p. ej. $env:DB_NAME = 'auto_cusco_test') o usa .\\scripts\\verificar.ps1 -ConBase. "
        "Ver docs/testing.md, seccion 4."
    )


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuracion (cacheada) para toda la vida del proceso."""
    return Settings()

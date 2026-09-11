"""Configuracion del engine y las sesiones de SQLAlchemy para PostgreSQL.

El engine se crea perezosamente (al primer uso) para no requerir una base
de datos disponible solo por importar el modulo -- util para tests que no
necesitan una conexion real (ver tests/test_health_api.py).
"""

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _session_factory


def get_db_session() -> Iterator[Session]:
    """Dependencia de FastAPI: entrega una sesion de BD y la cierra al finalizar."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()

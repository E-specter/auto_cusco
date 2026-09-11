"""Implementacion de DatabaseHealthPort contra PostgreSQL."""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.ports.health_port import DatabaseHealthPort


class PostgresHealthAdapter(DatabaseHealthPort):
    """Verifica la disponibilidad de PostgreSQL ejecutando un SELECT 1."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def is_available(self) -> bool:
        try:
            self._session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

"""Adaptador de entrada HTTP para el caso de uso de health-check."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.adapters.persistence.db import get_db_session
from app.adapters.persistence.postgres_health_adapter import PostgresHealthAdapter
from app.core.services.health_service import HealthService

router = APIRouter(prefix="/health", tags=["health"])


def get_health_service(session: Session = Depends(get_db_session)) -> HealthService:
    return HealthService(database_health_port=PostgresHealthAdapter(session))


class HealthRespuesta(BaseModel):
    api: bool
    database: bool
    ok: bool


@router.get("", response_model=HealthRespuesta)
def health(service: HealthService = Depends(get_health_service)) -> HealthRespuesta:
    """Reporta si la API y la base de datos estan disponibles."""
    status = service.check()
    return HealthRespuesta(api=status.api, database=status.database, ok=status.ok)

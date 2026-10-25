"""Composicion del mapeador de encabezados (RF-57 a RF-63).

Aqui se arma el servicio con su repositorio PostgreSQL, su lector y los catalogos que la aplicacion
ofrece (hoy, la sabana). Los endpoints `/mapeador` llegan en B3b; el arranque de la aplicacion ya
usa `crear_servicio_mapeador` para borrar los borradores vencidos.
"""

from app.adapters.input.lector_tabla import LectorTabla
from app.adapters.persistence.db import get_engine
from app.adapters.persistence.repositorio_mapeador_postgres import RepositorioMapeadorPostgres
from app.core.services.borradores_carga.servicio import MapeadorService
from app.core.services.ingesta_sabana.mapeable import CATALOGO_SABANA_MAPEABLE


def crear_servicio_mapeador() -> MapeadorService:
    return MapeadorService(
        RepositorioMapeadorPostgres(get_engine()), LectorTabla(), [CATALOGO_SABANA_MAPEABLE]
    )

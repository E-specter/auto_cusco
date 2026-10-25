"""Lo que comparten las pruebas del mapeador con la base real (B3a y B3b): limpieza y asignaciones.

La limpieza es un conjunto de sentencias que se construye aqui y no en cada archivo, para poder
compilarlas con el dialecto de PostgreSQL en una prueba sin base (`test_mapeador_sql.py`): un
parametro con el tipo equivocado (una fecha como texto) solo falla al ejecutarse contra PostgreSQL.

Cada archivo de pruebas trabaja con un prefijo propio (`b3a-`, `b3b-`) en el nombre de sus archivos
y en los encabezados que sube: la limpieza borra solo lo que lleva ese prefijo, y lo recordado de
otros encabezados, o de otro catalogo real, no se toca.
"""

from collections.abc import Sequence
from datetime import date

from sqlalchemy import delete
from sqlalchemy.sql import Delete

from app.adapters.persistence.modelos import (
    BorradorCargaArchivo,
    Carga,
    CargaAuditoria,
    MapeoRecordado,
)
from app.core.entities.mapeador import Asignacion, OrigenAsignacion
from app.core.services.ingesta_sabana.catalogo import CATALOGO_SABANA


def sentencias_de_limpieza(
    fecha_corte: date, prefijo: str, catalogos_de_prueba: Sequence[str] = ()
) -> list[Delete]:
    """Lo que borra una prueba al empezar y al terminar.

    - las versiones y la auditoria de la fecha de corte de la prueba (`fecha_corte` es un `date`);
    - los borradores cuyo archivo lleva el prefijo;
    - lo recordado de la sabana solo para encabezados con el prefijo, y todo lo recordado de los
      catalogos que la prueba inventa (`catalogos_de_prueba`).
    """
    sentencias = [
        delete(Carga).where(Carga.fecha_corte == fecha_corte),
        delete(CargaAuditoria).where(CargaAuditoria.fecha_corte == fecha_corte),
        delete(BorradorCargaArchivo).where(
            BorradorCargaArchivo.nombre_archivo.startswith(prefijo, autoescape=True)
        ),
        delete(MapeoRecordado).where(
            MapeoRecordado.catalogo_id == CATALOGO_SABANA.id,
            MapeoRecordado.encabezado_normalizado.startswith(prefijo.casefold(), autoescape=True),
        ),
    ]
    if catalogos_de_prueba:
        sentencias.append(
            delete(MapeoRecordado).where(MapeoRecordado.catalogo_id.in_(list(catalogos_de_prueba)))
        )
    return sentencias


def asignar(analizado, campos: Sequence[str | None]) -> list[Asignacion]:
    """Una asignacion por columna del analisis, con el campo que dice la prueba (`None` es «No
    cargar»). El origen va como `manual`: el backend lo recalcula al confirmar."""
    columnas = analizado.analisis.columnas
    assert len(columnas) == len(campos), (len(columnas), len(campos))
    return [
        Asignacion(c.indice, campo, OrigenAsignacion.MANUAL)
        for c, campo in zip(columnas, campos, strict=True)
    ]

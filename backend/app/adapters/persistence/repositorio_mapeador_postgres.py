"""Implementacion PostgreSQL de los borradores y los mapeos recordados del mapeador (§5).

`SesionMapeadorPostgres` es la sesion del mapeador sobre una conexion. `SesionCargasPostgres` la
hereda: confirmar un borrador crea la carga, guarda los recordados y borra el borrador en UNA
transaccion, con el borrador tomado antes con `SELECT ... FOR UPDATE`.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import Connection, Engine, delete, insert, select, update
from sqlalchemy.dialects.postgresql import insert as insert_pg
from sqlalchemy.engine import Row

from app.adapters.persistence.modelos import BorradorCargaArchivo, MapeoRecordado
from app.core.entities.borrador import DatosBorrador, NuevoBorrador
from app.core.ports.repositorio_mapeador_port import (
    ClaveRecordada,
    RepositorioMapeadorPort,
    SesionMapeadorPort,
)

_BORRADOR = BorradorCargaArchivo.__table__
_RECORDADO = MapeoRecordado.__table__

_COLUMNAS_BORRADOR = (
    _BORRADOR.c.id,
    _BORRADOR.c.catalogo_id,
    _BORRADOR.c.nombre_archivo,
    _BORRADOR.c.huella,
    _BORRADOR.c.tamano_bytes,
    _BORRADOR.c.opciones,
    _BORRADOR.c.analisis,
    _BORRADOR.c.creado_en,
)


def _borrador(fila: Row) -> DatosBorrador:
    return DatosBorrador(
        id=fila.id,
        catalogo_id=fila.catalogo_id,
        nombre_archivo=fila.nombre_archivo,
        huella=fila.huella,
        tamano_bytes=fila.tamano_bytes,
        opciones=fila.opciones,
        analisis=fila.analisis,
        creado_en=fila.creado_en,
    )


def sentencia_de_recordados(catalogo_id: str, asignaciones, ahora: datetime):
    """El upsert por lote de los recordados: lo que ya estaba se actualiza (`campo` y fecha)."""
    insercion = insert_pg(_RECORDADO).values(
        [
            {
                "catalogo_id": catalogo_id,
                "encabezado_normalizado": normalizado,
                "ocurrencia": ocurrencia,
                "campo": campo,  # None es NULL: «No cargar»
                "actualizado_en": ahora,
            }
            for (normalizado, ocurrencia), campo in asignaciones.items()
        ]
    )
    return insercion.on_conflict_do_update(
        index_elements=["catalogo_id", "encabezado_normalizado", "ocurrencia"],
        set_={
            "campo": insercion.excluded.campo,
            "actualizado_en": insercion.excluded.actualizado_en,
        },
    )


class SesionMapeadorPostgres(SesionMapeadorPort):
    def __init__(self, conexion: Connection) -> None:
        self._cx = conexion

    def crear_borrador(self, nuevo: NuevoBorrador, contenido: bytes) -> DatosBorrador:
        fila = self._cx.execute(
            insert(_BORRADOR)
            .values(
                catalogo_id=nuevo.catalogo_id,
                nombre_archivo=nuevo.nombre_archivo,
                contenido=contenido,
                huella=nuevo.huella,
                tamano_bytes=nuevo.tamano_bytes,
                opciones=nuevo.opciones,
                analisis=nuevo.analisis,
                creado_en=nuevo.creado_en,
            )
            .returning(*_COLUMNAS_BORRADOR)
        ).one()
        return _borrador(fila)

    def obtener_borrador(self, borrador_id: int, bloquear: bool = False) -> DatosBorrador | None:
        consulta = select(*_COLUMNAS_BORRADOR).where(_BORRADOR.c.id == borrador_id)
        if bloquear:
            consulta = consulta.with_for_update()
        fila = self._cx.execute(consulta).one_or_none()
        return _borrador(fila) if fila else None

    def contenido_de_borrador(self, borrador_id: int) -> bytes:
        return self._cx.execute(
            select(_BORRADOR.c.contenido).where(_BORRADOR.c.id == borrador_id)
        ).scalar_one()

    def reemplazar_analisis(
        self, borrador_id: int, opciones: dict, analisis: dict
    ) -> DatosBorrador | None:
        fila = self._cx.execute(
            update(_BORRADOR)
            .where(_BORRADOR.c.id == borrador_id)
            .values(opciones=opciones, analisis=analisis)
            .returning(*_COLUMNAS_BORRADOR)
        ).one_or_none()
        return _borrador(fila) if fila else None

    def borrar_borrador(self, borrador_id: int) -> bool:
        return self._cx.execute(delete(_BORRADOR).where(_BORRADOR.c.id == borrador_id)).rowcount > 0

    def borrar_borradores_vencidos(self, antes_de: datetime) -> int:
        return self._cx.execute(delete(_BORRADOR).where(_BORRADOR.c.creado_en < antes_de)).rowcount

    def recordados(self, catalogo_id: str) -> dict[ClaveRecordada, str | None]:
        filas = self._cx.execute(
            select(_RECORDADO.c.encabezado_normalizado, _RECORDADO.c.ocurrencia, _RECORDADO.c.campo)
            .where(_RECORDADO.c.catalogo_id == catalogo_id)
            .order_by(_RECORDADO.c.encabezado_normalizado, _RECORDADO.c.ocurrencia)
        )
        return {(f.encabezado_normalizado, f.ocurrencia): f.campo for f in filas}

    def guardar_recordados(self, catalogo_id: str, asignaciones, ahora: datetime) -> None:
        if asignaciones:
            self._cx.execute(sentencia_de_recordados(catalogo_id, asignaciones, ahora))


class RepositorioMapeadorPostgres(RepositorioMapeadorPort):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @contextmanager
    def transaccion(self) -> Iterator[SesionMapeadorPostgres]:
        with self._engine.begin() as conexion:
            yield SesionMapeadorPostgres(conexion)

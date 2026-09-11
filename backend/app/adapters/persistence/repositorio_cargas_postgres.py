"""Implementacion PostgreSQL del repositorio de versiones de sabana.

- Transacciones con SQLAlchemy Core (`engine.begin()`).
- Filas e incidencias con COPY de psycopg sobre la misma conexion y transaccion:
  carga masiva, ~46 mil filas en ~1 s (docs/versionado-sabanas.md, seccion 3).
- Bloqueo por fecha con `pg_advisory_xact_lock`, que se libera solo al terminar
  la transaccion (commit o rollback).
"""

import json
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import date
from enum import Enum
from typing import Any

from psycopg import sql
from sqlalchemy import Connection, Engine, func, insert, select, text, update
from sqlalchemy.engine import Row

from app.adapters.persistence.modelos import (
    Carga,
    CargaArchivo,
    CargaAuditoria,
    CargaFila,
    CargaIncidencia,
)
from app.core.entities.carga import (
    DatosCarga,
    EstadoCarga,
    EventoAuditoria,
    FilaParaGuardar,
    FormatoCarga,
    NuevaCarga,
    ResumenProcesamiento,
)
from app.core.entities.sabana import Incidencia
from app.core.ports.repositorio_cargas_port import RepositorioCargasPort, SesionCargasPort

_CARGA = Carga.__table__
_ARCHIVO = CargaArchivo.__table__
_AUDITORIA = CargaAuditoria.__table__

# Primer entero de pg_advisory_xact_lock: separa estos bloqueos de otros futuros.
_ESPACIO_BLOQUEO_FECHA = 7201

_COLUMNAS_DATOS = (
    _CARGA.c.id,
    _CARGA.c.fecha_corte,
    _CARGA.c.version,
    _CARGA.c.estado,
    _CARGA.c.vigente,
    _CARGA.c.nombre_archivo,
    _CARGA.c.huella_archivo,
    _CARGA.c.hoja,
)
_COLUMNAS_VALORES = [
    c.name
    for c in CargaFila.__table__.columns
    if c.name not in {"carga_id", "numero_fila", "extras"}
]
_COPY_FILAS = sql.SQL("COPY {} ({}) FROM STDIN").format(
    sql.Identifier(CargaFila.__tablename__),
    sql.SQL(", ").join(
        sql.Identifier(n) for n in ["carga_id", "numero_fila", *_COLUMNAS_VALORES, "extras"]
    ),
)
_COPY_INCIDENCIAS = sql.SQL("COPY {} ({}) FROM STDIN").format(
    sql.Identifier(CargaIncidencia.__tablename__),
    sql.SQL(", ").join(
        sql.Identifier(n)
        for n in ("carga_id", "fila", "columna", "codigo", "severidad", "detalle", "valor_original")
    ),
)


def _datos(fila: Row) -> DatosCarga:
    return DatosCarga(
        id=fila.id,
        fecha_corte=fila.fecha_corte,
        version=fila.version,
        estado=EstadoCarga(fila.estado),
        vigente=fila.vigente,
        nombre_archivo=fila.nombre_archivo,
        huella_archivo=fila.huella_archivo,
        hoja=fila.hoja,
    )


def _copiable(valor: Any) -> Any:
    return valor.value if isinstance(valor, Enum) else valor


def _texto(valor: Any) -> str | None:
    if valor is None:
        return None
    if isinstance(valor, date):
        return valor.isoformat()
    return str(valor)


class SesionCargasPostgres(SesionCargasPort):
    def __init__(self, conexion: Connection) -> None:
        self._cx = conexion

    def _driver(self):
        """Conexion psycopg subyacente, dentro de la misma transaccion de SQLAlchemy."""
        return self._cx.connection.driver_connection

    def bloquear_fecha(self, fecha_corte: date) -> None:
        self._cx.execute(
            text("SELECT pg_advisory_xact_lock(CAST(:espacio AS integer), CAST(:dia AS integer))"),
            {"espacio": _ESPACIO_BLOQUEO_FECHA, "dia": fecha_corte.toordinal()},
        )

    def siguiente_version(self, fecha_corte: date) -> int:
        return self._cx.execute(
            select(func.coalesce(func.max(_CARGA.c.version), 0) + 1).where(
                _CARGA.c.fecha_corte == fecha_corte
            )
        ).scalar_one()

    def versiones_con_huella(self, fecha_corte: date, huella_archivo: str) -> list[int]:
        return list(
            self._cx.execute(
                select(_CARGA.c.version)
                .where(
                    _CARGA.c.fecha_corte == fecha_corte, _CARGA.c.huella_archivo == huella_archivo
                )
                .order_by(_CARGA.c.version)
            ).scalars()
        )

    def crear_carga(self, nueva: NuevaCarga) -> DatosCarga:
        fila = self._cx.execute(
            insert(_CARGA)
            .values(
                fecha_corte=nueva.fecha_corte,
                version=nueva.version,
                nombre_archivo=nueva.nombre_archivo,
                huella_archivo=nueva.huella_archivo,
                tamano_bytes=nueva.tamano_bytes,
                hoja=nueva.hoja,
            )
            .returning(*_COLUMNAS_DATOS)
        ).one()
        return _datos(fila)

    def guardar_archivo(self, carga_id: int, contenido: bytes) -> None:
        self._cx.execute(insert(_ARCHIVO).values(carga_id=carga_id, contenido=contenido))

    def obtener_carga(self, carga_id: int) -> DatosCarga | None:
        fila = self._cx.execute(
            select(*_COLUMNAS_DATOS).where(_CARGA.c.id == carga_id)
        ).one_or_none()
        return _datos(fila) if fila else None

    def tomar_para_procesar(self, carga_id: int) -> DatosCarga | None:
        fila = self._cx.execute(
            update(_CARGA)
            .where(_CARGA.c.id == carga_id, _CARGA.c.estado == EstadoCarga.EN_COLA.value)
            .values(estado=EstadoCarga.PROCESANDO.value)
            .returning(*_COLUMNAS_DATOS)
        ).one_or_none()
        return _datos(fila) if fila else None

    def obtener_archivo(self, carga_id: int) -> bytes:
        return self._cx.execute(
            select(_ARCHIVO.c.contenido).where(_ARCHIVO.c.carga_id == carga_id)
        ).scalar_one()

    def guardar_filas(self, carga_id: int, filas: Iterable[FilaParaGuardar]) -> int:
        guardadas = 0
        with self._driver().cursor() as cursor, cursor.copy(_COPY_FILAS) as copia:
            for fila in filas:
                copia.write_row(
                    [
                        carga_id,
                        fila.numero_fila,
                        *(_copiable(fila.valores.get(nombre)) for nombre in _COLUMNAS_VALORES),
                        json.dumps(fila.extras, ensure_ascii=False) if fila.extras else None,
                    ]
                )
                guardadas += 1
        return guardadas

    def guardar_incidencias(self, carga_id: int, incidencias: Iterable[Incidencia]) -> int:
        guardadas = 0
        with self._driver().cursor() as cursor, cursor.copy(_COPY_INCIDENCIAS) as copia:
            for i in incidencias:
                copia.write_row(
                    [
                        carga_id,
                        i.fila,
                        i.columna,
                        i.codigo,
                        i.severidad.value,
                        i.detalle,
                        _texto(i.valor_original),
                    ]
                )
                guardadas += 1
        return guardadas

    def finalizar_carga(
        self,
        carga_id: int,
        estado: EstadoCarga,
        resumen: ResumenProcesamiento,
        formato: FormatoCarga | None = None,
        motivo_fallo: str | None = None,
    ) -> None:
        valores: dict[str, Any] = {
            "estado": estado.value,
            "filas_total": resumen.filas_total,
            "filas_ingestadas": resumen.filas_ingestadas,
            "incidencias_error": resumen.incidencias_error,
            "incidencias_advertencia": resumen.incidencias_advertencia,
            "incidencias_info": resumen.incidencias_info,
            "motivo_fallo": motivo_fallo,
            # clock_timestamp: hora real de fin (now() seria el inicio de la transaccion).
            "procesado_en": func.clock_timestamp(),
        }
        if formato is not None:
            valores |= {
                "fila_cabecera": formato.fila_cabecera,
                "cabeceras_originales": formato.cabeceras_originales,
                "huella_formato": formato.huella_formato,
                "mapeo": formato.mapeo,
            }
        self._cx.execute(update(_CARGA).where(_CARGA.c.id == carga_id).values(**valores))

    def id_vigente(self, fecha_corte: date) -> int | None:
        return self._cx.execute(
            select(_CARGA.c.id).where(_CARGA.c.fecha_corte == fecha_corte, _CARGA.c.vigente)
        ).scalar_one_or_none()

    def marcar_vigente(self, carga_id: int, vigente: bool) -> None:
        self._cx.execute(update(_CARGA).where(_CARGA.c.id == carga_id).values(vigente=vigente))

    def auditar(
        self,
        carga: DatosCarga,
        evento: EventoAuditoria,
        filas_total: int | None = None,
        detalle: dict[str, Any] | None = None,
    ) -> None:
        self._cx.execute(
            insert(_AUDITORIA).values(
                carga_id=carga.id,
                fecha_corte=carga.fecha_corte,
                version=carga.version,
                evento=evento.value,
                nombre_archivo=carga.nombre_archivo,
                huella_archivo=carga.huella_archivo,
                filas_total=filas_total,
                detalle=detalle,
            )
        )


class RepositorioCargasPostgres(RepositorioCargasPort):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @contextmanager
    def transaccion(self) -> Iterator[SesionCargasPostgres]:
        with self._engine.begin() as conexion:
            yield SesionCargasPostgres(conexion)

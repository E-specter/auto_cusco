"""Implementacion PostgreSQL de los borradores y los mapeos recordados del mapeador (§5).

`SesionMapeadorPostgres` es la sesion del mapeador sobre una conexion. `SesionCargasPostgres` la
hereda: confirmar un borrador crea la carga, guarda los recordados y borra el borrador en UNA
transaccion, con el borrador tomado antes con `SELECT ... FOR UPDATE`.
"""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import Connection, Engine, delete, insert, select, text, update
from sqlalchemy.dialects.postgresql import insert as insert_pg
from sqlalchemy.engine import Row

from app.adapters.persistence.modelos import (
    BorradorCargaArchivo,
    MapeoRecordado,
)
from app.adapters.persistence.modelos import (
    CampoAdicional as ModeloCampoAdicional,
)
from app.core.entities.borrador import DatosBorrador, NuevoBorrador
from app.core.entities.campos_adicionales import CampoAdicional, TipoAdicional
from app.core.ports.repositorio_campos_adicionales_port import RepositorioCamposAdicionalesPort
from app.core.ports.repositorio_mapeador_port import (
    ClaveRecordada,
    RepositorioMapeadorPort,
    SesionMapeadorPort,
)
from app.core.services.ingesta_sabana.catalogo import CATALOGO_SABANA
from app.core.services.mapeador.similitud import normalizar_cabecera

_BORRADOR = BorradorCargaArchivo.__table__
_RECORDADO = MapeoRecordado.__table__
_ADICIONAL = ModeloCampoAdicional.__table__

# Un solo candado para crear o renombrar campos adicionales: son pocos y raros, y asi el nombre
# tecnico y el legible se eligen sin carreras (el indice unico es la red de seguridad).
_ESPACIO_BLOQUEO_ADICIONALES = 0x0CA0

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


def _adicional(fila: Row) -> CampoAdicional:
    return CampoAdicional(
        nombre=fila.nombre,
        nombre_legible=fila.nombre_legible,
        tipo=TipoAdicional(fila.tipo),
        encabezado_origen=fila.encabezado_origen,
        archivado=fila.archivado,
    )


_COLUMNAS_ADICIONAL = (
    _ADICIONAL.c.nombre,
    _ADICIONAL.c.nombre_legible,
    _ADICIONAL.c.tipo,
    _ADICIONAL.c.encabezado_origen,
    _ADICIONAL.c.archivado,
)


def sentencia_de_adicionales(catalogo_id: str):
    return (
        select(*_COLUMNAS_ADICIONAL)
        .where(_ADICIONAL.c.catalogo_id == catalogo_id)
        .order_by(_ADICIONAL.c.orden)
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

    def bloquear_adicionales(self) -> None:
        self._cx.execute(
            text("SELECT pg_advisory_xact_lock(CAST(:espacio AS integer), 0)"),
            {"espacio": _ESPACIO_BLOQUEO_ADICIONALES},
        )

    def adicionales(self, catalogo_id: str) -> Sequence[CampoAdicional]:
        return [_adicional(f) for f in self._cx.execute(sentencia_de_adicionales(catalogo_id))]

    def crear_adicional(
        self, catalogo_id: str, campo: CampoAdicional, ahora: datetime
    ) -> CampoAdicional:
        fila = self._cx.execute(
            insert(_ADICIONAL)
            .values(
                nombre=campo.nombre,
                catalogo_id=catalogo_id,
                nombre_legible=campo.nombre_legible,
                nombre_legible_normalizado=normalizar_cabecera(campo.nombre_legible),
                tipo=campo.tipo.value,
                encabezado_origen=campo.encabezado_origen,
                archivado=campo.archivado,
                creado_en=ahora,
                actualizado_en=ahora,
            )
            .returning(*_COLUMNAS_ADICIONAL)
        ).one()
        return _adicional(fila)

    def actualizar_adicional(
        self,
        nombre: str,
        nombre_legible: str | None,
        archivado: bool | None,
        ahora: datetime,
    ) -> CampoAdicional | None:
        valores: dict = {"actualizado_en": ahora}
        if nombre_legible is not None:
            valores["nombre_legible"] = nombre_legible
            valores["nombre_legible_normalizado"] = normalizar_cabecera(nombre_legible)
        if archivado is not None:
            valores["archivado"] = archivado
        fila = self._cx.execute(
            update(_ADICIONAL)
            .where(_ADICIONAL.c.nombre == nombre)
            .values(**valores)
            .returning(*_COLUMNAS_ADICIONAL)
        ).one_or_none()
        return _adicional(fila) if fila else None


class RepositorioCamposAdicionalesPostgres(RepositorioCamposAdicionalesPort):
    """La lectura de las definiciones de un catalogo (el de la sabana, por defecto)."""

    def __init__(self, engine: Engine, catalogo_id: str = CATALOGO_SABANA.id) -> None:
        self._engine = engine
        self._catalogo_id = catalogo_id

    def listar(self) -> Sequence[CampoAdicional]:
        with self._engine.connect() as conexion:
            return [
                _adicional(f) for f in conexion.execute(sentencia_de_adicionales(self._catalogo_id))
            ]


class RepositorioMapeadorPostgres(RepositorioMapeadorPort):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @contextmanager
    def transaccion(self) -> Iterator[SesionMapeadorPostgres]:
        with self._engine.begin() as conexion:
            yield SesionMapeadorPostgres(conexion)

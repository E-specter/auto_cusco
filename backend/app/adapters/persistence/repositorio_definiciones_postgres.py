"""Definiciones de columnas guardadas y sus versiones, sobre PostgreSQL (RF-51).

La unicidad del nombre la impone la base sobre el nombre normalizado, y la de (definicion, numero)
de version tambien: una version nueva toma el siguiente numero con la fila de la definicion
bloqueada, asi dos personas guardando a la vez no se pisan ni repiten numero.
"""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import Engine, and_, func, insert, select, update
from sqlalchemy.engine import Row
from sqlalchemy.exc import IntegrityError

from app.adapters.persistence.modelos import DefinicionCargaGuardada, DefinicionCargaVersion
from app.core.entities.definiciones_columnas import (
    DefinicionGuardada,
    NombreDeDefinicionRepetido,
    ResumenDefinicion,
    VersionDefinicion,
    normalizar_nombre,
)
from app.core.ports.repositorio_definiciones_port import RepositorioDefinicionesPort

_DEFINICION = DefinicionCargaGuardada.__table__
_VERSION = DefinicionCargaVersion.__table__
_RESTRICCION_NOMBRE = "uq_definicion_carga_nombre_normalizado"


def _version(fila: Row) -> VersionDefinicion:
    return VersionDefinicion(
        numero=fila.numero,
        contenido=fila.contenido,
        usada_en=fila.usada_en,
        creado_en=fila.creado_en,
    )


def _es_nombre_repetido(exc: IntegrityError) -> bool:
    diagnostico = getattr(exc.orig, "diag", None)
    return getattr(diagnostico, "constraint_name", None) == _RESTRICCION_NOMBRE


class RepositorioDefinicionesPostgres(RepositorioDefinicionesPort):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def listar(self) -> list[ResumenDefinicion]:
        por_definicion = (
            select(
                _VERSION.c.definicion_id,
                func.max(_VERSION.c.numero).label("vigente"),
                func.count().label("cantidad"),
            )
            .group_by(_VERSION.c.definicion_id)
            .subquery()
        )
        consulta = (
            select(
                _DEFINICION.c.id,
                _DEFINICION.c.nombre,
                _DEFINICION.c.actualizado_en,
                por_definicion.c.vigente,
                por_definicion.c.cantidad,
                _VERSION.c.usada_en.is_not(None).label("vigente_usada"),
            )
            .join(por_definicion, por_definicion.c.definicion_id == _DEFINICION.c.id)
            .join(
                _VERSION,
                and_(
                    _VERSION.c.definicion_id == _DEFINICION.c.id,
                    _VERSION.c.numero == por_definicion.c.vigente,
                ),
            )
            .order_by(_DEFINICION.c.nombre_normalizado, _DEFINICION.c.id)
        )
        with self._engine.connect() as cx:
            return [
                ResumenDefinicion(
                    id=fila.id,
                    nombre=fila.nombre,
                    version_vigente=fila.vigente,
                    cantidad_versiones=fila.cantidad,
                    actualizado_en=fila.actualizado_en,
                    vigente_usada=fila.vigente_usada,
                )
                for fila in cx.execute(consulta).all()
            ]

    def obtener(self, definicion_id: int) -> DefinicionGuardada | None:
        with self._engine.connect() as cx:
            definicion = cx.execute(
                select(_DEFINICION).where(_DEFINICION.c.id == definicion_id)
            ).one_or_none()
            if definicion is None:
                return None
            versiones = cx.execute(
                select(_VERSION)
                .where(_VERSION.c.definicion_id == definicion_id)
                .order_by(_VERSION.c.numero)
            ).all()
        return DefinicionGuardada(
            id=definicion.id,
            nombre=definicion.nombre,
            creado_en=definicion.creado_en,
            actualizado_en=definicion.actualizado_en,
            versiones=tuple(_version(v) for v in versiones),
        )

    def crear(self, nombre: str, contenido: Mapping[str, Any]) -> DefinicionGuardada:
        try:
            with self._engine.begin() as cx:
                definicion = cx.execute(
                    insert(_DEFINICION)
                    .values(nombre=nombre, nombre_normalizado=normalizar_nombre(nombre))
                    .returning(*_DEFINICION.c)
                ).one()
                version = cx.execute(
                    insert(_VERSION)
                    .values(definicion_id=definicion.id, numero=1, contenido=dict(contenido))
                    .returning(*_VERSION.c)
                ).one()
        except IntegrityError as exc:
            if _es_nombre_repetido(exc):
                raise NombreDeDefinicionRepetido(nombre) from exc
            raise
        return DefinicionGuardada(
            id=definicion.id,
            nombre=definicion.nombre,
            creado_en=definicion.creado_en,
            actualizado_en=definicion.actualizado_en,
            versiones=(_version(version),),
        )

    def agregar_version(
        self, definicion_id: int, contenido: Mapping[str, Any]
    ) -> VersionDefinicion | None:
        with self._engine.begin() as cx:
            # Bloquea la definicion: dos versiones nuevas a la vez toman numeros distintos.
            existe = cx.execute(
                select(_DEFINICION.c.id).where(_DEFINICION.c.id == definicion_id).with_for_update()
            ).one_or_none()
            if existe is None:
                return None
            siguiente = cx.execute(
                select(func.coalesce(func.max(_VERSION.c.numero), 0) + 1).where(
                    _VERSION.c.definicion_id == definicion_id
                )
            ).scalar_one()
            fila = cx.execute(
                insert(_VERSION)
                .values(definicion_id=definicion_id, numero=siguiente, contenido=dict(contenido))
                .returning(*_VERSION.c)
            ).one()
            cx.execute(
                update(_DEFINICION)
                .where(_DEFINICION.c.id == definicion_id)
                # clock_timestamp: la hora real del cambio, no la del inicio de la transaccion.
                .values(actualizado_en=func.clock_timestamp())
            )
        return _version(fila)

    def marcar_version_usada(self, definicion_id: int, numero: int) -> bool:
        with self._engine.begin() as cx:
            cx.execute(
                update(_VERSION)
                .where(
                    _VERSION.c.definicion_id == definicion_id,
                    _VERSION.c.numero == numero,
                    _VERSION.c.usada_en.is_(None),
                )
                .values(usada_en=func.clock_timestamp())
            )
            existe = cx.execute(
                select(_VERSION.c.id).where(
                    _VERSION.c.definicion_id == definicion_id, _VERSION.c.numero == numero
                )
            ).one_or_none()
        return existe is not None

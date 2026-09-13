"""Selecciones de cartera guardadas, sobre PostgreSQL.

La unicidad del nombre la impone la base sobre el nombre normalizado, asi que
dos personas guardando a la vez no pueden crear dos selecciones con el mismo
nombre aunque lo escriban con distintas mayusculas.
"""

from typing import Any

from sqlalchemy import Engine, delete, func, insert, select, update
from sqlalchemy.engine import Row
from sqlalchemy.exc import IntegrityError

from app.adapters.persistence.modelos import Seleccion
from app.core.entities.selecciones import (
    DatosSeleccion,
    NombreDeSeleccionRepetido,
    SeleccionGuardada,
)
from app.core.ports.repositorio_selecciones_port import RepositorioSeleccionesPort

_SELECCION = Seleccion.__table__
_RESTRICCION_NOMBRE = "uq_seleccion_nombre_normalizado"


def normalizar_nombre(nombre: str) -> str:
    return nombre.strip().casefold()


def _valores(datos: DatosSeleccion) -> dict[str, Any]:
    return {
        "nombre": datos.nombre,
        "nombre_normalizado": normalizar_nombre(datos.nombre),
        "filtros": list(datos.filtros),
        "orden": datos.orden,
        "cantidad": datos.cantidad,
        "indicadores": list(datos.indicadores),
    }


def _seleccion(fila: Row) -> SeleccionGuardada:
    return SeleccionGuardada(
        id=fila.id,
        datos=DatosSeleccion(
            nombre=fila.nombre,
            filtros=tuple(fila.filtros),
            orden=fila.orden,
            cantidad=fila.cantidad,
            indicadores=tuple(fila.indicadores),
        ),
        creado_en=fila.creado_en,
        actualizado_en=fila.actualizado_en,
    )


def _es_nombre_repetido(exc: IntegrityError) -> bool:
    diagnostico = getattr(exc.orig, "diag", None)
    return getattr(diagnostico, "constraint_name", None) == _RESTRICCION_NOMBRE


class RepositorioSeleccionesPostgres(RepositorioSeleccionesPort):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def listar(self) -> list[SeleccionGuardada]:
        consulta = select(_SELECCION).order_by(_SELECCION.c.nombre_normalizado, _SELECCION.c.id)
        with self._engine.connect() as cx:
            return [_seleccion(fila) for fila in cx.execute(consulta).all()]

    def obtener(self, seleccion_id: int) -> SeleccionGuardada | None:
        with self._engine.connect() as cx:
            fila = cx.execute(
                select(_SELECCION).where(_SELECCION.c.id == seleccion_id)
            ).one_or_none()
        return _seleccion(fila) if fila else None

    def crear(self, datos: DatosSeleccion) -> SeleccionGuardada:
        consulta = insert(_SELECCION).values(**_valores(datos)).returning(*_SELECCION.c)
        try:
            with self._engine.begin() as cx:
                fila = cx.execute(consulta).one()
        except IntegrityError as exc:
            if _es_nombre_repetido(exc):
                raise NombreDeSeleccionRepetido(datos.nombre) from exc
            raise
        return _seleccion(fila)

    def actualizar(self, seleccion_id: int, datos: DatosSeleccion) -> SeleccionGuardada | None:
        consulta = (
            update(_SELECCION)
            .where(_SELECCION.c.id == seleccion_id)
            # clock_timestamp: la hora real del cambio, no la del inicio de la transaccion.
            .values(**_valores(datos), actualizado_en=func.clock_timestamp())
            .returning(*_SELECCION.c)
        )
        try:
            with self._engine.begin() as cx:
                fila = cx.execute(consulta).one_or_none()
        except IntegrityError as exc:
            if _es_nombre_repetido(exc):
                raise NombreDeSeleccionRepetido(datos.nombre) from exc
            raise
        return _seleccion(fila) if fila else None

    def eliminar(self, seleccion_id: int) -> bool:
        with self._engine.begin() as cx:
            resultado = cx.execute(delete(_SELECCION).where(_SELECCION.c.id == seleccion_id))
        return resultado.rowcount > 0

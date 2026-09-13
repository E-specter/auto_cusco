"""Excepciones del calendario laboral, sobre PostgreSQL.

La fecha es la clave: la base impide dos excepciones para el mismo dia aunque
se guarden a la vez.
"""

from datetime import date

from sqlalchemy import Engine, delete, insert, select
from sqlalchemy.engine import Row
from sqlalchemy.exc import IntegrityError

from app.adapters.persistence.modelos import CalendarioExcepcion
from app.core.entities.calendario import ExcepcionCalendario, ExcepcionRepetida, TipoExcepcion
from app.core.ports.repositorio_calendario_port import RepositorioCalendarioPort

_EXCEPCION = CalendarioExcepcion.__table__


def _excepcion(fila: Row) -> ExcepcionCalendario:
    return ExcepcionCalendario(
        fecha=fila.fecha,
        tipo=TipoExcepcion(fila.tipo),
        descripcion=fila.descripcion,
        creado_en=fila.creado_en,
    )


class RepositorioCalendarioPostgres(RepositorioCalendarioPort):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def listar_excepciones(
        self, desde: date | None = None, hasta: date | None = None
    ) -> list[ExcepcionCalendario]:
        consulta = select(_EXCEPCION).order_by(_EXCEPCION.c.fecha)
        if desde is not None:
            consulta = consulta.where(_EXCEPCION.c.fecha >= desde)
        if hasta is not None:
            consulta = consulta.where(_EXCEPCION.c.fecha <= hasta)
        with self._engine.connect() as cx:
            return [_excepcion(fila) for fila in cx.execute(consulta).all()]

    def agregar_excepcion(self, excepcion: ExcepcionCalendario) -> ExcepcionCalendario:
        consulta = (
            insert(_EXCEPCION)
            .values(
                fecha=excepcion.fecha,
                tipo=excepcion.tipo.value,
                descripcion=excepcion.descripcion,
            )
            .returning(*_EXCEPCION.c)
        )
        try:
            with self._engine.begin() as cx:
                fila = cx.execute(consulta).one()
        except IntegrityError as exc:
            raise ExcepcionRepetida(excepcion.fecha) from exc
        return _excepcion(fila)

    def eliminar_excepcion(self, fecha: date) -> bool:
        with self._engine.begin() as cx:
            resultado = cx.execute(delete(_EXCEPCION).where(_EXCEPCION.c.fecha == fecha))
        return resultado.rowcount > 0

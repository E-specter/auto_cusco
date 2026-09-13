"""Caso de uso: siguiente dia gestionable y excepciones del calendario (RF-MM-08).

Un dia es gestionable si cae de lunes a viernes y no es un dia no laborable:
feriado de ley no retirado o dia agregado por decreto. "Siguiente" es
estrictamente posterior a la fecha de partida, que por defecto es hoy en
America/Lima.
"""

from collections.abc import Callable
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.entities.calendario import (
    LARGO_MAXIMO_DESCRIPCION,
    ZONA_HORARIA,
    DiaNoLaborable,
    ExcepcionCalendario,
    ExcepcionInvalida,
    ExcepcionNoEncontrada,
    OrigenDia,
    TipoExcepcion,
)
from app.core.ports.repositorio_calendario_port import RepositorioCalendarioPort
from app.core.services.calendario.reglas import feriados_de_ley

ZONA = ZoneInfo(ZONA_HORARIA)
_SABADO = 5


def ahora_en_lima() -> datetime:
    return datetime.now(ZONA)


def siguiente_dia_gestionable(desde: date, no_laborables: Callable[[int], set[date]]) -> date:
    """Primer dia de lunes a viernes, posterior a `desde`, que no es no laborable.

    `no_laborables(anio)` devuelve las fechas no laborables de ese ano.
    """
    por_anio: dict[int, set[date]] = {}
    dia = desde + timedelta(days=1)
    while True:
        if dia.year not in por_anio:
            por_anio[dia.year] = no_laborables(dia.year)
        if dia.weekday() < _SABADO and dia not in por_anio[dia.year]:
            return dia
        dia += timedelta(days=1)


class CalendarioService:
    def __init__(
        self,
        repositorio: RepositorioCalendarioPort,
        reloj: Callable[[], datetime] = ahora_en_lima,
    ) -> None:
        self._repositorio = repositorio
        self._reloj = reloj

    def hoy(self) -> date:
        """Fecha actual en America/Lima, aunque el servidor corra en otra zona."""
        return self._reloj().astimezone(ZONA).date()

    def dias_no_laborables(self, anio: int) -> list[DiaNoLaborable]:
        """Feriados de ley (marcando los retirados) y dias agregados del ano."""
        excepciones = {
            e.fecha: e
            for e in self._repositorio.listar_excepciones(date(anio, 1, 1), date(anio, 12, 31))
        }
        dias = [
            DiaNoLaborable(
                fecha=feriado.fecha,
                descripcion=feriado.descripcion,
                origen=OrigenDia.LEY,
                retirado=_tipo(excepciones, feriado.fecha) is TipoExcepcion.RETIRADO,
            )
            for feriado in feriados_de_ley(anio)
        ]
        dias += [
            DiaNoLaborable(fecha=e.fecha, descripcion=e.descripcion, origen=OrigenDia.AGREGADO)
            for e in excepciones.values()
            if e.tipo is TipoExcepcion.AGREGADO
        ]
        return sorted(dias, key=lambda dia: dia.fecha)

    def fechas_no_laborables(self, anio: int) -> set[date]:
        return {dia.fecha for dia in self.dias_no_laborables(anio) if not dia.retirado}

    def siguiente_dia_gestionable(self, desde: date | None = None) -> date:
        return siguiente_dia_gestionable(desde or self.hoy(), self.fechas_no_laborables)

    def listar_excepciones(self) -> list[ExcepcionCalendario]:
        return self._repositorio.listar_excepciones()

    def agregar_excepcion(self, excepcion: ExcepcionCalendario) -> ExcepcionCalendario:
        descripcion = excepcion.descripcion.strip()
        if not 1 <= len(descripcion) <= LARGO_MAXIMO_DESCRIPCION:
            raise ExcepcionInvalida(
                f"La descripcion debe tener entre 1 y {LARGO_MAXIMO_DESCRIPCION} caracteres"
            )
        es_feriado = excepcion.fecha in {f.fecha for f in feriados_de_ley(excepcion.fecha.year)}
        if excepcion.tipo is TipoExcepcion.RETIRADO and not es_feriado:
            raise ExcepcionInvalida(
                f"El {excepcion.fecha.isoformat()} no es feriado de ley: no hay nada que retirar"
            )
        if excepcion.tipo is TipoExcepcion.AGREGADO and es_feriado:
            raise ExcepcionInvalida(
                f"El {excepcion.fecha.isoformat()} ya es feriado de ley: no hace falta agregarlo"
            )
        return self._repositorio.agregar_excepcion(
            ExcepcionCalendario(fecha=excepcion.fecha, tipo=excepcion.tipo, descripcion=descripcion)
        )

    def eliminar_excepcion(self, fecha: date) -> None:
        if not self._repositorio.eliminar_excepcion(fecha):
            raise ExcepcionNoEncontrada(fecha)


def _tipo(excepciones: dict[date, ExcepcionCalendario], fecha: date) -> TipoExcepcion | None:
    excepcion = excepciones.get(fecha)
    return excepcion.tipo if excepcion else None

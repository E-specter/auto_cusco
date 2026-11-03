"""Caso de uso: dias gestionables y excepciones del calendario (RF-MM-08, RF-70, RF-71).

Un dia es gestionable si cae de lunes a sabado y no es un dia no laborable: feriado de ley no
retirado o dia agregado por decreto. Solo el domingo no se envia gestion (decision del usuario,
2026-11-02); un feriado o un dia registrado que cae en sabado tampoco es gestionable. "Siguiente" y
"proximos" son estrictamente posteriores a la fecha de partida, que por defecto es hoy en
America/Lima.
"""

from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.entities.calendario import (
    LARGO_MAXIMO_DESCRIPCION,
    MAXIMO_PROXIMOS_POR_DEFECTO,
    ZONA_HORARIA,
    DiaNoLaborable,
    ExcepcionCalendario,
    ExcepcionInvalida,
    ExcepcionNoEncontrada,
    OrigenDia,
    ProximosFueraDeRango,
    TipoExcepcion,
)
from app.core.ports.repositorio_calendario_port import RepositorioCalendarioPort
from app.core.services.calendario.reglas import feriados_de_ley

ZONA = ZoneInfo(ZONA_HORARIA)
_DOMINGO = 6
MINIMO_PROXIMOS = 1


def ahora_en_lima() -> datetime:
    return datetime.now(ZONA)


def dias_gestionables(desde: date, no_laborables: Callable[[int], set[date]]) -> Iterator[date]:
    """Los dias gestionables posteriores a `desde`, en orden y sin fin: de lunes a sabado, menos
    los no laborables.

    `no_laborables(anio)` devuelve las fechas no laborables de ese ano; se pide una vez por ano.
    """
    por_anio: dict[int, set[date]] = {}
    dia = desde + timedelta(days=1)
    while True:
        if dia.year not in por_anio:
            por_anio[dia.year] = no_laborables(dia.year)
        if dia.weekday() != _DOMINGO and dia not in por_anio[dia.year]:
            yield dia
        dia += timedelta(days=1)


def siguiente_dia_gestionable(desde: date, no_laborables: Callable[[int], set[date]]) -> date:
    """Primer dia de lunes a sabado, posterior a `desde`, que no es no laborable."""
    return next(dias_gestionables(desde, no_laborables))


def proximos_dias_gestionables(
    desde: date, n: int, no_laborables: Callable[[int], set[date]]
) -> list[date]:
    """Los `n` primeros dias gestionables posteriores a `desde` (el primero es el siguiente)."""
    dias = dias_gestionables(desde, no_laborables)
    return [next(dias) for _ in range(n)]


class CalendarioService:
    def __init__(
        self,
        repositorio: RepositorioCalendarioPort,
        reloj: Callable[[], datetime] = ahora_en_lima,
        maximo_proximos: int = MAXIMO_PROXIMOS_POR_DEFECTO,
    ) -> None:
        self._repositorio = repositorio
        self._reloj = reloj
        self._maximo_proximos = maximo_proximos

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

    def proximos_dias_gestionables(self, n: int, desde: date | None = None) -> list[date]:
        """Los `n` siguientes dias gestionables posteriores a `desde` (por defecto, hoy en Lima).

        `n` va de 1 al tope configurado (RF-71); fuera de ese rango lanza `ProximosFueraDeRango`.
        """
        if not MINIMO_PROXIMOS <= n <= self._maximo_proximos:
            raise ProximosFueraDeRango(n, MINIMO_PROXIMOS, self._maximo_proximos)
        return proximos_dias_gestionables(desde or self.hoy(), n, self.fechas_no_laborables)

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

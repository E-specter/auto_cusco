"""Pruebas del calendario laboral (RF-MM-08): regla de feriados y siguiente dia gestionable."""

from datetime import UTC, date, datetime

import pytest

from app.core.entities.calendario import (
    ExcepcionCalendario,
    ExcepcionInvalida,
    ExcepcionNoEncontrada,
    ExcepcionRepetida,
    OrigenDia,
    TipoExcepcion,
)
from app.core.services.calendario.reglas import domingo_de_pascua, feriados_de_ley
from app.core.services.calendario.servicio import CalendarioService

LUNES_14_SEPTIEMBRE_2026 = datetime(2026, 9, 14, 15, 0, tzinfo=UTC)


class RepositorioCalendarioFalso:
    def __init__(self, *excepciones: ExcepcionCalendario) -> None:
        self.excepciones = {e.fecha: e for e in excepciones}

    def listar_excepciones(self, desde=None, hasta=None):
        return sorted(
            (
                e
                for e in self.excepciones.values()
                if (desde is None or e.fecha >= desde) and (hasta is None or e.fecha <= hasta)
            ),
            key=lambda e: e.fecha,
        )

    def agregar_excepcion(self, excepcion):
        if excepcion.fecha in self.excepciones:
            raise ExcepcionRepetida(excepcion.fecha)
        self.excepciones[excepcion.fecha] = excepcion
        return excepcion

    def eliminar_excepcion(self, fecha):
        return self.excepciones.pop(fecha, None) is not None


def _servicio(*excepciones: ExcepcionCalendario) -> CalendarioService:
    return CalendarioService(
        RepositorioCalendarioFalso(*excepciones), reloj=lambda: LUNES_14_SEPTIEMBRE_2026
    )


# --- Regla de feriados --------------------------------------------------


@pytest.mark.parametrize(
    ("anio", "pascua"),
    [
        (2024, date(2024, 3, 31)),
        (2025, date(2025, 4, 20)),
        (2026, date(2026, 4, 5)),
        (2027, date(2027, 3, 28)),
        (2038, date(2038, 4, 25)),  # la mas tardia posible
        (2285, date(2285, 3, 22)),  # la mas temprana posible
    ],
)
def test_domingo_de_pascua(anio, pascua) -> None:
    assert domingo_de_pascua(anio) == pascua


def test_2026_tiene_jueves_y_viernes_santo_el_2_y_3_de_abril() -> None:
    feriados = {f.fecha: f.descripcion for f in feriados_de_ley(2026)}

    assert feriados[date(2026, 4, 2)] == "Jueves Santo"
    assert feriados[date(2026, 4, 3)] == "Viernes Santo"


def test_otro_anio_calcula_su_propia_semana_santa() -> None:
    feriados = {f.fecha: f.descripcion for f in feriados_de_ley(2027)}

    assert feriados[date(2027, 3, 25)] == "Jueves Santo"
    assert feriados[date(2027, 3, 26)] == "Viernes Santo"
    assert date(2027, 4, 2) not in feriados


def test_la_regla_da_los_16_feriados_nacionales_de_2026_en_orden() -> None:
    fechas = [f.fecha for f in feriados_de_ley(2026)]

    assert fechas == [
        date(2026, 1, 1),
        date(2026, 4, 2),
        date(2026, 4, 3),
        date(2026, 5, 1),
        date(2026, 6, 7),
        date(2026, 6, 29),
        date(2026, 7, 23),
        date(2026, 7, 28),
        date(2026, 7, 29),
        date(2026, 8, 6),
        date(2026, 8, 30),
        date(2026, 10, 8),
        date(2026, 11, 1),
        date(2026, 12, 8),
        date(2026, 12, 9),
        date(2026, 12, 25),
    ]


# --- Siguiente dia gestionable ------------------------------------------


@pytest.mark.parametrize(
    ("desde", "esperado"),
    [
        (date(2026, 9, 13), date(2026, 9, 14)),  # domingo -> lunes
        (date(2026, 9, 11), date(2026, 9, 14)),  # viernes -> lunes
        (date(2026, 9, 14), date(2026, 9, 15)),  # es estrictamente posterior
        (date(2026, 4, 1), date(2026, 4, 6)),  # Jueves y Viernes Santo, y fin de semana
        (date(2026, 7, 27), date(2026, 7, 30)),  # Fiestas Patrias
        (date(2026, 12, 24), date(2026, 12, 28)),  # Navidad en viernes
        (date(2026, 12, 31), date(2027, 1, 4)),  # cruza el ano: Ano Nuevo 2027 es viernes
    ],
)
def test_siguiente_dia_gestionable(desde, esperado) -> None:
    assert _servicio().siguiente_dia_gestionable(desde) == esperado


def test_un_dia_decretado_no_laborable_se_salta() -> None:
    decreto = ExcepcionCalendario(date(2026, 9, 14), TipoExcepcion.AGREGADO, "Decreto sintetico")

    assert _servicio(decreto).siguiente_dia_gestionable(date(2026, 9, 13)) == date(2026, 9, 15)


def test_un_feriado_retirado_vuelve_a_ser_gestionable() -> None:
    retiro = ExcepcionCalendario(date(2026, 4, 2), TipoExcepcion.RETIRADO, "Cambio de ley")

    assert _servicio(retiro).siguiente_dia_gestionable(date(2026, 4, 1)) == date(2026, 4, 2)


def test_sin_fecha_parte_de_hoy_en_lima_aunque_en_utc_ya_sea_otro_dia() -> None:
    # 03:00 UTC del lunes 14 son las 22:00 del domingo 13 en Lima.
    servicio = CalendarioService(
        RepositorioCalendarioFalso(), reloj=lambda: datetime(2026, 9, 14, 3, 0, tzinfo=UTC)
    )

    assert servicio.hoy() == date(2026, 9, 13)
    assert servicio.siguiente_dia_gestionable() == date(2026, 9, 14)


def test_dias_no_laborables_del_anio_marcan_retirados_e_incluyen_agregados() -> None:
    servicio = _servicio(
        ExcepcionCalendario(date(2026, 4, 3), TipoExcepcion.RETIRADO, "Cambio de ley"),
        ExcepcionCalendario(date(2026, 9, 14), TipoExcepcion.AGREGADO, "Decreto sintetico"),
        ExcepcionCalendario(date(2027, 9, 14), TipoExcepcion.AGREGADO, "Otro ano"),
    )

    dias = servicio.dias_no_laborables(2026)

    por_fecha = {d.fecha: d for d in dias}
    assert len(dias) == 17
    assert [d.fecha for d in dias] == sorted(d.fecha for d in dias)
    assert por_fecha[date(2026, 4, 3)].retirado is True
    assert por_fecha[date(2026, 9, 14)].origen is OrigenDia.AGREGADO
    assert date(2026, 4, 3) not in servicio.fechas_no_laborables(2026)


# --- Excepciones -------------------------------------------------------


def test_agregar_una_excepcion_recorta_la_descripcion() -> None:
    servicio = _servicio()

    guardada = servicio.agregar_excepcion(
        ExcepcionCalendario(date(2026, 9, 14), TipoExcepcion.AGREGADO, "  Decreto sintetico  ")
    )

    assert guardada.descripcion == "Decreto sintetico"


@pytest.mark.parametrize(
    "excepcion",
    [
        ExcepcionCalendario(date(2026, 9, 14), TipoExcepcion.RETIRADO, "No es feriado"),
        ExcepcionCalendario(date(2026, 7, 28), TipoExcepcion.AGREGADO, "Ya es feriado"),
        ExcepcionCalendario(date(2026, 9, 14), TipoExcepcion.AGREGADO, "   "),
        ExcepcionCalendario(date(2026, 9, 14), TipoExcepcion.AGREGADO, "x" * 201),
    ],
)
def test_excepciones_sin_sentido_se_rechazan(excepcion) -> None:
    servicio = _servicio()

    with pytest.raises(ExcepcionInvalida):
        servicio.agregar_excepcion(excepcion)


def test_quitar_una_excepcion_que_no_existe() -> None:
    with pytest.raises(ExcepcionNoEncontrada):
        _servicio().eliminar_excepcion(date(2026, 9, 14))

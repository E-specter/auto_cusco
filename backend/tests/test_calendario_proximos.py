"""Dias de envio de lunes a sabado y proximos N dias gestionables (T-HI-B5, RF-70, RF-71).

Solo el domingo no se envia gestion; un feriado o un dia registrado que cae en sabado tampoco es
gestionable. Los repositorios son el doble en memoria de `test_calendario.py`.
"""

import random
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.calendario import obtener_servicio_calendario
from app.core.config import Settings
from app.core.entities.calendario import (
    MAXIMO_PROXIMOS_POR_DEFECTO,
    ExcepcionCalendario,
    ProximosFueraDeRango,
    TipoExcepcion,
)
from app.core.services.calendario.reglas import feriados_de_ley
from app.core.services.calendario.servicio import CalendarioService
from app.main import app
from tests.test_calendario import RepositorioCalendarioFalso

HOY = datetime(2026, 9, 14, 15, 0, tzinfo=UTC)  # lunes 14 de septiembre de 2026, en Lima


def _servicio(*excepciones: ExcepcionCalendario, **extra) -> CalendarioService:
    return CalendarioService(RepositorioCalendarioFalso(*excepciones), reloj=lambda: HOY, **extra)


def _agregado(fecha: date) -> ExcepcionCalendario:
    return ExcepcionCalendario(fecha, TipoExcepcion.AGREGADO, "Decreto sintetico")


# --- El sabado se envia, el domingo no ----------------------------------------------------------


def test_un_sabado_comun_es_gestionable() -> None:
    assert date(2026, 9, 12).weekday() == 5
    assert _servicio().siguiente_dia_gestionable(date(2026, 9, 11)) == date(2026, 9, 12)


def test_un_sabado_feriado_no_es_gestionable() -> None:
    # Ano Nuevo 2028 cae en sabado: desde el viernes 31 se salta el sabado feriado y el domingo.
    assert date(2028, 1, 1).weekday() == 5
    assert date(2028, 1, 1) in {f.fecha for f in feriados_de_ley(2028)}

    assert _servicio().siguiente_dia_gestionable(date(2027, 12, 31)) == date(2028, 1, 3)


def test_un_sabado_registrado_como_no_laborable_no_es_gestionable() -> None:
    servicio = _servicio(_agregado(date(2026, 9, 12)))

    assert servicio.siguiente_dia_gestionable(date(2026, 9, 11)) == date(2026, 9, 14)


def test_un_sabado_con_el_feriado_retirado_vuelve_a_ser_gestionable() -> None:
    retiro = ExcepcionCalendario(date(2028, 1, 1), TipoExcepcion.RETIRADO, "Cambio de ley")

    assert _servicio(retiro).siguiente_dia_gestionable(date(2027, 12, 31)) == date(2028, 1, 1)


def test_el_domingo_nunca_es_gestionable() -> None:
    servicio = _servicio()

    assert servicio.siguiente_dia_gestionable(date(2026, 9, 12)) == date(2026, 9, 14)
    assert servicio.siguiente_dia_gestionable(date(2026, 9, 13)) == date(2026, 9, 14)
    assert date(2026, 9, 13) not in servicio.proximos_dias_gestionables(10, date(2026, 9, 6))


# --- Los proximos N dias -------------------------------------------------------------------------


def test_los_proximos_son_posteriores_a_desde_aunque_desde_sea_gestionable() -> None:
    assert _servicio().proximos_dias_gestionables(3, date(2026, 9, 14)) == [
        date(2026, 9, 15),
        date(2026, 9, 16),
        date(2026, 9, 17),
    ]


def test_semana_santa_salta_jueves_y_viernes_y_conserva_el_sabado() -> None:
    assert _servicio().proximos_dias_gestionables(4, date(2026, 4, 1)) == [
        date(2026, 4, 4),  # sabado
        date(2026, 4, 6),  # el domingo 5 es Pascua y no se envia
        date(2026, 4, 7),
        date(2026, 4, 8),
    ]


def test_una_semana_que_cruza_fin_de_mes() -> None:
    assert _servicio().proximos_dias_gestionables(6, date(2026, 9, 28)) == [
        date(2026, 9, 29),
        date(2026, 9, 30),
        date(2026, 10, 1),
        date(2026, 10, 2),
        date(2026, 10, 3),  # sabado
        date(2026, 10, 5),
    ]


def test_una_semana_que_cruza_el_fin_de_ano() -> None:
    # Ano Nuevo 2027 es viernes: se salta, y el sabado 2 si se envia.
    assert _servicio().proximos_dias_gestionables(7, date(2026, 12, 28)) == [
        date(2026, 12, 29),
        date(2026, 12, 30),
        date(2026, 12, 31),
        date(2027, 1, 2),
        date(2027, 1, 4),
        date(2027, 1, 5),
        date(2027, 1, 6),
    ]


def test_sin_fecha_parten_de_hoy_en_lima() -> None:
    # 03:00 UTC del lunes 14 son las 22:00 del domingo 13 en Lima.
    servicio = CalendarioService(
        RepositorioCalendarioFalso(), reloj=lambda: datetime(2026, 9, 14, 3, 0, tzinfo=UTC)
    )

    assert servicio.proximos_dias_gestionables(2) == [date(2026, 9, 14), date(2026, 9, 15)]


def test_un_dia_decretado_se_salta_en_los_proximos() -> None:
    servicio = _servicio(_agregado(date(2026, 9, 15)))

    assert servicio.proximos_dias_gestionables(2, date(2026, 9, 14)) == [
        date(2026, 9, 16),
        date(2026, 9, 17),
    ]


# --- El rango de N -------------------------------------------------------------------------------


def test_el_tope_inicial_es_31() -> None:
    assert MAXIMO_PROXIMOS_POR_DEFECTO == 31
    assert Settings().maximo_proximos_dias == 31


@pytest.mark.parametrize("n", [1, 31])
def test_los_extremos_del_rango_valen(n) -> None:
    assert len(_servicio().proximos_dias_gestionables(n, date(2026, 9, 14))) == n


@pytest.mark.parametrize("n", [0, -1, 32, 10_000])
def test_fuera_de_rango_se_rechaza_indicando_el_rango(n) -> None:
    with pytest.raises(ProximosFueraDeRango) as error:
        _servicio().proximos_dias_gestionables(n, date(2026, 9, 14))

    assert (error.value.pedido, error.value.minimo, error.value.maximo) == (n, 1, 31)


def test_el_tope_es_configurable() -> None:
    servicio = _servicio(maximo_proximos=5)

    assert len(servicio.proximos_dias_gestionables(5, date(2026, 9, 14))) == 5
    with pytest.raises(ProximosFueraDeRango) as error:
        servicio.proximos_dias_gestionables(6, date(2026, 9, 14))
    assert error.value.maximo == 5


# --- Propiedad (semilla fija) --------------------------------------------------------------------


def test_propiedad_los_proximos_respetan_la_regla_en_cualquier_calendario() -> None:
    rng = random.Random(70)
    for _ in range(150):
        excepciones = []
        for anio in range(2024, 2032):
            feriados = [f.fecha for f in feriados_de_ley(anio)]
            for fecha in rng.sample(feriados, rng.randrange(0, 4)):
                excepciones.append(ExcepcionCalendario(fecha, TipoExcepcion.RETIRADO, "Retiro"))
            for _ in range(rng.randrange(0, 12)):
                fecha = date(anio, 1, 1) + timedelta(days=rng.randrange(365))
                if fecha not in feriados:
                    excepciones.append(_agregado(fecha))
        servicio = _servicio(*{e.fecha: e for e in excepciones}.values())
        desde = date(2024, 1, 1) + timedelta(days=rng.randrange(365 * 7))
        n = rng.randint(1, 31)

        dias = servicio.proximos_dias_gestionables(n, desde)

        assert len(dias) == n
        assert dias[0] == servicio.siguiente_dia_gestionable(desde)
        assert dias[0] > desde
        assert all(a < b for a, b in zip(dias, dias[1:], strict=False))  # orden estricto
        for dia in dias:
            assert dia.weekday() != 6  # ningun domingo
            assert dia not in servicio.fechas_no_laborables(dia.year)  # ni feriado ni excepcion
        # No se salta ningun dia gestionable: todo lo que queda entre dos elegidos es domingo o
        # no laborable.
        todos = [desde, *dias]
        for antes, despues in zip(todos, todos[1:], strict=False):
            for omitido in (antes + timedelta(days=k) for k in range(1, (despues - antes).days)):
                assert omitido.weekday() == 6 or omitido in servicio.fechas_no_laborables(
                    omitido.year
                )


# --- La API --------------------------------------------------------------------------------------


@pytest.fixture
def cliente():
    servicio = _servicio(_agregado(date(2026, 9, 15)))
    app.dependency_overrides[obtener_servicio_calendario] = lambda: servicio
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_get_proximos_devuelve_las_fechas_en_orden(cliente) -> None:
    respuesta = cliente.get("/calendario/proximos", params={"desde": "2026-09-10", "n": 4})

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "desde": "2026-09-10",
        "n": 4,
        "fechas": ["2026-09-11", "2026-09-12", "2026-09-14", "2026-09-16"],
    }


def test_get_proximos_sin_desde_parte_de_hoy_en_lima(cliente) -> None:
    cuerpo = cliente.get("/calendario/proximos", params={"n": 2}).json()

    assert cuerpo == {"desde": "2026-09-14", "n": 2, "fechas": ["2026-09-16", "2026-09-17"]}


def test_el_primero_coincide_con_el_siguiente_dia_gestionable(cliente) -> None:
    desde = {"desde": "2026-09-12"}

    siguiente = cliente.get("/calendario/siguiente-dia-gestionable", params=desde).json()
    proximos = cliente.get("/calendario/proximos", params={**desde, "n": 1}).json()

    assert proximos["fechas"] == [siguiente["fecha"]]


@pytest.mark.parametrize("n", [0, 32, -3])
def test_n_fuera_de_rango_es_400_con_codigo_y_rango(cliente, n) -> None:
    respuesta = cliente.get("/calendario/proximos", params={"n": n})

    assert respuesta.status_code == 400
    cuerpo = respuesta.json()
    assert cuerpo["codigo"] == "proximos_fuera_de_rango"
    assert (cuerpo["minimo"], cuerpo["maximo"]) == (1, 31)
    assert "1" in cuerpo["detail"] and "31" in cuerpo["detail"]


def test_sin_n_o_con_un_n_que_no_es_numero_es_422(cliente) -> None:
    assert cliente.get("/calendario/proximos").status_code == 422
    assert cliente.get("/calendario/proximos", params={"n": "muchos"}).status_code == 422

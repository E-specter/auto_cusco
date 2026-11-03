"""La fecha de envio de WhatsMKT contra el calendario comun, sin base (T-WM-B4c; RF-WM-06, 70, 71).

Siempre con un reloj fijo (`tests/ayudas/calendario_falso.py`): nunca el real. El «hoy» de las
pruebas es el lunes 26 de octubre de 2026, salvo donde se dice otra cosa. Telefonos 900000xxx.
"""

from datetime import UTC, date, datetime

import pytest

from app.core.entities.calendario import ExcepcionCalendario, ProximosFueraDeRango, TipoExcepcion
from app.core.entities.whatsmkt import CodigoWhatsmkt
from app.core.services.plataformas.whatsmkt.programacion import (
    FechaNoGestionable,
    ProgramacionWhatsmktService,
)
from tests.ayudas.calendario_falso import (
    LIMA,
    calendario_de_prueba,
    programacion_de_prueba,
)
from tests.test_whatsmkt_contactos import producto
from tests.test_whatsmkt_previa import previa

LUNES_26 = date(2026, 10, 26)
# Las 23:30 de Lima del sabado 7 de noviembre son las 04:30 UTC del domingo 8.
SABADO_23_30_LIMA = datetime(2026, 11, 7, 23, 30, tzinfo=LIMA)
SABADO_23_30_EN_UTC = datetime(2026, 11, 8, 4, 30, tzinfo=UTC)


def rechazo(programacion: ProgramacionWhatsmktService, fecha: date) -> FechaNoGestionable:
    with pytest.raises(FechaNoGestionable) as error:
        programacion.validar(fecha)
    return error.value


# --- La sugerida ------------------------------------------------------------------------------


def test_la_sugerida_es_el_siguiente_dia_gestionable_despues_de_hoy() -> None:
    programacion = programacion_de_prueba()

    assert programacion.sugerida() == date(2026, 10, 27)  # el martes
    assert programacion.programacion(3).sugerida == date(2026, 10, 27)


def test_la_minima_es_la_misma_que_la_sugerida_porque_hoy_nunca_sirve() -> None:
    resultado = programacion_de_prueba().programacion(5)

    assert resultado.minima == resultado.sugerida == resultado.proximas[0]


def test_a_las_23_30_de_lima_del_sabado_la_sugerida_es_el_lunes() -> None:
    # Con el reloj en hora de Lima y con el mismo instante en UTC (donde ya es domingo): hoy es el
    # sabado 7 en los dos casos, y el domingo no se envia.
    for instante in (SABADO_23_30_LIMA, SABADO_23_30_EN_UTC):
        programacion = programacion_de_prueba(ahora=instante)

        assert programacion.sugerida() == date(2026, 11, 9), instante
        assert programacion.programacion(2).proximas == (date(2026, 11, 9), date(2026, 11, 10))


def test_pasada_la_medianoche_de_lima_hoy_cambia_de_dia() -> None:
    domingo_00_30_lima = datetime(2026, 11, 8, 0, 30, tzinfo=LIMA)  # 05:30 UTC

    programacion = programacion_de_prueba(ahora=domingo_00_30_lima)

    assert programacion.sugerida() == date(2026, 11, 9)
    assert rechazo(programacion, date(2026, 11, 8)).sugerida == date(2026, 11, 9)  # hoy


def test_el_viernes_a_las_23_30_de_lima_el_sabado_es_valido() -> None:
    viernes_23_30_lima = datetime(2026, 11, 6, 23, 30, tzinfo=LIMA)  # sabado 04:30 UTC

    programacion = programacion_de_prueba(ahora=viernes_23_30_lima)

    assert programacion.sugerida() == date(2026, 11, 7)  # sabado: sí se envia


# --- Los proximos N ---------------------------------------------------------------------------


def test_los_proximos_n_son_los_siguientes_dias_gestionables_en_orden() -> None:
    resultado = programacion_de_prueba().programacion(7)

    assert resultado.proximas == (
        date(2026, 10, 27),
        date(2026, 10, 28),
        date(2026, 10, 29),
        date(2026, 10, 30),
        date(2026, 10, 31),  # sabado
        date(2026, 11, 2),  # el domingo 1 (y feriado) no esta
        date(2026, 11, 3),
    )


def test_los_proximos_saltan_los_feriados_y_los_dias_registrados() -> None:
    # Viernes 4 de diciembre: el 8 y el 9 son feriados de ley; el 11 se registra como no laborable.
    decretado = ExcepcionCalendario(date(2026, 12, 11), TipoExcepcion.AGREGADO, "Decretado")

    resultado = programacion_de_prueba(
        decretado, ahora=datetime(2026, 12, 4, 10, 0, tzinfo=LIMA)
    ).programacion(5)

    assert resultado.proximas == (
        date(2026, 12, 5),  # sabado
        date(2026, 12, 7),
        date(2026, 12, 10),
        date(2026, 12, 12),  # el 11 esta registrado
        date(2026, 12, 14),
    )


def test_n_va_de_1_al_tope_del_calendario() -> None:
    programacion = ProgramacionWhatsmktService(calendario_de_prueba(maximo_proximos=5))

    assert len(programacion.programacion(1).proximas) == 1
    assert len(programacion.programacion(5).proximas) == 5
    for fuera in (0, 6, -1):
        with pytest.raises(ProximosFueraDeRango) as error:
            programacion.programacion(fuera)
        assert (error.value.minimo, error.value.maximo) == (1, 5)


# --- Validar la fecha -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fecha",
    [date(2026, 10, 27), date(2026, 10, 31), date(2026, 11, 2), date(2027, 1, 4)],
    ids=["manana", "sabado", "lunes", "enero-2027"],
)
def test_un_dia_de_lunes_a_sabado_posterior_a_hoy_es_valido(fecha) -> None:
    programacion_de_prueba().validar(fecha)  # no lanza


@pytest.mark.parametrize(
    ("fecha", "sugerida"),
    [
        (date(2026, 10, 26), date(2026, 10, 27)),  # hoy nunca es valido
        (date(2026, 10, 25), date(2026, 10, 27)),  # ayer, un domingo
        (date(2026, 10, 20), date(2026, 10, 27)),  # el pasado: la sugerida es despues de hoy
        (date(2026, 11, 8), date(2026, 11, 9)),  # domingo
        (date(2026, 11, 1), date(2026, 11, 2)),  # domingo y feriado
        (date(2026, 12, 8), date(2026, 12, 10)),  # feriado de ley; el 9 tambien lo es
        (date(2026, 12, 9), date(2026, 12, 10)),
    ],
    ids=["hoy", "ayer", "pasado", "domingo", "domingo-feriado", "feriado", "feriado-seguido"],
)
def test_hoy_el_pasado_el_domingo_y_los_feriados_no_son_validos_y_traen_la_sugerida(
    fecha, sugerida
) -> None:
    error = rechazo(programacion_de_prueba(), fecha)

    assert (error.fecha, error.sugerida) == (fecha, sugerida)
    assert fecha.isoformat() in str(error) and sugerida.isoformat() in str(error)


def test_una_excepcion_registrada_no_es_gestionable() -> None:
    decretado = ExcepcionCalendario(date(2026, 11, 4), TipoExcepcion.AGREGADO, "Decretado")

    error = rechazo(programacion_de_prueba(decretado), date(2026, 11, 4))

    assert error.sugerida == date(2026, 11, 5)


def test_un_feriado_retirado_del_calendario_si_es_gestionable() -> None:
    retirado = ExcepcionCalendario(date(2026, 12, 8), TipoExcepcion.RETIRADO, "No se chambea")
    programacion = programacion_de_prueba(retirado)

    programacion.validar(date(2026, 12, 8))  # no lanza
    assert rechazo(programacion, date(2026, 12, 9)).sugerida == date(2026, 12, 10)  # sigue feriado


def test_el_dia_de_hoy_a_las_23_30_de_lima_sigue_sin_valer_aunque_en_utc_sea_otro_dia() -> None:
    programacion = programacion_de_prueba(ahora=SABADO_23_30_EN_UTC)

    assert rechazo(programacion, date(2026, 11, 7)).sugerida == date(2026, 11, 9)  # hoy en Lima
    assert rechazo(programacion, date(2026, 11, 8)).sugerida == date(2026, 11, 9)  # domingo


# --- La previsualizacion ----------------------------------------------------------------------


def problemas_de_fecha(resultado):
    return [p for p in resultado.problemas if p.codigo is CodigoWhatsmkt.FECHA_NO_GESTIONABLE]


def test_la_previa_de_una_fecha_gestionable_no_trae_el_problema() -> None:
    resultado = previa([producto(1, 0)], fecha_envio=date(2026, 11, 2))

    assert problemas_de_fecha(resultado) == []
    assert resultado.fecha_no_gestionable is None


@pytest.mark.parametrize(
    ("fecha", "sugerida"),
    [
        (date(2026, 10, 26), "2026-10-27"),  # hoy
        (date(2026, 11, 1), "2026-11-02"),  # domingo
        (date(2026, 12, 8), "2026-12-10"),  # feriado
    ],
    ids=["hoy", "domingo", "feriado"],
)
def test_la_previa_de_una_fecha_que_no_sirve_trae_el_problema_y_calcula_el_resto(
    fecha, sugerida
) -> None:
    # El corte es anterior a todas: lo unico que falla es la fecha.
    resultado = previa([producto(1, 0)], fecha_envio=fecha, corte=date(2026, 10, 1))

    [problema] = problemas_de_fecha(resultado)
    assert problema.parametros == {"fecha": fecha.isoformat(), "sugerida": sugerida}
    assert len(resultado.campanas) == 1  # lo demas se calcula igual


def test_la_previa_con_una_excepcion_registrada_rechaza_ese_dia() -> None:
    decretado = ExcepcionCalendario(date(2026, 11, 3), TipoExcepcion.AGREGADO, "Decretado")

    resultado = previa(
        [producto(1, 0)],
        fecha_envio=date(2026, 11, 3),
        programacion=programacion_de_prueba(decretado),
    )

    assert problemas_de_fecha(resultado)[0].parametros["sugerida"] == "2026-11-04"


def test_sin_fecha_de_envio_se_usa_la_sugerida_y_no_hoy() -> None:
    # Hoy es el lunes 2 de noviembre (el corte): sin fecha, la previa usa el martes 3.
    lunes_2 = datetime(2026, 11, 2, 10, 0, tzinfo=LIMA)

    resultado = previa(
        [producto(1, 0)], fecha_envio=None, programacion=programacion_de_prueba(ahora=lunes_2)
    )

    assert resultado.fecha_envio == date(2026, 11, 3)
    assert problemas_de_fecha(resultado) == []

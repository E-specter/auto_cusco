"""Reglas puras de la configuracion de WhatsMKT, sin base (T-WM-B1)."""

from dataclasses import replace
from datetime import date, time

import pytest

from app.core.entities.whatsmkt import (
    CLAVES_SEGMENTOS,
    PLANTILLA_NOMBRE_POR_DEFECTO,
    SEGMENTOS_POR_DEFECTO,
    CodigoWhatsmkt,
    ConfiguracionWhatsmkt,
    ErrorWhatsmkt,
    Horario,
    SegmentoWhatsmkt,
)
from app.core.services import segmentacion
from app.core.services.plataformas.whatsmkt import configuracion, segmentos
from tests.speech_congelado import cargar_migracion

MIGRACION = cargar_migracion("b7e4c1a9d826_configuracion_segmentos_y_adjuntos_de_whatsmkt.py")


def _seg(clave: str, desde: int | None, hasta: int | None) -> SegmentoWhatsmkt:
    return SegmentoWhatsmkt(clave, clave.title(), desde, hasta, 0)


# --- Valores por defecto ------------------------------------------------------------------------


def test_la_configuracion_por_defecto_son_los_supuestos_del_documento() -> None:
    c = ConfiguracionWhatsmkt()

    assert c.horario_1 == Horario(time(8, 0), time(14, 0))
    assert c.horario_2 == Horario(time(14, 0), time(20, 0))
    assert c.plantilla_nombre == "CUZCO_Vencida ({segmento}) whatsapp {fecha_corte}"
    assert (c.tope_mensaje, c.tope_video, c.tope_audio, c.tope_pdf) == (
        4096,
        16_000_000,
        16_000_000,
        16_000_000,
    )
    assert c.definicion_defecto_id is None
    assert configuracion.configuracion_valida(c) == c  # el defecto cumple sus propias reglas


def test_las_claves_fijas_son_las_de_los_segmentos_por_defecto() -> None:
    assert CLAVES_SEGMENTOS == {"preventivo", "tramo_2", "mayores_2"}


def test_los_segmentos_por_defecto_son_los_de_s_wm_1_y_cumplen_sus_reglas() -> None:
    assert [(s.clave, s.desde, s.hasta) for s in SEGMENTOS_POR_DEFECTO] == [
        ("preventivo", None, 0),
        ("tramo_2", 1, 8),
        ("mayores_2", 9, None),
    ]
    assert segmentos.segmentos_validos(SEGMENTOS_POR_DEFECTO) == SEGMENTOS_POR_DEFECTO


def test_la_siembra_de_la_migracion_es_la_misma_que_la_de_las_entidades() -> None:
    # La migracion copia los valores a proposito (no importa codigo de la app): aqui no se desvian.
    assert MIGRACION.PLANTILLA_POR_DEFECTO == PLANTILLA_NOMBRE_POR_DEFECTO
    sembrados = [
        SegmentoWhatsmkt(s["clave"], s["etiqueta"], s["desde"], s["hasta"], s["orden"])
        for s in MIGRACION.SEGMENTOS
    ]
    assert tuple(sembrados) == SEGMENTOS_POR_DEFECTO


# --- Horarios -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("inicio", "fin"),
    [(time(8, 0), time(8, 1)), (time(0, 0), time(23, 59)), (time(13, 59), time(14, 0))],
)
def test_un_horario_con_inicio_anterior_al_fin_es_valido(inicio: time, fin: time) -> None:
    assert configuracion.horario_valido(Horario(inicio, fin))


@pytest.mark.parametrize(
    ("inicio", "fin"),
    [(time(8, 0), time(8, 0)), (time(14, 0), time(8, 0)), (time(23, 59), time(0, 0))],
)
def test_un_horario_con_inicio_igual_o_posterior_al_fin_no_es_valido(
    inicio: time, fin: time
) -> None:
    assert not configuracion.horario_valido(Horario(inicio, fin))


@pytest.mark.parametrize(
    ("h1", "h2", "franjas"),
    [
        (Horario(time(9), time(8)), Horario(time(14), time(20)), ["horario_1"]),
        (Horario(time(8), time(14)), Horario(time(20), time(14)), ["horario_2"]),
        (Horario(time(8), time(8)), Horario(time(20), time(20)), ["horario_1", "horario_2"]),
    ],
)
def test_el_error_de_horario_dice_que_franja_fallo_y_si_son_las_dos_las_dos(
    h1: Horario, h2: Horario, franjas: list[str]
) -> None:
    mala = replace(ConfiguracionWhatsmkt(), horario_1=h1, horario_2=h2)

    with pytest.raises(ErrorWhatsmkt) as error:
        configuracion.configuracion_valida(mala)

    assert error.value.codigo is CodigoWhatsmkt.HORARIO_INVALIDO
    assert error.value.parametros == {"horarios": franjas}


# --- Plantilla del nombre -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "plantilla",
    [
        "CUZCO ({segmento}) {fecha_corte}",
        "{fecha_corte}",
        "{segmento} {segmento}",
        "Campana fija sin variables",
    ],
)
def test_la_plantilla_con_las_variables_validas_o_sin_variables_pasa(plantilla: str) -> None:
    assert configuracion.plantilla_valida(plantilla) == plantilla


def test_la_plantilla_se_recorta_y_si_queda_vacia_vuelve_la_de_por_defecto() -> None:
    assert configuracion.plantilla_valida("  hola {segmento}  ") == "hola {segmento}"
    assert configuracion.plantilla_valida("   ") == PLANTILLA_NOMBRE_POR_DEFECTO
    assert configuracion.plantilla_valida(None) == PLANTILLA_NOMBRE_POR_DEFECTO


def test_una_variable_desconocida_se_rechaza_diciendo_cual() -> None:
    with pytest.raises(ErrorWhatsmkt) as error:
        configuracion.plantilla_valida("{segmento} {horario}")

    assert error.value.codigo is CodigoWhatsmkt.VARIABLE_INEXISTENTE
    assert error.value.parametros == {"variable": "{horario}"}


@pytest.mark.parametrize("plantilla", ["{segmento", "segmento}", "{}", "{{segmento}}"])
def test_una_llave_suelta_se_rechaza(plantilla: str) -> None:
    with pytest.raises(ErrorWhatsmkt) as error:
        configuracion.plantilla_valida(plantilla)

    assert error.value.codigo is CodigoWhatsmkt.VARIABLE_INEXISTENTE


# --- Segmentos ----------------------------------------------------------------------------------


def test_los_segmentos_se_ordenan_de_menor_a_mayor_y_reciben_su_orden() -> None:
    desordenados = [_seg("c", 9, None), _seg("a", None, 0), _seg("b", 1, 8)]

    validos = segmentos.segmentos_validos(desordenados)

    assert [(s.clave, s.orden) for s in validos] == [("a", 0), ("b", 1), ("c", 2)]


def test_un_solo_segmento_sin_piso_ni_tope_cubre_todo() -> None:
    assert [s.clave for s in segmentos.segmentos_validos([_seg("todos", None, None)])] == ["todos"]


def test_la_etiqueta_se_recorta() -> None:
    [uno] = segmentos.segmentos_validos([SegmentoWhatsmkt("x", " Equis  ", None, None, 7)])

    assert (uno.etiqueta, uno.orden) == ("Equis", 0)


def test_un_hueco_entre_segmentos_se_rechaza_diciendo_los_dias_sin_segmento() -> None:
    with pytest.raises(ErrorWhatsmkt) as error:
        segmentos.segmentos_validos([_seg("a", None, 0), _seg("b", 4, None)])

    assert error.value.codigo is CodigoWhatsmkt.SEGMENTOS_CON_HUECO
    assert error.value.parametros == {"desde": 1, "hasta": 3}


@pytest.mark.parametrize(
    ("tabla", "extremos"),
    [
        ([_seg("a", 0, 5), _seg("b", 6, None)], {"desde": None, "hasta": -1}),  # sin piso
        ([_seg("a", None, 5), _seg("b", 6, 9)], {"desde": 10, "hasta": None}),  # sin tope
    ],
)
def test_un_hueco_arriba_o_abajo_de_la_tabla_se_rechaza(tabla, extremos) -> None:
    with pytest.raises(ErrorWhatsmkt) as error:
        segmentos.segmentos_validos(tabla)

    assert error.value.codigo is CodigoWhatsmkt.SEGMENTOS_CON_HUECO
    assert error.value.parametros == extremos


@pytest.mark.parametrize(
    "tabla",
    [
        [_seg("a", None, 3), _seg("b", 3, None)],  # se tocan en el 3
        [_seg("a", None, 8), _seg("b", 1, 5), _seg("c", 9, None)],  # b esta dentro de a
        [_seg("a", None, None), _seg("b", 1, None)],  # a cubre todo
        [_seg("a", None, 0), _seg("b", None, 5), _seg("c", 6, None)],  # dos sin piso
    ],
)
def test_segmentos_que_se_superponen_se_rechazan(tabla: list[SegmentoWhatsmkt]) -> None:
    with pytest.raises(ErrorWhatsmkt) as error:
        segmentos.segmentos_validos(tabla)

    assert error.value.codigo is CodigoWhatsmkt.SEGMENTOS_SUPERPUESTOS
    assert set(error.value.parametros) == {"segmento", "fila"}


def test_el_error_de_superposicion_nombra_con_quien_se_pisa_cada_fila() -> None:
    with pytest.raises(ErrorWhatsmkt) as error:
        segmentos.segmentos_validos([_seg("a", None, 3), _seg("b", 3, None)])

    assert error.value.parametros == {"segmento": "a", "fila": "b"}


def test_una_tabla_vacia_se_rechaza() -> None:
    with pytest.raises(ErrorWhatsmkt):
        segmentos.segmentos_validos([])


@pytest.mark.parametrize(
    ("dias", "clave"),
    [(-5, "preventivo"), (0, "preventivo"), (1, "tramo_2"), (8, "tramo_2"), (9, "mayores_2")]
    + [(500, "mayores_2")],
)
def test_segmento_de_en_los_bordes(dias: int, clave: str) -> None:
    assert segmentos.segmento_de(dias, SEGMENTOS_POR_DEFECTO).clave == clave


def test_segmento_de_sin_dias_no_da_segmento() -> None:
    assert segmentos.segmento_de(None, SEGMENTOS_POR_DEFECTO) is None


def test_segmento_de_con_los_dias_ajustados_de_rf_55() -> None:
    # 3 dias de atraso al corte (1 de nov): enviado el 6 son 8 dias ajustados, el 7 son 9.
    def segmento(envio: date) -> str:
        dias = segmentacion.dias_ajustados(3, date(2026, 11, 1), envio)
        return segmentos.segmento_de(dias, SEGMENTOS_POR_DEFECTO).clave

    assert segmento(date(2026, 11, 6)) == "tramo_2"
    assert segmento(date(2026, 11, 7)) == "mayores_2"

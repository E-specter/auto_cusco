"""Segmentacion compartida (RF-50, seccion 7 del diseno): tabla de rangos y criterio por campo.

El criterio por defecto es el segmento financiero CALCULADO desde los dias de atraso (el campo
`segmento_financiero` de la sabana llega mal cargado). Ningun codigo del nucleo nombra ese campo:
el criterio es un dato de la definicion.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.core.entities.segmentacion import (
    TABLA_RANGOS_POR_DEFECTO,
    CriterioCalculado,
    CriterioCampo,
    PoliticaSinSegmento,
    RangoDias,
    Segmentacion,
    SegmentacionInvalida,
)
from app.core.services import segmentacion

CLAVES = ["preventiva", "1_a_8", "9_a_30", "31_a_60", "61_a_90", "91_a_120"]


def _calculado(**cambios) -> Segmentacion:
    return Segmentacion(CriterioCalculado(**cambios))


# --- La tabla por defecto es la de MOWA MES de hoy ---------------------------------------------


def test_la_tabla_por_defecto_son_los_seis_rangos_de_mowa_mes() -> None:
    assert [(r.clave, r.etiqueta, r.desde, r.hasta) for r in TABLA_RANGOS_POR_DEFECTO] == [
        ("preventiva", "Preventiva", None, 0),
        ("1_a_8", "1 a 8", 1, 8),
        ("9_a_30", "9 a 30", 9, 30),
        ("31_a_60", "31 a 60", 31, 60),
        ("61_a_90", "61 a 90", 61, 90),
        ("91_a_120", "91 a 120", 91, 120),
    ]


def test_la_tabla_por_defecto_es_valida_y_contigua() -> None:
    segmentacion.validar_tabla(TABLA_RANGOS_POR_DEFECTO)

    for anterior, siguiente in zip(
        TABLA_RANGOS_POR_DEFECTO, TABLA_RANGOS_POR_DEFECTO[1:], strict=False
    ):
        assert siguiente.desde == anterior.hasta + 1


@pytest.mark.parametrize(
    ("dias", "clave"),
    [
        (-30, "preventiva"),
        (0, "preventiva"),  # S-MM-6: 0 dias es Preventiva
        (1, "1_a_8"),
        (8, "1_a_8"),
        (9, "9_a_30"),
        (30, "9_a_30"),
        (31, "31_a_60"),
        (60, "31_a_60"),
        (61, "61_a_90"),
        (90, "61_a_90"),
        (91, "91_a_120"),
        (120, "91_a_120"),
        (121, None),  # mas de 120 dias: sin segmento
        (10_000, None),
    ],
)
def test_los_bordes_de_cada_rango(dias, clave) -> None:
    rango = segmentacion.rango_de(dias, TABLA_RANGOS_POR_DEFECTO)

    assert (rango.clave if rango else None) == clave


def test_un_decimal_entero_cae_donde_el_entero() -> None:
    assert segmentacion.rango_de(Decimal("45"), TABLA_RANGOS_POR_DEFECTO).clave == "31_a_60"
    # Un valor con decimales entre dos rangos contiguos (8,5) cae en el hueco: sin segmento,
    # como hoy en MOWA MES. Los dias de atraso de la cartera son enteros.
    assert segmentacion.rango_de(Decimal("8.5"), TABLA_RANGOS_POR_DEFECTO) is None


# --- Dias ajustados -----------------------------------------------------------------------------


def test_dias_ajustados_suma_los_dias_entre_corte_y_envio() -> None:
    assert segmentacion.dias_ajustados(4, date(2026, 9, 1), date(2026, 9, 13)) == 16
    assert segmentacion.dias_ajustados(4, date(2026, 9, 13), date(2026, 9, 13)) == 4
    assert segmentacion.dias_ajustados(4, date(2026, 9, 13), date(2026, 9, 1)) == -8


# --- Criterio calculado -------------------------------------------------------------------------


def test_el_criterio_calculado_lee_dias_atraso_por_defecto() -> None:
    assert segmentacion.segmento_de(_calculado(), {"dias_atraso": 45}) == "31_a_60"
    assert CriterioCalculado().variable_dias == "dias_atraso"


def test_el_criterio_calculado_puede_leer_otra_variable_ya_ajustada() -> None:
    criterio = _calculado(variable_dias="dias_atraso_ajustados")

    producto = {"dias_atraso": 4, "dias_atraso_ajustados": 25}

    assert segmentacion.segmento_de(criterio, producto) == "9_a_30"


@pytest.mark.parametrize("dias", [None, "", "  ", "abc", True, [1], 1.5j])
def test_sin_dias_usables_no_hay_segmento(dias) -> None:
    assert segmentacion.segmento_de(_calculado(), {"dias_atraso": dias}) is None


def test_una_fila_sin_la_variable_no_tiene_segmento() -> None:
    assert segmentacion.segmento_de(_calculado(), {}) is None


def test_el_criterio_calculado_usa_la_tabla_de_la_definicion() -> None:
    tabla = (
        RangoDias("al_dia", "Al dia", None, 0),
        RangoDias("temprana", "Temprana", 1, 15),
        RangoDias("tardia", "Tardia", 16, None),
    )
    criterio = _calculado(tabla=tabla)

    assert segmentacion.segmento_de(criterio, {"dias_atraso": 15}) == "temprana"
    assert segmentacion.segmento_de(criterio, {"dias_atraso": 16}) == "tardia"
    assert segmentacion.segmento_de(criterio, {"dias_atraso": 9999}) == "tardia"  # sin limite


def test_no_se_nombra_el_segmento_financiero_de_la_sabana() -> None:
    producto = {"segmento_financiero": "mal cargado", "dias_atraso": 10}

    assert segmentacion.segmento_de(_calculado(), producto) == "9_a_30"


# --- Criterio por campo categorico -------------------------------------------------------------


def test_el_criterio_por_campo_devuelve_el_valor_tal_cual() -> None:
    criterio = Segmentacion(CriterioCampo("segmento_financiero"))

    assert segmentacion.segmento_de(criterio, {"segmento_financiero": "Vigente"}) == "Vigente"
    assert segmentacion.segmento_de(criterio, {"segmento_financiero": "vigente"}) == "vigente"
    assert segmentacion.segmento_de(criterio, {"segmento_financiero": 7}) == "7"
    assert segmentacion.segmento_de(criterio, {"segmento_financiero": False}) == "False"


@pytest.mark.parametrize("valor", [None, "", "   ", "\t"])
def test_un_campo_vacio_no_tiene_segmento(valor) -> None:
    criterio = Segmentacion(CriterioCampo("tramo_actual"))

    assert segmentacion.segmento_de(criterio, {"tramo_actual": valor}) is None


def test_el_valor_del_campo_conserva_sus_espacios_y_solo_se_ignora_el_vacio() -> None:
    criterio = Segmentacion(CriterioCampo("tramo_actual"))

    assert segmentacion.segmento_de(criterio, {"tramo_actual": " Tramo 2 "}) == " Tramo 2 "


# --- Politica sin segmento y segmentos posibles -------------------------------------------------


def test_la_politica_por_defecto_es_excluir() -> None:
    assert Segmentacion(CriterioCalculado()).politica is PoliticaSinSegmento.EXCLUIR
    assert {p.value for p in PoliticaSinSegmento} == {"excluir", "usar_por_defecto"}


def test_los_segmentos_posibles_salen_de_la_tabla_y_un_campo_no_los_conoce() -> None:
    assert segmentacion.segmentos_posibles(_calculado()) == tuple(CLAVES)
    assert segmentacion.segmentos_posibles(Segmentacion(CriterioCampo("tramo_actual"))) is None


# --- Validacion de la tabla ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tabla", "motivo"),
    [
        ((), "vacia"),
        ((RangoDias("a", "A", 1, 5), RangoDias("a", "B", 6, 9)), "clave repetida"),
        ((RangoDias("", "A", 1, 5),), "clave vacia"),
        ((RangoDias("a", "  ", 1, 5),), "etiqueta vacia"),
        ((RangoDias("a", "A", 5, 1),), "desde mayor que hasta"),
        ((RangoDias("a", "A", 1, 5), RangoDias("b", "B", 5, 9)), "se pisan en el 5"),
        ((RangoDias("a", "A", None, None), RangoDias("b", "B", 1, 2)), "uno sin limites pisa"),
        ((RangoDias("a", "A", 1, 10), RangoDias("b", "B", 3, 4)), "uno dentro de otro"),
    ],
)
def test_una_tabla_mal_armada_se_rechaza(tabla, motivo) -> None:
    with pytest.raises(SegmentacionInvalida):
        segmentacion.validar_tabla(tabla)


def test_una_tabla_con_huecos_es_valida_y_lo_que_cae_en_el_hueco_no_tiene_segmento() -> None:
    tabla = (RangoDias("a", "A", 1, 5), RangoDias("b", "B", 10, 15))
    segmentacion.validar_tabla(tabla)

    assert segmentacion.rango_de(7, tabla) is None


def test_la_tabla_puede_venir_desordenada() -> None:
    tabla = (RangoDias("b", "B", 10, 15), RangoDias("a", "A", 1, 5))
    segmentacion.validar_tabla(tabla)

    assert segmentacion.rango_de(3, tabla).clave == "a"
    assert segmentacion.rango_de(12, tabla).clave == "b"


def test_validar_la_segmentacion_valida_la_tabla_de_un_criterio_calculado() -> None:
    mala = Segmentacion(CriterioCalculado(tabla=(RangoDias("a", "A", 5, 1),)))

    with pytest.raises(SegmentacionInvalida):
        segmentacion.validar(mala)
    segmentacion.validar(Segmentacion(CriterioCalculado()))
    segmentacion.validar(Segmentacion(CriterioCampo("tramo_actual")))


@pytest.mark.parametrize("campo", ["", "   "])
def test_un_criterio_por_campo_necesita_el_nombre_del_campo(campo) -> None:
    with pytest.raises(SegmentacionInvalida):
        segmentacion.validar(Segmentacion(CriterioCampo(campo)))


def test_un_criterio_calculado_necesita_el_nombre_de_la_variable_de_dias() -> None:
    with pytest.raises(SegmentacionInvalida):
        segmentacion.validar(_calculado(variable_dias=""))

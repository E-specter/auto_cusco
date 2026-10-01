"""D3: la tabla de rangos de MOWA MES sale de la del nucleo y no se movio nada (B2).

`RANGOS_SEGMENTO` se arma desde `TABLA_RANGOS_POR_DEFECTO`: hay una sola tabla. El enum `Segmento`
sigue siendo de MOWA MES y sus valores tienen que coincidir con las claves del nucleo.
Condiciones de coordinador_modulo_mowa_mes: los 6 rangos con `hasta` cerrado (91 a 120 termina en
120: mas de 120 dias ajustados queda en `sin_speech`), S-MM-6 (0 dias es Preventiva) y un dato
vacio sin segmento.
"""

from datetime import date

import pytest

from app.core.entities.mowa_mes import (
    RANGOS_SEGMENTO,
    CodigoMowaMes,
    RangoSegmento,
    Segmento,
)
from app.core.entities.segmentacion import TABLA_RANGOS_POR_DEFECTO
from app.core.services import segmentacion as nucleo
from app.core.services.plataformas.mowa_mes import segmentos, speech
from app.core.services.plataformas.mowa_mes.campana import Exclusion, FilaCarga, evaluar_producto
from tests.test_mowa_mes_campana import producto
from tests.test_mowa_mes_speech import ORIGINAL

# Los valores de hoy, escritos a mano: no salen de la tabla que se esta comprobando.
RANGOS_DE_HOY = [
    (Segmento.PREVENTIVA, "Preventiva", None, 0),
    (Segmento.DE_1_A_8, "1 a 8", 1, 8),
    (Segmento.DE_9_A_30, "9 a 30", 9, 30),
    (Segmento.DE_31_A_60, "31 a 60", 31, 60),
    (Segmento.DE_61_A_90, "61 a 90", 61, 90),
    (Segmento.DE_91_A_120, "91 a 120", 91, 120),
]


def test_las_claves_del_nucleo_coinciden_con_el_enum_segmento() -> None:
    claves = [rango.clave for rango in TABLA_RANGOS_POR_DEFECTO]

    assert claves == [segmento.value for segmento in Segmento]
    assert set(claves) == {segmento.value for segmento in Segmento}


def test_los_seis_rangos_de_mowa_mes_son_los_de_hoy() -> None:
    assert [(r.segmento, r.etiqueta, r.desde, r.hasta) for r in RANGOS_SEGMENTO] == RANGOS_DE_HOY


def test_la_tabla_de_mowa_mes_se_arma_desde_la_del_nucleo_y_no_hay_dos() -> None:
    desde_el_nucleo = tuple(
        RangoSegmento(Segmento(r.clave), r.etiqueta, r.desde, r.hasta)
        for r in TABLA_RANGOS_POR_DEFECTO
    )

    assert RANGOS_SEGMENTO == desde_el_nucleo
    assert len(RANGOS_SEGMENTO) == len(TABLA_RANGOS_POR_DEFECTO) == 6


def test_ningun_rango_de_mowa_mes_tiene_hasta_abierto() -> None:
    assert all(rango.hasta is not None for rango in RANGOS_SEGMENTO)
    assert RANGOS_SEGMENTO[-1].hasta == 120


def test_mas_de_120_dias_no_tiene_segmento_ni_speech() -> None:
    assert segmentos.rango_de(120).segmento is Segmento.DE_91_A_120
    assert segmentos.rango_de(121) is None
    assert nucleo.rango_de(121, TABLA_RANGOS_POR_DEFECTO) is None


def test_cero_dias_es_preventiva_s_mm_6() -> None:
    assert segmentos.rango_de(0).segmento is Segmento.PREVENTIVA
    assert segmentos.rango_de(-30).segmento is Segmento.PREVENTIVA


def test_sin_dias_no_hay_segmento_en_el_nucleo_y_en_mowa_mes() -> None:
    assert nucleo.rango_de(None, TABLA_RANGOS_POR_DEFECTO) is None
    assert segmentos.rango_de(None) is None


def test_un_producto_sin_dias_de_atraso_termina_en_sin_speech_por_evaluar_producto() -> None:
    constructor = speech.ConstructorMensajes(ORIGINAL, "900000123")
    dia = date(2026, 9, 1)

    sin_dias = evaluar_producto(producto(1, dias_atraso=None), dia, dia, constructor)
    pasado = evaluar_producto(producto(2, dias_atraso=121), dia, dia, constructor)
    en_el_borde = evaluar_producto(producto(3, dias_atraso=120), dia, dia, constructor)

    assert sin_dias == Exclusion(producto(1)["pagare"], CodigoMowaMes.SIN_SPEECH)
    assert pasado == Exclusion(producto(2)["pagare"], CodigoMowaMes.SIN_SPEECH)
    assert isinstance(en_el_borde, FilaCarga)
    assert en_el_borde.segmento is Segmento.DE_91_A_120


def test_los_dias_ajustados_son_los_del_nucleo_con_la_misma_firma() -> None:
    assert segmentos.dias_ajustados is nucleo.dias_ajustados
    assert segmentos.dias_ajustados(4, date(2026, 9, 1), date(2026, 9, 13)) == 16


@pytest.mark.parametrize(
    ("dias", "segmento"),
    [
        (0, "preventiva"),
        (8, "1_a_8"),
        (9, "9_a_30"),
        (60, "31_a_60"),
        (90, "61_a_90"),
        (120, "91_a_120"),
    ],
)
def test_el_nucleo_y_mowa_mes_dan_el_mismo_segmento_en_los_bordes(dias, segmento) -> None:
    assert nucleo.rango_de(dias, TABLA_RANGOS_POR_DEFECTO).clave == segmento
    assert segmentos.rango_de(dias).segmento.value == segmento


def test_rango_de_acepta_una_tabla_propia_de_mowa_mes() -> None:
    tabla = (RangoSegmento(Segmento.PREVENTIVA, "Preventiva", None, 5),)

    assert segmentos.rango_de(5, tabla).segmento is Segmento.PREVENTIVA
    assert segmentos.rango_de(6, tabla) is None


def test_un_rango_del_nucleo_sin_limite_superior_no_entra_en_mowa_mes() -> None:
    from app.core.entities.mowa_mes import _desde_el_nucleo
    from app.core.entities.segmentacion import RangoDias

    with pytest.raises(ValueError, match="limite superior"):
        _desde_el_nucleo(RangoDias("91_a_120", "91 a 120", 91, None))
    assert _desde_el_nucleo(RangoDias("91_a_120", "91 a 120", 91, 120)).hasta == 120

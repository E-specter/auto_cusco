"""Los valores de los campos adicionales y su forma guardada (T-CA-B2). Datos sinteticos."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from app.api.cartera import CampoRespuesta
from app.core.entities.mapeador import CampoDestino
from app.core.entities.sabana import Severidad
from app.core.services.ingesta_sabana.adicionales import (
    normalizar_adicional_fecha,
    normalizar_adicional_numero,
    normalizar_adicional_texto,
)
from app.core.services.ingesta_sabana.catalogo import CATALOGO_VENCIDA, campo_destino
from app.core.services.mapeador.serializacion import campo_a_dict
from tests.campos_adicionales_memoria import catalogo_con


@pytest.mark.parametrize(
    ("crudo", "esperado"),
    [
        ("150.50", "150.5"),
        ("100", "100"),
        (100, "100"),
        (7.0, "7"),
        (Decimal("0.500"), "0.5"),
        ("-0", "0"),
        ("0.00", "0"),
        (" 12 ", "12"),
        ("1E+3", "1000"),
        ("-2.25", "-2.25"),
        ("", None),
        (None, None),
        ("   ", None),
    ],
)
def test_un_numero_sale_como_decimal_canonico_o_vacio_sin_aviso(crudo, esperado) -> None:
    resultado = normalizar_adicional_numero(crudo)

    assert resultado.valor == esperado and resultado.aviso is None


@pytest.mark.parametrize(
    "crudo",
    [
        "abc",
        "12,5",
        "1.2.3",
        True,
        float("inf"),
        float("nan"),
        "NaN",
        "1E+999999",
        "1E-999999",
        "9" * 31,
    ],
)
def test_lo_que_no_es_un_numero_razonable_queda_vacio_y_avisa(crudo) -> None:
    resultado = normalizar_adicional_numero(crudo)

    assert resultado.valor is None
    assert resultado.aviso is not None
    assert (resultado.aviso.codigo, resultado.aviso.severidad) == (
        "valor_no_convertible",
        Severidad.ADVERTENCIA,
    )


@pytest.mark.parametrize(
    ("crudo", "esperado"),
    [
        ("03/08/2099", "2099-08-03"),
        (date(2099, 8, 3), "2099-08-03"),
        (datetime(2099, 8, 3, 10, 30), "2099-08-03"),
        (47000, "2028-09-04"),  # serial de Excel
        ("", None),
        (None, None),
    ],
)
def test_una_fecha_sale_en_iso_o_vacia_sin_aviso(crudo, esperado) -> None:
    resultado = normalizar_adicional_fecha(crudo)

    assert resultado.valor == esperado and resultado.aviso is None


@pytest.mark.parametrize("crudo", ["32/13/2099", "mañana", "2099-08-03x", 12.5, 1])
def test_lo_que_no_es_una_fecha_queda_vacio_y_avisa_con_el_codigo_del_adicional(crudo) -> None:
    resultado = normalizar_adicional_fecha(crudo)

    assert resultado.valor is None and resultado.aviso.codigo == "valor_no_convertible"


def test_un_texto_se_recorta_y_un_numero_entero_no_gana_un_punto_cero() -> None:
    assert normalizar_adicional_texto("  SUR ").valor == "SUR"
    assert normalizar_adicional_texto(15.0).valor == "15"
    assert normalizar_adicional_texto("").valor is None


# --- El analisis guardado ------------------------------------------------------------------------


def test_un_campo_base_se_guarda_sin_las_claves_nuevas() -> None:
    """Compatibilidad: los borradores ya guardados y los nuevos con solo campos base son iguales."""
    datos = campo_a_dict(campo_destino(CATALOGO_VENCIDA[0]))

    assert set(datos) == {"nombre", "clave_etiqueta", "tipo", "obligatorio", "alias"}


def test_un_campo_adicional_guarda_su_etiqueta_y_su_marca() -> None:
    campo = next(c for c in _campos_del_catalogo() if c.adicional)

    datos = campo_a_dict(campo)

    assert datos["adicional"] is True and datos["etiqueta"] == campo.etiqueta


def _campos_del_catalogo() -> list[CampoDestino]:
    from app.core.services.ingesta_sabana.catalogo import armar_catalogo_sabana

    return list(armar_catalogo_sabana(catalogo_con()._definiciones()).campos)


def test_el_catalogo_publico_de_la_cartera_cabe_en_la_respuesta_de_campos() -> None:
    publico = catalogo_con().catalogo_publico()

    base = CampoRespuesta(**publico["dias_atraso"])
    extra = CampoRespuesta(**publico["ad_monto_extra"])

    assert (base.adicional, base.etiqueta) == (False, None)
    assert (extra.adicional, extra.etiqueta) == (True, "Monto extra")
    archivado = CampoRespuesta(**publico["ad_antiguo"])  # se lista, marcado
    assert (archivado.archivado, archivado.etiqueta) == (True, "Campo antiguo")
    assert (base.archivado, extra.archivado) == (False, False)


def test_la_incidencia_de_un_adicional_trae_en_columna_lo_mismo_que_la_de_un_campo_base() -> None:
    """`columna` es el NOMBRE DEL CAMPO (`telefono`, `ad_monto_extra`), no el encabezado del
    archivo: la pantalla lo resuelve con el catalogo de campos (que incluye los archivados)."""
    from app.core.entities.sabana import ColumnaSabana, MapeoCabeceras, TipoCampo
    from app.core.services.ingesta_sabana.normalizador import normalizar_fila

    mapeo = MapeoCabeceras(
        columnas={
            0: ColumnaSabana("pagare", TipoCampo.CLAVE, ("pagare",), requerida=True),
            1: ColumnaSabana("telefono", TipoCampo.TELEFONO, ("telefono",)),
            2: ColumnaSabana("ad_monto_extra", TipoCampo.ADICIONAL_NUMERO, ("monto extra",)),
        },
        desconocidas={},
        faltantes=[],
    )

    fila = normalizar_fila(["000000000000000001", "123", "abc"], mapeo, 2)

    por_codigo = {i.codigo: i for i in fila.incidencias}
    assert por_codigo["telefono_invalido"].columna == "telefono"
    assert por_codigo["valor_no_convertible"].columna == "ad_monto_extra"
    assert por_codigo["valor_no_convertible"].valor_original == "abc"

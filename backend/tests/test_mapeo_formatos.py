"""Pruebas del tipado y el formato de los campos generados (RF-12)."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from app.core.entities.mapeo import (
    CampoSalida,
    FormatoFinanciero,
    TipoSalida,
    ValorNoGenerable,
)
from app.core.services.mapeo_campos import formatos


@pytest.mark.parametrize(
    ("monto", "formato", "esperado"),
    [
        (Decimal("1234.5"), FormatoFinanciero(), "1,234.50"),
        (
            Decimal("1234.5"),
            FormatoFinanciero(separador_miles=".", separador_decimal=","),
            "1.234,50",
        ),
        (Decimal("1234567.891"), FormatoFinanciero(), "1,234,567.89"),
        (Decimal("999"), FormatoFinanciero(separador_miles="", decimales=0), "999"),
        (Decimal("1234.5"), FormatoFinanciero(separador_miles=" ", decimales=0), "1 234"),
        (Decimal("-1500.25"), FormatoFinanciero(), "-1,500.25"),
        (Decimal("0"), FormatoFinanciero(), "0.00"),
    ],
)
def test_formatear_importe(monto, formato, esperado) -> None:
    assert formatos.formatear_importe(monto, formato) == esperado


def _campo(tipo: TipoSalida, **kwargs) -> CampoSalida:
    return CampoSalida(nombre="destino", plantilla="[@x]", tipo=tipo, **kwargs)


def test_texto_deja_el_valor_tal_cual() -> None:
    campo = _campo(TipoSalida.TEXTO)

    assert formatos.convertir(campo, "51987654321", None) == "51987654321"
    assert formatos.convertir(campo, "", None) == ""


def test_numero_entero_y_decimal() -> None:
    campo = _campo(TipoSalida.NUMERO)

    assert formatos.convertir(campo, "1010", None) == 1010
    assert formatos.convertir(campo, "12.50", None) == Decimal("12.50")
    assert formatos.convertir(campo, "8", Decimal("8")) == 8


def test_financiero_usa_los_separadores_configurados() -> None:
    campo = _campo(
        TipoSalida.FINANCIERO,
        formato_financiero=FormatoFinanciero(separador_miles=".", separador_decimal=","),
    )

    assert formatos.convertir(campo, "1500.5", Decimal("1500.5")) == "1.500,50"
    assert formatos.convertir(campo, "1500.5", None) == "1.500,50"


def test_fecha_nativa_o_con_formato() -> None:
    sin_formato = _campo(TipoSalida.FECHA)
    con_formato = _campo(TipoSalida.FECHA, formato_fecha="%d/%m/%Y")

    assert formatos.convertir(sin_formato, "2026-09-18", date(2026, 9, 18)) == date(2026, 9, 18)
    assert formatos.convertir(con_formato, "2026-09-18", date(2026, 9, 18)) == "18/09/2026"
    assert formatos.convertir(con_formato, "2026-09-18", None) == "18/09/2026"
    assert formatos.convertir(con_formato, "x", datetime(2026, 9, 18, 10, 30)) == "18/09/2026"


def test_un_campo_sin_dato_de_origen_queda_vacio() -> None:
    for tipo in (TipoSalida.NUMERO, TipoSalida.FECHA, TipoSalida.FINANCIERO):
        assert formatos.convertir(_campo(tipo), "", None) is None


@pytest.mark.parametrize(
    ("tipo", "texto"),
    [
        (TipoSalida.NUMERO, "mucho"),
        (TipoSalida.FINANCIERO, "S/ 100"),
        (TipoSalida.FECHA, "18/09/2026"),
    ],
)
def test_valores_que_no_se_pueden_convertir(tipo, texto) -> None:
    with pytest.raises(ValorNoGenerable) as error:
        formatos.convertir(_campo(tipo), texto, None)

    assert error.value.campo == "destino"

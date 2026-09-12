"""Pruebas del interprete de plantillas de campos (RF-12)."""

from datetime import date
from decimal import Decimal

import pytest

from app.core.entities.mapeo import PlantillaInvalida
from app.core.services.mapeo_campos import plantillas
from app.core.services.seleccion_cartera.campos import CAMPOS_CARTERA

DISPONIBLES = tuple(CAMPOS_CARTERA)

PRODUCTO = {
    "pagare": "000000000000000001",
    "telefono": "987654321",
    "documento_numero": "01234567",
    "titular": "APELLIDO/APELLIDO,NOMBRE",
    "saldo_capital_pendiente": Decimal("1500.50"),
    "fecha_vencimiento_cuota": date(2026, 9, 18),
    "monto_cuota": None,
}


def _compilar(plantilla: str):
    return plantillas.compilar(plantilla, DISPONIBLES)


def test_valor_fijo_no_usa_campos() -> None:
    compilada = _compilar("1010")

    assert compilada.es_valor_fijo
    assert compilada.campos == ()
    assert plantillas.aplicar(compilada, PRODUCTO) == "1010"


def test_referencia_simple_copia_el_campo() -> None:
    compilada = _compilar("[@telefono]")

    assert compilada.es_referencia_simple
    assert compilada.campos == ("telefono",)
    assert plantillas.aplicar(compilada, PRODUCTO) == "987654321"


def test_prefijo_mas_campo() -> None:
    compilada = _compilar("51[@telefono]")

    assert not compilada.es_referencia_simple
    assert plantillas.aplicar(compilada, PRODUCTO) == "51987654321"


def test_concatenacion_de_texto_y_varios_campos() -> None:
    compilada = _compilar("documento=[@documento_numero]; pagare=[@pagare]")

    assert compilada.campos == ("documento_numero", "pagare")
    assert plantillas.aplicar(compilada, PRODUCTO) == (
        "documento=01234567; pagare=000000000000000001"
    )


def test_un_campo_sin_valor_queda_vacio() -> None:
    compilada = _compilar("cuota:[@monto_cuota]")

    assert plantillas.aplicar(compilada, PRODUCTO) == "cuota:"
    assert plantillas.aplicar(compilada, PRODUCTO, vacio="0") == "cuota:0"


def test_los_valores_no_textuales_se_vuelven_texto() -> None:
    compilada = _compilar("[@saldo_capital_pendiente] al [@fecha_vencimiento_cuota]")

    assert plantillas.aplicar(compilada, PRODUCTO) == "1500.50 al 2026-09-18"


def test_valor_crudo_conserva_el_tipo_solo_en_referencia_simple() -> None:
    simple = _compilar("[@saldo_capital_pendiente]")
    compuesta = _compilar("S/ [@saldo_capital_pendiente]")

    assert plantillas.valor_crudo(simple, PRODUCTO) == Decimal("1500.50")
    assert plantillas.valor_crudo(compuesta, PRODUCTO) is None


@pytest.mark.parametrize(
    ("plantilla", "motivo"),
    [
        ("[@campo_inventado]", "campo que no existe"),
        ("[@]", "referencia vacia"),
        ("51[@telefono", "corchete sin cerrar"),
        ("[@telefono] y [@otro_inventado]", "segundo campo inexistente"),
    ],
)
def test_plantillas_invalidas(plantilla, motivo) -> None:
    with pytest.raises(PlantillaInvalida):
        _compilar(plantilla)


def test_una_plantilla_vacia_es_valida_y_produce_texto_vacio() -> None:
    compilada = _compilar("")

    assert plantillas.aplicar(compilada, PRODUCTO) == ""

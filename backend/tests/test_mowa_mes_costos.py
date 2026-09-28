"""Pruebas de la tarifa por SMS y del costo de las campanas (RF-MM-23, RF-MM-24).

Piezas puras. Lo que se cuida: todo es Decimal exacto (nunca float), el costo real
distingue "pendiente" y "sin tarifa" de cero, y el texto del contrato es plano y
con 4 decimales.
"""

from decimal import Decimal

import pytest

from app.core.entities.mowa_mes import TARIFA_SMS_POR_DEFECTO
from app.core.entities.mowa_mes_costo import EstadoCosto, TarifaInvalida
from app.core.services.plataformas.mowa_mes import costos


def test_la_tarifa_por_defecto_es_dos_centimos() -> None:
    assert TARIFA_SMS_POR_DEFECTO == Decimal("0.02")
    assert isinstance(TARIFA_SMS_POR_DEFECTO, Decimal)


@pytest.mark.parametrize(
    ("texto", "esperada"),
    [
        ("0", Decimal("0")),
        ("0.02", Decimal("0.02")),
        ("0.0001", Decimal("0.0001")),
        ("  1.5  ", Decimal("1.5")),
        ("12345678.9999", Decimal("12345678.9999")),
        ("3", Decimal("3")),
    ],
)
def test_una_tarifa_valida_se_lee_como_decimal_exacto(texto, esperada) -> None:
    tarifa = costos.tarifa_desde_texto(texto)

    assert tarifa == esperada
    assert isinstance(tarifa, Decimal)


@pytest.mark.parametrize(
    "texto",
    [
        "",
        " ",
        "-0.01",  # negativa
        "0.00001",  # 5 decimales
        "0.02000",  # 5 decimales aunque el ultimo sea cero: el limite es de texto
        "123456789",  # 9 enteros: no cabe en NUMERIC(12, 4)
        "1e2",  # exponente
        "0,02",  # coma decimal
        "NaN",
        "Infinity",
        "0.02 soles",
        ".5",
        "5.",
    ],
)
def test_una_tarifa_invalida_se_rechaza_con_el_motivo(texto) -> None:
    with pytest.raises(TarifaInvalida, match="hasta 4 decimales"):
        costos.tarifa_desde_texto(texto)


@pytest.mark.parametrize(
    "tarifa",
    [
        0.02,  # float: un monto nunca entra por float
        "0.02",
        None,
        Decimal("-1"),
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("0.00001"),
        Decimal("1E+8"),
    ],
)
def test_validar_tarifa_rechaza_lo_que_no_es_un_decimal_finito_no_negativo_de_4_decimales(
    tarifa,
) -> None:
    with pytest.raises(TarifaInvalida):
        costos.validar_tarifa(tarifa)


def test_validar_tarifa_acepta_los_bordes() -> None:
    assert costos.validar_tarifa(Decimal("0")) == 0
    assert costos.validar_tarifa(Decimal("0.0001")) == Decimal("0.0001")
    assert costos.validar_tarifa(Decimal("99999999.9999")) == Decimal("99999999.9999")


def test_el_costo_es_exacto_y_no_pasa_por_float() -> None:
    # Con float, 3 * 0.1 da 0.30000000000000004 y 46_000 * 0.02 no es exacto.
    assert costos.costo(3, Decimal("0.1")) == Decimal("0.3")
    assert costos.costo(45_851, Decimal("0.02")) == Decimal("917.02")
    assert costos.costo(0, Decimal("0.02")) == 0
    assert isinstance(costos.costo(10, Decimal("0.02")), Decimal)
    # Sin redondeo intermedio: 7 SMS a 0.0125 son 0.0875, no 0.09.
    assert costos.costo(7, Decimal("0.0125")) == Decimal("0.0875")


def test_el_costo_maximo_posible_es_exacto_y_cabe_en_la_columna() -> None:
    # 120 000 productos (CANTIDAD_MAXIMA) mas 100 supervisores, con la tarifa maxima: el
    # peor caso cabe en NUMERIC(18, 4), que admite 14 enteros.
    costo = costos.costo(120_100, Decimal("99999999.9999"))

    assert costo == Decimal("12009999999987.9900")
    assert len(str(int(costo))) <= 14


def test_costo_real_calculado_con_reporte() -> None:
    real = costos.costo_real(Decimal("0.02"), hay_reporte=True, enviados=1_000)

    assert real.estado is EstadoCosto.CALCULADO
    assert real.valor == Decimal("20.00")


def test_costo_real_con_reporte_y_cero_enviados_es_cero_calculado_no_pendiente() -> None:
    real = costos.costo_real(Decimal("0.02"), hay_reporte=True, enviados=0)

    assert real.estado is EstadoCosto.CALCULADO
    assert real.valor == 0


def test_costo_real_sin_reporte_esta_pendiente_y_no_es_cero() -> None:
    real = costos.costo_real(Decimal("0.02"), hay_reporte=False, enviados=0)

    assert real.estado is EstadoCosto.PENDIENTE
    assert real.valor is None


@pytest.mark.parametrize("hay_reporte", [True, False])
def test_costo_real_sin_tarifa_no_esta_disponible_con_o_sin_reporte(hay_reporte) -> None:
    real = costos.costo_real(None, hay_reporte=hay_reporte, enviados=500)

    assert real.estado is EstadoCosto.NO_DISPONIBLE
    assert real.valor is None


@pytest.mark.parametrize(
    ("valor", "texto"),
    [
        (Decimal("0.02"), "0.0200"),
        (Decimal("0.0200"), "0.0200"),
        (Decimal("917.02"), "917.0200"),
        (Decimal("0"), "0.0000"),
        (Decimal("0E-10"), "0.0000000000"),  # no se recorta precision que ya trae
        (Decimal("1E+2"), "100.0000"),  # sin exponente
        (Decimal("249999999997500.0000"), "249999999997500.0000"),
        (Decimal("0.0875"), "0.0875"),
    ],
)
def test_el_texto_decimal_es_plano_y_con_al_menos_4_decimales(valor, texto) -> None:
    assert costos.texto_decimal(valor) == texto

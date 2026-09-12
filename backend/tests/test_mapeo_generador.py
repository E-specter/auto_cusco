"""Pruebas de la generacion de filas de carga a partir de una definicion (RF-12)."""

from datetime import date
from decimal import Decimal

import pytest

from app.core.entities.mapeo import (
    CampoSalida,
    DefinicionCarga,
    FormatoFinanciero,
    PlantillaInvalida,
    TipoSalida,
)
from app.core.services.mapeo_campos.generador import GeneradorCargas
from app.core.services.seleccion_cartera.campos import CAMPOS_CARTERA

DISPONIBLES = tuple(CAMPOS_CARTERA)

PRODUCTOS = [
    {
        "pagare": "000000000000000001",
        "telefono": "987654321",
        "titular": "APELLIDO/APELLIDO,NOMBRE",
        "saldo_capital_pendiente": Decimal("1500.50"),
        "fecha_vencimiento_cuota": date(2026, 9, 18),
    },
    {
        "pagare": "000000000000000002",
        "telefono": None,  # producto sin telefono valido
        "titular": "OTRO/APELLIDO,NOMBRE",
        "saldo_capital_pendiente": Decimal("980"),
        "fecha_vencimiento_cuota": date(2026, 10, 1),
    },
]

DEFINICION = DefinicionCarga(
    nombre="SMS de prueba",
    campos=(
        CampoSalida(nombre="anexo_agente", plantilla="1010", tipo=TipoSalida.NUMERO),
        CampoSalida(nombre="numero", plantilla="51[@telefono]"),
        CampoSalida(nombre="cliente", plantilla="[@titular]"),
        CampoSalida(
            nombre="deuda",
            plantilla="[@saldo_capital_pendiente]",
            tipo=TipoSalida.FINANCIERO,
            formato_financiero=FormatoFinanciero(separador_miles=",", separador_decimal="."),
        ),
        CampoSalida(
            nombre="vence",
            plantilla="[@fecha_vencimiento_cuota]",
            tipo=TipoSalida.FECHA,
            formato_fecha="%d/%m/%Y",
        ),
        CampoSalida(
            nombre="mensaje", plantilla="Pagare [@pagare] vence el [@fecha_vencimiento_cuota]"
        ),
    ),
)


def _generador(definicion: DefinicionCarga = DEFINICION) -> GeneradorCargas:
    return GeneradorCargas(definicion, DISPONIBLES)


def test_genera_las_filas_con_sus_cabeceras() -> None:
    carga = _generador().generar(PRODUCTOS)

    assert carga.cabeceras == (
        "anexo_agente",
        "numero",
        "cliente",
        "deuda",
        "vence",
        "mensaje",
    )
    assert carga.completa
    assert carga.filas[0] == {
        "anexo_agente": 1010,
        "numero": "51987654321",
        "cliente": "APELLIDO/APELLIDO,NOMBRE",
        "deuda": "1,500.50",
        "vence": "18/09/2026",
        "mensaje": "Pagare 000000000000000001 vence el 2026-09-18",
    }


def test_un_campo_sin_dato_no_rompe_la_fila() -> None:
    carga = _generador().generar(PRODUCTOS)

    assert carga.filas[1]["numero"] == "51"  # el prefijo queda solo, sin telefono
    assert carga.filas[1]["deuda"] == "980.00"


def test_los_errores_se_juntan_y_la_generacion_continua() -> None:
    definicion = DefinicionCarga(
        nombre="con error",
        campos=(
            CampoSalida(nombre="pagare", plantilla="[@pagare]"),
            CampoSalida(nombre="numerico", plantilla="[@titular]", tipo=TipoSalida.NUMERO),
        ),
    )

    carga = GeneradorCargas(definicion, DISPONIBLES).generar(PRODUCTOS)

    assert not carga.completa
    assert [(e.fila, e.campo) for e in carga.errores] == [(1, "numerico"), (2, "numerico")]
    assert [f["pagare"] for f in carga.filas] == [
        "000000000000000001",
        "000000000000000002",
    ]
    assert carga.filas[0]["numerico"] is None


def test_los_campos_de_origen_se_listan_sin_repetir() -> None:
    assert _generador().campos_de_origen() == (
        "telefono",
        "titular",
        "saldo_capital_pendiente",
        "fecha_vencimiento_cuota",
        "pagare",
    )


@pytest.mark.parametrize(
    ("definicion", "motivo"),
    [
        (DefinicionCarga(nombre="vacia", campos=()), "sin campos"),
        (
            DefinicionCarga(
                nombre="repetida",
                campos=(
                    CampoSalida(nombre="numero", plantilla="[@telefono]"),
                    CampoSalida(nombre="numero", plantilla="[@pagare]"),
                ),
            ),
            "nombre repetido",
        ),
        (
            DefinicionCarga(nombre="sin nombre", campos=(CampoSalida(nombre=" ", plantilla="1"),)),
            "nombre vacio",
        ),
        (
            DefinicionCarga(
                nombre="campo inexistente",
                campos=(CampoSalida(nombre="x", plantilla="[@no_existe]"),),
            ),
            "campo de origen inexistente",
        ),
    ],
)
def test_definiciones_invalidas_se_rechazan_al_compilar(definicion, motivo) -> None:
    with pytest.raises(PlantillaInvalida):
        GeneradorCargas(definicion, DISPONIBLES)


def test_una_definicion_se_compila_una_vez_y_sirve_para_muchos_productos() -> None:
    generador = _generador()

    primera = generador.generar(PRODUCTOS)
    segunda = generador.generar(PRODUCTOS[:1])

    assert len(primera.filas) == 2
    assert len(segunda.filas) == 1
    assert primera.filas[0] == segunda.filas[0]

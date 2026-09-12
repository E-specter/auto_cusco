"""Pruebas del catalogo de campos consultables y de la validacion de consultas."""

from datetime import date
from decimal import Decimal

import pytest

from app.adapters.persistence.modelos import CargaFila
from app.core.entities.cartera import (
    ConsultaInvalida,
    Filtro,
    Funcion,
    Indicador,
    Operador,
    Orden,
    TipoDato,
)
from app.core.services.seleccion_cartera import campos

COLUMNAS_TECNICAS = {"carga_id", "numero_fila", "extras"}


def test_los_campos_consultables_son_las_columnas_de_la_cartera() -> None:
    columnas = {c.name for c in CargaFila.__table__.columns} - COLUMNAS_TECNICAS

    assert set(campos.CAMPOS_CARTERA) == columnas


@pytest.mark.parametrize(
    ("campo", "tipo"),
    [
        ("pagare", TipoDato.TEXTO),
        ("documento_numero", TipoDato.TEXTO),
        ("telefono", TipoDato.TEXTO),
        ("saldo_capital_pendiente", TipoDato.NUMERO),
        ("dias_atraso", TipoDato.NUMERO),
        ("fecha_vencimiento_cuota", TipoDato.FECHA),
        ("vencimiento_operativo_fecha", TipoDato.FECHA),
        ("vencimiento_operativo_aplica", TipoDato.BOOLEANO),
        ("cliente_fallecido", TipoDato.BOOLEANO),
    ],
)
def test_tipo_de_cada_campo(campo, tipo) -> None:
    assert campos.tipo_de(campo) is tipo


def test_la_columna_duplicada_del_pagare_no_es_consultable() -> None:
    with pytest.raises(ConsultaInvalida):
        campos.tipo_de("pagare_duplicado")


@pytest.mark.parametrize(
    ("campo", "texto", "esperado"),
    [
        ("saldo_capital_pendiente", "1500.50", Decimal("1500.50")),
        ("dias_atraso", "-8", Decimal("-8")),
        ("fecha_vencimiento_cuota", "2026-09-18", date(2026, 9, 18)),
        ("cliente_fallecido", "si", True),
        ("cliente_fallecido", "FALSE", False),
        ("region", "  CUSCO SUR  ", "CUSCO SUR"),
    ],
)
def test_convertir_valores_de_texto(campo, texto, esperado) -> None:
    assert campos.convertir(campo, texto) == esperado


@pytest.mark.parametrize(
    ("campo", "texto"),
    [
        ("saldo_capital_pendiente", "mucho"),
        ("fecha_vencimiento_cuota", "18/09/2026"),
        ("cliente_fallecido", "quizas"),
        ("campo_que_no_existe", "1"),
    ],
)
def test_convertir_valores_invalidos(campo, texto) -> None:
    with pytest.raises(ConsultaInvalida):
        campos.convertir(campo, texto)


def test_filtro_valido() -> None:
    campos.validar_filtro(Filtro("dias_atraso", Operador.ENTRE, (Decimal(0), Decimal(30))))
    campos.validar_filtro(Filtro("telefono", Operador.NO_VACIO))
    campos.validar_filtro(Filtro("region", Operador.EN, ("CUSCO SUR", "TACNA")))


@pytest.mark.parametrize(
    ("filtro", "motivo"),
    [
        (Filtro("region", Operador.MAYOR, ("A",)), "operador que no aplica a texto"),
        (Filtro("saldo_capital_pendiente", Operador.CONTIENE, (Decimal(1),)), "contiene en numero"),
        (Filtro("cliente_fallecido", Operador.ENTRE, (True, False)), "entre en booleano"),
        (Filtro("dias_atraso", Operador.ENTRE, (Decimal(1),)), "entre necesita dos valores"),
        (Filtro("dias_atraso", Operador.IGUAL, ()), "igual necesita un valor"),
        (Filtro("region", Operador.EN, ()), "en necesita al menos un valor"),
        (Filtro("dias_atraso", Operador.IGUAL, ("3",)), "valor sin convertir"),
        (Filtro("no_existe", Operador.IGUAL, ("x",)), "campo inexistente"),
    ],
)
def test_filtros_invalidos(filtro, motivo) -> None:
    with pytest.raises(ConsultaInvalida):
        campos.validar_filtro(filtro)


def test_orden_solo_sobre_campos_existentes() -> None:
    campos.validar_orden(Orden("saldo_capital_pendiente", descendente=True))

    with pytest.raises(ConsultaInvalida):
        campos.validar_orden(Orden("inventado"))


def test_indicadores_validos() -> None:
    campos.validar_indicador(Indicador("cuentas", Funcion.CONTEO))
    campos.validar_indicador(Indicador("capital", Funcion.SUMA, "saldo_capital_pendiente"))
    campos.validar_indicador(
        Indicador("ultimo vencimiento", Funcion.MAXIMO, "fecha_vencimiento_cuota")
    )


@pytest.mark.parametrize(
    "indicador",
    [
        Indicador("", Funcion.CONTEO),
        Indicador("capital", Funcion.SUMA),
        Indicador("region promedio", Funcion.PROMEDIO, "region"),
        Indicador("x", Funcion.SUMA, "campo_inventado"),
    ],
)
def test_indicadores_invalidos(indicador) -> None:
    with pytest.raises(ConsultaInvalida):
        campos.validar_indicador(indicador)


def test_catalogo_publico_trae_tipo_y_operadores() -> None:
    catalogo = campos.catalogo_publico()

    assert catalogo["region"]["tipo"] == "texto"
    assert "contiene" in catalogo["region"]["operadores"]
    assert "entre" in catalogo["dias_atraso"]["operadores"]
    assert "contiene" not in catalogo["dias_atraso"]["operadores"]

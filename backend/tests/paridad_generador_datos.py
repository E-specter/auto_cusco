"""Matriz de la prueba de paridad de `GeneradorCargas` (B2, RF-54).

Definiciones x productos sinteticos, con todos los tipos de columna (texto, numero, fecha,
financiero), valores vacios, valores que no se pueden convertir y plantillas validas. La recorre
`test_generador_paridad.py` y se uso para congelar el SHA-256 en HEAD b8b9025, antes de tocar el
generador: la `CargaGenerada` ENTERA (cabeceras, filas con el tipo de cada celda y los errores con
su fila, campo y texto) tiene que salir igual.

Solo datos y dos funciones de serializacion. Nada es real.
"""

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.core.entities.mapeo import (
    CampoSalida,
    DefinicionCarga,
    FormatoFinanciero,
    TipoSalida,
)
from app.core.services.mapeo_campos.generador import CargaGenerada

T, N, F, FIN = TipoSalida.TEXTO, TipoSalida.NUMERO, TipoSalida.FECHA, TipoSalida.FINANCIERO


def _def(nombre: str, *campos: CampoSalida) -> DefinicionCarga:
    return DefinicionCarga(nombre=nombre, campos=campos)


DEFINICIONES: dict[str, DefinicionCarga] = {
    # Las de test_mapeo_generador.py, test_generacion_cargas.py y test_api_archivos_carga.py.
    "sms_de_prueba": _def(
        "SMS de prueba",
        CampoSalida("anexo_agente", "1010", N),
        CampoSalida("numero", "51[@telefono]"),
        CampoSalida("cliente", "[@titular]"),
        CampoSalida(
            "deuda",
            "[@saldo_capital_pendiente]",
            FIN,
            formato_financiero=FormatoFinanciero(separador_miles=",", separador_decimal="."),
        ),
        CampoSalida("vence", "[@fecha_vencimiento_cuota]", F, formato_fecha="%d/%m/%Y"),
        CampoSalida("mensaje", "Pagare [@pagare] vence el [@fecha_vencimiento_cuota]"),
    ),
    "api_archivos_carga": _def(
        "SMS preventiva",
        CampoSalida("anexo", "1010", N),
        CampoSalida("numero", "51[@telefono]"),
        CampoSalida(
            "deuda",
            "[@saldo_capital_pendiente]",
            FIN,
            formato_financiero=FormatoFinanciero(separador_miles=".", separador_decimal=","),
        ),
        CampoSalida("vence", "[@fecha_vencimiento_cuota]", F, formato_fecha="%d/%m/%Y"),
    ),
    "con_errores_de_tipo": _def(
        "Con errores",
        CampoSalida("pagare", "[@pagare]"),
        CampoSalida("roto", "x[@telefono]", N),
        CampoSalida("titular_numero", "[@titular]", N),
        CampoSalida("telefono_fecha", "[@telefono]", F),
        CampoSalida("titular_financiero", "[@titular]", FIN),
        CampoSalida("saldo_texto", "[@saldo_capital_pendiente]"),
    ),
    # Tipos y formatos.
    "numeros": _def(
        "Numeros",
        CampoSalida("crudo", "[@saldo_capital_pendiente]", N),
        CampoSalida("fijo_entero", "7", N),
        CampoSalida("fijo_decimal", "7.50", N),
        CampoSalida("fijo_vacio", "", N),
        CampoSalida("del_texto", "[@telefono]", N),
        CampoSalida("compuesto", "1[@telefono]", N),
    ),
    "fechas": _def(
        "Fechas",
        CampoSalida("nativa", "[@fecha_vencimiento_cuota]", F),
        CampoSalida("con_formato", "[@fecha_vencimiento_cuota]", F, formato_fecha="%Y-%m-%d"),
        CampoSalida("largo", "[@fecha_vencimiento_cuota]", F, formato_fecha="%d.%m.%y"),
        CampoSalida("fija", "2026-09-18", F, formato_fecha="%d/%m/%Y"),
        CampoSalida("fija_mala", "no es fecha", F),
        CampoSalida("fija_vacia", "", F),
        CampoSalida("del_pagare", "[@pagare]", F),
    ),
    "financieros": _def(
        "Financieros",
        CampoSalida("ingles", "[@saldo_capital_pendiente]", FIN),
        CampoSalida(
            "europeo",
            "[@saldo_capital_pendiente]",
            FIN,
            formato_financiero=FormatoFinanciero(".", ",", 2),
        ),
        CampoSalida(
            "sin_decimales",
            "[@saldo_capital_pendiente]",
            FIN,
            formato_financiero=FormatoFinanciero(" ", ",", 0),
        ),
        CampoSalida(
            "tres_decimales",
            "[@saldo_capital_pendiente]",
            FIN,
            formato_financiero=FormatoFinanciero("'", ".", 3),
        ),
        CampoSalida("fijo", "1234.5", FIN),
        CampoSalida("fijo_mal", "abc", FIN),
    ),
    "textos": _def(
        "Textos",
        CampoSalida("vacio", ""),
        CampoSalida("fijo", "texto fijo"),
        CampoSalida("fijo_con_tildes", "Señor ñandú ÁÉÍ"),
        CampoSalida("varios", "[@titular]-[@telefono]-[@pagare]"),
        CampoSalida("espacios", "[ @titular ] y [@ telefono ]"),
        CampoSalida("bool", "[@activo]"),
        CampoSalida("barra", "C:\\[@telefono]"),
        CampoSalida("corchetes", "[[@titular]] ]"),
        CampoSalida("saltos", "a\n[@titular]\tb"),
    ),
}

CAMPOS_DISPONIBLES = (
    "pagare",
    "telefono",
    "titular",
    "saldo_capital_pendiente",
    "fecha_vencimiento_cuota",
    "activo",
)

PRODUCTOS: tuple[dict[str, Any], ...] = (
    {
        "pagare": "000000000000000001",
        "telefono": "987654321",
        "titular": "APELLIDO/APELLIDO,NOMBRE",
        "saldo_capital_pendiente": Decimal("1500.50"),
        "fecha_vencimiento_cuota": date(2026, 9, 18),
        "activo": True,
    },
    {
        "pagare": "000000000000000002",
        "telefono": None,
        "titular": "OTRO/APELLIDO,NOMBRE",
        "saldo_capital_pendiente": Decimal("980"),
        "fecha_vencimiento_cuota": date(2026, 10, 1),
        "activo": False,
    },
    {
        "pagare": "2026-09-18",
        "telefono": "9",
        "titular": "  ",
        "saldo_capital_pendiente": Decimal("-1234567.891"),
        "fecha_vencimiento_cuota": datetime(2026, 9, 18, 10, 30),
        "activo": None,
    },
    {
        "pagare": "",
        "telefono": 987654321,
        "titular": "Ñandú Pérez",
        "saldo_capital_pendiente": 7,
        "fecha_vencimiento_cuota": "2026-09-18",
        "activo": 1,
    },
    {
        "pagare": None,
        "telefono": "abc",
        "titular": None,
        "saldo_capital_pendiente": "12.50",
        "fecha_vencimiento_cuota": "no es fecha",
        "activo": "si",
    },
    {
        "pagare": "000000000000000006",
        "telefono": "12",
        "titular": "12.5",
        "saldo_capital_pendiente": None,
        "fecha_vencimiento_cuota": None,
        "activo": True,
    },
    {
        "pagare": "000000000000000007",
        "telefono": " 987654321 ",
        "titular": "42",
        "saldo_capital_pendiente": Decimal("0"),
        "fecha_vencimiento_cuota": date(2027, 1, 31),
        "activo": False,
    },
    {},
)


def _celda(valor: Any) -> list[str]:
    return [type(valor).__name__, repr(valor)]


def serializar(nombre: str, carga: CargaGenerada) -> dict[str, Any]:
    """La `CargaGenerada` entera, con el tipo de cada celda, en una forma determinista."""
    return {
        "definicion": nombre,
        "cabeceras": list(carga.cabeceras),
        "filas": [{k: _celda(v) for k, v in fila.items()} for fila in carga.filas],
        "errores": [[e.fila, e.campo, e.detalle] for e in carga.errores],
    }


def huella_de_la_matriz(cargas: dict[str, CargaGenerada]) -> str:
    """SHA-256 de todas las cargas serializadas, en el orden de las definiciones."""
    datos = [serializar(nombre, carga) for nombre, carga in cargas.items()]
    texto = json.dumps(datos, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()

"""Pruebas de la normalizacion de filas (reglas N-2 a N-8). Solo datos sinteticos."""

from datetime import date
from decimal import Decimal

from app.core.entities.sabana import Severidad, TipoDocumento
from app.core.services.ingesta_sabana.cabeceras import mapear_cabeceras
from app.core.services.ingesta_sabana.normalizador import normalizar_fila
from tests.test_sabana_cabeceras import CABECERAS_10_09


def _fila_sintetica(**cambios) -> list:
    """Fila con la forma de los tipos que entrega el lector de .xlsb (floats, str, bool)."""
    base = {
        "Región": "REGION PRUEBA",
        "Agencia": "AGENCIA PRUEBA",
        "Analista": "PEREZ/PRUEBA,ANALISTA",
        "Titular": "APELLIDO/APELLIDO,NOMBRE FICTICIO",
        "DniRuc": 1234567.0,
        "Teléfono": 987654321.0,
        "Pagare": "000000000000000001",
        "SaldoSoles 03/09": 1500.5,
        "TIPO DE REPROGRAMACIÓN": "NULL",
        "Vencimientos Operativo": 46282.0,
        "Dias Atraso Hoy": -3.0,
        "Analista Actual": "PEREZ/PRUEBA,ANALISTA",
        "Saldo Capital Pendiente": 1500.5,
        "Monto Cuota": 210.35,
        "Estado del Crédito": "VIGENTE NORMAL",
        "Vencimiento Cuota": 46278.0,
        "Cliente Fallecido": "no",
        "DÍAS SICMAC-C": -3.0,
        "Cuotas Apro": 12.0,
        "Cuotas pagadas": 4.0,
        "Cuotas Pendientes": 8.0,
        "TipoBasilea": "CREDITO MICRO EMPRESA",
        "TipoProducto": "PERSONAL  DIRECTO",
        "PAGARE": "000000000000000001",
        "VALIDADOR": True,
        "Segmento Saldo": "1. Menos de 20 mil",
        "Moneda": "Soles",
        " Días Cierre Mes Anterior": 1520.0,
        "Saldo CIERRE actual": 1500.5,
        "Cod.Tipo Basilea": None,
        "BPO  ": "IMPULSE",
        "TAG ": "CARTERA SCORE SETIEMBRE -CUENTAS NUEVAS ",
        "MES DE GESTIÓN ": "GESTION SETIEMBRE ",
        "SEGMENTO ACTUAL ": "1. Preventiva",
        "SEGMENTO FINACIERO": "1. Preventiva",
        "validacion descuento planilla": "NO",
        "Segmento": "Menor a 0",
        "Tramo Actual": "0. Mora Preventiva",
        "Provisión Actual": "1. Provisión Normal",
        "Mora Impacto Actual": "NO",
        "Tramo Proyectado": "2. Mora Tramo 9 a 15",
        "Provisión Proyectada": "2. Provisión CPP",
        "Mora Impacto Proyectada": "SI",
        "Cant.Paralelos": 1.0,
        "Celular Analista": 912345678.0,
    }
    base.update(cambios)
    return [base[c] for c in CABECERAS_10_09]


MAPEO = mapear_cabeceras(CABECERAS_10_09)


def test_fila_valida_se_normaliza_con_tipos_de_dominio() -> None:
    fila = normalizar_fila(_fila_sintetica(), MAPEO, numero_fila=2)
    v = fila.valores

    assert fila.ingestable and fila.clave == "000000000000000001"
    assert v["documento_tipo"] is TipoDocumento.DNI
    assert v["documento_numero"] == "01234567"
    assert v["telefono"] == "987654321"
    assert v["saldo_capital_pendiente"] == Decimal("1500.50")
    assert v["tipo_reprogramacion"] is None
    assert v["vencimiento_operativo_aplica"] is True
    assert v["vencimiento_operativo_fecha"] == date(2026, 9, 17)
    assert v["fecha_vencimiento_cuota"] == date(2026, 9, 13)
    assert v["dias_atraso"] == -3
    assert v["cliente_fallecido"] is False
    assert v["mora_impacto_proyectada"] is True
    assert v["tipo_producto"] == "PERSONAL DIRECTO"
    assert v["cartera_tag"] == "CARTERA SCORE SETIEMBRE -CUENTAS NUEVAS"
    assert v["mes_gestion"] == "GESTION SETIEMBRE"
    assert "validador" not in v and "cod_tipo_basilea" not in v
    assert "pagare_duplicado" not in v  # se verifica y se descarta
    assert [(i.codigo, i.severidad) for i in fila.incidencias] == [
        ("dni_completado_con_ceros", Severidad.INFO)
    ]


def test_incidencias_ubican_fila_columna_y_valor() -> None:
    fila = normalizar_fila(_fila_sintetica(**{"Teléfono": 98765432.0}), MAPEO, numero_fila=7)

    incidencia = next(i for i in fila.incidencias if i.codigo == "telefono_invalido")
    assert (incidencia.fila, incidencia.columna) == (7, "telefono")
    assert incidencia.valor_original == 98765432.0
    assert fila.valores["telefono"] is None
    assert fila.ingestable


def test_pagare_vacio_o_numerico_hace_la_fila_no_ingestable() -> None:
    vacio = normalizar_fila(_fila_sintetica(Pagare=None), MAPEO, numero_fila=3)
    numerico = normalizar_fila(_fila_sintetica(Pagare=1.0e17), MAPEO, numero_fila=4)

    assert not vacio.ingestable
    assert not numerico.ingestable
    assert {i.codigo for i in numerico.incidencias} >= {"clave_no_texto"}


def test_chequeos_de_consistencia() -> None:
    fila = normalizar_fila(
        _fila_sintetica(
            **{"Cuotas pagadas": 5.0, "DÍAS SICMAC-C": -2.0, "PAGARE": "000000000000000002"}
        ),
        MAPEO,
        numero_fila=5,
    )

    codigos = {(i.codigo, i.severidad) for i in fila.incidencias}
    assert ("cuotas_inconsistentes", Severidad.ADVERTENCIA) in codigos
    assert ("dias_atraso_difiere_entidad", Severidad.INFO) in codigos
    assert ("pagare_duplicado_distinto", Severidad.ADVERTENCIA) in codigos
    assert fila.ingestable


def test_tipos_de_python_calamine_dan_el_mismo_resultado_que_pyxlsb() -> None:
    """python-calamine entrega date nativo, int y "" donde pyxlsb entrega float y None."""
    estilo_pyxlsb = _fila_sintetica(**{"Cod.Tipo Basilea": None})
    estilo_calamine = _fila_sintetica(
        **{
            "Vencimiento Cuota": date(2026, 9, 13),
            "Vencimientos Operativo": date(2026, 9, 17),
            "DniRuc": 1234567,
            "Teléfono": 987654321,
            " Días Cierre Mes Anterior": 1520,
            "Cod.Tipo Basilea": "",
            "TIPO DE REPROGRAMACIÓN": "",
        }
    )

    a = normalizar_fila(estilo_pyxlsb, MAPEO, numero_fila=2)
    b = normalizar_fila(estilo_calamine, MAPEO, numero_fila=2)

    assert a.valores == b.valores
    assert [i.codigo for i in a.incidencias] == [i.codigo for i in b.incidencias]


def test_fila_mas_corta_que_la_cabecera_no_falla() -> None:
    celdas = _fila_sintetica()[:10]

    fila = normalizar_fila(celdas, MAPEO, numero_fila=9)

    assert fila.clave == "000000000000000001"
    assert fila.valores["monto_cuota"] is None

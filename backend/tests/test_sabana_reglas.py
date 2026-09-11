"""Pruebas de las reglas de normalizacion por valor (docs/sabana-schema.md, seccion 6).

Solo datos sinteticos. El RUC 20131312955 es el RUC publico de SUNAT.
"""

from datetime import date, datetime
from decimal import Decimal

import pytest

from app.core.entities.sabana import Severidad, TipoDocumento
from app.core.services.ingesta_sabana import reglas

# ---------- N-3: documentos ----------


@pytest.mark.parametrize(
    ("valor", "tipo", "numero", "codigo_aviso"),
    [
        (12345678.0, TipoDocumento.DNI, "12345678", None),
        ("12345678", TipoDocumento.DNI, "12345678", None),
        (1234567.0, TipoDocumento.DNI, "01234567", "dni_completado_con_ceros"),
        (123456.0, TipoDocumento.DNI, "00123456", "dni_completado_con_ceros"),
        (12345, TipoDocumento.DNI, "00012345", "dni_completado_con_ceros"),
        ("1234567.0", TipoDocumento.DNI, "01234567", "dni_completado_con_ceros"),
        (" 00123456 ", TipoDocumento.DNI, "00123456", None),
        (20131312955.0, TipoDocumento.RUC, "20131312955", None),
        ("10100000003", TipoDocumento.RUC, "10100000003", None),
        ("123456789", TipoDocumento.EXTRANJERO, "123456789", None),
        ("CE00012345", TipoDocumento.EXTRANJERO, "CE00012345", None),
        (123456789012.0, TipoDocumento.EXTRANJERO, "123456789012", None),
    ],
)
def test_documento_valido(valor, tipo, numero, codigo_aviso) -> None:
    resultado = reglas.normalizar_documento(valor)

    assert resultado.valor is not None
    assert resultado.valor.tipo is tipo
    assert resultado.valor.numero == numero
    assert (resultado.aviso.codigo if resultado.aviso else None) == codigo_aviso


def test_dni_completado_es_informativo() -> None:
    assert reglas.normalizar_documento(1234567.0).aviso.severidad is Severidad.INFO


@pytest.mark.parametrize(
    ("valor", "codigo"),
    [
        (None, "documento_vacio"),
        ("   ", "documento_vacio"),
        ("NULL", "documento_vacio"),
        (0.0, "documento_solo_ceros"),
        ("0000", "documento_solo_ceros"),
        (1234.5, "documento_formato_invalido"),
        (-12345678.0, "documento_formato_invalido"),
        (True, "documento_formato_invalido"),
        ("20131312954", "ruc_invalido"),  # digito verificador incorrecto
        ("30131312955", "ruc_invalido"),  # prefijo inexistente
    ],
)
def test_documento_invalido(valor, codigo) -> None:
    resultado = reglas.normalizar_documento(valor)

    assert resultado.valor is None
    assert resultado.aviso.codigo == codigo
    assert resultado.aviso.severidad is Severidad.ERROR


@pytest.mark.parametrize(
    "ruc",
    [
        "20131312955",  # verificador normal
        "10100000020",  # 11 - (suma mod 11) == 10 -> 0
        "10100000071",  # 11 - (suma mod 11) == 11 -> 1
        "20100000050",
        "20100000131",
    ],
)
def test_ruc_digito_verificador_casos_borde(ruc) -> None:
    assert reglas.es_ruc_valido(ruc)


@pytest.mark.parametrize("prefijo", ["10", "15", "16", "17", "20"])
def test_ruc_prefijos_validos_se_aceptan(prefijo) -> None:
    base = prefijo + "12345678"
    for verificador in "0123456789":
        if reglas.es_ruc_valido(base + verificador):
            return
    pytest.fail(f"Ningun verificador valido para el prefijo {prefijo}")


# ---------- N-4: telefonos ----------


@pytest.mark.parametrize("valor", [987654321.0, "987654321", 987654321, " 912345678 "])
def test_telefono_valido(valor) -> None:
    resultado = reglas.normalizar_telefono(valor)

    assert resultado.valor == str(valor).strip().removesuffix(".0")
    assert resultado.aviso is None


@pytest.mark.parametrize(
    ("valor", "codigo"),
    [
        (None, "telefono_vacio"),
        ("", "telefono_vacio"),
        (9876543210.0, "telefono_invalido"),  # 10 digitos
        (887654321.0, "telefono_invalido"),  # no empieza con 9
        (654321.0, "telefono_invalido"),
        ("98765 4321", "telefono_invalido"),  # no se corrige automaticamente
        (98765432.1, "telefono_invalido"),
    ],
)
def test_telefono_invalido_se_reporta_sin_corregir(valor, codigo) -> None:
    resultado = reglas.normalizar_telefono(valor)

    assert resultado.valor is None
    assert resultado.aviso.codigo == codigo
    assert resultado.aviso.severidad is Severidad.ADVERTENCIA


# ---------- N-5: fechas ----------


@pytest.mark.parametrize(
    ("valor", "esperada"),
    [
        (46275.0, date(2026, 9, 10)),
        (46204, date(2026, 7, 1)),
        (46283.75, date(2026, 9, 18)),  # la parte horaria se descarta
        ("46290", date(2026, 9, 25)),
        ("10/09/2026", date(2026, 9, 10)),
        (datetime(2026, 9, 10, 8, 30), date(2026, 9, 10)),
        (date(2026, 9, 10), date(2026, 9, 10)),
    ],
)
def test_fecha_valida(valor, esperada) -> None:
    assert reglas.normalizar_fecha(valor).valor == esperada


@pytest.mark.parametrize("valor", [30.0, 3_000_000.0, "31/02/2026", "ayer", True, float("nan")])
def test_fecha_invalida(valor) -> None:
    resultado = reglas.normalizar_fecha(valor)

    assert resultado.valor is None
    assert resultado.aviso.codigo == "fecha_invalida"


def test_fecha_vacia_no_genera_aviso() -> None:
    assert reglas.normalizar_fecha(None) == reglas.Resultado(None)


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [("NO", (False, None)), ("no ", (False, None)), (46282.0, (True, date(2026, 9, 17)))],
)
def test_vencimiento_operativo(valor, esperado) -> None:
    assert reglas.normalizar_vencimiento_operativo(valor).valor == esperado


@pytest.mark.parametrize(
    ("valor", "codigo"),
    [(None, "vencimiento_operativo_vacio"), ("SI", "vencimiento_operativo_invalido")],
)
def test_vencimiento_operativo_invalido(valor, codigo) -> None:
    assert reglas.normalizar_vencimiento_operativo(valor).aviso.codigo == codigo


# ---------- N-6: booleanos ----------


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("si", True),
        ("SI", True),
        ("Sí", True),
        ("no", False),
        ("NO", False),
        (True, True),
        (0, False),
    ],
)
def test_booleano(valor, esperado) -> None:
    assert reglas.normalizar_booleano(valor).valor is esperado


def test_booleano_invalido() -> None:
    assert reglas.normalizar_booleano("tal vez").aviso.codigo == "booleano_invalido"


# ---------- numeros ----------


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (2521280.36, Decimal("2521280.36")),
        (50.745, Decimal("50.75")),
        (0.0, Decimal("0.00")),
        (1500, Decimal("1500.00")),
        ("96216.15", Decimal("96216.15")),
    ],
)
def test_financiero(valor, esperado) -> None:
    assert reglas.normalizar_financiero(valor).valor == esperado


@pytest.mark.parametrize("valor", ["1,500.00", "S/ 10", True, float("inf")])
def test_financiero_invalido(valor) -> None:
    assert reglas.normalizar_financiero(valor).aviso.codigo == "monto_invalido"


@pytest.mark.parametrize(("valor", "esperado"), [(-8.0, -8), (71.0, 71), ("12", 12), (3, 3)])
def test_entero(valor, esperado) -> None:
    assert reglas.normalizar_entero(valor).valor == esperado


@pytest.mark.parametrize("valor", [1.5, "doce", False])
def test_entero_invalido(valor) -> None:
    assert reglas.normalizar_entero(valor).aviso.codigo == "entero_invalido"


# ---------- N-2: texto y cabeceras ----------


def test_texto_literal_null_es_nulo() -> None:
    assert reglas.normalizar_texto("NULL").valor is None


def test_texto_recorta_y_colapsa_en_catalogos() -> None:
    assert reglas.normalizar_texto("  GESTION SETIEMBRE ").valor == "GESTION SETIEMBRE"
    assert reglas.normalizar_texto("PERSONAL  DIRECTO", colapsar_espacios=True).valor == (
        "PERSONAL DIRECTO"
    )


@pytest.mark.parametrize(
    ("cabecera", "esperada"),
    [
        ("Región", "region"),
        (" Días Cierre Mes Anterior", "dias cierre mes anterior"),
        ("MES DE GESTIÓN ", "mes de gestion"),
        ("BPO  ", "bpo"),
        ("DÍAS SICMAC-C", "dias sicmac-c"),
    ],
)
def test_normalizar_cabecera(cabecera, esperada) -> None:
    assert reglas.normalizar_cabecera(cabecera) == esperada

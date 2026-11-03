"""Lector del «Informe» de WhatsMKT sobre una tabla ya leida (T-WM-B6a; RF-WM-37, DU-WM-7).

Los informes se arman como tablas en la propia prueba, con la forma observada el 30.10: nunca se
abre un archivo. Numeros sinteticos 51900000xxx.
"""

from datetime import date, datetime
from pathlib import Path

import pytest

from app.core.entities.lectura_tabla import FormatoTabla, TablaLeida
from app.core.entities.sabana import FilaCruda
from app.core.entities.whatsmkt import CodigoWhatsmkt, ErrorWhatsmkt
from app.core.services.plataformas.whatsmkt import conciliacion, informe
from app.core.services.plataformas.whatsmkt.informe import leer_informe, solo_digitos

CAMPANA = "CUZCO_Vencida (sintetica) whatsapp 2026.10.30"
TIPO = "CAMPAÑA DE IMAGEN + TEXTO"


def tabla(filas: list[list]) -> TablaLeida:
    """Lo que entrega el lector comun: la primera fila con datos es la cabecera y una fila sin
    ningun valor no se incluye (los numeros de fila siguen siendo los de la hoja)."""
    con_datos = [(i, f) for i, f in enumerate(filas, 1) if any(c not in (None, "") for c in f)]
    (primera, cabeceras), resto = con_datos[0], con_datos[1:]
    return TablaLeida(
        formato=FormatoTabla.XLSX,
        hojas=("Informe",),
        hoja="Informe",
        separador=None,
        codificacion=None,
        fila_cabecera=primera,
        cabeceras=cabeceras,
        filas=[FilaCruda(i, f) for i, f in resto],
    )


def detalle(*numeros, campana=CAMPANA, tipo=TIPO) -> list[list]:
    return [[campana, tipo, n] for n in numeros]


def observado(numeros=("51900000001", "51900000002", "51900000003"), **cambios) -> list[list]:
    """La estructura observada, con filas vacias entre la fecha, los encabezados y el detalle."""
    base = {
        "fecha": ["FECHA", "30-10-2026"],
        "total": ["TOTAL DE ENVIO", len(numeros)],
        "encabezados": ["CAMPAÑA", "TIPO DE ENVIO", "NUMERO"],
    }
    base.update(cambios)
    return [base["fecha"], base["total"], [], base["encabezados"], [], *detalle(*numeros)]


def error_de(filas) -> CodigoWhatsmkt:
    with pytest.raises(ErrorWhatsmkt) as error:
        leer_informe(tabla(filas))
    return error.value.codigo


# --- La estructura observada ------------------------------------------------------------------


def test_el_informe_observado_se_lee_completo() -> None:
    resultado = leer_informe(tabla(observado()))

    assert resultado.fecha_informada == date(2026, 10, 30)
    assert resultado.total_informado == 3
    assert resultado.campana == CAMPANA
    assert resultado.tipo_envio == TIPO
    assert resultado.numeros == ("51900000001", "51900000002", "51900000003")
    assert resultado.coincide_total is True


def test_las_filas_se_buscan_por_su_contenido_y_no_por_su_numero() -> None:
    desplazado = [
        [],
        [],
        ["TOTAL DE ENVIO", 2],
        [],
        ["FECHA", "05-11-2026"],
        [],
        [],
        ["CAMPAÑA", "TIPO DE ENVIO", "NUMERO"],
        [],
        [],
        *detalle("51900000001", "51900000002"),
    ]

    resultado = leer_informe(tabla(desplazado))

    assert resultado.fecha_informada == date(2026, 11, 5)
    assert resultado.total_informado == 2
    assert resultado.numeros == ("51900000001", "51900000002")


def test_las_columnas_se_buscan_por_su_encabezado() -> None:
    filas = [
        ["FECHA", "30-10-2026"],
        ["TOTAL DE ENVIO", 1],
        ["NUMERO", "CAMPAÑA", "TIPO DE ENVIO"],
        ["51900000001", CAMPANA, TIPO],
    ]

    resultado = leer_informe(tabla(filas))

    assert (resultado.numeros, resultado.campana, resultado.tipo_envio) == (
        ("51900000001",),
        CAMPANA,
        TIPO,
    )


def test_las_filas_vacias_del_detalle_se_ignoran() -> None:
    filas = observado(numeros=())
    filas += [
        *detalle("51900000001"),
        [],
        [None, None, None],
        *detalle("51900000002"),
        ["", "", ""],
        *detalle("51900000003"),
    ]
    filas[1] = ["TOTAL DE ENVIO", 3]

    resultado = leer_informe(tabla(filas))

    assert resultado.numeros == ("51900000001", "51900000002", "51900000003")
    assert resultado.coincide_total is True


def test_una_fila_de_detalle_sin_numero_no_cuenta() -> None:
    filas = observado(numeros=("51900000001",)) + [[CAMPANA, TIPO, None], [CAMPANA, TIPO]]

    assert leer_informe(tabla(filas)).numeros == ("51900000001",)


def test_la_campana_y_el_tipo_son_los_de_la_primera_fila_de_detalle() -> None:
    filas = observado(numeros=()) + [
        ["Una campana", "TIPO A", "51900000001"],
        ["Otra a mano", "TIPO B", "51900000002"],
    ]
    filas[1] = ["TOTAL DE ENVIO", 2]

    resultado = leer_informe(tabla(filas))

    assert (resultado.campana, resultado.tipo_envio) == ("Una campana", "TIPO A")


# --- El total (DU-WM-7) -----------------------------------------------------------------------


def test_un_total_que_no_coincide_se_informa_y_no_rechaza() -> None:
    resultado = leer_informe(tabla(observado(total=["TOTAL DE ENVIO", 101])))

    assert resultado.total_informado == 101
    assert len(resultado.numeros) == 3
    assert resultado.coincide_total is False


@pytest.mark.parametrize("total", [None, "", "no es un numero", True])
def test_un_total_ausente_o_ilegible_es_nulo_y_no_rechaza(total) -> None:
    resultado = leer_informe(tabla(observado(total=["TOTAL DE ENVIO", total])))

    assert resultado.total_informado is None
    assert resultado.coincide_total is None
    assert len(resultado.numeros) == 3


@pytest.mark.parametrize(
    ("celda", "esperado"),
    [(101, 101), (101.0, 101), ("101", 101), ("101.0", 101), ("1,205", 1205), ("1 205", 1205)],
)
def test_el_total_se_lee_de_un_numero_o_de_un_texto(celda, esperado) -> None:
    resultado = leer_informe(tabla(observado(total=["TOTAL DE ENVIO", celda])))

    assert resultado.total_informado == esperado


def test_sin_la_fila_total_el_total_es_nulo() -> None:
    filas = [f for f in observado() if f[:1] != ["TOTAL DE ENVIO"]]

    assert leer_informe(tabla(filas)).total_informado is None


# --- La fecha ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("celda", "esperada"),
    [
        ("30-10-2026", date(2026, 10, 30)),
        ("30/10/2026", date(2026, 10, 30)),
        ("2026-10-30", date(2026, 10, 30)),
        (date(2026, 10, 30), date(2026, 10, 30)),
        (datetime(2026, 10, 30, 14, 5), date(2026, 10, 30)),
        ("  30-10-2026 ", date(2026, 10, 30)),
    ],
)
def test_la_fecha_se_lee_en_texto_o_como_celda_de_fecha(celda, esperada) -> None:
    resultado = leer_informe(tabla(observado(fecha=["FECHA", celda])))

    assert resultado.fecha_informada == esperada


@pytest.mark.parametrize("celda", [None, "", "ayer", "31-02-2026", "30-10"])
def test_una_fecha_ausente_o_ilegible_es_nula_y_no_rechaza(celda) -> None:
    resultado = leer_informe(tabla(observado(fecha=["FECHA", celda])))

    assert resultado.fecha_informada is None
    assert len(resultado.numeros) == 3


def test_el_rotulo_fecha_admite_dos_puntos_y_otra_forma_de_escribirse() -> None:
    resultado = leer_informe(tabla(observado(fecha=["Fecha:", "30-10-2026"])))

    assert resultado.fecha_informada == date(2026, 10, 30)


# --- Los encabezados --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "encabezados",
    [
        ["CAMPAÑA", "TIPO DE ENVIO", "NUMERO"],
        ["CAMPANA", "TIPO DE ENVIO", "NUMERO"],
        ["campaña", "tipo de envio", "numero"],
        ["Campaña ", " Tipo  de Envío", "Número"],
        ["CAMPAÑA", "TIPO DE ENVÍO", "NÚMERO"],
    ],
)
def test_los_encabezados_se_comparan_sin_tildes_ni_mayusculas(encabezados) -> None:
    resultado = leer_informe(tabla(observado(encabezados=encabezados)))

    assert resultado.numeros == ("51900000001", "51900000002", "51900000003")


@pytest.mark.parametrize(
    "encabezados",
    [
        ["TIPO DE ENVIO", "NUMERO"],
        ["CAMPAÑA", "NUMERO"],
        ["CAMPAÑA", "TIPO DE ENVIO"],
        ["NUMERO"],
        ["CAMPAÑA", "TIPO DE ENVIO", "TELEFONO"],
    ],
)
def test_un_encabezado_que_falta_es_informe_sin_encabezados(encabezados) -> None:
    assert error_de(observado(encabezados=encabezados)) is CodigoWhatsmkt.INFORME_SIN_ENCABEZADOS


def test_sin_la_fila_de_encabezados_es_informe_sin_encabezados() -> None:
    filas = [observado()[0], observado()[1], [], *detalle("51900000001")]

    assert error_de(filas) is CodigoWhatsmkt.INFORME_SIN_ENCABEZADOS


def test_una_tabla_que_no_es_el_informe_es_informe_sin_encabezados() -> None:
    otra = [["Pagare", "Telefono", "Monto"], ["0001", "900000001", 10]]

    assert error_de(otra) is CodigoWhatsmkt.INFORME_SIN_ENCABEZADOS


def test_el_motivo_dice_que_encabezado_falta() -> None:
    with pytest.raises(ErrorWhatsmkt) as error:
        leer_informe(tabla(observado(encabezados=["CAMPAÑA", "NUMERO"])))

    assert "TIPO DE ENVIO" in str(error.value)


# --- Sin numeros ------------------------------------------------------------------------------


def test_sin_ningun_numero_es_informe_sin_filas() -> None:
    assert error_de(observado(numeros=())) is CodigoWhatsmkt.INFORME_SIN_FILAS


def test_con_solo_filas_vacias_despues_de_los_encabezados_es_informe_sin_filas() -> None:
    filas = observado(numeros=()) + [[], [None, None, None], [CAMPANA, TIPO, ""]]

    assert error_de(filas) is CodigoWhatsmkt.INFORME_SIN_FILAS


# --- Los numeros ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("celda", "esperado"),
    [
        (51900000001, "51900000001"),
        (51900000001.0, "51900000001"),
        ("51900000001", "51900000001"),
        ("51900000001.0", "51900000001"),
        ("5.1900000001e10", "51900000001"),
        ("+51 900 000 001", "51900000001"),
        ("  51900000001 ", "51900000001"),
    ],
)
def test_un_numero_se_lee_siempre_como_texto_de_digitos(celda, esperado) -> None:
    assert solo_digitos(celda) == esperado
    assert leer_informe(tabla(observado(numeros=(celda,)))).numeros == (esperado,)


@pytest.mark.parametrize("celda", [None, "", "   ", "sin numero", True, 1.5])
def test_lo_que_no_es_un_numero_no_tiene_digitos(celda) -> None:
    assert solo_digitos(celda) is None


def test_un_numero_repetido_se_conserva_repetido_para_comparar_el_total() -> None:
    resultado = leer_informe(tabla(observado(numeros=("51900000001", "51900000001"))))

    assert resultado.numeros == ("51900000001", "51900000001")
    assert resultado.coincide_total is True


# --- Puro: sin archivos ni adaptadores --------------------------------------------------------


@pytest.mark.parametrize("modulo", [informe, conciliacion])
def test_el_nucleo_no_importa_adaptadores_ni_abre_archivos(modulo) -> None:
    fuente = Path(modulo.__file__).read_text(encoding="utf-8")

    for prohibido in ("app.adapters", "openpyxl", "open(", "Path(", "lector_tabla", "pandas"):
        assert prohibido not in fuente, prohibido

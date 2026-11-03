"""Conciliacion de lo cargado con el informe de WhatsMKT, por numero (T-WM-B6a; RF-WM-39, RF-41).

Todo sintetico y en memoria: las filas cargadas y los numeros del informe se arman en la prueba.
Numeros 51900000xxx.
"""

import pytest

from app.core.entities.whatsmkt_informe import FilaCargadaWhatsmkt
from app.core.services.plataformas.whatsmkt.conciliacion import conciliar


def producto(i: int, numero: str | None = None) -> FilaCargadaWhatsmkt:
    return FilaCargadaWhatsmkt(numero or f"51900000{i:03d}", f"{i:018d}", False)


def supervisor(i: int) -> FilaCargadaWhatsmkt:
    return FilaCargadaWhatsmkt(f"51900000{900 + i}", None, True)


def numeros(filas) -> list[str]:
    return [f.numero for f in filas]


# --- Lo basico --------------------------------------------------------------------------------


def test_un_producto_esta_enviado_si_su_numero_aparece_en_el_informe() -> None:
    cargadas = [producto(1), producto(2), producto(3)]

    resultado = conciliar(cargadas, ["51900000001", "51900000003"])

    assert numeros(resultado.productos_enviados) == ["51900000001", "51900000003"]
    assert numeros(resultado.productos_no_enviados) == ["51900000002"]
    assert (resultado.productos.cargados, resultado.productos.enviados) == (3, 2)
    assert resultado.productos.no_enviados == 1
    assert resultado.sin_correspondencia == ()


def test_el_orden_del_informe_y_el_de_la_carga_no_importan() -> None:
    cargadas = [producto(1), producto(2), producto(3)]

    en_orden = conciliar(cargadas, ["51900000001", "51900000002", "51900000003"])
    revuelto = conciliar(cargadas, ["51900000003", "51900000001", "51900000002"])
    carga_revuelta = conciliar(
        [producto(3), producto(1), producto(2)], ["51900000001", "51900000002", "51900000003"]
    )

    assert en_orden.productos == revuelto.productos == carga_revuelta.productos
    assert en_orden.productos.enviados == 3
    assert sorted(numeros(carga_revuelta.productos_enviados)) == numeros(
        en_orden.productos_enviados
    )


def test_todo_enviado() -> None:
    resultado = conciliar(
        [producto(1), producto(2), supervisor(1)], ["51900000001", "51900000002", "51900000901"]
    )

    assert (resultado.total.cargados, resultado.total.enviados, resultado.total.no_enviados) == (
        3,
        3,
        0,
    )
    assert resultado.productos_no_enviados == () == resultado.supervision_no_enviados


def test_nada_enviado() -> None:
    resultado = conciliar([producto(1), producto(2), supervisor(1)], ["51900000555"])

    assert (resultado.total.cargados, resultado.total.enviados, resultado.total.no_enviados) == (
        3,
        0,
        3,
    )
    assert resultado.productos_enviados == () == resultado.supervision_enviados


def test_sin_filas_cargadas_todo_el_informe_queda_sin_correspondencia() -> None:
    resultado = conciliar([], ["51900000001", "51900000002"])

    assert resultado.total.cargados == 0
    assert resultado.sin_correspondencia == ("51900000001", "51900000002")


def test_un_informe_vacio_deja_todo_sin_enviar() -> None:
    resultado = conciliar([producto(1), supervisor(1)], [])

    assert (resultado.productos.no_enviados, resultado.supervision.no_enviados) == (1, 1)
    assert resultado.sin_correspondencia == ()


# --- Un numero, dos productos (P-7) -----------------------------------------------------------


def test_si_un_numero_cubre_dos_productos_el_envio_cuenta_para_los_dos() -> None:
    cargadas = [producto(1), producto(2, numero="51900000001"), producto(3)]

    resultado = conciliar(cargadas, ["51900000001"])

    assert numeros(resultado.productos_enviados) == ["51900000001", "51900000001"]
    assert [f.pagare for f in resultado.productos_enviados] == [f"{1:018d}", f"{2:018d}"]
    assert (resultado.productos.cargados, resultado.productos.enviados) == (3, 2)


def test_un_numero_repetido_en_el_informe_no_cuenta_dos_veces_para_un_producto() -> None:
    resultado = conciliar([producto(1)], ["51900000001", "51900000001"])

    assert resultado.productos.enviados == 1
    assert resultado.sin_correspondencia == ()


# --- Numeros del informe sin correspondencia --------------------------------------------------


def test_un_numero_del_informe_que_no_esta_en_la_carga_queda_sin_correspondencia() -> None:
    resultado = conciliar([producto(1)], ["51900000001", "51900000777", "51900000888"])

    assert resultado.sin_correspondencia == ("51900000777", "51900000888")
    assert resultado.total_sin_correspondencia == 2


def test_los_sin_correspondencia_no_se_repiten_y_siguen_el_orden_del_informe() -> None:
    resultado = conciliar(
        [producto(1)], ["51900000888", "51900000777", "51900000888", "51900000001"]
    )

    assert resultado.sin_correspondencia == ("51900000888", "51900000777")


def test_el_numero_de_un_supervisor_en_el_informe_tiene_correspondencia() -> None:
    resultado = conciliar([producto(1), supervisor(1)], ["51900000901"])

    assert resultado.sin_correspondencia == ()


# --- Supervision aparte (RF-41) ---------------------------------------------------------------


def test_los_supervisores_se_concilian_aparte_de_los_productos() -> None:
    cargadas = [supervisor(1), supervisor(2), producto(1), producto(2)]

    resultado = conciliar(cargadas, ["51900000901", "51900000001"])

    assert numeros(resultado.supervision_enviados) == ["51900000901"]
    assert numeros(resultado.supervision_no_enviados) == ["51900000902"]
    assert numeros(resultado.productos_enviados) == ["51900000001"]
    assert numeros(resultado.productos_no_enviados) == ["51900000002"]
    assert (resultado.supervision.cargados, resultado.supervision.enviados) == (2, 1)
    assert (resultado.productos.cargados, resultado.productos.enviados) == (2, 1)
    assert (resultado.total.cargados, resultado.total.enviados, resultado.total.no_enviados) == (
        4,
        2,
        2,
    )
    assert all(f.pagare is None for f in resultado.supervision_enviados)


def test_un_supervisor_con_el_numero_de_un_producto_se_cuenta_en_cada_grupo() -> None:
    resultado = conciliar([supervisor(1), producto(1, numero="51900000901")], ["51900000901"])

    assert (resultado.supervision.enviados, resultado.productos.enviados) == (1, 1)


# --- Los numeros se comparan como digitos -----------------------------------------------------


@pytest.mark.parametrize("en_el_informe", ["51900000001", "51900000001.0", "+51 900 000 001"])
def test_los_numeros_se_comparan_como_texto_de_digitos(en_el_informe) -> None:
    resultado = conciliar([producto(1, numero="51900000001.0")], [en_el_informe])

    assert resultado.productos.enviados == 1
    assert resultado.sin_correspondencia == ()


def test_un_valor_del_informe_sin_digitos_se_ignora() -> None:
    resultado = conciliar([producto(1)], ["", "sin numero", "51900000001"])

    assert resultado.productos.enviados == 1
    assert resultado.sin_correspondencia == ()

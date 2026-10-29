"""Las ayudas de las pruebas espejo de i18n (T-MM-C10, L-B6): nombran la clave que falta."""

from enum import Enum

import pytest

from tests.ayudas.espejo_i18n import (
    assert_cubre,
    claves_de,
    diccionario,
    problemas_de_cobertura,
)


class _Codigo(Enum):
    UNO = "uno"
    DOS = "dos"
    TRES = "tres"


def test_las_claves_que_faltan_o_estan_vacias_se_nombran() -> None:
    plano = {"p.uno": "Uno", "p.dos": "", "otro.tres": "Tres"}

    assert problemas_de_cobertura(_Codigo, "p", plano) == (["p.tres"], ["p.dos"])


def test_sin_problemas_no_devuelve_nada() -> None:
    plano = {"p.uno": "Uno", "p.dos": "Dos", "p.tres": "Tres"}

    assert problemas_de_cobertura(_Codigo, "p", plano) == ([], [])


def test_assert_cubre_falla_nombrando_la_clave_y_el_idioma() -> None:
    with pytest.raises(AssertionError) as error:
        assert_cubre(_Codigo, "claveQueNoExiste.codigo", ayuda="Se agrega en el frontend.")

    mensaje = str(error.value)
    assert "claveQueNoExiste.codigo.uno" in mensaje
    assert "es.json" in mensaje
    assert "Se agrega en el frontend." in mensaje


def test_los_diccionarios_reales_son_planos_y_traen_el_bloque_de_mowa_mes() -> None:
    for idioma in ("es", "en"):
        assert all(isinstance(valor, str) for valor in diccionario(idioma).values())
        assert claves_de("mowaMes.codigo", idioma)


def test_claves_de_exige_el_punto_despues_del_prefijo() -> None:
    assert all(k.startswith("mowaMes.codigo.") for k in claves_de("mowaMes.codigo", "es"))
    assert claves_de("mowaMes.codig", "es") == {}

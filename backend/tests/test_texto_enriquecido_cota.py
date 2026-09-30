"""Largo maximo de una expresion (RF-47, seccion 6): la cota es siempre un tope verdadero."""

from datetime import date

import pytest

from app.core.entities.texto_enriquecido import TipoValor
from app.core.services.texto_enriquecido import evaluador

T, N, F = TipoValor.TEXTO, TipoValor.NUMERO, TipoValor.FECHA
VARIABLES = {"t": T, "n": N, "f": F, "tel": T, "otro": T}


def _cota(plantilla: str) -> int | None:
    return evaluador.compilar_texto(plantilla, VARIABLES).cota


def test_un_texto_fijo_mide_lo_que_mide() -> None:
    assert _cota("") == 0
    assert _cota("Hola ñandú") == 10


def test_una_variable_sin_funciones_no_tiene_cota() -> None:
    assert _cota("[@t]") is None
    assert _cota("[@n]") is None
    assert _cota("[@f]") is None


def test_una_sola_parte_sin_cota_deja_la_expresion_sin_cota() -> None:
    assert _cota("Hola [@t | primeros(8)] y [@otro]") is None


def test_primeros_y_ultimos_dan_n() -> None:
    assert _cota("[@t | primeros(8)]") == 8
    assert _cota("[@t | ultimos(3)]") == 3


def test_recortes_encadenados_dan_el_menor() -> None:
    assert _cota("[@t | primeros(3) | primeros(8)]") == 3
    assert _cota("[@t | primeros(8) | ultimos(3)]") == 3


def test_las_funciones_que_solo_transforman_conservan_la_cota() -> None:
    for funcion in ["mayusculas", "minusculas", "capitalizar", "recortar", "sin_tildes"]:
        assert _cota(f"[@t | primeros(8) | {funcion}]") == 8, funcion
        assert _cota(f"[@t | {funcion}]") is None, funcion


def test_formato_fecha_da_el_largo_del_patron() -> None:
    assert _cota('[@f | formato_fecha("dd/mm/aaaa")]') == 10
    assert _cota('[@f | formato_fecha("dd/mm/aa")]') == 8
    assert _cota('[@f | formato_fecha("dd de nombre_mes de aaaa")]') == 2 + 4 + 10 + 4 + 4
    assert _cota('[@f | formato_fecha("aaaa")]') == 4


def test_enlace_whatsapp_da_el_largo_del_prefijo_mas_9() -> None:
    assert _cota("[@tel | enlace_whatsapp]") == len("https://wa.me/+51") + 9
    assert _cota('[@tel | enlace_whatsapp("https://x.test/")]') == len("https://x.test/") + 9


def test_la_cota_de_un_mensaje_es_la_suma_de_sus_partes() -> None:
    plantilla = (
        "Estimado(a) [@t | primeros(8)]: su cuota vence el "
        '[@f | formato_fecha("dd/mm/aaaa")]. Escribenos a [@tel | enlace_whatsapp]'
    )
    fijo = len("Estimado(a) ") + len(": su cuota vence el ") + len(". Escribenos a ")

    assert _cota(plantilla) == fijo + 8 + 10 + len("https://wa.me/+51") + 9


def test_reemplazar_cuenta_lo_que_puede_alargar() -> None:
    assert _cota('[@t | primeros(10) | reemplazar("a", "xyz")]') == 10 + 10 * 2
    assert _cota('[@t | primeros(10) | reemplazar("ab", "x")]') == 10
    assert _cota('[@t | reemplazar("a", "xyz")]') is None


def test_rellenar_izquierda_da_el_mayor_entre_el_texto_y_el_relleno() -> None:
    assert _cota('[@t | primeros(5) | rellenar_izquierda(8, "0")]') == 8
    assert _cota('[@t | primeros(20) | rellenar_izquierda(8, "0")]') == 20
    assert _cota('[@t | rellenar_izquierda(8, "0")]') is None


def test_si_vacio_puede_alargar_hasta_el_alternativo() -> None:
    assert _cota('[@t | primeros(3) | si_vacio("sin dato")]') == len("sin dato")
    assert _cota('[@t | primeros(30) | si_vacio("x")]') == 30
    assert _cota("[@t | primeros(3) | si_vacio(@otro)]") is None
    assert _cota('[@t | si_vacio("x")]') is None


def test_las_conversiones_y_los_formatos_de_numero_pierden_la_cota() -> None:
    assert _cota("[@n | redondear(2)]") is None
    assert _cota("[@n | formato_numero(2)]") is None
    assert _cota("[@n | a_texto | primeros(4)]") == 4
    assert _cota("[@n | a_texto]") is None
    assert _cota("[@t | primeros(3) | a_numero]") is None


def test_una_fecha_calculada_mide_10() -> None:
    assert _cota("[@f | sumar_dias(3)]") == 10
    assert _cota('[@t | a_fecha("dd/mm/aaaa")]') == 10


@pytest.mark.parametrize(
    ("plantilla", "producto"),
    [
        ("[@t | primeros(8)]", {"t": "ÁÉÍÓÚ" * 5}),
        ('[@t | primeros(6) | rellenar_izquierda(10, "*")]', {"t": "ab"}),
        ('[@t | primeros(5) | reemplazar("a", "xyz")]', {"t": "aaaaaaaa"}),
        ('[@f | formato_fecha("dd de nombre_mes de aaaa")]', {"f": date(2026, 9, 29)}),
        ('[@f | formato_fecha("dd de nombre_mes de aaaa")]', {"f": date(2026, 5, 1)}),
        ("[@tel | enlace_whatsapp]", {"tel": "999999999"}),
        ('[@t | primeros(3) | si_vacio("sin dato")]', {"t": None}),
        ("[@f | sumar_dias(3)]", {"f": date(999, 1, 1)}),
    ],
)
def test_la_cota_nunca_es_menor_que_lo_que_se_puede_producir(plantilla, producto) -> None:
    compilada = evaluador.compilar_texto(plantilla, VARIABLES)

    resultado = compilada.evaluar(producto)

    assert resultado.problemas == ()
    assert len(resultado.texto) <= compilada.cota

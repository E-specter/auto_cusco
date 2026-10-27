"""Normalizacion, coincidencia y similitud del mapeador (T-MAP-B1, RF-58)."""

import random
import re

import pytest

from app.core.entities.mapeador import CampoDestino
from app.core.services.ingesta_sabana.catalogo import CATALOGO_SABANA
from app.core.services.mapeador.similitud import (
    DIFERENCIA_DE_EMPATE,
    UMBRAL_PARECIDO,
    alias_legible,
    alias_legibles,
    candidatos_de_similitud,
    coincide,
    normalizar_cabecera,
    similitud,
    similitud_entre,
    sin_tildes,
)


def campo(nombre: str, *alias: str) -> CampoDestino:
    return CampoDestino(nombre, f"campo.{nombre}", "texto", False, alias)


# --- Normalizacion ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cabecera", "esperada"),
    [
        ("Región", "region"),
        ("  TIPO   DE  REPROGRAMACIÓN ", "tipo de reprogramacion"),
        ("Días\tAtraso\nHoy", "dias atraso hoy"),
        ("DÍAS SICMAC-C", "dias sicmac-c"),
        ("ñandú", "nandu"),
        ("", ""),
        ("   ", ""),
        ("ÁÉÍÓÚ", "aeiou"),
    ],
)
def test_normalizar_cabecera(cabecera, esperada) -> None:
    assert normalizar_cabecera(cabecera) == esperada


def test_normalizar_es_idempotente() -> None:
    azar = random.Random(7)
    alfabeto = "aAeEñÑ áéÍ_-.\t12"
    for _ in range(300):
        texto = "".join(azar.choice(alfabeto) for _ in range(azar.randint(0, 12)))
        una_vez = normalizar_cabecera(texto)
        assert normalizar_cabecera(una_vez) == una_vez


def test_sin_tildes_solo_quita_marcas() -> None:
    assert sin_tildes("canción Ñu") == "cancion Nu"


# --- Coincide -----------------------------------------------------------------------------------


def test_coincide_por_alias_con_fullmatch_y_no_con_search() -> None:
    zona = campo("zona", "zona")

    assert coincide("zona", zona)
    assert not coincide("zona norte", zona)
    assert not coincide("la zona", zona)


def test_coincide_por_alias_con_expresion_regular() -> None:
    saldo = campo("saldo", r"saldo( [0-9]{1,2}/[0-9]{1,2})?")

    assert coincide("saldo", saldo)
    assert coincide("saldo 03/09", saldo)
    assert not coincide("saldo 03/09/2026", saldo)


def test_coincide_por_nombre_con_guion_bajo_como_espacio() -> None:
    dias = campo("dias_atraso", "dias atraso hoy")

    assert coincide("dias atraso", dias)
    assert coincide("dias atraso hoy", dias)
    assert not coincide("dias_atraso", dias)  # el normalizado no trae guiones bajos del archivo
    assert not coincide("dias", dias)


def test_un_campo_sin_alias_coincide_solo_por_su_nombre() -> None:
    assert coincide("fecha pago", campo("fecha_pago"))
    assert not coincide("fecha", campo("fecha_pago"))


def test_coincide_no_ve_la_diferencia_de_mayusculas_porque_recibe_el_normalizado() -> None:
    assert not coincide("Zona", campo("zona", "zona"))  # el que normaliza es el llamador


# --- Similitud ----------------------------------------------------------------------------------


def test_la_similitud_de_dos_textos_iguales_es_uno_y_la_de_dos_sin_nada_en_comun_es_cero() -> None:
    assert similitud_entre("fecha de pago", "fecha de pago") == 1.0
    assert similitud_entre("abc", "xyz") == 0.0
    assert similitud_entre("", "") == 1.0


def test_el_orden_de_las_palabras_no_baja_la_similitud() -> None:
    # SequenceMatcher lo castigaria; la proporcion de palabras en comun, no.
    assert similitud_entre("pago fecha de", "fecha de pago") == 1.0


def test_la_similitud_es_el_maximo_de_las_dos_medidas() -> None:
    from difflib import SequenceMatcher

    a, b = "fecha de pagos", "fecha de pago"
    razon = SequenceMatcher(None, a, b).ratio()

    assert similitud_entre(a, b) == max(razon, 2 / 4)  # una palabra de cuatro distintas
    assert similitud_entre(a, b) == razon


def test_la_similitud_esta_entre_cero_y_uno_y_solo_es_uno_con_algo_en_comun() -> None:
    azar = random.Random(11)
    alfabeto = "abc d"
    for _ in range(300):
        a = "".join(azar.choice(alfabeto) for _ in range(azar.randint(0, 8))).strip()
        b = "".join(azar.choice(alfabeto) for _ in range(azar.randint(0, 8))).strip()

        assert 0.0 <= similitud_entre(a, b) <= 1.0
        # `SequenceMatcher` no es simetrico: el orden es siempre (encabezado, candidato).
        assert similitud_entre(a, b) == similitud_entre(a, b)
        assert similitud_entre(a, a) == 1.0


def test_se_compara_contra_el_nombre_y_los_alias_literales() -> None:
    saldo = campo("saldo_total", "importe final", r"saldo( [0-9]{1,2}/[0-9]{1,2})?")

    assert candidatos_de_similitud(saldo) == ("saldo total", "importe final")


def test_un_alias_con_cualquier_metacaracter_no_participa() -> None:
    for alias in ["a.b", "a*", "a+", "a?", "a|b", "(a)", "[a]", "a{2}", "^a", "a$", "a\\d"]:
        assert candidatos_de_similitud(campo("x", alias)) == ("x",), alias


def test_un_alias_literal_con_guion_o_espacio_participa() -> None:
    assert candidatos_de_similitud(campo("x", "dias sicmac-c")) == ("x", "dias sicmac-c")


def test_la_similitud_de_un_campo_es_la_mayor_de_sus_candidatos() -> None:
    importe = campo("monto", "importe final")

    assert similitud("importe final", importe) == 1.0
    assert similitud("monto", importe) == 1.0
    assert similitud("importe finals", importe) == similitud_entre(
        "importe finals", "importe final"
    )


def test_un_campo_solo_con_alias_de_expresion_regular_se_compara_contra_su_nombre() -> None:
    documento = campo("documento", r"dni ?/ ?ruc")

    assert similitud("documentos", documento) >= UMBRAL_PARECIDO
    assert similitud("dni / ruc", documento) < UMBRAL_PARECIDO  # el alias no participa


def test_las_constantes_de_configuracion() -> None:
    assert UMBRAL_PARECIDO == 0.75
    assert DIFERENCIA_DE_EMPATE == 0.02


# --- El alias legible (T-MAP-B4) ----------------------------------------------------------------


@pytest.mark.parametrize(
    "regex", [r"dni ?/ ?ruc", r"saldo.*", r"^x$", r"a|b", r"(a)", r"a\.b", r"[ab]", r"a{2}"]
)
def test_un_alias_de_expresion_regular_no_es_legible(regex) -> None:
    assert alias_legible(regex) is None
    assert alias_legibles(campo("x", regex)) == ()


def test_un_alias_literal_sale_en_forma_legible_con_los_guiones_bajos_como_espacio() -> None:
    assert alias_legible("dias atraso hoy") == "dias atraso hoy"
    assert alias_legible("dias_atraso_hoy") == "dias atraso hoy"
    assert alias_legible("dias sicmac-c") == "dias sicmac-c"  # el guion no es metacaracter


def test_los_alias_legibles_de_un_campo_van_en_el_orden_del_catalogo_y_sin_repetir() -> None:
    mixto = campo("x", "beta", r"a|b", "alfa", "beta", "al_fa", "gamma")

    assert alias_legibles(mixto) == ("beta", "alfa", "al fa", "gamma")
    assert alias_legibles(mixto) == alias_legibles(mixto)  # estable


def test_un_campo_sin_alias_literales_da_vacio() -> None:
    assert alias_legibles(campo("x")) == ()
    assert alias_legibles(campo("x", r"dni ?/ ?ruc", r"saldo.*")) == ()


def test_ningun_alias_legible_del_catalogo_tiene_metacaracteres_ni_guion_bajo() -> None:
    for c in CATALOGO_SABANA.campos:
        for alias in alias_legibles(c):
            assert re.search(r"[\.^$*+?{}\[\]|()_]", alias) is None, (c.nombre, alias)


def test_el_alias_legible_y_los_candidatos_de_similitud_hablan_de_los_mismos_alias() -> None:
    # Los candidatos son el nombre y los alias literales; sin guiones bajos son los mismos.
    for c in CATALOGO_SABANA.campos:
        assert alias_legibles(c) == tuple(dict.fromkeys(candidatos_de_similitud(c)[1:])), c.nombre

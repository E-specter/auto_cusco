"""Pruebas de `grafemas_borrados` (T-MM-B9): lo que `a_gsm7` borra, agrupado por grafema.

Los emoji se escriben con escapes de punto de codigo, no pegados en el codigo fuente: el archivo
es ASCII y las pruebas no dependen de como un editor muestre un ZWJ o un selector de variacion.
"""

import random
import time

import pytest

from app.core.services.texto_enriquecido.gsm7 import (
    a_gsm7,
    caracteres_borrados,
    grafemas_borrados,
)

MANO = "\U0001f44d"
TONO = "\U0001f3fd"
HOMBRE = "\U0001f468"
MUJER = "\U0001f469"
NINA = "\U0001f467"
ZWJ = "\N{ZERO WIDTH JOINER}"
VS16 = "\N{VARIATION SELECTOR-16}"
KEYCAP = "\N{COMBINING ENCLOSING KEYCAP}"
CORAZON = "\N{HEAVY BLACK HEART}"
PE = ["\U0001f1f5", "\U0001f1ea"]  # indicadores regionales P y E
AR = ["\U0001f1e6", "\U0001f1f7"]  # A y R
BANDERA = "\U0001f3f4"
ETIQUETAS = "".join(chr(0xE0000 + ord(c)) for c in "gbeng") + "\U000e007f"  # Inglaterra

# Invisibles y signos que a_gsm7 conserva, transliteran o borra, por su nombre Unicode.
ZWSP = "\N{ZERO WIDTH SPACE}"
BOM = "\N{ZERO WIDTH NO-BREAK SPACE}"
SHY = "\N{SOFT HYPHEN}"
CIRILICA_I = "\N{CYRILLIC CAPITAL LETTER SHORT I}"
A_TILDE = "\N{LATIN SMALL LETTER A WITH ACUTE}"
O_TILDE = "\N{LATIN SMALL LETTER O WITH ACUTE}"
U_TILDE = "\N{LATIN SMALL LETTER U WITH ACUTE}"
N_TILDE = "\N{LATIN SMALL LETTER N WITH TILDE}"
COMILLA_I = "\N{LEFT DOUBLE QUOTATION MARK}"
COMILLA_D = "\N{RIGHT DOUBLE QUOTATION MARK}"
ANGULAR_I = "\N{LEFT-POINTING DOUBLE ANGLE QUOTATION MARK}"
ANGULAR_D = "\N{RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK}"
SIMPLE_I = "\N{LEFT SINGLE QUOTATION MARK}"
SIMPLE_D = "\N{RIGHT SINGLE QUOTATION MARK}"
PUNTOS = "\N{HORIZONTAL ELLIPSIS}"
RAYA_CORTA = "\N{EN DASH}"
RAYA_LARGA = "\N{EM DASH}"
GRADO = "\N{DEGREE SIGN}"
ORD_M = "\N{MASCULINE ORDINAL INDICATOR}"
ORD_F = "\N{FEMININE ORDINAL INDICATOR}"
ESP_DURO = "\N{NO-BREAK SPACE}"
ESP_FINO = "\N{THIN SPACE}"
ESP_IDEOGRAFICO = "\N{IDEOGRAPHIC SPACE}"
EURO = "\N{EURO SIGN}"


def test_un_emoji_con_tono_de_piel_es_un_solo_elemento() -> None:
    assert grafemas_borrados(f"a{MANO}{TONO}b") == (MANO + TONO,)


def test_una_familia_con_zwj_es_un_solo_elemento() -> None:
    familia = HOMBRE + ZWJ + MUJER + ZWJ + NINA

    assert grafemas_borrados(f"x{familia}y") == (familia,)


def test_una_bandera_son_dos_indicadores_en_un_elemento() -> None:
    assert grafemas_borrados("".join(PE)) == ("".join(PE),)


def test_dos_banderas_seguidas_no_se_funden() -> None:
    assert grafemas_borrados("".join(PE + AR)) == ("".join(PE), "".join(AR))


def test_tres_indicadores_son_una_bandera_y_un_indicador_suelto() -> None:
    assert grafemas_borrados("".join(PE + AR[:1])) == ("".join(PE), AR[0])


def test_un_keycap_deja_el_numero_y_se_informa_solo_la_parte_borrada() -> None:
    # "1" + selector de variacion + keycap: el 1 se queda en el SMS.
    assert grafemas_borrados("1" + VS16 + KEYCAP) == (VS16 + KEYCAP,)
    assert a_gsm7("1" + VS16 + KEYCAP) == "1"


def test_un_corazon_con_selector_de_variacion_es_un_elemento() -> None:
    # El corazon (U+2764) esta fuera de GSM-7 y su selector tambien.
    assert grafemas_borrados(f"te{CORAZON}{VS16}go") == (CORAZON + VS16,)


def test_una_bandera_de_subdivision_con_etiquetas_es_un_elemento() -> None:
    assert grafemas_borrados(f"({BANDERA}{ETIQUETAS})") == (BANDERA + ETIQUETAS,)


def test_un_emoji_repetido_aparece_una_sola_vez_y_en_orden_de_aparicion() -> None:
    texto = f"{MANO}a{CORAZON}b{MANO}c{MANO}{TONO}d{CORAZON}"

    assert grafemas_borrados(texto) == (MANO, CORAZON, MANO + TONO)


def test_el_mismo_emoji_con_y_sin_tono_son_dos_elementos_distintos() -> None:
    assert grafemas_borrados(f"{MANO}{MANO}{TONO}") == (MANO, MANO + TONO)


def test_un_zwj_suelto_entre_letras_se_informa_solo() -> None:
    assert grafemas_borrados(f"a{ZWJ}b") == (ZWJ,)


def test_un_invisible_suelto_se_informa_con_su_caracter() -> None:
    assert grafemas_borrados(f"a{ZWSP}b") == (ZWSP,)
    # El guion suave tampoco esta en GSM-7: se borra y se informa, aparte del BOM.
    assert grafemas_borrados(f"a{BOM}b{SHY}c") == (BOM, SHY)


def test_un_vs16_suelto_y_un_indicador_regional_impar_se_informan_solos() -> None:
    assert grafemas_borrados(f"a{VS16}b") == (VS16,)
    assert grafemas_borrados(f"a{PE[0]}b") == (PE[0],)


def test_una_corrida_larga_de_indicadores_regionales_son_banderas_de_dos_en_dos() -> None:
    # 20 000 indicadores iguales: 10 000 banderas identicas, que se informan una sola vez.
    assert grafemas_borrados(PE[0] * 20_000) == (PE[0] * 2,)
    # Con una cantidad impar sobra uno suelto, tras la bandera.
    assert grafemas_borrados(PE[0] * 20_001) == (PE[0] * 2, PE[0])
    # Alternando P y E: las banderas son "PE", todas iguales.
    assert grafemas_borrados("".join(PE) * 10_000) == ("".join(PE),)


def test_una_corrida_larga_de_indicadores_termina_enseguida() -> None:
    # Cota holgada (no mide el tiempo fino): una cuenta cuadratica de 200 000 indicadores
    # tardaria minutos; la lineal, una fraccion de segundo.
    inicio = time.perf_counter()
    grafemas_borrados(PE[0] * 200_000)
    grafemas_borrados((MANO + ZWJ) * 100_000 + "".join(PE))

    assert time.perf_counter() - inicio < 10


def test_un_emoji_con_zwj_largo_seguido_de_una_bandera_las_separa_bien() -> None:
    cadena = ZWJ.join([MANO] * 50)

    assert grafemas_borrados(f"{cadena}{PE[0]}{PE[1]}") == (cadena, "".join(PE))


def test_un_emoji_pegado_a_una_letra_con_tilde_informa_solo_el_emoji() -> None:
    assert grafemas_borrados(f"{O_TILDE}{MANO}{N_TILDE}") == (MANO,)
    assert grafemas_borrados(f"{MANO}{O_TILDE}") == (MANO,)


@pytest.mark.parametrize(
    "texto",
    [
        f"venci{O_TILDE} el pago {N_TILDE}and{U_TILDE}",  # diacriticos: se quitan, no se pierden
        f"{COMILLA_I}hola{COMILLA_D} {ANGULAR_I}x{ANGULAR_D} {SIMPLE_I}a{SIMPLE_D} {PUNTOS}",
        f"{RAYA_CORTA} {RAYA_LARGA} N{GRADO} 1{ORD_M} 2{ORD_F}",  # signos transliterados
        f"a{ESP_DURO}b{ESP_FINO}c{ESP_IDEOGRAFICO}d\te",  # pasan a un espacio normal
        f"{EURO} [x] {{y}} \\ ~ |",  # extendidos: se transliteran, no se pierden
        "linea 1\nlinea 2",
        "",
    ],
)
def test_lo_que_se_conserva_o_se_transliteran_nunca_aparece(texto) -> None:
    assert grafemas_borrados(texto) == ()


def test_el_texto_sin_nada_que_borrar_da_vacio() -> None:
    assert grafemas_borrados("Cobranza: su cuota vencio el 06/09/2026.") == ()


def test_un_texto_con_todo_mezclado() -> None:
    texto = (
        f"{COMILLA_I}Hola{COMILLA_D} {MANO}{TONO} N{GRADO} 1 {CORAZON}{VS16} {CIRILICA_I} {MANO}"
    )

    assert grafemas_borrados(texto) == (MANO + TONO, CORAZON + VS16, CIRILICA_I, MANO)


def test_el_orden_es_el_de_primera_aparicion_con_elementos_distintos() -> None:
    elementos = [MANO + TONO, CIRILICA_I, ZWJ, "".join(PE), CORAZON + VS16, KEYCAP + VS16, ZWSP]

    assert grafemas_borrados("a".join(elementos)) == tuple(elementos)
    assert grafemas_borrados("a".join(reversed(elementos))) == tuple(reversed(elementos))


# --- Propiedades (semilla fija) -----------------------------------------------------------------

_ALFABETO = (
    list("abcXYZ 019.,:\n")
    # Se conservan o se transliteran: nunca deben aparecer.
    + [A_TILDE, N_TILDE, COMILLA_I, PUNTOS, GRADO, ESP_DURO, "\t"]
    + [
        MANO,
        TONO,
        CORAZON,
        VS16,
        ZWJ,
        KEYCAP,
        HOMBRE,
        MUJER,
        BANDERA,
        "\N{ZERO WIDTH SPACE}",
        "\N{CYRILLIC CAPITAL LETTER SHORT I}",
    ]
    + PE
    + AR
    + list(ETIQUETAS)
)


def _al_azar(azar: random.Random) -> str:
    return "".join(azar.choice(_ALFABETO) for _ in range(azar.randint(0, 40)))


def test_propiedad_la_union_de_los_puntos_de_codigo_es_lo_que_borra_a_gsm7() -> None:
    azar = random.Random(20261022)
    for _ in range(4000):
        texto = _al_azar(azar)

        informado = {c for grafema in grafemas_borrados(texto) for c in grafema}

        assert informado == set(caracteres_borrados(texto)), repr(texto)


def test_propiedad_sin_repetir_en_orden_y_sin_inventar() -> None:
    azar = random.Random(7)
    for _ in range(2000):
        texto = _al_azar(azar)

        grafemas = grafemas_borrados(texto)

        assert len(set(grafemas)) == len(grafemas), repr(texto)
        # Cada elemento sale tal cual del texto, sin caracteres que a_gsm7 conserve.
        for grafema in grafemas:
            assert grafema in texto, repr(texto)
            assert all(caracteres_borrados(c) for c in grafema), repr(texto)


def test_propiedad_el_orden_es_el_de_primera_aparicion_y_se_compone() -> None:
    """Separar dos textos con una letra que se conserva no cambia nada: la lista del texto entero
    es la del primero y luego la del segundo, sin repetir (primera aparicion)."""
    azar = random.Random(20261023)
    for _ in range(2000):
        a, b = _al_azar(azar), _al_azar(azar)

        entero = grafemas_borrados(a + "x" + b)

        assert entero == tuple(dict.fromkeys(grafemas_borrados(a) + grafemas_borrados(b))), (
            repr(a),
            repr(b),
        )


def test_propiedad_si_a_gsm7_no_borra_nada_la_lista_es_vacia_y_al_reves() -> None:
    azar = random.Random(11)
    for _ in range(2000):
        texto = _al_azar(azar)
        sin_nada_borrado = not caracteres_borrados(texto)

        assert (grafemas_borrados(texto) == ()) is sin_nada_borrado, repr(texto)

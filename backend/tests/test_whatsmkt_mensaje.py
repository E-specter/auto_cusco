"""Reglas puras del mensaje de WhatsMKT, sin base (T-WM-B3; RF-WM-24 a RF-WM-27, DU-WM-3).

Datos sinteticos (telefonos 900000xxx).
"""

import pytest

from app.core.entities.texto_enriquecido import CodigoTexto
from app.core.entities.whatsmkt import CodigoWhatsmkt, ErrorWhatsmkt
from app.core.services.plataformas.whatsmkt import mensaje
from app.core.services.plataformas.whatsmkt.contexto import contexto_mensaje

ZWJ, VS16, VS15, KEYCAP = "‍", "️", "︎", "⃣"
FAMILIA = "👨" + ZWJ + "👩" + ZWJ + "👧"
BANDERA = "🇵🇪"


def error_de(llamada, *args) -> ErrorWhatsmkt:
    with pytest.raises(ErrorWhatsmkt) as error:
        llamada(*args)
    return error.value


# --- Emojis (RF-WM-24) ------------------------------------------------------------------------


def test_un_emoji_simple_se_rechaza_con_el_caracter_y_su_posicion_desde_1() -> None:
    error = error_de(mensaje.validar_sin_emojis, "Hola 😀")

    assert error.codigo is CodigoWhatsmkt.MENSAJE_CON_EMOJI
    assert error.parametros == {"caracter": "😀", "posicion": 6}


def test_se_informa_el_primero_aunque_haya_varios() -> None:
    error = error_de(mensaje.validar_sin_emojis, "ab 🔥 y 😀")

    assert error.parametros == {"caracter": "🔥", "posicion": 4}


def test_la_posicion_cuenta_caracteres_unicode_y_no_unidades_utf16() -> None:
    assert error_de(mensaje.validar_sin_emojis, "😀").parametros["posicion"] == 1
    assert error_de(mensaje.validar_sin_emojis, "a😀").parametros["posicion"] == 2
    # Un caracter fuera del plano basico antes del emoji cuenta uno (en UTF-16 serian dos).
    assert error_de(mensaje.validar_sin_emojis, "𝒜😀").parametros["posicion"] == 2


def test_un_emoji_compuesto_con_zwj_se_rechaza_por_su_primer_pictograma() -> None:
    error = error_de(mensaje.validar_sin_emojis, "Hola " + FAMILIA)

    assert error.parametros == {"caracter": "👨", "posicion": 6}


def test_un_zwj_suelto_se_rechaza() -> None:
    error = error_de(mensaje.validar_sin_emojis, "a" + ZWJ + "b")

    assert error.parametros == {"caracter": ZWJ, "posicion": 2}


def test_una_bandera_se_rechaza_por_sus_indicadores_regionales() -> None:
    error = error_de(mensaje.validar_sin_emojis, "Peru " + BANDERA)

    assert error.parametros["posicion"] == 6
    assert error.parametros["caracter"] == "🇵"


@pytest.mark.parametrize("selector", [VS16, VS15])
def test_un_selector_de_variante_se_rechaza_aunque_el_simbolo_sea_texto(selector) -> None:
    # `❤` solo es texto; con el selector pide dibujarse como emoji.
    error = error_de(mensaje.validar_sin_emojis, "Gracias ❤" + selector)

    assert error.parametros == {"caracter": selector, "posicion": 10}


def test_la_tecla_con_su_cierre_se_rechaza() -> None:
    assert error_de(mensaje.validar_sin_emojis, "1" + VS16 + KEYCAP).parametros["posicion"] == 2
    assert error_de(mensaje.validar_sin_emojis, "1" + KEYCAP).parametros["caracter"] == KEYCAP


@pytest.mark.parametrize(
    "emoji",
    [
        "✅",
        "❌",
        "⭐",
        "⚽",
        "☔",
        "⚡",
        "⏰",
        "🔥",
        "🚀",
        "🤝",
        "🥰",
        "🫶",
        "🟢",
        "🅰",
        "🏽",
        "⌚",
        "㊗",
    ],
)
def test_los_pictogramas_de_cada_bloque_se_rechazan(emoji) -> None:
    assert error_de(mensaje.validar_sin_emojis, f"x{emoji}").parametros["caracter"] == emoji


def test_las_tildes_la_enie_la_dieresis_y_los_signos_de_apertura_pasan() -> None:
    texto = "Camión, año, pingüino, ¿qué tal? ¡Hola! ÁÉÍÓÚ Ñ Ü á é í ó ú ñ ü"

    mensaje.validar_sin_emojis(texto)


def test_la_puntuacion_y_los_signos_de_un_mensaje_de_cobranza_pasan() -> None:
    mensaje.validar_sin_emojis(
        "Tu cuota de S/ 1,234.50 vence el 15/10/2026 (80%). “Pague” – ya – 100% seguro… €5 #1 *2*"
    )


# R-4: © y ✓ son simbolos de texto (no se dibujan como emoji sin el selector de variante).
@pytest.mark.parametrize("simbolo", ["©", "®", "™", "✓", "✗", "→", "←", "♥", "☎", "✔", "★", "•"])
def test_los_simbolos_que_son_texto_pasan_mientras_no_pidan_ser_emoji(simbolo) -> None:
    mensaje.validar_sin_emojis(f"Caja Cusco {simbolo} 2026")


@pytest.mark.parametrize("simbolo", ["©", "✓", "™"])
def test_el_mismo_simbolo_con_el_selector_de_emoji_si_se_rechaza(simbolo) -> None:
    error = error_de(mensaje.validar_sin_emojis, f"a{simbolo}{VS16}")

    assert error.parametros == {"caracter": VS16, "posicion": 3}


def test_un_texto_vacio_o_sin_emojis_no_lanza_nada() -> None:
    mensaje.validar_sin_emojis("")
    mensaje.validar_sin_emojis("Hola [$MACRO1$], INFO por [whatsapp]")


# --- Marcadores y macros (RF-WM-25) -----------------------------------------------------------


def test_los_marcadores_del_texto_son_las_macros_sin_repetir_y_si_usa_whatsapp() -> None:
    marcadores = mensaje.marcadores_del_texto(
        "Hola [$MACRO2$] y [$MACRO1$], de nuevo [$MACRO2$]. INFO por [whatsapp]"
    )

    assert marcadores.macros == (1, 2)
    assert marcadores.usa_whatsapp is True


def test_sin_marcadores() -> None:
    marcadores = mensaje.marcadores_del_texto("Hola, sin nada")

    assert (marcadores.macros, marcadores.usa_whatsapp) == ((), False)


def test_la_errata_marcro_y_los_marcadores_mal_escritos_no_cuentan() -> None:
    marcadores = mensaje.marcadores_del_texto("[$MARCRO1$] [$MACRO$] [MACRO1] [$macro1$] [$MACRO1]")

    assert marcadores.macros == ()


def test_una_macro_que_no_existe_se_rechaza_diciendo_cual_y_cuantas_hay() -> None:
    error = error_de(mensaje.validar_macros, "Hola [$MACRO1$] y [$MACRO4$]", 3)

    assert error.codigo is CodigoWhatsmkt.MACRO_INEXISTENTE
    assert error.parametros == {"macro": "[$MACRO4$]", "n": 3}


def test_se_informa_la_primera_macro_inexistente_en_el_orden_del_texto() -> None:
    error = error_de(mensaje.validar_macros, "[$MACRO5$] [$MACRO4$]", 3)

    assert error.parametros["macro"] == "[$MACRO5$]"


def test_la_macro_0_no_existe_y_la_ultima_si() -> None:
    assert error_de(mensaje.validar_macros, "[$MACRO0$]", 3).parametros["macro"] == "[$MACRO0$]"
    mensaje.validar_macros("[$MACRO3$]", 3)


def test_una_macro_de_la_definicion_que_el_mensaje_no_usa_no_es_un_error() -> None:
    mensaje.validar_macros("Hola [$MACRO1$]", 3)
    mensaje.validar_macros("Sin macros", 3)
    mensaje.validar_macros("Sin macros", 0)


def test_con_una_definicion_sin_macros_cualquier_macro_sobra() -> None:
    assert error_de(mensaje.validar_macros, "[$MACRO1$]", 0).parametros["n"] == 0


# --- Largo (RF-WM-26, DU-WM-3) ----------------------------------------------------------------


def test_el_tope_exacto_pasa_y_un_caracter_mas_no() -> None:
    mensaje.validar_largo("a" * 4096, 4096)
    error = error_de(mensaje.validar_largo, "a" * 4097, 4096)

    assert error.codigo is CodigoWhatsmkt.MENSAJE_LARGO
    assert error.parametros == {"largo": 4097, "maximo": 4096}


def test_las_macros_cuentan_tal_como_estan_escritas() -> None:
    mensaje.validar_largo("a" * 90 + "[$MACRO1$]", 100)  # el marcador son 10 caracteres
    assert error_de(mensaje.validar_largo, "a" * 91 + "[$MACRO1$]", 100).parametros["largo"] == 101


def test_whatsapp_cuenta_como_el_enlace_de_26_caracteres_y_no_como_sus_10() -> None:
    assert mensaje.LARGO_ENLACE_WHATSAPP == 26 == len("https://wa.me/+51900000123")
    assert mensaje.largo_del_mensaje("[whatsapp]") == 26
    assert mensaje.largo_del_mensaje("a[whatsapp]b[whatsapp]") == 2 + 2 * 26


def test_un_texto_con_whatsapp_que_contado_como_26_pasa_el_tope_por_uno_se_rechaza() -> None:
    cabe = "a" * 74 + "[whatsapp]"  # 84 literales, 100 contados
    se_pasa = "a" * 75 + "[whatsapp]"  # 85 literales, 101 contados

    mensaje.validar_largo(cabe, 100)
    error = error_de(mensaje.validar_largo, se_pasa, 100)

    assert len(se_pasa) < 100  # por sus caracteres literales cabria de sobra
    assert error.parametros == {"largo": 101, "maximo": 100}


def test_el_largo_de_un_texto_sin_whatsapp_es_su_largo() -> None:
    assert mensaje.largo_del_mensaje("Hola [$MACRO1$] ñandú") == len("Hola [$MACRO1$] ñandú")


# --- Vista (RF-WM-27) -------------------------------------------------------------------------


def test_la_vista_reemplaza_las_macros_con_los_valores_de_la_fila() -> None:
    texto = "Hola [$MACRO1$], tu cuota vence el [$MACRO2$] ([$MACRO3$])."

    assert mensaje.vista(texto, ["Ana", "15/10/2026", "1,234.50"]) == (
        "Hola Ana, tu cuota vence el 15/10/2026 (1,234.50)."
    )


def test_una_macro_repetida_se_reemplaza_en_cada_lugar() -> None:
    assert mensaje.vista("[$MACRO1$] y [$MACRO1$]", ["Ana"]) == "Ana y Ana"


def test_una_macro_vacia_se_reemplaza_por_nada() -> None:
    assert mensaje.vista("Hola [$MACRO1$]|", [None]) == "Hola |"
    assert mensaje.vista("Hola [$MACRO1$]|", [""]) == "Hola |"


def test_una_macro_que_la_fila_no_tiene_se_deja_tal_cual() -> None:
    assert (
        mensaje.vista("[$MACRO1$] [$MACRO3$] [$MACRO0$]", ["Ana", "x"])
        == "Ana [$MACRO3$] [$MACRO0$]"
    )


def test_la_vista_reemplaza_whatsapp_por_el_enlace_con_el_numero() -> None:
    assert mensaje.vista("INFO por [whatsapp]", [], "900000123") == (
        "INFO por https://wa.me/+51900000123"
    )
    assert mensaje.enlace_whatsapp("900000123") == "https://wa.me/+51900000123"


@pytest.mark.parametrize("numero", [None, ""])
def test_sin_numero_whatsapp_queda_tal_cual(numero) -> None:
    assert mensaje.vista("INFO por [whatsapp] y [$MACRO1$]", ["Ana"], numero) == (
        "INFO por [whatsapp] y Ana"
    )


def test_el_valor_de_una_macro_no_se_vuelve_a_interpretar() -> None:
    # Un valor que parece un marcador no se reemplaza otra vez.
    assert mensaje.vista("[$MACRO1$]", ["[$MACRO2$]", "x"]) == "[$MACRO2$]"
    assert mensaje.vista("[$MACRO1$]", ["[whatsapp]"], "900000123") == "[whatsapp]"


# --- El contexto de textos guardados ----------------------------------------------------------


def test_el_contexto_es_de_texto_plano_con_su_clave() -> None:
    contexto = contexto_mensaje(lambda: 4096)

    assert contexto.clave == "whatsmkt.mensaje"
    assert contexto.tipo.value == "texto_plano"


def test_el_validador_del_contexto_aplica_las_reglas_del_mensaje_con_el_tope_que_se_le_da() -> None:
    validar = contexto_mensaje(lambda: 4096).validar

    assert validar({"texto": "Hola [$MACRO1$]"}) == ()
    assert validar({"texto": "a" * 4096}) == ()
    [largo] = validar({"texto": "a" * 4097})
    assert largo.codigo is CodigoTexto.REGLA_DEL_CONTEXTO
    assert largo.codigo_contexto == "mensaje_largo"
    assert dict(largo.parametros) == {"largo": 4097, "maximo": 4096}
    [emoji] = validar({"texto": "Hola 😀"})
    assert emoji.codigo_contexto == "mensaje_con_emoji"
    assert dict(emoji.parametros) == {"caracter": "😀", "posicion": 6}
    # Lo que no es del modulo sigue siendo el problema generico del contexto de texto plano.
    for malo in ({"texto": "   "}, {"texto": 5}, {"otro": "x"}):
        [problema] = validar(malo)
        assert problema.codigo is CodigoTexto.TEXTO_GUARDADO_INVALIDO


def test_el_tope_se_lee_en_cada_validacion() -> None:
    tope = [10]
    validar = contexto_mensaje(lambda: tope[0]).validar

    assert validar({"texto": "a" * 20}) != ()
    tope[0] = 20
    assert validar({"texto": "a" * 20}) == ()

"""GSM-7 en el motor (RF-MM-27, B16): `a_gsm7`, `largo_gsm7` y `caracteres_borrados`.

Un caso por signo de la tabla de transliteracion, el emoji borrado, un extendido conservado que
cuenta 2 y el salto de linea; despues propiedades con semilla fija (el proyecto no usa Hypothesis:
`random.Random` y una semilla, para que una falla se reproduzca igual). Datos sinteticos.
"""

import random
import unicodedata
from datetime import date

import pytest

from app.core.entities.texto_enriquecido import (
    Expresion,
    LlamadaFuncion,
    NodoTexto,
    NodoVariable,
    TipoValor,
)
from app.core.services.plataformas.mowa_mes.conciliacion import normalizar_mensaje
from app.core.services.texto_enriquecido import evaluador
from app.core.services.texto_enriquecido.funciones import REGISTRO
from app.core.services.texto_enriquecido.gsm7 import (
    CARACTERES_GSM7,
    EXTENDIDOS,
    TOPE_DE_CACHE,
    TRANSLITERACION,
    a_gsm7,
    caracteres_borrados,
    largo_gsm7,
    largo_gsm7_normalizado,
)

SEMILLA = 20261019
T, F = TipoValor.TEXTO, TipoValor.FECHA


# --- La tabla ---------------------------------------------------------------------------------


def test_la_tabla_tiene_127_caracteres_basicos_y_10_extendidos_sin_repetir() -> None:
    basicos = CARACTERES_GSM7 - set(EXTENDIDOS)

    assert (len(basicos), len(EXTENDIDOS), len(set(EXTENDIDOS))) == (127, 10, 10)
    assert set(EXTENDIDOS) == set("\f^{}\\[~]|€")
    assert "\n" in basicos and "\r" in basicos  # los saltos de linea son del alfabeto basico


def test_la_transliteracion_solo_usa_signos_que_gsm7_no_tiene_y_da_caracteres_de_gsm7() -> None:
    for signo, equivalente in TRANSLITERACION.items():
        assert signo not in CARACTERES_GSM7, signo
        assert equivalente and all(c in CARACTERES_GSM7 for c in equivalente), signo


def test_ninguna_descomposicion_nfd_produce_un_signo_de_la_tabla() -> None:
    # Por eso transliterar antes o despues de quitar los diacriticos da lo mismo: la tabla y las
    # marcas nunca se cruzan (se comprobo sobre todo Unicode al escribir la funcion).
    for codigo in range(0x110000):
        if 0xD800 <= codigo <= 0xDFFF:
            continue
        caracter = chr(codigo)
        if caracter not in TRANSLITERACION:
            assert not set(unicodedata.normalize("NFD", caracter)) & set(TRANSLITERACION)


# --- a_gsm7: un caso por paso -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("ñ", "n"),
        ("Ñ", "N"),
        ("ü", "u"),
        ("é", "e"),  # esta en GSM-7, pero el primer paso quita la marca (igual que la conciliacion)
        ("Ç", "C"),
        ("Peña Núñez", "Pena Nunez"),
        ("e\u0301", "e"),  # la tilde suelta (descompuesta) tambien
        ("ø Ø æ Æ ß", "ø Ø æ Æ ß"),  # no se descomponen y son de GSM-7: se conservan
    ],
)
def test_quita_los_diacriticos(entrada, esperado) -> None:
    assert a_gsm7(entrada) == esperado


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("\u201chola\u201d", '"hola"'),  # “ ”
        ("\u00abhola\u00bb", '"hola"'),  # « »
        ("\u2018hola\u2019", "'hola'"),  # ‘ ’
        ("espera\u2026", "espera..."),  # …
        ("2020\u20132021", "2020-2021"),  # –
        ("si\u2014no", "si-no"),  # —
        ("N\u00b0 5", "No 5"),  # °
        ("Nº 5", "No 5"),  # º
        ("1ª cuota", "1a cuota"),  # ª
        ("N\u00b0", "No"),
        ("don\u2019t", "don't"),
    ],
)
def test_translitera_los_signos_con_equivalente_simple(entrada, esperado) -> None:
    assert a_gsm7(entrada) == esperado


def test_hay_un_caso_para_cada_signo_de_la_tabla() -> None:
    probados = {"\u201c", "\u201d", "\u00ab", "\u00bb", "\u2018", "\u2019", "\u2026"}
    probados |= {"\u2013", "\u2014", "\u00b0", "º", "ª"}

    assert probados == set(TRANSLITERACION)


def test_la_transliteracion_puede_alargar_el_texto() -> None:
    assert (len("\u2026"), len(a_gsm7("\u2026")), largo_gsm7(a_gsm7("\u2026"))) == (1, 3, 3)


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("hola \U0001f600", "hola "),  # un emoji se borra
        ("a\U0001f468\u200d\U0001f469b", "ab"),  # una secuencia de emoji, con su unidor
        ("a`b", "ab"),  # la comilla inversa tampoco
        ("a\x0bb", "ab"),  # la tabulacion vertical: sin equivalente decidido
        ("a\u2028b", "ab"),  # separador de linea (Zl)
        ("a\u2029b", "ab"),  # separador de parrafo (Zp)
        ("\u0439", ""),  # una letra cirilica
        ("\uac01", ""),  # una silaba hangul (su NFD son jamo)
        ("a\x00b\x07c", "abc"),  # controles
    ],
)
def test_borra_lo_que_queda_fuera_de_gsm7(entrada, esperado) -> None:
    assert a_gsm7(entrada) == esperado


@pytest.mark.parametrize("extendido", list(EXTENDIDOS))
def test_conserva_cada_extendido_y_cada_uno_cuenta_2(extendido) -> None:
    texto = f"a{extendido}b"

    assert a_gsm7(texto) == texto
    assert largo_gsm7(texto) == 4  # 1 + 2 + 1


def test_conserva_los_saltos_de_linea() -> None:
    texto = "linea 1\nlinea 2\r\nlinea 3"

    assert a_gsm7(texto) == texto
    assert largo_gsm7(texto) == len(texto)  # \n y \r son basicos: cuentan 1


def test_un_texto_solo_ascii_de_gsm7_no_cambia_y_el_ascii_fuera_se_borra() -> None:
    assert (
        a_gsm7("Hola, mundo 123 @_$#%&'()*+,-./:;<=>?") == "Hola, mundo 123 @_$#%&'()*+,-./:;<=>?"
    )
    assert a_gsm7("a\x1fb\x7fc") == "abc"
    assert a_gsm7("") == ""


# --- largo_gsm7 -------------------------------------------------------------------------------


def test_largo_gsm7_cuenta_2_por_cada_extendido_y_1_por_el_resto() -> None:
    assert largo_gsm7("") == 0
    assert largo_gsm7("hola") == 4
    assert largo_gsm7("€") == 2  # €
    assert largo_gsm7("100€ [x]") == 3 + 2 + 1 + 2 + 1 + 2  # € , [ y ] cuentan 2
    assert largo_gsm7("\f") == 2
    assert largo_gsm7("{}") == 4


def test_largo_gsm7_normalizado_mide_lo_que_saldria() -> None:
    assert (
        largo_gsm7_normalizado("N\u00b0 5\u2026 € \U0001f600") == 10 + 1
    )  # «No 5... € »: 10 caracteres y el euro cuenta 2
    assert largo_gsm7_normalizado("hola") == largo_gsm7("hola")


# --- caracteres_borrados -----------------------------------------------------------------------


def test_los_caracteres_borrados_van_sin_repetir_y_en_orden_de_aparicion() -> None:
    texto = "b\U0001f600a\U0001f680\U0001f600\u0439b\U0001f680\x0b"

    assert caracteres_borrados(texto) == ("\U0001f600", "\U0001f680", "\u0439", "\x0b")


def test_lo_transliterado_y_los_diacriticos_no_cuentan_como_borrados() -> None:
    texto = "Cuota N\u00b0 5\u2026 \u201chola\u201d \u2014 peña áéí e\u0301 €"

    assert caracteres_borrados(texto) == ()


def test_se_informa_el_caracter_tal_como_aparece_y_no_su_base() -> None:
    assert caracteres_borrados("\u0439") == ("\u0439",)  # й, no la и que queda al quitarle la breve
    assert caracteres_borrados("\uac01") == ("\uac01",)


def test_lo_borrado_es_justo_lo_que_a_gsm7_pierde() -> None:
    texto = "a\U0001f600ñ\u2026\x0b\u0439"

    quitados = caracteres_borrados(texto)

    assert a_gsm7(texto) == "an...", quitados
    assert quitados == ("\U0001f600", "\x0b", "\u0439")


# --- la funcion del motor ----------------------------------------------------------------------


def test_a_gsm7_esta_en_el_registro_en_la_familia_texto() -> None:
    funcion = REGISTRO["a_gsm7"]

    assert funcion.familia == "texto"
    assert (funcion.recibe, funcion.devuelve) == ((T,), T)
    assert funcion.parametros == ()
    assert funcion.clave_nombre == "textoEnriquecido.funcion.a_gsm7.nombre"


def _compilar(*nodos, **extra):
    return evaluador.compilar(Expresion(tuple(nodos)), {"t": T, "f": F}, **extra)


def _a_gsm7(nodo: str = "t", *antes: LlamadaFuncion) -> NodoVariable:
    return NodoVariable(nodo, (*antes, LlamadaFuncion("a_gsm7")))


def test_a_gsm7_se_aplica_desde_la_expresion() -> None:
    compilada = _compilar(NodoTexto("N: "), _a_gsm7())

    assert compilada.evaluar({"t": "Peña\u2019s \U0001f600"}).texto == "N: Pena's "


# --- la cota -----------------------------------------------------------------------------------


def test_la_cota_de_a_gsm7_es_el_triple_porque_el_peor_caso_es_la_elipsis() -> None:
    corta = _compilar(_a_gsm7("t", LlamadaFuncion("primeros", (8,))))
    sin_recorte = _compilar(_a_gsm7())

    assert corta.cota == 3 * 8  # un tope verdadero, en caracteres y en unidades GSM-7
    assert sin_recorte.cota is None  # una variable sin recorte no tiene cota, como antes
    peor = corta.evaluar({"t": "\u2026" * 8}).texto
    assert (len(peor), largo_gsm7(peor)) == (24, 24)  # el peor caso llega justo a la cota
    assert largo_gsm7(corta.evaluar({"t": "\u20ac" * 8}).texto) == 16  # un extendido, 2 por 1


def test_con_a_gsm7_en_la_variable_la_cota_es_un_tope_verdadero_en_caracteres_y_unidades() -> None:
    azar = random.Random(SEMILLA + 9)

    for _ in range(2000):
        n = azar.randint(1, 12)
        compilada = _compilar(_a_gsm7("t", LlamadaFuncion("primeros", (n,))))
        texto = compilada.evaluar({"t": _texto(azar, ALFABETO_RICO, 30) or "x"}).texto

        assert len(texto) <= compilada.cota and largo_gsm7(texto) <= compilada.cota, (n, texto)


def test_el_texto_fijo_se_mide_en_unidades_gsm7_si_el_conector_lo_pide() -> None:
    fijo = "Cuota N\u00b0 5\u2026 €"
    por_defecto = _compilar(NodoTexto(fijo))
    en_gsm7 = _compilar(NodoTexto(fijo), medida=largo_gsm7_normalizado)

    assert por_defecto.cota == len(fijo) == 13  # como siempre: caracteres
    # «Cuota No 5... €»: 15 caracteres y el € cuenta 2
    assert en_gsm7.cota == len(a_gsm7(fijo)) + 1 == 16


def test_la_cota_de_un_texto_fijo_ya_normalizado_es_exactamente_su_largo_gsm7() -> None:
    fijo = a_gsm7("Pago de 100€ [ya]\u2026")
    compilada = _compilar(NodoTexto(fijo), medida=largo_gsm7_normalizado)

    assert compilada.cota == largo_gsm7(fijo)
    assert compilada.evaluar({}).texto == fijo


def test_el_supuesto_de_1_por_caracter_es_de_quien_normaliza_el_texto_ya_evaluado() -> None:
    # El camino de MOWA MES: la variable va cruda, la cota cuenta 8 y la normalizacion se aplica al
    # texto evaluado. Un dato con un extendido puede pasarla; el control exacto es el de cada fila.
    compilada = _compilar(NodoVariable("t", (LlamadaFuncion("primeros", (8,)),)))

    mensaje = a_gsm7(compilada.evaluar({"t": "\u20ac" * 8}).texto)

    assert (compilada.cota, largo_gsm7(mensaje)) == (8, 16)


# --- Propiedades con semilla -------------------------------------------------------------------

_LETRAS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789.,;:-/'\"()#%&*+=<>?!@_$"
_CON_TILDE = "áéíóúüñÁÉÍÓÚÜÑàèìòùâêîôûãõçÇäöÄÖåÅ"
_SIGNOS = "".join(TRANSLITERACION)
_FUERA = "\U0001f600\U0001f680\u0439\u00a0\t\u200d`\x01\u03b1\uac01\u4e2d\x0b\u2028\u2029 \u2009"
_COMBINANTES = "\u0301\u0308\u0323\u0327\u0303"
_EXTENDIDOS_Y_ALARGAN = EXTENDIDOS + "\u2026"
ALFABETO_RICO = list(_LETRAS + _CON_TILDE + _SIGNOS + _FUERA + _COMBINANTES + EXTENDIDOS + "\n\r")
# Lo que NO alarga: sin extendidos (cuentan 2) y sin `…` (pasa a 3). Es la hipotesis del supuesto.
ALFABETO_SIN_ALARGAR = [c for c in ALFABETO_RICO if c not in _EXTENDIDOS_Y_ALARGAN]


def _texto(azar: random.Random, alfabeto: list[str], maximo: int = 40) -> str:
    return "".join(azar.choice(alfabeto) for _ in range(azar.randint(0, maximo)))


def test_es_idempotente() -> None:
    azar = random.Random(SEMILLA)

    for _ in range(3000):
        texto = _texto(azar, ALFABETO_RICO)
        una_vez = a_gsm7(texto)
        assert a_gsm7(una_vez) == una_vez, repr(texto)


def test_la_salida_siempre_esta_dentro_de_gsm7() -> None:
    azar = random.Random(SEMILLA + 1)

    for _ in range(3000):
        texto = _texto(azar, ALFABETO_RICO)
        assert set(a_gsm7(texto)) <= CARACTERES_GSM7, repr(texto)


def test_el_largo_de_la_salida_nunca_pasa_de_3_veces_el_de_la_entrada() -> None:
    # El peor caso es `…` (1 caracter, 3 unidades). No es `2 * len`: esa cota no vale con `…`.
    azar = random.Random(SEMILLA + 2)

    for _ in range(3000):
        texto = _texto(azar, ALFABETO_RICO)
        assert largo_gsm7(a_gsm7(texto)) <= 3 * len(texto), repr(texto)
    assert largo_gsm7(a_gsm7("\u2026")) == 3


def test_aplicarla_a_cada_pieza_da_lo_mismo_que_al_texto_entero() -> None:
    azar = random.Random(SEMILLA + 3)

    for _ in range(3000):
        texto = _texto(azar, ALFABETO_RICO, 60)
        cortes = sorted(azar.randint(0, len(texto)) for _ in range(azar.randint(1, 4)))
        piezas = [texto[a:b] for a, b in zip([0, *cortes], [*cortes, len(texto)], strict=True)]
        assert "".join(a_gsm7(p) for p in piezas) == a_gsm7(texto), repr(piezas)


def test_borrados_sin_repetir_y_es_justo_lo_que_se_pierde() -> None:
    azar = random.Random(SEMILLA + 4)

    for _ in range(2000):
        texto = _texto(azar, ALFABETO_RICO)
        borrados = caracteres_borrados(texto)
        assert len(set(borrados)) == len(borrados)
        assert all(c in texto for c in borrados)
        # sin lo borrado, ni los diacriticos ni lo transliterado se pierden: lo que queda es igual
        sin_borrados = "".join(c for c in texto if c not in borrados)
        assert a_gsm7(sin_borrados) == a_gsm7(texto), repr(texto)
        if not borrados:
            assert a_gsm7(texto) == a_gsm7(sin_borrados)


def test_coincide_con_la_normalizacion_de_la_conciliacion_en_los_diacriticos() -> None:
    # Misma regla que `normalizar_mensaje` (NFD sin marcas): lo ya normalizado a GSM-7 es estable
    # para la conciliacion, que lo vuelve a normalizar sin cambiar nada (salvo el strip).
    azar = random.Random(SEMILLA + 5)

    for _ in range(2000):
        texto = _texto(azar, ALFABETO_RICO)
        normalizado = a_gsm7(texto)
        assert normalizar_mensaje(normalizado) == normalizado.strip(), repr(texto)


def _expresion_de_un_mensaje(parte_1: str, parte_2: str, por_pieza: bool) -> Expresion:
    """Como armara MOWA MES un segmento: titular de 8, parte 1, fecha y parte 2."""
    funciones = (LlamadaFuncion("primeros", (8,)),)
    fecha = (LlamadaFuncion("formato_fecha", ("dd/mm/aaaa",)),)
    if por_pieza:
        return Expresion(
            (
                NodoVariable("t", (*funciones, LlamadaFuncion("a_gsm7"))),
                NodoTexto(a_gsm7(parte_1)),
                NodoVariable("f", fecha),
                NodoTexto(a_gsm7(parte_2)),
            )
        )
    return Expresion(
        (
            NodoVariable("t", funciones),
            NodoTexto(parte_1),
            NodoVariable("f", fecha),
            NodoTexto(parte_2),
        )
    )


def test_normalizar_por_pieza_tras_primeros_8_es_igual_que_normalizar_el_segmento() -> None:
    azar = random.Random(SEMILLA + 6)
    variables = {"t": T, "f": F}

    for _ in range(1500):
        titular = _texto(azar, ALFABETO_RICO, 20) or "x"
        parte_1, parte_2 = _texto(azar, ALFABETO_RICO, 40), _texto(azar, ALFABETO_RICO, 40)
        fila = {"t": titular, "f": date(2026, 9, 5)}
        por_pieza = evaluador.compilar(_expresion_de_un_mensaje(parte_1, parte_2, True), variables)
        entero = evaluador.compilar(_expresion_de_un_mensaje(parte_1, parte_2, False), variables)

        assert por_pieza.evaluar(fila).texto == a_gsm7(entero.evaluar(fila).texto), (
            titular,
            parte_1,
            parte_2,
        )


def test_con_variables_sin_extendidos_el_mensaje_normalizado_no_pasa_de_la_cota() -> None:
    # El camino de MOWA MES: medida=largo_gsm7_normalizado, se evalua cruda y se normaliza el texto.
    azar = random.Random(SEMILLA + 7)
    variables = {"t": T, "f": F}

    for _ in range(1500):
        parte_1, parte_2 = _texto(azar, ALFABETO_RICO, 40), _texto(azar, ALFABETO_RICO, 40)
        compilada = evaluador.compilar(
            _expresion_de_un_mensaje(parte_1, parte_2, False),
            variables,
            medida=largo_gsm7_normalizado,
        )
        titular = _texto(azar, ALFABETO_SIN_ALARGAR, 20) or "x"
        mensaje = a_gsm7(compilada.evaluar({"t": titular, "f": date(2026, 9, 5)}).texto)

        assert compilada.cota is not None
        assert largo_gsm7(mensaje) <= compilada.cota, (titular, parte_1, parte_2)


def test_sin_variables_la_cota_es_exactamente_el_largo_gsm7_del_mensaje_normalizado() -> None:
    azar = random.Random(SEMILLA + 8)

    for _ in range(1500):
        fijo = _texto(azar, ALFABETO_RICO, 60)
        compilada = evaluador.compilar(
            Expresion((NodoTexto(fijo),)), {}, medida=largo_gsm7_normalizado
        )

        assert compilada.cota == largo_gsm7(a_gsm7(compilada.evaluar({}).texto))


def test_el_largo_en_caracteres_y_en_unidades_de_la_salida_nunca_pasa_del_triple() -> None:
    azar = random.Random(SEMILLA + 10)

    for _ in range(3000):
        texto = _texto(azar, ALFABETO_RICO)
        salida = a_gsm7(texto)
        assert len(salida) <= 3 * len(texto) and largo_gsm7(salida) <= 3 * len(texto), repr(texto)


# --- Espacios especiales y tabulacion: un espacio normal (decision del usuario, 2026-10-20) -------

ESPACIOS = [
    ("\u00a0", "espacio duro"),
    ("\u2009", "espacio fino"),
    ("\u202f", "espacio duro angosto"),
    ("\u3000", "espacio ideografico"),
    ("\u2002", "espacio en"),
    ("\u2007", "espacio de cifras"),
    ("\u205f", "espacio medio matematico"),
    ("\u1680", "marca de espacio ogham"),
    ("\t", "tabulacion"),
]


@pytest.mark.parametrize(("espacio", "nombre"), ESPACIOS, ids=[n for _, n in ESPACIOS])
def test_los_espacios_especiales_y_la_tabulacion_pasan_a_un_espacio_normal(espacio, nombre) -> None:
    assert a_gsm7(f"a{espacio}b") == "a b", nombre
    assert caracteres_borrados(f"a{espacio}b") == ()  # no se pierde nada
    assert len(a_gsm7(f"a{espacio}b")) == 3  # y el largo no cambia
    assert largo_gsm7(a_gsm7(espacio)) == 1


def test_un_nombre_con_espacio_duro_no_queda_pegado() -> None:
    assert a_gsm7("Ana\u00a0Ruiz") == "Ana Ruiz"
    assert a_gsm7("Ana\u00a0\u00a0Ruiz") == "Ana  Ruiz"  # uno por uno, sin colapsar


def test_todos_los_espacios_de_unicode_distintos_del_normal_pasan_a_un_espacio() -> None:
    zs = [chr(c) for c in range(0x110000) if unicodedata.category(chr(c)) == "Zs" and chr(c) != " "]

    assert len(zs) >= 7  # el espacio duro, el fino, U+202F, U+3000...
    for espacio in zs:
        assert a_gsm7(espacio) == " ", hex(ord(espacio))
        assert caracteres_borrados(espacio) == (), hex(ord(espacio))


def test_los_separadores_de_linea_y_de_parrafo_y_la_tabulacion_vertical_se_siguen_borrando() -> (
    None
):
    assert a_gsm7("a\u2028b\u2029c\x0bd") == "abcd"
    assert caracteres_borrados("a\u2028b\u2029c\x0bd") == ("\u2028", "\u2029", "\x0b")


def test_el_espacio_normal_y_los_saltos_de_linea_no_se_tocan() -> None:
    assert a_gsm7("a b\nc\rd\fe") == "a b\nc\rd\fe"


def test_el_espacio_duro_en_los_extremos_queda_como_espacio_y_la_conciliacion_lo_recorta() -> None:
    mensaje = a_gsm7("\u00a0Hola\u00a0")

    assert mensaje == " Hola "
    assert normalizar_mensaje(mensaje) == normalizar_mensaje("Hola")  # lo mismo que MES devuelve


# --- Las caches tienen tope ---------------------------------------------------------------------


def test_las_caches_no_crecen_sin_limite_con_miles_de_caracteres_distintos() -> None:
    from app.core.services.texto_enriquecido import gsm7

    distintos = "".join(chr(c) for c in range(0x4E00, 0x4E00 + 3 * TOPE_DE_CACHE))  # CJK

    assert a_gsm7(distintos) == ""  # todo se borra
    assert gsm7._caracter.cache_info().currsize <= TOPE_DE_CACHE
    assert len(gsm7._TABLA) <= TOPE_DE_CACHE
    assert gsm7._caracter.cache_info().maxsize == TOPE_DE_CACHE


def test_la_tabla_guarda_lo_que_ya_normalizo_mientras_haya_lugar() -> None:
    from app.core.services.texto_enriquecido import gsm7

    gsm7._TABLA.clear()
    gsm7._caracter.cache_clear()

    a_gsm7("áñ\u2026")

    assert {ord("á"), ord("ñ"), ord("\u2026")} <= set(gsm7._TABLA)
    assert gsm7._caracter.cache_info().currsize == 3


def test_pasado_el_tope_se_sigue_normalizando_bien() -> None:
    from app.core.services.texto_enriquecido import gsm7

    a_gsm7("".join(chr(c) for c in range(0x4E00, 0x4E00 + 3 * TOPE_DE_CACHE)))  # llena las dos

    texto = "Peña\u00a0N\u00b0 5\u2026 \u01d8 \U0001f600€"
    assert a_gsm7(texto) == "Pena No 5... u €"
    assert caracteres_borrados(texto) == ("\U0001f600",)
    assert len(gsm7._TABLA) <= TOPE_DE_CACHE

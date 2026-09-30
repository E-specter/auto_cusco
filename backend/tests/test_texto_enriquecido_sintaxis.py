"""Sintaxis de texto del motor de texto enriquecido: `[@campo | funcion(args)]` (D9)."""

import time
from decimal import Decimal

import pytest

from app.core.entities.texto_enriquecido import (
    ArgumentoVariable,
    CodigoTexto,
    Expresion,
    ExpresionInvalida,
    ExpresionNoEscribible,
    LimitesExpresion,
    LlamadaFuncion,
    NodoTexto,
    NodoVariable,
)
from app.core.services.texto_enriquecido import sintaxis


def _codigo(texto: str) -> CodigoTexto:
    with pytest.raises(ExpresionInvalida) as error:
        sintaxis.leer(texto)
    return error.value.problemas[0].codigo


def test_un_texto_sin_referencias_es_un_solo_nodo_texto() -> None:
    assert sintaxis.leer("1010") == Expresion((NodoTexto("1010"),))


def test_un_texto_vacio_no_tiene_nodos() -> None:
    assert sintaxis.leer("") == Expresion(())


def test_una_referencia_simple_es_una_variable_sin_funciones() -> None:
    assert sintaxis.leer("[@telefono]") == Expresion((NodoVariable("telefono"),))


def test_texto_y_referencias_se_alternan_en_orden() -> None:
    expresion = sintaxis.leer("documento=[@documento_numero]; pagare=[@pagare]")

    assert expresion == Expresion(
        (
            NodoTexto("documento="),
            NodoVariable("documento_numero"),
            NodoTexto("; pagare="),
            NodoVariable("pagare"),
        )
    )


def test_los_espacios_dentro_de_la_referencia_no_cuentan() -> None:
    assert sintaxis.leer("[@ campo ]") == sintaxis.leer("[@campo]")
    assert sintaxis.leer("[@\tcampo\n]") == sintaxis.leer("[@campo]")


def test_la_tuberia_encadena_funciones_con_argumentos() -> None:
    expresion = sintaxis.leer('[@fecha | sumar_dias(3) | formato_fecha("dd/mm/aaaa") | mayusculas]')

    assert expresion == Expresion(
        (
            NodoVariable(
                "fecha",
                (
                    LlamadaFuncion("sumar_dias", (3,)),
                    LlamadaFuncion("formato_fecha", ("dd/mm/aaaa",)),
                    LlamadaFuncion("mayusculas"),
                ),
            ),
        )
    )


def test_los_argumentos_son_numero_texto_o_variable() -> None:
    expresion = sintaxis.leer('[@x | f(-2, 2.50, "a", @otra)]')

    assert expresion.nodos[0].funciones[0].args == (
        -2,
        Decimal("2.50"),
        "a",
        ArgumentoVariable("otra"),
    )


def test_los_parentesis_vacios_son_lo_mismo_que_sin_parentesis() -> None:
    assert sintaxis.leer("[@x | recortar()]") == sintaxis.leer("[@x | recortar]")


def test_un_argumento_entre_comillas_puede_llevar_corchete_y_tuberia() -> None:
    expresion = sintaxis.leer('[@x | reemplazar("]", "|") | reemplazar("[@", "a\\"b\\\\c")]')

    llamadas = expresion.nodos[0].funciones
    assert llamadas[0].args == ("]", "|")
    assert llamadas[1].args == ("[@", 'a"b\\c')


def test_un_argumento_entre_comillas_conserva_saltos_de_linea() -> None:
    expresion = sintaxis.leer('[@x | reemplazar(" ", "\n")]')

    assert expresion.nodos[0].funciones[0].args == (" ", "\n")


def test_la_apertura_escapada_es_un_arroba_literal() -> None:
    assert sintaxis.leer("a[@@]b") == Expresion((NodoTexto("a[@b"),))
    assert sintaxis.leer("[@@][@campo]") == Expresion((NodoTexto("[@"), NodoVariable("campo")))


def test_los_corchetes_y_arrobas_sueltos_son_texto() -> None:
    assert sintaxis.leer("a [b] @c ] [") == Expresion((NodoTexto("a [b] @c ] ["),))


def test_una_barra_invertida_delante_de_una_referencia_no_escapa_nada() -> None:
    # Compatibilidad con RF-12: hoy `C:\[@campo]` es "C:\" mas el campo.
    assert sintaxis.leer("C:\\[@campo]") == Expresion((NodoTexto("C:\\"), NodoVariable("campo")))


@pytest.mark.parametrize(
    ("texto", "codigo"),
    [
        ("[@]", CodigoTexto.REFERENCIA_VACIA),
        ("[@   ]", CodigoTexto.REFERENCIA_VACIA),
        ("[@ | f]", CodigoTexto.REFERENCIA_VACIA),
        ("51[@telefono", CodigoTexto.SINTAXIS_INVALIDA),
        ("[@a[@b]", CodigoTexto.SINTAXIS_INVALIDA),
        ("[@a b]", CodigoTexto.SINTAXIS_INVALIDA),
        ("[@a |]", CodigoTexto.SINTAXIS_INVALIDA),
        ("[@a | 3f]", CodigoTexto.SINTAXIS_INVALIDA),
        ("[@a | f(]", CodigoTexto.SINTAXIS_INVALIDA),
        ("[@a | f(1,)]", CodigoTexto.SINTAXIS_INVALIDA),
        ("[@a | f(1 2)]", CodigoTexto.SINTAXIS_INVALIDA),
        ('[@a | f("sin cerrar)]', CodigoTexto.SINTAXIS_INVALIDA),
        ('[@a | f("\\n")]', CodigoTexto.SINTAXIS_INVALIDA),
        ("[@a | f(@)]", CodigoTexto.SINTAXIS_INVALIDA),
        ("[@a | f(1.)]", CodigoTexto.SINTAXIS_INVALIDA),
        ("[@a | f(abc)]", CodigoTexto.SINTAXIS_INVALIDA),
        ("[@a | f(1)x]", CodigoTexto.SINTAXIS_INVALIDA),
    ],
)
def test_los_textos_mal_escritos_se_rechazan_con_su_codigo(texto, codigo) -> None:
    assert _codigo(texto) is codigo


def test_el_problema_de_sintaxis_dice_en_que_posicion_esta() -> None:
    with pytest.raises(ExpresionInvalida) as error:
        sintaxis.leer("abc [@a b]")

    assert "posicion 8" in error.value.problemas[0].detalle


def test_los_limites_se_rechazan_al_leer_sin_construir_todo() -> None:
    limites = LimitesExpresion(nodos=3, funciones_por_nodo=2, largo_literal=5)

    with pytest.raises(ExpresionInvalida) as nodos:
        sintaxis.leer("[@a][@a][@a][@a]", limites)
    with pytest.raises(ExpresionInvalida) as funciones:
        sintaxis.leer("[@a|f|f|f]", limites)
    with pytest.raises(ExpresionInvalida) as literal:
        sintaxis.leer("abcdef", limites)
    with pytest.raises(ExpresionInvalida) as argumento:
        sintaxis.leer('[@a|f("abcdef")]', limites)

    for error in (nodos, funciones, literal, argumento):
        assert error.value.problemas[0].codigo is CodigoTexto.LIMITE_EXCEDIDO


def test_escribir_produce_la_forma_canonica() -> None:
    expresion = Expresion(
        (
            NodoTexto("a[@b"),
            NodoVariable(
                "x", (LlamadaFuncion("f", (1, Decimal("2.50"), 'q"\\', ArgumentoVariable("v"))),)
            ),
            NodoVariable("y", (LlamadaFuncion("recortar"),)),
        )
    )

    assert sintaxis.escribir(expresion) == 'a[@@]b[@x | f(1, 2.50, "q\\"\\\\", @v)][@y | recortar]'


@pytest.mark.parametrize(
    "texto",
    [
        "",
        "1010",
        "[@telefono]",
        "51[@telefono]",
        "[@a | f]",
        '[@a | f(1) | g("x", @y)]',
        "[@@]",
        "x[@@]y[@@]",
        "[@@][@a]",
        "]]][@a]",
    ],
)
def test_ida_y_vuelta_de_textos_canonicos(texto) -> None:
    assert sintaxis.escribir(sintaxis.leer(texto)) == texto


def test_escribir_de_un_texto_no_canonico_lo_normaliza_sin_cambiar_la_expresion() -> None:
    original = sintaxis.leer('[@ a |  f( 1 ,"x" ) ]')

    escrito = sintaxis.escribir(original)

    assert escrito == '[@a | f(1, "x")]'
    assert sintaxis.leer(escrito) == original


def test_los_nodos_texto_contiguos_se_escriben_como_uno_y_se_leen_igual_de_juntos() -> None:
    expresion = Expresion((NodoTexto("a"), NodoTexto("b")))

    assert sintaxis.escribir(expresion) == "ab"
    assert sintaxis.leer("ab") == Expresion((NodoTexto("ab"),))


@pytest.mark.parametrize(
    "expresion",
    [
        Expresion((NodoVariable("x", obligatoria=True),)),
        Expresion((NodoVariable("con espacio"),)),
        Expresion((NodoVariable("con|tuberia"),)),
        Expresion((NodoVariable("con]"),)),
        Expresion((NodoVariable(""),)),
        Expresion((NodoVariable("x", (LlamadaFuncion("no valida"),)),)),
        Expresion((NodoVariable("x", (LlamadaFuncion("f", (Decimal("NaN"),)),)),)),
        Expresion((NodoVariable("x", (LlamadaFuncion("f", (ArgumentoVariable("a b"),)),)),)),
    ],
)
def test_lo_que_no_se_puede_escribir_como_texto_se_informa(expresion) -> None:
    with pytest.raises(ExpresionNoEscribible) as error:
        sintaxis.escribir(expresion)

    assert error.value.problema.codigo is CodigoTexto.NO_SE_PUEDE_ESCRIBIR_COMO_TEXTO


def test_un_decimal_con_exponente_se_escribe_sin_exponente() -> None:
    expresion = Expresion((NodoVariable("x", (LlamadaFuncion("f", (Decimal("1E+2"),)),)),))

    assert sintaxis.escribir(expresion) == "[@x | f(100)]"


# --- Entradas largas y maliciosas: el analizador es lineal (no hay regex con backtracking) ---

ENTRADAS_MALICIOSAS = {
    "aperturas": "[@" * 50_000,
    "aperturas_con_tuberia": "[@a|" * 25_000,
    "anidadas": "[@a|f(" * 16_000,
    "sin_cerrar_con_tuberias": "[@a" + "|" * 100_000,
    "comillas_sin_cerrar": '[@a|f("' + '\\"' * 50_000,
    "argumentos_sin_fin": "[@a|f(" + "1," * 50_000,
    "corchetes": "[" * 100_000,
    "escapes": "[@@]" * 25_000,
    "espacios": "[@" + " " * 100_000,
    "texto_largo": "x" * 100_000,
}


@pytest.mark.parametrize("nombre", list(ENTRADAS_MALICIOSAS))
def test_una_entrada_larga_y_maliciosa_se_resuelve_en_menos_de_un_segundo(nombre) -> None:
    entrada = ENTRADAS_MALICIOSAS[nombre]

    inicio = time.perf_counter()
    try:
        sintaxis.leer(entrada)
    except ExpresionInvalida:
        pass
    duracion = time.perf_counter() - inicio

    assert duracion < 1.0, f"{nombre}: {duracion:.2f} s"


def test_una_entrada_valida_y_larga_tambien_es_lineal() -> None:
    entrada = "[@@]" * 20_000 + "x" * 60_000  # 80 000 caracteres, un solo nodo texto...
    limites = LimitesExpresion(nodos=10, funciones_por_nodo=10, largo_literal=10**6)

    inicio = time.perf_counter()
    expresion = sintaxis.leer(entrada, limites)
    duracion = time.perf_counter() - inicio

    assert expresion == Expresion((NodoTexto("[@" * 20_000 + "x" * 60_000),))
    assert duracion < 1.0


def test_una_variable_llamada_arroba_chocaria_con_el_escape_y_no_existe() -> None:
    # Regresion hallada por las pruebas de propiedades: `[@ @]` se leia como una variable
    # `@`, que al escribirse (`[@@]`) volvia como el texto literal `[@`.
    assert _codigo("[@ @]") is CodigoTexto.SINTAXIS_INVALIDA
    assert _codigo("[@@ | f]") is CodigoTexto.SINTAXIS_INVALIDA
    with pytest.raises(ExpresionNoEscribible):
        sintaxis.escribir(Expresion((NodoVariable("@"),)))
    assert sintaxis.leer("[@@x]") == Expresion((NodoVariable("@x"),))  # solo el nombre exacto

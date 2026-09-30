"""Compilar una vez y evaluar por fila: tipos, nulos, limites y seguridad (RF-42 a RF-48)."""

import re
from datetime import date
from decimal import Decimal

import pytest

from app.core.entities.cartera import TipoDato
from app.core.entities.texto_enriquecido import (
    ArgumentoVariable,
    CodigoTexto,
    Expresion,
    ExpresionInvalida,
    LimitesExpresion,
    LlamadaFuncion,
    NodoTexto,
    NodoVariable,
    TipoValor,
)
from app.core.services.seleccion_cartera.campos import CAMPOS_CARTERA
from app.core.services.texto_enriquecido import evaluador
from app.core.services.texto_enriquecido.tipos import tipo_de_valor, variables_desde_campos

T, N, F, B = TipoValor.TEXTO, TipoValor.NUMERO, TipoValor.FECHA, TipoValor.BOOLEANO
VARIABLES = {"titular": T, "monto": N, "vence": F, "activo": B, "dias": N, "telefono": T}


def _compilar(plantilla: str):
    return evaluador.compilar_texto(plantilla, VARIABLES)


def _problemas(expresion: Expresion):
    with pytest.raises(ExpresionInvalida) as error:
        evaluador.compilar(expresion, VARIABLES)
    return error.value.problemas


def _variable(nombre: str, *funciones: LlamadaFuncion, obligatoria: bool = False) -> NodoVariable:
    return NodoVariable(nombre, funciones, obligatoria)


# --- conversion implicita a texto (D1) y booleanos (D2) ---


def test_un_valor_sin_funciones_pasa_a_texto_con_str_como_las_plantillas_de_hoy() -> None:
    producto = {
        "monto": Decimal("1500.50"),
        "vence": date(2026, 9, 18),
        "activo": True,
        "titular": "PÉREZ",
        "dias": 12,
    }

    resultado = _compilar("[@monto]|[@vence]|[@activo]|[@titular]|[@dias]").evaluar(producto)

    assert resultado.texto == "1500.50|2026-09-18|True|PÉREZ|12"


def test_un_booleano_falso_es_False_y_no_es_vacio() -> None:
    assert _compilar("[@activo]").evaluar({"activo": False}).texto == "False"
    assert _compilar("[@activo | si_vacio(@activo)]").evaluar({"activo": False}).texto == "False"


def test_los_campos_booleanos_de_la_cartera_son_de_tipo_booleano() -> None:
    variables = variables_desde_campos(CAMPOS_CARTERA)
    booleanos = [n for n, t in CAMPOS_CARTERA.items() if t is TipoDato.BOOLEANO]

    assert booleanos
    assert any(nombre.endswith("_aplica") for nombre in booleanos)
    assert all(variables[nombre] is B for nombre in booleanos)
    assert {variables[n] for n, t in CAMPOS_CARTERA.items() if t is not TipoDato.BOOLEANO} == {
        T,
        N,
        F,
    }


def test_un_booleano_no_tiene_funciones_propias() -> None:
    problemas = _problemas(Expresion((_variable("activo", LlamadaFuncion("mayusculas")),)))

    assert problemas[0].codigo is CodigoTexto.TIPO_INCOMPATIBLE


def test_si_vacio_si_sirve_sobre_un_booleano_con_el_alternativo_de_otra_variable() -> None:
    compilada = _compilar("[@activo | si_vacio(@activo)]")

    assert compilada.evaluar({"activo": None}).texto == ""
    assert compilada.tipo is B


def test_el_tipo_en_tiempo_de_ejecucion_distingue_el_vacio() -> None:
    assert tipo_de_valor(None) is TipoValor.NULO
    assert tipo_de_valor("  ") is TipoValor.NULO
    assert tipo_de_valor(False) is TipoValor.BOOLEANO
    assert tipo_de_valor(3) is TipoValor.NUMERO
    assert tipo_de_valor(Decimal(1)) is TipoValor.NUMERO
    assert tipo_de_valor(date(2026, 1, 1)) is TipoValor.FECHA
    assert tipo_de_valor("x") is TipoValor.TEXTO


# --- nulos (4.3) ---


def test_una_variable_vacia_deja_su_parte_vacia_y_conserva_el_resto() -> None:
    compilada = _compilar(
        'Hola [@titular | mayusculas], vence [@vence | formato_fecha("dd/mm/aaaa")].'
    )

    assert compilada.evaluar({"titular": None, "vence": None}).texto == "Hola , vence ."


def test_la_cadena_no_se_aplica_sobre_un_vacio() -> None:
    compilada = _compilar('[@titular | rellenar_izquierda(5, "0")]')

    assert compilada.evaluar({"titular": None}).texto == ""
    assert compilada.evaluar({"titular": "   "}).texto == ""
    assert compilada.evaluar({"titular": "7"}).texto == "00007"


def test_las_funciones_que_aceptan_nulo_si_actuan_sobre_un_vacio() -> None:
    compilada = _compilar('[@titular | mayusculas | si_vacio("sin titular") | primeros(3)]')

    assert compilada.evaluar({"titular": None}).texto == "sin"
    assert compilada.evaluar({"titular": "ana"}).texto == "ANA"


def test_un_texto_sin_funciones_conserva_los_espacios_como_hoy() -> None:
    assert _compilar("[@titular]").evaluar({"titular": "  "}).texto == "  "


def test_una_variable_obligatoria_vacia_se_informa_con_su_nombre_y_su_nodo() -> None:
    compilada = evaluador.compilar(
        Expresion((NodoTexto("a"), _variable("titular", obligatoria=True))), VARIABLES
    )

    resultado = compilada.evaluar({"titular": None})

    assert resultado.texto == "a"
    (problema,) = resultado.problemas
    assert problema.codigo is CodigoTexto.VARIABLE_OBLIGATORIA_VACIA
    assert (problema.nodo, problema.nombre) == (1, "titular")


def test_una_variable_obligatoria_en_blanco_cuenta_como_vacia_como_en_mowa_mes() -> None:
    compilada = evaluador.compilar(
        Expresion((_variable("titular", LlamadaFuncion("mayusculas"), obligatoria=True),)),
        VARIABLES,
    )

    for vacio in (None, "", "   "):
        resultado = compilada.evaluar({"titular": vacio})
        assert [p.codigo for p in resultado.problemas] == [CodigoTexto.VARIABLE_OBLIGATORIA_VACIA]

    assert compilada.evaluar({"titular": "x"}).problemas == ()
    assert compilada.evaluar({"titular": False}).problemas == ()


def test_una_variable_obligatoria_con_un_cero_no_esta_vacia() -> None:
    compilada = evaluador.compilar(Expresion((_variable("monto", obligatoria=True),)), VARIABLES)

    assert compilada.evaluar({"monto": Decimal(0)}).problemas == ()


# --- valor tipado final (D11) ---


def test_un_solo_nodo_variable_devuelve_tambien_el_valor_tipado_final() -> None:
    fecha = _compilar("[@vence | sumar_dias(3)]").evaluar({"vence": date(2026, 9, 29)})
    numero = _compilar("[@monto | redondear(2)]").evaluar({"monto": Decimal("1.005")})

    assert fecha.valor == date(2026, 10, 2)
    assert fecha.texto == "2026-10-02"
    assert numero.valor == Decimal("1.01")
    assert isinstance(numero.valor, Decimal)


def test_sin_funciones_el_valor_es_el_del_producto_sin_tocar() -> None:
    assert _compilar("[@monto]").evaluar({"monto": Decimal("1500.50")}).valor == Decimal("1500.50")
    assert _compilar("[@vence]").evaluar({"vence": date(2026, 9, 18)}).valor == date(2026, 9, 18)
    assert _compilar("[@titular]").evaluar({"titular": "  "}).valor == "  "
    assert _compilar("[@monto]").evaluar({}).valor is None


def test_con_texto_alrededor_o_varios_nodos_no_hay_valor_tipado() -> None:
    assert _compilar("S/ [@monto]").evaluar({"monto": Decimal(1)}).valor is None
    assert _compilar("[@monto][@dias]").evaluar({"monto": Decimal(1), "dias": 2}).valor is None
    assert _compilar("[@monto]").es_variable_unica
    assert not _compilar("S/ [@monto]").es_variable_unica


def test_un_vacio_o_un_problema_dejan_el_valor_en_none() -> None:
    assert _compilar("[@vence | sumar_dias(3)]").evaluar({"vence": None}).valor is None
    assert _compilar("[@monto | dividir(0)]").evaluar({"monto": Decimal(1)}).valor is None


def test_el_tipo_de_la_expresion_sigue_la_cadena() -> None:
    assert _compilar("[@vence | sumar_dias(3)]").tipo is F
    assert _compilar('[@vence | formato_fecha("dd")]').tipo is T
    assert _compilar("[@monto | redondear(0)]").tipo is N
    assert _compilar("S/ [@monto]").tipo is T
    assert _compilar("").tipo is T


# --- comprobacion al compilar (RF-46) ---


def test_formato_fecha_sobre_un_texto_se_rechaza_al_compilar_no_al_generar() -> None:
    (problema,) = _problemas(
        Expresion((_variable("titular", LlamadaFuncion("formato_fecha", ("dd/mm/aaaa",))),))
    )

    assert problema.codigo is CodigoTexto.TIPO_INCOMPATIBLE
    assert (problema.nodo, problema.funcion) == (0, 0)
    assert "texto" in problema.detalle


def test_el_tipo_se_sigue_a_lo_largo_de_toda_la_cadena() -> None:
    # sumar_dias devuelve fecha; mayusculas no recibe fecha.
    (problema,) = _problemas(
        Expresion(
            (_variable("vence", LlamadaFuncion("sumar_dias", (1,)), LlamadaFuncion("mayusculas")),)
        )
    )

    assert (problema.codigo, problema.funcion) == (CodigoTexto.TIPO_INCOMPATIBLE, 1)


def test_una_cadena_valida_que_cambia_de_tipo_se_acepta() -> None:
    compilada = _compilar(
        '[@vence | sumar_dias(1) | formato_fecha("dd/mm") | rellenar_izquierda(8, "-")]'
    )

    assert compilada.evaluar({"vence": date(2026, 9, 29)}).texto == "---30/09"


def test_todos_los_problemas_se_informan_juntos_con_su_ubicacion() -> None:
    expresion = Expresion(
        (
            _variable("no_existe"),
            NodoTexto("-"),
            _variable("titular", LlamadaFuncion("inventada"), LlamadaFuncion("mayusculas")),
            _variable("titular", LlamadaFuncion("primeros", (0,))),
            _variable("monto", LlamadaFuncion("sumar", (ArgumentoVariable("titular"),))),
        )
    )

    problemas = evaluador.validar(expresion, VARIABLES)

    assert [(p.codigo, p.nodo, p.funcion, p.parametro) for p in problemas] == [
        (CodigoTexto.VARIABLE_DESCONOCIDA, 0, None, None),
        (CodigoTexto.FUNCION_DESCONOCIDA, 2, 0, None),
        (CodigoTexto.PARAMETRO_INVALIDO, 3, 0, "n"),
        (CodigoTexto.PARAMETRO_INVALIDO, 4, 0, "valor"),
    ]


def test_una_variable_desconocida_como_argumento_se_informa_en_su_parametro() -> None:
    (problema,) = _problemas(
        Expresion((_variable("monto", LlamadaFuncion("sumar", (ArgumentoVariable("nada"),))),))
    )

    assert problema.codigo is CodigoTexto.VARIABLE_DESCONOCIDA
    assert (problema.nodo, problema.funcion, problema.parametro) == (0, 0, "valor")


@pytest.mark.parametrize(
    ("llamada", "parametro"),
    [
        (LlamadaFuncion("primeros"), "n"),  # falta
        (LlamadaFuncion("primeros", (1, 2)), None),  # sobra
        (LlamadaFuncion("primeros", ("a",)), "n"),  # tipo
        (LlamadaFuncion("primeros", (1.5,)), "n"),  # no es Decimal ni int
        (LlamadaFuncion("primeros", (Decimal("1.5"),)), "n"),  # no es entero
        (LlamadaFuncion("primeros", (True,)), "n"),  # un booleano no es numero
        (LlamadaFuncion("primeros", (ArgumentoVariable("dias"),)), "n"),  # no admite variable
        (LlamadaFuncion("recortar", (1,)), None),  # no lleva argumentos
    ],
)
def test_los_argumentos_mal_formados_se_rechazan_en_el_parametro_que_toca(
    llamada, parametro
) -> None:
    (problema,) = _problemas(Expresion((_variable("titular", llamada),)))

    assert problema.codigo is CodigoTexto.PARAMETRO_INVALIDO
    assert problema.parametro == parametro


# --- limites (RF-48) ---


def test_los_limites_se_rechazan_al_compilar_sin_procesar_nada() -> None:
    limites = LimitesExpresion(
        nodos=2, funciones_por_nodo=2, argumentos_por_funcion=1, largo_literal=4
    )
    casos = {
        "nodos": Expresion((NodoTexto("a"), NodoTexto("b"), NodoTexto("c"))),
        "literal": Expresion((NodoTexto("abcde"),)),
        "funciones": Expresion((_variable("titular", *[LlamadaFuncion("recortar")] * 3),)),
        "argumentos": Expresion((_variable("titular", LlamadaFuncion("reemplazar", ("a", "b"))),)),
        "argumento_de_texto": Expresion(
            (_variable("titular", LlamadaFuncion("reemplazar", ("abcde",))),)
        ),
    }

    for nombre, expresion in casos.items():
        with pytest.raises(ExpresionInvalida) as error:
            evaluador.compilar(expresion, VARIABLES, limites)
        assert {p.codigo for p in error.value.problemas} == {CodigoTexto.LIMITE_EXCEDIDO}, nombre


def test_un_limite_excedido_en_un_nodo_dice_donde() -> None:
    limites = LimitesExpresion(funciones_por_nodo=1)
    expresion = Expresion(
        (
            NodoTexto("a"),
            _variable("titular", LlamadaFuncion("recortar"), LlamadaFuncion("mayusculas")),
        )
    )

    problemas = evaluador.validar(expresion, VARIABLES, limites)

    assert [(p.codigo, p.nodo) for p in problemas] == [(CodigoTexto.LIMITE_EXCEDIDO, 1)]


def test_los_limites_por_defecto_admiten_un_uso_normal() -> None:
    texto = "x" * 4000 + "[@titular | mayusculas | primeros(5)]" * 100

    assert _compilar(texto).cota == 4000 + 5 * 100


def test_un_texto_de_plantilla_que_excede_los_limites_se_rechaza_al_leer() -> None:
    with pytest.raises(ExpresionInvalida):
        _compilar("[@titular]" * 300)


# --- seguridad (RF-48) ---


def test_el_texto_nunca_se_interpreta_como_codigo() -> None:
    peligro = "__import__('os').system('x') {{7*7}} ${x} %(x)s {x}"

    resultado = _compilar(peligro + "[@titular]").evaluar({"titular": peligro})

    assert resultado.texto == peligro + peligro


def test_las_funciones_se_buscan_solo_en_el_registro_cerrado() -> None:
    for nombre in ["eval", "exec", "__import__", "open", "getattr", "lower", "__class__"]:
        (problema,) = _problemas(Expresion((_variable("titular", LlamadaFuncion(nombre)),)))
        assert problema.codigo is CodigoTexto.FUNCION_DESCONOCIDA, nombre


def test_los_argumentos_de_texto_son_datos_no_expresiones() -> None:
    codigo = "__import__('os').getcwd()"

    resultado = _compilar(f'[@titular | reemplazar("A", "{codigo}")]').evaluar({"titular": "A"})

    assert resultado.texto == codigo


def test_una_variable_que_no_esta_en_el_catalogo_no_se_lee_del_producto() -> None:
    with pytest.raises(ExpresionInvalida):
        _compilar("[@secreto]")


# --- compilar una vez, evaluar por fila ---


def test_por_fila_no_se_compilan_expresiones_regulares(monkeypatch) -> None:
    # Solo comprueba que evaluar no COMPILA patrones (re._compile). `enlace_whatsapp` si aplica la
    # regex ya compilada y lineal de RF-02 (`9\d{8}`) por fila, y eso esta permitido.
    compilada = _compilar(
        'ref [@titular | recortar | sin_tildes | mayusculas | reemplazar(".", "") | primeros(20)] '
        '[@vence | sumar_dias(1) | formato_fecha("dd de nombre_mes de aaaa")] '
        "[@monto | multiplicar(@dias) | redondear(2) | formato_numero(2)] "
        "[@telefono | enlace_whatsapp] [@titular | a_numero]"
    )

    def _sin_regex(*args, **kwargs):
        raise AssertionError("se compilo una expresion regular por fila")

    monkeypatch.setattr(re, "_compile", _sin_regex)
    producto = {
        "titular": " Ñandú. S.A. ",
        "vence": date(2026, 9, 29),
        "monto": Decimal("10.005"),
        "dias": 2,
        "telefono": "987654321",
    }

    resultado = compilada.evaluar(producto)

    assert resultado.texto.startswith("ref NANDU SA 30 de septiembre de 2026 20.01 ")
    assert len(resultado.problemas) == 1  # el titular no es un numero


def test_compilar_resuelve_una_sola_vez_y_evaluar_no_vuelve_a_comprobar_tipos() -> None:
    compilada = _compilar('[@vence | formato_fecha("dd/mm/aaaa")]')

    primero = compilada.evaluar({"vence": date(2026, 1, 2)})
    segundo = compilada.evaluar({"vence": date(2027, 3, 4)})

    assert (primero.texto, segundo.texto) == ("02/01/2026", "04/03/2027")


def test_las_variables_que_lee_la_expresion_incluyen_las_de_los_argumentos_sin_repetir() -> None:
    compilada = _compilar("[@monto | sumar(@dias)] y [@monto] y [@titular]")

    assert compilada.variables == ("monto", "dias", "titular")
    assert not compilada.es_valor_fijo
    assert _compilar("1010").es_valor_fijo


def test_un_producto_sin_la_clave_se_trata_como_vacio() -> None:
    assert _compilar("a[@titular]b").evaluar({}).texto == "ab"


def test_un_valor_de_tipo_equivocado_en_el_producto_es_un_problema_de_la_fila() -> None:
    resultado = _compilar("[@monto | sumar(1)]").evaluar({"monto": "abc"})

    assert resultado.texto == ""
    assert resultado.problemas[0].codigo is CodigoTexto.NO_ES_NUMERO
    assert resultado.problemas[0].funcion is None


def test_un_problema_en_un_nodo_no_detiene_a_los_demas() -> None:
    resultado = _compilar("[@monto | dividir(0)]-[@titular]-[@dias | sumar(1)]").evaluar(
        {"monto": Decimal(1), "titular": "x", "dias": 1}
    )

    assert resultado.texto == "-x-2"
    assert [(p.codigo, p.nodo) for p in resultado.problemas] == [(CodigoTexto.DIVISION_POR_CERO, 0)]


def test_una_expresion_justo_en_el_tope_de_cada_limite_se_acepta() -> None:
    limites = LimitesExpresion(
        nodos=2, funciones_por_nodo=2, argumentos_por_funcion=2, largo_literal=4
    )
    en_el_tope = Expresion(
        (
            NodoTexto("abcd"),
            _variable(
                "titular", LlamadaFuncion("recortar"), LlamadaFuncion("reemplazar", ("abcd", "x"))
            ),
        )
    )

    assert evaluador.validar(en_el_tope, VARIABLES, limites) == ()


def test_un_literal_booleano_no_es_un_argumento_valido_ni_donde_no_se_normaliza() -> None:
    # `si_vacio` no normaliza su alternativo: True (un int en Python) debe rechazarse aparte
    (problema,) = _problemas(Expresion((_variable("monto", LlamadaFuncion("si_vacio", (True,))),)))

    assert problema.codigo is CodigoTexto.PARAMETRO_INVALIDO
    assert problema.parametro == "alternativo"

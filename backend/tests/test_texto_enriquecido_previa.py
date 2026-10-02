"""Resultado por nodo y motivo de "sin cota" (B4a): lo que necesita la previsualizacion (RF-47).

La interfaz resalta la parte del resultado que produce cada pieza y marca con un punteado la
variable que llego vacia; cuando el largo maximo no se puede calcular, dice por que.
"""

import random
from datetime import date
from decimal import Decimal

import pytest

from app.core.entities.texto_enriquecido import CodigoTexto, TipoValor
from app.core.services.texto_enriquecido import evaluador

T, N, F = TipoValor.TEXTO, TipoValor.NUMERO, TipoValor.FECHA
VARIABLES = {"t": T, "u": T, "n": N, "m": N, "f": F, "tel": T}


def _c(plantilla: str, constantes=None):
    return evaluador.compilar_texto(plantilla, VARIABLES, constantes=constantes)


# --- Resultado por nodo ------------------------------------------------------------------------


def test_cada_nodo_trae_su_texto_y_su_tipo() -> None:
    resultado = _c("Hola [@t | mayusculas], vence [@f | sumar_dias(1)].").evaluar_por_nodo(
        {"t": "uno", "f": date(2026, 10, 5)}
    )

    assert [(n.indice, n.tipo, n.texto, n.vacio) for n in resultado.nodos] == [
        (0, "texto", "Hola ", False),
        (1, "variable", "UNO", False),
        (2, "texto", ", vence ", False),
        (3, "variable", "2026-10-06", False),
        (4, "texto", ".", False),
    ]
    assert resultado.texto == "Hola UNO, vence 2026-10-06."


def test_una_variable_vacia_se_distingue_de_un_texto_vacio() -> None:
    resultado = _c('a[@t]b[@u | si_vacio("x")]c[@tel | si_vacio(@t)]').evaluar_por_nodo(
        {"t": None, "u": "  ", "tel": None}
    )

    por_indice = {n.indice: n for n in resultado.nodos}
    assert por_indice[1].vacio is True and por_indice[1].texto == ""
    # `si_vacio` la llena: ya no se muestra como falta de dato
    assert por_indice[3].vacio is False and por_indice[3].texto == "x"
    # y si lo que la llena tambien esta vacio, sigue siendo falta de dato
    assert por_indice[5].vacio is True
    assert resultado.texto == "abxc"


def test_una_variable_ausente_o_nula_es_vacia_y_una_en_blanco_conserva_sus_espacios() -> None:
    nodos = (
        _c("[@t][@u][@n][@tel | mayusculas]")
        .evaluar_por_nodo({"t": "   ", "n": None, "tel": "  "})
        .nodos
    )

    # Sin funciones el texto es `str(valor)` como en RF-12: los espacios se conservan y no es vacio.
    assert [(n.texto, n.vacio) for n in nodos] == [
        ("   ", False),
        ("", True),
        ("", True),
        ("", True),
    ]


def test_una_variable_con_valor_no_es_vacia_aunque_su_texto_sea_cero() -> None:
    nodos = _c("[@n][@t]").evaluar_por_nodo({"n": Decimal(0), "t": "0"}).nodos

    assert [(n.texto, n.vacio) for n in nodos] == [("0", False), ("0", False)]


def test_un_texto_fijo_vacio_no_existe_y_uno_con_contenido_nunca_es_vacio() -> None:
    nodos = _c("hola").evaluar_por_nodo({}).nodos

    assert [(n.tipo, n.texto, n.vacio) for n in nodos] == [("texto", "hola", False)]


def test_los_problemas_de_fila_salen_con_su_ubicacion_y_el_nodo_queda_vacio() -> None:
    resultado = _c("x[@n | dividir(0)]y").evaluar_por_nodo({"n": Decimal(1)})

    (problema,) = resultado.problemas
    assert (problema.codigo, problema.nodo, problema.funcion) == (
        CodigoTexto.DIVISION_POR_CERO,
        1,
        0,
    )
    assert [n.texto for n in resultado.nodos] == ["x", "", "y"]
    assert resultado.nodos[1].vacio is False  # el dato estaba: el problema es de la funcion


def test_una_obligatoria_vacia_se_informa_igual_que_al_generar() -> None:
    from app.core.entities.texto_enriquecido import Expresion, NodoVariable

    compilada = evaluador.compilar(Expresion((NodoVariable("t", obligatoria=True),)), VARIABLES)

    resultado = compilada.evaluar_por_nodo({"t": None})

    assert [p.codigo for p in resultado.problemas] == [CodigoTexto.VARIABLE_OBLIGATORIA_VACIA]
    assert resultado.nodos[0].vacio is True


def test_el_valor_tipado_de_un_nodo_unico_viaja_igual_que_en_evaluar() -> None:
    resultado = _c("[@f | sumar_dias(3)]").evaluar_por_nodo({"f": date(2026, 9, 29)})

    assert resultado.valor == date(2026, 10, 2)


def test_con_constantes_el_nodo_plegado_tambien_sale() -> None:
    resultado = _c("a[@t]b[@u]", {"t": "X"}).evaluar_por_nodo({"u": "Y"})

    assert resultado.texto == "aXbY"
    assert [n.texto for n in resultado.nodos] == ["aXb", "Y"]  # el texto plegado se une


def test_la_suma_de_los_nodos_es_siempre_el_resultado_de_evaluar() -> None:
    azar = random.Random(20261001)
    plantillas = [
        "a[@t]b",
        "[@t | mayusculas][@u | si_vacio('x')]".replace("'", '"'),
        "[@n | sumar(@m)] y [@n | dividir(@m)]",
        '[@f | sumar_dias(@n) | formato_fecha("dd/mm/aaaa")]',
        "[@tel | enlace_whatsapp] [@t]",
        "",
        "solo texto",
    ]
    valores = {
        "t": [None, "", "  ", "abc", "Ñandú"],
        "u": [None, "x"],
        "n": [None, Decimal(0), Decimal("2.5"), 3, "abc"],
        "m": [None, Decimal(0), 2],
        "f": [None, date(2026, 9, 5), date(9999, 12, 31)],
        "tel": [None, "987654321", "12"],
    }

    for _ in range(2000):
        compilada = _c(azar.choice(plantillas))
        fila = {k: azar.choice(v) for k, v in valores.items()}

        por_nodo = compilada.evaluar_por_nodo(fila)
        normal = compilada.evaluar(fila)

        assert por_nodo.texto == normal.texto == "".join(n.texto for n in por_nodo.nodos)
        assert por_nodo.problemas == normal.problemas
        assert por_nodo.valor == normal.valor


# --- Motivo de "sin cota" -----------------------------------------------------------------------


def _motivo(plantilla: str):
    compilada = _c(plantilla)
    assert compilada.cota is None, plantilla
    return compilada.motivo_sin_cota


def test_con_cota_no_hay_motivo() -> None:
    assert _c("[@t | primeros(8)]").motivo_sin_cota is None
    assert _c("hola").motivo_sin_cota is None
    assert _c("").motivo_sin_cota is None


def test_una_variable_sola_no_tiene_largo_porque_depende_del_dato() -> None:
    motivo = _motivo("a[@t]")

    assert (motivo.codigo, motivo.nodo, motivo.funcion) == (CodigoTexto.SIN_COTA_VARIABLE, 1, None)
    assert "t" in motivo.detalle


def test_las_funciones_que_solo_transforman_no_arreglan_una_variable_sin_largo() -> None:
    motivo = _motivo("[@t | mayusculas | recortar]")

    assert motivo.codigo is CodigoTexto.SIN_COTA_VARIABLE
    assert (motivo.nodo, motivo.funcion) == (0, None)


def test_una_funcion_sin_cota_se_senala_con_su_posicion() -> None:
    motivo = _motivo("[@n | sumar(1) | redondear(2)]")

    assert (motivo.codigo, motivo.nodo, motivo.funcion) == (CodigoTexto.SIN_COTA_FUNCION, 0, 1)
    assert "redondear" in motivo.detalle


def test_si_una_funcion_pierde_la_cota_que_habia_el_motivo_es_esa_funcion() -> None:
    motivo = _motivo("[@t | primeros(3) | a_numero]")

    assert (motivo.codigo, motivo.funcion) == (CodigoTexto.SIN_COTA_FUNCION, 1)


def test_el_motivo_es_el_del_primer_nodo_sin_largo() -> None:
    motivo = _motivo("[@t | primeros(3)] [@n | redondear(0)] [@u]")

    assert (motivo.codigo, motivo.nodo) == (CodigoTexto.SIN_COTA_FUNCION, 2)


@pytest.mark.parametrize(
    ("plantilla", "codigo"),
    [
        ("[@t]", CodigoTexto.SIN_COTA_VARIABLE),
        ("[@n]", CodigoTexto.SIN_COTA_VARIABLE),
        ("[@n | a_texto]", CodigoTexto.SIN_COTA_FUNCION),
        ("[@n | formato_numero(2)]", CodigoTexto.SIN_COTA_FUNCION),
    ],
)
def test_los_dos_motivos(plantilla, codigo) -> None:
    assert _motivo(plantilla).codigo is codigo


def test_plegar_no_cambia_el_motivo() -> None:
    sin = _c("[@t]").motivo_sin_cota
    con = _c("[@t]", {"t": "ab"}).motivo_sin_cota

    assert sin == con


def test_una_constante_usada_como_argumento_tambien_cuenta_en_el_detalle_por_nodo() -> None:
    resultado = _c("[@n | sumar(@m)]", {"m": Decimal(5)}).evaluar_por_nodo({"n": Decimal(2)})

    assert resultado.texto == "7"
    assert resultado.problemas == ()


def test_el_indice_de_cada_nodo_es_su_posicion_en_la_expresion_aunque_se_plegue() -> None:
    resultado = _c("[@t]-[@u]!", {"t": "K"}).evaluar_por_nodo({"u": "x"})

    assert [(n.indice, n.tipo, n.texto) for n in resultado.nodos] == [
        (0, "texto", "K-"),
        (2, "variable", "x"),
        (3, "texto", "!"),
    ]

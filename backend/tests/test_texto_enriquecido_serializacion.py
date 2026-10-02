"""Forma JSON canonica de una expresion (seccion 4.1 del diseno) y su lectura estricta.

Es la forma que viaja por la API y la que se guardara con las definiciones (B4b) y el speech v2
(B6). Lo estructuralmente imposible (un tipo de nodo desconocido, un argumento con forma invalida)
no revienta: sale como problema `expresion_invalida` con su ubicacion, para que el editor lo ubique.
"""

import random
from decimal import Decimal

import pytest

from app.core.entities.texto_enriquecido import (
    ArgumentoVariable,
    CodigoTexto,
    Expresion,
    ExpresionInvalida,
    LlamadaFuncion,
    NodoTexto,
    NodoVariable,
)
from app.core.services.texto_enriquecido import serializacion

EJEMPLO = {
    "nodos": [
        {
            "tipo": "variable",
            "nombre": "titular",
            "funciones": [{"nombre": "primeros", "args": [8]}],
        },
        {"tipo": "texto", "valor": " Caja Cusco te informa que tu cuota venció el "},
        {
            "tipo": "variable",
            "nombre": "fecha_vencimiento_cuota",
            "funciones": [{"nombre": "formato_fecha", "args": ["dd/mm/aaaa"]}],
        },
        {"tipo": "texto", "valor": ", acércate a pagar."},
    ]
}


def _problemas(dato) -> tuple:
    with pytest.raises(ExpresionInvalida) as error:
        serializacion.expresion_desde_dict(dato)
    return error.value.problemas


def test_el_ejemplo_del_diseno_se_lee_como_expresion() -> None:
    expresion = serializacion.expresion_desde_dict(EJEMPLO)

    assert expresion == Expresion(
        (
            NodoVariable("titular", (LlamadaFuncion("primeros", (8,)),)),
            NodoTexto(" Caja Cusco te informa que tu cuota venció el "),
            NodoVariable(
                "fecha_vencimiento_cuota", (LlamadaFuncion("formato_fecha", ("dd/mm/aaaa",)),)
            ),
            NodoTexto(", acércate a pagar."),
        )
    )


def test_los_opcionales_toman_su_valor_por_defecto() -> None:
    expresion = serializacion.expresion_desde_dict(
        {
            "nodos": [
                {"tipo": "variable", "nombre": "t"},
                {"tipo": "variable", "nombre": "u", "funciones": [{"nombre": "recortar"}]},
            ]
        }
    )

    assert expresion == Expresion(
        (NodoVariable("t"), NodoVariable("u", (LlamadaFuncion("recortar"),)))
    )


def test_una_expresion_vacia_es_valida() -> None:
    assert serializacion.expresion_desde_dict({"nodos": []}) == Expresion(())


def test_la_obligatoria_viaja_y_vuelve() -> None:
    dato = {"nodos": [{"tipo": "variable", "nombre": "t", "funciones": [], "obligatoria": True}]}

    expresion = serializacion.expresion_desde_dict(dato)

    assert expresion.nodos[0].obligatoria is True
    assert serializacion.expresion_a_dict(expresion) == dato


def test_los_argumentos_son_texto_entero_decimal_o_variable() -> None:
    dato = {
        "nodos": [
            {
                "tipo": "variable",
                "nombre": "x",
                "funciones": [{"nombre": "f", "args": ["a", -3, 2.5, {"variable": "otra"}]}],
            }
        ]
    }

    args = serializacion.expresion_desde_dict(dato).nodos[0].funciones[0].args

    assert args == ("a", -3, Decimal("2.5"), ArgumentoVariable("otra"))
    assert isinstance(args[1], int) and isinstance(args[2], Decimal)


def test_ida_y_vuelta_de_la_forma_json() -> None:
    assert serializacion.expresion_a_dict(serializacion.expresion_desde_dict(EJEMPLO)) == {
        "nodos": [
            {**n, "funciones": n.get("funciones", []), "obligatoria": False}
            if n["tipo"] == "variable"
            else n
            for n in EJEMPLO["nodos"]
        ]
    }


def test_un_decimal_viaja_como_numero_json_sin_perder_su_valor() -> None:
    expresion = Expresion(
        (
            NodoVariable(
                "x", (LlamadaFuncion("f", (Decimal("2.50"), Decimal("3"), Decimal("-0.1"))),)
            ),
        )
    )

    args = serializacion.expresion_a_dict(expresion)["nodos"][0]["funciones"][0]["args"]

    assert args == [2.5, 3, -0.1]
    assert (
        serializacion.expresion_desde_dict(serializacion.expresion_a_dict(expresion)) == expresion
    )


# --- Lo estructuralmente imposible es un problema, no una excepcion ----------------------------


@pytest.mark.parametrize(
    "dato",
    [
        None,
        [],
        "texto",
        {},
        {"nodos": None},
        {"nodos": "x"},
        {"nodos": [], "otra": 1},
    ],
)
def test_una_expresion_que_no_tiene_la_forma_es_un_problema_de_toda_la_expresion(dato) -> None:
    (problema,) = _problemas(dato)

    assert problema.codigo is CodigoTexto.EXPRESION_INVALIDA
    assert problema.nodo is None  # sin ubicacion: es de toda la expresion


@pytest.mark.parametrize(
    "nodo",
    [
        None,
        "texto",
        {},
        {"tipo": "funcion"},
        {"tipo": "texto"},
        {"tipo": "texto", "valor": 5},
        {"tipo": "texto", "valor": "a", "nombre": "x"},
        {"tipo": "variable"},
        {"tipo": "variable", "nombre": ""},
        {"tipo": "variable", "nombre": 3},
        {"tipo": "variable", "nombre": "x", "funciones": "recortar"},
        {"tipo": "variable", "nombre": "x", "obligatoria": "si"},
        {"tipo": "variable", "nombre": "x", "valor": "a"},
    ],
)
def test_un_nodo_mal_formado_se_ubica_por_su_posicion(nodo) -> None:
    (problema,) = _problemas({"nodos": [{"tipo": "texto", "valor": "ok"}, nodo]})

    assert problema.codigo is CodigoTexto.EXPRESION_INVALIDA
    assert problema.nodo == 1


@pytest.mark.parametrize(
    "funcion",
    [
        None,
        "primeros",
        {},
        {"nombre": ""},
        {"nombre": 3},
        {"nombre": "f", "args": "8"},
        {"nombre": "f", "args": [True]},
        {"nombre": "f", "args": [None]},
        {"nombre": "f", "args": [[1]]},
        {"nombre": "f", "args": [float("nan")]},
        {"nombre": "f", "args": [float("inf")]},
        {"nombre": "f", "args": [{}]},
        {"nombre": "f", "args": [{"variable": ""}]},
        {"nombre": "f", "args": [{"variable": 3}]},
        {"nombre": "f", "args": [{"variable": "a", "otra": 1}]},
        {"nombre": "f", "args": [{"var": "a"}]},
        {"nombre": "f", "otra": 1},
    ],
)
def test_una_funcion_o_un_argumento_mal_formado_se_ubica_por_nodo_y_funcion(funcion) -> None:
    dato = {
        "nodos": [{"tipo": "variable", "nombre": "x", "funciones": [{"nombre": "ok"}, funcion]}]
    }

    (problema,) = _problemas(dato)

    assert problema.codigo is CodigoTexto.EXPRESION_INVALIDA
    assert (problema.nodo, problema.funcion) == (0, 1)


def test_todos_los_problemas_se_informan_juntos() -> None:
    dato = {
        "nodos": [{"tipo": "x"}, {"tipo": "texto", "valor": 1}, {"tipo": "variable", "nombre": ""}]
    }

    problemas = _problemas(dato)

    assert [p.nodo for p in problemas] == [0, 1, 2]


def test_un_tipo_desconocido_dice_cual_es() -> None:
    (problema,) = _problemas({"nodos": [{"tipo": "formula", "valor": "=1"}]})

    assert "formula" in problema.detalle


def test_un_entero_enorme_o_un_texto_largo_pasan_la_lectura_y_los_limites_los_pone_el_motor() -> (
    None
):
    dato = {"nodos": [{"tipo": "texto", "valor": "x" * 10_000}]}

    assert serializacion.expresion_desde_dict(dato).nodos[0].valor == "x" * 10_000


# --- Propiedad con semilla fija -----------------------------------------------------------------


def _nodo_al_azar(azar: random.Random):
    if azar.random() < 0.4:
        return NodoTexto("".join(azar.choice('ab [@]|"\\ñ\n') for _ in range(azar.randint(1, 8))))
    funciones = tuple(
        LlamadaFuncion(
            azar.choice(["f", "g_h", "recortar"]),
            tuple(
                azar.choice(
                    [
                        azar.randint(-100, 100),
                        Decimal(azar.randint(-999, 999)) / 10,
                        "t" * azar.randint(0, 3),
                        ArgumentoVariable(azar.choice(["a", "b_c"])),
                    ]
                )
                for _ in range(azar.randint(0, 3))
            ),
        )
        for _ in range(azar.randint(0, 3))
    )
    return NodoVariable(azar.choice(["x", "y_z"]), funciones, azar.random() < 0.3)


def test_ida_y_vuelta_de_expresiones_al_azar() -> None:
    azar = random.Random(20261001)

    for _ in range(3000):
        expresion = Expresion(tuple(_nodo_al_azar(azar) for _ in range(azar.randint(0, 6))))

        dato = serializacion.expresion_a_dict(expresion)

        assert serializacion.expresion_desde_dict(dato) == expresion
        assert serializacion.expresion_a_dict(serializacion.expresion_desde_dict(dato)) == dato

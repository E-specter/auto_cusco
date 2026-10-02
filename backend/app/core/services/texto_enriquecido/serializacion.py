"""Forma JSON canonica de una expresion y su lectura estricta (seccion 4.1 del diseno).

    {"nodos": [
        {"tipo": "variable", "nombre": "titular",
         "funciones": [{"nombre": "primeros", "args": [8]}]},
        {"tipo": "texto", "valor": " vencio el "},
        {"tipo": "variable", "nombre": "fecha", "funciones": [], "obligatoria": false}
    ]}

Un argumento es un texto, un numero o `{"variable": "nombre"}`. Es la forma que viaja por la API y
la que guardaran las definiciones (B4b) y el speech v2 (B6).

La lectura no revienta con lo estructuralmente imposible (un tipo de nodo desconocido, un
argumento con forma invalida, una clave de mas): lo informa como problema `expresion_invalida`,
con el nodo y la funcion donde esta, para que el editor lo ubique. Los limites de tamano y las
variables o funciones que no existen los comprueba despues `evaluador.compilar`.
"""

import math
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from app.core.entities.texto_enriquecido import (
    Argumento,
    ArgumentoVariable,
    CodigoTexto,
    Expresion,
    ExpresionInvalida,
    LlamadaFuncion,
    Nodo,
    NodoTexto,
    NodoVariable,
    Problema,
)


def expresion_desde_dict(dato: Any) -> Expresion:
    """Lee la forma JSON. Si no la tiene, `ExpresionInvalida` con todos los problemas."""
    problemas: list[Problema] = []
    if (
        not isinstance(dato, Mapping)
        or set(dato) != {"nodos"}
        or not isinstance(dato["nodos"], list)
    ):
        raise ExpresionInvalida(
            (_problema("Una expresion es un objeto con una unica clave `nodos`, que es una lista"),)
        )
    nodos: list[Nodo] = []
    for indice, crudo in enumerate(dato["nodos"]):
        nodo = _nodo(crudo, indice, problemas)
        if nodo is not None:
            nodos.append(nodo)
    if problemas:
        raise ExpresionInvalida(tuple(problemas))
    return Expresion(tuple(nodos))


def expresion_a_dict(expresion: Expresion) -> dict[str, Any]:
    """La forma JSON canonica de una expresion; `expresion_desde_dict` la lee de vuelta igual."""
    nodos: list[dict[str, Any]] = []
    for nodo in expresion.nodos:
        if isinstance(nodo, NodoTexto):
            nodos.append({"tipo": "texto", "valor": nodo.valor})
            continue
        nodos.append(
            {
                "tipo": "variable",
                "nombre": nodo.nombre,
                "funciones": [
                    {"nombre": f.nombre, "args": [_argumento_a_json(a) for a in f.args]}
                    for f in nodo.funciones
                ],
                "obligatoria": nodo.obligatoria,
            }
        )
    return {"nodos": nodos}


def _problema(detalle: str, nodo: int | None = None, funcion: int | None = None) -> Problema:
    return Problema(CodigoTexto.EXPRESION_INVALIDA, detalle, nodo=nodo, funcion=funcion)


def _nodo(crudo: Any, indice: int, problemas: list[Problema]) -> Nodo | None:
    def falla(detalle: str) -> None:
        problemas.append(_problema(detalle, indice))

    if not isinstance(crudo, Mapping):
        falla("Un nodo es un objeto con su `tipo`")
        return None
    tipo = crudo.get("tipo")
    if tipo == "texto":
        if set(crudo) != {"tipo", "valor"}:
            falla("Un nodo de texto lleva solo `tipo` y `valor`")
        elif not isinstance(crudo["valor"], str):
            falla("El `valor` de un nodo de texto es un texto")
        else:
            return NodoTexto(crudo["valor"])
        return None
    if tipo == "variable":
        return _variable(crudo, indice, problemas)
    falla(f"El tipo de nodo {tipo!r} no existe: es `texto` o `variable`")
    return None


def _variable(
    crudo: Mapping[str, Any], indice: int, problemas: list[Problema]
) -> NodoVariable | None:
    antes = len(problemas)

    def falla(detalle: str) -> None:
        problemas.append(_problema(detalle, indice))

    desconocidas = set(crudo) - {"tipo", "nombre", "funciones", "obligatoria"}
    if desconocidas:
        falla(f"Un nodo de variable no lleva {sorted(desconocidas)}")
    nombre = crudo.get("nombre")
    if not isinstance(nombre, str) or not nombre:
        falla("El `nombre` de una variable es un texto no vacio")
    crudas = crudo.get("funciones", [])
    obligatoria = crudo.get("obligatoria", False)
    if not isinstance(obligatoria, bool):
        falla("`obligatoria` es verdadero o falso")
    funciones: list[LlamadaFuncion] = []
    if not isinstance(crudas, list):
        falla("`funciones` es una lista")
    else:
        for posicion, cruda in enumerate(crudas):
            funcion = _funcion(cruda, indice, posicion, problemas)
            if funcion is not None:
                funciones.append(funcion)
    if len(problemas) > antes:
        return None
    return NodoVariable(nombre, tuple(funciones), obligatoria)


def _funcion(
    cruda: Any, indice: int, posicion: int, problemas: list[Problema]
) -> LlamadaFuncion | None:
    antes = len(problemas)

    def falla(detalle: str) -> None:
        problemas.append(_problema(detalle, indice, posicion))

    if not isinstance(cruda, Mapping):
        falla("Una funcion es un objeto con su `nombre`")
        return None
    desconocidas = set(cruda) - {"nombre", "args"}
    if desconocidas:
        falla(f"Una funcion no lleva {sorted(desconocidas)}")
    nombre = cruda.get("nombre")
    if not isinstance(nombre, str) or not nombre:
        falla("El `nombre` de una funcion es un texto no vacio")
    argumentos = cruda.get("args", [])
    leidos: list[Argumento] = []
    if not isinstance(argumentos, list):
        falla("`args` es una lista")
    else:
        for numero, argumento in enumerate(argumentos, start=1):
            leido, motivo = _argumento(argumento)
            if motivo is not None:
                falla(f"El argumento {numero} {motivo}")
            else:
                leidos.append(leido)
    if len(problemas) > antes:
        return None
    return LlamadaFuncion(nombre, tuple(leidos))


def _argumento(crudo: Any) -> tuple[Argumento, str | None]:
    """(argumento, None) si se pudo leer; (0, motivo) si no."""
    if isinstance(crudo, bool) or crudo is None:
        return 0, "no puede ser verdadero, falso ni nulo"
    if isinstance(crudo, (str, int, Decimal)):
        if isinstance(crudo, Decimal) and not crudo.is_finite():
            return 0, "no es un numero finito"
        return crudo, None
    if isinstance(crudo, float):
        if not math.isfinite(crudo):
            return 0, "no es un numero finito"
        return Decimal(repr(crudo)), None
    if isinstance(crudo, Mapping):
        nombre = crudo.get("variable")
        if set(crudo) == {"variable"} and isinstance(nombre, str) and nombre:
            return ArgumentoVariable(nombre), None
        return 0, 'es un objeto y solo puede ser {"variable": "nombre"}'
    return 0, "es un texto, un numero o una variable"


def _argumento_a_json(argumento: Argumento) -> Any:
    if isinstance(argumento, ArgumentoVariable):
        return {"variable": argumento.nombre}
    if isinstance(argumento, Decimal):
        return int(argumento) if argumento == argumento.to_integral_value() else float(argumento)
    return argumento

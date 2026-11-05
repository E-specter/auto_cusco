"""Que variables usa una expresion, mirando sus nodos y no su texto.

Un conector que decide algo segun las variables de una expresion (por ejemplo, MOWA MES excluye a
un producto sin titular solo si el segmento usa el titular) lo decide aqui: un nodo `variable`, o
una variable que es argumento de una funcion (`{"variable": "dias"}`), cuenta; un nombre que aparece
dentro de un texto fijo no cuenta nunca.
"""

from app.core.entities.texto_enriquecido import (
    ArgumentoVariable,
    CodigoTexto,
    Expresion,
    NodoVariable,
    Problema,
)


def variables_usadas(expresion: Expresion) -> frozenset[str]:
    """Los nombres de las variables que la expresion lee, incluidas las de sus argumentos."""
    nombres: set[str] = set()
    for nodo in expresion.nodos:
        if not isinstance(nodo, NodoVariable):
            continue
        nombres.add(nodo.nombre)
        for llamada in nodo.funciones:
            nombres.update(a.nombre for a in llamada.args if isinstance(a, ArgumentoVariable))
    return frozenset(nombres)


def problemas_de_funciones(expresion: Expresion) -> tuple[Problema, ...]:
    """Un problema por cada funcion de la expresion, ubicado en su nodo y su posicion en la cadena.
    Para un contexto que no admite funciones (`ContextoTexto.admite_funciones`)."""
    return tuple(
        Problema(
            CodigoTexto.FUNCION_NO_ADMITIDA,
            f"Este texto no admite funciones: quita {llamada.nombre} de {nodo.nombre}",
            nodo=indice,
            funcion=posicion,
            nombre=llamada.nombre,
        )
        for indice, nodo in enumerate(expresion.nodos)
        if isinstance(nodo, NodoVariable)
        for posicion, llamada in enumerate(nodo.funciones)
    )

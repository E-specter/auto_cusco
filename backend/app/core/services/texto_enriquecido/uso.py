"""Que variables usa una expresion, mirando sus nodos y no su texto.

Un conector que decide algo segun las variables de una expresion (por ejemplo, MOWA MES excluye a
un producto sin titular solo si el segmento usa el titular) lo decide aqui: un nodo `variable`, o
una variable que es argumento de una funcion (`{"variable": "dias"}`), cuenta; un nombre que aparece
dentro de un texto fijo no cuenta nunca.
"""

from app.core.entities.texto_enriquecido import ArgumentoVariable, Expresion, NodoVariable


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

"""Todos los problemas de una definicion de carga, cada uno con su columna y su variante.

`GeneradorCargas` se detiene en la primera columna que no compila, porque para generar una carga
una falla basta. El editor necesita lo contrario: ver de una vez todo lo que hay que corregir y
donde. Aqui se comprueba cada columna y cada variante por separado, con las mismas reglas con que
las compilara el generador (las plantillas conservan sus topes crecientes, RF-54).
"""

from collections.abc import Iterable, Mapping
from dataclasses import replace
from typing import Any

from app.core.entities.mapeo import DefinicionCarga, PlantillaInvalida
from app.core.entities.texto_enriquecido import (
    LIMITES,
    CodigoTexto,
    Expresion,
    ExpresionInvalida,
    Problema,
)
from app.core.services.mapeo_campos.generador import (
    GeneradorCargas,
    limites_de_plantilla,
    variables_de,
)
from app.core.services.mapeo_campos.serializacion import DefinicionLeida, ProblemaDeDefinicion
from app.core.services.texto_enriquecido import evaluador, sintaxis


def diagnosticar_leida(
    leida: DefinicionLeida, variables: Iterable[str] | Mapping[str, Any]
) -> tuple[ProblemaDeDefinicion, ...]:
    """Lo mismo que `diagnosticar`, con la columna de cada problema en la posicion del pedido.

    El diagnostico cuenta las columnas ya ordenadas por `orden`; el pedido las identifica por su
    posicion en la lista (C-1), y `leida.posiciones` dice cual es cual.
    """
    return tuple(
        p if p.columna is None else replace(p, columna=leida.posiciones[p.columna])
        for p in diagnosticar(leida.definicion, variables)
    )


def diagnosticar(
    definicion: DefinicionCarga, variables: Iterable[str] | Mapping[str, Any]
) -> tuple[ProblemaDeDefinicion, ...]:
    """Los problemas de compilacion de la definicion; vacio si el generador la acepta."""
    tipos = variables_de(variables)
    problemas: list[ProblemaDeDefinicion] = []
    for indice, campo in enumerate(definicion.campos):
        problemas += _de_contenido(campo.plantilla, campo.expresion, tipos, indice, None)
        for variante in campo.variantes:
            problemas += _de_contenido(
                variante.plantilla or "", variante.expresion, tipos, indice, variante.segmento
            )
    if problemas:
        return tuple(problemas)
    try:
        GeneradorCargas(definicion, variables)
    except PlantillaInvalida as error:
        problema = Problema(CodigoTexto.DEFINICION_INVALIDA, str(error))
        return (ProblemaDeDefinicion(problema, campo="definicion"),)
    return ()


def _de_contenido(
    plantilla: str,
    expresion: Expresion | None,
    tipos: Mapping[str, Any],
    columna: int,
    segmento: str | None,
) -> list[ProblemaDeDefinicion]:
    limites = LIMITES
    try:
        if expresion is None:
            limites = limites_de_plantilla(plantilla)
            expresion = sintaxis.leer(plantilla, limites)
        encontrados = evaluador.validar(expresion, tipos, limites)
    except ExpresionInvalida as error:
        encontrados = error.problemas
    return [ProblemaDeDefinicion(problema, columna, segmento) for problema in encontrados]

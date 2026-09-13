"""Sintaxis de texto de una seleccion: filtros, orden e indicadores.

Es la misma en toda la API (la URL de `/cartera`, el cuerpo de
`/archivos-carga`) y tambien la forma en que se guardan las selecciones
compartidas. Por eso vive en el nucleo y no en el adaptador HTTP:

    filtro:     campo:operador:valor    (varios valores separados por `|`)
    orden:      campo, o -campo para descendente
    indicador:  nombre:funcion:campo
"""

from app.core.entities.cartera import ConsultaInvalida, Filtro, Funcion, Indicador, Operador, Orden
from app.core.services.seleccion_cartera import campos

SEPARADOR_VALORES = "|"


def parsear_filtro(crudo: str) -> Filtro:
    partes = crudo.split(":", 2)
    if len(partes) < 2:
        raise ConsultaInvalida(
            f"El filtro {crudo!r} debe tener la forma campo:operador o campo:operador:valor"
        )
    campo, operador_crudo = partes[0].strip(), partes[1].strip()
    try:
        operador = Operador(operador_crudo)
    except ValueError as exc:
        permitidos = ", ".join(sorted(o.value for o in Operador))
        raise ConsultaInvalida(
            f"El operador {operador_crudo!r} no existe; permitidos: {permitidos}"
        ) from exc
    if len(partes) == 2:
        return Filtro(campo=campo, operador=operador)
    valores = tuple(campos.convertir(campo, valor) for valor in partes[2].split(SEPARADOR_VALORES))
    return Filtro(campo=campo, operador=operador, valores=valores)


def parsear_orden(crudo: str | None) -> Orden | None:
    if not crudo:
        return None
    descendente = crudo.startswith("-")
    return Orden(campo=crudo.lstrip("-").strip(), descendente=descendente)


def parsear_indicador(crudo: str) -> Indicador:
    partes = [parte.strip() for parte in crudo.split(":")]
    if len(partes) not in (2, 3):
        raise ConsultaInvalida(
            f"El indicador {crudo!r} debe tener la forma nombre:funcion o nombre:funcion:campo"
        )
    try:
        funcion = Funcion(partes[1])
    except ValueError as exc:
        permitidas = ", ".join(sorted(f.value for f in Funcion))
        raise ConsultaInvalida(
            f"La funcion {partes[1]!r} no existe; permitidas: {permitidas}"
        ) from exc
    return Indicador(
        nombre=partes[0], funcion=funcion, campo=partes[2] if len(partes) == 3 else None
    )

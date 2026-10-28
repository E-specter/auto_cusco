r"""Sintaxis de texto de una seleccion: filtros, orden e indicadores.

Es la misma en toda la API (la URL de `/cartera`, el cuerpo de
`/archivos-carga`) y tambien la forma en que se guardan las selecciones
compartidas. Por eso vive en el nucleo y no en el adaptador HTTP:

    filtro:     campo:operador:valor    (varios valores separados por `|`)
                `\|` es una barra literal y `\\` una barra invertida; una `\` seguida de otro
                caracter, o al final, queda literal (tolerante: un filtro guardado con una barra
                suelta se lee igual que siempre). En `en`/`no_en` de un texto, un elemento vacio
                es «(vacio)».
    orden:      campo, o -campo para descendente
    indicador:  nombre:funcion:campo
"""

from app.core.entities.cartera import (
    OPERADORES_DE_LISTA,
    ConsultaInvalida,
    Filtro,
    Funcion,
    Indicador,
    Operador,
    Orden,
    TipoDato,
)
from app.core.services.seleccion_cartera.campos import CatalogoCartera

SEPARADOR_VALORES = "|"
ESCAPE = chr(92)  # la barra invertida


def partir_valores(texto: str) -> list[str]:
    """Parte la lista de valores por `|`, respetando el escape.

    `ESCAPE + "|"` es una barra literal y `ESCAPE + ESCAPE` una barra invertida. Una barra invertida
    seguida de cualquier otro caracter, o al final, queda LITERAL: el parseo es tolerante para que
    un filtro guardado con una barra suelta se lea igual que antes del escape.
    """
    valores: list[str] = []
    actual: list[str] = []
    i = 0
    while i < len(texto):
        c = texto[i]
        if c == ESCAPE and i + 1 < len(texto) and texto[i + 1] in (SEPARADOR_VALORES, ESCAPE):
            actual.append(texto[i + 1])
            i += 2
            continue
        if c == SEPARADOR_VALORES:
            valores.append("".join(actual))
            actual = []
        else:
            actual.append(c)
        i += 1
    valores.append("".join(actual))
    return valores


def escapar_valor(valor: str) -> str:
    """Lo inverso de `partir_valores` para un valor: el que lo escribe (guardar un filtro)."""
    return valor.replace(ESCAPE, ESCAPE + ESCAPE).replace(
        SEPARADOR_VALORES, ESCAPE + SEPARADOR_VALORES
    )


def parsear_filtro(crudo: str, catalogo: CatalogoCartera) -> Filtro:
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
    es_lista_de_texto = (
        operador in OPERADORES_DE_LISTA and catalogo.tipo_de(campo) is TipoDato.TEXTO
    )
    valores = tuple(
        # Un elemento vacio de la lista de un texto es «(vacio)»: None, no una cadena vacia.
        None if es_lista_de_texto and not valor.strip() else catalogo.convertir(campo, valor)
        for valor in partir_valores(partes[2])
    )
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

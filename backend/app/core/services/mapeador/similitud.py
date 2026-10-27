"""Normalizacion, coincidencia y similitud de un encabezado con los campos de un catalogo.

Es la parte del mapeador que decide, por encabezado, si un campo coincide o se parece. Las usa
`analisis.analizar` y tambien `ingesta_sabana.cabeceras.mapear_cabeceras`, el camino viejo de
`POST /cargas`: una sola `coincide` para los dos (M-6 a).
"""

import re
import unicodedata
from difflib import SequenceMatcher

from app.core.entities.mapeador import CampoDestino

# Un parecido solo se sugiere si supera este umbral (RF-32: una constante, en un solo lugar).
UMBRAL_PARECIDO = 0.75
# Palabras que no distinguen un campo de otro: no cuentan en el solapamiento de palabras.
PALABRAS_VACIAS = frozenset({"de", "del", "la", "las", "el", "los", "y"})
# Si los dos mejores candidatos difieren en menos que esto, no se sugiere ninguno (RF-58).
DIFERENCIA_DE_EMPATE = 0.02

_METACARACTERES = re.compile(r"[\\.^$*+?{}\[\]|()]")


def sin_tildes(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def normalizar_cabecera(cabecera: str) -> str:
    """Forma canonica de una cabecera para compararla con el catalogo (N-1): sin tildes, en
    minusculas, con los espacios recortados y colapsados."""
    return re.sub(r"\s+", " ", sin_tildes(cabecera)).strip().casefold()


def _nombre_como_texto(campo: CampoDestino) -> str:
    """El nombre del campo como texto para comparar. El de un campo adicional es su nombre legible:
    su nombre tecnico (`ad_...`) no es algo que un encabezado pueda decir."""
    if campo.adicional and campo.etiqueta:
        return normalizar_cabecera(campo.etiqueta)
    return campo.nombre.replace("_", " ")


def coincide(normalizado: str, campo: CampoDestino) -> bool:
    """El encabezado normalizado cumple un alias del campo (`fullmatch`) o es igual a su nombre
    con `_` como espacio. Es la unica definicion de «coincide» de la aplicacion."""
    if normalizado == _nombre_como_texto(campo):
        return True
    # El alias de un campo adicional es un texto (su encabezado de origen), no una regex.
    return any(
        re.fullmatch(re.escape(alias) if campo.adicional else alias, normalizado)
        for alias in campo.alias
    )


def _es_literal(alias: str) -> bool:
    return _METACARACTERES.search(alias) is None


def alias_legible(alias: str, literal: bool = False) -> str | None:
    """El alias como texto para mostrar o buscar, o `None` si no se puede: un alias con
    metacaracteres es una expresion regular, no un texto. Un literal sale con `_` como espacio.
    `literal=True` es para el alias de un campo adicional (RF-64): es su encabezado de origen y
    siempre es un texto, aunque lleve un punto o un parentesis.
    Es LA funcion de «alias legible»: la usa la API del catalogo, tambien para los adicionales."""
    return alias.replace("_", " ") if literal or _es_literal(alias) else None


def alias_legibles(campo: CampoDestino) -> tuple[str, ...]:
    """Los alias de un campo que se pueden mostrar, en el orden del catalogo y sin repetir. Un
    campo sin alias literales da `()`."""
    legibles = (alias_legible(a, campo.adicional) for a in campo.alias)
    return tuple(dict.fromkeys(a for a in legibles if a is not None))


def candidatos_de_similitud(campo: CampoDestino) -> tuple[str, ...]:
    """Los textos contra los que se compara un encabezado: el nombre del campo y sus alias que son
    texto literal. Un alias con metacaracteres de expresion regular no participa."""
    return (
        _nombre_como_texto(campo),
        *(a for a in campo.alias if campo.adicional or _es_literal(a)),
    )


def _palabras(texto: str) -> set[str]:
    return set(texto.split()) - PALABRAS_VACIAS


def similitud_entre(a: str, b: str) -> float:
    """El mayor entre la razon de `SequenceMatcher`, la proporcion de palabras en comun (Jaccard) y
    el coeficiente de solapamiento de las palabras, |A n B| / min(|A|, |B|), de 0 a 1.

    El solapamiento premia al encabezado que CONTIENE el nombre del campo y le suma palabras
    («numero de pagare» contiene «pagare»), que las otras dos medidas castigan. Las palabras vacias
    (`PALABRAS_VACIAS`) no cuentan en las palabras en comun.
    """
    razon = SequenceMatcher(None, a, b).ratio()
    palabras_a, palabras_b = set(a.split()), set(b.split())
    union = palabras_a | palabras_b
    jaccard = len(palabras_a & palabras_b) / len(union) if union else 0.0
    utiles_a, utiles_b = _palabras(a), _palabras(b)
    menor = min(len(utiles_a), len(utiles_b))
    solapamiento = len(utiles_a & utiles_b) / menor if menor else 0.0
    return max(razon, jaccard, solapamiento)


def similitud(normalizado: str, campo: CampoDestino) -> float:
    """El maximo de `similitud_entre` contra el nombre y los alias literales del campo."""
    return max(similitud_entre(normalizado, texto) for texto in candidatos_de_similitud(campo))

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
    return campo.nombre.replace("_", " ")


def coincide(normalizado: str, campo: CampoDestino) -> bool:
    """El encabezado normalizado cumple un alias del campo (`fullmatch`) o es igual a su nombre
    con `_` como espacio. Es la unica definicion de «coincide» de la aplicacion."""
    if normalizado == _nombre_como_texto(campo):
        return True
    return any(re.fullmatch(alias, normalizado) for alias in campo.alias)


def _es_literal(alias: str) -> bool:
    return _METACARACTERES.search(alias) is None


def alias_legible(alias: str) -> str | None:
    """El alias como texto para mostrar o buscar, o `None` si no se puede: un alias con
    metacaracteres es una expresion regular, no un texto. Un literal sale con `_` como espacio.
    Es LA funcion de «alias legible»: la usa la API del catalogo, y tambien los alias de un campo
    adicional (RF-64, que es el encabezado de origen) pasan por aqui."""
    return alias.replace("_", " ") if _es_literal(alias) else None


def alias_legibles(campo: CampoDestino) -> tuple[str, ...]:
    """Los alias de un campo que se pueden mostrar, en el orden del catalogo y sin repetir. Un
    campo sin alias literales da `()`."""
    return tuple(dict.fromkeys(a for a in map(alias_legible, campo.alias) if a is not None))


def candidatos_de_similitud(campo: CampoDestino) -> tuple[str, ...]:
    """Los textos contra los que se compara un encabezado: el nombre del campo y sus alias que son
    texto literal. Un alias con metacaracteres de expresion regular no participa."""
    return (_nombre_como_texto(campo), *(a for a in campo.alias if _es_literal(a)))


def similitud_entre(a: str, b: str) -> float:
    """El mayor entre la razon de `SequenceMatcher` y la proporcion de palabras en comun (Jaccard
    de las palabras), de 0 a 1."""
    razon = SequenceMatcher(None, a, b).ratio()
    palabras_a, palabras_b = set(a.split()), set(b.split())
    union = palabras_a | palabras_b
    jaccard = len(palabras_a & palabras_b) / len(union) if union else 0.0
    return max(razon, jaccard)


def similitud(normalizado: str, campo: CampoDestino) -> float:
    """El maximo de `similitud_entre` contra el nombre y los alias literales del campo."""
    return max(similitud_entre(normalizado, texto) for texto in candidatos_de_similitud(campo))

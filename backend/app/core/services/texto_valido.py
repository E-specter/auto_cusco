r"""Texto sin mitades sueltas de un par sustituto (T-API-B1).

Un par sustituto es como UTF-16 escribe un caracter fuera del plano basico (un emoji): dos
mitades, U+D800 a U+DBFF y U+DC00 a U+DFFF. UTF-8 no las admite sueltas, y un `str` de Python que
trae una no se puede escribir (UTF-8, PostgreSQL, un `.xlsx`, la respuesta JSON): revienta mucho
despues, con un 500.

Entran por un solo lugar: un JSON que las trae escritas (`"\ud800"`, o los tres bytes de CESU-8,
que `json.loads` acepta con `surrogatepass`). Un par COMPLETO (`"\ud83d\ude00"`) lo une
`json.loads` en un solo caracter y no es un problema. Las consultas, las rutas, los formularios y
las cabeceras llegan como UTF-8 o Latin-1 y no las pueden traer (se comprueba en
`tests/test_api_texto_valido.py`).

Este modulo no sabe de HTTP: busca la mitad suelta en un valor ya leido y da su ruta. Lo usan el
filtro de la API (`app/api/texto_valido.py`) y el lector de archivos JSON.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

MITAD_SUELTA = re.compile("[\ud800-\udfff]")

# Lo que PUEDE traer una mitad suelta, en el cuerpo sin leer: un escape `\uD800` a `\uDFFF` (que
# tambien es la primera mitad de un par completo, asi que solo avisa) o los tres bytes de una mitad
# en CESU-8. Si no esta, no hay nada que buscar y no hace falta leer el JSON.
SOSPECHA_EN_BYTES = re.compile(rb"\\u[dD][89a-fA-F][0-9a-fA-F]{2}|\xed[\xa0-\xbf][\x80-\xbf]")
SOSPECHA_EN_TEXTO = re.compile(r"\\u[dD][89a-fA-F][0-9a-fA-F]{2}")


@dataclass(frozen=True)
class Hallazgo:
    """Donde esta la mitad suelta: la ruta hasta el texto (con la clave si esta en una clave)."""

    ruta: tuple[str | int, ...]
    en_clave: bool
    punto_de_codigo: int

    @property
    def codigo(self) -> str:
        return f"U+{self.punto_de_codigo:04X}"


def tiene_mitad_suelta(texto: str) -> bool:
    return not texto.isascii() and MITAD_SUELTA.search(texto) is not None


def a_texto_seguro(valor: Any) -> Any:
    """El mismo valor con cada mitad suelta escrita como texto (`\\ud800`): se puede mostrar y
    serializar. Recorre diccionarios (claves y valores), listas y tuplas; no toca lo demas."""
    if isinstance(valor, str):
        if not tiene_mitad_suelta(valor):
            return valor
        return MITAD_SUELTA.sub(lambda m: f"\\u{ord(m.group()):04x}", valor)
    if isinstance(valor, Mapping):
        return {a_texto_seguro(k): a_texto_seguro(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [a_texto_seguro(v) for v in valor]
    return valor


def _hijos(valor: Any, ruta: tuple[str | int, ...]):
    """(ruta, es_clave, hijo) de un diccionario (cada clave y despues su valor) o de una lista."""
    if isinstance(valor, dict):
        for clave, hijo in valor.items():
            yield (*ruta, clave), True, clave
            yield (*ruta, clave), False, hijo
    else:
        for posicion, hijo in enumerate(valor):
            yield (*ruta, posicion), False, hijo


def buscar_mitad_suelta(valor: Any) -> Hallazgo | None:
    """La primera mitad suelta de un valor leido de JSON (valores Y claves, en el orden del
    documento), o `None`. Iterativo: un JSON muy anidado no agota la pila."""
    pila = [_hijos([valor], ())]  # la raiz como unico elemento de una lista: ruta (0,)
    while pila:
        try:
            ruta, es_clave, hijo = next(pila[-1])
        except StopIteration:
            pila.pop()
            continue
        if isinstance(hijo, str):
            if tiene_mitad_suelta(hijo):
                encontrada = MITAD_SUELTA.search(hijo)
                assert encontrada is not None
                return Hallazgo(ruta[1:], es_clave, ord(encontrada.group()))
        elif isinstance(hijo, (dict, list)):
            pila.append(_hijos(hijo, ruta))
    return None

"""Interpretacion de plantillas con referencias a campos (RF-12).

Una plantilla es texto plano con referencias entre `[@...]`:

    "1010"                           -> valor fijo
    "[@telefono]"                    -> copia directa del campo
    "51[@telefono]"                  -> prefijo mas campo
    "documento=[@documento_numero]"  -> concatenacion

Compilar una plantilla la valida contra el catalogo de campos disponibles, asi
un error de escritura se detecta al guardar la definicion y no al generar miles
de filas.
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from app.core.entities.mapeo import PlantillaInvalida

REFERENCIA = re.compile(r"\[@([^\]\[]*)\]")
_APERTURA_SUELTA = re.compile(r"\[@")


@dataclass(frozen=True)
class Parte:
    """Un trozo de la plantilla: texto fijo o el nombre de un campo."""

    texto: str | None = None
    campo: str | None = None


@dataclass(frozen=True)
class Plantilla:
    partes: tuple[Parte, ...]
    original: str

    @property
    def campos(self) -> tuple[str, ...]:
        return tuple(parte.campo for parte in self.partes if parte.campo is not None)

    @property
    def es_valor_fijo(self) -> bool:
        return not self.campos

    @property
    def es_referencia_simple(self) -> bool:
        """La plantilla es exactamente un campo, sin texto alrededor."""
        return len(self.partes) == 1 and self.partes[0].campo is not None


def compilar(plantilla: str, campos_disponibles: Iterable[str]) -> Plantilla:
    """Divide la plantilla en partes y comprueba que los campos existan."""
    disponibles = set(campos_disponibles)
    partes: list[Parte] = []
    posicion = 0
    for coincidencia in REFERENCIA.finditer(plantilla):
        if coincidencia.start() > posicion:
            partes.append(Parte(texto=plantilla[posicion : coincidencia.start()]))
        campo = coincidencia.group(1).strip()
        if not campo:
            raise PlantillaInvalida(f"La plantilla {plantilla!r} tiene una referencia vacia")
        if campo not in disponibles:
            raise PlantillaInvalida(
                f"La plantilla {plantilla!r} usa el campo {campo!r}, que no existe en el producto"
            )
        partes.append(Parte(campo=campo))
        posicion = coincidencia.end()
    if posicion < len(plantilla):
        partes.append(Parte(texto=plantilla[posicion:]))
    resto = REFERENCIA.sub("", plantilla)
    if _APERTURA_SUELTA.search(resto):
        raise PlantillaInvalida(f"La plantilla {plantilla!r} tiene un '[@' sin cerrar con ']'")
    if not partes:
        partes.append(Parte(texto=""))
    return Plantilla(partes=tuple(partes), original=plantilla)


def valor_crudo(plantilla: Plantilla, producto: Mapping[str, Any]) -> Any:
    """Valor del producto cuando la plantilla es una sola referencia.

    Sirve para conservar el tipo original (fecha, importe) en vez de pasarlo
    por texto. Para cualquier otra plantilla devuelve None.
    """
    if not plantilla.es_referencia_simple:
        return None
    return producto.get(plantilla.partes[0].campo)


def aplicar(plantilla: Plantilla, producto: Mapping[str, Any], vacio: str = "") -> str:
    """Arma el texto de la plantilla para un producto. Un campo sin valor queda vacio."""
    trozos: list[str] = []
    for parte in plantilla.partes:
        if parte.texto is not None:
            trozos.append(parte.texto)
            continue
        valor = producto.get(parte.campo)
        trozos.append(vacio if valor is None else str(valor))
    return "".join(trozos)

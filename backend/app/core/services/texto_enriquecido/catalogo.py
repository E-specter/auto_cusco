"""Catalogo de funciones del motor para la interfaz (RF-44): todo sale del registro.

Una funcion nueva (un modulo en `funciones/` con sus metadatos) aparece aqui con sus tipos, sus
parametros y sus claves i18n sin tocar la API. Los nombres visibles y las descripciones no viajan:
viajan las claves (`textoEnriquecido.funcion.<nombre>.nombre`, `.descripcion`,
`.parametro.<parametro>`, `textoEnriquecido.familia.<familia>`) y la interfaz las traduce.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any

from .funciones import REGISTRO
from .funciones import fecha as _fecha
from .funciones.base import MISMO_TIPO, Funcion, Parametro

# Los ejemplos de patrones y de marcas se calculan con esta fecha, con la funcion de siempre.
FECHA_DE_EJEMPLO = date(2026, 10, 5)

TIPO_DEL_ARGUMENTO_IGUAL_A_LA_ENTRADA = "entrada"


@dataclass(frozen=True)
class OpcionCatalogo:
    valor: str
    ejemplo: str | None = None


@dataclass(frozen=True)
class ParametroCatalogo:
    nombre: str
    clave_nombre: str
    tipo: str  # "numero", "texto" o "entrada" (el mismo tipo que recibe la funcion)
    obligatorio: bool
    por_defecto: Any
    acepta_variable: bool
    entero: bool
    minimo: int | None
    maximo: int | None
    largo_minimo: int | None
    largo_maximo: int | None
    opciones: tuple[OpcionCatalogo, ...]
    opciones_cerradas: bool


@dataclass(frozen=True)
class FuncionCatalogo:
    nombre: str
    familia: str
    clave_familia: str
    clave_nombre: str
    clave_descripcion: str
    recibe: tuple[str, ...]
    devuelve: str  # un tipo, o "entrada" si devuelve el mismo que recibe
    acepta_nulo: bool
    parametros: tuple[ParametroCatalogo, ...]


@dataclass(frozen=True)
class PatronFecha:
    patron: str
    ejemplo: str


@dataclass(frozen=True)
class MarcaFecha:
    marca: str
    clave: str
    ejemplo: str


def _ejemplo_de_fecha(patron: str) -> str:
    return _fecha._formato_fecha(FECHA_DE_EJEMPLO, _fecha._convertir_patron(patron))


def _opciones(funcion: Funcion, parametro: Parametro) -> tuple[OpcionCatalogo, ...]:
    if parametro.nombre == "patron" and funcion.familia in ("fecha", "conversion"):
        return tuple(OpcionCatalogo(p, _ejemplo_de_fecha(p)) for p in parametro.opciones)
    return tuple(OpcionCatalogo(valor) for valor in parametro.opciones)


def _parametro(funcion: Funcion, parametro: Parametro) -> ParametroCatalogo:
    tipo = (
        parametro.tipo.value
        if parametro.tipo is not None
        else TIPO_DEL_ARGUMENTO_IGUAL_A_LA_ENTRADA
    )
    return ParametroCatalogo(
        nombre=parametro.nombre,
        clave_nombre=f"{funcion.clave_nombre.removesuffix('.nombre')}.parametro.{parametro.nombre}",
        tipo=tipo,
        obligatorio=parametro.obligatorio,
        por_defecto=None if parametro.obligatorio else parametro.por_defecto,
        acepta_variable=parametro.acepta_variable,
        entero=parametro.entero,
        minimo=parametro.minimo,
        maximo=parametro.maximo,
        largo_minimo=parametro.largo_minimo,
        largo_maximo=parametro.largo_maximo,
        opciones=_opciones(funcion, parametro),
        opciones_cerradas=parametro.opciones_cerradas,
    )


def _funcion(funcion: Funcion) -> FuncionCatalogo:
    devuelve = funcion.devuelve if funcion.devuelve == MISMO_TIPO else str(funcion.devuelve.value)
    return FuncionCatalogo(
        nombre=funcion.nombre,
        familia=funcion.familia,
        clave_familia=f"textoEnriquecido.familia.{funcion.familia}",
        clave_nombre=funcion.clave_nombre,
        clave_descripcion=funcion.clave_descripcion,
        recibe=tuple(tipo.value for tipo in funcion.recibe),
        devuelve=devuelve,
        acepta_nulo=funcion.acepta_nulo,
        parametros=tuple(_parametro(funcion, p) for p in funcion.parametros),
    )


def catalogo_de_funciones() -> tuple[FuncionCatalogo, ...]:
    """Las funciones del registro, en su orden."""
    return tuple(_funcion(f) for f in REGISTRO.values())


def familias() -> tuple[str, ...]:
    """Las familias, en el orden en que aparecen en el registro."""
    return tuple(dict.fromkeys(f.familia for f in REGISTRO.values()))


def patrones_de_fecha() -> tuple[PatronFecha, ...]:
    return tuple(PatronFecha(p, _ejemplo_de_fecha(p)) for p in _fecha.PATRONES_FRECUENTES)


def marcas_de_fecha() -> tuple[MarcaFecha, ...]:
    return tuple(
        MarcaFecha(m, f"textoEnriquecido.marcaFecha.{m}", _ejemplo_de_fecha(m))
        for m in _fecha.MARCAS_LEGIBLES
    )

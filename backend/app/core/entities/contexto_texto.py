"""Contexto de un texto enriquecido: las variables que un modulo aporta al motor (RF-43).

El motor no conoce MOWA MES ni ninguna plataforma: recibe un contexto con las variables, su tipo,
un registro de ejemplo, el limite de largo que impone el canal y como se segmenta por defecto.
Las arma la composicion (`services/contextos_texto.py`).
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.core.entities.segmentacion import RangoDias
from app.core.entities.texto_enriquecido import TipoValor

# El contexto que aporta los campos de la cartera: el origen de casi todas las variables.
ORIGEN_CARTERA = "cartera"


class TemaVariable(StrEnum):
    """El tema en que el buscador agrupa una variable (§13.3 del motor), en el orden en que se
    muestran. `OTROS` es un campo base sin tema asignado: nunca se pierde, y la prueba del catalogo
    avisa que le falta uno."""

    PERSONA = "persona"
    DEUDA = "deuda"
    FECHAS = "fechas"
    CREDITO = "credito"
    GESTION = "gestion"
    RIESGO = "riesgo"
    ADICIONALES = "adicionales"
    OTROS = "otros"


def _sin_cambios(texto: str) -> str:
    """La `salida` por defecto: el texto tal cual se evalua."""
    return texto


@dataclass(frozen=True)
class VariableContexto:
    """Una variable del contexto. `clave_nombre` solo la tiene la que aporta el modulo.

    `origen` es el nombre del contexto que la aporta: `cartera` para un campo de la cartera, o el
    del modulo (`mowa_mes.speech`) para una variable que es suya. La interfaz agrupa por origen.

    Un campo adicional (RF-64) trae su nombre legible en `etiqueta` y `adicional`; si esta
    `archivado` se sigue resolviendo (lo que ya lo usa compila), pero el editor no lo ofrece. En
    las demas, `etiqueta` es None y las marcas son falsas.

    `tema` es la agrupacion del buscador (una sola fuente: la manda el backend). Un campo adicional
    es de `ADICIONALES`; uno base sin tema asignado cae en `OTROS`.
    """

    nombre: str
    tipo: TipoValor
    clave_nombre: str | None = None
    origen: str = ORIGEN_CARTERA
    etiqueta: str | None = None
    adicional: bool = False
    archivado: bool = False
    tema: TemaVariable = TemaVariable.OTROS


@dataclass(frozen=True)
class ContextoTexto:
    nombre: str
    clave_nombre: str
    variables: tuple[VariableContexto, ...]
    ejemplo: Mapping[str, Any]
    limite_largo: int | None
    umbral_advertencia: int | None
    variable_dias: str
    tabla_rangos: tuple[RangoDias, ...]
    registro_de_producto: Callable[[Mapping[str, Any]], dict[str, Any]]
    # La clave i18n de la linea de alcance que el buscador muestra al pie (§13.3): que NO ofrece
    # este contexto, dicho como regla del lugar. None si ofrece todo (Columnas): sin linea.
    clave_alcance: str | None = None
    # Comportamiento del canal, no datos del catalogo (por eso no entran en `repr`, en la
    # comparacion ni en el contrato). `medida` es la unidad del largo y de la cota (por defecto,
    # caracteres); `salida` es lo que se le hace al texto antes de enviarlo (por defecto, nada). El
    # speech de MOWA MES mide en unidades GSM-7 y normaliza a GSM-7 (RF-MM-27).
    medida: Callable[[str], int] = field(default=len, repr=False, compare=False)
    salida: Callable[[str], str] = field(default=_sin_cambios, repr=False, compare=False)

    @property
    def tipos(self) -> dict[str, TipoValor]:
        return {variable.nombre: variable.tipo for variable in self.variables}


class ContextoDesconocido(Exception):
    def __init__(self, nombre: str) -> None:
        super().__init__(f"El contexto {nombre!r} no existe")
        self.nombre = nombre

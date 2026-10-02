"""Contexto de un texto enriquecido: las variables que un modulo aporta al motor (RF-43).

El motor no conoce MOWA MES ni ninguna plataforma: recibe un contexto con las variables, su tipo,
un registro de ejemplo, el limite de largo que impone el canal y como se segmenta por defecto.
Las arma la composicion (`services/contextos_texto.py`).
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from app.core.entities.segmentacion import RangoDias
from app.core.entities.texto_enriquecido import TipoValor

# El contexto que aporta los campos de la cartera: el origen de casi todas las variables.
ORIGEN_CARTERA = "cartera"


@dataclass(frozen=True)
class VariableContexto:
    """Una variable del contexto. `clave_nombre` solo la tiene la que aporta el modulo.

    `origen` es el nombre del contexto que la aporta: `cartera` para un campo de la cartera, o el
    del modulo (`mowa_mes.speech`) para una variable que es suya. La interfaz agrupa por origen.
    """

    nombre: str
    tipo: TipoValor
    clave_nombre: str | None = None
    origen: str = ORIGEN_CARTERA


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

    @property
    def tipos(self) -> dict[str, TipoValor]:
        return {variable.nombre: variable.tipo for variable in self.variables}


class ContextoDesconocido(Exception):
    def __init__(self, nombre: str) -> None:
        super().__init__(f"El contexto {nombre!r} no existe")
        self.nombre = nombre

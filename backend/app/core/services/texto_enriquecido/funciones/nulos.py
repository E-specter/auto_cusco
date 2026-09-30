"""Funciones de valores vacios (RF-45): el valor alternativo."""

from typing import Any

from app.core.entities.texto_enriquecido import TipoValor

from .base import MISMO_TIPO, Funcion, Parametro, es_vacio


def _si_vacio(valor: Any, alternativo: Any) -> Any:
    return alternativo if es_vacio(valor) else valor


def _cota_si_vacio(entrada: int | None, args: tuple) -> int | None:
    alternativo = args[0]
    if entrada is None or not isinstance(alternativo, str):
        return None
    return max(entrada, len(alternativo))


FUNCIONES = (
    Funcion(
        "si_vacio",
        "nulos",
        (TipoValor.TEXTO, TipoValor.NUMERO, TipoValor.FECHA, TipoValor.BOOLEANO),
        MISMO_TIPO,
        _si_vacio,
        (Parametro("alternativo", None, acepta_variable=True),),
        acepta_nulo=True,
        cota=_cota_si_vacio,
    ),
)

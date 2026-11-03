"""Los contextos de textos guardados y su registro (RF-69, T-HI-B4).

Un contexto lo declara el modulo que usa los textos (`whatsmkt.mensaje`) y trae su validador: el
contenido de una version es un objeto JSON, y el contexto dice que objeto es y que lo hace valido.
Hay dos formas de declararlo:

- `validador_de_expresion`: `{"expresion": {...}}`, una expresion del motor de texto enriquecido
  (RF-42) validada contra un `ContextoTexto` (RF-46);
- `validador_de_texto_plano`: `{"texto": "..."}`, un texto con un largo maximo (fijo, leido de la
  configuracion en cada validacion, o sin medir) y, si el modulo las tiene, reglas propias (por
  ejemplo, las macros `[$MACROn$]` del mensaje de WhatsMKT). Una regla devuelve un `Problema` con
  `REGLA_DEL_CONTEXTO`, su `codigo_contexto` y sus `parametros`.

El nucleo no conoce ningun contexto: cada modulo registra el suyo en el `RegistroContextosGuardados`
desde la capa de composicion de la API, como las plataformas de las definiciones (RF-72).
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.core.entities.contexto_texto import ContextoTexto
from app.core.entities.texto_enriquecido import CodigoTexto, ExpresionInvalida, Problema
from app.core.services.texto_enriquecido import evaluador
from app.core.services.texto_enriquecido.serializacion import expresion_desde_dict

Validador = Callable[[Mapping[str, Any]], tuple[Problema, ...]]


class TipoContenido(StrEnum):
    EXPRESION = "expresion"
    TEXTO_PLANO = "texto_plano"


@dataclass(frozen=True)
class ContextoGuardado:
    """Un contexto: su clave estable (se guarda con cada texto), su etiqueta y su validador."""

    clave: str
    etiqueta: str
    tipo: TipoContenido
    validar: Validador

    def __post_init__(self) -> None:
        if not self.clave.strip() or not self.etiqueta.strip():
            raise ValueError("Un contexto de textos guardados necesita clave y etiqueta")


class ContextoGuardadoDesconocido(Exception):
    def __init__(self, clave: str) -> None:
        super().__init__(f"El contexto de textos guardados {clave!r} no esta registrado")
        self.clave = clave


class RegistroContextosGuardados:
    """Los contextos que la aplicacion conoce, por clave y en el orden en que se registraron."""

    def __init__(self, contextos: Iterable[ContextoGuardado] = ()) -> None:
        self._contextos: dict[str, ContextoGuardado] = {}
        for contexto in contextos:
            self.registrar(contexto)

    def registrar(self, contexto: ContextoGuardado) -> None:
        if contexto.clave in self._contextos:
            raise ValueError(f"El contexto {contexto.clave!r} esta registrado dos veces")
        self._contextos[contexto.clave] = contexto

    def disponibles(self) -> tuple[ContextoGuardado, ...]:
        return tuple(self._contextos.values())

    def obtener(self, clave: str) -> ContextoGuardado:
        try:
            return self._contextos[clave]
        except KeyError:
            raise ContextoGuardadoDesconocido(clave) from None

    def __contains__(self, clave: object) -> bool:
        return clave in self._contextos


def _invalido(detalle: str) -> tuple[Problema, ...]:
    return (Problema(CodigoTexto.TEXTO_GUARDADO_INVALIDO, detalle),)


def validador_de_expresion(contexto: ContextoTexto) -> Validador:
    """Valida `{"expresion": ...}` con el mismo motor y las mismas variables que RF-46."""

    def validar(contenido: Mapping[str, Any]) -> tuple[Problema, ...]:
        if set(contenido) != {"expresion"}:
            return _invalido("El contenido es un objeto con una unica clave `expresion`")
        try:
            evaluador.compilar(
                expresion_desde_dict(contenido["expresion"]), contexto.tipos, medida=contexto.medida
            )
        except ExpresionInvalida as error:
            return tuple(error.problemas)
        return ()

    return validar


def validador_de_texto_plano(
    maximo: int | Callable[[], int] | None,
    reglas: Callable[[str], Sequence[Problema]] | None = None,
) -> Validador:
    """Valida `{"texto": ...}`: un texto no vacio de hasta `maximo` caracteres y, si hay, las
    `reglas` del modulo (que devuelven `Problema`s, con `REGLA_DEL_CONTEXTO` si son propias).

    `maximo` puede ser un entero fijo; una funcion sin argumentos, que se lee en CADA validacion
    (para un tope que viene de la configuracion y puede cambiar sin reiniciar); o None, que no
    mide el largo y solo exige que el texto no este vacio.
    """

    def validar(contenido: Mapping[str, Any]) -> tuple[Problema, ...]:
        if set(contenido) != {"texto"} or not isinstance(contenido["texto"], str):
            return _invalido("El contenido es un objeto con una unica clave `texto`, de texto")
        texto = contenido["texto"]
        limite = maximo() if callable(maximo) else maximo
        if not texto.strip():
            return _invalido("El texto no puede estar vacio")
        if limite is not None and len(texto) > limite:
            return _invalido(f"El texto debe tener entre 1 y {limite} caracteres")
        return tuple(reglas(texto)) if reglas else ()

    return validar

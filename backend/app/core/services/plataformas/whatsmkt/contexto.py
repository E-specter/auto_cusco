"""El contexto de textos guardados `whatsmkt.mensaje` (RF-WM-19, RF-69).

Cada mensaje de WhatsMKT es un texto guardado y versionado de este contexto: texto plano, un solo
bloque. Al guardar se aplican DOS reglas del modulo (`mensaje.py`), que el validador devuelve como
`Problema(REGLA_DEL_CONTEXTO)` con el codigo de WhatsMKT y sus parametros; la interfaz los traduce
con `whatsmkt.codigo.<codigo_contexto>`:

- sin emojis (RF-WM-24): `mensaje_con_emoji` con `{caracter, posicion}`;
- el largo (RF-WM-26): `mensaje_largo` con `{largo, maximo}`; `[whatsapp]` cuenta como el enlace
  de 26 caracteres.

El tope NO se fija al registrar: la capa de composicion pasa una funcion que lo lee de la
configuracion en CADA validacion, asi un cambio en la configuracion vale en el siguiente pedido y el
nucleo no toca la base. Las macros contra la definicion NO van aqui: al guardar no se sabe que
definicion se usara (van en la previsualizacion y al crear).
"""

from collections.abc import Callable, Sequence

from app.core.entities.texto_enriquecido import CodigoTexto, Problema
from app.core.entities.whatsmkt import ErrorWhatsmkt
from app.core.services.plataformas.whatsmkt import mensaje
from app.core.services.textos_guardados.contextos import (
    ContextoGuardado,
    TipoContenido,
    validador_de_texto_plano,
)

CLAVE_CONTEXTO_MENSAJE = "whatsmkt.mensaje"


def _problema(error: ErrorWhatsmkt) -> Problema:
    """Una regla del mensaje como problema del contexto: el codigo del modulo va adentro."""
    return Problema(
        CodigoTexto.REGLA_DEL_CONTEXTO,
        str(error),
        codigo_contexto=error.codigo.value,
        parametros=dict(error.parametros),
    )


def reglas_del_mensaje(tope: Callable[[], int]) -> Callable[[str], Sequence[Problema]]:
    """Las reglas que se aplican al guardar un mensaje, en este orden: emojis y largo. Se aplican
    las dos aunque falle la primera; `tope()` se llama en cada validacion."""

    def reglas(texto: str) -> list[Problema]:
        problemas = []
        for regla in (
            mensaje.validar_sin_emojis,
            lambda t: mensaje.validar_largo(t, tope()),
        ):
            try:
                regla(texto)
            except ErrorWhatsmkt as error:
                problemas.append(_problema(error))
        return problemas

    return reglas


def contexto_mensaje(tope: Callable[[], int]) -> ContextoGuardado:
    """El contexto `whatsmkt.mensaje`, con el tope de largo que da `tope()` en cada validacion."""
    return ContextoGuardado(
        clave=CLAVE_CONTEXTO_MENSAJE,
        etiqueta="Mensaje de WhatsMKT",
        tipo=TipoContenido.TEXTO_PLANO,
        # `maximo=None`: el largo lo mide la regla `mensaje_largo`, que cuenta [whatsapp] como el
        # enlace y da `{largo, maximo}`; el validador solo exige que no este vacio.
        validar=validador_de_texto_plano(None, reglas_del_mensaje(tope)),
    )

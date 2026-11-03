"""Reglas puras de la configuracion de WhatsMKT (RF-WM-04, 07 y 33).

Los topes (RF-WM-26 y 31) son enteros mayores que cero en bytes: los valida el modelo de la API
(422 generico) y la base con un CHECK; no tienen codigo."""

import re
from dataclasses import replace

from app.core.entities.telefono import numero_valido
from app.core.entities.whatsmkt import (
    PLANTILLA_NOMBRE_POR_DEFECTO,
    VARIABLES_PLANTILLA,
    CodigoWhatsmkt,
    ConfiguracionWhatsmkt,
    ErrorWhatsmkt,
    Horario,
)

_VARIABLE = re.compile(r"\{([^{}]*)\}")
_VALIDAS = ", ".join("{" + v + "}" for v in VARIABLES_PLANTILLA)


def horario_valido(horario: Horario) -> bool:
    """RF-WM-07: el inicio es estrictamente anterior al fin (sin franjas de cero minutos)."""
    return horario.inicio < horario.fin


def plantilla_valida(plantilla: str | None) -> str:
    """RF-WM-33 (DU-WM-6): texto fijo con `{fecha_corte}` y `{segmento}`; nada mas entre llaves.

    Vacia vuelve la de por defecto, como la de MOWA MES (RF-MM-25). Una variable desconocida o
    una llave suelta se rechaza diciendo cual.
    """
    limpia = (plantilla or "").strip()
    if not limpia:
        return PLANTILLA_NOMBRE_POR_DEFECTO
    for nombre in _VARIABLE.findall(limpia):
        if nombre not in VARIABLES_PLANTILLA:
            raise ErrorWhatsmkt(
                CodigoWhatsmkt.VARIABLE_INEXISTENTE,
                f"La variable {{{nombre}}} no existe; las validas son {_VALIDAS}",
                variable=f"{{{nombre}}}",
            )
    resto = _VARIABLE.sub("", limpia)
    if "{" in resto or "}" in resto:
        raise ErrorWhatsmkt(
            CodigoWhatsmkt.VARIABLE_INEXISTENTE,
            f"La plantilla tiene una llave sin cerrar; las variables validas son {_VALIDAS}",
            variable=resto.strip(),
        )
    return limpia


def whatsapp_valido(numero: str | None) -> str | None:
    """DU-WM-11 (a): el WhatsApp de contacto es de 9 digitos y empieza con 9 (RF-02). Sin texto
    queda sin numero (None); uno mal escrito es `whatsapp_invalido`."""
    limpio = (numero or "").strip()
    if not limpio:
        return None
    if not numero_valido(limpio):
        raise ErrorWhatsmkt(
            CodigoWhatsmkt.WHATSAPP_INVALIDO, "El WhatsApp debe tener 9 digitos y empezar con 9"
        )
    return limpio


def configuracion_valida(configuracion: ConfiguracionWhatsmkt) -> ConfiguracionWhatsmkt:
    """La configuracion con sus reglas aplicadas: horarios, plantilla (que queda limpia) y el
    WhatsApp de contacto.

    Un horario malo se rechaza nombrando la franja (`horarios`); si fallan las dos, las dos.
    """
    malos = [
        nombre
        for nombre, horario in (
            ("horario_1", configuracion.horario_1),
            ("horario_2", configuracion.horario_2),
        )
        if not horario_valido(horario)
    ]
    if malos:
        raise ErrorWhatsmkt(
            CodigoWhatsmkt.HORARIO_INVALIDO,
            f"{', '.join(malos)}: la hora de inicio tiene que ser anterior a la de fin",
            horarios=malos,
        )
    return replace(
        configuracion,
        plantilla_nombre=plantilla_valida(configuracion.plantilla_nombre),
        whatsapp_contacto=whatsapp_valido(configuracion.whatsapp_contacto),
    )

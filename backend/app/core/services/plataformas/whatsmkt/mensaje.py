"""Reglas puras del mensaje de WhatsMKT (RF-WM-17, RF-WM-24 a RF-WM-27).

El mensaje es un solo bloque de texto plano con marcadores `[$MACROn$]` que WhatsMKT reemplaza por
el valor de la macro n de cada fila (S-WM-6), y `[whatsapp]`, que el sistema reemplaza por el
enlace de contacto de la Caja al mostrarlo y copiarlo (DU-WM-11). No compila nada: lo valida y lo
muestra.

Cada regla lanza `ErrorWhatsmkt` con su codigo y sus parametros, o devuelve el resultado; ninguna
usa `Problema` del motor de texto (eso lo adapta la capa del contexto de textos guardados).
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.core.entities.whatsmkt import CodigoWhatsmkt, ErrorWhatsmkt

_MACRO = re.compile(r"\[\$MACRO(\d+)\$\]")
MARCADOR_WHATSAPP = "[whatsapp]"
ENLACE_WHATSAPP = "https://wa.me/+51"
# `[whatsapp]` se reemplaza por el enlace de contacto, de largo fijo: el prefijo mas los 9 digitos
# del numero. El tope de largo lo cuenta asi, como el contador del editor; las macros `[$MACROn$]`
# cuentan tal como estan escritas (DU-WM-3).
LARGO_ENLACE_WHATSAPP = len(ENLACE_WHATSAPP) + 9

# --- Emojis (RF-WM-24) ------------------------------------------------------------------------
# Una lista EXPLICITA de rangos, sin dependencias. El criterio: se rechaza lo que se dibuja como
# emoji sin que nadie lo pida (propiedad Emoji_Presentation de Unicode), todo el plano de los
# pictogramas, las banderas (indicadores regionales) y los modificadores de piel, mas las piezas
# que arman un emoji compuesto: el ZWJ, los selectores de variante y el cierre de teclas.
# Se ACEPTAN los simbolos que son texto salvo que se les pida lo contrario con el selector de
# variante (que si se rechaza): © ® ™ ✓ ✗ ← → ♥ ✔ ☎ ✈. Es la decision R-4 (DU provisional).
_RANGOS_EMOJI: tuple[tuple[int, int], ...] = (
    # Piezas de un emoji compuesto
    (0x200D, 0x200D),  # ZWJ, el unificador de ancho cero
    (0xFE0E, 0xFE0F),  # selectores de variante: texto y emoji
    (0x20E3, 0x20E3),  # cierre de tecla (1️⃣)
    (0xE0020, 0xE007F),  # etiquetas (banderas de Inglaterra, Escocia...)
    # Plano de los pictogramas
    (0x1F000, 0x1F2FF),  # mahjong, domino, cartas, letras y simbolos encerrados (incluye banderas)
    (0x1F300, 0x1F64F),  # pictogramas y simbolos varios, modificadores de piel y emoticonos
    (0x1F680, 0x1F6FF),  # transporte y mapas
    (0x1F7E0, 0x1F7EB),  # circulos y cuadrados de colores
    (0x1F90C, 0x1F9FF),  # simbolos y pictogramas suplementarios
    (0x1FA70, 0x1FAFF),  # simbolos y pictogramas extendidos
    # Emoji por defecto del plano basico
    (0x231A, 0x231B),  # reloj de pulsera y reloj de arena
    (0x23E9, 0x23EC),
    (0x23F0, 0x23F0),
    (0x23F3, 0x23F3),
    (0x25FD, 0x25FE),
    (0x2614, 0x2615),
    (0x2648, 0x2653),  # signos del zodiaco
    (0x267F, 0x267F),
    (0x2693, 0x2693),
    (0x26A1, 0x26A1),
    (0x26AA, 0x26AB),
    (0x26BD, 0x26BE),
    (0x26C4, 0x26C5),
    (0x26CE, 0x26CE),
    (0x26D4, 0x26D4),
    (0x26EA, 0x26EA),
    (0x26F2, 0x26F3),
    (0x26F5, 0x26F5),
    (0x26FA, 0x26FA),
    (0x26FD, 0x26FD),
    (0x2705, 0x2705),  # ✅
    (0x270A, 0x270B),
    (0x2728, 0x2728),
    (0x274C, 0x274C),  # ❌
    (0x274E, 0x274E),
    (0x2753, 0x2755),
    (0x2757, 0x2757),
    (0x2795, 0x2797),
    (0x27B0, 0x27B0),
    (0x27BF, 0x27BF),
    (0x2B1B, 0x2B1C),
    (0x2B50, 0x2B50),  # ⭐
    (0x2B55, 0x2B55),
    (0x3297, 0x3297),
    (0x3299, 0x3299),
)


def _es_emoji(caracter: str) -> bool:
    punto = ord(caracter)
    return any(desde <= punto <= hasta for desde, hasta in _RANGOS_EMOJI)


def validar_sin_emojis(texto: str) -> None:
    """RF-WM-24: lanza `mensaje_con_emoji` con el PRIMER caracter rechazado y su posicion.

    `posicion` cuenta caracteres Unicode desde 1 (no unidades UTF-16: un emoji de dos unidades
    cuenta uno). Las tildes, la `ñ`, la `ü`, `¿` y `¡` pasan.
    """
    for indice, caracter in enumerate(texto):
        if _es_emoji(caracter):
            raise ErrorWhatsmkt(
                CodigoWhatsmkt.MENSAJE_CON_EMOJI,
                f"No se admiten emojis: el primero es «{caracter}», en la posicion {indice + 1}",
                caracter=caracter,
                posicion=indice + 1,
            )


# --- Marcadores -------------------------------------------------------------------------------


@dataclass(frozen=True)
class MarcadoresDelMensaje:
    """Los `[$MACROn$]` que usa (sin repetir, de menor a mayor) y si usa `[whatsapp]`."""

    macros: tuple[int, ...]
    usa_whatsapp: bool


def marcadores_del_texto(texto: str) -> MarcadoresDelMensaje:
    return MarcadoresDelMensaje(
        macros=tuple(sorted({int(n) for n in _MACRO.findall(texto)})),
        usa_whatsapp=MARCADOR_WHATSAPP in texto,
    )


def validar_macros(texto: str, cantidad_de_macros: int) -> None:
    """RF-WM-25: lanza `macro_inexistente` con el PRIMER `[$MACROn$]` (en el orden del texto) cuya
    macro no existe: la definicion tiene `cantidad_de_macros` (1 a n).

    Una macro de la definicion que el mensaje no usa no es un error.
    """
    for encontrado in _MACRO.finditer(texto):
        if not 1 <= int(encontrado.group(1)) <= cantidad_de_macros:
            raise ErrorWhatsmkt(
                CodigoWhatsmkt.MACRO_INEXISTENTE,
                f"{encontrado.group(0)} no existe en la definicion elegida: tiene "
                f"{cantidad_de_macros} macros",
                macro=encontrado.group(0),
                n=cantidad_de_macros,
            )


def largo_del_mensaje(texto: str) -> int:
    """El largo que cuenta el tope (RF-WM-26): el texto con las macros sin reemplazar (DU-WM-3) y
    cada `[whatsapp]` como el enlace que sera (`LARGO_ENLACE_WHATSAPP`)."""
    usos = texto.count(MARCADOR_WHATSAPP)
    return len(texto) + usos * (LARGO_ENLACE_WHATSAPP - len(MARCADOR_WHATSAPP))


def validar_largo(texto: str, maximo: int) -> None:
    """RF-WM-26: lanza `mensaje_largo` si el texto pasa el tope, medido con `largo_del_mensaje`."""
    largo = largo_del_mensaje(texto)
    if largo > maximo:
        raise ErrorWhatsmkt(
            CodigoWhatsmkt.MENSAJE_LARGO,
            f"El mensaje tiene {largo} caracteres: el maximo es {maximo}",
            largo=largo,
            maximo=maximo,
        )


# --- Vista ------------------------------------------------------------------------------------


def enlace_whatsapp(numero: str) -> str:
    return f"{ENLACE_WHATSAPP}{numero}"


def vista(texto: str, macros_de_una_fila: Sequence[str | None], whatsapp: str | None = None) -> str:
    """El mensaje como lo vera el cliente (RF-WM-27): `[$MACROn$]` por el valor de la macro n de la
    fila y `[whatsapp]` por el enlace de contacto.

    Una macro que la fila no tiene (n fuera de rango) se deja tal cual, para que se vea el error;
    una vacia (None) se reemplaza por nada. Sin numero de WhatsApp, `[whatsapp]` queda tal cual.
    """

    def reemplazo(encontrado: re.Match[str]) -> str:
        n = int(encontrado.group(1))
        if not 1 <= n <= len(macros_de_una_fila):
            return encontrado.group(0)
        return macros_de_una_fila[n - 1] or ""

    # Primero el enlace y despues las macros, en una sola pasada cada uno: el valor de una macro es
    # un dato de la fila y no se vuelve a interpretar como marcador.
    if whatsapp:
        texto = texto.replace(MARCADOR_WHATSAPP, enlace_whatsapp(whatsapp))
    return _MACRO.sub(reemplazo, texto)

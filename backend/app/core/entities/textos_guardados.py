"""Textos guardados y versionados por contexto (RF-69, T-HI-B4).

Un texto se guarda con un nombre dentro de un **contexto** que declara el modulo que lo usa (por
ejemplo, el mensaje de WhatsMKT). Se versiona como una definicion de columnas (RF-51): una version
no se modifica, un cambio crea la siguiente (la vigente es la ultima) y `usada_en` marca la primera
vez que algo la uso. El nombre es unico dentro de su contexto, sin distinguir mayusculas ni los
espacios de los extremos.

Un texto deshabilitado deja de ofrecerse para lo nuevo (no sale en el listado por defecto y no
admite versiones nuevas), pero lo que ya lo uso lo sigue leyendo. Un texto con alguna version usada
no se elimina: solo se deshabilita.

El contenido es siempre un objeto JSON; que contiene y como se valida lo declara el contexto
(`services/textos_guardados/contextos.py`). El speech de MOWA MES conserva sus propias tablas y no
migra a esta capacidad.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

LARGO_MAXIMO_NOMBRE = 120


@dataclass(frozen=True)
class VersionTexto:
    """Una version: `contenido` es un objeto JSON, tal como lo valido el contexto."""

    numero: int
    contenido: Mapping[str, Any]
    usada_en: datetime | None
    creado_en: datetime

    @property
    def usada(self) -> bool:
        return self.usada_en is not None


@dataclass(frozen=True)
class TextoGuardado:
    """El texto con todas sus versiones, de la primera a la ultima (la vigente)."""

    id: int
    contexto: str
    nombre: str
    creado_en: datetime
    actualizado_en: datetime
    deshabilitado_en: datetime | None
    versiones: tuple[VersionTexto, ...]

    @property
    def deshabilitado(self) -> bool:
        return self.deshabilitado_en is not None

    @property
    def vigente(self) -> VersionTexto:
        return max(self.versiones, key=lambda version: version.numero)

    @property
    def alguna_usada(self) -> bool:
        return any(version.usada for version in self.versiones)

    def version(self, numero: int | None) -> VersionTexto | None:
        """La version `numero`, o la vigente si no se pide una; None si no existe."""
        if numero is None:
            return self.vigente
        return next((v for v in self.versiones if v.numero == numero), None)


@dataclass(frozen=True)
class ResumenTexto:
    """Una fila del listado: sin el contenido de las versiones."""

    id: int
    contexto: str
    nombre: str
    version_vigente: int
    cantidad_versiones: int
    actualizado_en: datetime
    vigente_usada: bool
    deshabilitado_en: datetime | None
    # Verdadero si ninguna version se uso (no solo la vigente): solo entonces se puede eliminar.
    eliminable: bool


class TextoNoEncontrado(Exception):
    def __init__(self, texto_id: int) -> None:
        super().__init__(f"No existe el texto guardado {texto_id}")
        self.texto_id = texto_id


class VersionDeTextoNoEncontrada(Exception):
    def __init__(self, texto_id: int, numero: int) -> None:
        super().__init__(f"El texto guardado {texto_id} no tiene la version {numero}")
        self.texto_id = texto_id
        self.numero = numero


class NombreDeTextoRepetido(Exception):
    def __init__(self, contexto: str, nombre: str) -> None:
        super().__init__(f"Ya existe un texto llamado {nombre!r} en el contexto {contexto!r}")
        self.contexto = contexto
        self.nombre = nombre


class TextoConVersionesUsadas(Exception):
    """No se elimina un texto del que alguna version ya se uso: solo se deshabilita."""

    def __init__(self, texto_id: int) -> None:
        super().__init__(
            f"El texto guardado {texto_id} tiene versiones usadas: no se puede eliminar, "
            "solo deshabilitar"
        )
        self.texto_id = texto_id


class TextoDeshabilitado(Exception):
    """Un texto deshabilitado no admite versiones nuevas."""

    def __init__(self, texto_id: int) -> None:
        super().__init__(f"El texto guardado {texto_id} esta deshabilitado")
        self.texto_id = texto_id

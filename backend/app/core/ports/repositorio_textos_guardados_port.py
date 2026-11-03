"""Puerto de persistencia de los textos guardados y sus versiones (RF-69)."""

from collections.abc import Mapping
from typing import Any, Protocol

from app.core.entities.textos_guardados import ResumenTexto, TextoGuardado, VersionTexto


class RepositorioTextosGuardadosPort(Protocol):
    def listar(self, contexto: str, incluir_deshabilitados: bool = False) -> list[ResumenTexto]:
        """Los textos del contexto, ordenados por nombre. Sin los deshabilitados por defecto."""
        ...

    def obtener(self, texto_id: int) -> TextoGuardado | None:
        """El texto con todas sus versiones, o None si no existe."""
        ...

    def crear(self, contexto: str, nombre: str, contenido: Mapping[str, Any]) -> TextoGuardado:
        """Crea el texto con su version 1. Lanza NombreDeTextoRepetido si el contexto ya tiene
        ese nombre, sin distinguir mayusculas."""
        ...

    def agregar_version(self, texto_id: int, contenido: Mapping[str, Any]) -> VersionTexto | None:
        """Crea la version siguiente y la deja vigente. None si el texto no existe; lanza
        TextoDeshabilitado si esta deshabilitado."""
        ...

    def renombrar(self, texto_id: int, nombre: str) -> TextoGuardado | None:
        """Cambia solo el nombre (RF-56): ninguna version se toca y `actualizado_en` se mueve.

        Si el nombre ya es exactamente el actual no escribe nada. Lanza NombreDeTextoRepetido si
        otro texto del contexto tiene ese nombre sin distinguir mayusculas (el cambio de
        mayusculas del propio texto si se permite). None si no existe.
        """
        ...

    def deshabilitar(self, texto_id: int) -> TextoGuardado | None:
        """Marca `deshabilitado_en` la primera vez y no lo cambia despues. None si no existe."""
        ...

    def habilitar(self, texto_id: int) -> TextoGuardado | None:
        """Limpia `deshabilitado_en`. Si ya esta habilitado no escribe nada. None si no existe."""
        ...

    def eliminar(self, texto_id: int) -> bool:
        """Borra el texto y sus versiones. False si no existe; lanza TextoConVersionesUsadas si
        alguna version tiene `usada_en`."""
        ...

    def marcar_version_usada(self, texto_id: int, numero: int) -> bool:
        """Marca `usada_en` la primera vez y no la cambia despues. False si no existe."""
        ...

"""Puerto de persistencia del mapeador de encabezados: borradores y mapeos recordados (§5).

La sesion de las cargas (`SesionCargasPort`) tambien cumple `SesionMapeadorPort`: confirmar un
borrador crea la carga, guarda los recordados y borra el borrador en UNA transaccion.
"""

from collections.abc import Mapping, Sequence
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Protocol

from app.core.entities.borrador import DatosBorrador, NuevoBorrador
from app.core.entities.campos_adicionales import CampoAdicional

# (encabezado normalizado, ocurrencia) -> campo, o None para «No cargar» (RF-61, M-1).
ClaveRecordada = tuple[str, int]
Recordados = Mapping[ClaveRecordada, str | None]


class SesionMapeadorPort(Protocol):
    """Operaciones dentro de una transaccion: se confirman juntas o se revierten juntas."""

    def crear_borrador(self, nuevo: NuevoBorrador, contenido: bytes) -> DatosBorrador: ...

    def obtener_borrador(self, borrador_id: int, bloquear: bool = False) -> DatosBorrador | None:
        """El borrador sin su contenido. Con `bloquear`, lo toma con `SELECT ... FOR UPDATE`: una
        segunda confirmacion espera y, al entrar, ya no lo encuentra."""
        ...

    def contenido_de_borrador(self, borrador_id: int) -> bytes: ...

    def reemplazar_analisis(
        self, borrador_id: int, opciones: dict, analisis: dict
    ) -> DatosBorrador | None:
        """Cambia las opciones de lectura y el analisis (volver a analizar). None si no existe."""
        ...

    def borrar_borrador(self, borrador_id: int) -> bool:
        """True si existia."""
        ...

    def borrar_borradores_vencidos(self, antes_de: datetime) -> int:
        """Borra los creados antes de `antes_de` y devuelve cuantos."""
        ...

    def recordados(self, catalogo_id: str) -> dict[ClaveRecordada, str | None]:
        """Lo recordado de un catalogo: lo de otro catalogo no se mezcla (RF-63)."""
        ...

    def guardar_recordados(
        self, catalogo_id: str, asignaciones: Recordados, ahora: datetime
    ) -> None:
        """Upsert por lote: lo que ya estaba se actualiza y lo nuevo se agrega (RF-61)."""
        ...

    # --- campos adicionales (RF-64 a RF-66) ---

    def bloquear_adicionales(self) -> None:
        """Serializa a quienes crean o renombran campos adicionales hasta el fin de la transaccion:
        dos a la vez no pueden elegir el mismo nombre tecnico ni el mismo nombre legible."""
        ...

    def adicionales(self, catalogo_id: str) -> Sequence[CampoAdicional]:
        """Las definiciones del catalogo, archivadas incluidas, en el orden en que se crearon."""
        ...

    def crear_adicional(
        self, catalogo_id: str, campo: CampoAdicional, ahora: datetime
    ) -> CampoAdicional:
        """Guarda la definicion. El nombre legible es unico por catalogo, comparado normalizado."""
        ...

    def actualizar_adicional(
        self,
        nombre: str,
        nombre_legible: str | None,
        archivado: bool | None,
        ahora: datetime,
    ) -> CampoAdicional | None:
        """Cambia solo lo que viene (renombrar, archivar o reactivar); el nombre tecnico y el tipo
        no cambian nunca. None si no existe."""
        ...


class RepositorioMapeadorPort(Protocol):
    def transaccion(self) -> AbstractContextManager[SesionMapeadorPort]:
        """Abre una transaccion: confirma al salir sin error, revierte si hay excepcion."""
        ...

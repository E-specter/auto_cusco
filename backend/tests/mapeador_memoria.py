"""Dobles en memoria de los borradores y los recordados del mapeador (T-MAP-B3a).

Se comportan como el adaptador PostgreSQL en lo que el caso de uso necesita: los ids los asigna el
repositorio, `obtener_borrador` devuelve una copia, lo recordado se separa por catalogo y se
actualiza por (encabezado normalizado, ocurrencia), y la transaccion revierte todo ante una
excepcion. `FOR UPDATE` no tiene que hacer nada aqui: lo que se prueba es que la segunda
confirmacion de un borrador ya no lo encuentra.
"""

import copy
from collections.abc import Sequence
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
from typing import Any

from app.core.entities.borrador import DatosBorrador, NuevoBorrador
from app.core.entities.campos_adicionales import CampoAdicional
from app.core.ports.repositorio_campos_adicionales_port import RepositorioCamposAdicionalesPort
from app.core.services.ingesta_sabana.catalogo import CATALOGO_SABANA


class SesionMapeadorEnMemoria:
    """Lo del mapeador de `SesionMapeadorPort`, para mezclarlo con otro doble o usarlo solo."""

    def _iniciar_mapeador(self) -> None:
        self.borradores: dict[int, DatosBorrador] = {}
        self.contenidos_de_borradores: dict[int, bytes] = {}
        self.mapeos_recordados: dict[tuple[str, str, int], tuple[str | None, datetime]] = {}
        self.bloqueos_de_borradores: list[int] = []
        # (catalogo_id, definicion) en el orden en que se crearon; nunca se borra una.
        self.campos_adicionales: list[tuple[str, CampoAdicional]] = []
        self.bloqueos_de_adicionales = 0
        self.siguiente_id_de_borrador = 1  # como una identidad: nunca se reutiliza

    def crear_borrador(self, nuevo: NuevoBorrador, contenido: bytes) -> DatosBorrador:
        borrador_id = self.siguiente_id_de_borrador
        self.siguiente_id_de_borrador += 1
        self.borradores[borrador_id] = DatosBorrador(
            id=borrador_id,
            catalogo_id=nuevo.catalogo_id,
            nombre_archivo=nuevo.nombre_archivo,
            huella=nuevo.huella,
            tamano_bytes=nuevo.tamano_bytes,
            opciones=copy.deepcopy(nuevo.opciones),
            analisis=copy.deepcopy(nuevo.analisis),
            creado_en=nuevo.creado_en,
        )
        self.contenidos_de_borradores[borrador_id] = contenido
        return self.borradores[borrador_id]

    def obtener_borrador(self, borrador_id: int, bloquear: bool = False) -> DatosBorrador | None:
        if bloquear:
            self.bloqueos_de_borradores.append(borrador_id)
        borrador = self.borradores.get(borrador_id)
        return None if borrador is None else copy.deepcopy(borrador)

    def contenido_de_borrador(self, borrador_id: int) -> bytes:
        return self.contenidos_de_borradores[borrador_id]

    def reemplazar_analisis(
        self, borrador_id: int, opciones: dict[str, Any], analisis: dict[str, Any]
    ) -> DatosBorrador | None:
        if borrador_id not in self.borradores:
            return None
        self.borradores[borrador_id] = replace(
            self.borradores[borrador_id],
            opciones=copy.deepcopy(opciones),
            analisis=copy.deepcopy(analisis),
        )
        return copy.deepcopy(self.borradores[borrador_id])

    def borrar_borrador(self, borrador_id: int) -> bool:
        self.contenidos_de_borradores.pop(borrador_id, None)
        return self.borradores.pop(borrador_id, None) is not None

    def borrar_borradores_vencidos(self, antes_de: datetime) -> int:
        vencidos = [i for i, b in self.borradores.items() if b.creado_en < antes_de]
        for borrador_id in vencidos:
            self.borrar_borrador(borrador_id)
        return len(vencidos)

    def recordados(self, catalogo_id: str) -> dict[tuple[str, int], str | None]:
        return {
            (normalizado, ocurrencia): campo
            for (catalogo, normalizado, ocurrencia), (campo, _) in self.mapeos_recordados.items()
            if catalogo == catalogo_id
        }

    def guardar_recordados(self, catalogo_id: str, asignaciones, ahora: datetime) -> None:
        for (normalizado, ocurrencia), campo in asignaciones.items():
            self.mapeos_recordados[(catalogo_id, normalizado, ocurrencia)] = (campo, ahora)

    def bloquear_adicionales(self) -> None:
        self.bloqueos_de_adicionales += 1

    def adicionales(self, catalogo_id: str) -> Sequence[CampoAdicional]:
        return tuple(c for catalogo, c in self.campos_adicionales if catalogo == catalogo_id)

    def crear_adicional(
        self, catalogo_id: str, campo: CampoAdicional, ahora: datetime
    ) -> CampoAdicional:
        self.campos_adicionales.append((catalogo_id, campo))
        return campo

    def actualizar_adicional(
        self,
        nombre: str,
        nombre_legible: str | None,
        archivado: bool | None,
        ahora: datetime,
    ) -> CampoAdicional | None:
        for i, (catalogo, campo) in enumerate(self.campos_adicionales):
            if campo.nombre == nombre:
                cambios: dict[str, Any] = {}
                if nombre_legible is not None:
                    cambios["nombre_legible"] = nombre_legible
                if archivado is not None:
                    cambios["archivado"] = archivado
                self.campos_adicionales[i] = (catalogo, replace(campo, **cambios))
                return self.campos_adicionales[i][1]
        return None


class AdicionalesDe(RepositorioCamposAdicionalesPort):
    """El puerto de lectura del catalogo, sobre lo que guarda un repositorio de estos dobles: lo que
    crea el mapeador lo ve la cartera."""

    def __init__(
        self, repositorio: SesionMapeadorEnMemoria, catalogo_id: str = CATALOGO_SABANA.id
    ) -> None:
        self._repositorio = repositorio
        self._catalogo_id = catalogo_id

    def listar(self) -> Sequence[CampoAdicional]:
        return self._repositorio.adicionales(self._catalogo_id)


class RepositorioMapeadorEnMemoria(SesionMapeadorEnMemoria):
    """Repositorio y sesion a la vez; `transaccion` revierte todo ante una excepcion."""

    def __init__(self) -> None:
        self._iniciar_mapeador()

    @contextmanager
    def transaccion(self):
        respaldo = copy.deepcopy(self.__dict__)
        try:
            yield self
        except BaseException:
            self.__dict__.clear()
            self.__dict__.update(respaldo)
            raise

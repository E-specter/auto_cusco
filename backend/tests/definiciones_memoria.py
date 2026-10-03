"""Repositorio de definiciones en memoria: el doble de las pruebas de nucleo y de API.

Cumple lo que promete el puerto sin base: nombre unico sin distinguir mayusculas, versiones
numeradas desde 1, `usada_en` que se marca una vez y no se cambia.
"""

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from app.core.entities.definiciones_columnas import (
    DefinicionGuardada,
    NombreDeDefinicionRepetido,
    ResumenDefinicion,
    VersionDefinicion,
    normalizar_nombre,
)


class RepositorioEnMemoria:
    def __init__(self) -> None:
        self.definiciones: dict[int, DefinicionGuardada] = {}
        self._siguiente = 1
        self._reloj = 0

    def _ahora(self) -> datetime:
        self._reloj += 1
        return datetime(2099, 1, 1, tzinfo=UTC).replace(
            second=self._reloj % 60, minute=self._reloj // 60
        )

    def listar(self) -> list[ResumenDefinicion]:
        resumenes = [
            ResumenDefinicion(
                id=d.id,
                nombre=d.nombre,
                version_vigente=d.vigente.numero,
                cantidad_versiones=len(d.versiones),
                actualizado_en=d.actualizado_en,
                vigente_usada=d.vigente.usada,
            )
            for d in self.definiciones.values()
        ]
        return sorted(resumenes, key=lambda r: (normalizar_nombre(r.nombre), r.id))

    def obtener(self, definicion_id: int) -> DefinicionGuardada | None:
        return self.definiciones.get(definicion_id)

    def crear(self, nombre: str, contenido: Mapping[str, Any]) -> DefinicionGuardada:
        if any(
            normalizar_nombre(d.nombre) == normalizar_nombre(nombre)
            for d in self.definiciones.values()
        ):
            raise NombreDeDefinicionRepetido(nombre)
        ahora = self._ahora()
        definicion = DefinicionGuardada(
            id=self._siguiente,
            nombre=nombre,
            creado_en=ahora,
            actualizado_en=ahora,
            versiones=(VersionDefinicion(1, dict(contenido), None, ahora),),
        )
        self.definiciones[definicion.id] = definicion
        self._siguiente += 1
        return definicion

    def agregar_version(
        self, definicion_id: int, contenido: Mapping[str, Any]
    ) -> VersionDefinicion | None:
        definicion = self.definiciones.get(definicion_id)
        if definicion is None:
            return None
        ahora = self._ahora()
        version = VersionDefinicion(definicion.vigente.numero + 1, dict(contenido), None, ahora)
        self.definiciones[definicion_id] = replace(
            definicion, versiones=(*definicion.versiones, version), actualizado_en=ahora
        )
        return version

    def reemplazar_contenido(
        self, definicion_id: int, numero: int, contenido: Mapping[str, Any]
    ) -> None:
        """Solo para pruebas: simula que lo guardado ya no encaja con el catalogo actual."""
        definicion = self.definiciones[definicion_id]
        self.definiciones[definicion_id] = replace(
            definicion,
            versiones=tuple(
                replace(v, contenido=dict(contenido)) if v.numero == numero else v
                for v in definicion.versiones
            ),
        )

    def marcar_version_usada(self, definicion_id: int, numero: int) -> bool:
        definicion = self.definiciones.get(definicion_id)
        version = definicion.version(numero) if definicion else None
        if definicion is None or version is None:
            return False
        if version.usada_en is None:
            usada = replace(version, usada_en=self._ahora())
            self.definiciones[definicion_id] = replace(
                definicion,
                versiones=tuple(usada if v.numero == numero else v for v in definicion.versiones),
            )
        return True

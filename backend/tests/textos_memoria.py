"""Repositorio de textos guardados en memoria: el doble de las pruebas de nucleo y de API.

Cumple lo que promete el puerto sin base: nombre unico por contexto sin distinguir mayusculas,
versiones numeradas desde 1, `usada_en` que se marca una vez y no se cambia, y los mismos errores.
"""

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from app.core.entities.nombres import normalizar_nombre
from app.core.entities.textos_guardados import (
    NombreDeTextoRepetido,
    ResumenTexto,
    TextoConVersionesUsadas,
    TextoDeshabilitado,
    TextoGuardado,
    VersionTexto,
)


class RepositorioTextosEnMemoria:
    def __init__(self) -> None:
        self.textos: dict[int, TextoGuardado] = {}
        self._siguiente = 1
        self._reloj = 0

    def _ahora(self) -> datetime:
        self._reloj += 1
        return datetime(2099, 1, 1, tzinfo=UTC).replace(
            second=self._reloj % 60, minute=self._reloj // 60
        )

    def _repetido(self, contexto: str, nombre: str, salvo: int | None = None) -> bool:
        return any(
            t.id != salvo
            and t.contexto == contexto
            and normalizar_nombre(t.nombre) == normalizar_nombre(nombre)
            for t in self.textos.values()
        )

    def listar(self, contexto: str, incluir_deshabilitados: bool = False) -> list[ResumenTexto]:
        resumenes = [
            ResumenTexto(
                id=t.id,
                contexto=t.contexto,
                nombre=t.nombre,
                version_vigente=t.vigente.numero,
                cantidad_versiones=len(t.versiones),
                actualizado_en=t.actualizado_en,
                vigente_usada=t.vigente.usada,
                deshabilitado_en=t.deshabilitado_en,
                eliminable=not t.alguna_usada,
            )
            for t in self.textos.values()
            if t.contexto == contexto and (incluir_deshabilitados or not t.deshabilitado)
        ]
        return sorted(resumenes, key=lambda r: (normalizar_nombre(r.nombre), r.id))

    def obtener(self, texto_id: int) -> TextoGuardado | None:
        return self.textos.get(texto_id)

    def crear(self, contexto: str, nombre: str, contenido: Mapping[str, Any]) -> TextoGuardado:
        if self._repetido(contexto, nombre):
            raise NombreDeTextoRepetido(contexto, nombre)
        ahora = self._ahora()
        texto = TextoGuardado(
            id=self._siguiente,
            contexto=contexto,
            nombre=nombre,
            creado_en=ahora,
            actualizado_en=ahora,
            deshabilitado_en=None,
            versiones=(VersionTexto(1, dict(contenido), None, ahora),),
        )
        self.textos[texto.id] = texto
        self._siguiente += 1
        return texto

    def agregar_version(self, texto_id: int, contenido: Mapping[str, Any]) -> VersionTexto | None:
        texto = self.textos.get(texto_id)
        if texto is None:
            return None
        if texto.deshabilitado:
            raise TextoDeshabilitado(texto_id)
        ahora = self._ahora()
        version = VersionTexto(texto.vigente.numero + 1, dict(contenido), None, ahora)
        self.textos[texto_id] = replace(
            texto, versiones=(*texto.versiones, version), actualizado_en=ahora
        )
        return version

    def renombrar(self, texto_id: int, nombre: str) -> TextoGuardado | None:
        texto = self.textos.get(texto_id)
        if texto is None:
            return None
        if self._repetido(texto.contexto, nombre, salvo=texto_id):
            raise NombreDeTextoRepetido(texto.contexto, nombre)
        if texto.nombre == nombre:
            return texto
        renombrado = replace(texto, nombre=nombre, actualizado_en=self._ahora())
        self.textos[texto_id] = renombrado
        return renombrado

    def deshabilitar(self, texto_id: int) -> TextoGuardado | None:
        texto = self.textos.get(texto_id)
        if texto is None:
            return None
        if texto.deshabilitado:
            return texto
        ahora = self._ahora()
        deshabilitado = replace(texto, deshabilitado_en=ahora, actualizado_en=ahora)
        self.textos[texto_id] = deshabilitado
        return deshabilitado

    def habilitar(self, texto_id: int) -> TextoGuardado | None:
        texto = self.textos.get(texto_id)
        if texto is None:
            return None
        if not texto.deshabilitado:
            return texto
        habilitado = replace(texto, deshabilitado_en=None, actualizado_en=self._ahora())
        self.textos[texto_id] = habilitado
        return habilitado

    def eliminar(self, texto_id: int) -> bool:
        texto = self.textos.get(texto_id)
        if texto is None:
            return False
        if texto.alguna_usada:
            raise TextoConVersionesUsadas(texto_id)
        del self.textos[texto_id]
        return True

    def marcar_version_usada(self, texto_id: int, numero: int) -> bool:
        texto = self.textos.get(texto_id)
        version = texto.version(numero) if texto else None
        if texto is None or version is None:
            return False
        if version.usada_en is None:
            usada = replace(version, usada_en=self._ahora())
            self.textos[texto_id] = replace(
                texto,
                versiones=tuple(usada if v.numero == numero else v for v in texto.versiones),
            )
        return True

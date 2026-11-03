"""Repositorio de WhatsMKT en memoria para las pruebas de la biblioteca de adjuntos.

Imita lo que importa del de PostgreSQL: la huella se calcula con el contenido, un archivo repetido
devuelve el existente (archivado o no) y listar no trae el contenido.
"""

import hashlib
from dataclasses import replace
from datetime import UTC, datetime

from app.core.entities.whatsmkt import AdjuntoWhatsmkt, ConfiguracionWhatsmkt, TipoAdjunto

MOMENTO = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)


class RepositorioAdjuntosFalso:
    def __init__(self, configuracion: ConfiguracionWhatsmkt | None = None) -> None:
        self.configuracion = configuracion or ConfiguracionWhatsmkt(actualizado_en=MOMENTO)
        self.adjuntos: dict[int, AdjuntoWhatsmkt] = {}
        self.contenidos: dict[int, bytes] = {}
        self.escrituras = 0

    def obtener_configuracion(self):
        return self.configuracion

    def guardar_adjunto(self, tipo: TipoAdjunto, nombre: str, contenido: bytes):
        huella = hashlib.sha256(contenido).hexdigest()
        existente = self.buscar_adjunto_por_huella(huella)
        if existente is not None:
            return existente
        self.escrituras += 1
        nuevo = AdjuntoWhatsmkt(
            len(self.adjuntos) + 1, tipo, nombre, len(contenido), huella, MOMENTO
        )
        self.adjuntos[nuevo.id] = nuevo
        self.contenidos[nuevo.id] = contenido
        return nuevo

    def buscar_adjunto_por_huella(self, huella: str):
        return next((a for a in self.adjuntos.values() if a.huella == huella), None)

    def listar_adjuntos(self, archivados: bool = False):
        return [a for a in self.adjuntos.values() if (a.archivado_en is not None) == archivados]

    def obtener_adjunto(self, adjunto_id: int):
        return self.adjuntos.get(adjunto_id)

    def leer_contenido_adjunto(self, adjunto_id: int):
        return self.contenidos.get(adjunto_id)

    def archivar_adjunto(self, adjunto_id: int):
        actual = self.adjuntos.get(adjunto_id)
        if actual is None:
            return None
        if actual.archivado_en is None:
            actual = replace(actual, archivado_en=MOMENTO)
            self.adjuntos[adjunto_id] = actual
        return actual

    def desarchivar_adjunto(self, adjunto_id: int):
        actual = self.adjuntos.get(adjunto_id)
        if actual is None:
            return None
        self.adjuntos[adjunto_id] = replace(actual, archivado_en=None)
        return self.adjuntos[adjunto_id]

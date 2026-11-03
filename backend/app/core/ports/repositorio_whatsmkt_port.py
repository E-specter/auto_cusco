"""Puerto de persistencia del modulo WhatsMKT: configuracion, segmentos y biblioteca de adjuntos."""

from typing import Protocol

from app.core.entities.whatsmkt import (
    AdjuntoWhatsmkt,
    ConfiguracionWhatsmkt,
    SegmentoWhatsmkt,
    TipoAdjunto,
)


class RepositorioWhatsmktPort(Protocol):
    def obtener_configuracion(self) -> ConfiguracionWhatsmkt: ...

    def guardar_configuracion(
        self, configuracion: ConfiguracionWhatsmkt
    ) -> ConfiguracionWhatsmkt: ...

    def listar_segmentos(self) -> list[SegmentoWhatsmkt]:
        """De menor a mayor (por `orden`)."""
        ...

    def reemplazar_segmentos(self, segmentos: list[SegmentoWhatsmkt]) -> list[SegmentoWhatsmkt]:
        """Edita etiqueta, limites y orden de los segmentos (ya existen, son fijos) en una sola
        transaccion: si algo falla, queda la tabla anterior."""
        ...

    def guardar_adjunto(self, tipo: TipoAdjunto, nombre: str, contenido: bytes) -> AdjuntoWhatsmkt:
        """Guarda el archivo; si su huella (SHA-256) ya existe devuelve el existente, archivado o
        no, sin tocarlo. La huella la calcula el repositorio."""
        ...

    def listar_adjuntos(self, archivados: bool = False) -> list[AdjuntoWhatsmkt]:
        """Los activos o los archivados, sin contenido, del mas reciente al mas antiguo."""
        ...

    def obtener_adjunto(self, adjunto_id: int) -> AdjuntoWhatsmkt | None: ...

    def leer_contenido_adjunto(self, adjunto_id: int) -> bytes | None: ...

    def archivar_adjunto(self, adjunto_id: int) -> AdjuntoWhatsmkt | None:
        """Repetirlo conserva la primera fecha. None si no existe."""
        ...

    def desarchivar_adjunto(self, adjunto_id: int) -> AdjuntoWhatsmkt | None: ...

"""Casos de uso de la configuracion de WhatsMKT: valores de la plataforma y segmentos (RF-WM-04)."""

from collections.abc import Sequence

from app.core.entities.whatsmkt import (
    CodigoWhatsmkt,
    ConfiguracionWhatsmkt,
    DefinicionDefectoNoExiste,
    ErrorWhatsmkt,
    SegmentoWhatsmkt,
)
from app.core.ports.repositorio_definiciones_port import RepositorioDefinicionesPort
from app.core.ports.repositorio_whatsmkt_port import RepositorioWhatsmktPort
from app.core.services.plataformas.whatsmkt import configuracion, segmentos
from app.core.services.plataformas.whatsmkt.plataforma import CLAVE


class ConfiguracionWhatsmktService:
    def __init__(
        self, repositorio: RepositorioWhatsmktPort, definiciones: RepositorioDefinicionesPort
    ) -> None:
        self._repositorio = repositorio
        self._definiciones = definiciones

    def obtener_configuracion(self) -> ConfiguracionWhatsmkt:
        return self._repositorio.obtener_configuracion()

    def guardar_configuracion(self, nueva: ConfiguracionWhatsmkt) -> ConfiguracionWhatsmkt:
        valida = configuracion.configuracion_valida(nueva)
        self._revisar_definicion_por_defecto(valida.definicion_defecto_id)
        return self._repositorio.guardar_configuracion(valida)

    def _revisar_definicion_por_defecto(self, definicion_id: int | None) -> None:
        """RF-WM-04: la definicion por defecto existe y es de plataforma `whatsmkt` (RF-72)."""
        if definicion_id is None:
            return
        definicion = self._definiciones.obtener(definicion_id)
        if definicion is None:
            raise DefinicionDefectoNoExiste(definicion_id)
        if definicion.plataforma != CLAVE:
            raise ErrorWhatsmkt(
                CodigoWhatsmkt.DEFINICION_NO_WHATSMKT,
                f"La definicion {definicion.nombre!r} no es de la plataforma WhatsMKT",
            )

    def listar_segmentos(self) -> list[SegmentoWhatsmkt]:
        return self._repositorio.listar_segmentos()

    def reemplazar_segmentos(self, nuevos: Sequence[SegmentoWhatsmkt]) -> list[SegmentoWhatsmkt]:
        return self._repositorio.reemplazar_segmentos(list(segmentos.segmentos_validos(nuevos)))

"""Casos de uso de la configuracion de WhatsMKT: valores de la plataforma y segmentos (RF-WM-04)."""

from collections.abc import Sequence

from app.core.entities.whatsmkt import ConfiguracionWhatsmkt, SegmentoWhatsmkt
from app.core.ports.repositorio_whatsmkt_port import RepositorioWhatsmktPort
from app.core.services.plataformas.whatsmkt import configuracion, segmentos


class ConfiguracionWhatsmktService:
    def __init__(self, repositorio: RepositorioWhatsmktPort) -> None:
        self._repositorio = repositorio

    def obtener_configuracion(self) -> ConfiguracionWhatsmkt:
        return self._repositorio.obtener_configuracion()

    def guardar_configuracion(self, nueva: ConfiguracionWhatsmkt) -> ConfiguracionWhatsmkt:
        return self._repositorio.guardar_configuracion(configuracion.configuracion_valida(nueva))

    def listar_segmentos(self) -> list[SegmentoWhatsmkt]:
        return self._repositorio.listar_segmentos()

    def reemplazar_segmentos(self, nuevos: Sequence[SegmentoWhatsmkt]) -> list[SegmentoWhatsmkt]:
        return self._repositorio.reemplazar_segmentos(list(segmentos.segmentos_validos(nuevos)))

"""Casos de uso de la configuracion de WhatsMKT: valores de la plataforma y segmentos (RF-WM-04)."""

from collections.abc import Sequence

from app.core.entities.whatsmkt import (
    CodigoWhatsmkt,
    ConfiguracionWhatsmkt,
    DefinicionDefectoNoExiste,
    ErrorWhatsmkt,
    SegmentoWhatsmkt,
    TextoDeSegmentoInvalido,
)
from app.core.ports.repositorio_definiciones_port import RepositorioDefinicionesPort
from app.core.ports.repositorio_textos_guardados_port import RepositorioTextosGuardadosPort
from app.core.ports.repositorio_whatsmkt_port import RepositorioWhatsmktPort
from app.core.services.plataformas.whatsmkt import configuracion, segmentos
from app.core.services.plataformas.whatsmkt.contexto import CLAVE_CONTEXTO_MENSAJE
from app.core.services.plataformas.whatsmkt.plataforma import CLAVE


class ConfiguracionWhatsmktService:
    def __init__(
        self,
        repositorio: RepositorioWhatsmktPort,
        definiciones: RepositorioDefinicionesPort,
        textos: RepositorioTextosGuardadosPort,
    ) -> None:
        self._repositorio = repositorio
        self._definiciones = definiciones
        self._textos = textos

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
        validos = segmentos.segmentos_validos(nuevos)
        for segmento in validos:
            self._revisar_texto_del_segmento(segmento)
        return self._repositorio.reemplazar_segmentos(list(validos))

    def _revisar_texto_del_segmento(self, segmento: SegmentoWhatsmkt) -> None:
        """RF-WM-19: el mensaje del segmento es un texto del contexto `whatsmkt.mensaje`."""
        if segmento.texto_guardado_id is None:
            return
        texto = self._textos.obtener(segmento.texto_guardado_id)
        if texto is None:
            raise TextoDeSegmentoInvalido(segmento.clave, segmento.texto_guardado_id, "no existe")
        if texto.contexto != CLAVE_CONTEXTO_MENSAJE:
            raise TextoDeSegmentoInvalido(
                segmento.clave,
                segmento.texto_guardado_id,
                f"no es un mensaje de WhatsMKT (es del contexto {texto.contexto!r})",
            )

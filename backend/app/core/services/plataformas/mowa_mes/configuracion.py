"""Casos de uso de configuracion del conector MOWA MES: limite, WhatsApp y speech.

Una version de speech usada por una campana no se modifica (RF-MM-17), y el
Speech original tampoco: es la referencia de RF-MM-18. Editar cualquiera de las
dos crea una version nueva.
"""

import re

from app.core.entities.mowa_mes import (
    ConfiguracionInvalida,
    ConfiguracionMowaMes,
    DatosSpeech,
    LargoSegmento,
    PartesSegmento,
    ProblemaSpeech,
    SpeechInmutable,
    SpeechInvalido,
    SpeechNoEncontrado,
    VersionSpeech,
)
from app.core.ports.repositorio_mowa_mes_port import RepositorioMowaMesPort
from app.core.services.plataformas.mowa_mes import speech

_NOMBRE_AUTOMATICO = re.compile(r"Speech (\d+)", re.IGNORECASE)


def nombre_siguiente(nombres: list[str]) -> str:
    """`Speech 2`, `Speech 3`...: uno mas que el mayor numero usado (RF-MM-17)."""
    numeros = [
        int(coincidencia.group(1))
        for nombre in nombres
        if (coincidencia := _NOMBRE_AUTOMATICO.fullmatch(nombre.strip()))
    ]
    return f"Speech {max([1, *numeros]) + 1}"


class ConfiguracionMowaMesService:
    def __init__(self, repositorio: RepositorioMowaMesPort) -> None:
        self._repositorio = repositorio

    # --- Configuracion del conector ----------------------------------

    def obtener_configuracion(self) -> ConfiguracionMowaMes:
        return self._repositorio.obtener_configuracion()

    def guardar_configuracion(self, configuracion: ConfiguracionMowaMes) -> ConfiguracionMowaMes:
        if configuracion.limite_mensual < 1:
            raise ConfiguracionInvalida("El limite mensual debe ser mayor que cero")
        whatsapp = (configuracion.whatsapp_contacto or "").strip() or None
        if whatsapp is not None and not speech.whatsapp_valido(whatsapp):
            raise ConfiguracionInvalida(
                "El WhatsApp de contacto debe tener 9 digitos y empezar con 9"
            )
        return self._repositorio.guardar_configuracion(
            ConfiguracionMowaMes(
                limite_mensual=configuracion.limite_mensual, whatsapp_contacto=whatsapp
            )
        )

    # --- Speech ------------------------------------------------------

    def listar_speech(self) -> list[VersionSpeech]:
        return self._repositorio.listar_speech()

    def obtener_speech(self, speech_id: int) -> VersionSpeech:
        version = self._repositorio.obtener_speech(speech_id)
        if version is None:
            raise SpeechNoEncontrado(speech_id)
        return version

    def crear_speech(
        self, nombre: str | None, partes: tuple[PartesSegmento, ...], basada_en_id: int | None
    ) -> VersionSpeech:
        if basada_en_id is not None:
            self.obtener_speech(basada_en_id)
        if not (nombre or "").strip():
            nombre = nombre_siguiente([v.datos.nombre for v in self._repositorio.listar_speech()])
        datos = self._validos(DatosSpeech(nombre=nombre, partes=partes))
        return self._repositorio.crear_speech(datos, basada_en_id)

    def actualizar_speech(self, speech_id: int, datos: DatosSpeech) -> VersionSpeech:
        version = self.obtener_speech(speech_id)
        if not version.editable:
            raise SpeechInmutable(version)
        actualizada = self._repositorio.actualizar_speech(speech_id, self._validos(datos))
        if actualizada is None:
            # Entre la lectura y la escritura, una campana la uso o alguien la borro.
            raise SpeechInmutable(self.obtener_speech(speech_id))
        return actualizada

    def previsualizar_speech(
        self, partes: tuple[PartesSegmento, ...], whatsapp: str | None
    ) -> tuple[str | None, tuple[ProblemaSpeech, ...], tuple[LargoSegmento, ...]]:
        """Largo maximo por segmento con el WhatsApp dado o, si no viene, el configurado."""
        if whatsapp is not None and not speech.whatsapp_valido(whatsapp):
            raise ConfiguracionInvalida("El WhatsApp debe tener 9 digitos y empezar con 9")
        numero = whatsapp or self._repositorio.obtener_configuracion().whatsapp_contacto
        # El nombre no se revisa aqui: la previsualizacion no guarda nada.
        problemas = speech.problemas_de(DatosSpeech(nombre="previsualizacion", partes=partes))
        return numero, problemas, speech.previsualizar(partes, numero)

    @staticmethod
    def _validos(datos: DatosSpeech) -> DatosSpeech:
        limpios = speech.limpiar(datos)
        problemas = speech.problemas_de(limpios)
        if problemas:
            raise SpeechInvalido(problemas)
        ordenadas = tuple(
            sorted(limpios.partes, key=lambda p: list(type(p.segmento)).index(p.segmento))
        )
        return DatosSpeech(nombre=limpios.nombre, partes=ordenadas)

"""Casos de uso de configuracion del conector MOWA MES: limite, WhatsApp y speech.

Una version de speech usada por una campana no se modifica (RF-MM-17), y el
Speech original tampoco: es la referencia de RF-MM-18. Editar cualquiera de las
dos crea una version nueva.

Una version es una expresion del motor por segmento (M2). Desde M-B4 (RF-MM-17) no hay versiones
de dos partes: la migracion `d7a3e5b9c241` las convirtio en su lugar.
"""

import re
from dataclasses import replace

from app.core.entities.mowa_mes import (
    BYTES_POR_ARCHIVO,
    BYTES_POR_ARCHIVO_MINIMO,
    REGISTROS_POR_ARCHIVO,
    CampoConfiguracion,
    CodigoErrorSpeech,
    ConfiguracionInvalida,
    ConfiguracionMowaMes,
    DatosSpeech,
    ExpresionSegmento,
    LargoSegmento,
    ProblemaSpeech,
    Segmento,
    SpeechInmutable,
    SpeechInvalido,
    SpeechNoEliminable,
    SpeechNoEncontrado,
    VersionSpeech,
)
from app.core.entities.mowa_mes_costo import PlantillaInvalida, TarifaInvalida
from app.core.entities.texto_enriquecido import TipoValor
from app.core.ports.repositorio_mowa_mes_port import RepositorioMowaMesPort
from app.core.services.plataformas.mowa_mes import costos, nombre_archivo, speech
from app.core.services.seleccion_cartera.campos import CatalogoCartera

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
    def __init__(
        self, repositorio: RepositorioMowaMesPort, catalogo: CatalogoCartera | None = None
    ) -> None:
        self._repositorio = repositorio
        # El catalogo de la cartera da los campos adicionales que una v2 puede leer (D-CA-0); sin
        # el, una v2 solo ve las variables del mensaje.
        self._catalogo = catalogo

    # --- Configuracion del conector ----------------------------------

    def obtener_configuracion(self) -> ConfiguracionMowaMes:
        return self._repositorio.obtener_configuracion()

    def guardar_configuracion(self, configuracion: ConfiguracionMowaMes) -> ConfiguracionMowaMes:
        if configuracion.limite_mensual < 1:
            raise ConfiguracionInvalida(
                "El limite mensual debe ser mayor que cero", CampoConfiguracion.LIMITE_MENSUAL
            )
        whatsapp = (configuracion.whatsapp_contacto or "").strip() or None
        if whatsapp is not None and not speech.whatsapp_valido(whatsapp):
            raise ConfiguracionInvalida(
                "El WhatsApp de contacto debe tener 9 digitos y empezar con 9",
                CampoConfiguracion.WHATSAPP_CONTACTO,
            )
        if not 1 <= configuracion.registros_por_archivo <= REGISTROS_POR_ARCHIVO:
            raise ConfiguracionInvalida(
                f"Las filas por archivo deben estar entre 1 y {REGISTROS_POR_ARCHIVO}",
                CampoConfiguracion.REGISTROS_POR_ARCHIVO,
            )
        if not BYTES_POR_ARCHIVO_MINIMO <= configuracion.bytes_por_archivo <= BYTES_POR_ARCHIVO:
            raise ConfiguracionInvalida(
                f"Los bytes por archivo deben estar entre {BYTES_POR_ARCHIVO_MINIMO} y "
                f"{BYTES_POR_ARCHIVO}",
                CampoConfiguracion.BYTES_POR_ARCHIVO,
            )
        try:
            tarifa = costos.validar_tarifa(configuracion.tarifa_sms)
        except TarifaInvalida as exc:
            raise ConfiguracionInvalida(str(exc), CampoConfiguracion.TARIFA_SMS) from exc
        try:
            plantilla = nombre_archivo.plantilla_valida(configuracion.plantilla_nombre_archivo)
        except PlantillaInvalida as exc:
            raise ConfiguracionInvalida(
                str(exc), CampoConfiguracion.PLANTILLA_NOMBRE_ARCHIVO
            ) from exc
        return self._repositorio.guardar_configuracion(
            ConfiguracionMowaMes(
                limite_mensual=configuracion.limite_mensual,
                whatsapp_contacto=whatsapp,
                registros_por_archivo=configuracion.registros_por_archivo,
                bytes_por_archivo=configuracion.bytes_por_archivo,
                tarifa_sms=tarifa,
                plantilla_nombre_archivo=plantilla,
            )
        )

    @staticmethod
    def revisar_plantilla_nombre(plantilla: str | None) -> tuple[str, list[str]]:
        """La plantilla validada y los nombres que daria con datos de muestra (RF-MM-25).

        Es la misma resolucion de la creacion de campanas, con dos archivos de muestra.
        No guarda nada.
        """
        try:
            valida = nombre_archivo.plantilla_valida(plantilla)
        except PlantillaInvalida as exc:
            raise ConfiguracionInvalida(
                str(exc), CampoConfiguracion.PLANTILLA_NOMBRE_ARCHIVO
            ) from exc
        return valida, nombre_archivo.resolver_nombres(
            valida, nombre_archivo.CONTEXTO_EJEMPLO, nombre_archivo.CANTIDADES_EJEMPLO
        )

    # --- Speech ------------------------------------------------------

    def listar_speech(self) -> list[VersionSpeech]:
        return self._repositorio.listar_speech()

    def obtener_speech(self, speech_id: int) -> VersionSpeech:
        version = self._repositorio.obtener_speech(speech_id)
        if version is None:
            raise SpeechNoEncontrado(speech_id)
        return version

    def crear_speech_v2(
        self,
        nombre: str | None,
        expresiones: tuple[ExpresionSegmento, ...],
        basada_en_id: int | None,
    ) -> VersionSpeech:
        """Una version nueva: una expresion por segmento, validada con el motor (RF-46)."""
        datos = DatosSpeech(nombre="", expresiones=expresiones)
        return self._crear(nombre, datos, basada_en_id)

    def _crear(
        self, nombre: str | None, contenido: DatosSpeech, basada_en_id: int | None
    ) -> VersionSpeech:
        if basada_en_id is not None:
            self.obtener_speech(basada_en_id)
        if not (nombre or "").strip():
            nombre = nombre_siguiente([v.datos.nombre for v in self._repositorio.listar_speech()])
        datos = self._validos(replace(contenido, nombre=nombre))
        return self._repositorio.crear_speech(datos, basada_en_id)

    def renombrar_speech(self, speech_id: int, nombre: str) -> VersionSpeech:
        """RF-MM-28: cualquier version, la usada y el original incluidos. No cambia el contenido
        ni la huella; el nombre repetido (sin distinguir mayusculas) es `NombreDeSpeechRepetido`."""
        self.obtener_speech(speech_id)
        limpio = nombre.strip()
        problemas = speech.problemas_del_nombre(limpio)
        if problemas:
            raise SpeechInvalido(problemas)
        version = self._repositorio.renombrar_speech(speech_id, limpio)
        if version is None:
            raise SpeechNoEncontrado(speech_id)
        return version

    def deshabilitar_speech(self, speech_id: int) -> VersionSpeech:
        """RF-MM-29: ya no se elige en campanas nuevas; conserva todo. Repetirlo no cambia nada."""
        return self._cambiar_habilitacion(speech_id, habilitada=False)

    def habilitar_speech(self, speech_id: int) -> VersionSpeech:
        return self._cambiar_habilitacion(speech_id, habilitada=True)

    def _cambiar_habilitacion(self, speech_id: int, habilitada: bool) -> VersionSpeech:
        self.obtener_speech(speech_id)
        version = self._repositorio.cambiar_habilitacion(speech_id, habilitada)
        if version is None:
            raise SpeechNoEncontrado(speech_id)
        return version

    def eliminar_speech(self, speech_id: int) -> None:
        """RF-MM-30: solo una version deshabilitada, sin uso y que no sea el original."""
        version = self.obtener_speech(speech_id)
        if version.bloqueo_para_eliminar is not None:
            raise SpeechNoEliminable(version, version.bloqueo_para_eliminar)
        if not self._repositorio.eliminar_speech(speech_id):
            # Entre la lectura y el borrado, alguien la habilito o una campana la uso.
            actual = self.obtener_speech(speech_id)
            raise SpeechNoEliminable(
                actual, actual.bloqueo_para_eliminar or CodigoErrorSpeech.SPEECH_NO_DESHABILITADO
            )

    def actualizar_speech(self, speech_id: int, datos: DatosSpeech) -> VersionSpeech:
        version = self.obtener_speech(speech_id)
        if not version.editable:
            raise SpeechInmutable(version)
        actualizada = self._repositorio.actualizar_speech(speech_id, self._validos(datos))
        if actualizada is None:
            # Entre la lectura y la escritura, una campana la uso o alguien la borro.
            raise SpeechInmutable(self.obtener_speech(speech_id))
        return actualizada

    def previsualizar_speech_v2(
        self, expresiones: tuple[ExpresionSegmento, ...], whatsapp: str | None
    ) -> tuple[
        str | None,
        tuple[ProblemaSpeech, ...],
        tuple[LargoSegmento, ...],
        tuple[tuple[str, str], ...],
    ]:
        """Largo maximo (la cota), nivel y ejemplo por segmento, sin guardar (C-6), y los
        campos archivados que usa, como (nombre, etiqueta): un aviso, nunca un bloqueo (RF-65).

        Un segmento sin cota se informa con `largo_maximo` nulo y su motivo; el control por fila
        de los 160 caracteres es de la campana, sobre el mensaje real.
        """
        if whatsapp is not None and not speech.whatsapp_valido(whatsapp):
            raise ConfiguracionInvalida("El WhatsApp debe tener 9 digitos y empezar con 9")
        numero = whatsapp or self._repositorio.obtener_configuracion().whatsapp_contacto
        adicionales = speech.adicionales_de(self._catalogo)
        problemas = speech.problemas_de(
            DatosSpeech(nombre="previsualizacion", expresiones=expresiones),
            adicionales=adicionales,
        )
        largos = speech.previsualizar_v2(expresiones, numero, adicionales=adicionales)
        return numero, problemas, largos, self._archivados_usados(expresiones, adicionales)

    def _archivados_usados(
        self, expresiones: tuple[ExpresionSegmento, ...], adicionales: dict[str, TipoValor]
    ) -> tuple[tuple[str, str], ...]:
        if self._catalogo is None:
            return ()
        usados = [
            n for e in expresiones for n in speech.adicionales_usados_en(e.expresion, adicionales)
        ]
        return tuple(
            (n, self._catalogo.etiqueta_de(n)) for n in self._catalogo.archivados_entre(usados)
        )

    def _validos(self, datos: DatosSpeech) -> DatosSpeech:
        limpios = speech.limpiar(datos)
        problemas = speech.problemas_de(limpios, adicionales=speech.adicionales_de(self._catalogo))
        if problemas:
            raise SpeechInvalido(problemas)
        orden = {segmento: i for i, segmento in enumerate(Segmento)}
        return replace(
            limpios,
            expresiones=tuple(sorted(limpios.expresiones, key=lambda e: orden[e.segmento])),
        )

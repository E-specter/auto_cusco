"""Casos de uso de configuracion del conector MOWA MES: limite, WhatsApp y speech.

Una version de speech usada por una campana no se modifica (RF-MM-17), y el
Speech original tampoco: es la referencia de RF-MM-18. Editar cualquiera de las
dos crea una version nueva.

Una version es v1 (dos partes por segmento) o v2 (una expresion del motor por segmento, M2); el
formato no cambia al editarla. `como_v2` convierte una v1 en el borrador de una v2 que da los
mismos mensajes, sin guardar nada: guardarlo es crear una version nueva basada en la v1.
"""

import re
from dataclasses import dataclass, replace

from app.core.entities.mowa_mes import (
    BYTES_POR_ARCHIVO,
    BYTES_POR_ARCHIVO_MINIMO,
    REGISTROS_POR_ARCHIVO,
    CampoConfiguracion,
    CodigoMowaMes,
    ConfiguracionInvalida,
    ConfiguracionMowaMes,
    DatosSpeech,
    ExpresionSegmento,
    FormatoSpeech,
    LargoSegmento,
    PartesSegmento,
    ProblemaSpeech,
    Segmento,
    SpeechInmutable,
    SpeechInvalido,
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


MENSAJE_V1_RETIRADA = (
    "Las versiones nuevas del speech se arman con el motor de texto, una expresion por segmento "
    "(v2): una version de dos partes ya no se crea ni se edita. Convierte la que quieras "
    "personalizar con como-v2 y guarda el resultado"
)


def version_v1_retirada() -> SpeechInvalido:
    """El rechazo de crear o editar una version de dos partes (RF-MM-17, M3)."""
    return SpeechInvalido(
        (
            ProblemaSpeech(
                None,
                "formato",
                MENSAJE_V1_RETIRADA,
                codigo_mowa_mes=CodigoMowaMes.VERSION_V1_RETIRADA,
            ),
        )
    )


@dataclass(frozen=True)
class BorradorV2:
    """Una v1 convertida a v2, sin guardar: lo que el editor muestra para seguir editando."""

    basada_en_id: int
    nombre_sugerido: str
    expresiones: tuple[ExpresionSegmento, ...]
    problemas: tuple[ProblemaSpeech, ...]


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

    def crear_speech(
        self, nombre: str | None, partes: tuple[PartesSegmento, ...], basada_en_id: int | None
    ) -> VersionSpeech:
        """Ya no se crean versiones de dos partes (RF-MM-17, M3): siempre `SpeechInvalido` con el
        codigo `version_v1_retirada`, antes de mirar el resto del pedido. Las v1 que ya existen
        se siguen leyendo, usando en campanas y convirtiendo con `como_v2`.

        La firma se mantiene aunque ningun argumento se use: es la de siempre del caso de uso, la
        que llama el endpoint con lo que trae el pedido, y asi el rechazo sigue siendo UN solo
        lugar (aqui) y no un `if` en cada adaptador. Si un dia se quita la ruta con `partes`, se
        borra este metodo entero.
        """
        raise version_v1_retirada()

    def crear_speech_v2(
        self,
        nombre: str | None,
        expresiones: tuple[ExpresionSegmento, ...],
        basada_en_id: int | None,
    ) -> VersionSpeech:
        """Una version v2 nueva: una expresion por segmento, validada con el motor (RF-46)."""
        datos = DatosSpeech(nombre="", expresiones=expresiones, formato=FormatoSpeech.V2)
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

    def como_v2(self, speech_id: int) -> BorradorV2:
        """El borrador v2 de una v1: sus mismos mensajes, con titular y fecha obligatorios (C-5)."""
        version = self.obtener_speech(speech_id)
        if version.datos.formato is not FormatoSpeech.V1:
            raise SpeechInvalido(
                (ProblemaSpeech(None, "formato", "La version ya es v2: no hay nada que convertir"),)
            )
        expresiones = speech.convertir_a_v2(version.datos.partes)
        nombre = nombre_siguiente([v.datos.nombre for v in self._repositorio.listar_speech()])
        problemas = speech.problemas_de(
            DatosSpeech(nombre=nombre, expresiones=expresiones, formato=FormatoSpeech.V2),
            adicionales=speech.adicionales_de(self._catalogo),
        )
        return BorradorV2(version.id, nombre, expresiones, problemas)

    def actualizar_speech(self, speech_id: int, datos: DatosSpeech) -> VersionSpeech:
        if datos.formato is FormatoSpeech.V1:
            raise version_v1_retirada()  # tampoco se editan en dos partes (RF-MM-17, M3)
        version = self.obtener_speech(speech_id)
        if not version.editable:
            raise SpeechInmutable(version)
        if datos.formato is not version.datos.formato:
            raise SpeechInvalido(
                (
                    ProblemaSpeech(
                        None,
                        "formato",
                        f"La version es {version.datos.formato.value} y no cambia de formato al "
                        "editarla; guarda el cambio como una version nueva",
                    ),
                )
            )
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

    def previsualizar_speech_v2(
        self, expresiones: tuple[ExpresionSegmento, ...], whatsapp: str | None
    ) -> tuple[
        str | None,
        tuple[ProblemaSpeech, ...],
        tuple[LargoSegmento, ...],
        tuple[tuple[str, str], ...],
    ]:
        """Largo maximo (la cota), nivel y ejemplo por segmento de una v2, sin guardar (C-6), y los
        campos archivados que usa, como (nombre, etiqueta): un aviso, nunca un bloqueo (RF-65).

        Un segmento sin cota se informa con `largo_maximo` nulo y su motivo; el control por fila
        de los 160 caracteres es de la campana, sobre el mensaje real.
        """
        if whatsapp is not None and not speech.whatsapp_valido(whatsapp):
            raise ConfiguracionInvalida("El WhatsApp debe tener 9 digitos y empezar con 9")
        numero = whatsapp or self._repositorio.obtener_configuracion().whatsapp_contacto
        adicionales = speech.adicionales_de(self._catalogo)
        problemas = speech.problemas_de(
            DatosSpeech(
                nombre="previsualizacion", expresiones=expresiones, formato=FormatoSpeech.V2
            ),
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
            partes=tuple(sorted(limpios.partes, key=lambda p: orden[p.segmento])),
            expresiones=tuple(sorted(limpios.expresiones, key=lambda e: orden[e.segmento])),
        )

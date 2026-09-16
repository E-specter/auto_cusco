"""Adaptador de entrada HTTP del conector MOWA MES (docs/requerimientos-mowa-mes.md).

Primer corte (B6a), configuracion:

    GET  /mowa-mes/configuracion              limite mensual y WhatsApp por defecto
    PUT  /mowa-mes/configuracion
    GET  /mowa-mes/speech                     versiones, la original primero
    GET  /mowa-mes/speech/{id}
    POST /mowa-mes/speech                     version nueva
    PUT  /mowa-mes/speech/{id}                solo si no se uso y no es la original; si no, 409
    POST /mowa-mes/speech/previsualizacion    largo maximo por segmento, sin guardar
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.adapters.persistence.db import get_engine
from app.adapters.persistence.repositorio_mowa_mes_postgres import RepositorioMowaMesPostgres
from app.api.errores import respuestas_de_error
from app.api.respuestas import ModeloRespuesta
from app.core.entities.mowa_mes import (
    BYTES_POR_ARCHIVO,
    BYTES_POR_ARCHIVO_MINIMO,
    LARGO_ADVERTENCIA,
    LARGO_MAXIMO,
    LARGO_MAXIMO_NOMBRE_SPEECH,
    RANGOS_SEGMENTO,
    REGISTROS_POR_ARCHIVO,
    CodigoMowaMes,
    ConfiguracionInvalida,
    ConfiguracionMowaMes,
    DatosSpeech,
    NombreDeSpeechRepetido,
    PartesSegmento,
    Segmento,
    SpeechInmutable,
    SpeechInvalido,
    SpeechNoEncontrado,
    VersionSpeech,
)
from app.core.services.plataformas.mowa_mes.configuracion import ConfiguracionMowaMesService
from app.core.services.plataformas.mowa_mes.speech import usa_whatsapp

router = APIRouter(prefix="/mowa-mes", tags=["mowa-mes"])

LARGO_MAXIMO_PARTE = 500
LIMITE_MENSUAL_MAXIMO = 1_000_000_000
_RANGO = {rango.segmento: rango for rango in RANGOS_SEGMENTO}


def obtener_servicio_mowa_mes() -> ConfiguracionMowaMesService:
    """Dependencia de FastAPI; los tests la sustituyen por un doble de prueba."""
    return ConfiguracionMowaMesService(RepositorioMowaMesPostgres(get_engine()))


# --- Configuracion -------------------------------------------------------


class ConfiguracionEntrada(BaseModel):
    limite_mensual: int = Field(ge=1, le=LIMITE_MENSUAL_MAXIMO)
    whatsapp_contacto: str | None = Field(
        default=None,
        max_length=20,
        description="Sin el campo se conserva el actual; null lo borra (queda sin numero)",
    )
    # Sin null: el defecto None solo marca "omitido" (no se valida); un null explicito
    # no es un entero y responde 422.
    registros_por_archivo: int = Field(
        default=None,
        ge=1,
        le=REGISTROS_POR_ARCHIVO,
        description="Filas por archivo (RF-MM-11). Sin el campo se conserva el actual; null: 422",
    )
    bytes_por_archivo: int = Field(
        default=None,
        ge=BYTES_POR_ARCHIVO_MINIMO,
        le=BYTES_POR_ARCHIVO,
        description="Bytes por archivo (RF-MM-11). Sin el campo se conserva el actual; null: 422",
    )

    def valor(self, campo: str, actual: ConfiguracionMowaMes):
        """El valor enviado o, si el campo no vino, el guardado (actualizacion parcial)."""
        return getattr(self if campo in self.model_fields_set else actual, campo)


class ConfiguracionRespuesta(ModeloRespuesta):
    limite_mensual: int
    whatsapp_contacto: str | None
    actualizado_en: datetime | None
    registros_por_archivo: int
    bytes_por_archivo: int


def _configuracion(configuracion: ConfiguracionMowaMes) -> ConfiguracionRespuesta:
    return ConfiguracionRespuesta(
        limite_mensual=configuracion.limite_mensual,
        whatsapp_contacto=configuracion.whatsapp_contacto,
        actualizado_en=configuracion.actualizado_en,
        registros_por_archivo=configuracion.registros_por_archivo,
        bytes_por_archivo=configuracion.bytes_por_archivo,
    )


@router.get("/configuracion", response_model=ConfiguracionRespuesta)
def obtener_configuracion(
    servicio: ConfiguracionMowaMesService = Depends(obtener_servicio_mowa_mes),
) -> ConfiguracionRespuesta:
    return _configuracion(servicio.obtener_configuracion())


@router.put(
    "/configuracion",
    summary="Actualizar la configuracion del conector (parcial)",
    response_model=ConfiguracionRespuesta,
    responses=respuestas_de_error(400),
)
def guardar_configuracion(
    entrada: ConfiguracionEntrada,
    servicio: ConfiguracionMowaMesService = Depends(obtener_servicio_mowa_mes),
) -> ConfiguracionRespuesta:
    """Actualizacion parcial sobre PUT, no un reemplazo completo.

    - `limite_mensual` es obligatorio (RF-MM-01).
    - Cualquier otro campo omitido conserva el valor guardado.
    - `whatsapp_contacto: null` borra el numero de contacto (RF-MM-16).
    - `registros_por_archivo` y `bytes_por_archivo` no admiten null (422) y solo pueden
      bajar del maximo de la plataforma (RF-MM-11).

    Esta regla es propia de este endpoint: `PUT /supervisores` reemplaza la lista completa.
    """
    actual = servicio.obtener_configuracion()
    try:
        return _configuracion(
            servicio.guardar_configuracion(
                ConfiguracionMowaMes(
                    limite_mensual=entrada.limite_mensual,
                    whatsapp_contacto=entrada.valor("whatsapp_contacto", actual),
                    registros_por_archivo=entrada.valor("registros_por_archivo", actual),
                    bytes_por_archivo=entrada.valor("bytes_por_archivo", actual),
                )
            )
        )
    except ConfiguracionInvalida as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# --- Speech --------------------------------------------------------------


class PartesEntrada(BaseModel):
    segmento: Segmento
    parte_1: str = Field(max_length=LARGO_MAXIMO_PARTE)
    parte_2: str = Field(max_length=LARGO_MAXIMO_PARTE)


class SpeechNuevoEntrada(BaseModel):
    nombre: str | None = Field(
        default=None,
        max_length=LARGO_MAXIMO_NOMBRE_SPEECH,
        description="Sin nombre, se le asigna el siguiente 'Speech N'",
    )
    basada_en_id: int | None = None
    partes: list[PartesEntrada]


class SpeechEdicionEntrada(BaseModel):
    nombre: str = Field(min_length=1, max_length=LARGO_MAXIMO_NOMBRE_SPEECH)
    partes: list[PartesEntrada]


class PrevisualizacionEntrada(BaseModel):
    partes: list[PartesEntrada]
    whatsapp: str | None = Field(
        default=None,
        max_length=20,
        description="Sin numero, se usa el WhatsApp de contacto configurado",
    )


class PartesRespuesta(ModeloRespuesta):
    segmento: Segmento
    etiqueta: str
    dias_desde: int | None
    dias_hasta: int
    parte_1: str
    parte_2: str
    usa_whatsapp: bool


class VersionSpeechRespuesta(ModeloRespuesta):
    id: int
    nombre: str
    original: bool
    basada_en_id: int | None
    usada: bool
    editable: bool
    creado_en: datetime
    partes: list[PartesRespuesta]


class ProblemaSpeechRespuesta(ModeloRespuesta):
    segmento: Segmento | None
    campo: str
    detalle: str


class LargoSegmentoRespuesta(ModeloRespuesta):
    segmento: Segmento
    etiqueta: str
    usa_whatsapp: bool
    falta_whatsapp: bool
    largo_maximo: int
    codigo: CodigoMowaMes | None
    ejemplo: str | None


class PrevisualizacionRespuesta(ModeloRespuesta):
    whatsapp: str | None
    largo_advertencia: int
    largo_maximo: int
    problemas: list[ProblemaSpeechRespuesta]
    segmentos: list[LargoSegmentoRespuesta]


def _partes(entrada: list[PartesEntrada]) -> tuple[PartesSegmento, ...]:
    return tuple(PartesSegmento(p.segmento, p.parte_1, p.parte_2) for p in entrada)


def _version(version: VersionSpeech) -> VersionSpeechRespuesta:
    return VersionSpeechRespuesta(
        id=version.id,
        nombre=version.datos.nombre,
        original=version.original,
        basada_en_id=version.basada_en_id,
        usada=version.usada,
        editable=version.editable,
        creado_en=version.creado_en,
        partes=[
            PartesRespuesta(
                segmento=p.segmento,
                etiqueta=_RANGO[p.segmento].etiqueta,
                dias_desde=_RANGO[p.segmento].desde,
                dias_hasta=_RANGO[p.segmento].hasta,
                parte_1=p.parte_1,
                parte_2=p.parte_2,
                usa_whatsapp=usa_whatsapp(p),
            )
            for p in version.datos.partes
        ],
    )


def _traducir(exc: Exception) -> HTTPException:
    if isinstance(exc, SpeechNoEncontrado):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (SpeechInmutable, NombreDeSpeechRepetido)):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/speech", response_model=list[VersionSpeechRespuesta])
def listar_speech(
    servicio: ConfiguracionMowaMesService = Depends(obtener_servicio_mowa_mes),
) -> list[VersionSpeechRespuesta]:
    return [_version(version) for version in servicio.listar_speech()]


@router.post(
    "/speech/previsualizacion",
    response_model=PrevisualizacionRespuesta,
    responses=respuestas_de_error(400),
)
def previsualizar_speech(
    entrada: PrevisualizacionEntrada,
    servicio: ConfiguracionMowaMesService = Depends(obtener_servicio_mowa_mes),
) -> PrevisualizacionRespuesta:
    """Largo maximo de cada segmento, con titular de 8 y fecha de 10 (RF-MM-19).

    Un segmento que usa [whatsapp] sin numero se marca con `falta_whatsapp` y sin
    ejemplo: nunca se muestra un enlace roto.
    """
    try:
        whatsapp, problemas, largos = servicio.previsualizar_speech(
            _partes(entrada.partes), entrada.whatsapp
        )
    except ConfiguracionInvalida as exc:
        raise _traducir(exc) from exc
    return PrevisualizacionRespuesta(
        whatsapp=whatsapp,
        largo_advertencia=LARGO_ADVERTENCIA,
        largo_maximo=LARGO_MAXIMO,
        problemas=[
            ProblemaSpeechRespuesta(segmento=p.segmento, campo=p.campo, detalle=p.detalle)
            for p in problemas
        ],
        segmentos=[
            LargoSegmentoRespuesta(
                segmento=largo.rango.segmento,
                etiqueta=largo.rango.etiqueta,
                usa_whatsapp=largo.usa_whatsapp,
                falta_whatsapp=largo.usa_whatsapp and whatsapp is None,
                largo_maximo=largo.largo_maximo,
                codigo=largo.codigo,
                ejemplo=largo.ejemplo,
            )
            for largo in largos
        ],
    )


@router.get(
    "/speech/{speech_id}", response_model=VersionSpeechRespuesta, responses=respuestas_de_error(404)
)
def obtener_speech(
    speech_id: int,
    servicio: ConfiguracionMowaMesService = Depends(obtener_servicio_mowa_mes),
) -> VersionSpeechRespuesta:
    try:
        return _version(servicio.obtener_speech(speech_id))
    except SpeechNoEncontrado as exc:
        raise _traducir(exc) from exc


@router.post(
    "/speech",
    status_code=201,
    response_model=VersionSpeechRespuesta,
    responses=respuestas_de_error(400, 404, 409),
)
def crear_speech(
    entrada: SpeechNuevoEntrada,
    servicio: ConfiguracionMowaMesService = Depends(obtener_servicio_mowa_mes),
) -> VersionSpeechRespuesta:
    """Guarda una version nueva. 404 si `basada_en_id` no existe."""
    try:
        return _version(
            servicio.crear_speech(entrada.nombre, _partes(entrada.partes), entrada.basada_en_id)
        )
    except (SpeechInvalido, SpeechNoEncontrado, NombreDeSpeechRepetido) as exc:
        raise _traducir(exc) from exc


@router.put(
    "/speech/{speech_id}",
    response_model=VersionSpeechRespuesta,
    responses=respuestas_de_error(400, 404, 409),
)
def actualizar_speech(
    speech_id: int,
    entrada: SpeechEdicionEntrada,
    servicio: ConfiguracionMowaMesService = Depends(obtener_servicio_mowa_mes),
) -> VersionSpeechRespuesta:
    """Reemplaza una version que nadie uso. Si ya se uso o es la original, 409."""
    try:
        return _version(
            servicio.actualizar_speech(
                speech_id, DatosSpeech(nombre=entrada.nombre, partes=_partes(entrada.partes))
            )
        )
    except (SpeechInvalido, SpeechNoEncontrado, SpeechInmutable, NombreDeSpeechRepetido) as exc:
        raise _traducir(exc) from exc

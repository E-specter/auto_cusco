"""Adaptador de entrada HTTP del conector MOWA MES (docs/requerimientos-mowa-mes.md).

Primer corte (B6a), configuracion:

    GET  /mowa-mes/configuracion              limite mensual, WhatsApp, tarifa por SMS y plantilla
    PUT  /mowa-mes/configuracion              del nombre de los archivos (B8)
    POST /mowa-mes/plantilla-nombre-archivo/previsualizacion   nombres de muestra, sin guardar
    GET  /mowa-mes/speech                     versiones, la original primero
    GET  /mowa-mes/speech/{id}
    POST /mowa-mes/speech                     version nueva
    PUT  /mowa-mes/speech/{id}                solo si no se uso y no es la original; si no, 409
    POST /mowa-mes/speech/previsualizacion    largo maximo por segmento, sin guardar
    GET  /mowa-mes/speech/{id}/como-v2        el borrador v2 de una v1 (sus mismos mensajes)

Una version es v1 (`partes`, dos por segmento) o v2 (`expresiones`, una del motor de texto
enriquecido por segmento, M2); el pedido lleva `partes` o `expresiones`, no las dos. Un 400 de una
version trae `problemas`, cada uno con su segmento, su campo y, en una v2, su codigo y su ubicacion.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.adapters.persistence.db import get_engine
from app.adapters.persistence.repositorio_mowa_mes_postgres import RepositorioMowaMesPostgres
from app.api.definiciones_columnas import ExpresionGuardadaRespuesta
from app.api.errores import DetalleError, respuestas_de_error
from app.api.respuestas import ModeloRespuesta
from app.api.texto_enriquecido import ExpresionEntrada, SinCotaRespuesta, UbicacionRespuesta
from app.core.entities.mowa_mes import (
    BYTES_POR_ARCHIVO,
    BYTES_POR_ARCHIVO_MINIMO,
    LARGO_ADVERTENCIA,
    LARGO_MAXIMO,
    LARGO_MAXIMO_NOMBRE_SPEECH,
    RANGOS_SEGMENTO,
    REGISTROS_POR_ARCHIVO,
    CampoConfiguracion,
    CampoProblemaSpeech,
    CodigoMowaMes,
    ConfiguracionInvalida,
    ConfiguracionMowaMes,
    DatosSpeech,
    ExpresionSegmento,
    FormatoSpeech,
    NombreDeSpeechRepetido,
    PartesSegmento,
    ProblemaSpeech,
    Segmento,
    SpeechInmutable,
    SpeechInvalido,
    SpeechNoEncontrado,
    VersionSpeech,
)
from app.core.entities.mowa_mes_costo import VARIABLES_PLANTILLA, TarifaInvalida
from app.core.entities.texto_enriquecido import CodigoTexto, ExpresionInvalida, MotivoSinCota
from app.core.services.plataformas.mowa_mes import costos
from app.core.services.plataformas.mowa_mes.configuracion import (
    BorradorV2,
    ConfiguracionMowaMesService,
)
from app.core.services.plataformas.mowa_mes.speech import (
    VARIABLE_CONTACTO,
    VARIABLE_TITULAR,
    VARIABLE_VENCIMIENTO,
    usa_whatsapp,
)
from app.core.services.texto_enriquecido.serializacion import expresion_a_dict, expresion_desde_dict
from app.core.services.texto_enriquecido.uso import variables_usadas

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
    # Texto y no numero: un monto no pasa por float (RF-MM-23). Lo valida el nucleo, que
    # responde 400 con el motivo; null no es texto y responde 422.
    tarifa_sms: str = Field(
        default=None,
        max_length=32,
        description=(
            "Soles por SMS, texto decimal mayor o igual a 0 con hasta 4 decimales (RF-MM-23). "
            "Sin el campo se conserva la actual; null: 422"
        ),
    )
    plantilla_nombre_archivo: str = Field(
        default=None,
        max_length=1000,
        description=(
            "Plantilla del nombre de los archivos de carga (RF-MM-25). Sin el campo se conserva "
            "la actual; vacia, vuelve la de por defecto; null: 422"
        ),
    )

    def valor(self, campo: str, actual: ConfiguracionMowaMes):
        """El valor enviado o, si el campo no vino, el guardado (actualizacion parcial)."""
        return getattr(self if campo in self.model_fields_set else actual, campo)

    def tarifa(self, actual: ConfiguracionMowaMes) -> Decimal:
        """La tarifa enviada, leida como texto decimal, o la guardada si el campo no vino."""
        if "tarifa_sms" not in self.model_fields_set:
            return actual.tarifa_sms
        return costos.tarifa_desde_texto(self.tarifa_sms)


class VariablePlantillaRespuesta(ModeloRespuesta):
    nombre: str
    descripcion: str


class ConfiguracionRespuesta(ModeloRespuesta):
    limite_mensual: int
    whatsapp_contacto: str | None
    actualizado_en: datetime | None
    registros_por_archivo: int
    bytes_por_archivo: int
    tarifa_sms: str = Field(description="Soles por SMS, texto decimal con 4 decimales")
    plantilla_nombre_archivo: str
    variables_plantilla: list[VariablePlantillaRespuesta] = Field(
        description="Las variables validas de la plantilla, en el orden del requerimiento"
    )


def _configuracion(configuracion: ConfiguracionMowaMes) -> ConfiguracionRespuesta:
    return ConfiguracionRespuesta(
        limite_mensual=configuracion.limite_mensual,
        whatsapp_contacto=configuracion.whatsapp_contacto,
        actualizado_en=configuracion.actualizado_en,
        registros_por_archivo=configuracion.registros_por_archivo,
        bytes_por_archivo=configuracion.bytes_por_archivo,
        tarifa_sms=costos.texto_decimal(configuracion.tarifa_sms),
        plantilla_nombre_archivo=configuracion.plantilla_nombre_archivo,
        variables_plantilla=[
            VariablePlantillaRespuesta(nombre=v.nombre, descripcion=v.descripcion)
            for v in VARIABLES_PLANTILLA
        ],
    )


@router.get("/configuracion", response_model=ConfiguracionRespuesta)
def obtener_configuracion(
    servicio: ConfiguracionMowaMesService = Depends(obtener_servicio_mowa_mes),
) -> ConfiguracionRespuesta:
    return _configuracion(servicio.obtener_configuracion())


class ErrorConfiguracionRespuesta(ModeloRespuesta):
    """400 propio de la configuracion: dice a que campo pertenece el error.

    El frontend ubica el mensaje bajo su campo por `campo`, sin adivinar por las palabras
    del `detail`. Extiende `detail` como pide la regla de docs/contrato-api.md, seccion 3.
    """

    detail: str
    campo: CampoConfiguracion


def _error_de_configuracion(detail: str, campo: CampoConfiguracion | None) -> JSONResponse:
    # Pasa por el modelo: un 400 sin campo seria un error del backend, no una respuesta valida.
    cuerpo = ErrorConfiguracionRespuesta(detail=detail, campo=campo)
    return JSONResponse(status_code=400, content=cuerpo.model_dump(mode="json"))


_ERROR_400_CONFIGURACION = {
    400: {
        "model": ErrorConfiguracionRespuesta,
        "description": "Un valor no es valido; `campo` dice cual y `detail` el motivo",
    }
}


@router.put(
    "/configuracion",
    summary="Actualizar la configuracion del conector (parcial)",
    response_model=ConfiguracionRespuesta,
    responses=_ERROR_400_CONFIGURACION,
)
def guardar_configuracion(
    entrada: ConfiguracionEntrada,
    servicio: ConfiguracionMowaMesService = Depends(obtener_servicio_mowa_mes),
) -> ConfiguracionRespuesta | JSONResponse:
    """Actualizacion parcial sobre PUT, no un reemplazo completo.

    - `limite_mensual` es obligatorio (RF-MM-01).
    - Cualquier otro campo omitido conserva el valor guardado.
    - `whatsapp_contacto: null` borra el numero de contacto (RF-MM-16).
    - `registros_por_archivo` y `bytes_por_archivo` no admiten null (422) y solo pueden
      bajar del maximo de la plataforma (RF-MM-11).
    - `tarifa_sms` (RF-MM-23) y `plantilla_nombre_archivo` (RF-MM-25) tampoco admiten null
      (422). Una tarifa que no es un decimal mayor o igual a 0 con hasta 4 decimales, o una
      plantilla con una variable desconocida o una llave sin cerrar, responde 400.

    Todo 400 de este endpoint trae `detail` (el motivo) y `campo` (el campo de la
    configuracion al que pertenece), para que el frontend lo ubique sin leer el texto.

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
                    tarifa_sms=entrada.tarifa(actual),
                    plantilla_nombre_archivo=entrada.valor("plantilla_nombre_archivo", actual),
                )
            )
        )
    except TarifaInvalida as exc:
        return _error_de_configuracion(str(exc), CampoConfiguracion.TARIFA_SMS)
    except ConfiguracionInvalida as exc:
        return _error_de_configuracion(str(exc), exc.campo)


class PlantillaNombreEntrada(BaseModel):
    plantilla: str = Field(max_length=1000, description="Vacia: la plantilla de por defecto")


class PlantillaNombreRespuesta(ModeloRespuesta):
    plantilla: str = Field(description="La plantilla validada, la que se guardaria")
    nombres_ejemplo: list[str] = Field(
        description="Los nombres que daria con datos de muestra: un archivo de una campana de dos"
    )


@router.post(
    "/plantilla-nombre-archivo/previsualizacion",
    summary="Previsualizar una plantilla del nombre de los archivos, sin guardarla",
    response_model=PlantillaNombreRespuesta,
    responses=_ERROR_400_CONFIGURACION,
)
def previsualizar_plantilla_nombre(
    entrada: PlantillaNombreEntrada,
    servicio: ConfiguracionMowaMesService = Depends(obtener_servicio_mowa_mes),
) -> PlantillaNombreRespuesta | JSONResponse:
    """Resuelve la plantilla con datos de muestra usando la misma funcion que la creacion de
    campanas (RF-MM-25). Una variable desconocida o una llave sin cerrar responde 400 con
    `detail` y `campo` (`plantilla_nombre_archivo`)."""
    try:
        plantilla, nombres = servicio.revisar_plantilla_nombre(entrada.plantilla)
    except ConfiguracionInvalida as exc:
        return _error_de_configuracion(str(exc), exc.campo)
    return PlantillaNombreRespuesta(plantilla=plantilla, nombres_ejemplo=nombres)


# --- Speech --------------------------------------------------------------


class PartesEntrada(BaseModel):
    segmento: Segmento
    parte_1: str = Field(max_length=LARGO_MAXIMO_PARTE)
    parte_2: str = Field(max_length=LARGO_MAXIMO_PARTE)


class ExpresionSegmentoEntrada(BaseModel):
    """El contenido de un segmento de una v2: su expresion completa (el modelo del motor)."""

    segmento: Segmento
    expresion: ExpresionEntrada


_DESCRIPCION_CONTENIDO = "Las `partes` de una v1 o las `expresiones` de una v2: una de las dos"


class SpeechNuevoEntrada(BaseModel):
    nombre: str | None = Field(
        default=None,
        max_length=LARGO_MAXIMO_NOMBRE_SPEECH,
        description="Sin nombre, se le asigna el siguiente 'Speech N'",
    )
    basada_en_id: int | None = None
    partes: list[PartesEntrada] | None = Field(default=None, description=_DESCRIPCION_CONTENIDO)
    expresiones: list[ExpresionSegmentoEntrada] | None = Field(
        default=None, description=_DESCRIPCION_CONTENIDO
    )


class SpeechEdicionEntrada(BaseModel):
    nombre: str = Field(min_length=1, max_length=LARGO_MAXIMO_NOMBRE_SPEECH)
    partes: list[PartesEntrada] | None = Field(default=None, description=_DESCRIPCION_CONTENIDO)
    expresiones: list[ExpresionSegmentoEntrada] | None = Field(
        default=None, description=_DESCRIPCION_CONTENIDO
    )


class PrevisualizacionEntrada(BaseModel):
    partes: list[PartesEntrada] | None = Field(default=None, description=_DESCRIPCION_CONTENIDO)
    expresiones: list[ExpresionSegmentoEntrada] | None = Field(
        default=None, description=_DESCRIPCION_CONTENIDO
    )
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


class ExpresionSegmentoRespuesta(ModeloRespuesta):
    """El segmento de una v2. `usa_titular` y `usa_vencimiento` dicen si un producto sin ese dato
    se excluye en este segmento (RF-MM-13): solo si la expresion usa la variable."""

    segmento: Segmento
    etiqueta: str
    dias_desde: int | None
    dias_hasta: int
    expresion: ExpresionGuardadaRespuesta
    usa_titular: bool
    usa_vencimiento: bool
    usa_whatsapp: bool


class VersionSpeechRespuesta(ModeloRespuesta):
    """`partes` si es v1 y `expresiones` si es v2; la otra lista viene vacia."""

    id: int
    nombre: str
    formato: FormatoSpeech
    original: bool
    basada_en_id: int | None
    usada: bool
    editable: bool
    creado_en: datetime
    partes: list[PartesRespuesta]
    expresiones: list[ExpresionSegmentoRespuesta]


class ProblemaSpeechRespuesta(ModeloRespuesta):
    """`codigo` y `ubicacion` (nodo, funcion y parametro) vienen en los problemas de una v2.

    `codigo` es de uno de los dos catalogos (`CodigoTexto` o `CodigoMowaMes`; un nombre que no
    esta en ninguno no compila en el cliente) y `catalogo` dice en cual i18n se traduce: `texto`
    (`textoEnriquecido.codigo.*`, el del motor) o `mowa_mes` (`mowaMes.codigo.*`). Los dos
    catalogos comparten nombres (`telefono_invalido`) con textos distintos, asi que el codigo solo
    no basta. Es nulo cuando `codigo` lo es.
    """

    segmento: Segmento | None
    campo: CampoProblemaSpeech
    detalle: str
    codigo: CodigoTexto | CodigoMowaMes | None
    catalogo: Literal["texto", "mowa_mes"] | None
    ubicacion: UbicacionRespuesta | None


class DetalleErrorSpeech(DetalleError):
    """Un 400 de speech: el motivo y los problemas, cada uno con su ubicacion."""

    problemas: list[ProblemaSpeechRespuesta]


_RESPUESTAS_400 = {
    400: {
        "model": DetalleErrorSpeech,
        "description": "La peticion no vale: `detail` es el motivo y `problemas` dice donde",
    }
}


class BorradorV2Respuesta(ModeloRespuesta):
    """Una v1 convertida a v2, sin guardar: se edita y se guarda como version nueva."""

    basada_en_id: int
    nombre_sugerido: str
    expresiones: list[ExpresionSegmentoRespuesta]
    problemas: list[ProblemaSpeechRespuesta]


class LargoSegmentoRespuesta(ModeloRespuesta):
    """`largo_maximo` es nulo cuando la expresion de una v2 no tiene maximo calculable: `sin_maximo`
    dice por que (una variable cuyo largo depende del dato, o una funcion que no lo acota)."""

    segmento: Segmento
    etiqueta: str
    usa_whatsapp: bool
    falta_whatsapp: bool
    largo_maximo: int | None
    sin_maximo: SinCotaRespuesta | None
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


def _contenido(
    partes: list[PartesEntrada] | None, expresiones: list[ExpresionSegmentoEntrada] | None
) -> tuple[tuple[PartesSegmento, ...], tuple[ExpresionSegmento, ...]]:
    """Las partes de una v1 o las expresiones de una v2, leidas con el lector estricto del motor.

    Una forma imposible (un tipo de nodo que no existe) no es un 422 sin ubicacion: es un problema
    `expresion_invalida` con su segmento y su nodo.
    """
    if (partes is None) == (expresiones is None):
        raise SpeechInvalido(
            (
                ProblemaSpeech(
                    None,
                    "formato",
                    "Se piden `partes` (v1) o `expresiones` (v2), no las dos ni ninguna",
                ),
            )
        )
    if partes is not None:
        return _partes(partes), ()
    leidas: list[ExpresionSegmento] = []
    problemas: list[ProblemaSpeech] = []
    for item in expresiones or ():
        try:
            dato = item.expresion.model_dump(exclude_unset=True, exclude_none=True)
            leidas.append(ExpresionSegmento(item.segmento, expresion_desde_dict(dato)))
        except ExpresionInvalida as error:
            problemas += [
                ProblemaSpeech(item.segmento, "expresion", p.detalle, p) for p in error.problemas
            ]
    if problemas:
        raise SpeechInvalido(tuple(problemas))
    return (), tuple(leidas)


def _problema(p: ProblemaSpeech) -> ProblemaSpeechRespuesta:
    motor = p.problema
    ubicacion = None
    if motor is not None and motor.nodo is not None:
        ubicacion = UbicacionRespuesta(
            nodo=motor.nodo, funcion=motor.funcion, parametro=motor.parametro
        )
    codigo: CodigoTexto | CodigoMowaMes | None = None
    catalogo: Literal["texto", "mowa_mes"] | None = None
    if motor is not None:
        codigo, catalogo = motor.codigo, "texto"
    elif p.codigo_mowa_mes is not None:
        codigo, catalogo = p.codigo_mowa_mes, "mowa_mes"
    return ProblemaSpeechRespuesta(
        segmento=p.segmento,
        campo=p.campo,
        detalle=p.detalle,
        codigo=codigo,
        catalogo=catalogo,
        ubicacion=ubicacion,
    )


def _error_400(detalle: str, problemas: tuple[ProblemaSpeech, ...] = ()) -> JSONResponse:
    # Pasa por el modelo: el 400 declarado en el contrato es el que se envia.
    cuerpo = DetalleErrorSpeech(detail=detalle, problemas=[_problema(p) for p in problemas])
    return JSONResponse(status_code=400, content=cuerpo.model_dump(mode="json"))


def _sin_maximo(motivo: MotivoSinCota | None) -> SinCotaRespuesta | None:
    if motivo is None:
        return None
    return SinCotaRespuesta(
        codigo=motivo.codigo,
        detalle=motivo.detalle,
        ubicacion=UbicacionRespuesta(nodo=motivo.nodo, funcion=motivo.funcion, parametro=None),
    )


def _expresion_de_segmento(item: ExpresionSegmento) -> ExpresionSegmentoRespuesta:
    rango = _RANGO[item.segmento]
    usadas = variables_usadas(item.expresion)
    return ExpresionSegmentoRespuesta(
        segmento=item.segmento,
        etiqueta=rango.etiqueta,
        dias_desde=rango.desde,
        dias_hasta=rango.hasta,
        expresion=ExpresionGuardadaRespuesta.model_validate(expresion_a_dict(item.expresion)),
        usa_titular=VARIABLE_TITULAR in usadas,
        usa_vencimiento=VARIABLE_VENCIMIENTO in usadas,
        usa_whatsapp=VARIABLE_CONTACTO in usadas,
    )


def _version(version: VersionSpeech) -> VersionSpeechRespuesta:
    return VersionSpeechRespuesta(
        id=version.id,
        nombre=version.datos.nombre,
        formato=version.datos.formato,
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
        expresiones=[_expresion_de_segmento(e) for e in version.datos.expresiones],
    )


def _traducir(exc: Exception) -> HTTPException:
    if isinstance(exc, SpeechNoEncontrado):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (SpeechInmutable, NombreDeSpeechRepetido)):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


def _respuesta_de_error(exc: Exception) -> JSONResponse:
    """El 400 con sus problemas; el 404 y el 409 siguen siendo `{"detail"}`."""
    if isinstance(exc, SpeechInvalido):
        return _error_400(str(exc), exc.problemas)
    if isinstance(exc, ConfiguracionInvalida):
        return _error_400(str(exc))
    http = _traducir(exc)
    return JSONResponse(status_code=http.status_code, content={"detail": http.detail})


@router.get("/speech", response_model=list[VersionSpeechRespuesta])
def listar_speech(
    servicio: ConfiguracionMowaMesService = Depends(obtener_servicio_mowa_mes),
) -> list[VersionSpeechRespuesta]:
    return [_version(version) for version in servicio.listar_speech()]


@router.post(
    "/speech/previsualizacion",
    response_model=PrevisualizacionRespuesta,
    responses=_RESPUESTAS_400,
)
def previsualizar_speech(
    entrada: PrevisualizacionEntrada,
    servicio: ConfiguracionMowaMesService = Depends(obtener_servicio_mowa_mes),
) -> Any:
    """Largo maximo de cada segmento, con titular de 8 y fecha de 10 (RF-MM-19).

    Con `expresiones` (v2) devuelve por segmento el largo maximo (la cota de la expresion), el
    nivel (`codigo`: 150 o 160 si lo cruza) y el ejemplo evaluado; sin maximo calculable,
    `largo_maximo` es nulo y `sin_maximo` dice por que. El control de los 160 caracteres de la
    campana es por fila, sobre el mensaje real.

    Un segmento que usa [whatsapp] sin numero se marca con `falta_whatsapp` y sin
    ejemplo: nunca se muestra un enlace roto.
    """
    try:
        partes, expresiones = _contenido(entrada.partes, entrada.expresiones)
        if entrada.expresiones is not None:
            whatsapp, problemas, largos = servicio.previsualizar_speech_v2(
                expresiones, entrada.whatsapp
            )
        else:
            whatsapp, problemas, largos = servicio.previsualizar_speech(partes, entrada.whatsapp)
    except (ConfiguracionInvalida, SpeechInvalido) as exc:
        return _respuesta_de_error(exc)
    return PrevisualizacionRespuesta(
        whatsapp=whatsapp,
        largo_advertencia=LARGO_ADVERTENCIA,
        largo_maximo=LARGO_MAXIMO,
        problemas=[_problema(p) for p in problemas],
        segmentos=[
            LargoSegmentoRespuesta(
                segmento=largo.rango.segmento,
                etiqueta=largo.rango.etiqueta,
                usa_whatsapp=largo.usa_whatsapp,
                falta_whatsapp=largo.usa_whatsapp and whatsapp is None,
                largo_maximo=largo.largo_maximo,
                sin_maximo=_sin_maximo(largo.motivo_sin_cota),
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


@router.get(
    "/speech/{speech_id}/como-v2",
    response_model=BorradorV2Respuesta,
    responses={**_RESPUESTAS_400, **respuestas_de_error(404)},
)
def convertir_a_v2(
    speech_id: int,
    servicio: ConfiguracionMowaMesService = Depends(obtener_servicio_mowa_mes),
) -> Any:
    """El borrador v2 de una v1: la misma estructura expresada con el motor, que da los mismos
    mensajes y largos (con el titular y la fecha obligatorios). No guarda nada: se edita y se
    guarda con `POST /speech` y `basada_en_id`, como una version nueva con huella propia. La v1
    queda intacta. Una version que ya es v2 responde 400."""
    try:
        borrador: BorradorV2 = servicio.como_v2(speech_id)
    except (SpeechNoEncontrado, SpeechInvalido) as exc:
        return _respuesta_de_error(exc)
    return BorradorV2Respuesta(
        basada_en_id=borrador.basada_en_id,
        nombre_sugerido=borrador.nombre_sugerido,
        expresiones=[_expresion_de_segmento(e) for e in borrador.expresiones],
        problemas=[_problema(p) for p in borrador.problemas],
    )


@router.post(
    "/speech",
    status_code=201,
    response_model=VersionSpeechRespuesta,
    responses={**_RESPUESTAS_400, **respuestas_de_error(404, 409)},
)
def crear_speech(
    entrada: SpeechNuevoEntrada,
    servicio: ConfiguracionMowaMesService = Depends(obtener_servicio_mowa_mes),
) -> Any:
    """Guarda una version nueva, v1 (`partes`) o v2 (`expresiones`). 404 si `basada_en_id` no
    existe."""
    try:
        partes, expresiones = _contenido(entrada.partes, entrada.expresiones)
        if entrada.expresiones is not None:
            version = servicio.crear_speech_v2(entrada.nombre, expresiones, entrada.basada_en_id)
        else:
            version = servicio.crear_speech(entrada.nombre, partes, entrada.basada_en_id)
        return _version(version)
    except (SpeechInvalido, SpeechNoEncontrado, NombreDeSpeechRepetido) as exc:
        return _respuesta_de_error(exc)


@router.put(
    "/speech/{speech_id}",
    response_model=VersionSpeechRespuesta,
    responses={**_RESPUESTAS_400, **respuestas_de_error(404, 409)},
)
def actualizar_speech(
    speech_id: int,
    entrada: SpeechEdicionEntrada,
    servicio: ConfiguracionMowaMesService = Depends(obtener_servicio_mowa_mes),
) -> Any:
    """Reemplaza una version que nadie uso, en su mismo formato. Si ya se uso o es la original,
    409; si el contenido es del otro formato, 400."""
    try:
        partes, expresiones = _contenido(entrada.partes, entrada.expresiones)
        formato = FormatoSpeech.V2 if entrada.expresiones is not None else FormatoSpeech.V1
        datos = DatosSpeech(
            nombre=entrada.nombre, partes=partes, expresiones=expresiones, formato=formato
        )
        return _version(servicio.actualizar_speech(speech_id, datos))
    except (SpeechInvalido, SpeechNoEncontrado, SpeechInmutable, NombreDeSpeechRepetido) as exc:
        return _respuesta_de_error(exc)

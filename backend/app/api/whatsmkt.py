"""Adaptador de entrada HTTP del modulo WhatsMKT (docs/requerimientos-whatsmkt.md).

Primer corte (T-WM-B1), configuracion y segmentos:

    GET  /whatsmkt/configuracion   horarios, plantilla del nombre, definicion por defecto, topes
    PUT  /whatsmkt/configuracion   actualizacion parcial (como la de MOWA MES)
    GET  /whatsmkt/segmentos       de menor a mayor
    PUT  /whatsmkt/segmentos       edita etiqueta y limites de los 3 segmentos fijos

Una regla de negocio rota responde `422` con `{detail, codigo}`, donde `codigo` es de
`CodigoWhatsmkt` (el frontend lo traduce como `whatsmkt.codigo.<codigo>`). Un campo mal formado
(una hora que no es HH:MM, un tope menor que 1, un `null` donde no cabe, otras claves de
segmento) responde el `422` de validacion de FastAPI.
Los adjuntos (biblioteca de RF-WM-30) van en B5: B1 deja solo el repositorio.
"""

from dataclasses import replace
from datetime import datetime, time
from typing import Annotated, Self

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import AfterValidator, BaseModel, Field, StringConstraints, model_validator

from app.adapters.persistence.db import get_engine
from app.adapters.persistence.repositorio_definiciones_postgres import (
    RepositorioDefinicionesPostgres,
)
from app.adapters.persistence.repositorio_whatsmkt_postgres import RepositorioWhatsmktPostgres
from app.api.errores import DetalleError, ErrorConCodigo, respuestas_de_error
from app.api.respuestas import ModeloRespuesta
from app.core.entities.whatsmkt import (
    CLAVES_SEGMENTOS,
    VARIABLES_PLANTILLA,
    CodigoWhatsmkt,
    ConfiguracionWhatsmkt,
    DefinicionDefectoNoExiste,
    ErrorWhatsmkt,
    Horario,
    SegmentoWhatsmkt,
)
from app.core.services.plataformas.whatsmkt.administracion import ConfiguracionWhatsmktService

router = APIRouter(prefix="/whatsmkt", tags=["whatsmkt"])

_HORA = r"^([01][0-9]|2[0-3]):[0-5][0-9]$"
_MAXIMO_DIAS = 100_000
_MAXIMO_TOPE = 2_000_000_000
PARAMETROS = ("horarios", "variable", "segmento", "fila", "desde", "hasta") + (
    "peso",
    "maximo",
    "tipo",
    "ancho",
    "alto",
)


def obtener_servicio_whatsmkt() -> ConfiguracionWhatsmktService:
    """Dependencia de FastAPI; los tests la sustituyen por un doble de prueba."""
    return ConfiguracionWhatsmktService(
        RepositorioWhatsmktPostgres(get_engine()), RepositorioDefinicionesPostgres(get_engine())
    )


class ErrorWhatsmktRespuesta(DetalleError):
    """422 de una regla de negocio: el motivo, el codigo que la interfaz traduce y los datos que
    su texto nombra. Los parametros siempre viajan; los que el codigo no usa van nulos."""

    codigo: CodigoWhatsmkt
    horarios: list[str] | None = Field(description="horario_invalido: las franjas que fallan")
    variable: str | None = Field(description="variable_inexistente: la que no existe")
    segmento: str | None = Field(
        description="segmentos_superpuestos: el segmento con el que se pisa"
    )
    fila: str | None = Field(description="segmentos_superpuestos: la fila bajo la que se muestra")
    desde: int | None = Field(
        description="segmentos_con_hueco: primer dia sin segmento (null: -inf)"
    )
    hasta: int | None = Field(
        description="segmentos_con_hueco: ultimo dia sin segmento (null: +inf)"
    )
    peso: int | None = Field(description="adjunto_peso y foto_peso: bytes del archivo")
    maximo: int | None = Field(description="adjunto_peso: bytes que admite ese tipo")
    tipo: str | None = Field(
        description="adjunto_peso: el tipo (video, audio, pdf, imagen_jpeg...)"
    )
    ancho: int | None = Field(description="foto_medidas: ancho leido del archivo, en pixeles")
    alto: int | None = Field(description="foto_medidas: alto leido del archivo, en pixeles")


def error_whatsmkt(exc: ErrorWhatsmkt) -> ErrorConCodigo:
    """El `ErrorWhatsmkt` como 422 `{detail, codigo, ...parametros}`."""
    parametros = {campo: None for campo in PARAMETROS} | exc.parametros
    return ErrorConCodigo(422, str(exc), exc.codigo, parametros)


RESPUESTA_422 = {
    422: {
        "model": ErrorWhatsmktRespuesta,
        "description": "Una regla del modulo no se cumple; `codigo` dice cual y `detail` el motivo",
    }
}


# --- Configuracion -------------------------------------------------------


class HorarioWhatsmktEntrada(BaseModel):
    inicio: str = Field(pattern=_HORA, description="HH:MM, 24 horas")
    fin: str = Field(pattern=_HORA, description="HH:MM, 24 horas; posterior al inicio")

    def a_horario(self) -> Horario:
        return Horario(time.fromisoformat(self.inicio), time.fromisoformat(self.fin))


class HorarioWhatsmktRespuesta(ModeloRespuesta):
    inicio: str
    fin: str


class ConfiguracionWhatsmktEntrada(BaseModel):
    """Todos los campos son opcionales: uno omitido conserva el guardado y un `null` en uno que
    no admite vacio responde 422 (como la configuracion de MOWA MES). Solo la definicion por
    defecto admite `null`: quita la elegida."""

    # Sin null en los tipos: el defecto None solo marca "omitido" (no se valida); un null
    # explicito no es del tipo y responde 422.
    horario_1: HorarioWhatsmktEntrada = Field(default=None, description="Franja 1 (RF-WM-07)")
    horario_2: HorarioWhatsmktEntrada = Field(default=None, description="Franja 2 (RF-WM-07)")
    plantilla_nombre: str = Field(
        default=None,
        max_length=300,
        description=(
            "Plantilla del nombre de campana (RF-WM-33): texto fijo con {fecha_corte} y "
            "{segmento}. Vacia, vuelve la de por defecto"
        ),
    )
    definicion_defecto_id: int | None = Field(
        default=None,
        description="Definicion de carga por defecto (RF-WM-04); null la quita",
    )
    tope_mensaje: int = Field(
        default=None, gt=0, le=_MAXIMO_TOPE, description="Caracteres, mayor que 0 (RF-WM-26)"
    )
    tope_video: int = Field(
        default=None, gt=0, le=_MAXIMO_TOPE, description="Bytes, mayor que 0 (RF-WM-31)"
    )
    tope_audio: int = Field(
        default=None, gt=0, le=_MAXIMO_TOPE, description="Bytes, mayor que 0 (RF-WM-31)"
    )
    tope_pdf: int = Field(
        default=None, gt=0, le=_MAXIMO_TOPE, description="Bytes, mayor que 0 (RF-WM-31)"
    )

    def sobre(self, actual: ConfiguracionWhatsmkt) -> ConfiguracionWhatsmkt:
        """La configuracion guardada con los campos que vinieron."""
        enviados = self.model_fields_set
        cambios = {campo: getattr(self, campo) for campo in enviados}
        for campo in ("horario_1", "horario_2"):
            if campo in cambios:
                cambios[campo] = cambios[campo].a_horario()
        return replace(actual, **cambios)


class ConfiguracionWhatsmktRespuesta(ModeloRespuesta):
    horario_1: HorarioWhatsmktRespuesta
    horario_2: HorarioWhatsmktRespuesta
    plantilla_nombre: str
    definicion_defecto_id: int | None
    tope_mensaje: int
    tope_video: int
    tope_audio: int
    tope_pdf: int
    actualizado_en: datetime | None
    variables_plantilla: list[str] = Field(description="Las variables validas de la plantilla")


def _hora(valor: time) -> str:
    return valor.strftime("%H:%M")


def _horario(horario: Horario) -> HorarioWhatsmktRespuesta:
    return HorarioWhatsmktRespuesta(inicio=_hora(horario.inicio), fin=_hora(horario.fin))


def _configuracion(c: ConfiguracionWhatsmkt) -> ConfiguracionWhatsmktRespuesta:
    return ConfiguracionWhatsmktRespuesta(
        horario_1=_horario(c.horario_1),
        horario_2=_horario(c.horario_2),
        plantilla_nombre=c.plantilla_nombre,
        definicion_defecto_id=c.definicion_defecto_id,
        tope_mensaje=c.tope_mensaje,
        tope_video=c.tope_video,
        tope_audio=c.tope_audio,
        tope_pdf=c.tope_pdf,
        actualizado_en=c.actualizado_en,
        variables_plantilla=list(VARIABLES_PLANTILLA),
    )


@router.get("/configuracion", response_model=ConfiguracionWhatsmktRespuesta)
def obtener_configuracion(
    servicio: ConfiguracionWhatsmktService = Depends(obtener_servicio_whatsmkt),
) -> ConfiguracionWhatsmktRespuesta:
    return _configuracion(servicio.obtener_configuracion())


@router.put(
    "/configuracion",
    summary="Actualizar la configuracion de WhatsMKT (parcial)",
    response_model=ConfiguracionWhatsmktRespuesta,
    responses={**RESPUESTA_422, **respuestas_de_error(404)},
)
def guardar_configuracion(
    entrada: ConfiguracionWhatsmktEntrada,
    servicio: ConfiguracionWhatsmktService = Depends(obtener_servicio_whatsmkt),
) -> ConfiguracionWhatsmktRespuesta:
    """Actualizacion parcial sobre PUT: un campo omitido conserva el guardado.

    - `null` en un campo que no admite vacio responde 422 de validacion.
    - `definicion_defecto_id: null` quita la definicion por defecto; una que no existe es 404.
    - Un tope menor o igual a cero responde el 422 de validacion, sin codigo.
    - Un horario con inicio igual o posterior al fin (`horarios` dice cuales franjas) o una
      variable desconocida en la plantilla (`variable`) responden 422 con su `codigo`.
    """
    try:
        return _configuracion(
            servicio.guardar_configuracion(entrada.sobre(servicio.obtener_configuracion()))
        )
    except ErrorWhatsmkt as exc:
        raise error_whatsmkt(exc) from exc
    except DefinicionDefectoNoExiste as exc:
        raise HTTPException(404, str(exc)) from exc


# --- Segmentos -----------------------------------------------------------


class SegmentoWhatsmktEntrada(BaseModel):
    clave: str = Field(description="Una de las 3 fijas: preventivo, tramo_2 o mayores_2")
    etiqueta: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    desde: int | None = Field(ge=-_MAXIMO_DIAS, le=_MAXIMO_DIAS, description="null: sin piso")
    hasta: int | None = Field(ge=-_MAXIMO_DIAS, le=_MAXIMO_DIAS, description="null: sin tope")

    @model_validator(mode="after")
    def _rango(self) -> Self:
        if self.desde is not None and self.hasta is not None and self.desde > self.hasta:
            raise ValueError("desde no puede ser mayor que hasta")
        return self


def _las_tres_fijas(segmentos: list[SegmentoWhatsmktEntrada]) -> list[SegmentoWhatsmktEntrada]:
    """Los segmentos son fijos: exactamente los 3 de S-WM-1, cada uno una vez."""
    if sorted(s.clave for s in segmentos) != sorted(CLAVES_SEGMENTOS):
        raise ValueError(f"Los segmentos son {', '.join(sorted(CLAVES_SEGMENTOS))}, uno cada uno")
    return segmentos


class SegmentoWhatsmktRespuesta(ModeloRespuesta):
    clave: str
    etiqueta: str
    desde: int | None
    hasta: int | None
    orden: int


def _segmentos(segmentos: list[SegmentoWhatsmkt]) -> list[SegmentoWhatsmktRespuesta]:
    return [
        SegmentoWhatsmktRespuesta(
            clave=s.clave, etiqueta=s.etiqueta, desde=s.desde, hasta=s.hasta, orden=s.orden
        )
        for s in segmentos
    ]


@router.get("/segmentos", response_model=list[SegmentoWhatsmktRespuesta])
def listar_segmentos(
    servicio: ConfiguracionWhatsmktService = Depends(obtener_servicio_whatsmkt),
) -> list[SegmentoWhatsmktRespuesta]:
    return _segmentos(servicio.listar_segmentos())


@router.put(
    "/segmentos",
    summary="Editar los 3 segmentos (etiqueta y limites)",
    response_model=list[SegmentoWhatsmktRespuesta],
    responses=RESPUESTA_422,
)
def reemplazar_segmentos(
    entrada: Annotated[list[SegmentoWhatsmktEntrada], AfterValidator(_las_tres_fijas), Body()],
    servicio: ConfiguracionWhatsmktService = Depends(obtener_servicio_whatsmkt),
) -> list[SegmentoWhatsmktRespuesta]:
    """Edita la etiqueta y los limites de los 3 segmentos fijos, en una transaccion (RF-WM-20).
    El `orden` lo fija la API, de menor a mayor.

    Otras claves, una repetida o una que falta responden el 422 de validacion, sin codigo.
    Segmentos que se superponen o dejan huecos responden 422 con su `codigo` y sus parametros, y
    la tabla anterior queda como estaba."""
    nuevos = [SegmentoWhatsmkt(s.clave, s.etiqueta, s.desde, s.hasta, 0) for s in entrada]
    try:
        return _segmentos(servicio.reemplazar_segmentos(nuevos))
    except ErrorWhatsmkt as exc:
        raise error_whatsmkt(exc) from exc

"""Seguimiento de las campanas de WhatsMKT por HTTP (T-WM-B6; RF-WM-37 a RF-WM-42).

    POST   /whatsmkt/campanas/{id}/reportes       importar el informe de WhatsMKT (multipart)
    GET    /whatsmkt/campanas/{id}/conciliacion   cargados contra enviados, por numero
    POST   /whatsmkt/campanas/{id}/descartar      logico: no borra nada
    POST   /whatsmkt/campanas/{id}/restaurar      la devuelve a las activas
    DELETE /whatsmkt/campanas/{id}                solo si esta descartada

La lista y el detalle (con el filtro de estado y si tiene informe) estan en `whatsmkt_campanas`.
Los rechazos viajan con su `codigo`: el 409 del estado de la campana o del informe, el 422 del
contenido del informe.
"""

import os
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import Field

from app.adapters.input.lector_informe_whatsmkt import leer_tabla_del_informe
from app.adapters.persistence.db import get_engine
from app.adapters.persistence.repositorio_campanas_whatsmkt_postgres import (
    RepositorioCampanasWhatsmktPostgres,
)
from app.api.errores import ErrorConCodigo, respuestas_de_error
from app.api.respuestas import ModeloRespuesta
from app.api.whatsmkt import RESPUESTA_422, error_whatsmkt
from app.api.whatsmkt_campanas import ResumenCampanaWhatsmktRespuesta, respuesta_resumen
from app.core.entities.whatsmkt import CodigoWhatsmkt, ErrorWhatsmkt
from app.core.entities.whatsmkt_campana import (
    CampanaDescartada,
    CampanaNoDescartada,
    CampanaNoEncontrada,
    InformeYaImportado,
)
from app.core.entities.whatsmkt_informe import CifrasWhatsmkt
from app.core.services.plataformas.whatsmkt.gestion import GestionCampanasWhatsmktService
from app.core.services.plataformas.whatsmkt.informes import (
    EstadoInforme,
    InformesWhatsmktService,
)

router = APIRouter(prefix="/whatsmkt/campanas", tags=["whatsmkt"])

TAMANO_MAXIMO_INFORME = 32 * 1024 * 1024  # el informe de una campana grande; como el de MOWA


class ErrorCampanaWhatsmktRespuesta(ModeloRespuesta):
    """409: el estado de la campana o del informe impide la operacion; `codigo` dice cual."""

    detail: str
    codigo: CodigoWhatsmkt


class InformeWhatsmktRespuesta(ModeloRespuesta):
    """Lo que informa WhatsMKT y el archivo del que salio."""

    archivo_nombre: str
    importado_en: datetime
    fecha_informada: date | None = Field(description="La fila FECHA; nula si no se entendio")
    total_informado: int | None = Field(
        description="La fila TOTAL DE ENVIO; nula si no se entendio"
    )
    filas: int = Field(description="Filas de detalle del informe (un numero cada una)")
    coincide_total: bool | None = Field(
        description="Si el total informado es `filas`; nulo si no se informo (DU-WM-7: no rechaza)"
    )
    campana_informada: str | None = Field(
        description="El nombre que trae el informe: solo para leer, no se compara"
    )
    tipo_envio_informado: str | None


class CifrasConciliacionWhatsmktRespuesta(ModeloRespuesta):
    cargados: int
    enviados: int
    no_enviados: int


class ConciliacionWhatsmktRespuesta(ModeloRespuesta):
    productos: CifrasConciliacionWhatsmktRespuesta
    supervision: CifrasConciliacionWhatsmktRespuesta = Field(
        description="Los registros de supervision, aparte de los productos (RF-41)"
    )
    total: CifrasConciliacionWhatsmktRespuesta
    sin_correspondencia: list[str] = Field(
        description="Numeros del informe que no estan en la carga, sin repetir"
    )
    total_sin_correspondencia: int


class EstadoInformeWhatsmktRespuesta(ModeloRespuesta):
    campana_id: int
    pendiente: bool = Field(description="Verdadero si la campana todavia no tiene informe")
    informe: InformeWhatsmktRespuesta | None = Field(description="Nulo si esta pendiente")
    conciliacion: ConciliacionWhatsmktRespuesta | None = Field(description="Nula si esta pendiente")


def _cifras(c: CifrasWhatsmkt) -> CifrasConciliacionWhatsmktRespuesta:
    return CifrasConciliacionWhatsmktRespuesta(
        cargados=c.cargados, enviados=c.enviados, no_enviados=c.no_enviados
    )


def _estado(campana_id: int, estado: EstadoInforme) -> EstadoInformeWhatsmktRespuesta:
    if estado.reporte is None or estado.conciliacion is None:
        return EstadoInformeWhatsmktRespuesta(
            campana_id=campana_id, pendiente=True, informe=None, conciliacion=None
        )
    r, informe, c = estado.reporte, estado.reporte.informe, estado.conciliacion
    return EstadoInformeWhatsmktRespuesta(
        campana_id=campana_id,
        pendiente=False,
        informe=InformeWhatsmktRespuesta(
            archivo_nombre=r.archivo_nombre,
            importado_en=r.importado_en,
            fecha_informada=informe.fecha_informada,
            total_informado=informe.total_informado,
            filas=len(informe.numeros),
            coincide_total=informe.coincide_total,
            campana_informada=informe.campana,
            tipo_envio_informado=informe.tipo_envio,
        ),
        conciliacion=ConciliacionWhatsmktRespuesta(
            productos=_cifras(c.productos),
            supervision=_cifras(c.supervision),
            total=_cifras(c.total),
            sin_correspondencia=list(c.sin_correspondencia),
            total_sin_correspondencia=c.total_sin_correspondencia,
        ),
    )


def _no_encontrada(exc: CampanaNoEncontrada) -> ErrorConCodigo:
    return ErrorConCodigo(404, str(exc), None)


def obtener_servicio_informes_whatsmkt() -> InformesWhatsmktService:
    """Dependencia de FastAPI; los tests la sustituyen por un doble de prueba."""
    return InformesWhatsmktService(
        RepositorioCampanasWhatsmktPostgres(get_engine()), leer_tabla_del_informe
    )


def obtener_servicio_gestion_whatsmkt() -> GestionCampanasWhatsmktService:
    """Dependencia de FastAPI; los tests la sustituyen por un doble de prueba."""
    return GestionCampanasWhatsmktService(RepositorioCampanasWhatsmktPostgres(get_engine()))


_RESPUESTA_409 = {
    "model": ErrorCampanaWhatsmktRespuesta,
    "description": "El estado de la campana o del informe lo impide; `codigo` dice cual",
}


@router.post(
    "/{campana_id}/reportes",
    status_code=201,
    summary="Importar el informe de WhatsMKT",
    response_model=EstadoInformeWhatsmktRespuesta,
    responses={
        **respuestas_de_error(404, 413),
        409: {
            **_RESPUESTA_409,
            "description": (
                "La campana ya tiene un informe y no se pidio reemplazarlo (`informe_ya_importado`)"
                ", o esta descartada y hay que restaurarla primero (`campana_descartada`)"
            ),
        },
        **RESPUESTA_422,
    },
)
async def importar_informe(
    campana_id: int,
    archivo: UploadFile = File(
        description=(
            "El informe que genera WhatsMKT al terminar el envio (hoja «Informe»), en cualquiera "
            "de los formatos de la sabana: .xlsx, .xlsb, .xls, .ods, .csv, .tsv, .txt o .json"
        )
    ),
    reemplazar: bool = Form(
        default=False, description="Reemplazar el informe que la campana ya tenia (RF-WM-38)"
    ),
    servicio: InformesWhatsmktService = Depends(obtener_servicio_informes_whatsmkt),
) -> EstadoInformeWhatsmktRespuesta:
    """Guarda el informe como el vigente de la campana y devuelve su conciliacion (RF-WM-37).

    Un informe sin los encabezados CAMPAÑA, TIPO DE ENVIO y NUMERO, o sin numeros, responde 422 y
    no guarda nada. Reemplazar uno ya importado exige `reemplazar=true`: sin el, responde 409.
    """
    # El tamano sale del propio archivo ya recibido, sin leerlo (como los adjuntos).
    fichero = archivo.file
    fichero.seek(0, os.SEEK_END)
    tamano = fichero.tell()
    fichero.seek(0)
    if tamano > TAMANO_MAXIMO_INFORME:
        raise HTTPException(
            413, f"El archivo supera el maximo de {TAMANO_MAXIMO_INFORME // 1024 // 1024} MB"
        )
    contenido = await archivo.read()
    try:
        estado = servicio.importar(
            campana_id, archivo.filename or "informe.xlsx", contenido, reemplazar
        )
    except CampanaNoEncontrada as exc:
        raise _no_encontrada(exc) from exc
    except CampanaDescartada as exc:
        raise ErrorConCodigo(409, str(exc), CodigoWhatsmkt.CAMPANA_DESCARTADA) from exc
    except InformeYaImportado as exc:
        raise ErrorConCodigo(409, str(exc), CodigoWhatsmkt.INFORME_YA_IMPORTADO) from exc
    except ErrorWhatsmkt as exc:
        raise error_whatsmkt(exc) from exc
    return _estado(campana_id, estado)


@router.get(
    "/{campana_id}/conciliacion",
    summary="Conciliacion de la campana con su informe",
    response_model=EstadoInformeWhatsmktRespuesta,
    responses=respuestas_de_error(404),
)
def conciliacion(
    campana_id: int,
    servicio: InformesWhatsmktService = Depends(obtener_servicio_informes_whatsmkt),
) -> EstadoInformeWhatsmktRespuesta:
    """Los productos y la supervision cargados contra los numeros del informe (RF-WM-39).

    Una campana sin informe no es un error: responde 200 con `pendiente=true` y sin cifras. El 404
    es solo para una campana que no existe.
    """
    try:
        return _estado(campana_id, servicio.estado(campana_id))
    except CampanaNoEncontrada as exc:
        raise _no_encontrada(exc) from exc


@router.post(
    "/{campana_id}/descartar",
    summary="Descartar una campana",
    response_model=ResumenCampanaWhatsmktRespuesta,
    responses=respuestas_de_error(404),
)
def descartar_campana(
    campana_id: int,
    servicio: GestionCampanasWhatsmktService = Depends(obtener_servicio_gestion_whatsmkt),
) -> ResumenCampanaWhatsmktRespuesta:
    """La saca de las activas sin borrar nada (RF-WM-41). Descartar una ya descartada no cambia
    nada."""
    try:
        return respuesta_resumen(servicio.descartar(campana_id))
    except CampanaNoEncontrada as exc:
        raise _no_encontrada(exc) from exc


@router.post(
    "/{campana_id}/restaurar",
    summary="Restaurar una campana descartada",
    response_model=ResumenCampanaWhatsmktRespuesta,
    responses=respuestas_de_error(404),
)
def restaurar_campana(
    campana_id: int,
    servicio: GestionCampanasWhatsmktService = Depends(obtener_servicio_gestion_whatsmkt),
) -> ResumenCampanaWhatsmktRespuesta:
    """La devuelve a las activas (RF-WM-42)."""
    try:
        return respuesta_resumen(servicio.restaurar(campana_id))
    except CampanaNoEncontrada as exc:
        raise _no_encontrada(exc) from exc


@router.delete(
    "/{campana_id}",
    status_code=204,
    summary="Eliminar una campana descartada",
    responses={
        **respuestas_de_error(404),
        409: {
            **_RESPUESTA_409,
            "description": "La campana esta activa: solo se elimina una descartada",
        },
    },
)
def eliminar_campana(
    campana_id: int,
    servicio: GestionCampanasWhatsmktService = Depends(obtener_servicio_gestion_whatsmkt),
) -> Response:
    """Borra del todo una campana DESCARTADA, con su archivo, filas cargadas, exclusiones e
    informes (RF-WM-42). Si era la ultima de su lote, borra tambien el lote y sus exclusiones de
    fuera del lote. No borra los adjuntos de la biblioteca ni las versiones del mensaje."""
    try:
        servicio.eliminar(campana_id)
    except CampanaNoEncontrada as exc:
        raise _no_encontrada(exc) from exc
    except CampanaNoDescartada as exc:
        raise ErrorConCodigo(409, str(exc), CodigoWhatsmkt.CAMPANA_NO_DESCARTADA) from exc
    return Response(status_code=204)

"""Adaptador de entrada HTTP para la ingesta de sabanas con versionado.

Flujo de docs/versionado-sabanas.md, seccion 4.4: subir el archivo responde de
inmediato y el procesamiento sigue en segundo plano; el frontend consulta el
estado y, si la fecha ya tenia una version vigente, decide si la reemplaza.
"""

import logging
from datetime import date, datetime

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict

from app.adapters.input.lector_calamine import LectorCalamine
from app.adapters.persistence.db import get_engine
from app.adapters.persistence.repositorio_cargas_postgres import RepositorioCargasPostgres
from app.core.entities.carga import (
    CargaDetalle,
    CargaNoEncontrada,
    CargaNoProcesable,
    EliminacionNoPermitida,
    EstadoCarga,
    VigenciaNoPermitida,
)
from app.core.entities.sabana import HOJA_DATOS_POR_DEFECTO, Incidencia, Severidad
from app.core.services.ingesta_sabana.servicio import IngestaSabanaService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cargas", tags=["cargas"])

TAMANO_MAXIMO_BYTES = 64 * 1024 * 1024


def crear_servicio_ingesta() -> IngestaSabanaService:
    return IngestaSabanaService(RepositorioCargasPostgres(get_engine()), LectorCalamine())


def obtener_servicio() -> IngestaSabanaService:
    """Dependencia de FastAPI; los tests la sustituyen por un doble de prueba."""
    return crear_servicio_ingesta()


class VersionRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fecha_corte: date
    version: int
    estado: EstadoCarga
    vigente: bool
    nombre_archivo: str
    tamano_bytes: int
    hoja: str
    creado_en: datetime
    procesado_en: datetime | None = None
    huella_formato: str | None = None
    filas_total: int | None = None
    filas_ingestadas: int | None = None
    incidencias_error: int = 0
    incidencias_advertencia: int = 0
    incidencias_info: int = 0
    motivo_fallo: str | None = None


class CargaCreadaRespuesta(BaseModel):
    id: int
    fecha_corte: date
    version: int
    estado: EstadoCarga
    versiones_identicas: list[int]
    aviso: str | None = None


class IncidenciaRespuesta(BaseModel):
    fila: int | None
    columna: str | None
    codigo: str
    severidad: Severidad
    detalle: str
    valor_original: str | None = None


class IncidenciasRespuesta(BaseModel):
    total: int
    incidencias: list[IncidenciaRespuesta]


def _a_incidencia(incidencia: Incidencia) -> IncidenciaRespuesta:
    valor = incidencia.valor_original
    return IncidenciaRespuesta(
        fila=incidencia.fila,
        columna=incidencia.columna,
        codigo=incidencia.codigo,
        severidad=incidencia.severidad,
        detalle=incidencia.detalle,
        valor_original=None if valor is None else str(valor),
    )


def _procesar_en_segundo_plano(servicio: IngestaSabanaService, carga_id: int) -> None:
    try:
        resultado = servicio.procesar_carga(carga_id)
        logger.info(
            "Carga %s procesada: %s, %s filas guardadas",
            carga_id,
            resultado.estado.value,
            resultado.resumen.filas_ingestadas,
        )
    except Exception as exc:
        # Solo el tipo: los mensajes pueden arrastrar valores de la sabana.
        logger.error("Error al procesar la carga %s (%s)", carga_id, type(exc).__name__)


@router.post("", status_code=202, response_model=CargaCreadaRespuesta)
async def subir_sabana(
    tareas: BackgroundTasks,
    fecha_corte: date = Form(description="Fecha del corte que representa la sabana"),
    archivo: UploadFile = File(description="Archivo de la sabana (.xlsb, .xlsx)"),
    hoja: str = Form(default=HOJA_DATOS_POR_DEFECTO),
    servicio: IngestaSabanaService = Depends(obtener_servicio),
) -> CargaCreadaRespuesta:
    """Registra una version nueva y lanza su procesamiento en segundo plano (V-1)."""
    contenido = await archivo.read()
    if not contenido:
        raise HTTPException(status_code=400, detail="El archivo esta vacio")
    if len(contenido) > TAMANO_MAXIMO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"El archivo supera el maximo de {TAMANO_MAXIMO_BYTES // 1024 // 1024} MB",
        )

    registro = await run_in_threadpool(
        servicio.registrar_carga, fecha_corte, archivo.filename or "sabana", contenido, hoja
    )
    tareas.add_task(_procesar_en_segundo_plano, servicio, registro.carga.id)

    aviso = None
    if registro.versiones_identicas:
        aviso = (
            "Este archivo es identico al de las versiones "
            f"{registro.versiones_identicas} de la misma fecha"
        )
    return CargaCreadaRespuesta(
        id=registro.carga.id,
        fecha_corte=registro.carga.fecha_corte,
        version=registro.carga.version,
        estado=registro.carga.estado,
        versiones_identicas=registro.versiones_identicas,
        aviso=aviso,
    )


@router.get("", response_model=list[VersionRespuesta])
def listar_versiones(
    fecha_corte: date | None = Query(default=None),
    limite: int = Query(default=50, ge=1, le=200),
    desplazamiento: int = Query(default=0, ge=0),
    servicio: IngestaSabanaService = Depends(obtener_servicio),
) -> list[CargaDetalle]:
    return servicio.listar_versiones(fecha_corte, limite, desplazamiento)


@router.get("/{carga_id}", response_model=VersionRespuesta)
def obtener_version(
    carga_id: int, servicio: IngestaSabanaService = Depends(obtener_servicio)
) -> CargaDetalle:
    try:
        return servicio.obtener(carga_id)
    except CargaNoEncontrada as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{carga_id}/incidencias", response_model=IncidenciasRespuesta)
def listar_incidencias(
    carga_id: int,
    severidad: Severidad | None = Query(default=None),
    limite: int = Query(default=100, ge=1, le=500),
    desplazamiento: int = Query(default=0, ge=0),
    servicio: IngestaSabanaService = Depends(obtener_servicio),
) -> IncidenciasRespuesta:
    try:
        total, incidencias = servicio.incidencias(carga_id, severidad, limite, desplazamiento)
    except CargaNoEncontrada as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return IncidenciasRespuesta(total=total, incidencias=[_a_incidencia(i) for i in incidencias])


@router.post("/{carga_id}/vigente", response_model=VersionRespuesta)
def asignar_vigente(
    carga_id: int, servicio: IngestaSabanaService = Depends(obtener_servicio)
) -> CargaDetalle:
    """Regla V-7: elige que version se considera para su fecha."""
    try:
        servicio.asignar_vigente(carga_id)
        return servicio.obtener(carga_id)
    except CargaNoEncontrada as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except VigenciaNoPermitida as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/{carga_id}", status_code=204)
def eliminar_version(
    carga_id: int,
    dejar_fecha_sin_vigente: bool = Query(
        default=False, description="Confirma que la fecha quede sin version vigente (V-8)"
    ),
    servicio: IngestaSabanaService = Depends(obtener_servicio),
) -> None:
    try:
        servicio.eliminar_version(carga_id, dejar_fecha_sin_vigente)
    except CargaNoEncontrada as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (EliminacionNoPermitida, CargaNoProcesable) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

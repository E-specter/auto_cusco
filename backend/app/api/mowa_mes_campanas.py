"""Adaptador de entrada HTTP de las campanas de MOWA MES (segundo corte del contrato, B6b).

    POST /mowa-mes/campanas/previsualizacion         sin guardar: cifras, muestra, exclusiones,
                                                     errores, archivos previstos y limite
    POST /mowa-mes/campanas                          crear (201); 409 limite sin confirmar o
                                                     speech cambiado
    GET  /mowa-mes/campanas                          listado, las mas recientes primero
    GET  /mowa-mes/campanas/{id}
    GET  /mowa-mes/campanas/{id}/exclusiones         paginadas, filtrables por codigo
    GET  /mowa-mes/campanas/{id}/archivos/{n}        el .xlsx, con el resumen en X-Mowa-Mes-*
    GET  /mowa-mes/limite-mensual?mes=YYYY-MM        consumo del mes (S-MM-7)
    POST /mowa-mes/campanas/{id}/reportes            importar el reporte de enviados (multipart)
    GET  /mowa-mes/campanas/{id}/conciliacion        cargados y enviados

Filtros y orden en la misma sintaxis que `/cartera`.
"""

from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field

from app.adapters.input.lector_reporte_mowa_mes import LectorReporteMowaMes
from app.adapters.output.plataformas.mowa_mes.archivo_carga import escribir_archivo_carga
from app.adapters.persistence.db import get_engine
from app.adapters.persistence.repositorio_campanas_mowa_mes_postgres import (
    RepositorioCampanasMowaMesPostgres,
)
from app.adapters.persistence.repositorio_mowa_mes_postgres import RepositorioMowaMesPostgres
from app.adapters.persistence.repositorio_supervision_postgres import (
    RepositorioSupervisionPostgres,
)
from app.api.cartera import obtener_servicio_cartera
from app.api.errores import respuestas_de_error
from app.api.respuestas import ModeloRespuesta
from app.core.entities.cartera import SinVersionVigente
from app.core.entities.gestiones_digitales import Supervisor
from app.core.entities.mowa_mes import (
    RANGOS_SEGMENTO,
    TIPO_CODIGO,
    CodigoMowaMes,
    Programacion,
    Segmento,
    SpeechNoEncontrado,
    TipoCodigo,
)
from app.core.entities.mowa_mes_campana import (
    ArchivoDemasiadoGrande,
    ArchivoNoEncontrado,
    CampanaArmada,
    CampanaInvalida,
    CampanaNoEncontrada,
    CampanaRegistrada,
    ConsumoLimite,
    Herramientas,
    LimiteMensualExcedido,
    PeticionCampana,
    PeticionCampanaInvalida,
    Salida,
    SpeechCambiado,
    TipoCarga,
)
from app.core.entities.mowa_mes_reporte import CifrasGrupo, ReporteInvalido, ReporteYaImportado
from app.core.services.plataformas.mowa_mes import division
from app.core.services.plataformas.mowa_mes.campana import CampanasMowaMesService
from app.core.services.plataformas.mowa_mes.reportes import (
    EstadoConciliacion,
    ReportesMowaMesService,
)
from app.core.services.seleccion_cartera.servicio import CANTIDAD_MAXIMA, ConsultaCarteraService

router = APIRouter(prefix="/mowa-mes", tags=["mowa-mes"])

FILAS_DE_MUESTRA = 20
EXCLUSIONES_POR_PAGINA = 100
TAMANO_MAXIMO_REPORTE = 32 * 1024 * 1024
TIPO_MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_ETIQUETAS = {rango.segmento: rango.etiqueta for rango in RANGOS_SEGMENTO}

# Resumen que acompana a cada archivo descargado. Una sola lista para lo que se
# envia, lo que declara el contrato y lo que CORS deja leer al navegador.
CABECERAS_ARCHIVO: dict[str, str] = {
    "X-Mowa-Mes-Campana": "Id de la campana",
    "X-Mowa-Mes-Archivo": "Numero de este archivo, desde 1",
    "X-Mowa-Mes-Archivos-Total": "Cantidad de archivos de la campana",
    "X-Mowa-Mes-Filas": "Filas de este archivo, supervision incluida",
    "X-Mowa-Mes-Supervision": "Registros de supervision en este archivo",
    "X-Mowa-Mes-Bytes": "Tamano del archivo en bytes",
}


def obtener_servicio_campanas(
    consulta: ConsultaCarteraService = Depends(obtener_servicio_cartera),
) -> CampanasMowaMesService:
    """Dependencia de FastAPI; los tests la sustituyen por un doble de prueba."""
    engine = get_engine()
    return CampanasMowaMesService(
        consulta,
        RepositorioMowaMesPostgres(engine),
        RepositorioSupervisionPostgres(engine),
        RepositorioCampanasMowaMesPostgres(engine),
        escribir_archivo_carga,
    )


def obtener_servicio_reportes() -> ReportesMowaMesService:
    """Dependencia de FastAPI; los tests la sustituyen por un doble de prueba."""
    return ReportesMowaMesService(
        RepositorioCampanasMowaMesPostgres(get_engine()), LectorReporteMowaMes()
    )


# --- Entrada -------------------------------------------------------------


class HerramientasModelo(BaseModel):
    keyword: bool = False
    respuesta_automatica: bool = False
    blacklist_indecopi: bool = False
    speech_optimizado: bool = False


class SupervisorCampanaEntrada(BaseModel):
    numero: str = Field(max_length=20)
    procedencia: str = Field(max_length=60)


class PeticionCampanaEntrada(BaseModel):
    fecha_corte: date
    filtros: list[str] = []
    orden: str | None = None
    cantidad: int = Field(ge=1, le=CANTIDAD_MAXIMA)
    seleccion_id: int | None = Field(
        default=None, description="Referencia informativa a la seleccion guardada de origen"
    )
    tipo_carga: TipoCarga = TipoCarga.MASIVA
    descripcion: str | None = Field(
        default=None, max_length=1000, description="Sin descripcion se usa la sugerida"
    )
    salida: Salida = Salida.NUMERO_LARGO
    herramientas: HerramientasModelo = HerramientasModelo()
    programacion: Programacion = Programacion.HORA_DETERMINADA
    envios: list[datetime] = Field(
        default=[],
        max_length=50,
        description="Fechas y horas de envio; sin zona horaria se toman en America/Lima",
    )
    speech_id: int | None = Field(default=None, description="Sin id se usa el Speech original")
    whatsapp: str | None = Field(
        default=None, max_length=20, description="Sin numero se usa el de la configuracion"
    )
    supervisores: list[SupervisorCampanaEntrada] | None = Field(
        default=None, max_length=100, description="Sin lista se usa la configurada por defecto"
    )

    def peticion(self, speech_huella: str | None = None, confirmar_limite: bool = False):
        return PeticionCampana(
            fecha_corte=self.fecha_corte,
            cantidad=self.cantidad,
            programacion=self.programacion,
            filtros=tuple(self.filtros),
            orden=self.orden,
            seleccion_id=self.seleccion_id,
            tipo_carga=self.tipo_carga,
            descripcion=self.descripcion,
            salida=self.salida,
            herramientas=Herramientas(**self.herramientas.model_dump()),
            envios=tuple(self.envios),
            speech_id=self.speech_id,
            speech_huella=speech_huella,
            whatsapp=self.whatsapp,
            supervisores=(
                None
                if self.supervisores is None
                else tuple(Supervisor(s.numero, s.procedencia) for s in self.supervisores)
            ),
            confirmar_limite=confirmar_limite,
        )


class CreacionCampanaEntrada(PeticionCampanaEntrada):
    speech_huella: str = Field(
        min_length=64,
        max_length=64,
        description="La huella del speech que devolvio la previsualizacion; si cambio, 409",
    )
    confirmar_limite: bool = Field(
        default=False, description="Crear aunque la campana supere el limite mensual (S-MM-2)"
    )


# --- Respuestas ----------------------------------------------------------


class HerramientasRespuesta(ModeloRespuesta):
    keyword: bool
    respuesta_automatica: bool
    blacklist_indecopi: bool
    speech_optimizado: bool


class CodigoConteoRespuesta(ModeloRespuesta):
    codigo: CodigoMowaMes
    tipo: TipoCodigo
    cantidad: int


class AvisoCampanaRespuesta(ModeloRespuesta):
    codigo: CodigoMowaMes
    tipo: TipoCodigo
    detalle: str


class SupervisorAsignadoRespuesta(ModeloRespuesta):
    numero: str
    procedencia: str
    documento: str


class FilaMuestraRespuesta(ModeloRespuesta):
    numero: str
    mensaje: str
    dni: str
    supervision: bool
    pagare: str | None
    segmento: Segmento | None
    largo: int
    advertencias: list[CodigoMowaMes]


class ExclusionRespuesta(ModeloRespuesta):
    pagare: str
    codigo: CodigoMowaMes


class PaginaExclusionesRespuesta(ModeloRespuesta):
    total: int
    limite: int
    desplazamiento: int
    exclusiones: list[ExclusionRespuesta]


class SegmentoConteoRespuesta(ModeloRespuesta):
    segmento: Segmento
    etiqueta: str
    cantidad: int


class ArchivoPrevistoRespuesta(ModeloRespuesta):
    numero: int
    filas: int
    supervision: int


class ArchivoRespuesta(ModeloRespuesta):
    numero: int
    filas: int
    supervision: int
    bytes: int


class ConsumoLimiteRespuesta(ModeloRespuesta):
    mes: str = Field(description="YYYY-MM")
    limite: int
    cargados_mes: int
    esta_campana: int
    total: int
    disponible: int
    excedido: bool


class SpeechCampanaRespuesta(ModeloRespuesta):
    id: int
    nombre: str
    huella: str


class PrevisualizacionCampanaRespuesta(ModeloRespuesta):
    descripcion: str
    descripcion_sugerida: str
    fecha_generacion: date
    fecha_envio: date
    speech: SpeechCampanaRespuesta
    whatsapp: str | None
    supervisores: list[SupervisorAsignadoRespuesta]
    disponibles: int
    solicitados: int
    evaluados: int
    productos_cargados: int
    supervision_cargados: int
    total_cargados: int
    excluidos: int
    exclusiones_por_codigo: list[CodigoConteoRespuesta]
    advertencias_por_codigo: list[CodigoConteoRespuesta]
    productos_por_segmento: list[SegmentoConteoRespuesta]
    muestra: list[FilaMuestraRespuesta]
    exclusiones: PaginaExclusionesRespuesta
    archivos_previstos_por_filas: list[ArchivoPrevistoRespuesta] = Field(
        description=(
            "Estimacion solo por filas: al crear pueden salir mas archivos por el tope de bytes"
        )
    )
    limite: ConsumoLimiteRespuesta
    advertencias: list[AvisoCampanaRespuesta]
    errores: list[AvisoCampanaRespuesta]
    puede_crear: bool


class SpeechRegistradoRespuesta(ModeloRespuesta):
    id: int
    nombre: str


class CampanaRespuesta(ModeloRespuesta):
    id: int
    creado_en: datetime
    fecha_corte: date
    filtros: list[str]
    orden: str | None
    cantidad: int
    seleccion_id: int | None
    tipo_carga: TipoCarga
    descripcion: str
    salida: Salida
    herramientas: HerramientasRespuesta
    programacion: Programacion
    envios: list[datetime]
    fecha_envio: date
    mes_imputacion: str = Field(description="YYYY-MM")
    speech: SpeechRegistradoRespuesta
    whatsapp: str | None
    supervisores: list[SupervisorAsignadoRespuesta]
    disponibles: int
    evaluados: int
    productos_cargados: int
    supervision_cargados: int
    total_cargados: int
    excluidos: int
    advertencias: int
    confirmo_limite: bool
    archivos: list[ArchivoRespuesta]


class ListaCampanasRespuesta(ModeloRespuesta):
    total: int
    limite: int
    desplazamiento: int
    campanas: list[CampanaRespuesta]


class EstadoConteoRespuesta(ModeloRespuesta):
    estado: str
    cantidad: int


class CifrasGrupoRespuesta(ModeloRespuesta):
    cargados: int
    enviados: int
    no_enviados: int
    por_estado: list[EstadoConteoRespuesta]


class CifrasIdRespuesta(ModeloRespuesta):
    mes_id: int
    filas: int
    con_correspondencia: int


class AdvertenciaReporteRespuesta(ModeloRespuesta):
    codigo: CodigoMowaMes
    tipo: TipoCodigo
    mes_id: int
    detalle: str


class ReporteImportadoRespuesta(ModeloRespuesta):
    mes_id: int
    nombre_archivo: str
    filas: int
    importado_en: datetime


class ConciliacionRespuesta(ModeloRespuesta):
    campana_id: int
    reportes: list[ReporteImportadoRespuesta]
    productos: CifrasGrupoRespuesta
    supervision: CifrasGrupoRespuesta
    total: CifrasGrupoRespuesta
    sin_correspondencia: int
    sin_correspondencia_por_estado: list[EstadoConteoRespuesta]
    por_id: list[CifrasIdRespuesta]
    advertencias: list[AdvertenciaReporteRespuesta]


# --- Traduccion ----------------------------------------------------------


def _mes(valor: date) -> str:
    return f"{valor:%Y-%m}"


def _conteos(conteo: dict[CodigoMowaMes, int]) -> list[CodigoConteoRespuesta]:
    orden = list(CodigoMowaMes)
    return [
        CodigoConteoRespuesta(codigo=codigo, tipo=TIPO_CODIGO[codigo], cantidad=cantidad)
        for codigo, cantidad in sorted(conteo.items(), key=lambda par: orden.index(par[0]))
    ]


def _consumo(consumo: ConsumoLimite) -> ConsumoLimiteRespuesta:
    return ConsumoLimiteRespuesta(
        mes=_mes(consumo.mes),
        limite=consumo.limite,
        cargados_mes=consumo.cargados_mes,
        esta_campana=consumo.esta_campana,
        total=consumo.total,
        disponible=consumo.disponible,
        excedido=consumo.excedido,
    )


def _supervisores(supervisores) -> list[SupervisorAsignadoRespuesta]:
    return [
        SupervisorAsignadoRespuesta(
            numero=s.numero, procedencia=s.procedencia, documento=s.documento
        )
        for s in supervisores
    ]


def _previsualizacion(armada: CampanaArmada) -> PrevisualizacionCampanaRespuesta:
    advertencias = []
    if armada.consumo.excedido:
        codigo = CodigoMowaMes.LIMITE_MENSUAL_EXCEDIDO
        advertencias.append(
            AvisoCampanaRespuesta(
                codigo=codigo,
                tipo=TIPO_CODIGO[codigo],
                detalle=str(LimiteMensualExcedido(armada.consumo)),
            )
        )
    por_segmento = armada.productos_por_segmento()
    return PrevisualizacionCampanaRespuesta(
        descripcion=armada.descripcion,
        descripcion_sugerida=armada.descripcion_sugerida,
        fecha_generacion=armada.fecha_generacion,
        fecha_envio=armada.fecha_envio,
        speech=SpeechCampanaRespuesta(
            id=armada.speech.id, nombre=armada.speech.datos.nombre, huella=armada.speech_huella
        ),
        whatsapp=armada.whatsapp,
        supervisores=_supervisores(armada.supervisores),
        disponibles=armada.disponibles,
        solicitados=armada.peticion.cantidad,
        evaluados=armada.evaluados,
        productos_cargados=armada.productos_cargados,
        supervision_cargados=armada.supervision_cargados,
        total_cargados=armada.total_cargados,
        excluidos=len(armada.exclusiones),
        exclusiones_por_codigo=_conteos(armada.exclusiones_por_codigo()),
        advertencias_por_codigo=_conteos(armada.advertencias_por_codigo()),
        productos_por_segmento=[
            SegmentoConteoRespuesta(
                segmento=r.segmento, etiqueta=r.etiqueta, cantidad=por_segmento.get(r.segmento, 0)
            )
            for r in RANGOS_SEGMENTO
        ],
        muestra=[
            FilaMuestraRespuesta(
                numero=f.numero,
                mensaje=f.mensaje,
                dni=f.dni,
                supervision=f.supervision,
                pagare=f.pagare,
                segmento=f.segmento,
                largo=len(f.mensaje),
                advertencias=list(f.advertencias),
            )
            for f in armada.filas[:FILAS_DE_MUESTRA]
        ],
        exclusiones=PaginaExclusionesRespuesta(
            total=len(armada.exclusiones),
            limite=EXCLUSIONES_POR_PAGINA,
            desplazamiento=0,
            exclusiones=[
                ExclusionRespuesta(pagare=e.pagare, codigo=e.codigo)
                for e in armada.exclusiones[:EXCLUSIONES_POR_PAGINA]
            ],
        ),
        archivos_previstos_por_filas=[
            ArchivoPrevistoRespuesta(numero=a.numero, filas=a.filas, supervision=a.supervision)
            for a in division.previstos_por_filas(armada.filas, armada.registros_por_archivo)
        ],
        limite=_consumo(armada.consumo),
        advertencias=advertencias,
        errores=[
            AvisoCampanaRespuesta(codigo=e.codigo, tipo=TIPO_CODIGO[e.codigo], detalle=e.detalle)
            for e in armada.errores
        ],
        puede_crear=not armada.errores,
    )


def _campana(campana: CampanaRegistrada) -> CampanaRespuesta:
    return CampanaRespuesta(
        id=campana.id,
        creado_en=campana.creado_en,
        fecha_corte=campana.fecha_corte,
        filtros=list(campana.filtros),
        orden=campana.orden,
        cantidad=campana.cantidad,
        seleccion_id=campana.seleccion_id,
        tipo_carga=campana.tipo_carga,
        descripcion=campana.descripcion,
        salida=campana.salida,
        herramientas=HerramientasRespuesta(**vars(campana.herramientas)),
        programacion=campana.programacion,
        envios=list(campana.envios),
        fecha_envio=campana.fecha_envio,
        mes_imputacion=_mes(campana.mes_imputacion),
        speech=SpeechRegistradoRespuesta(id=campana.speech_id, nombre=campana.speech_nombre),
        whatsapp=campana.whatsapp,
        supervisores=_supervisores(campana.supervisores),
        disponibles=campana.disponibles,
        evaluados=campana.evaluados,
        productos_cargados=campana.productos_cargados,
        supervision_cargados=campana.supervision_cargados,
        total_cargados=campana.total_cargados,
        excluidos=campana.excluidos,
        advertencias=campana.advertencias,
        confirmo_limite=campana.confirmo_limite,
        archivos=[
            ArchivoRespuesta(
                numero=a.numero, filas=a.filas, supervision=a.supervision, bytes=a.bytes
            )
            for a in campana.archivos
        ],
    )


def _estados(conteo: dict[str, int]) -> list[EstadoConteoRespuesta]:
    return [EstadoConteoRespuesta(estado=e, cantidad=n) for e, n in conteo.items()]


def _grupo(cifras: CifrasGrupo) -> CifrasGrupoRespuesta:
    return CifrasGrupoRespuesta(
        cargados=cifras.cargados,
        enviados=cifras.enviados,
        no_enviados=cifras.no_enviados,
        por_estado=_estados(cifras.por_estado),
    )


def _conciliacion(campana_id: int, estado: EstadoConciliacion) -> ConciliacionRespuesta:
    c = estado.conciliacion
    return ConciliacionRespuesta(
        campana_id=campana_id,
        reportes=[
            ReporteImportadoRespuesta(
                mes_id=r.mes_id,
                nombre_archivo=r.nombre_archivo,
                filas=r.filas,
                importado_en=r.importado_en,
            )
            for r in estado.reportes
        ],
        productos=_grupo(c.productos),
        supervision=_grupo(c.supervision),
        total=_grupo(c.total),
        sin_correspondencia=c.sin_correspondencia,
        sin_correspondencia_por_estado=_estados(c.sin_correspondencia_por_estado),
        por_id=[
            CifrasIdRespuesta(
                mes_id=i.mes_id, filas=i.filas, con_correspondencia=i.con_correspondencia
            )
            for i in c.por_id
        ],
        advertencias=[
            AdvertenciaReporteRespuesta(
                codigo=a.codigo, tipo=TIPO_CODIGO[a.codigo], mes_id=a.mes_id, detalle=a.detalle
            )
            for a in c.advertencias
        ],
    )


def _traducir(exc: Exception) -> HTTPException:
    if isinstance(
        exc, (SinVersionVigente, SpeechNoEncontrado, CampanaNoEncontrada, ArchivoNoEncontrado)
    ):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (LimiteMensualExcedido, SpeechCambiado, ReporteYaImportado)):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


_ERRORES_ARMADO = (PeticionCampanaInvalida, SinVersionVigente, SpeechNoEncontrado)


# --- Endpoints -----------------------------------------------------------


@router.post(
    "/campanas/previsualizacion",
    response_model=PrevisualizacionCampanaRespuesta,
    responses=respuestas_de_error(400, 404),
)
def previsualizar_campana(
    entrada: PeticionCampanaEntrada,
    servicio: CampanasMowaMesService = Depends(obtener_servicio_campanas),
) -> PrevisualizacionCampanaRespuesta:
    """La campana calculada sin guardar nada. Los errores de campana no son 4xx: se listan.

    `speech.huella` es lo que la creacion tiene que enviar como `speech_huella`.
    """
    try:
        return _previsualizacion(servicio.previsualizar(entrada.peticion()))
    except _ERRORES_ARMADO as exc:
        raise _traducir(exc) from exc


@router.post(
    "/campanas",
    status_code=201,
    response_model=CampanaRespuesta,
    responses=respuestas_de_error(400, 404, 409),
)
def crear_campana(
    entrada: CreacionCampanaEntrada,
    servicio: CampanasMowaMesService = Depends(obtener_servicio_campanas),
) -> CampanaRespuesta:
    """Genera los archivos y guarda la campana. 400 si tiene errores (los de la
    previsualizacion), 409 si supera el limite sin `confirmar_limite` o si el speech
    cambio desde la previsualizacion."""
    try:
        return _campana(
            servicio.crear(entrada.peticion(entrada.speech_huella, entrada.confirmar_limite))
        )
    except (
        *_ERRORES_ARMADO,
        CampanaInvalida,
        LimiteMensualExcedido,
        SpeechCambiado,
        ArchivoDemasiadoGrande,
    ) as exc:
        raise _traducir(exc) from exc


@router.get("/campanas", response_model=ListaCampanasRespuesta)
def listar_campanas(
    limite: int = Query(default=50, ge=1, le=500),
    desplazamiento: int = Query(default=0, ge=0),
    servicio: CampanasMowaMesService = Depends(obtener_servicio_campanas),
) -> ListaCampanasRespuesta:
    total, campanas = servicio.listar(limite, desplazamiento)
    return ListaCampanasRespuesta(
        total=total,
        limite=limite,
        desplazamiento=desplazamiento,
        campanas=[_campana(c) for c in campanas],
    )


@router.get(
    "/campanas/{campana_id}", response_model=CampanaRespuesta, responses=respuestas_de_error(404)
)
def obtener_campana(
    campana_id: int, servicio: CampanasMowaMesService = Depends(obtener_servicio_campanas)
) -> CampanaRespuesta:
    try:
        return _campana(servicio.obtener(campana_id))
    except CampanaNoEncontrada as exc:
        raise _traducir(exc) from exc


@router.get(
    "/campanas/{campana_id}/exclusiones",
    response_model=PaginaExclusionesRespuesta,
    responses=respuestas_de_error(404),
)
def listar_exclusiones(
    campana_id: int,
    codigo: CodigoMowaMes | None = None,
    limite: int = Query(default=EXCLUSIONES_POR_PAGINA, ge=1, le=1000),
    desplazamiento: int = Query(default=0, ge=0),
    servicio: CampanasMowaMesService = Depends(obtener_servicio_campanas),
) -> PaginaExclusionesRespuesta:
    try:
        total, exclusiones = servicio.exclusiones(campana_id, codigo, limite, desplazamiento)
    except CampanaNoEncontrada as exc:
        raise _traducir(exc) from exc
    return PaginaExclusionesRespuesta(
        total=total,
        limite=limite,
        desplazamiento=desplazamiento,
        exclusiones=[ExclusionRespuesta(pagare=e.pagare, codigo=e.codigo) for e in exclusiones],
    )


def _respuesta_de_descarga() -> dict:
    numero = {"type": "string", "pattern": "^[0-9]+$"}
    return {
        200: {
            "description": "Archivo de carga de MOWA MES",
            "content": {TIPO_MIME_XLSX: {"schema": {"type": "string", "format": "binary"}}},
            "headers": {
                "Content-Disposition": {
                    "description": 'attachment; filename="<nombre>.xlsx"',
                    "schema": {"type": "string"},
                },
                **{
                    nombre: {"description": descripcion, "schema": numero}
                    for nombre, descripcion in CABECERAS_ARCHIVO.items()
                },
            },
        },
        **respuestas_de_error(404),
    }


def nombre_archivo(campana_id: int, numero: int, total: int) -> str:
    return f"mowa_mes_campana_{campana_id}_{numero}_de_{total}.xlsx"


@router.get(
    "/campanas/{campana_id}/archivos/{numero}",
    response_class=Response,
    responses=_respuesta_de_descarga(),
)
def descargar_archivo(
    campana_id: int,
    numero: int,
    servicio: CampanasMowaMesService = Depends(obtener_servicio_campanas),
) -> Response:
    """Los bytes guardados al crear la campana: la misma descarga siempre (C-6)."""
    try:
        campana, archivo = servicio.archivo(campana_id, numero)
    except (CampanaNoEncontrada, ArchivoNoEncontrado) as exc:
        raise _traducir(exc) from exc
    total = len(campana.archivos)
    return Response(
        content=archivo.contenido,
        media_type=TIPO_MIME_XLSX,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{nombre_archivo(campana_id, numero, total)}"'
            ),
            "X-Mowa-Mes-Campana": str(campana_id),
            "X-Mowa-Mes-Archivo": str(archivo.numero),
            "X-Mowa-Mes-Archivos-Total": str(total),
            "X-Mowa-Mes-Filas": str(archivo.filas),
            "X-Mowa-Mes-Supervision": str(archivo.supervision),
            "X-Mowa-Mes-Bytes": str(archivo.bytes),
        },
    )


@router.get("/limite-mensual", response_model=ConsumoLimiteRespuesta)
def limite_mensual(
    mes: str | None = Query(
        default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="YYYY-MM; sin mes, el actual"
    ),
    servicio: CampanasMowaMesService = Depends(obtener_servicio_campanas),
) -> ConsumoLimiteRespuesta:
    """Cargados del mes (productos y supervision) respecto del limite (RF-MM-01, S-MM-7)."""
    primero = None if mes is None else date(int(mes[:4]), int(mes[5:]), 1)
    return _consumo(servicio.limite_mensual(primero))


@router.post(
    "/campanas/{campana_id}/reportes",
    status_code=201,
    response_model=ConciliacionRespuesta,
    responses=respuestas_de_error(400, 404, 409, 413),
)
async def importar_reporte(
    campana_id: int,
    archivo: UploadFile = File(description="Reporte 'Campanas de enviados' de MES (.xlsx)"),
    reemplazar: bool = Form(
        default=False, description="Reemplazar los id de MES que ya estaban importados"
    ),
    servicio: ReportesMowaMesService = Depends(obtener_servicio_reportes),
) -> ConciliacionRespuesta:
    """Asocia cada `id` de MES del archivo a la campana y devuelve la conciliacion."""
    contenido = await archivo.read()
    if len(contenido) > TAMANO_MAXIMO_REPORTE:
        raise HTTPException(
            status_code=413,
            detail=f"El archivo supera el maximo de {TAMANO_MAXIMO_REPORTE // 1024 // 1024} MB",
        )
    try:
        estado = servicio.importar(
            campana_id, archivo.filename or "reporte.xlsx", contenido, reemplazar
        )
    except (CampanaNoEncontrada, ReporteInvalido, ReporteYaImportado) as exc:
        raise _traducir(exc) from exc
    return _conciliacion(campana_id, estado)


@router.get(
    "/campanas/{campana_id}/conciliacion",
    response_model=ConciliacionRespuesta,
    responses=respuestas_de_error(404),
)
def conciliacion(
    campana_id: int, servicio: ReportesMowaMesService = Depends(obtener_servicio_reportes)
) -> ConciliacionRespuesta:
    try:
        return _conciliacion(campana_id, servicio.conciliacion(campana_id))
    except CampanaNoEncontrada as exc:
        raise _traducir(exc) from exc

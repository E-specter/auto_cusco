"""Campanas de WhatsMKT por HTTP (docs/requerimientos-whatsmkt.md; T-WM-B4a).

Primer corte, la previsualizacion (RF-WM-35):

    POST /whatsmkt/campanas/previsualizacion   los archivos que resultarian, sin guardar nada

Devuelve una campana por archivo (una, o una por segmento con productos), con su cantidad, las
primeras 20 filas, las primeras 100 exclusiones y el total exacto de ellas: la pantalla pagina esas
listas sin volver a calcular (como RF-MM-26). Lo que impide crear (`definicion_no_whatsmkt`,
`sin_supervisores`, `sin_productos`) viaja en `problemas` con un 200, no como error 4xx.

Todavia sin el mensaje ni la validacion de la fecha de envio (B4b), ni las tablas de campana.
"""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.adapters.persistence.db import get_engine
from app.adapters.persistence.repositorio_whatsmkt_postgres import RepositorioWhatsmktPostgres
from app.api.archivos_carga import RESPUESTAS_ERROR, obtener_servicio_generacion
from app.api.cartera import obtener_catalogo_cartera
from app.api.consultas import parsear_filtro, parsear_orden
from app.api.definiciones_columnas import obtener_servicio_definiciones
from app.api.errores import ErrorConCodigo
from app.api.fecha_envio import error_de_fecha_envio
from app.api.respuestas import ModeloRespuesta
from app.api.supervisores import obtener_servicio_supervision
from app.core.entities.cartera import ConsultaInvalida, SinVersionVigente
from app.core.entities.definiciones_columnas import DefinicionNoEncontrada, VersionNoEncontrada
from app.core.entities.mapeo import PlantillaInvalida
from app.core.entities.texto_enriquecido import CodigoTexto
from app.core.entities.whatsmkt import CodigoWhatsmkt, ModoCampana
from app.core.services.definiciones_columnas.servicio import DefinicionesColumnasService
from app.core.services.fecha_envio import FechaEnvioAnterior
from app.core.services.generacion_cargas.servicio import (
    CANTIDAD_MAXIMA,
    GeneracionCargasService,
)
from app.core.services.gestiones_digitales.servicio import SupervisionService
from app.core.services.plataformas.whatsmkt.archivo_contactos import (
    ArchivoContactosService,
    ExclusionContacto,
    SeleccionCampana,
)
from app.core.services.plataformas.whatsmkt.previa import (
    CampanaPrevista,
    PeticionPrevia,
    PreviaCampanas,
    PrevisualizacionWhatsmktService,
)
from app.core.services.seleccion_cartera.campos import CatalogoCartera

router = APIRouter(prefix="/whatsmkt/campanas", tags=["whatsmkt"])

FILAS_DE_MUESTRA = 20
EXCLUSIONES_EN_PREVIA = 100


def obtener_servicio_previa_whatsmkt(
    generacion: GeneracionCargasService = Depends(obtener_servicio_generacion),
    definiciones: DefinicionesColumnasService = Depends(obtener_servicio_definiciones),
    supervision: SupervisionService = Depends(obtener_servicio_supervision),
) -> PrevisualizacionWhatsmktService:
    """Dependencia de FastAPI; los tests la sustituyen por un doble de prueba."""
    return PrevisualizacionWhatsmktService(
        ArchivoContactosService(generacion),
        RepositorioWhatsmktPostgres(get_engine()),
        definiciones,
        supervision,
    )


class DefinicionWhatsmktEntrada(BaseModel):
    """Una definicion de `/definiciones-columnas`: la version pedida o, sin ella, la vigente."""

    id: int
    version: int | None = Field(default=None, ge=1)


class PrevisualizacionCampanasWhatsmktEntrada(BaseModel):
    fecha_corte: date
    filtros: list[str] = []
    orden: str | None = None
    cantidad: int = Field(ge=1, le=CANTIDAD_MAXIMA)
    seleccion_id: int | None = Field(
        default=None, description="Referencia informativa a la seleccion guardada de origen"
    )
    definicion: DefinicionWhatsmktEntrada
    modo: ModoCampana = ModoCampana.GLOBAL
    fecha_envio: date | None = Field(
        default=None,
        description=(
            "Fecha de envio, solo para los dias de atraso ajustados (RF-55); sin ella, hoy en "
            "America/Lima. Todavia SIN validar contra los dias de envio (RF-70): eso llega con "
            "el mensaje"
        ),
    )

    def seleccion(self, catalogo: CatalogoCartera) -> SeleccionCampana:
        return SeleccionCampana(
            fecha_corte=self.fecha_corte,
            # shortcut: fecha_envio llega sin validar; B4b la valida con RF-70 cuando entre T-HI-B5
            fecha_envio=self.fecha_envio,
            filtros=[parsear_filtro(crudo, catalogo) for crudo in self.filtros],
            orden=parsear_orden(self.orden),
            cantidad=self.cantidad,
        )


class CabeceraWhatsmktRespuesta(ModeloRespuesta):
    nombre: str = Field(description="El encabezado del archivo")
    etiqueta: str | None = Field(description="La etiqueta de la columna; no sale en el archivo")


class FilaMuestraWhatsmktRespuesta(ModeloRespuesta):
    supervision: bool = Field(description="Una fila de supervision (van antes de los productos)")
    celdas: list[str | None] = Field(description="Un valor por cabecera, en el mismo orden")


class ExclusionWhatsmktRespuesta(ModeloRespuesta):
    codigo: CodigoWhatsmkt
    fila: int = Field(description="Posicion del producto entre los que genero la seleccion")
    pagare: str | None
    detalle: str
    macro: int | None = Field(description="macro_vacia: el numero de la macro (1 es la segunda)")
    etiqueta: str | None = Field(description="macro_vacia: la etiqueta de la columna")


class CampanaPrevistaWhatsmktRespuesta(ModeloRespuesta):
    segmento: str | None = Field(description="La clave del segmento; null en una campana global")
    etiqueta_segmento: str | None
    cantidad: int = Field(description="Filas del archivo, supervisores incluidos (S-WM-4)")
    productos: int
    supervisores: int
    cabeceras: list[CabeceraWhatsmktRespuesta]
    total_exclusiones: int
    exclusiones: list[ExclusionWhatsmktRespuesta] = Field(
        description=f"Las primeras {EXCLUSIONES_EN_PREVIA}; el total esta en `total_exclusiones`"
    )
    muestra: list[FilaMuestraWhatsmktRespuesta] = Field(
        description=f"Las primeras {FILAS_DE_MUESTRA} filas del archivo"
    )


class ProblemaWhatsmktRespuesta(ModeloRespuesta):
    codigo: CodigoWhatsmkt
    detalle: str


class PrevisualizacionCampanasWhatsmktRespuesta(ModeloRespuesta):
    campanas: list[CampanaPrevistaWhatsmktRespuesta]
    problemas: list[ProblemaWhatsmktRespuesta] = Field(
        description="Lo que impide crear; con alguno, la pantalla deja «Crear» inactivo"
    )
    disponibles: int = Field(description="Productos de la seleccion completa (RF-08)")
    solicitados: int
    total_exclusiones: int = Field(description="Todas, incluidas las que no son de una campana")
    total_exclusiones_sin_campana: int
    exclusiones_sin_campana: list[ExclusionWhatsmktRespuesta] = Field(
        description=(
            "Exclusiones que no son de ninguna campana: un producto sin dias de atraso, o de un "
            f"segmento que se quedo sin productos. Las primeras {EXCLUSIONES_EN_PREVIA}"
        )
    )


def _texto(valor: Any) -> str | None:
    return None if valor is None else str(valor)


def _exclusion(e: ExclusionContacto) -> ExclusionWhatsmktRespuesta:
    return ExclusionWhatsmktRespuesta(
        codigo=e.codigo,
        fila=e.fila,
        pagare=e.pagare,
        detalle=e.detalle,
        macro=e.macro,
        etiqueta=e.etiqueta,
    )


def _campana(c: CampanaPrevista) -> CampanaPrevistaWhatsmktRespuesta:
    archivo = c.archivo
    cabeceras = archivo.tabla.cabeceras
    return CampanaPrevistaWhatsmktRespuesta(
        segmento=None if c.segmento is None else c.segmento.clave,
        etiqueta_segmento=None if c.segmento is None else c.segmento.etiqueta,
        cantidad=archivo.cantidad,
        productos=archivo.productos,
        supervisores=archivo.supervisores,
        cabeceras=[
            CabeceraWhatsmktRespuesta(nombre=h.nombre, etiqueta=h.etiqueta) for h in c.cabeceras
        ],
        total_exclusiones=len(c.exclusiones),
        exclusiones=[_exclusion(e) for e in c.exclusiones[:EXCLUSIONES_EN_PREVIA]],
        muestra=[
            FilaMuestraWhatsmktRespuesta(
                supervision=indice < archivo.supervisores,
                celdas=[_texto(fila[h]) for h in cabeceras],
            )
            for indice, fila in enumerate(archivo.tabla.filas[:FILAS_DE_MUESTRA])
        ],
    )


def _respuesta(previa: PreviaCampanas) -> PrevisualizacionCampanasWhatsmktRespuesta:
    return PrevisualizacionCampanasWhatsmktRespuesta(
        campanas=[_campana(c) for c in previa.campanas],
        problemas=[
            ProblemaWhatsmktRespuesta(codigo=p.codigo, detalle=p.detalle) for p in previa.problemas
        ],
        disponibles=previa.disponibles,
        solicitados=previa.solicitados,
        total_exclusiones=previa.total_exclusiones,
        total_exclusiones_sin_campana=len(previa.exclusiones_sin_campana),
        exclusiones_sin_campana=[
            _exclusion(e) for e in previa.exclusiones_sin_campana[:EXCLUSIONES_EN_PREVIA]
        ],
    )


def _error(exc: Exception) -> ErrorConCodigo:
    if isinstance(exc, DefinicionNoEncontrada):
        return ErrorConCodigo(404, str(exc), CodigoTexto.DEFINICION_NO_ENCONTRADA)
    if isinstance(exc, VersionNoEncontrada):
        return ErrorConCodigo(404, str(exc), CodigoTexto.VERSION_NO_ENCONTRADA)
    if isinstance(exc, SinVersionVigente):
        return ErrorConCodigo(404, str(exc), CodigoTexto.SIN_VERSION_VIGENTE)
    if isinstance(exc, FechaEnvioAnterior):
        return error_de_fecha_envio(exc)
    return ErrorConCodigo(400, str(exc), None)


@router.post(
    "/previsualizacion",
    summary="Previsualizar los archivos de la campana",
    response_model=PrevisualizacionCampanasWhatsmktRespuesta,
    responses=RESPUESTAS_ERROR,
)
def previsualizar_campanas(
    entrada: PrevisualizacionCampanasWhatsmktEntrada,
    servicio: PrevisualizacionWhatsmktService = Depends(obtener_servicio_previa_whatsmkt),
    catalogo: CatalogoCartera = Depends(obtener_catalogo_cartera),
) -> PrevisualizacionCampanasWhatsmktRespuesta:
    """Los archivos que resultarian de la seleccion, sin guardar nada (RF-WM-35).

    En modo `por_segmento` sale una campana por cada segmento con productos (RF-WM-23); en
    `global`, una. Los problemas (`definicion_no_whatsmkt`, `sin_supervisores`, `sin_productos`)
    se listan con un 200: no impiden previsualizar, impiden crear.
    """
    try:
        previa = servicio.previsualizar(
            PeticionPrevia(
                seleccion=entrada.seleccion(catalogo),
                definicion_id=entrada.definicion.id,
                version=entrada.definicion.version,
                modo=entrada.modo,
            )
        )
    except (
        ConsultaInvalida,
        PlantillaInvalida,
        SinVersionVigente,
        DefinicionNoEncontrada,
        VersionNoEncontrada,
        FechaEnvioAnterior,
    ) as exc:
        raise _error(exc) from exc
    return _respuesta(previa)

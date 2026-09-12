"""Adaptador de entrada HTTP para generar archivos de carga (RF-09, RF-13, RF-15).

Tres operaciones:

    GET  /archivos-carga/formatos          formatos disponibles y sus opciones
    POST /archivos-carga/previsualizacion  una muestra en JSON, para revisar
    POST /archivos-carga                   el archivo listo para descargar

La seleccion de productos se expresa igual que en `/cartera` (filtros
`campo:operador:valor` y orden `campo` / `-campo`), asi lo que el usuario armo
en la pantalla de cartera se reutiliza tal cual.

La definicion de la carga viaja en el cuerpo: todavia no se guarda en la base,
asi que el frontend la envia completa en cada llamada (ver docs/mapeo-campos.md).
"""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from app.adapters.output import exportadores
from app.api.cartera import obtener_servicio_cartera
from app.api.consultas import parsear_filtro, parsear_orden, texto_si_es_monto, traducir_errores
from app.core.entities.cartera import ConsultaInvalida, SinVersionVigente
from app.core.entities.exportacion import (
    EXTENSIONES,
    ExportacionInvalida,
    FormatoArchivo,
    OpcionesArchivo,
)
from app.core.entities.mapeo import (
    CampoSalida,
    DefinicionCarga,
    FormatoFinanciero,
    PlantillaInvalida,
    TipoSalida,
)
from app.core.services.generacion_cargas.servicio import (
    CANTIDAD_MAXIMA,
    CANTIDAD_POR_DEFECTO,
    GeneracionCargasService,
    ResultadoGeneracion,
)
from app.core.services.seleccion_cartera.servicio import ConsultaCarteraService

router = APIRouter(prefix="/archivos-carga", tags=["archivos de carga"])

FILAS_DE_MUESTRA = 20


def obtener_servicio_generacion(
    consulta: ConsultaCarteraService = Depends(obtener_servicio_cartera),
) -> GeneracionCargasService:
    """Dependencia de FastAPI; los tests la sustituyen por un doble de prueba."""
    return GeneracionCargasService(consulta)


class FormatoFinancieroEntrada(BaseModel):
    separador_miles: str = Field(default=",", max_length=1)
    separador_decimal: str = Field(default=".", max_length=1)
    decimales: int = Field(default=2, ge=0, le=6)


class CampoEntrada(BaseModel):
    nombre: str
    plantilla: str
    tipo: TipoSalida = TipoSalida.TEXTO
    formato_fecha: str | None = None
    formato_financiero: FormatoFinancieroEntrada | None = None


class DefinicionEntrada(BaseModel):
    nombre: str
    campos: list[CampoEntrada] = Field(min_length=1)


class OpcionesEntrada(BaseModel):
    delimitador: str = Field(default=",", min_length=1, max_length=1)
    codificacion: str = "utf-8"
    con_cabeceras: bool = True
    hoja: str = "Carga"
    sangria: int | None = Field(default=None, ge=0, le=8)


class PeticionGeneracion(BaseModel):
    fecha_corte: date
    definicion: DefinicionEntrada
    formato: FormatoArchivo = FormatoArchivo.XLSX
    filtros: list[str] = []
    orden: str | None = None
    cantidad: int = Field(default=CANTIDAD_POR_DEFECTO, ge=1, le=CANTIDAD_MAXIMA)
    opciones: OpcionesEntrada | None = None


class ErrorRespuesta(BaseModel):
    fila: int
    campo: str
    detalle: str


class PrevisualizacionRespuesta(BaseModel):
    nombre_archivo: str
    cabeceras: list[str]
    filas: list[dict[str, Any]]
    disponibles: int
    solicitados: int
    generados: int
    suficiente: bool
    completa: bool
    errores: list[ErrorRespuesta]


class FormatoRespuesta(BaseModel):
    formato: str
    extension: str
    opciones: list[str]


# Que opcion de OpcionesArchivo usa cada formato, para que la interfaz muestre
# solo las que corresponden.
OPCIONES_POR_FORMATO: dict[FormatoArchivo, tuple[str, ...]] = {
    FormatoArchivo.XLSX: ("con_cabeceras", "hoja"),
    FormatoArchivo.CSV: ("delimitador", "codificacion", "con_cabeceras"),
    FormatoArchivo.JSON: ("codificacion", "sangria"),
}


def _definicion(entrada: DefinicionEntrada) -> DefinicionCarga:
    return DefinicionCarga(
        nombre=entrada.nombre,
        campos=tuple(
            CampoSalida(
                nombre=campo.nombre,
                plantilla=campo.plantilla,
                tipo=campo.tipo,
                formato_fecha=campo.formato_fecha,
                formato_financiero=(
                    FormatoFinanciero()
                    if campo.formato_financiero is None
                    else FormatoFinanciero(**campo.formato_financiero.model_dump())
                ),
            )
            for campo in entrada.campos
        ),
    )


def _opciones(entrada: OpcionesEntrada | None) -> OpcionesArchivo:
    return OpcionesArchivo() if entrada is None else OpcionesArchivo(**entrada.model_dump())


def _generar(
    servicio: GeneracionCargasService, peticion: PeticionGeneracion, cantidad: int
) -> ResultadoGeneracion:
    try:
        return servicio.generar(
            peticion.fecha_corte,
            _definicion(peticion.definicion),
            [parsear_filtro(crudo) for crudo in peticion.filtros],
            parsear_orden(peticion.orden),
            cantidad,
        )
    except (ConsultaInvalida, PlantillaInvalida, SinVersionVigente) as exc:
        raise traducir_errores(exc) from exc


def _valor_json(valor: Any) -> Any:
    return texto_si_es_monto(valor) if not isinstance(valor, date) else valor.isoformat()


@router.get("/formatos", response_model=list[FormatoRespuesta])
def listar_formatos() -> list[FormatoRespuesta]:
    """Formatos que se pueden generar y que opciones admite cada uno (RF-13)."""
    return [
        FormatoRespuesta(
            formato=formato.value,
            extension=EXTENSIONES[formato],
            opciones=list(OPCIONES_POR_FORMATO[formato]),
        )
        for formato in exportadores.EXPORTADORES
    ]


@router.post("/previsualizacion", response_model=PrevisualizacionRespuesta)
def previsualizar(
    peticion: PeticionGeneracion,
    servicio: GeneracionCargasService = Depends(obtener_servicio_generacion),
) -> PrevisualizacionRespuesta:
    """Primeras filas y errores de la carga, sin escribir el archivo.

    `disponibles` es el total de la seleccion completa, no el de la muestra: es
    lo que dice si alcanzan los productos para la cantidad pedida (RF-08).
    """
    muestra = min(peticion.cantidad, FILAS_DE_MUESTRA)
    resultado = _generar(servicio, peticion, muestra)
    tabla = resultado.tabla
    return PrevisualizacionRespuesta(
        nombre_archivo=exportadores.nombre_de_archivo(tabla.nombre, peticion.formato),
        cabeceras=list(tabla.cabeceras),
        filas=[
            {clave: _valor_json(valor) for clave, valor in fila.items()} for fila in tabla.filas
        ],
        disponibles=resultado.disponibles,
        solicitados=peticion.cantidad,
        generados=resultado.generados,
        suficiente=resultado.disponibles >= peticion.cantidad,
        completa=resultado.completa,
        errores=[
            ErrorRespuesta(fila=error.fila, campo=error.campo, detalle=error.detalle)
            for error in resultado.errores
        ],
    )


@router.post("")
def generar_archivo(
    peticion: PeticionGeneracion,
    servicio: GeneracionCargasService = Depends(obtener_servicio_generacion),
) -> Response:
    """Genera la carga completa y devuelve el archivo (RF-09, RF-13, RF-15).

    El resumen viaja en cabeceras `X-Carga-*` porque el cuerpo es el archivo;
    el detalle de los errores se consulta en `/previsualizacion`.
    """
    resultado = _generar(servicio, peticion, peticion.cantidad)
    try:
        archivo = exportadores.exportar(
            resultado.tabla, peticion.formato, _opciones(peticion.opciones)
        )
    except ExportacionInvalida as exc:
        raise traducir_errores(exc) from exc
    return Response(
        content=archivo.contenido,
        media_type=archivo.tipo_mime,
        headers={
            "Content-Disposition": f'attachment; filename="{archivo.nombre}"',
            "X-Carga-Generados": str(resultado.generados),
            "X-Carga-Disponibles": str(resultado.disponibles),
            "X-Carga-Solicitados": str(resultado.solicitados),
            "X-Carga-Suficiente": "1" if resultado.suficiente else "0",
            "X-Carga-Errores": str(len(resultado.errores)),
        },
    )

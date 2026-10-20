"""Adaptador de entrada HTTP de las definiciones de columnas guardadas (RF-51, RF-46, B4b).

    GET  /definiciones-columnas                        el listado (C-7)
    POST /definiciones-columnas                        guarda una definicion nueva (version 1)
    GET  /definiciones-columnas/{id}?version=N         una definicion con su version vigente o la N
    POST /definiciones-columnas/{id}/versiones         guarda un cambio como una version nueva
    PATCH /definiciones-columnas/{id}                  cambia solo el nombre (RF-56)

Ninguna version se modifica: un cambio es una version nueva y la vigente es la ultima. El nombre es
unico sin distinguir mayusculas y no cambia con las versiones; solo `PATCH` lo cambia. El pedido
es la misma definicion del constructor que acepta `/texto-enriquecido/previsualizacion`
(`DefinicionColumnasEntrada`): una sola forma para armar, previsualizar y guardar.

Al guardar se valida con el mismo motor (RF-46): si algo no vale, un `400` que extiende
`DetalleError` con `codigo` y los `problemas`, cada uno con su ubicacion (columna, variante, campo,
nodo, funcion y parametro; C-2). Lo que se devuelve es siempre expresion, con tipos cerrados.
"""

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.adapters.persistence.db import get_engine
from app.adapters.persistence.repositorio_definiciones_postgres import (
    RepositorioDefinicionesPostgres,
)
from app.api.respuestas import ModeloRespuesta
from app.api.texto_enriquecido import (
    DefinicionColumnasEntrada,
    DetalleErrorTexto,
    ProblemaTextoRespuesta,
    RangoRespuesta,
    obtener_registro_contextos,
    problema_respuesta,
    respuesta_de_error,
)
from app.core.entities.definiciones_columnas import (
    DefinicionGuardada,
    DefinicionNoEncontrada,
    NombreDeDefinicionRepetido,
    ResumenDefinicion,
    VersionDefinicion,
    VersionNoEncontrada,
)
from app.core.entities.texto_enriquecido import CodigoTexto
from app.core.services.contextos_texto import RegistroContextos
from app.core.services.definiciones_columnas.servicio import (
    DefinicionesColumnasService,
    DefinicionInvalida,
    VistaDefinicion,
)

router = APIRouter(prefix="/definiciones-columnas", tags=["definiciones de columnas"])


def obtener_servicio_definiciones(
    contextos: RegistroContextos = Depends(obtener_registro_contextos),
) -> DefinicionesColumnasService:
    """Dependencia de FastAPI; los tests la sustituyen por un doble de prueba.

    Las definiciones guardadas se validan contra el contexto `cartera`: alimentan `/archivos-carga`.
    """
    return DefinicionesColumnasService(
        RepositorioDefinicionesPostgres(get_engine()), contextos.obtener("cartera")
    )


# --- Errores ------------------------------------------------------------------------------------


class DetalleErrorDefinicion(DetalleErrorTexto):
    """Un `400` al guardar: el motivo, el `codigo` y todos los problemas con su ubicacion."""

    problemas: list[ProblemaTextoRespuesta]


RESPUESTAS_ESCRITURA: dict[int | str, dict[str, Any]] = {
    400: {
        "model": DetalleErrorDefinicion,
        "description": "La definicion no se puede guardar: los problemas dicen donde esta cada uno",
    },
    404: {"model": DetalleErrorTexto, "description": "No existe la definicion"},
    409: {"model": DetalleErrorTexto, "description": "Ya hay una definicion con ese nombre"},
}
RESPUESTAS_LECTURA: dict[int | str, dict[str, Any]] = {
    404: {"model": DetalleErrorTexto, "description": "No existe la definicion o su version"},
}


def _invalida(error: DefinicionInvalida) -> JSONResponse:
    problemas = [problema_respuesta(p.problema, p).model_dump() for p in error.problemas]
    return respuesta_de_error(400, CodigoTexto.DEFINICION_INVALIDA, str(error), problemas=problemas)


def _no_existe(error: DefinicionNoEncontrada | VersionNoEncontrada) -> JSONResponse:
    codigo = (
        CodigoTexto.DEFINICION_NO_ENCONTRADA
        if isinstance(error, DefinicionNoEncontrada)
        else CodigoTexto.VERSION_NO_ENCONTRADA
    )
    return respuesta_de_error(404, codigo, str(error))


# --- Respuesta: la definicion guardada, siempre con expresiones ----------------------------------


class NodoTextoGuardadoRespuesta(ModeloRespuesta):
    tipo: Literal["texto"]
    valor: str


class ArgumentoVariableGuardadoRespuesta(ModeloRespuesta):
    variable: str


class LlamadaGuardadaRespuesta(ModeloRespuesta):
    nombre: str
    args: list[str | int | float | ArgumentoVariableGuardadoRespuesta]


class NodoVariableGuardadoRespuesta(ModeloRespuesta):
    tipo: Literal["variable"]
    nombre: str
    funciones: list[LlamadaGuardadaRespuesta]
    obligatoria: bool


NodoGuardadoRespuesta = Annotated[
    NodoTextoGuardadoRespuesta | NodoVariableGuardadoRespuesta, Field(discriminator="tipo")
]


class ExpresionGuardadaRespuesta(ModeloRespuesta):
    nodos: list[NodoGuardadoRespuesta]


class FormatoFinancieroGuardadoRespuesta(ModeloRespuesta):
    separador_miles: str
    separador_decimal: str
    decimales: int


class VarianteGuardadaRespuesta(ModeloRespuesta):
    segmento: str
    expresion: ExpresionGuardadaRespuesta


class ColumnaGuardadaRespuesta(ModeloRespuesta):
    nombre: str
    orden: int
    expresion: ExpresionGuardadaRespuesta
    tipo: Literal["texto", "numero", "fecha", "financiero"]
    formato_fecha: str | None  # con marcas legibles (`dd/mm/aaaa`)
    formato_financiero: FormatoFinancieroGuardadoRespuesta
    valor_por_defecto: str | None
    variantes: list[VarianteGuardadaRespuesta]


class CriterioCalculadoGuardadoRespuesta(ModeloRespuesta):
    tipo: Literal["calculado"]
    variable_dias: str
    tabla: list[RangoRespuesta]


class CriterioCampoGuardadoRespuesta(ModeloRespuesta):
    tipo: Literal["campo"]
    campo: str


class SegmentacionGuardadaRespuesta(ModeloRespuesta):
    criterio: Annotated[
        CriterioCalculadoGuardadoRespuesta | CriterioCampoGuardadoRespuesta,
        Field(discriminator="tipo"),
    ]
    politica: Literal["excluir", "usar_por_defecto"]


class ContenidoGuardadoRespuesta(ModeloRespuesta):
    """La definicion de una version, con la tabla de rangos resuelta y las columnas por `orden`."""

    proteger_formulas: bool
    columnas: list[ColumnaGuardadaRespuesta]
    segmentacion: SegmentacionGuardadaRespuesta | None


class VersionDefinicionResumenRespuesta(ModeloRespuesta):
    numero: int
    creado_en: datetime
    usada_en: datetime | None
    usada: bool


class VersionDefinicionRespuesta(VersionDefinicionResumenRespuesta):
    contenido: ContenidoGuardadoRespuesta


class DefinicionRespuesta(ModeloRespuesta):
    """La definicion, todas sus versiones (sin contenido) y la pedida (la vigente por defecto)."""

    id: int
    nombre: str
    creado_en: datetime
    actualizado_en: datetime
    version_vigente: int
    versiones: list[VersionDefinicionResumenRespuesta]
    version: VersionDefinicionRespuesta


class ResumenDefinicionRespuesta(ModeloRespuesta):
    id: int
    nombre: str
    version_vigente: int
    cantidad_versiones: int
    actualizado_en: datetime
    vigente_usada: bool


def _resumen_de_version(version: VersionDefinicion) -> VersionDefinicionResumenRespuesta:
    return VersionDefinicionResumenRespuesta(
        numero=version.numero,
        creado_en=version.creado_en,
        usada_en=version.usada_en,
        usada=version.usada,
    )


def _version(version: VersionDefinicion) -> VersionDefinicionRespuesta:
    return VersionDefinicionRespuesta(
        **_resumen_de_version(version).model_dump(),
        contenido=ContenidoGuardadoRespuesta.model_validate(version.contenido),
    )


def _definicion(definicion: DefinicionGuardada, version: VersionDefinicion) -> DefinicionRespuesta:
    return DefinicionRespuesta(
        id=definicion.id,
        nombre=definicion.nombre,
        creado_en=definicion.creado_en,
        actualizado_en=definicion.actualizado_en,
        version_vigente=definicion.vigente.numero,
        versiones=[_resumen_de_version(v) for v in definicion.versiones],
        version=_version(version),
    )


def _vista(vista: VistaDefinicion) -> DefinicionRespuesta:
    return _definicion(vista.definicion, vista.version)


def _resumen(resumen: ResumenDefinicion) -> ResumenDefinicionRespuesta:
    return ResumenDefinicionRespuesta(
        id=resumen.id,
        nombre=resumen.nombre,
        version_vigente=resumen.version_vigente,
        cantidad_versiones=resumen.cantidad_versiones,
        actualizado_en=resumen.actualizado_en,
        vigente_usada=resumen.vigente_usada,
    )


class RenombrarDefinicionEntrada(BaseModel):
    """RF-56: el nombre nuevo. Se recortan los espacios de los extremos."""

    nombre: str


def _repetido(error: NombreDeDefinicionRepetido) -> JSONResponse:
    return respuesta_de_error(409, CodigoTexto.NOMBRE_REPETIDO, str(error))


def _a_json(entrada: DefinicionColumnasEntrada) -> Any:
    """Lo que el cliente envio, sin lo que no mando: el lector estricto decide que es valido."""
    return entrada.model_dump(exclude_unset=True, exclude_none=True)


# --- Endpoints ----------------------------------------------------------------------------------


@router.get("", response_model=list[ResumenDefinicionRespuesta])
def listar_definiciones(
    servicio: DefinicionesColumnasService = Depends(obtener_servicio_definiciones),
) -> list[ResumenDefinicionRespuesta]:
    """Las definiciones, ordenadas por nombre, con su version vigente (C-7). Sin paginar."""
    return [_resumen(r) for r in servicio.listar()]


@router.post(
    "", status_code=201, response_model=DefinicionRespuesta, responses=RESPUESTAS_ESCRITURA
)
def crear_definicion(
    entrada: DefinicionColumnasEntrada,
    servicio: DefinicionesColumnasService = Depends(obtener_servicio_definiciones),
) -> Any:
    """Guarda una definicion nueva con su version 1. El nombre es obligatorio y unico."""
    try:
        return _vista(servicio.crear(_a_json(entrada)))
    except DefinicionInvalida as error:
        return _invalida(error)
    except NombreDeDefinicionRepetido as error:
        return _repetido(error)


@router.get("/{definicion_id}", response_model=DefinicionRespuesta, responses=RESPUESTAS_LECTURA)
def obtener_definicion(
    definicion_id: int,
    version: int | None = Query(default=None, ge=1, description="Por defecto, la vigente"),
    servicio: DefinicionesColumnasService = Depends(obtener_servicio_definiciones),
) -> Any:
    """Una definicion con la version vigente o con la `version` pedida."""
    try:
        return _vista(servicio.obtener(definicion_id, version))
    except (DefinicionNoEncontrada, VersionNoEncontrada) as error:
        return _no_existe(error)


@router.patch(
    "/{definicion_id}",
    response_model=DefinicionRespuesta,
    responses=RESPUESTAS_ESCRITURA,
)
def renombrar_definicion(
    definicion_id: int,
    entrada: RenombrarDefinicionEntrada,
    servicio: DefinicionesColumnasService = Depends(obtener_servicio_definiciones),
) -> Any:
    """Cambia solo el nombre (RF-56): no crea una version ni modifica ninguna, y mueve
    `actualizado_en`. Mismo nombre que el actual: sin error y sin cambios. Otro nombre ya en uso
    (sin distinguir mayusculas ni espacios) es 409 `nombre_repetido`; vacio o de mas de 120
    caracteres, 400 con el problema en `campo = nombre`. Devuelve la definicion con su version
    vigente."""
    try:
        renombrada = servicio.renombrar(definicion_id, entrada.nombre)
    except DefinicionNoEncontrada as error:
        return _no_existe(error)
    except DefinicionInvalida as error:
        return _invalida(error)
    except NombreDeDefinicionRepetido as error:
        return _repetido(error)
    return _definicion(renombrada, renombrada.vigente)


@router.post(
    "/{definicion_id}/versiones",
    status_code=201,
    response_model=DefinicionRespuesta,
    responses=RESPUESTAS_ESCRITURA,
)
def agregar_version(
    definicion_id: int,
    entrada: DefinicionColumnasEntrada,
    servicio: DefinicionesColumnasService = Depends(obtener_servicio_definiciones),
) -> Any:
    """Guarda el cambio como una version nueva, que pasa a ser la vigente.

    El nombre no cambia: si viene, debe ser el de la definicion (sin distinguir mayusculas).
    """
    try:
        return _vista(servicio.agregar_version(definicion_id, _a_json(entrada)))
    except DefinicionNoEncontrada as error:
        return _no_existe(error)
    except DefinicionInvalida as error:
        return _invalida(error)

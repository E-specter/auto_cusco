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

La carga tiene una fecha de envio (RF-55): la que pide `fecha_envio` o, sin ella, hoy en Lima. Si
es anterior a la fecha de corte se rechaza con `400` y las dos fechas; las respuestas dicen cual
se uso.
"""

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from app.adapters.output import exportadores
from app.adapters.output.exportadores.exportador_xlsx import LARGO_MAXIMO_HOJA
from app.api.cartera import obtener_servicio_cartera
from app.api.consultas import parsear_filtro, parsear_orden, texto_si_es_monto
from app.api.definiciones_columnas import obtener_servicio_definiciones
from app.api.errores import ErrorConCodigo, respuestas_de_error_con_codigo
from app.api.fecha_envio import DetalleErrorFechaEnvio, error_de_fecha_envio
from app.api.respuestas import ModeloRespuesta
from app.core.entities.cartera import ConsultaInvalida, SinVersionVigente
from app.core.entities.definiciones_columnas import DefinicionNoEncontrada, VersionNoEncontrada
from app.core.entities.exportacion import (
    CODIFICACIONES_SUGERIDAS,
    DELIMITADORES_SUGERIDOS,
    EXTENSIONES,
    LARGO_DELIMITADOR,
    OPCIONES_POR_DEFECTO,
    SANGRIA_MAXIMA,
    TIPOS_MIME,
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
from app.core.entities.texto_enriquecido import CodigoTexto
from app.core.services.definiciones_columnas.servicio import (
    DefinicionCargada,
    DefinicionesColumnasService,
)
from app.core.services.fecha_envio import FechaEnvioAnterior
from app.core.services.generacion_cargas.servicio import (
    CANTIDAD_MAXIMA,
    CANTIDAD_POR_DEFECTO,
    GeneracionCargasService,
    ResultadoGeneracion,
)
from app.core.services.seleccion_cartera.servicio import ConsultaCarteraService

router = APIRouter(prefix="/archivos-carga", tags=["archivos de carga"])

# Los `400` de estas entradas pueden traer, con `fecha_envio_anterior`, las dos fechas.
RESPUESTAS_ERROR: dict[int | str, dict[str, Any]] = {
    **respuestas_de_error_con_codigo(404),
    400: {
        "model": DetalleErrorFechaEnvio,
        "description": (
            "La peticion no se puede atender tal como viene; el motivo esta en detail. Con el "
            "codigo fecha_envio_anterior trae ademas fecha_envio y fecha_corte"
        ),
    },
}

FILAS_DE_MUESTRA = 20

# Resumen que acompana a la descarga. Una sola lista para lo que se envia, lo
# que declara el contrato OpenAPI y lo que CORS deja leer al navegador.
CABECERAS_RESUMEN: dict[str, str] = {
    "X-Carga-Generados": "Filas escritas en el archivo",
    "X-Carga-Disponibles": "Productos que cumplen la seleccion completa",
    "X-Carga-Solicitados": "Cantidad de productos pedida",
    "X-Carga-Suficiente": "1 si habia al menos tantos productos como se pidieron, 0 si no",
    "X-Carga-Errores": "Campos que no se pudieron generar; el detalle esta en /previsualizacion",
    "X-Carga-Excluidos": (
        "Productos que no salen en el archivo porque no caen en ningun segmento (RF-50); "
        "generados + excluidos = min(disponibles, solicitados). El detalle de los primeros "
        "esta en /previsualizacion"
    ),
}


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
    """Los defectos y los limites salen de `OpcionesArchivo` y de las constantes de la entidad: es
    lo mismo que anuncia `GET /formatos`."""

    delimitador: str = Field(
        default=OPCIONES_POR_DEFECTO.delimitador,
        min_length=LARGO_DELIMITADOR,
        max_length=LARGO_DELIMITADOR,
    )
    codificacion: str = OPCIONES_POR_DEFECTO.codificacion
    con_cabeceras: bool = OPCIONES_POR_DEFECTO.con_cabeceras
    hoja: str = OPCIONES_POR_DEFECTO.hoja
    sangria: int | None = Field(default=OPCIONES_POR_DEFECTO.sangria, ge=0, le=SANGRIA_MAXIMA)


class DefinicionGuardadaEntrada(BaseModel):
    """Una definicion de `/definiciones-columnas`: la version pedida o, sin ella, la vigente."""

    id: int
    version: int | None = Field(default=None, ge=1)


class PeticionGeneracion(BaseModel):
    """Una definicion en linea (como siempre, RF-54) o una `definicion_guardada`: exactamente una.

    Con una guardada, `proteger_formulas` de la definicion pasa a las opciones del archivo y, al
    generar el archivo, la version queda marcada como usada.
    """

    fecha_corte: date
    fecha_envio: date | None = Field(
        default=None,
        description=(
            "Fecha en que se envia la carga (RF-55); por defecto, hoy en America/Lima. No puede "
            "ser anterior a fecha_corte. Ajusta dias_atraso_ajustados a los dias que pasaron"
        ),
    )
    definicion: DefinicionEntrada | None = None
    definicion_guardada: DefinicionGuardadaEntrada | None = None
    formato: FormatoArchivo = FormatoArchivo.XLSX
    filtros: list[str] = []
    orden: str | None = None
    cantidad: int = Field(default=CANTIDAD_POR_DEFECTO, ge=1, le=CANTIDAD_MAXIMA)
    opciones: OpcionesEntrada | None = None


class ErrorGeneracionRespuesta(ModeloRespuesta):
    fila: int
    campo: str
    detalle: str


class ExclusionCargaRespuesta(ModeloRespuesta):
    """Un producto de la muestra que no sale en la carga y por que (RF-50).

    `fila` es su posicion en la seleccion (desde 1), no la de la tabla; `pagare` lo identifica.
    """

    fila: int
    pagare: str | None
    codigo: CodigoTexto
    detalle: str


class PrevisualizacionRespuesta(ModeloRespuesta):
    """`generados + excluidos` son los productos evaluados de la muestra: `min(disponibles,
    muestra)`, con `muestra = min(solicitados, 20)`. `suficiente` es de la seleccion completa
    (habia productos para lo pedido) y no considera las exclusiones."""

    nombre_archivo: str
    cabeceras: list[str]
    filas: list[dict[str, Any]]
    disponibles: int
    solicitados: int
    generados: int
    excluidos: int
    suficiente: bool
    completa: bool
    fecha_envio: date  # la que se uso: la pedida o, sin ella, hoy en Lima (RF-55)
    errores: list[ErrorGeneracionRespuesta]
    exclusiones: list[ExclusionCargaRespuesta]


class OpcionFormatoRespuesta(ModeloRespuesta):
    """Una opcion del archivo con lo que la pantalla necesita para pintarla sin repetir reglas.

    `defecto` es el de `OpcionesArchivo` (nulo en `sangria` significa una sola linea). `sugeridos`
    son valores usuales de una lista ABIERTA (el exportador acepta otros); ninguna opcion tiene hoy
    una lista cerrada. `minimo` y `maximo` acotan el valor de un `entero` y el largo de un
    `texto`; nulos si no hay limite.
    """

    nombre: str
    tipo: Literal["texto", "booleano", "entero"]
    defecto: bool | int | str | None
    sugeridos: list[str] | None
    minimo: int | None
    maximo: int | None


class FormatoRespuesta(ModeloRespuesta):
    formato: str
    extension: str
    opciones: list[OpcionFormatoRespuesta]


# Que opcion de OpcionesArchivo usa cada formato, para que la interfaz muestre
# solo las que corresponden.
OPCIONES_POR_FORMATO: dict[FormatoArchivo, tuple[str, ...]] = {
    FormatoArchivo.XLSX: ("con_cabeceras", "hoja"),
    FormatoArchivo.CSV: ("delimitador", "codificacion", "con_cabeceras"),
    FormatoArchivo.JSON: ("codificacion", "sangria"),
}


def _opcion(nombre: str) -> OpcionFormatoRespuesta:
    """La descripcion de una opcion; el defecto se lee de `OpcionesArchivo`."""
    defecto = getattr(OPCIONES_POR_DEFECTO, nombre)
    descripciones: dict[str, dict[str, Any]] = {
        "delimitador": {
            "tipo": "texto",
            "sugeridos": list(DELIMITADORES_SUGERIDOS),
            "minimo": LARGO_DELIMITADOR,
            "maximo": LARGO_DELIMITADOR,
        },
        "codificacion": {"tipo": "texto", "sugeridos": list(CODIFICACIONES_SUGERIDAS)},
        "con_cabeceras": {"tipo": "booleano"},
        "hoja": {"tipo": "texto", "maximo": LARGO_MAXIMO_HOJA},
        "sangria": {"tipo": "entero", "minimo": 0, "maximo": SANGRIA_MAXIMA},
    }
    return OpcionFormatoRespuesta(
        nombre=nombre,
        defecto=defecto,
        **{"sugeridos": None, "minimo": None, "maximo": None, **descripciones[nombre]},
    )


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


def _opciones(entrada: OpcionesEntrada | None, proteger_formulas: bool = True) -> OpcionesArchivo:
    valores = {} if entrada is None else entrada.model_dump()
    return OpcionesArchivo(**valores, proteger_formulas=proteger_formulas)


def _resolver_definicion(
    peticion: PeticionGeneracion, definiciones: DefinicionesColumnasService
) -> tuple[DefinicionCarga, DefinicionCargada | None]:
    """La definicion en linea, o la guardada ya cargada. Exactamente una de las dos."""
    if (peticion.definicion is None) == (peticion.definicion_guardada is None):
        raise ErrorConCodigo(
            400,
            "Se pide una definicion en linea o una definicion guardada, no las dos ni ninguna",
            CodigoTexto.DEFINICION_INVALIDA,
        )
    if peticion.definicion is not None:
        return _definicion(peticion.definicion), None
    guardada = peticion.definicion_guardada
    try:
        cargada = definiciones.cargar(guardada.id, guardada.version)  # type: ignore[union-attr]
    except DefinicionNoEncontrada as exc:
        raise ErrorConCodigo(404, str(exc), CodigoTexto.DEFINICION_NO_ENCONTRADA) from exc
    except VersionNoEncontrada as exc:
        raise ErrorConCodigo(404, str(exc), CodigoTexto.VERSION_NO_ENCONTRADA) from exc
    return cargada.definicion, cargada


def _error(exc: Exception) -> ErrorConCodigo:
    """Los errores de siempre, sin codigo: el `detail` es el mismo que antes."""
    if isinstance(exc, SinVersionVigente):
        return ErrorConCodigo(404, str(exc), CodigoTexto.SIN_VERSION_VIGENTE)
    return ErrorConCodigo(400, str(exc), None)


def _generar(
    servicio: GeneracionCargasService,
    peticion: PeticionGeneracion,
    cantidad: int,
    definicion: DefinicionCarga,
) -> ResultadoGeneracion:
    try:
        return servicio.generar(
            peticion.fecha_corte,
            definicion,
            [parsear_filtro(crudo) for crudo in peticion.filtros],
            parsear_orden(peticion.orden),
            cantidad,
            peticion.fecha_envio,
        )
    except FechaEnvioAnterior as exc:
        raise error_de_fecha_envio(exc) from exc
    except (ConsultaInvalida, PlantillaInvalida, SinVersionVigente) as exc:
        raise _error(exc) from exc


def _valor_json(valor: Any) -> Any:
    return texto_si_es_monto(valor) if not isinstance(valor, date) else valor.isoformat()


@router.get("/formatos", response_model=list[FormatoRespuesta])
def listar_formatos() -> list[FormatoRespuesta]:
    """Formatos que se pueden generar y que opciones admite cada uno (RF-13)."""
    return [
        FormatoRespuesta(
            formato=formato.value,
            extension=EXTENSIONES[formato],
            opciones=[_opcion(nombre) for nombre in OPCIONES_POR_FORMATO[formato]],
        )
        for formato in exportadores.EXPORTADORES
    ]


@router.post(
    "/previsualizacion",
    response_model=PrevisualizacionRespuesta,
    responses=RESPUESTAS_ERROR,
)
def previsualizar(
    peticion: PeticionGeneracion,
    servicio: GeneracionCargasService = Depends(obtener_servicio_generacion),
    definiciones: DefinicionesColumnasService = Depends(obtener_servicio_definiciones),
) -> PrevisualizacionRespuesta:
    """Primeras filas y errores de la carga, sin escribir el archivo.

    `disponibles` es el total de la seleccion completa, no el de la muestra: es
    lo que dice si alcanzan los productos para la cantidad pedida (RF-08).
    """
    muestra = min(peticion.cantidad, FILAS_DE_MUESTRA)
    definicion, _ = _resolver_definicion(peticion, definiciones)
    resultado = _generar(servicio, peticion, muestra, definicion)
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
        excluidos=resultado.excluidos,
        suficiente=resultado.disponibles >= peticion.cantidad,
        completa=resultado.completa,
        fecha_envio=resultado.fecha_envio,
        errores=[
            ErrorGeneracionRespuesta(fila=error.fila, campo=error.campo, detalle=error.detalle)
            for error in resultado.errores
        ],
        exclusiones=[
            ExclusionCargaRespuesta(
                fila=e.fila, pagare=e.pagare, codigo=CodigoTexto(e.codigo), detalle=e.detalle
            )
            for e in resultado.exclusiones
        ],
    )


def _respuesta_de_descarga() -> dict[int | str, dict[str, Any]]:
    """El archivo generado y su resumen, en vez del JSON que FastAPI supondria."""
    numero = {"type": "string", "pattern": "^[0-9]+$"}
    esquemas = {nombre: numero for nombre in CABECERAS_RESUMEN}
    esquemas["X-Carga-Suficiente"] = {"type": "string", "enum": ["0", "1"]}
    return {
        200: {
            "description": "El archivo de carga en el formato pedido",
            "content": {
                TIPOS_MIME[formato]: {"schema": {"type": "string", "format": "binary"}}
                for formato in exportadores.EXPORTADORES
            },
            "headers": {
                "Content-Disposition": {
                    "description": 'attachment; filename="<nombre>.<extension>"',
                    "schema": {"type": "string"},
                },
                **{
                    nombre: {"description": descripcion, "schema": esquemas[nombre]}
                    for nombre, descripcion in CABECERAS_RESUMEN.items()
                },
            },
        },
        **RESPUESTAS_ERROR,
    }


@router.post("", response_class=Response, responses=_respuesta_de_descarga())
def generar_archivo(
    peticion: PeticionGeneracion,
    servicio: GeneracionCargasService = Depends(obtener_servicio_generacion),
    definiciones: DefinicionesColumnasService = Depends(obtener_servicio_definiciones),
) -> Response:
    """Genera la carga completa y devuelve el archivo (RF-09, RF-13, RF-15).

    El resumen viaja en cabeceras `X-Carga-*` porque el cuerpo es el archivo;
    el detalle de los errores se consulta en `/previsualizacion`. Con una definicion guardada, su
    `proteger_formulas` rige el archivo y, una vez generado, la version queda marcada como usada
    (`usada_en`): la previsualizacion no la marca.
    """
    definicion, guardada = _resolver_definicion(peticion, definiciones)
    resultado = _generar(servicio, peticion, peticion.cantidad, definicion)
    try:
        archivo = exportadores.exportar(
            resultado.tabla,
            peticion.formato,
            _opciones(peticion.opciones, definicion.proteger_formulas),
        )
    except ExportacionInvalida as exc:
        raise _error(exc) from exc
    if guardada is not None:
        definiciones.marcar_usada(guardada.id, guardada.numero)
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
            "X-Carga-Excluidos": str(resultado.excluidos),
        },
    )

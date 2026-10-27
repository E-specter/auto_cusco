"""Adaptador HTTP del mapeador de encabezados (RF-57 a RF-63, docs/mapeador-encabezados.md §6).

Generico del mapeador, sin saber de la sabana: recibe un `catalogo_id`.

    GET    /mapeador/catalogos/{catalogo_id}       los campos del catalogo y las codificaciones
    POST   /mapeador/{catalogo_id}/borradores      sube un archivo, lo analiza y deja un borrador
    POST   /mapeador/borradores/{id}/analisis      vuelve a analizar el mismo borrador
    POST   /mapeador/borradores/{id}/validacion    los problemas de unas asignaciones
    DELETE /mapeador/borradores/{id}               descarta el borrador (cancelar)

Confirmar es del consumidor: para la sabana, `POST /cargas/desde-borrador` (en `cargas.py`).

Los `indice` van en base 0. Los estados, los origenes y los codigos de problema son enums del
contrato: el frontend no los escribe a mano. Un borrador que no existe, vencio o ya se confirmo es
un 404. Tambien arma el servicio con su repositorio PostgreSQL (`crear_servicio_mapeador`), que usa
el arranque de la aplicacion para borrar los borradores vencidos.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.adapters.input.lector_csv import CANDIDATOS_DE_SEPARADOR, CODIFICACIONES
from app.adapters.input.lector_tabla import LectorTabla
from app.adapters.persistence.db import get_engine
from app.adapters.persistence.repositorio_mapeador_postgres import RepositorioMapeadorPostgres
from app.api.errores import DetalleError, ErrorConCodigo
from app.api.respuestas import ModeloRespuesta
from app.core.entities.borrador import BorradorNoEncontrado, CatalogoDesconocido
from app.core.entities.campos_adicionales import (
    CampoAdicional,
    CampoAdicionalNoEncontrado,
    ColumnaInexistente,
    NombreDeCampoRepetido,
    TipoAdicional,
)
from app.core.entities.lectura_tabla import (
    AdvertenciaLectura,
    CodigoAdvertenciaLectura,
    FormatoTabla,
    OpcionDetectable,
    OpcionesLectura,
)
from app.core.entities.mapeador import (
    Asignacion,
    CampoDestino,
    CodigoErrorMapeador,
    CodigoMapeo,
    ColumnaAnalizada,
    EstadoEncabezado,
    OrigenAsignacion,
    ProblemaMapeo,
)
from app.core.entities.sabana import (
    ArchivoSabanaError,
    ArchivoVacio,
    CodificacionInvalida,
    CodificacionNoCoincide,
    ExtensionNoCoincide,
    HojaNoEncontrada,
    HojaVacia,
    SeparadorInvalido,
)
from app.core.services.borradores_carga.servicio import BorradorAnalizado, MapeadorService
from app.core.services.ingesta_sabana.mapeable import CATALOGO_SABANA_MAPEABLE
from app.core.services.mapeador.similitud import alias_legibles

router = APIRouter(prefix="/mapeador", tags=["mapeador de encabezados"])

TAMANO_MAXIMO_BYTES = 64 * 1024 * 1024  # el mismo que POST /cargas


def crear_servicio_mapeador() -> MapeadorService:
    return MapeadorService(
        RepositorioMapeadorPostgres(get_engine()), LectorTabla(), [CATALOGO_SABANA_MAPEABLE]
    )


def obtener_servicio_mapeador() -> MapeadorService:
    """Dependencia de FastAPI; los tests la sustituyen por un doble de prueba."""
    return crear_servicio_mapeador()


# --- Respuestas ---------------------------------------------------------------------------------


class CampoDestinoRespuesta(ModeloRespuesta):
    """Un campo del catalogo; `clave_etiqueta` es la clave i18n de su nombre legible. `alias` son
    solo los alias literales, legibles (sin `_` ni expresiones regulares), para buscar el campo.
    Un campo `adicional` (RF-64) lo creo el usuario: su nombre legible es `etiqueta`, un texto
    literal que manda sobre `clave_etiqueta`; en uno base es nulo."""

    nombre: str
    clave_etiqueta: str
    tipo: str
    obligatorio: bool
    alias: list[str]
    etiqueta: str | None
    adicional: bool


class CatalogoMapeadorRespuesta(ModeloRespuesta):
    """Los campos del catalogo (la lista del desplegable) y lo que la pantalla ofrece para leer un
    CSV, en el orden en que se prueba al detectar: las `codificaciones` y los `separadores`."""

    id: str
    campos: list[CampoDestinoRespuesta]
    codificaciones: list[str]
    separadores: list[str]


class ColumnaAnalizadaRespuesta(ModeloRespuesta):
    """Una columna del archivo. `indice` va en base 0 y es su posicion en el archivo (los
    encabezados vacios no se listan, pero el indice de las demas se conserva). `sugerido` es un
    campo o nulo («No cargar»); `similitud` solo la tiene un `parecido`."""

    indice: int
    encabezado: str
    ejemplos: list[str]
    estado: EstadoEncabezado
    sugerido: str | None
    similitud: float | None


class ProblemaMapeoRespuesta(ModeloRespuesta):
    """Un problema de las asignaciones; `indice` es nulo si es de todo el mapeo (un obligatorio)."""

    indice: int | None
    codigo: CodigoMapeo
    detalle: str
    campo: str | None


class AdvertenciaLecturaRespuesta(ModeloRespuesta):
    """Un aviso de la lectura en una fila (`numero_fila` en base 1, como Excel)."""

    numero_fila: int
    columna: str
    codigo: CodigoAdvertenciaLectura


class AnalisisRespuesta(ModeloRespuesta):
    """El borrador con su analisis y lo que se detecto al leer el archivo.

    `hojas` y `hoja` son de una hoja de calculo; `separador` y `codificacion`, de un CSV (nulos y
    vacios en los demas). `filas` son las de datos. `problemas` son los del mapeo sugerido tal como
    llega (RF-60). `detectados` son las opciones de lectura que el lector detecto porque no se
    eligieron (`hoja`, `separador`, `codificacion`): la pantalla las marca «(detectado)».
    """

    borrador_id: int
    catalogo_id: str
    formato: FormatoTabla
    hojas: list[str]
    hoja: str | None
    separador: str | None
    codificacion: str | None
    filas: int
    columnas: list[ColumnaAnalizadaRespuesta]
    problemas: list[ProblemaMapeoRespuesta]
    advertencias: list[AdvertenciaLecturaRespuesta]
    detectados: list[OpcionDetectable]


class ValidacionMapeoRespuesta(ModeloRespuesta):
    problemas: list[ProblemaMapeoRespuesta]


class DetalleErrorMapeo(ModeloRespuesta):
    """Un `422` al confirmar: el motivo, el `codigo` (`mapeo_con_problemas`) y todos los problemas
    de las asignaciones (RF-60)."""

    detail: str
    codigo: CodigoErrorMapeador
    problemas: list[ProblemaMapeoRespuesta]


class CampoAdicionalRespuesta(ModeloRespuesta):
    """La definicion de un campo adicional. `nombre` es el nombre tecnico (`ad_...`): estable, y el
    que usa todo lo guardado. `encabezado_origen` es el encabezado de la sabana, normalizado."""

    nombre: str
    nombre_legible: str
    tipo: TipoAdicional
    encabezado_origen: str
    archivado: bool


class CampoAdicionalCreadoRespuesta(ModeloRespuesta):
    """El campo recien creado y los campos del catalogo con los que ya cuenta el borrador (los
    base y los adicionales activos), para refrescar la lista del desplegable."""

    campo: CampoDestinoRespuesta
    campos: list[CampoDestinoRespuesta]


class DetalleErrorMapeador(DetalleError):
    """El cuerpo de un `400`, `404`, `409` o `413` del mapeador: el motivo en `detail` (para el
    registro) y el `codigo` que la pantalla traduce. Los datos viajan solo con su codigo: `hoja` y
    `hojas` con `hoja_inexistente`, `maximo_mb` con `archivo_demasiado_grande` y `campo` (el que
    ya tiene ese nombre) con `nombre_repetido`."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=False)

    codigo: CodigoErrorMapeador
    hoja: str | None = None
    hojas: list[str] | None = None
    maximo_mb: int | None = None
    campo: CampoDestinoRespuesta | None = None


_DESCRIPCIONES = {
    400: "El archivo o las opciones de lectura no sirven; `codigo` dice por que",
    404: "No existe el catalogo, el borrador (o venció, o ya se confirmó), la columna o el campo",
    409: "Otro campo ya tiene ese nombre (`campo` es el que choca)",
    413: "El archivo supera el tamano maximo (`maximo_mb`)",
}


def respuestas_de_error_mapeador(*estados: int) -> dict[int | str, dict[str, Any]]:
    return {
        estado: {"model": DetalleErrorMapeador, "description": _DESCRIPCIONES[estado]}
        for estado in estados
    }


_CODIGOS_NO_ENCONTRADO: tuple[tuple[type[Exception], CodigoErrorMapeador], ...] = (
    (CatalogoDesconocido, CodigoErrorMapeador.CATALOGO_DESCONOCIDO),
    (CampoAdicionalNoEncontrado, CodigoErrorMapeador.CAMPO_ADICIONAL_NO_ENCONTRADO),
    (ColumnaInexistente, CodigoErrorMapeador.COLUMNA_INEXISTENTE),
)


def error_no_encontrado(error: Exception) -> ErrorConCodigo:
    """Un `404`: el borrador, salvo que sea de las otras causas conocidas."""
    codigo = next(
        (c for tipo, c in _CODIGOS_NO_ENCONTRADO if isinstance(error, tipo)),
        CodigoErrorMapeador.BORRADOR_NO_ENCONTRADO,
    )
    return ErrorConCodigo(404, str(error), codigo)


def _campo_destino(c: CampoDestino) -> CampoDestinoRespuesta:
    return CampoDestinoRespuesta(
        nombre=c.nombre,
        clave_etiqueta=c.clave_etiqueta,
        tipo=c.tipo,
        obligatorio=c.obligatorio,
        alias=list(alias_legibles(c)),
        etiqueta=c.etiqueta,
        adicional=c.adicional,
    )


def error_de_nombre_repetido(error: NombreDeCampoRepetido) -> ErrorConCodigo:
    """Un `409` con el campo que ya tiene ese nombre."""
    return ErrorConCodigo(
        409,
        str(error),
        CodigoErrorMapeador.NOMBRE_REPETIDO,
        {"campo": _campo_destino(error.campo).model_dump(mode="json")},
    )


def _definicion(c: CampoAdicional) -> CampoAdicionalRespuesta:
    return CampoAdicionalRespuesta(
        nombre=c.nombre,
        nombre_legible=c.nombre_legible,
        tipo=c.tipo,
        encabezado_origen=c.encabezado_origen,
        archivado=c.archivado,
    )


# La causa mas especifica primero: todas son un `ArchivoSabanaError`.
_CODIGOS_DE_LECTURA: tuple[tuple[type[ArchivoSabanaError], CodigoErrorMapeador], ...] = (
    (ArchivoVacio, CodigoErrorMapeador.ARCHIVO_VACIO),
    (ExtensionNoCoincide, CodigoErrorMapeador.EXTENSION_NO_COINCIDE),
    (SeparadorInvalido, CodigoErrorMapeador.SEPARADOR_INVALIDO),
    (CodificacionInvalida, CodigoErrorMapeador.CODIFICACION_INVALIDA),
    (CodificacionNoCoincide, CodigoErrorMapeador.CODIFICACION_NO_COINCIDE),
    (HojaVacia, CodigoErrorMapeador.ARCHIVO_SIN_DATOS),
)


def error_de_lectura(error: ArchivoSabanaError) -> ErrorConCodigo:
    """Un `400` con el `codigo` de lo que fallo al leer el archivo."""
    if isinstance(error, HojaNoEncontrada):
        return ErrorConCodigo(
            400,
            str(error),
            CodigoErrorMapeador.HOJA_INEXISTENTE,
            {"hoja": error.hoja, "hojas": list(error.disponibles)},
        )
    for tipo, codigo in _CODIGOS_DE_LECTURA:
        if isinstance(error, tipo):
            return ErrorConCodigo(400, str(error), codigo)
    return ErrorConCodigo(400, str(error), CodigoErrorMapeador.ARCHIVO_ILEGIBLE)


def _columna(c: ColumnaAnalizada) -> ColumnaAnalizadaRespuesta:
    return ColumnaAnalizadaRespuesta(
        indice=c.indice,
        encabezado=c.encabezado,
        ejemplos=list(c.ejemplos),
        estado=c.estado,
        sugerido=c.sugerido,
        similitud=c.similitud,
    )


def problema_respuesta(p: ProblemaMapeo) -> ProblemaMapeoRespuesta:
    return ProblemaMapeoRespuesta(
        indice=p.indice, codigo=p.codigo, detalle=p.detalle, campo=p.campo
    )


def _advertencia(a: AdvertenciaLectura) -> AdvertenciaLecturaRespuesta:
    return AdvertenciaLecturaRespuesta(
        numero_fila=a.numero_fila, columna=a.columna, codigo=a.codigo
    )


def _analisis(analizado: BorradorAnalizado) -> AnalisisRespuesta:
    return AnalisisRespuesta(
        borrador_id=analizado.borrador.id,
        catalogo_id=analizado.borrador.catalogo_id,
        formato=analizado.formato,
        hojas=list(analizado.hojas),
        hoja=analizado.hoja,
        separador=analizado.separador,
        codificacion=analizado.codificacion,
        filas=analizado.filas,
        columnas=[_columna(c) for c in analizado.analisis.columnas],
        problemas=[problema_respuesta(p) for p in analizado.analisis.problemas_iniciales],
        advertencias=[_advertencia(a) for a in analizado.advertencias],
        detectados=list(analizado.detectados),
    )


# --- Entradas -----------------------------------------------------------------------------------


def opciones_de(
    hoja: str | None, separador: str | None, codificacion: str | None
) -> OpcionesLectura:
    """Un campo en blanco vale como no elegido."""
    return OpcionesLectura(
        hoja=hoja or None, separador=separador or None, codificacion=codificacion or None
    )


class OpcionesLecturaEntrada(BaseModel):
    """Lo que el usuario elige para leer el archivo; lo que falte se detecta (RF-57)."""

    hoja: str | None = None
    separador: str | None = None
    codificacion: str | None = None

    def a_opciones(self) -> OpcionesLectura:
        return opciones_de(self.hoja, self.separador, self.codificacion)


class AsignacionEntrada(BaseModel):
    """Lo que se hace con una columna: `campo` nulo es «No cargar esta columna». `origen` lo manda
    la pantalla y el backend lo ajusta (docs/mapeador-encabezados.md §3.4)."""

    indice: int
    campo: str | None
    origen: OrigenAsignacion

    def a_asignacion(self) -> Asignacion:
        return Asignacion(self.indice, self.campo, self.origen)


class ValidacionEntrada(BaseModel):
    """Una asignacion por cada columna listada (M-5)."""

    asignaciones: list[AsignacionEntrada]


NombreLegible = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)
]


class NuevoCampoAdicionalEntrada(BaseModel):
    """Crear un campo adicional desde una columna del archivo: `indice` (base 0) es la columna, y
    su encabezado pasa a ser el alias del campo. El tipo no se puede cambiar despues (RF-65)."""

    indice: int = Field(ge=0)
    nombre_legible: NombreLegible
    tipo: TipoAdicional


class CambioCampoAdicionalEntrada(BaseModel):
    """Renombrar, archivar o reactivar: lo que no viene no cambia. El nombre tecnico no cambia."""

    nombre_legible: NombreLegible | None = None
    archivado: bool | None = None

    @model_validator(mode="after")
    def _algo_que_cambiar(self) -> "CambioCampoAdicionalEntrada":
        if self.nombre_legible is None and self.archivado is None:
            raise ValueError("Falta nombre_legible o archivado")
        return self


# --- Endpoints ----------------------------------------------------------------------------------


@router.get(
    "/catalogos/{catalogo_id}",
    response_model=CatalogoMapeadorRespuesta,
    responses=respuestas_de_error_mapeador(404),
)
def obtener_catalogo(
    catalogo_id: str, servicio: MapeadorService = Depends(obtener_servicio_mapeador)
) -> CatalogoMapeadorRespuesta:
    """Los campos del catalogo, con su nombre legible, su tipo y si son obligatorios (la lista del
    desplegable), y las codificaciones de un CSV."""
    try:
        catalogo = servicio.catalogo(catalogo_id)
    except CatalogoDesconocido as error:
        raise error_no_encontrado(error) from error
    return CatalogoMapeadorRespuesta(
        id=catalogo.id,
        campos=[_campo_destino(c) for c in catalogo.campos],
        codificaciones=list(CODIFICACIONES),
        separadores=list(CANDIDATOS_DE_SEPARADOR),
    )


@router.post(
    "/{catalogo_id}/borradores",
    response_model=AnalisisRespuesta,
    status_code=201,
    responses=respuestas_de_error_mapeador(400, 404, 413),
)
async def crear_borrador(
    catalogo_id: str,
    archivo: UploadFile = File(description="Excel, ODS, CSV o JSON"),
    hoja: str | None = Form(default=None, description="La hoja de un Excel u ODS"),
    separador: str | None = Form(default=None, description="El separador de un CSV"),
    codificacion: str | None = Form(default=None, description="La codificacion de un CSV"),
    servicio: MapeadorService = Depends(obtener_servicio_mapeador),
) -> AnalisisRespuesta:
    """Sube el archivo, lo lee, lo analiza contra el catalogo (con lo recordado) y lo deja en un
    borrador que vence a las 24 horas. `400` si el archivo esta vacio o no se puede leer, `413` si
    supera el tamano maximo y `404` si el catalogo no existe."""
    contenido = await archivo.read()
    if not contenido:
        raise ErrorConCodigo(400, "El archivo está vacío", CodigoErrorMapeador.ARCHIVO_VACIO)
    if len(contenido) > TAMANO_MAXIMO_BYTES:
        maximo_mb = TAMANO_MAXIMO_BYTES // 1024 // 1024
        raise ErrorConCodigo(
            413,
            f"El archivo supera el máximo de {maximo_mb} MB",
            CodigoErrorMapeador.ARCHIVO_DEMASIADO_GRANDE,
            {"maximo_mb": maximo_mb},
        )
    try:
        analizado = await run_in_threadpool(
            servicio.crear_borrador,
            catalogo_id,
            archivo.filename or "archivo",
            contenido,
            opciones_de(hoja, separador, codificacion),
        )
    except CatalogoDesconocido as error:
        raise error_no_encontrado(error) from error
    except ArchivoSabanaError as error:
        raise error_de_lectura(error) from error
    return _analisis(analizado)


@router.post(
    "/borradores/{borrador_id}/analisis",
    response_model=AnalisisRespuesta,
    responses=respuestas_de_error_mapeador(400, 404),
)
async def volver_a_analizar(
    borrador_id: int,
    opciones: OpcionesLecturaEntrada,
    servicio: MapeadorService = Depends(obtener_servicio_mapeador),
) -> AnalisisRespuesta:
    """Vuelve a analizar el MISMO borrador con otras opciones (hoja, separador, codificacion): no se
    sube el archivo otra vez. Reemplaza el analisis guardado. `404` si no existe o vencio y `400`
    si el archivo no se puede leer con esas opciones."""
    try:
        analizado = await run_in_threadpool(servicio.reanalizar, borrador_id, opciones.a_opciones())
    except BorradorNoEncontrado as error:
        raise error_no_encontrado(error) from error
    except ArchivoSabanaError as error:
        raise error_de_lectura(error) from error
    return _analisis(analizado)


@router.post(
    "/borradores/{borrador_id}/validacion",
    response_model=ValidacionMapeoRespuesta,
    responses=respuestas_de_error_mapeador(404),
)
def validar_asignaciones(
    borrador_id: int,
    entrada: ValidacionEntrada,
    servicio: MapeadorService = Depends(obtener_servicio_mapeador),
) -> ValidacionMapeoRespuesta:
    """Los problemas de las asignaciones, validados contra el analisis que se le mostro al usuario
    (el guardado con el borrador), no contra uno nuevo. Vacio = se puede confirmar."""
    try:
        problemas = servicio.validar(borrador_id, [a.a_asignacion() for a in entrada.asignaciones])
    except BorradorNoEncontrado as error:
        raise error_no_encontrado(error) from error
    return ValidacionMapeoRespuesta(problemas=[problema_respuesta(p) for p in problemas])


@router.delete(
    "/borradores/{borrador_id}", status_code=204, responses=respuestas_de_error_mapeador(404)
)
def descartar_borrador(
    borrador_id: int, servicio: MapeadorService = Depends(obtener_servicio_mapeador)
) -> None:
    """Cancelar: descarta el borrador."""
    try:
        servicio.descartar(borrador_id)
    except BorradorNoEncontrado as error:
        raise error_no_encontrado(error) from error


@router.post(
    "/borradores/{borrador_id}/campos-adicionales",
    response_model=CampoAdicionalCreadoRespuesta,
    status_code=201,
    responses=respuestas_de_error_mapeador(404, 409),
)
def crear_campo_adicional(
    borrador_id: int,
    entrada: NuevoCampoAdicionalEntrada,
    servicio: MapeadorService = Depends(obtener_servicio_mapeador),
) -> CampoAdicionalCreadoRespuesta:
    """Crea un campo adicional desde una columna del borrador y lo suma al analisis guardado, en
    una sola transaccion: enseguida se puede asignar y validar. `409` si otro campo (base o
    adicional, archivado o no) ya tiene ese nombre, con el campo que choca; `404` si el borrador o
    la columna no existen."""
    try:
        campo, catalogo = servicio.crear_campo_adicional(
            borrador_id, entrada.indice, entrada.nombre_legible, entrada.tipo
        )
    except NombreDeCampoRepetido as error:
        raise error_de_nombre_repetido(error) from error
    except (BorradorNoEncontrado, CatalogoDesconocido, ColumnaInexistente) as error:
        raise error_no_encontrado(error) from error
    creado = next(c for c in catalogo.campos if c.nombre == campo.nombre)
    return CampoAdicionalCreadoRespuesta(
        campo=_campo_destino(creado), campos=[_campo_destino(c) for c in catalogo.campos]
    )


@router.get(
    "/{catalogo_id}/campos-adicionales",
    response_model=list[CampoAdicionalRespuesta],
    responses=respuestas_de_error_mapeador(404),
)
def listar_campos_adicionales(
    catalogo_id: str, servicio: MapeadorService = Depends(obtener_servicio_mapeador)
) -> list[CampoAdicionalRespuesta]:
    """Las definiciones de los campos adicionales del catalogo, archivadas incluidas, en el orden
    en que se crearon."""
    try:
        return [_definicion(c) for c in servicio.campos_adicionales(catalogo_id)]
    except CatalogoDesconocido as error:
        raise error_no_encontrado(error) from error


@router.patch(
    "/{catalogo_id}/campos-adicionales/{nombre}",
    response_model=CampoAdicionalRespuesta,
    responses=respuestas_de_error_mapeador(404, 409),
)
def cambiar_campo_adicional(
    catalogo_id: str,
    nombre: str,
    entrada: CambioCampoAdicionalEntrada,
    servicio: MapeadorService = Depends(obtener_servicio_mapeador),
) -> CampoAdicionalRespuesta:
    """Renombra, archiva o reactiva un campo adicional. El nombre tecnico y el tipo no cambian: lo
    guardado que lo usa sigue funcionando. Archivar no borra ningun dato. `409` si el nombre nuevo
    ya lo tiene otro campo."""
    try:
        cambiado = servicio.cambiar_campo_adicional(
            catalogo_id, nombre, entrada.nombre_legible, entrada.archivado
        )
    except NombreDeCampoRepetido as error:
        raise error_de_nombre_repetido(error) from error
    except (CatalogoDesconocido, CampoAdicionalNoEncontrado) as error:
        raise error_no_encontrado(error) from error
    return _definicion(cambiado)

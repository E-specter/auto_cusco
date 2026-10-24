"""Adaptador de entrada HTTP del motor de texto enriquecido (RF-44, RF-47). Solo lectura.

    GET  /texto-enriquecido/catalogo?contexto=   variables, funciones, limites y ejemplos
    POST /texto-enriquecido/validacion           problemas, tipo y cota de una expresion
    POST /texto-enriquecido/previsualizacion     el resultado por fila y por nodo

Una expresion o definicion con problemas es un `200` con los problemas y su ubicacion (nodo,
funcion, parametro; columna y segmento en una definicion): la interfaz los muestra mientras el
usuario edita. Los `404` son lo que no existe (contexto, producto, version de la sabana) y traen
`codigo` ademas de `detail`. Los `400` de las definiciones guardadas son de B4b (guardar).

El contrato de la expresion es permisivo a proposito: `tipo` es un texto y los argumentos son
cualquier valor JSON, porque una forma imposible (un tipo de nodo que no existe) se informa como
problema `expresion_invalida` con su nodo y no como un 422 sin ubicacion.

Los contextos se registran aqui, una linea por contexto (`obtener_registro_contextos`): sumar un
canal es su archivo en `services/plataformas/<canal>/` mas una linea en esta funcion.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.cartera import obtener_servicio_cartera
from app.api.errores import DetalleError, ErrorConCodigo
from app.api.fecha_envio import DetalleErrorFechaEnvio, error_de_fecha_envio
from app.api.respuestas import ModeloRespuesta
from app.api.selecciones import obtener_servicio_selecciones
from app.core.entities.cartera import ConsultaInvalida, SinVersionVigente
from app.core.entities.contexto_texto import ContextoDesconocido, ContextoTexto
from app.core.entities.definiciones_columnas import (
    LARGO_MAXIMO_NOMBRE,
    MAXIMO_COLUMNAS,
    MAXIMO_VARIANTES,
)
from app.core.entities.segmentacion import RangoDias
from app.core.entities.selecciones import SeleccionNoEncontrada
from app.core.entities.texto_enriquecido import CodigoTexto, MotivoSinCota, Problema
from app.core.services.contextos_texto import RegistroContextos, contexto_cartera
from app.core.services.fecha_envio import FechaEnvioAnterior
from app.core.services.mapeo_campos.serializacion import ProblemaDeDefinicion
from app.core.services.plataformas.mowa_mes.contexto_texto import contexto_speech
from app.core.services.previsualizar_texto import (
    MAXIMO_MUESTRA,
    MUESTRA_POR_DEFECTO,
    CatalogoTexto,
    ColumnaPrevia,
    FilaPrevia,
    Muestra,
    MuestraEjemplo,
    MuestraEjemplosPorSegmento,
    MuestraPrimerosDeSeleccion,
    MuestraProductoReal,
    PrevisualizacionTextoService,
    ProductoNoEncontrado,
    ValidacionTexto,
)
from app.core.services.seleccion_cartera.servicio import ConsultaCarteraService
from app.core.services.selecciones.servicio import SeleccionesService
from app.core.services.texto_enriquecido import catalogo as catalogo_funciones

router = APIRouter(prefix="/texto-enriquecido", tags=["texto enriquecido"])


# --- Composicion --------------------------------------------------------------------------------


def obtener_registro_contextos() -> RegistroContextos:
    """Los contextos de la aplicacion: una linea por contexto."""
    return RegistroContextos(
        [
            contexto_cartera(),
            contexto_speech(),
        ]
    )


def obtener_servicio_texto(
    contextos: RegistroContextos = Depends(obtener_registro_contextos),
    cartera: ConsultaCarteraService = Depends(obtener_servicio_cartera),
    selecciones: SeleccionesService = Depends(obtener_servicio_selecciones),
) -> PrevisualizacionTextoService:
    """Dependencia de FastAPI; los tests la sustituyen por un doble de prueba."""
    return PrevisualizacionTextoService(contextos, cartera, selecciones)


# --- Errores ------------------------------------------------------------------------------------


class DetalleErrorTexto(DetalleError):
    """El motivo y el `codigo` del catalogo (`CodigoTexto`) que la interfaz traduce."""

    codigo: CodigoTexto


RESPUESTAS_404: dict[int | str, dict[str, Any]] = {
    404: {
        "model": DetalleErrorTexto,
        "description": "No existe el contexto, el producto o la version de sabana pedidos",
    }
}


def respuesta_de_error(
    estado: int, codigo: CodigoTexto, detalle: str, **extra: Any
) -> JSONResponse:
    """El cuerpo es `{"detail", "codigo", ...}`: `HTTPException` solo sabe enviar `{"detail"}`."""
    return JSONResponse(
        status_code=estado, content={"detail": detalle, "codigo": codigo.value, **extra}
    )


def _no_existe(codigo: CodigoTexto, detalle: str) -> JSONResponse:
    return respuesta_de_error(404, codigo, detalle)


# --- Entrada ------------------------------------------------------------------------------------


class _Entrada(BaseModel):
    """Lo que no esta en el modelo no se descarta: llega al lector, que lo informa como problema."""

    model_config = ConfigDict(extra="allow")


class FuncionEntrada(_Entrada):
    nombre: str
    args: list[Any] | None = None


class NodoEntrada(_Entrada):
    tipo: str
    valor: str | None = None
    nombre: str | None = None
    funciones: list[FuncionEntrada] | None = None
    obligatoria: bool | None = None


class ExpresionEntrada(_Entrada):
    nodos: list[NodoEntrada]


class FormatoFinancieroColumnaEntrada(_Entrada):
    separador_miles: str | None = None
    separador_decimal: str | None = None
    decimales: int | None = None


class VarianteEntrada(_Entrada):
    segmento: str
    expresion: ExpresionEntrada


class ColumnaEntrada(_Entrada):
    """Una columna de la definicion: la forma que guardara B4b. El contenido es solo expresion;
    `formato_fecha` va con marcas legibles (`dd/mm/aaaa`) y el backend las traduce."""

    nombre: str
    orden: int
    expresion: ExpresionEntrada
    tipo: str | None = None
    formato_fecha: str | None = None
    formato_financiero: FormatoFinancieroColumnaEntrada | None = None
    valor_por_defecto: str | None = None
    variantes: list[VarianteEntrada] | None = None


class RangoEntrada(_Entrada):
    clave: str
    etiqueta: str
    desde: int | None = None
    hasta: int | None = None


class CriterioEntrada(_Entrada):
    tipo: str
    campo: str | None = None
    variable_dias: str | None = None
    tabla: list[RangoEntrada] | None = None


class SegmentacionEntrada(_Entrada):
    criterio: CriterioEntrada | None = None
    politica: str | None = None


class DefinicionColumnasEntrada(_Entrada):
    """Las columnas van con `orden` explicito y se identifican por su posicion en la lista;
    `proteger_formulas` (por defecto verdadero) lo aplica el exportador (RF-53)."""

    nombre: str | None = None
    columnas: list[ColumnaEntrada]
    segmentacion: SegmentacionEntrada | None = None
    proteger_formulas: bool | None = None


class MuestraEntrada(BaseModel):
    """La muestra con la que se evalua.

    `ejemplos_por_segmento` (por defecto), `ejemplo`, `producto_real` (`fecha_corte` y `pagare`) o
    `primeros_de_seleccion`: la `fecha_corte` y una seleccion con la forma de `/cartera`
    (`filtros` y `orden`) o una guardada (`seleccion_id`), con `cantidad` de 1 a 5 (5 por
    defecto), el mismo orden y desempate que la carga. Solo lectura.

    Las dos muestras de la cartera real aceptan `fecha_envio` (RF-55): por defecto, hoy en
    America/Lima, y no puede ser anterior a la `fecha_corte`. Ajusta `dias_atraso_ajustados`; la
    respuesta dice cual se uso. Una muestra de ejemplo no la admite.
    """

    tipo: Literal["ejemplo", "ejemplos_por_segmento", "producto_real", "primeros_de_seleccion"] = (
        "ejemplos_por_segmento"
    )
    fecha_corte: date | None = None
    fecha_envio: date | None = None
    pagare: str | None = None
    filtros: list[str] | None = None
    orden: str | None = None
    seleccion_id: int | None = None
    cantidad: int = Field(default=MUESTRA_POR_DEFECTO, ge=1, le=MAXIMO_MUESTRA)

    @model_validator(mode="after")
    def _la_muestra_se_identifica(self) -> "MuestraEntrada":
        if self.fecha_envio is not None and self.tipo not in (
            "producto_real",
            "primeros_de_seleccion",
        ):
            raise ValueError("Solo la cartera real tiene fecha de envio: no va con un ejemplo")
        if self.tipo == "producto_real" and (self.fecha_corte is None or not self.pagare):
            raise ValueError("Un producto real se pide con `fecha_corte` y `pagare`")
        if self.tipo == "primeros_de_seleccion":
            if self.fecha_corte is None:
                raise ValueError("Los primeros de una seleccion se piden con `fecha_corte`")
            if self.seleccion_id is not None and (self.filtros or self.orden):
                raise ValueError("Una seleccion guardada o `filtros` y `orden`, no las dos")
        return self

    def a_muestra(self) -> Muestra:
        if self.tipo == "producto_real":
            return MuestraProductoReal(
                self.fecha_corte,  # type: ignore[arg-type]
                self.pagare,  # type: ignore[arg-type]
                self.fecha_envio,
            )
        if self.tipo == "primeros_de_seleccion":
            return MuestraPrimerosDeSeleccion(
                fecha_corte=self.fecha_corte,  # type: ignore[arg-type]
                filtros=tuple(self.filtros or ()),
                orden=self.orden,
                seleccion_id=self.seleccion_id,
                cantidad=self.cantidad,
                fecha_envio=self.fecha_envio,
            )
        if self.tipo == "ejemplo":
            return MuestraEjemplo()
        return MuestraEjemplosPorSegmento()


class PeticionValidacion(BaseModel):
    contexto: str
    expresion: ExpresionEntrada


class PeticionPrevisualizacion(BaseModel):
    """Una `expresion` o una `definicion`, y la muestra con la que se evalua."""

    contexto: str
    expresion: ExpresionEntrada | None = None
    definicion: DefinicionColumnasEntrada | None = None
    muestra: MuestraEntrada = MuestraEntrada()

    @model_validator(mode="after")
    def _una_de_las_dos(self) -> "PeticionPrevisualizacion":
        if (self.expresion is None) == (self.definicion is None):
            raise ValueError("Se pide la previsualizacion de una `expresion` o de una `definicion`")
        return self


def _a_json(modelo: BaseModel | None) -> Any:
    """Lo que el cliente envio, sin lo que no mando: el lector estricto decide que es valido."""
    return None if modelo is None else modelo.model_dump(exclude_unset=True, exclude_none=True)


# --- Respuesta ----------------------------------------------------------------------------------


class UbicacionRespuesta(ModeloRespuesta):
    nodo: int
    funcion: int | None
    parametro: str | None


class ProblemaTextoRespuesta(ModeloRespuesta):
    """`ubicacion` es nula cuando el problema es de toda la expresion. `columna` y `segmento`
    ubican el problema dentro de una definicion; `campo` nombra el campo de la definicion cuando
    no es de una columna (`definicion`, `nombre`, `campos`, `segmentacion`)."""

    codigo: CodigoTexto
    detalle: str
    ubicacion: UbicacionRespuesta | None
    nombre: str | None
    columna: int | None
    segmento: str | None
    campo: str | None


class SinCotaRespuesta(ModeloRespuesta):
    codigo: CodigoTexto
    detalle: str
    ubicacion: UbicacionRespuesta


# Tipos cerrados: el cliente generado los recibe como uniones y un tipo nuevo no pasa sin avisar.
# `nulo` no sale: ninguna variable ni funcion lo declara. Una prueba exige que esta lista siga a
# `TipoValor`. `entrada` solo lo dice una funcion o un parametro que toma el tipo de lo que recibe.
TipoValorRespuesta = Literal["texto", "numero", "fecha", "booleano"]
TipoOEntradaRespuesta = Literal["texto", "numero", "fecha", "booleano", "entrada"]


class VariableRespuesta(ModeloRespuesta):
    """`origen` es el contexto que aporta la variable: `cartera` para un campo de la cartera, o el
    del modulo (`mowa_mes.speech`) para una variable suya. La interfaz las agrupa por origen."""

    nombre: str
    tipo: TipoValorRespuesta
    clave_nombre: str | None
    origen: str


class RangoRespuesta(ModeloRespuesta):
    clave: str
    etiqueta: str
    desde: int | None
    hasta: int | None


class ContextoRespuesta(ModeloRespuesta):
    nombre: str
    clave_nombre: str
    variables: list[VariableRespuesta]
    ejemplo: dict[str, Any]
    limite_largo: int | None
    umbral_advertencia: int | None
    variable_dias: str
    segmentos: list[RangoRespuesta]


class ContextoDisponibleRespuesta(ModeloRespuesta):
    nombre: str
    clave_nombre: str


class OpcionRespuesta(ModeloRespuesta):
    valor: str
    ejemplo: str | None


class ParametroRespuesta(ModeloRespuesta):
    nombre: str
    clave_nombre: str
    tipo: TipoOEntradaRespuesta
    obligatorio: bool
    por_defecto: Any
    acepta_variable: bool
    entero: bool
    minimo: int | None
    maximo: int | None
    largo_minimo: int | None
    largo_maximo: int | None
    opciones: list[OpcionRespuesta]
    opciones_cerradas: bool


class FuncionRespuesta(ModeloRespuesta):
    nombre: str
    familia: str
    clave_familia: str
    clave_nombre: str
    clave_descripcion: str
    recibe: list[TipoValorRespuesta]
    devuelve: TipoOEntradaRespuesta
    acepta_nulo: bool
    parametros: list[ParametroRespuesta]


class PatronFechaRespuesta(ModeloRespuesta):
    patron: str
    ejemplo: str


class MarcaFechaRespuesta(ModeloRespuesta):
    marca: str
    clave: str
    ejemplo: str


class LimitesRespuesta(ModeloRespuesta):
    """Los del motor (`LimitesExpresion`) y los de una definicion guardada (C-9)."""

    nodos: int
    funciones_por_nodo: int
    argumentos_por_funcion: int
    largo_literal: int
    columnas_por_definicion: int
    variantes_por_columna: int
    largo_nombre_definicion: int


class CatalogoRespuesta(ModeloRespuesta):
    contexto: ContextoRespuesta
    contextos: list[ContextoDisponibleRespuesta]
    funciones: list[FuncionRespuesta]
    familias: list[str]
    patrones_fecha: list[PatronFechaRespuesta]
    marcas_fecha: list[MarcaFechaRespuesta]
    limites: LimitesRespuesta


class ValidacionRespuesta(ModeloRespuesta):
    """`tipo`, `cota` y `variables` solo tienen valor si la expresion es valida; `sin_cota` explica
    por que no hay largo maximo cuando es valida y `cota` es nula."""

    problemas: list[ProblemaTextoRespuesta]
    tipo: str | None
    cota: int | None
    sin_cota: SinCotaRespuesta | None
    variables: list[str]


class NodoRespuesta(ModeloRespuesta):
    """El texto de un nodo. `vacio` es la variable que llego sin dato: no es un texto vacio."""

    indice: int
    tipo: str
    texto: str
    vacio: bool


class ColumnaRespuesta(ModeloRespuesta):
    nombre: str
    tipo: str
    texto: str
    valor: Any
    largo: int
    cota: int | None
    sin_cota: SinCotaRespuesta | None
    usa_variante: bool
    nodos: list[NodoRespuesta]
    problemas: list[ProblemaTextoRespuesta]


class ExclusionFilaRespuesta(ModeloRespuesta):
    codigo: CodigoTexto
    detalle: str


class FilaRespuesta(ModeloRespuesta):
    """`pagare` y `fecha_corte` identifican el producto real que la fila representa (el editor
    lo fija como muestra); son nulos en las muestras de ejemplo."""

    numero: int
    etiqueta: str | None
    segmento: str | None
    pagare: str | None
    fecha_corte: date | None
    excluida: ExclusionFilaRespuesta | None
    columnas: list[ColumnaRespuesta]


class PrevisualizacionTextoRespuesta(ModeloRespuesta):
    """O `problemas` (no compila: sin filas) o `filas`."""

    problemas: list[ProblemaTextoRespuesta]
    filas: list[FilaRespuesta]
    limite_largo: int | None
    umbral_advertencia: int | None
    disponibles: int | None  # los productos de la seleccion, si la muestra es una seleccion
    # La fecha de envio con la que se evaluo (la pedida u hoy en Lima, RF-55); nula si la muestra
    # no es de la cartera real.
    fecha_envio: date | None


# --- Conversion ---------------------------------------------------------------------------------


def _valor_json(valor: Any) -> Any:
    """Fechas en ISO y montos como texto, como el resto de la API."""
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return str(valor)
    return valor


def _ubicacion(
    nodo: int | None, funcion: int | None, parametro: str | None
) -> UbicacionRespuesta | None:
    return (
        None
        if nodo is None
        else UbicacionRespuesta(nodo=nodo, funcion=funcion, parametro=parametro)
    )


def problema_respuesta(
    problema: Problema, de_definicion: ProblemaDeDefinicion | None = None
) -> ProblemaTextoRespuesta:
    return ProblemaTextoRespuesta(
        codigo=problema.codigo,
        detalle=problema.detalle,
        ubicacion=_ubicacion(problema.nodo, problema.funcion, problema.parametro),
        nombre=problema.nombre,
        columna=de_definicion.columna if de_definicion else None,
        segmento=de_definicion.segmento if de_definicion else None,
        campo=de_definicion.campo if de_definicion else None,
    )


def _sin_cota(motivo: MotivoSinCota | None) -> SinCotaRespuesta | None:
    if motivo is None:
        return None
    return SinCotaRespuesta(
        codigo=motivo.codigo,
        detalle=motivo.detalle,
        ubicacion=UbicacionRespuesta(nodo=motivo.nodo, funcion=motivo.funcion, parametro=None),
    )


def _rango(rango: RangoDias) -> RangoRespuesta:
    return RangoRespuesta(
        clave=rango.clave, etiqueta=rango.etiqueta, desde=rango.desde, hasta=rango.hasta
    )


def _contexto(contexto: ContextoTexto) -> ContextoRespuesta:
    return ContextoRespuesta(
        nombre=contexto.nombre,
        clave_nombre=contexto.clave_nombre,
        variables=[
            VariableRespuesta(
                nombre=v.nombre, tipo=v.tipo.value, clave_nombre=v.clave_nombre, origen=v.origen
            )
            for v in contexto.variables
        ],
        ejemplo={nombre: _valor_json(valor) for nombre, valor in contexto.ejemplo.items()},
        limite_largo=contexto.limite_largo,
        umbral_advertencia=contexto.umbral_advertencia,
        variable_dias=contexto.variable_dias,
        segmentos=[_rango(r) for r in contexto.tabla_rangos],
    )


def _parametro(p: catalogo_funciones.ParametroCatalogo) -> ParametroRespuesta:
    return ParametroRespuesta(
        nombre=p.nombre,
        clave_nombre=p.clave_nombre,
        tipo=p.tipo,
        obligatorio=p.obligatorio,
        por_defecto=_valor_json(p.por_defecto),
        acepta_variable=p.acepta_variable,
        entero=p.entero,
        minimo=p.minimo,
        maximo=p.maximo,
        largo_minimo=p.largo_minimo,
        largo_maximo=p.largo_maximo,
        opciones=[OpcionRespuesta(valor=o.valor, ejemplo=o.ejemplo) for o in p.opciones],
        opciones_cerradas=p.opciones_cerradas,
    )


def _funcion(f: catalogo_funciones.FuncionCatalogo) -> FuncionRespuesta:
    return FuncionRespuesta(
        nombre=f.nombre,
        familia=f.familia,
        clave_familia=f.clave_familia,
        clave_nombre=f.clave_nombre,
        clave_descripcion=f.clave_descripcion,
        recibe=list(f.recibe),
        devuelve=f.devuelve,
        acepta_nulo=f.acepta_nulo,
        parametros=[_parametro(p) for p in f.parametros],
    )


def _catalogo(catalogo: CatalogoTexto, contextos: list[ContextoTexto]) -> CatalogoRespuesta:
    limites = catalogo.limites
    return CatalogoRespuesta(
        contexto=_contexto(catalogo.contexto),
        contextos=[
            ContextoDisponibleRespuesta(nombre=c.nombre, clave_nombre=c.clave_nombre)
            for c in contextos
        ],
        funciones=[_funcion(f) for f in catalogo.funciones],
        familias=list(catalogo.familias),
        patrones_fecha=[
            PatronFechaRespuesta(patron=p.patron, ejemplo=p.ejemplo)
            for p in catalogo.patrones_fecha
        ],
        marcas_fecha=[
            MarcaFechaRespuesta(marca=m.marca, clave=m.clave, ejemplo=m.ejemplo)
            for m in catalogo.marcas_fecha
        ],
        limites=LimitesRespuesta(
            nodos=limites.nodos,
            funciones_por_nodo=limites.funciones_por_nodo,
            argumentos_por_funcion=limites.argumentos_por_funcion,
            largo_literal=limites.largo_literal,
            columnas_por_definicion=MAXIMO_COLUMNAS,
            variantes_por_columna=MAXIMO_VARIANTES,
            largo_nombre_definicion=LARGO_MAXIMO_NOMBRE,
        ),
    )


def _columna(c: ColumnaPrevia) -> ColumnaRespuesta:
    return ColumnaRespuesta(
        nombre=c.nombre,
        tipo=c.tipo.value,
        texto=c.texto,
        valor=_valor_json(c.valor),
        largo=c.largo,
        cota=c.cota,
        sin_cota=_sin_cota(c.sin_cota),
        usa_variante=c.usa_variante,
        nodos=[
            NodoRespuesta(indice=n.indice, tipo=n.tipo, texto=n.texto, vacio=n.vacio)
            for n in c.nodos
        ],
        problemas=[problema_respuesta(p) for p in c.problemas],
    )


def _fila(f: FilaPrevia) -> FilaRespuesta:
    return FilaRespuesta(
        numero=f.numero,
        etiqueta=f.etiqueta,
        segmento=f.segmento,
        pagare=f.pagare,
        fecha_corte=f.fecha_corte,
        excluida=(
            None
            if f.excluida is None
            else ExclusionFilaRespuesta(codigo=f.excluida.codigo, detalle=f.excluida.detalle)
        ),
        columnas=[_columna(c) for c in f.columnas],
    )


def _validacion(v: ValidacionTexto) -> ValidacionRespuesta:
    return ValidacionRespuesta(
        problemas=[problema_respuesta(p) for p in v.problemas],
        tipo=None if v.tipo is None else v.tipo.value,
        cota=v.cota,
        sin_cota=_sin_cota(v.sin_cota),
        variables=list(v.variables),
    )


# --- Endpoints ----------------------------------------------------------------------------------


@router.get("/catalogo", response_model=CatalogoRespuesta, responses=RESPUESTAS_404)
def obtener_catalogo(
    contexto: str = Query(default="cartera", description="Nombre del contexto de variables"),
    servicio: PrevisualizacionTextoService = Depends(obtener_servicio_texto),
) -> Any:
    """Variables del contexto con su tipo, funciones con sus parametros y claves i18n, patrones y
    marcas de fecha, limites del motor y el registro de ejemplo (RF-44). Todo sale del registro de
    funciones y de los contextos: una funcion o un contexto nuevo aparece sin tocar este endpoint.
    """
    try:
        return _catalogo(servicio.catalogo(contexto), list(servicio.contextos_disponibles()))
    except ContextoDesconocido as error:
        return _no_existe(CodigoTexto.CONTEXTO_DESCONOCIDO, str(error))


@router.post("/validacion", response_model=ValidacionRespuesta, responses=RESPUESTAS_404)
def validar(
    peticion: PeticionValidacion,
    servicio: PrevisualizacionTextoService = Depends(obtener_servicio_texto),
) -> Any:
    """Los problemas de la expresion con su ubicacion, su tipo resultante y su largo maximo (RF-47).

    Una expresion con problemas responde `200` con ellos: es lo que el editor muestra mientras se
    escribe.
    """
    try:
        return _validacion(servicio.validar(peticion.contexto, _a_json(peticion.expresion)))
    except ContextoDesconocido as error:
        return _no_existe(CodigoTexto.CONTEXTO_DESCONOCIDO, str(error))


@router.post(
    "/previsualizacion",
    response_model=PrevisualizacionTextoRespuesta,
    responses={
        **RESPUESTAS_404,
        400: {
            "model": DetalleErrorFechaEnvio,
            "description": (
                "La peticion no se puede atender tal como viene; el motivo esta en detail. Con el "
                "codigo fecha_envio_anterior trae ademas fecha_envio y fecha_corte"
            ),
        },
    },
)
def previsualizar(
    peticion: PeticionPrevisualizacion,
    servicio: PrevisualizacionTextoService = Depends(obtener_servicio_texto),
) -> Any:
    """El resultado de una expresion o una definicion, por fila y por nodo, con una muestra (RF-47).

    Solo lectura: no guarda nada. Con problemas de compilacion no hay filas y la respuesta trae los
    problemas, cada uno con su columna y su segmento.
    """
    try:
        resultado = servicio.previsualizar(
            peticion.contexto,
            peticion.muestra.a_muestra(),
            expresion=_a_json(peticion.expresion),
            definicion=_a_json(peticion.definicion),
        )
    except ContextoDesconocido as error:
        return _no_existe(CodigoTexto.CONTEXTO_DESCONOCIDO, str(error))
    except ProductoNoEncontrado as error:
        return _no_existe(CodigoTexto.PRODUCTO_NO_ENCONTRADO, str(error))
    except SeleccionNoEncontrada as error:
        return _no_existe(CodigoTexto.SELECCION_NO_ENCONTRADA, str(error))
    except FechaEnvioAnterior as error:
        raise error_de_fecha_envio(error) from error
    except ConsultaInvalida as error:
        raise ErrorConCodigo(400, str(error), None) from error
    except SinVersionVigente as error:
        return _no_existe(CodigoTexto.SIN_VERSION_VIGENTE, str(error))
    return PrevisualizacionTextoRespuesta(
        problemas=[problema_respuesta(p.problema, p) for p in resultado.problemas],
        filas=[_fila(f) for f in resultado.filas],
        limite_largo=resultado.limite_largo,
        umbral_advertencia=resultado.umbral_advertencia,
        disponibles=resultado.disponibles,
        fecha_envio=resultado.fecha_envio,
    )

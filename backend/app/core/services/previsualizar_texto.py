"""Casos de uso del motor de texto enriquecido para la interfaz (RF-44, RF-47): catalogo, validacion
y previsualizacion. Solo lectura: no guardan nada.

La interfaz no evalua ni valida reglas de negocio: pide el catalogo para armar sus menus, la
validacion despues de cada cambio y la previsualizacion para ver el resultado con una muestra.
Una expresion o definicion con problemas no es un error de la peticion: la respuesta los trae con su
ubicacion (nodo, funcion, parametro; columna y variante en una definicion).

La muestra de la previsualizacion es una de tres:

- `ejemplo`: el registro de ejemplo del contexto.
- `ejemplos_por_segmento` (la de por defecto): una fila por segmento, con el registro de ejemplo y
  un valor sintetico de dias que cae en cada rango de la tabla (de la tabla, no escrito a mano). Con
  un criterio por campo, una fila por cada valor que alguna columna contempla.
- `producto_real`: un producto de la cartera, por fecha de corte y pagare.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from app.core.entities.cartera import Filtro, Operador
from app.core.entities.contexto_texto import ContextoTexto
from app.core.entities.mapeo import CampoSalida, DefinicionCarga, FilaExcluida, TipoSalida
from app.core.entities.segmentacion import CriterioCalculado, RangoDias
from app.core.entities.texto_enriquecido import (
    LIMITES,
    ExpresionInvalida,
    LimitesExpresion,
    MotivoSinCota,
    Problema,
    TipoValor,
)
from app.core.services.contextos_texto import RegistroContextos
from app.core.services.mapeo_campos.diagnostico import diagnosticar_leida
from app.core.services.mapeo_campos.generador import GeneradorCargas
from app.core.services.mapeo_campos.serializacion import (
    DefinicionIlegible,
    DefinicionLeida,
    ProblemaDeDefinicion,
    definicion_desde_dict,
)
from app.core.services.seleccion_cartera import expresiones
from app.core.services.seleccion_cartera.recorrido import SeleccionPaginada
from app.core.services.seleccion_cartera.servicio import ConsultaCarteraService
from app.core.services.selecciones.servicio import SeleccionesService
from app.core.services.texto_enriquecido import catalogo, evaluador
from app.core.services.texto_enriquecido.evaluador import NodoEvaluado
from app.core.services.texto_enriquecido.serializacion import expresion_desde_dict

COLUMNA_DE_UNA_EXPRESION = "texto"

# Una fila de `ejemplos_por_segmento`: la etiqueta y la CLAVE del segmento que representa. La clave
# se informa aunque la definicion no tenga segmentacion (una expresion suelta): es lo que permite
# asociar la fila con su segmento.
Representado = tuple[str, str]


class ProductoNoEncontrado(Exception):
    def __init__(self, fecha_corte: date, pagare: str) -> None:
        super().__init__(f"El pagare {pagare!r} no esta en la cartera del {fecha_corte}")
        self.fecha_corte = fecha_corte
        self.pagare = pagare


# --- Catalogo -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class CatalogoTexto:
    contexto: ContextoTexto
    funciones: tuple[catalogo.FuncionCatalogo, ...]
    familias: tuple[str, ...]
    patrones_fecha: tuple[catalogo.PatronFecha, ...]
    marcas_fecha: tuple[catalogo.MarcaFecha, ...]
    limites: LimitesExpresion


# --- Validacion ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidacionTexto:
    """`tipo`, `cota` y `variables` solo existen si la expresion es valida; `sin_cota` explica por
    que no hay largo maximo cuando la expresion es valida y `cota` es None."""

    problemas: tuple[Problema, ...]
    tipo: TipoValor | None
    cota: int | None
    sin_cota: MotivoSinCota | None
    variables: tuple[str, ...]


# --- Previsualizacion ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MuestraEjemplo:
    pass


@dataclass(frozen=True)
class MuestraEjemplosPorSegmento:
    pass


@dataclass(frozen=True)
class MuestraProductoReal:
    fecha_corte: date
    pagare: str


MAXIMO_MUESTRA = 5  # los primeros N de una seleccion: lo bastante para ver, poco para esperar
MUESTRA_POR_DEFECTO = 5


@dataclass(frozen=True)
class MuestraPrimerosDeSeleccion:
    """Los primeros `cantidad` productos de una seleccion, en el orden y con el desempate de la
    carga. La seleccion es `filtros` y `orden` (la sintaxis de `/cartera`) o una guardada
    (`seleccion_id`), no las dos."""

    fecha_corte: date
    filtros: tuple[str, ...] = ()
    orden: str | None = None
    seleccion_id: int | None = None
    cantidad: int = MUESTRA_POR_DEFECTO


Muestra = (
    MuestraEjemplo | MuestraEjemplosPorSegmento | MuestraProductoReal | MuestraPrimerosDeSeleccion
)


@dataclass(frozen=True)
class ColumnaPrevia:
    nombre: str
    tipo: TipoSalida
    texto: str
    valor: Any
    nodos: tuple[NodoEvaluado, ...]
    cota: int | None
    sin_cota: MotivoSinCota | None
    usa_variante: bool
    problemas: tuple[Problema, ...]

    @property
    def largo(self) -> int:
        return len(self.texto)


@dataclass(frozen=True)
class FilaPrevia:
    numero: int
    etiqueta: str | None
    segmento: str | None  # la clave que representa la fila; si no, la que calcula la definicion
    excluida: FilaExcluida | None
    columnas: tuple[ColumnaPrevia, ...]


@dataclass(frozen=True)
class Previsualizacion:
    """O `problemas` (la expresion o la definicion no compila y no hay filas) o `filas`."""

    problemas: tuple[ProblemaDeDefinicion, ...]
    filas: tuple[FilaPrevia, ...]
    limite_largo: int | None
    umbral_advertencia: int | None
    disponibles: int | None = None  # el total de la seleccion, si la muestra es una seleccion


class PrevisualizacionTextoService:
    def __init__(
        self,
        contextos: RegistroContextos,
        cartera: ConsultaCarteraService | None = None,
        selecciones: SeleccionesService | None = None,
    ) -> None:
        self._contextos = contextos
        self._cartera = cartera
        self._selecciones = selecciones

    # --- catalogo ---

    def contextos_disponibles(self) -> tuple[ContextoTexto, ...]:
        return self._contextos.disponibles()

    def catalogo(self, contexto: str) -> CatalogoTexto:
        return CatalogoTexto(
            contexto=self._contextos.obtener(contexto),
            funciones=catalogo.catalogo_de_funciones(),
            familias=catalogo.familias(),
            patrones_fecha=catalogo.patrones_de_fecha(),
            marcas_fecha=catalogo.marcas_de_fecha(),
            limites=LIMITES,
        )

    # --- validacion ---

    def validar(self, contexto: str, expresion: Any) -> ValidacionTexto:
        tipos = self._contextos.obtener(contexto).tipos
        try:
            leida = expresion_desde_dict(expresion)
            compilada = evaluador.compilar(leida, tipos)
        except ExpresionInvalida as error:
            return ValidacionTexto(error.problemas, None, None, None, ())
        return ValidacionTexto(
            (), compilada.tipo, compilada.cota, compilada.motivo_sin_cota, compilada.variables
        )

    # --- previsualizacion ---

    def previsualizar(
        self,
        contexto: str,
        muestra: Muestra,
        expresion: Any = None,
        definicion: Any = None,
    ) -> Previsualizacion:
        """Una `expresion` o una `definicion` (la forma JSON de cada una), no las dos."""
        if (expresion is None) == (definicion is None):
            raise ValueError("Se pide la previsualizacion de una expresion o de una definicion")
        ctx = self._contextos.obtener(contexto)

        def sin_filas(problemas: tuple[ProblemaDeDefinicion, ...]) -> Previsualizacion:
            return Previsualizacion(problemas, (), ctx.limite_largo, ctx.umbral_advertencia)

        try:
            if expresion is not None:
                leida = DefinicionLeida(
                    DefinicionCarga(
                        "",
                        (
                            CampoSalida(
                                COLUMNA_DE_UNA_EXPRESION,
                                "",
                                TipoSalida.TEXTO,
                                expresion=expresion_desde_dict(expresion),
                            ),
                        ),
                    ),
                    (0,),
                )
            else:
                leida = definicion_desde_dict(definicion, ctx.tabla_rangos, ctx.variable_dias)
        except ExpresionInvalida as error:
            return sin_filas(tuple(ProblemaDeDefinicion(p) for p in error.problemas))
        except DefinicionIlegible as error:
            return sin_filas(error.problemas)
        definicion_leida = leida.definicion
        problemas = diagnosticar_leida(leida, ctx.tipos)
        if problemas:
            # Una expresion suelta no tiene columnas: sus problemas no llevan `columna`.
            if expresion is not None:
                problemas = tuple(replace(p, columna=None) for p in problemas)
            return sin_filas(problemas)

        generador = GeneradorCargas(definicion_leida, ctx.tipos)
        registros, disponibles = self._registros(ctx, definicion_leida, muestra)
        filas = tuple(
            self._fila(generador, numero, representado, registro)
            for numero, (representado, registro) in enumerate(registros, 1)
        )
        return Previsualizacion((), filas, ctx.limite_largo, ctx.umbral_advertencia, disponibles)

    @staticmethod
    def _fila(
        generador: GeneradorCargas,
        numero: int,
        representado: Representado | None,
        registro: Mapping[str, Any],
    ) -> FilaPrevia:
        detalle = generador.detallar_fila(registro, numero)
        etiqueta, clave = (None, None) if representado is None else representado
        return FilaPrevia(
            numero=numero,
            etiqueta=etiqueta,
            segmento=clave if clave is not None else detalle.segmento,
            excluida=detalle.exclusion,
            columnas=tuple(
                ColumnaPrevia(
                    nombre=celda.campo.nombre,
                    tipo=celda.campo.tipo,
                    texto=celda.texto,
                    valor=celda.valor,
                    nodos=celda.nodos,
                    cota=celda.cota,
                    sin_cota=celda.motivo_sin_cota,
                    usa_variante=celda.usa_variante,
                    problemas=celda.problemas,
                )
                for celda in detalle.celdas
            ),
        )

    # --- muestras ---

    def _registros(
        self, contexto: ContextoTexto, definicion: DefinicionCarga, muestra: Muestra
    ) -> tuple[list[tuple[Representado | None, dict[str, Any]]], int | None]:
        """Los registros de la muestra y, si es una seleccion, cuantos productos tiene."""
        if isinstance(muestra, MuestraProductoReal):
            return [(None, contexto.registro_de_producto(self._producto(muestra)))], None
        if isinstance(muestra, MuestraPrimerosDeSeleccion):
            productos, disponibles = self._primeros(muestra)
            return [(None, contexto.registro_de_producto(p)) for p in productos], disponibles
        if isinstance(muestra, MuestraEjemplosPorSegmento):
            return _ejemplos_por_segmento(contexto, definicion), None
        return [(None, dict(contexto.ejemplo))], None

    def _primeros(self, muestra: MuestraPrimerosDeSeleccion) -> tuple[list[Mapping[str, Any]], int]:
        """Los primeros productos de la seleccion, con el recorrido de la carga.

        `ConsultaInvalida` si un filtro o el orden no valen; `SeleccionNoEncontrada` si la
        guardada no existe; `SinVersionVigente` si la fecha no tiene sabana.
        """
        if self._cartera is None:
            raise RuntimeError("La previsualizacion con una seleccion necesita la cartera")
        filtros, orden = muestra.filtros, muestra.orden
        if muestra.seleccion_id is not None:
            if self._selecciones is None:
                raise RuntimeError("La previsualizacion con una seleccion guardada la necesita")
            datos = self._selecciones.obtener(muestra.seleccion_id).seleccion.datos
            filtros, orden = datos.filtros, datos.orden
        cantidad = min(max(muestra.cantidad, 1), MAXIMO_MUESTRA)
        recorrido = SeleccionPaginada(
            self._cartera,
            muestra.fecha_corte,
            [expresiones.parsear_filtro(crudo) for crudo in filtros],
            expresiones.parsear_orden(orden),
            cantidad,
        )
        return list(recorrido), recorrido.disponibles

    def _producto(self, muestra: MuestraProductoReal) -> Mapping[str, Any]:
        if self._cartera is None:
            raise RuntimeError("La previsualizacion con un producto real necesita la cartera")
        pagina = self._cartera.consultar(
            muestra.fecha_corte, [Filtro("pagare", Operador.IGUAL, (muestra.pagare,))], None, 1
        )
        if not pagina.filas:
            raise ProductoNoEncontrado(muestra.fecha_corte, muestra.pagare)
        return pagina.filas[0]


def _dias_de_ejemplo(rango: RangoDias) -> int:
    """Un valor de dias que cae en el rango: su inicio, o su fin si no tiene inicio."""
    if rango.desde is not None:
        return rango.desde
    return rango.hasta if rango.hasta is not None else 0


def _ejemplos_por_segmento(
    contexto: ContextoTexto, definicion: DefinicionCarga
) -> list[tuple[Representado | None, dict[str, Any]]]:
    criterio = (
        definicion.segmentacion.criterio
        if definicion.segmentacion is not None
        else CriterioCalculado(contexto.tabla_rangos, contexto.variable_dias)
    )
    filas: list[tuple[Representado | None, dict[str, Any]]] = []
    if isinstance(criterio, CriterioCalculado):
        for rango in criterio.tabla:
            registro = dict(contexto.ejemplo)
            if contexto.tipos.get(criterio.variable_dias) is TipoValor.NUMERO:
                registro[criterio.variable_dias] = _dias_de_ejemplo(rango)
            filas.append(((rango.etiqueta, rango.clave), registro))
        return filas
    claves = dict.fromkeys(v.segmento for c in definicion.campos for v in c.variantes)
    for clave in claves:
        registro = dict(contexto.ejemplo)
        registro[criterio.campo] = _valor_de_clave(clave, contexto.tipos.get(criterio.campo))
        filas.append(((clave, clave), registro))
    return filas


def _valor_de_clave(clave: str, tipo: TipoValor | None) -> Any:
    """El valor cuyo texto es la clave: el criterio por campo compara `str(valor)`."""
    if tipo is TipoValor.NUMERO and clave.lstrip("-").isdigit():
        return int(clave)
    return clave

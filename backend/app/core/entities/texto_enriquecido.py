"""Entidades del motor de texto enriquecido (RF-42 a RF-48).

Una expresion es un arbol de datos, no codigo: una secuencia de nodos `texto`
(literal, nunca se interpreta) y nodos `variable` (un campo o variable de
contexto mas una cadena de funciones). Las funciones se buscan por nombre en un
registro cerrado; nada del usuario se ejecuta (RF-48).

El diseno completo esta en docs/motor-texto-enriquecido.md.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

# Prefijo del enlace de WhatsApp por defecto. Vive en la entidad para que `enlace_whatsapp` y MOWA
# MES (`entities/mowa_mes.py` lo reexporta) tengan un solo dueno, sin que una entidad dependa de
# un servicio.
PREFIJO_WHATSAPP = "https://wa.me/+51"


class TipoValor(StrEnum):
    """Tipos de valor del motor. Los montos son `Decimal`, nunca `float`."""

    TEXTO = "texto"
    NUMERO = "numero"
    FECHA = "fecha"
    BOOLEANO = "booleano"
    NULO = "nulo"


class CodigoTexto(StrEnum):
    """Catalogo de codigos que el frontend traducira como `textoEnriquecido.codigo.<codigo>`.

    Un codigo por linea, con la forma `NOMBRE = "codigo"`: la prueba espejo del
    frontend lee esta clase. Los primeros se detectan al compilar (una expresion
    invalida no procesa ninguna fila); los siguientes, al evaluar una fila concreta; al final,
    los que solo informa la API del motor (B4a): lo que no se puede leer, el contexto o el
    producto que no existen, y por que una expresion no tiene largo maximo.
    """

    # Al compilar
    EXPRESION_INVALIDA = "expresion_invalida"  # la forma JSON es imposible (nodo, argumento)
    DEFINICION_INVALIDA = "definicion_invalida"  # columnas, variantes o segmentacion mal armadas
    SINTAXIS_INVALIDA = "sintaxis_invalida"
    REFERENCIA_VACIA = "referencia_vacia"
    VARIABLE_DESCONOCIDA = "variable_desconocida"
    FUNCION_DESCONOCIDA = "funcion_desconocida"
    PARAMETRO_INVALIDO = "parametro_invalido"
    TIPO_INCOMPATIBLE = "tipo_incompatible"
    LIMITE_EXCEDIDO = "limite_excedido"
    NO_SE_PUEDE_ESCRIBIR_COMO_TEXTO = "no_se_puede_escribir_como_texto"
    # Al evaluar una fila (`sin_segmento`: el producto no cae en ningun segmento y se excluye)
    SIN_SEGMENTO = "sin_segmento"
    VARIABLE_OBLIGATORIA_VACIA = "variable_obligatoria_vacia"
    ARGUMENTO_VACIO = "argumento_vacio"
    DIVISION_POR_CERO = "division_por_cero"
    NO_ES_NUMERO = "no_es_numero"
    NO_ES_FECHA = "no_es_fecha"
    TELEFONO_INVALIDO = "telefono_invalido"
    RESULTADO_FUERA_DE_RANGO = "resultado_fuera_de_rango"
    VALOR_NO_CONVERTIBLE = "valor_no_convertible"  # el texto no cabe en el tipo de la columna
    # Solo la API del motor
    SIN_COTA_VARIABLE = "sin_cota_variable"  # el largo de una variable depende del dato
    SIN_COTA_FUNCION = "sin_cota_funcion"  # una funcion no puede acotar el largo
    CONTEXTO_DESCONOCIDO = "contexto_desconocido"
    PRODUCTO_NO_ENCONTRADO = "producto_no_encontrado"
    SIN_VERSION_VIGENTE = "sin_version_vigente"


@dataclass(frozen=True)
class Problema:
    """Un problema con su ubicacion: que nodo, que funcion de la cadena y que parametro.

    `nodo` y `funcion` son posiciones que cuentan desde 0; `parametro` es el
    nombre del parametro de la funcion (`n`, `patron`...), como lo espera el
    frontend. Con `nodo` en None el problema es de toda la expresion y no tiene
    ubicacion. `nombre` es la variable o la funcion involucrada, para que el
    mensaje pueda nombrarla.
    """

    codigo: CodigoTexto
    detalle: str
    nodo: int | None = None
    funcion: int | None = None
    parametro: str | None = None
    nombre: str | None = None


@dataclass(frozen=True)
class MotivoSinCota:
    """Por que una expresion no tiene largo maximo: una variable cuyo largo depende del dato
    (`sin_cota_variable`) o una funcion que no puede acotarlo (`sin_cota_funcion`)."""

    codigo: CodigoTexto
    detalle: str
    nodo: int
    funcion: int | None = None


@dataclass(frozen=True)
class ArgumentoVariable:
    """Un argumento que toma su valor de otra variable, por ejemplo `{"variable": "dias"}`."""

    nombre: str


Argumento = int | Decimal | str | ArgumentoVariable


@dataclass(frozen=True)
class LlamadaFuncion:
    nombre: str
    args: tuple[Argumento, ...] = ()


@dataclass(frozen=True)
class NodoTexto:
    """Texto literal: UTF-8, con saltos de linea si hace falta. Un `[@` aqui es texto."""

    valor: str


@dataclass(frozen=True)
class NodoVariable:
    """Una variable y las funciones que se le aplican, en orden.

    `obligatoria`: si la variable llega vacia, la fila lleva el problema
    `variable_obligatoria_vacia`; el modulo consumidor decide que hacer (4.3).
    """

    nombre: str
    funciones: tuple[LlamadaFuncion, ...] = ()
    obligatoria: bool = False


Nodo = NodoTexto | NodoVariable


@dataclass(frozen=True)
class Expresion:
    nodos: tuple[Nodo, ...] = ()


@dataclass(frozen=True)
class LimitesExpresion:
    """Topes de tamano que se validan al compilar (RF-48)."""

    nodos: int = 200
    funciones_por_nodo: int = 10
    argumentos_por_funcion: int = 8
    largo_literal: int = 5000


LIMITES = LimitesExpresion()


class ExpresionInvalida(Exception):
    """La expresion no se puede compilar. `problemas` dice donde esta cada falla."""

    def __init__(self, problemas: tuple[Problema, ...]) -> None:
        super().__init__("; ".join(f"{p.codigo.value}: {p.detalle}" for p in problemas))
        self.problemas = problemas


class ExpresionNoEscribible(Exception):
    """La expresion no tiene forma de texto `[@...]`; se informa, no se deforma (D9)."""

    def __init__(self, problema: Problema) -> None:
        super().__init__(problema.detalle)
        self.problema = problema

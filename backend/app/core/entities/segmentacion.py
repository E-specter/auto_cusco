"""Segmentacion compartida de las columnas (RF-50, docs/motor-texto-enriquecido.md seccion 7).

Una definicion de carga puede declarar un contenido distinto por segmento. El segmento de cada
producto sale de un criterio, que es un dato de la definicion y no una regla del motor:

- `CriterioCalculado` (el de por defecto): los dias de atraso contra una tabla de rangos con
  etiquetas. Es el de por defecto porque el campo `segmento_financiero` de la sabana llega mal
  cargado (decision del usuario, 2026-09-29).
- `CriterioCampo`: el valor de un campo de la cartera, tal cual.

La tabla de rangos son datos: la de MOWA MES (RF-MM-15, con S-MM-6) es la tabla por defecto y
MOWA MES arma su `RANGOS_SEGMENTO` desde ella, asi que hay una sola. La clave de cada rango es un
texto: el enum `Segmento` es de MOWA MES.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class ConLimitesDeDias(Protocol):
    """Cualquier rango con `desde` y `hasta`: el de MOWA MES (con su enum) tambien lo cumple."""

    desde: int | None
    hasta: int | None


@dataclass(frozen=True)
class RangoDias:
    """Dias que cubre un segmento. `None` en un extremo es sin limite en ese lado."""

    clave: str
    etiqueta: str
    desde: int | None
    hasta: int | None


# RF-MM-15, con S-MM-6 (0 dias es Preventiva; mas de 120 queda sin segmento).
#
# CUIDADO: MOWA MES consume esta tabla tal cual (`RANGOS_SEGMENTO` en entities/mowa_mes.py se
# arma desde ella). Cambiarla (un rango "121 o mas", otra etiqueta u otra clave) es cambiar la
# regla de negocio RF-MM-15 sin tocar un archivo del modulo, y una clave nueva haria fallar
# `Segmento(clave)` al importar y tumbaria la aplicacion. Otro canal define SU PROPIA tabla
# (`CriterioCalculado(tabla=...)`) y no edita este valor por defecto. Lo guardan
# `test_mowa_mes_rangos_nucleo.py` y `test_segmentacion.py`.
TABLA_RANGOS_POR_DEFECTO: tuple[RangoDias, ...] = (
    RangoDias("preventiva", "Preventiva", None, 0),
    RangoDias("1_a_8", "1 a 8", 1, 8),
    RangoDias("9_a_30", "9 a 30", 9, 30),
    RangoDias("31_a_60", "31 a 60", 31, 60),
    RangoDias("61_a_90", "61 a 90", 61, 90),
    RangoDias("91_a_120", "91 a 120", 91, 120),
)

# El nucleo segmenta por defecto sobre los dias de la sabana, sin ajuste. Las definiciones NUEVAS de
# la cartera nombran `VARIABLE_DIAS_AJUSTADOS` (RF-55): lo resuelve el contexto al guardar, y una
# version ya guardada conserva la variable que guardo.
VARIABLE_DIAS_POR_DEFECTO = "dias_atraso"
VARIABLE_DIAS_AJUSTADOS = "dias_atraso_ajustados"


@dataclass(frozen=True)
class CriterioCalculado:
    """Segmento financiero calculado: los dias de la variable `variable_dias` contra la tabla.

    Un modulo con fecha de envio aporta una variable ya ajustada (`dias_atraso_ajustados`) y la
    nombra aqui; sin ella se usa `dias_atraso`, sin ajuste.
    """

    tabla: tuple[RangoDias, ...] = TABLA_RANGOS_POR_DEFECTO
    variable_dias: str = VARIABLE_DIAS_POR_DEFECTO


@dataclass(frozen=True)
class CriterioCampo:
    """El valor de un campo de la cartera, tal cual, es el segmento."""

    campo: str


class PoliticaSinSegmento(StrEnum):
    """Que hace la definicion con un producto que no cae en ningun segmento."""

    EXCLUIR = "excluir"  # la fila no sale y se informa con el motivo `sin_segmento`
    USAR_POR_DEFECTO = "usar_por_defecto"  # sale con el contenido por defecto de cada columna


@dataclass(frozen=True)
class Segmentacion:
    criterio: CriterioCalculado | CriterioCampo = field(default_factory=CriterioCalculado)
    politica: PoliticaSinSegmento = PoliticaSinSegmento.EXCLUIR


class SegmentacionInvalida(Exception):
    """La segmentacion o la tabla de rangos estan mal armadas."""

"""Costo de las campanas y nombre de sus archivos (RF-MM-23, RF-MM-24, RF-MM-25).

Todo monto es `Decimal`, nunca `float`: el valor exacto es el que se guarda y el
redondeo a dos decimales es solo de presentacion.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

EXTENSION_ARCHIVO = ".xlsx"
LARGO_MAXIMO_NOMBRE_ARCHIVO = 120  # RF-MM-25, sin la extension


class EstadoCosto(StrEnum):
    """Por que un costo trae o no un valor; distingue "pendiente" y "sin tarifa" de cero."""

    CALCULADO = "calculado"
    PENDIENTE = "pendiente"  # costo real sin reporte de enviados importado (RF-MM-24)
    NO_DISPONIBLE = "no_disponible"  # campana sin tarifa guardada (RF-MM-23)


class EstadoCostoEstimado(StrEnum):
    """El costo estimado de una campana: con valor, o no disponible porque no tiene tarifa."""

    CALCULADO = "calculado"
    NO_DISPONIBLE = "no_disponible"


@dataclass(frozen=True)
class CostoReal:
    estado: EstadoCosto
    valor: Decimal | None  # solo con estado CALCULADO


@dataclass(frozen=True)
class CostoMes:
    """Costo estimado de las campanas imputadas a un mes, con la regla del limite (RF-MM-24)."""

    costo: Decimal  # suma de valores exactos; solo las campanas con tarifa guardada
    campanas_sin_tarifa: int  # las que quedaron fuera del total (D-2)


@dataclass(frozen=True)
class VariablePlantilla:
    nombre: str
    descripcion: str


# RF-MM-25, en el orden de la tabla del requerimiento. Es el catalogo de variables
# validas: la respuesta de configuracion la expone para que el frontend no la copie.
VARIABLES_PLANTILLA: tuple[VariablePlantilla, ...] = (
    VariablePlantilla("campana", "Numero de la campana en el sistema"),
    VariablePlantilla("descripcion", "Descripcion de la campana"),
    VariablePlantilla("fecha_envio", "Fecha de envio, en formato AAAA-MM-DD"),
    VariablePlantilla("fecha_corte", "Fecha de corte de la sabana, en formato AAAA-MM-DD"),
    VariablePlantilla("archivo", "Numero del archivo dentro de la campana (1, 2, ...)"),
    VariablePlantilla("total", "Cantidad de archivos de la campana"),
    VariablePlantilla("cantidad", "Filas de ese archivo, incluida la supervision si va en el"),
)


class PlantillaInvalida(Exception):
    """La plantilla usa una variable que no existe o tiene una llave sin cerrar."""


class TarifaInvalida(Exception):
    """La tarifa no es un decimal mayor o igual a 0 con hasta 4 decimales."""

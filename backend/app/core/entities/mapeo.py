"""Entidades del motor de reglas de mapeo y expresion de campos (RF-12).

Es un modulo compartido: las cargas para plataformas digitales (Fase 3) y las
de VoIP (Fase 4) usan el mismo motor con reglas propias por plataforma, en vez
de reimplementarlo cada una (ver docs/modules.md, modulo 4).

Una definicion de carga describe, campo por campo del archivo de salida, como
se construye su valor a partir de los campos del producto.
"""

from dataclasses import dataclass, field
from enum import StrEnum


class TipoSalida(StrEnum):
    """Tipado explicito de cada campo generado (RF-12)."""

    TEXTO = "texto"
    NUMERO = "numero"
    FECHA = "fecha"
    FINANCIERO = "financiero"


@dataclass(frozen=True)
class FormatoFinanciero:
    """Separadores configurables de un importe, por ejemplo 1,234.56."""

    separador_miles: str = ","
    separador_decimal: str = "."
    decimales: int = 2


@dataclass(frozen=True)
class CampoSalida:
    """Un campo del archivo de carga.

    `plantilla` es texto con referencias a campos del producto entre `[@...]`:

        "1010"                        valor fijo
        "[@telefono]"                 copia directa
        "51[@telefono]"               prefijo mas campo
        "documento=[@documento_numero]"   concatenacion

    `formato_fecha` usa la notacion de strftime, por ejemplo "%d/%m/%Y". Si un
    campo de fecha no lo trae, el valor sale como fecha nativa.
    """

    nombre: str
    plantilla: str
    tipo: TipoSalida = TipoSalida.TEXTO
    formato_fecha: str | None = None
    formato_financiero: FormatoFinanciero = field(default_factory=FormatoFinanciero)


@dataclass(frozen=True)
class DefinicionCarga:
    """Reglas completas de una carga: que columnas tiene y como se llena cada una.

    Es configuracion, no codigo (RF-32): se guarda, se edita y se reutiliza sin
    tocar el sistema.
    """

    nombre: str
    campos: tuple[CampoSalida, ...]


class PlantillaInvalida(Exception):
    """La plantilla esta mal escrita o nombra un campo que no existe."""


class ValorNoGenerable(Exception):
    """Un producto concreto no puede producir el valor pedido para un campo."""

    def __init__(self, campo: str, detalle: str) -> None:
        super().__init__(f"{campo}: {detalle}")
        self.campo = campo
        self.detalle = detalle


@dataclass(frozen=True)
class ErrorGeneracion:
    """Un campo que no se pudo generar para un producto concreto."""

    fila: int
    campo: str
    detalle: str

"""Entidades del motor de reglas de mapeo y expresion de campos (RF-12).

Es un modulo compartido: las cargas para plataformas digitales (Fase 3) y las
de VoIP (Fase 4) usan el mismo motor con reglas propias por plataforma, en vez
de reimplementarlo cada una (ver docs/modules.md, modulo 4).

Una definicion de carga describe, campo por campo del archivo de salida, como
se construye su valor a partir de los campos del producto.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from app.core.entities.segmentacion import Segmentacion
from app.core.entities.texto_enriquecido import Expresion


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
class VarianteCampo:
    """El contenido de una columna para un segmento (RF-50).

    `segmento` es la clave del segmento: un rango de la tabla (criterio calculado) o el valor de
    un campo (criterio por campo). El contenido es una `plantilla` o una `expresion`, no ambas.
    """

    segmento: str
    plantilla: str | None = None
    expresion: Expresion | None = None


@dataclass(frozen=True)
class CampoSalida:
    """Un campo del archivo de carga.

    `plantilla` es texto con referencias a campos del producto entre `[@...]`:

        "1010"                        valor fijo
        "[@telefono]"                 copia directa
        "51[@telefono]"               prefijo mas campo
        "documento=[@documento_numero]"   concatenacion

    `formato_fecha` usa la notacion de strftime, por ejemplo "%d/%m/%Y". Si un
    campo de fecha no lo trae, el valor sale como fecha nativa. `patron_fecha` es lo mismo con las
    marcas legibles del motor (`dd/mm/aaaa`, con `nombre_mes` en espanol): es lo que guardan las
    definiciones (C-3) y manda sobre `formato_fecha`.

    Columnas dinamicas (RF-49, RF-50), todo opcional:

    - `expresion`: el contenido como expresion del motor de texto enriquecido; si esta, manda
      sobre `plantilla` (que entonces se ignora). La plantilla tambien admite funciones en
      cadena: `[@titular | primeros(8)]`.
    - `valor_por_defecto`: lo que sale cuando todo el resultado queda vacio. Pasa por el tipo
      de la columna.
    - `variantes`: un contenido por segmento; el de la columna (`expresion` o `plantilla`) es el
      contenido por defecto. Necesitan `DefinicionCarga.segmentacion`.
    """

    nombre: str
    plantilla: str
    tipo: TipoSalida = TipoSalida.TEXTO
    formato_fecha: str | None = None
    patron_fecha: str | None = None
    formato_financiero: FormatoFinanciero = field(default_factory=FormatoFinanciero)
    expresion: Expresion | None = None
    valor_por_defecto: str | None = None
    variantes: tuple[VarianteCampo, ...] = ()


@dataclass(frozen=True)
class DefinicionCarga:
    """Reglas completas de una carga: que columnas tiene y como se llena cada una.

    Es configuracion, no codigo (RF-32): se guarda, se edita y se reutiliza sin
    tocar el sistema.
    """

    nombre: str
    campos: tuple[CampoSalida, ...]
    segmentacion: Segmentacion | None = None
    proteger_formulas: bool = True  # RF-53: lo aplica el exportador, no el generador


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
    codigo: str | None = None  # `CodigoTexto` cuando lo informa el motor de texto enriquecido


@dataclass(frozen=True)
class FilaExcluida:
    """Un producto que no sale en la carga: no cae en ningun segmento y la definicion excluye.

    `fila` es la posicion del producto en la seleccion (desde 1) y `pagare`, el del producto, para
    que quien lee el motivo pueda ubicarlo (el pagare ya viaja en la cartera).
    """

    fila: int
    codigo: str
    detalle: str
    pagare: str | None = None

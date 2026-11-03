"""Entidades de la campana de WhatsMKT ya creada (RF-WM-23, RF-WM-35, RF-WM-36, T-WM-B4b1).

Una campana guarda TODO lo que uso, congelado: cambiar despues la configuracion, la definicion o el
mensaje no la toca. `CampanaNueva` es lo que se inserta; `CampanaWhatsmkt`, lo que se lee.
"""

from dataclasses import dataclass
from datetime import date, datetime, time
from enum import StrEnum

from app.core.entities.whatsmkt import ModoCampana, TipoEnvio
from app.core.services.plataformas.whatsmkt.archivo_contactos import ExclusionContacto


@dataclass(frozen=True)
class HorarioElegido:
    """Una franja de envio con sus horas tal como estaban al crear (RF-WM-07)."""

    nombre: str  # horario_1 u horario_2
    inicio: time
    fin: time


@dataclass(frozen=True)
class FilaNueva:
    """Una fila del archivo: los supervisores primero (sin pagare) y luego los productos."""

    posicion: int
    numero: str
    pagare: str | None
    supervision: bool
    macros: tuple[str | None, ...]


@dataclass(frozen=True)
class CampanaNueva:
    nombre: str
    segmento: str | None
    segmento_etiqueta: str | None
    definicion_id: int
    definicion_nombre: str
    definicion_version: int
    texto_guardado_id: int
    texto_version: int
    mensaje_texto: str
    whatsapp_contacto: str | None
    fecha_corte: date
    filtros: tuple[str, ...]
    orden: str | None
    cantidad_pedida: int
    fecha_envio: date
    horarios: tuple[HorarioElegido, ...]
    lo_antes_posible: bool
    tipo_envio: TipoEnvio
    foto_id: int | None
    adjunto_id: int | None
    etiqueta_vcard: str | None
    cantidad: int
    productos: int
    supervisores: tuple[str, ...]
    archivo_nombre: str
    archivo_contenido: bytes
    filas: tuple[FilaNueva, ...]
    exclusiones: tuple[ExclusionContacto, ...]


@dataclass(frozen=True)
class LoteNuevo:
    modo: ModoCampana
    campanas: tuple[CampanaNueva, ...]
    # Los que quedan fuera de todas las campanas del lote (campana_id nulo).
    exclusiones_sin_campana: tuple[ExclusionContacto, ...]


@dataclass(frozen=True)
class CampanaWhatsmkt:
    """Una campana tal como esta guardada."""

    id: int
    lote_id: int
    nombre: str
    segmento: str | None
    segmento_etiqueta: str | None
    definicion_id: int | None
    definicion_nombre: str
    definicion_version: int
    texto_guardado_id: int | None
    texto_version: int
    mensaje_texto: str
    whatsapp_contacto: str | None
    fecha_corte: date
    filtros: tuple[str, ...]
    orden: str | None
    cantidad_pedida: int
    fecha_envio: date
    horarios: tuple[HorarioElegido, ...]
    lo_antes_posible: bool
    tipo_envio: TipoEnvio
    foto_id: int | None
    adjunto_id: int | None
    etiqueta_vcard: str | None
    cantidad: int
    productos: int
    supervisores: tuple[str, ...]
    creado_en: datetime
    descartada_en: datetime | None
    archivo_nombre: str
    archivo_tamano: int
    # Si ya tiene el informe de WhatsMKT importado (RF-WM-40: las otras estan pendientes).
    con_informe: bool = False


@dataclass(frozen=True)
class LoteCreado:
    lote_id: int
    modo: ModoCampana
    campanas: tuple[CampanaWhatsmkt, ...]


class EstadoCampana(StrEnum):
    ACTIVAS = "activas"
    DESCARTADAS = "descartadas"


@dataclass(frozen=True)
class PaginaCampanas:
    total: int  # de todas las que cumplen los filtros, no solo de esta pagina
    campanas: tuple[CampanaWhatsmkt, ...]
    # De TODAS las campanas, sin los filtros: para los contadores de las dos vistas y la
    # linea de pendientes (las activas que no tienen informe).
    total_activas: int = 0
    total_descartadas: int = 0
    total_pendientes: int = 0


@dataclass(frozen=True)
class PaginaExclusiones:
    total: int
    exclusiones: tuple[ExclusionContacto, ...]


@dataclass(frozen=True)
class ArchivoGuardado:
    nombre: str
    contenido: bytes


class CampanaNoEncontrada(Exception):
    def __init__(self, campana_id: int) -> None:
        super().__init__(f"No existe la campana {campana_id}")
        self.campana_id = campana_id


class CampanaDescartada(Exception):
    """RF-WM-37: no se importa un informe en una campana descartada; hay que restaurarla."""

    def __init__(self, campana_id: int) -> None:
        super().__init__(f"La campana {campana_id} esta descartada: restaurala primero")
        self.campana_id = campana_id


class CampanaNoDescartada(Exception):
    """RF-WM-42: solo se elimina del todo una campana descartada."""

    def __init__(self, campana_id: int) -> None:
        super().__init__(f"La campana {campana_id} esta activa: descartala antes de eliminarla")
        self.campana_id = campana_id


class InformeYaImportado(Exception):
    """RF-WM-38: la campana ya tiene un informe y no se pidio reemplazarlo."""

    def __init__(self, campana_id: int) -> None:
        super().__init__(f"La campana {campana_id} ya tiene un informe; confirma para reemplazarlo")
        self.campana_id = campana_id

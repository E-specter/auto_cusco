"""Selecciones de cartera guardadas y compartidas (pedido de la pantalla de seleccion).

Una seleccion es lo que el analista armo para elegir productos: filtros, orden,
cantidad e indicadores. No lleva fecha de corte: se reutiliza otro dia sobre
otra sabana. Sin usuarios (decision C-3), cualquiera puede editarla o borrarla.

Se guarda en la misma sintaxis de texto que usa la API, asi que puede dejar de
aplicar si cambia el catalogo de campos. Por eso al cargarla no se rechaza: se
devuelve marcando que parte ya no aplica. Ver docs/selecciones-guardadas.md.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

LARGO_MAXIMO_NOMBRE = 120


class ParteSeleccion(StrEnum):
    NOMBRE = "nombre"
    FILTRO = "filtro"
    ORDEN = "orden"
    CANTIDAD = "cantidad"
    INDICADOR = "indicador"


@dataclass(frozen=True)
class DatosSeleccion:
    """Lo que escribe el usuario, en la sintaxis de la API."""

    nombre: str
    filtros: tuple[str, ...] = ()
    orden: str | None = None
    cantidad: int | None = None
    indicadores: tuple[str, ...] = ()


@dataclass(frozen=True)
class SeleccionGuardada:
    id: int
    datos: DatosSeleccion
    creado_en: datetime
    actualizado_en: datetime


@dataclass(frozen=True)
class ProblemaSeleccion:
    """Una parte de la seleccion que no aplica sobre el catalogo actual."""

    parte: ParteSeleccion
    expresion: str
    detalle: str


@dataclass(frozen=True)
class SeleccionRevisada:
    """Una seleccion guardada junto con lo que ya no aplica de ella."""

    seleccion: SeleccionGuardada
    problemas: tuple[ProblemaSeleccion, ...]

    @property
    def aplicable(self) -> bool:
        return not self.problemas


class SeleccionNoEncontrada(Exception):
    def __init__(self, seleccion_id: int) -> None:
        super().__init__(f"No existe la seleccion {seleccion_id}")
        self.seleccion_id = seleccion_id


class SeleccionInvalida(Exception):
    """Se intento guardar una seleccion con partes que no aplican."""

    def __init__(self, problemas: tuple[ProblemaSeleccion, ...]) -> None:
        resumen = "; ".join(f"{p.parte.value} {p.expresion!r}: {p.detalle}" for p in problemas)
        super().__init__(f"La seleccion no se puede guardar. {resumen}")
        self.problemas = problemas


class NombreDeSeleccionRepetido(Exception):
    def __init__(self, nombre: str) -> None:
        super().__init__(f"Ya existe una seleccion llamada {nombre!r}")
        self.nombre = nombre

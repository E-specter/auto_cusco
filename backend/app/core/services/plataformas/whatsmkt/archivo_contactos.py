"""Armado del archivo de contactos de WhatsMKT (RF-WM-13 a RF-WM-16).

Lo hace el mismo generador que «Generar carga» (RF-12, `GeneracionCargasService`), sin un armado
propio del modulo: aqui solo se agrega lo que es de WhatsMKT.

- Una fila por producto (RF-WM-13): un telefono con dos productos sale dos veces.
- Exclusiones, con UN solo codigo por producto y en este orden (RF-WM-15): `sin_telefono`,
  `telefono_invalido` (RF-02) y `macro_vacia` (una macro que queda vacia en una columna sin valor
  por defecto; con valor por defecto el generador ya lo uso).
- Los supervisores van primero (RF-WM-14): `número` es `51` mas el numero del supervisor y las
  macros copian las de la primera fila de productos DEL ARCHIVO (RF-40).
- En un lote por segmento (RF-WM-23) sale un archivo por segmento con productos, segun los dias de
  atraso ajustados a la fecha de envio (RF-55) y la tabla de segmentos de B1.

Para saber el telefono, el pagare y los dias de cada fila el generador recibe tres columnas
auxiliares que se quitan de la salida: asi el producto se evalua una sola vez y con las mismas
reglas que cualquier carga.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.entities.cartera import Filtro, Orden
from app.core.entities.exportacion import Tabla
from app.core.entities.gestiones_digitales import Supervisor
from app.core.entities.mapeo import CampoSalida, DefinicionCarga, ErrorGeneracion, FilaExcluida
from app.core.entities.telefono import numero_valido
from app.core.entities.valores import vacia
from app.core.entities.whatsmkt import CodigoWhatsmkt, SegmentoWhatsmkt
from app.core.services.fecha_envio import DIAS_AJUSTADOS
from app.core.services.generacion_cargas.servicio import (
    CANTIDAD_POR_DEFECTO,
    GeneracionCargasService,
)
from app.core.services.gestiones_digitales import supervision
from app.core.services.plataformas.whatsmkt.plataforma import PREFIJO_PAIS
from app.core.services.plataformas.whatsmkt.segmentos import segmento_de

# Columnas auxiliares: no salen en el archivo. Nombres que ninguna definicion usaria.
_TELEFONO, _PAGARE, _DIAS = "__whatsmkt_telefono", "__whatsmkt_pagare", "__whatsmkt_dias"
_AUXILIARES = (
    CampoSalida(nombre=_TELEFONO, plantilla="[@telefono]"),
    CampoSalida(nombre=_PAGARE, plantilla="[@pagare]"),
    CampoSalida(nombre=_DIAS, plantilla=f"[@{DIAS_AJUSTADOS}]"),
)


@dataclass(frozen=True)
class SeleccionCampana:
    """La seleccion de la campana tal como se guardo: lo mismo que pide «Generar carga»."""

    fecha_corte: date
    fecha_envio: date | None = None  # sin ella, hoy en Lima (RF-55)
    filtros: Sequence[Filtro] = ()
    orden: Orden | None = None
    cantidad: int = CANTIDAD_POR_DEFECTO


@dataclass(frozen=True)
class ExclusionContacto:
    """Un producto que no sale en el archivo, con su unico codigo (RF-WM-15).

    `fila` es la posicion del producto entre los que genero la seleccion (desde 1). Para
    `macro_vacia`, `macro` es su numero (1 es la segunda columna) y `etiqueta`, la de la columna.
    """

    fila: int
    pagare: str | None
    codigo: CodigoWhatsmkt
    detalle: str
    macro: int | None = None
    etiqueta: str | None = None
    # El segmento al que pertenece el producto (solo en un lote por segmento; None si no tiene).
    segmento: str | None = None


@dataclass(frozen=True)
class SinSegmento:
    """Un producto sin dias de atraso: no cae en ningun segmento (RF-WM-20 los supone siempre).

    No es una exclusion de las del catalogo (no hay codigo para ella): lo decide la campana.
    """

    fila: int
    pagare: str | None


@dataclass(frozen=True)
class ArchivoContactos:
    """Un archivo listo para escribir: los supervisores primero y luego los productos.

    `segmento` es la clave del segmento (None en una campana global). `cantidad` son las filas del
    archivo, supervisores incluidos: es la que WhatsMKT pide declarar (S-WM-4).
    """

    segmento: str | None
    tabla: Tabla
    productos: int
    supervisores: int
    columnas_texto: frozenset[str]
    # El pagare de cada producto, en el orden de las filas de productos (las que vienen despues
    # de los supervisores): lo que concilia el informe (RF-WM-39).
    pagares: tuple[str | None, ...] = ()

    @property
    def cantidad(self) -> int:
        return self.tabla.cantidad


@dataclass(frozen=True)
class ResultadoContactos:
    archivos: tuple[ArchivoContactos, ...]
    exclusiones: tuple[ExclusionContacto, ...]
    sin_segmento: tuple[SinSegmento, ...]
    errores: tuple[ErrorGeneracion, ...]
    exclusiones_de_la_definicion: tuple[FilaExcluida, ...]
    disponibles: int
    solicitados: int
    fecha_envio: date


def _con_auxiliares(definicion: DefinicionCarga) -> DefinicionCarga:
    usados = {c.nombre for c in definicion.campos} & {c.nombre for c in _AUXILIARES}
    if usados:
        raise ValueError(f"La definicion usa nombres reservados: {sorted(usados)}")
    return replace(definicion, campos=(*definicion.campos, *_AUXILIARES))


def _dias(texto: Any) -> int | None:
    if vacia(texto):
        return None
    try:
        return int(Decimal(str(texto).strip()))
    except (InvalidOperation, ValueError):
        return None


class ArchivoContactosService:
    def __init__(self, generacion: GeneracionCargasService) -> None:
        self._generacion = generacion

    def armar(
        self,
        seleccion: SeleccionCampana,
        definicion: DefinicionCarga,
        segmentos: Sequence[SegmentoWhatsmkt],
        supervisores: Sequence[Supervisor],
        procedencias: Sequence[str],
        por_segmento: bool = False,
    ) -> ResultadoContactos:
        """Los archivos de la campana: uno (global) o uno por segmento con productos."""
        if not definicion.campos:
            raise ValueError("La definicion no tiene columnas")
        generado = self._generacion.generar(
            seleccion.fecha_corte,
            _con_auxiliares(definicion),
            seleccion.filtros,
            seleccion.orden,
            seleccion.cantidad,
            seleccion.fecha_envio,
        )
        cabeceras = tuple(c.nombre for c in definicion.campos)
        exclusiones: list[ExclusionContacto] = []
        sin_segmento: list[SinSegmento] = []
        por_clave: dict[str | None, list[dict[str, Any]]] = {}
        pagares: dict[str | None, list[str | None]] = {}
        for posicion, fila in enumerate(generado.tabla.filas, 1):
            pagare = None if vacia(fila[_PAGARE]) else str(fila[_PAGARE])
            segmento = segmento_de(_dias(fila[_DIAS]), segmentos) if por_segmento else None
            clave = None if segmento is None else segmento.clave
            exclusion = _exclusion(posicion, pagare, fila, definicion)
            if exclusion is not None:
                exclusiones.append(replace(exclusion, segmento=clave))
                continue
            if por_segmento and segmento is None:
                sin_segmento.append(SinSegmento(posicion, pagare))
                continue
            por_clave.setdefault(clave, []).append({c: fila[c] for c in cabeceras})
            pagares.setdefault(clave, []).append(pagare)
        return ResultadoContactos(
            archivos=tuple(
                self._archivo(
                    clave, por_clave[clave], pagares[clave], definicion, supervisores, procedencias
                )
                for clave in _en_orden(por_clave, segmentos)
            ),
            exclusiones=tuple(exclusiones),
            sin_segmento=tuple(sin_segmento),
            errores=generado.errores,
            exclusiones_de_la_definicion=generado.exclusiones,
            disponibles=generado.disponibles,
            solicitados=generado.solicitados,
            fecha_envio=generado.fecha_envio,
        )

    @staticmethod
    def _archivo(
        clave: str | None,
        productos: list[dict[str, Any]],
        pagares: list[str | None],
        definicion: DefinicionCarga,
        supervisores: Sequence[Supervisor],
        procedencias: Sequence[str],
    ) -> ArchivoContactos:
        columna_numero = definicion.campos[0].nombre
        primera = productos[0]
        # RF-37: las procedencias dan el orden; el DNI no real de RF-39 no existe en WhatsMKT.
        ordenados = [s for s, _ in supervision.documentos_asignados(supervisores, procedencias)]
        filas_supervision = [
            {**primera, columna_numero: f"{PREFIJO_PAIS}{s.numero}"} for s in ordenados
        ]
        return ArchivoContactos(
            segmento=clave,
            tabla=Tabla(
                nombre=definicion.nombre,
                cabeceras=tuple(c.nombre for c in definicion.campos),
                filas=(*filas_supervision, *productos),
            ),
            productos=len(productos),
            supervisores=len(filas_supervision),
            # RF-73: `número` va SIEMPRE en celda de texto, diga lo que diga la definicion guardada
            # (una definicion guardada por la API podria venir sin `celda_texto`).
            columnas_texto=definicion.columnas_texto | {columna_numero},
            pagares=tuple(pagares),
        )


def _en_orden(
    por_clave: Mapping[str | None, Any], segmentos: Sequence[SegmentoWhatsmkt]
) -> Iterable[str | None]:
    """Los archivos en el orden de los segmentos (de menor a mayor); el global es uno solo."""
    if None in por_clave:
        return [None]
    return [s.clave for s in sorted(segmentos, key=lambda s: s.orden) if s.clave in por_clave]


def _exclusion(
    fila: int, pagare: str | None, celdas: Mapping[str, Any], definicion: DefinicionCarga
) -> ExclusionContacto | None:
    """El PRIMER motivo que falla, en el orden del catalogo: telefono, telefono invalido, macro."""
    telefono = celdas[_TELEFONO]
    if vacia(telefono):
        return ExclusionContacto(
            fila, pagare, CodigoWhatsmkt.SIN_TELEFONO, "El producto no tiene telefono"
        )
    if not numero_valido(str(telefono)):
        return ExclusionContacto(
            fila,
            pagare,
            CodigoWhatsmkt.TELEFONO_INVALIDO,
            "El telefono debe tener 9 digitos y empezar con 9",
        )
    # La columna 1 es `número`; desde la 2 cada una es una macro, por posicion (RF-WM-11).
    for macro, campo in enumerate(definicion.campos[1:], 1):
        if campo.valor_por_defecto is None and vacia(celdas[campo.nombre]):
            etiqueta = campo.etiqueta or campo.nombre
            detalle = f"La macro {macro} ({etiqueta}) queda vacia y su columna no tiene valor "
            return ExclusionContacto(
                fila,
                pagare,
                CodigoWhatsmkt.MACRO_VACIA,
                detalle + "por defecto",
                macro=macro,
                etiqueta=etiqueta,
            )
    return None

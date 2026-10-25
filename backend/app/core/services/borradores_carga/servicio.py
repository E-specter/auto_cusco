"""Caso de uso: borradores de carga del mapeador de encabezados (RF-57 a RF-60).

Diseno en docs/mapeador-encabezados.md, seccion 5.

Subir un archivo lo lee, lo analiza contra el catalogo del consumidor (con lo recordado) y lo deja
en un borrador. El usuario puede volver a analizarlo con otra hoja, separador o codificacion,
validar sus asignaciones contra el analisis que vio y descartarlo. Confirmarlo es del consumidor
(la ingesta de la sabana: `IngestaSabanaService.registrar_desde_borrador`), porque sabe que hacer
con el archivo.

Un borrador vence a las 24 horas: se limpia al crear uno nuevo y al iniciar la aplicacion.
"""

import hashlib
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.core.entities.borrador import (
    VIGENCIA_DEL_BORRADOR,
    BorradorNoEncontrado,
    CatalogoDesconocido,
    DatosBorrador,
    NuevoBorrador,
)
from app.core.entities.lectura_tabla import (
    AdvertenciaLectura,
    FormatoTabla,
    OpcionDetectable,
    OpcionesLectura,
    TablaLeida,
)
from app.core.entities.mapeador import (
    AnalisisEncabezados,
    Asignacion,
    CatalogoCampos,
    ProblemaMapeo,
)
from app.core.ports.lector_tabla_port import LectorTablaPort
from app.core.ports.repositorio_mapeador_port import RepositorioMapeadorPort
from app.core.services.mapeador.analisis import EsVacio, analizar, es_vacio
from app.core.services.mapeador.serializacion import analisis_a_dict, analisis_desde_dict
from app.core.services.mapeador.validacion import validar

Reloj = Callable[[], datetime]


def ahora_utc() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class CatalogoMapeable:
    """Un catalogo de campos y lo que su consumidor toma por vacio (en la sabana, `es_vacio`)."""

    catalogo: CatalogoCampos
    vacio: EsVacio = es_vacio


@dataclass(frozen=True)
class BorradorAnalizado:
    """El borrador con su analisis y lo que se detecto al leer el archivo, para mostrarlo."""

    borrador: DatosBorrador
    analisis: AnalisisEncabezados
    formato: FormatoTabla
    hojas: tuple[str, ...]
    hoja: str | None
    separador: str | None
    codificacion: str | None
    filas: int
    advertencias: tuple[AdvertenciaLectura, ...]
    # Lo que el lector detecto porque el usuario no lo eligio, para decir «(detectado)».
    detectados: tuple[OpcionDetectable, ...] = ()


def opciones_usadas(tabla: TablaLeida) -> dict[str, Any]:
    """Las opciones con las que se leyo el archivo (lo elegido o lo detectado): con ellas se vuelve
    a leer igual al procesarlo."""
    return {
        "formato": tabla.formato.value,
        "hoja": tabla.hoja,
        "separador": tabla.separador,
        "codificacion": tabla.codificacion,
    }


def opciones_de_lectura(
    guardadas: dict[str, Any], respaldo_hoja: str | None = None
) -> OpcionesLectura:
    """Las `OpcionesLectura` de las guardadas con un borrador o una carga."""
    return OpcionesLectura(
        hoja=guardadas.get("hoja") or respaldo_hoja or None,
        separador=guardadas.get("separador"),
        codificacion=guardadas.get("codificacion"),
    )


class MapeadorService:
    def __init__(
        self,
        repositorio: RepositorioMapeadorPort,
        lector: LectorTablaPort,
        catalogos: Iterable[CatalogoMapeable],
        reloj: Reloj = ahora_utc,
    ) -> None:
        self._repositorio = repositorio
        self._lector = lector
        self._catalogos = {c.catalogo.id: c for c in catalogos}
        self._reloj = reloj

    def _catalogo(self, catalogo_id: str) -> CatalogoMapeable:
        try:
            return self._catalogos[catalogo_id]
        except KeyError:
            raise CatalogoDesconocido(catalogo_id) from None

    def catalogo(self, catalogo_id: str) -> CatalogoCampos:
        return self._catalogo(catalogo_id).catalogo

    def _vigente(self, borrador: DatosBorrador | None) -> bool:
        vence = None if borrador is None else borrador.vence_en()
        return vence is not None and self._reloj() < vence

    # --- crear ---

    def crear_borrador(
        self,
        catalogo_id: str,
        nombre_archivo: str,
        contenido: bytes,
        opciones: OpcionesLectura = OpcionesLectura(),  # noqa: B008
    ) -> BorradorAnalizado:
        """Lee y analiza el archivo y lo deja en un borrador.

        Lanza `CatalogoDesconocido`, o `ArchivoIlegible`, `HojaNoEncontrada` o `HojaVacia` de la
        lectura (`app.core.entities.sabana`).
        """
        catalogo = self._catalogo(catalogo_id)
        tabla = self._lector.leer(contenido, nombre_archivo, opciones)
        ahora = self._reloj()
        with self._repositorio.transaccion() as sesion:
            sesion.borrar_borradores_vencidos(ahora - VIGENCIA_DEL_BORRADOR)
            analisis = self._analizar(tabla, catalogo, sesion.recordados(catalogo_id))
            borrador = sesion.crear_borrador(
                NuevoBorrador(
                    catalogo_id=catalogo_id,
                    nombre_archivo=nombre_archivo,
                    huella=hashlib.sha256(contenido).hexdigest(),
                    tamano_bytes=len(contenido),
                    opciones=opciones_usadas(tabla),
                    analisis=analisis_a_dict(analisis),
                    creado_en=ahora,
                ),
                contenido,
            )
        return _analizado(borrador, analisis, tabla, opciones)

    @staticmethod
    def _analizar(tabla: TablaLeida, catalogo: CatalogoMapeable, recordados) -> AnalisisEncabezados:
        return analizar(
            tabla.cabeceras,
            (fila.celdas for fila in tabla.filas),
            catalogo.catalogo,
            recordados,
            catalogo.vacio,
        )

    # --- volver a analizar ---

    def reanalizar(self, borrador_id: int, opciones: OpcionesLectura) -> BorradorAnalizado:
        """Vuelve a leer y analizar el MISMO borrador con otras opciones (sin volver a subir el
        archivo). Reemplaza el analisis guardado. `BorradorNoEncontrado` si no existe o venció."""
        with self._repositorio.transaccion() as sesion:
            borrador = sesion.obtener_borrador(borrador_id, bloquear=True)
            if not self._vigente(borrador):
                raise BorradorNoEncontrado(borrador_id)
            assert borrador is not None
            catalogo = self._catalogo(borrador.catalogo_id)
            tabla = self._lector.leer(
                sesion.contenido_de_borrador(borrador_id), borrador.nombre_archivo, opciones
            )
            analisis = self._analizar(tabla, catalogo, sesion.recordados(borrador.catalogo_id))
            actualizado = sesion.reemplazar_analisis(
                borrador_id, opciones_usadas(tabla), analisis_a_dict(analisis)
            )
        return _analizado(actualizado or borrador, analisis, tabla, opciones)

    # --- validar y descartar ---

    def validar(
        self, borrador_id: int, asignaciones: Sequence[Asignacion]
    ) -> tuple[ProblemaMapeo, ...]:
        """Los problemas de las asignaciones, contra el analisis que se mostro (M-4)."""
        with self._repositorio.transaccion() as sesion:
            borrador = sesion.obtener_borrador(borrador_id)
        if not self._vigente(borrador):
            raise BorradorNoEncontrado(borrador_id)
        assert borrador is not None
        return validar(asignaciones, analisis_desde_dict(borrador.analisis))

    def analisis_guardado(self, borrador_id: int) -> AnalisisEncabezados:
        with self._repositorio.transaccion() as sesion:
            borrador = sesion.obtener_borrador(borrador_id)
        if not self._vigente(borrador):
            raise BorradorNoEncontrado(borrador_id)
        assert borrador is not None
        return analisis_desde_dict(borrador.analisis)

    def descartar(self, borrador_id: int) -> None:
        """Cancelar: borra el borrador. `BorradorNoEncontrado` si no existe."""
        with self._repositorio.transaccion() as sesion:
            if not sesion.borrar_borrador(borrador_id):
                raise BorradorNoEncontrado(borrador_id)

    def descartar_vencidos(self) -> int:
        """Borra los borradores de mas de 24 horas. Pensado para el arranque de la aplicacion."""
        with self._repositorio.transaccion() as sesion:
            return sesion.borrar_borradores_vencidos(self._reloj() - VIGENCIA_DEL_BORRADOR)


def opciones_detectadas(
    tabla: TablaLeida, elegidas: OpcionesLectura
) -> tuple[OpcionDetectable, ...]:
    """Las opciones que el lector reporto (no son nulas en la tabla) y el usuario no eligio."""
    return tuple(
        opcion
        for opcion in OpcionDetectable
        if getattr(tabla, opcion.value) is not None and not getattr(elegidas, opcion.value)
    )


def _analizado(
    borrador: DatosBorrador,
    analisis: AnalisisEncabezados,
    tabla: TablaLeida,
    elegidas: OpcionesLectura,
) -> BorradorAnalizado:
    return BorradorAnalizado(
        borrador=borrador,
        analisis=analisis,
        formato=tabla.formato,
        hojas=tabla.hojas,
        hoja=tabla.hoja,
        separador=tabla.separador,
        codificacion=tabla.codificacion,
        filas=len(tabla.filas),
        advertencias=tabla.advertencias,
        detectados=opciones_detectadas(tabla, elegidas),
    )

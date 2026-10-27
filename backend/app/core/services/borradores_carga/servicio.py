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
from app.core.entities.campos_adicionales import (
    CampoAdicional,
    CampoAdicionalNoEncontrado,
    ColumnaInexistente,
    NombreDeCampoRepetido,
    TipoAdicional,
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
from app.core.services.mapeador.serializacion import (
    analisis_a_dict,
    analisis_desde_dict,
    campo_a_dict,
)
from app.core.services.mapeador.similitud import coincide, normalizar_cabecera
from app.core.services.mapeador.validacion import validar
from app.core.services.seleccion_cartera.nombres_adicionales import nombre_tecnico

Reloj = Callable[[], datetime]


def ahora_utc() -> datetime:
    return datetime.now(UTC)


ArmarCatalogo = Callable[[Sequence[CampoAdicional], bool], CatalogoCampos]


@dataclass(frozen=True)
class CatalogoMapeable:
    """Un catalogo de campos y lo que su consumidor toma por vacio (en la sabana, `es_vacio`).

    `armar` suma al catalogo los campos adicionales (RF-64) que el usuario creo: recibe sus
    definiciones y si incluye los archivados. Sin `armar`, el catalogo no admite adicionales.
    """

    catalogo: CatalogoCampos
    vacio: EsVacio = es_vacio
    armar: ArmarCatalogo | None = None

    def con_adicionales(
        self, adicionales: Sequence[CampoAdicional], con_archivados: bool = False
    ) -> CatalogoCampos:
        if self.armar is None:
            return self.catalogo
        return self.armar(adicionales, con_archivados)


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
        """Los campos del catalogo: los base y los adicionales activos."""
        mapeable = self._catalogo(catalogo_id)
        if mapeable.armar is None:
            return mapeable.catalogo
        with self._repositorio.transaccion() as sesion:
            return mapeable.con_adicionales(sesion.adicionales(catalogo_id))

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
            analisis = self._analizar(tabla, catalogo, sesion, catalogo_id)
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
    def _analizar(
        tabla: TablaLeida, catalogo: CatalogoMapeable, sesion, catalogo_id: str
    ) -> AnalisisEncabezados:
        adicionales = sesion.adicionales(catalogo_id) if catalogo.armar else ()
        return analizar(
            tabla.cabeceras,
            (fila.celdas for fila in tabla.filas),
            catalogo.con_adicionales(adicionales),
            sesion.recordados(catalogo_id),
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
            analisis = self._analizar(tabla, catalogo, sesion, borrador.catalogo_id)
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

    # --- campos adicionales (RF-64 a RF-66) ---

    def crear_campo_adicional(
        self, borrador_id: int, indice: int, nombre_legible: str, tipo: TipoAdicional
    ) -> tuple[CampoAdicional, CatalogoCampos]:
        """Crea un campo adicional desde una columna del archivo y lo suma al analisis guardado del
        borrador, en UNA transaccion: el usuario lo puede asignar enseguida y, si algo falla, no
        queda ni el campo ni el cambio. El encabezado de origen de la columna es su alias.

        `BorradorNoEncontrado`, `ColumnaInexistente` y `NombreDeCampoRepetido` (con el campo que
        choca). Devuelve el campo y el catalogo con el que ya cuenta el borrador.
        """
        nombre_legible = " ".join(nombre_legible.split())
        with self._repositorio.transaccion() as sesion:
            borrador = sesion.obtener_borrador(borrador_id, bloquear=True)
            if not self._vigente(borrador):
                raise BorradorNoEncontrado(borrador_id)
            assert borrador is not None
            mapeable = self._catalogo(borrador.catalogo_id)
            if mapeable.armar is None:
                raise CatalogoDesconocido(borrador.catalogo_id)
            analisis = analisis_desde_dict(borrador.analisis)
            columna = next((c for c in analisis.columnas if c.indice == indice), None)
            if columna is None:
                raise ColumnaInexistente(indice)
            sesion.bloquear_adicionales()
            existentes = sesion.adicionales(borrador.catalogo_id)
            _verificar_nombre(mapeable, existentes, nombre_legible)
            campo = sesion.crear_adicional(
                borrador.catalogo_id,
                CampoAdicional(
                    nombre=nombre_tecnico(nombre_legible, (c.nombre for c in existentes)),
                    nombre_legible=nombre_legible,
                    tipo=tipo,
                    encabezado_origen=columna.normalizado,
                ),
                self._reloj(),
            )
            nuevo = next(
                c for c in mapeable.con_adicionales([campo]).campos if c.nombre == campo.nombre
            )
            guardado = dict(borrador.analisis)
            guardado["campos"] = [*borrador.analisis["campos"], campo_a_dict(nuevo)]
            sesion.reemplazar_analisis(borrador_id, borrador.opciones, guardado)
            catalogo = mapeable.con_adicionales([*existentes, campo])
        return campo, catalogo

    def campos_adicionales(self, catalogo_id: str) -> Sequence[CampoAdicional]:
        """Todas las definiciones del catalogo, archivadas incluidas (para reactivarlas)."""
        mapeable = self._catalogo(catalogo_id)
        if mapeable.armar is None:
            return ()
        with self._repositorio.transaccion() as sesion:
            return sesion.adicionales(catalogo_id)

    def cambiar_campo_adicional(
        self,
        catalogo_id: str,
        nombre: str,
        nombre_legible: str | None = None,
        archivado: bool | None = None,
    ) -> CampoAdicional:
        """Renombra, archiva o reactiva un campo adicional. El nombre tecnico y el tipo no cambian,
        asi que lo guardado que lo usa (selecciones, definiciones, mapeos) sigue resolviendo.

        `CampoAdicionalNoEncontrado` y `NombreDeCampoRepetido`.
        """
        mapeable = self._catalogo(catalogo_id)
        with self._repositorio.transaccion() as sesion:
            sesion.bloquear_adicionales()
            existentes = sesion.adicionales(catalogo_id)
            actual = next((c for c in existentes if c.nombre == nombre), None)
            if actual is None:
                raise CampoAdicionalNoEncontrado(nombre)
            if nombre_legible is not None:
                nombre_legible = " ".join(nombre_legible.split())
                _verificar_nombre(
                    mapeable, [c for c in existentes if c.nombre != nombre], nombre_legible
                )
            cambiado = sesion.actualizar_adicional(nombre, nombre_legible, archivado, self._reloj())
        assert cambiado is not None
        return cambiado

    def descartar(self, borrador_id: int) -> None:
        """Cancelar: borra el borrador. `BorradorNoEncontrado` si no existe."""
        with self._repositorio.transaccion() as sesion:
            if not sesion.borrar_borrador(borrador_id):
                raise BorradorNoEncontrado(borrador_id)

    def descartar_vencidos(self) -> int:
        """Borra los borradores de mas de 24 horas. Pensado para el arranque de la aplicacion."""
        with self._repositorio.transaccion() as sesion:
            return sesion.borrar_borradores_vencidos(self._reloj() - VIGENCIA_DEL_BORRADOR)


def _verificar_nombre(
    mapeable: CatalogoMapeable, otros: Sequence[CampoAdicional], nombre_legible: str
) -> None:
    """El nombre legible no puede coincidir con ningun otro campo: ni con uno base (por su nombre o
    sus alias) ni con un adicional, archivado o no (por su nombre o su encabezado de origen). Es
    la misma `coincide` con la que el mapeador reconoce un encabezado."""
    normalizado = normalizar_cabecera(nombre_legible)
    for campo in mapeable.con_adicionales(otros, con_archivados=True).campos:
        if coincide(normalizado, campo):
            raise NombreDeCampoRepetido(nombre_legible, campo)


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

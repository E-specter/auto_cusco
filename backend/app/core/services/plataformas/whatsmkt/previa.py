"""Previsualizacion de los archivos de la campana de WhatsMKT, sin guardar nada (RF-WM-35, B4a).

Usa `ArchivoContactosService` (B2) sin rearmar nada y le suma lo que la pantalla necesita para
decidir si deja «Crear»:

- el reparto de las exclusiones por campana (por el segmento del producto);
- `sin_dias_atraso` (RF-WM-20): en un lote por segmento, un producto sin dias de atraso no cae en
  ningun segmento y es una exclusion mas; en modo global no aplica;
- los problemas, que NO son errores 4xx sino una lista: `definicion_no_whatsmkt`,
  `sin_supervisores` y `sin_productos`. La interfaz deja «Crear» inactivo mientras haya alguno.

Todavia no incluye el mensaje (B4b) ni valida la fecha de envio.
"""

from dataclasses import dataclass
from datetime import date

from app.core.entities.whatsmkt import CodigoWhatsmkt, ModoCampana, SegmentoWhatsmkt
from app.core.ports.repositorio_whatsmkt_port import RepositorioWhatsmktPort
from app.core.services.definiciones_columnas.servicio import DefinicionesColumnasService
from app.core.services.gestiones_digitales.servicio import SupervisionService
from app.core.services.plataformas.whatsmkt.archivo_contactos import (
    ArchivoContactos,
    ArchivoContactosService,
    ExclusionContacto,
    SeleccionCampana,
)
from app.core.services.plataformas.whatsmkt.plataforma import CLAVE


@dataclass(frozen=True)
class PeticionPrevia:
    seleccion: SeleccionCampana
    definicion_id: int
    version: int | None  # sin version, la vigente
    modo: ModoCampana = ModoCampana.GLOBAL


@dataclass(frozen=True)
class ProblemaCampana:
    """Algo que impide crear la campana; la interfaz lo muestra con el texto de su `codigo`."""

    codigo: CodigoWhatsmkt
    detalle: str


@dataclass(frozen=True)
class CabeceraPrevia:
    """El encabezado del archivo y, debajo, la etiqueta de la columna (RF-WM-12)."""

    nombre: str
    etiqueta: str | None


@dataclass(frozen=True)
class CampanaPrevista:
    """Una campana que resultara: su segmento (None si es global), su archivo y sus exclusiones."""

    segmento: SegmentoWhatsmkt | None
    archivo: ArchivoContactos
    cabeceras: tuple[CabeceraPrevia, ...]
    exclusiones: tuple[ExclusionContacto, ...]


@dataclass(frozen=True)
class PreviaCampanas:
    campanas: tuple[CampanaPrevista, ...]
    # Exclusiones que no pertenecen a ninguna campana: las de un producto sin dias de atraso y las
    # de un segmento que se quedo sin productos.
    exclusiones_sin_campana: tuple[ExclusionContacto, ...]
    problemas: tuple[ProblemaCampana, ...]
    disponibles: int
    solicitados: int
    fecha_envio: date | None

    @property
    def total_exclusiones(self) -> int:
        return sum(len(c.exclusiones) for c in self.campanas) + len(self.exclusiones_sin_campana)


class PrevisualizacionWhatsmktService:
    def __init__(
        self,
        archivos: ArchivoContactosService,
        repositorio: RepositorioWhatsmktPort,
        definiciones: DefinicionesColumnasService,
        supervision: SupervisionService,
    ) -> None:
        self._archivos = archivos
        self._repositorio = repositorio
        self._definiciones = definiciones
        self._supervision = supervision

    def previsualizar(self, peticion: PeticionPrevia) -> PreviaCampanas:
        """Lanza `DefinicionNoEncontrada` o `VersionNoEncontrada` si la definicion no existe."""
        vista = self._definiciones.obtener(peticion.definicion_id, peticion.version)
        if vista.definicion.plataforma != CLAVE:
            return PreviaCampanas(
                campanas=(),
                exclusiones_sin_campana=(),
                problemas=(
                    ProblemaCampana(
                        CodigoWhatsmkt.DEFINICION_NO_WHATSMKT,
                        f"La definicion {vista.definicion.nombre!r} no es de la plataforma "
                        "WhatsMKT",
                    ),
                ),
                disponibles=0,
                solicitados=peticion.seleccion.cantidad,
                fecha_envio=peticion.seleccion.fecha_envio,
            )
        cargada = self._definiciones.cargar(peticion.definicion_id, vista.version.numero)
        supervision = self._supervision.obtener()
        segmentos = self._repositorio.listar_segmentos()
        por_segmento = peticion.modo is ModoCampana.POR_SEGMENTO
        armado = self._archivos.armar(
            peticion.seleccion,
            cargada.definicion,
            segmentos,
            supervision.supervisores,
            supervision.procedencias,
            por_segmento,
        )
        # RF-WM-20: solo en un lote por segmento un producto sin dias de atraso se excluye.
        exclusiones = sorted(
            [
                *armado.exclusiones,
                *(
                    ExclusionContacto(
                        s.fila,
                        s.pagare,
                        CodigoWhatsmkt.SIN_DIAS_ATRASO,
                        "No tiene dias de atraso, asi que no cae en ningun segmento",
                    )
                    for s in armado.sin_segmento
                ),
            ],
            key=lambda e: e.fila,
        )
        por_clave = {s.clave: s for s in segmentos}
        cabeceras = tuple(CabeceraPrevia(c.nombre, c.etiqueta) for c in cargada.definicion.campos)
        campanas = tuple(
            CampanaPrevista(
                segmento=None if a.segmento is None else por_clave[a.segmento],
                archivo=a,
                cabeceras=cabeceras,
                exclusiones=tuple(e for e in exclusiones if e.segmento == a.segmento),
            )
            for a in armado.archivos
        )
        con_campana = {a.segmento for a in armado.archivos}
        return PreviaCampanas(
            campanas=campanas,
            exclusiones_sin_campana=tuple(e for e in exclusiones if e.segmento not in con_campana),
            problemas=self._problemas(bool(supervision.supervisores), bool(campanas)),
            disponibles=armado.disponibles,
            solicitados=armado.solicitados,
            fecha_envio=armado.fecha_envio,
        )

    @staticmethod
    def _problemas(hay_supervisores: bool, hay_campanas: bool) -> tuple[ProblemaCampana, ...]:
        problemas = []
        if not hay_supervisores:
            problemas.append(
                ProblemaCampana(
                    CodigoWhatsmkt.SIN_SUPERVISORES,
                    "No hay supervisores configurados: sin ellos no se crea la campana",
                )
            )
        if not hay_campanas:
            problemas.append(
                ProblemaCampana(
                    CodigoWhatsmkt.SIN_PRODUCTOS,
                    "Ningun segmento tiene productos despues de las exclusiones: "
                    "no se crea ninguna campana",
                )
            )
        return tuple(problemas)

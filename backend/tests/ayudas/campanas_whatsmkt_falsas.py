"""Dobles en memoria para crear campanas de WhatsMKT (T-WM-B4b1, parte 2).

Un repositorio de campanas que imita lo que importa del de PostgreSQL: el lote se guarda entero o
no se guarda (aqui, al final), el archivo conserva sus bytes y las versiones usadas se marcan.
"""

from dataclasses import replace
from datetime import date, datetime, timedelta

from app.adapters.output.plataformas.whatsmkt.exportador_contactos import exportar_contactos
from app.core.entities.whatsmkt import ExclusionContacto, ModoCampana
from app.core.entities.whatsmkt_campana import (
    ArchivoGuardado,
    CampanaNueva,
    CampanaWhatsmkt,
    EstadoCampana,
    LoteCreado,
    LoteNuevo,
    PaginaCampanas,
    PaginaExclusiones,
)
from app.core.entities.whatsmkt_informe import (
    FilaCargadaWhatsmkt,
    ReporteGuardado,
    ReporteNuevo,
)
from app.core.services.generacion_cargas.servicio import GeneracionCargasService
from app.core.services.plataformas.whatsmkt.archivo_contactos import (
    ArchivoContactosService,
)
from app.core.services.plataformas.whatsmkt.biblioteca import BibliotecaWhatsmktService
from app.core.services.plataformas.whatsmkt.crear import CreacionCampanasWhatsmktService
from app.core.services.plataformas.whatsmkt.previa import PrevisualizacionWhatsmktService
from app.core.services.plataformas.whatsmkt.programacion import ProgramacionWhatsmktService
from app.core.services.seleccion_cartera.servicio import ConsultaCarteraService
from tests.ayudas.calendario_falso import calendario_de_prueba
from tests.ayudas.previa_whatsmkt_falsos import (
    DefinicionesGuardadasFalsas,
    RepositorioWhatsmktFalso,
    SupervisionFalsa,
    TextosFalsos,
)
from tests.ayudas.repositorio_whatsmkt_falso import RepositorioAdjuntosFalso
from tests.test_whatsmkt_contactos import SUPERVISORES, RepositorioCartera, definicion

CREADA_EN = datetime(2026, 11, 3, 10, 0)
DESCARTADA_EN = datetime(2026, 11, 4, 9, 0)


def registrada(
    campana_id: int, lote_id: int, c: CampanaNueva, creado_en: datetime = CREADA_EN
) -> CampanaWhatsmkt:
    return CampanaWhatsmkt(
        id=campana_id,
        lote_id=lote_id,
        nombre=c.nombre,
        segmento=c.segmento,
        segmento_etiqueta=c.segmento_etiqueta,
        definicion_id=c.definicion_id,
        definicion_nombre=c.definicion_nombre,
        definicion_version=c.definicion_version,
        texto_guardado_id=c.texto_guardado_id,
        texto_version=c.texto_version,
        mensaje_texto=c.mensaje_texto,
        whatsapp_contacto=c.whatsapp_contacto,
        fecha_corte=c.fecha_corte,
        filtros=c.filtros,
        orden=c.orden,
        cantidad_pedida=c.cantidad_pedida,
        fecha_envio=c.fecha_envio,
        horarios=c.horarios,
        lo_antes_posible=c.lo_antes_posible,
        tipo_envio=c.tipo_envio,
        foto_id=c.foto_id,
        adjunto_id=c.adjunto_id,
        etiqueta_vcard=c.etiqueta_vcard,
        cantidad=c.cantidad,
        productos=c.productos,
        supervisores=c.supervisores,
        creado_en=creado_en,
        descartada_en=None,
        archivo_nombre=c.archivo_nombre,
        archivo_tamano=len(c.archivo_contenido),
    )


class RepositorioCampanasFalso:
    """Guarda el lote entero al final: si `crear_lote` falla antes, no queda nada."""

    def __init__(self) -> None:
        self.lotes: list[LoteNuevo] = []
        self.campanas: dict[int, CampanaWhatsmkt] = {}
        self.archivos: dict[int, ArchivoGuardado] = {}
        self.modos: dict[int, ModoCampana] = {}
        # (lote, campana o None, exclusion), en el orden en que se guardaron
        self.exclusiones: list[tuple[int, int | None, ExclusionContacto]] = []
        self.filas: dict[int, tuple[FilaCargadaWhatsmkt, ...]] = {}
        self.reportes: dict[int, ReporteGuardado] = {}  # por campana: uno vigente
        self.ahora = DESCARTADA_EN  # el instante que pone descartar e importar; se puede mover
        self.falla: Exception | None = None

    def crear_lote(self, lote: LoteNuevo) -> LoteCreado:
        if self.falla is not None:
            raise self.falla
        lote_id = len(self.lotes) + 1
        # Cada lote es posterior al anterior; las campanas de un lote comparten el instante.
        creado_en = CREADA_EN + timedelta(minutes=lote_id)
        creadas = [
            registrada(len(self.campanas) + i, lote_id, c, creado_en)
            for i, c in enumerate(lote.campanas, 1)
        ]
        self.lotes.append(lote)
        for c, nueva in zip(creadas, lote.campanas, strict=True):
            self.campanas[c.id] = c
            self.archivos[c.id] = ArchivoGuardado(nueva.archivo_nombre, nueva.archivo_contenido)
            self.exclusiones += [(lote_id, c.id, e) for e in nueva.exclusiones]
            self.filas[c.id] = tuple(
                FilaCargadaWhatsmkt(f.numero, f.pagare, f.supervision) for f in nueva.filas
            )
        self.exclusiones += [(lote_id, None, e) for e in lote.exclusiones_sin_campana]
        self.modos[lote_id] = lote.modo
        return LoteCreado(lote_id, lote.modo, tuple(creadas))

    def obtener_archivo(self, campana_id: int):
        return self.archivos.get(campana_id)

    def _vista(self, c: CampanaWhatsmkt) -> CampanaWhatsmkt:
        return replace(c, con_informe=c.id in self.reportes)

    def listar(
        self,
        limite: int,
        desplazamiento: int,
        lote_id: int | None = None,
        mes: date | None = None,
        estado: EstadoCampana = EstadoCampana.ACTIVAS,
    ) -> PaginaCampanas:
        todas = [self._vista(c) for c in self.campanas.values()]
        descartadas = estado is EstadoCampana.DESCARTADAS
        # Como PostgreSQL: las mas recientes primero y, a igual instante, el id mayor primero.
        cumplen = sorted(
            (
                c
                for c in todas
                if (c.descartada_en is not None) == descartadas
                and (lote_id is None or c.lote_id == lote_id)
                and (
                    mes is None
                    or (c.fecha_envio.year, c.fecha_envio.month) == (mes.year, mes.month)
                )
            ),
            key=lambda c: (c.creado_en, c.id),
            reverse=True,
        )
        activas = [c for c in todas if c.descartada_en is None]
        return PaginaCampanas(
            len(cumplen),
            tuple(cumplen[desplazamiento : desplazamiento + limite]),
            len(activas),
            len(todas) - len(activas),
            sum(1 for c in activas if not c.con_informe),
        )

    def obtener(self, campana_id: int) -> CampanaWhatsmkt | None:
        c = self.campanas.get(campana_id)
        return None if c is None else self._vista(c)

    def modo_del_lote(self, lote_id: int) -> ModoCampana:
        return self.modos[lote_id]

    def listar_exclusiones(
        self, lote_id: int, campana_id: int | None, limite: int, desplazamiento: int
    ) -> PaginaExclusiones:
        propias = sorted(
            (
                e
                for lote, campana, e in self.exclusiones
                if (lote, campana) == (lote_id, campana_id)
            ),
            key=lambda e: e.fila,
        )
        return PaginaExclusiones(
            len(propias), tuple(propias[desplazamiento : desplazamiento + limite])
        )

    def descartar(self, campana_id: int) -> CampanaWhatsmkt | None:
        c = self.campanas.get(campana_id)
        if c is None:
            return None
        if c.descartada_en is None:
            self.campanas[campana_id] = replace(c, descartada_en=self.ahora)
        return self.obtener(campana_id)

    def restaurar(self, campana_id: int) -> CampanaWhatsmkt | None:
        c = self.campanas.get(campana_id)
        if c is None:
            return None
        self.campanas[campana_id] = replace(c, descartada_en=None)
        return self.obtener(campana_id)

    def eliminar_descartada(self, campana_id: int) -> bool:
        c = self.campanas.get(campana_id)
        if c is None or c.descartada_en is None:
            return False
        del self.campanas[campana_id]
        for tabla in (self.archivos, self.filas, self.reportes):
            tabla.pop(campana_id, None)
        self.exclusiones = [x for x in self.exclusiones if x[1] != campana_id]
        if not any(o.lote_id == c.lote_id for o in self.campanas.values()):
            self.exclusiones = [x for x in self.exclusiones if x[0] != c.lote_id]
            self.modos.pop(c.lote_id, None)
        return True

    def obtener_reporte(self, campana_id: int) -> ReporteGuardado | None:
        return self.reportes.get(campana_id)

    def reemplazar_reporte(self, campana_id: int, reporte: ReporteNuevo) -> ReporteGuardado:
        self.reportes[campana_id] = ReporteGuardado(
            id=len(self.reportes) + 1,
            campana_id=campana_id,
            archivo_nombre=reporte.archivo_nombre,
            huella=reporte.huella,
            importado_en=self.ahora,
            informe=reporte.informe,
        )
        return self.reportes[campana_id]

    def filas_cargadas(self, campana_id: int) -> tuple[FilaCargadaWhatsmkt, ...]:
        return self.filas.get(campana_id, ())


class Entorno:
    """Todo lo que la creacion lee, para cambiarlo entre un pedido y otro."""

    def __init__(self, productos: list[dict], supervisores=SUPERVISORES) -> None:
        self.textos = TextosFalsos()
        self.whatsmkt = RepositorioWhatsmktFalso()
        self.adjuntos = RepositorioAdjuntosFalso(self.whatsmkt.configuracion)
        self.campanas = RepositorioCampanasFalso()
        self.calendario = calendario_de_prueba()  # se puede cambiar entre un pedido y otro
        self.productos = productos
        self.supervisores = supervisores

    def servicio(self) -> CreacionCampanasWhatsmktService:
        generacion = GeneracionCargasService(
            ConsultaCarteraService(RepositorioCartera(self.productos))
        )
        previa = PrevisualizacionWhatsmktService(
            ArchivoContactosService(generacion),
            self.whatsmkt,
            DefinicionesGuardadasFalsas(definicion(), "whatsmkt"),
            SupervisionFalsa(self.supervisores),
            self.textos,
            ProgramacionWhatsmktService(self.calendario),
        )
        # La biblioteca lee las dos cosas del mismo repositorio de adjuntos en memoria.
        self.adjuntos.configuracion = self.whatsmkt.configuracion
        return CreacionCampanasWhatsmktService(
            previa,
            self.whatsmkt,
            self.campanas,
            BibliotecaWhatsmktService(self.adjuntos),
            exportar_contactos,
        )

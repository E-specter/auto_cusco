"""Dobles en memoria para crear campanas de WhatsMKT (T-WM-B4b1, parte 2).

Un repositorio de campanas que imita lo que importa del de PostgreSQL: el lote se guarda entero o
no se guarda (aqui, al final), el archivo conserva sus bytes y las versiones usadas se marcan.
"""

from datetime import date, datetime, timedelta

from app.adapters.output.plataformas.whatsmkt.exportador_contactos import exportar_contactos
from app.core.entities.whatsmkt import ModoCampana
from app.core.entities.whatsmkt_campana import (
    ArchivoGuardado,
    CampanaNueva,
    CampanaWhatsmkt,
    LoteCreado,
    LoteNuevo,
    PaginaCampanas,
    PaginaExclusiones,
)
from app.core.services.generacion_cargas.servicio import GeneracionCargasService
from app.core.services.plataformas.whatsmkt.archivo_contactos import (
    ArchivoContactosService,
    ExclusionContacto,
)
from app.core.services.plataformas.whatsmkt.biblioteca import BibliotecaWhatsmktService
from app.core.services.plataformas.whatsmkt.crear import CreacionCampanasWhatsmktService
from app.core.services.plataformas.whatsmkt.previa import PrevisualizacionWhatsmktService
from app.core.services.seleccion_cartera.servicio import ConsultaCarteraService
from tests.ayudas.previa_whatsmkt_falsos import (
    DefinicionesGuardadasFalsas,
    RepositorioWhatsmktFalso,
    SupervisionFalsa,
    TextosFalsos,
)
from tests.ayudas.repositorio_whatsmkt_falso import RepositorioAdjuntosFalso
from tests.test_whatsmkt_contactos import SUPERVISORES, RepositorioCartera, definicion

CREADA_EN = datetime(2026, 11, 3, 10, 0)


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
        self.exclusiones += [(lote_id, None, e) for e in lote.exclusiones_sin_campana]
        self.modos[lote_id] = lote.modo
        return LoteCreado(lote_id, lote.modo, tuple(creadas))

    def obtener_archivo(self, campana_id: int):
        return self.archivos.get(campana_id)

    def listar(
        self,
        limite: int,
        desplazamiento: int,
        lote_id: int | None = None,
        mes: date | None = None,
    ) -> PaginaCampanas:
        # Como PostgreSQL: las mas recientes primero y, a igual instante, el id mayor primero.
        cumplen = sorted(
            (
                c
                for c in self.campanas.values()
                if (lote_id is None or c.lote_id == lote_id)
                and (
                    mes is None
                    or (c.fecha_envio.year, c.fecha_envio.month) == (mes.year, mes.month)
                )
            ),
            key=lambda c: (c.creado_en, c.id),
            reverse=True,
        )
        return PaginaCampanas(
            len(cumplen), tuple(cumplen[desplazamiento : desplazamiento + limite])
        )

    def obtener(self, campana_id: int) -> CampanaWhatsmkt | None:
        return self.campanas.get(campana_id)

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


class Entorno:
    """Todo lo que la creacion lee, para cambiarlo entre un pedido y otro."""

    def __init__(self, productos: list[dict], supervisores=SUPERVISORES) -> None:
        self.textos = TextosFalsos()
        self.whatsmkt = RepositorioWhatsmktFalso()
        self.adjuntos = RepositorioAdjuntosFalso(self.whatsmkt.configuracion)
        self.campanas = RepositorioCampanasFalso()
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

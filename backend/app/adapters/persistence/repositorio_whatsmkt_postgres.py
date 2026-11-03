"""Configuracion, segmentos y biblioteca de adjuntos de WhatsMKT, sobre PostgreSQL."""

import hashlib

from sqlalchemy import Engine, func, select, update
from sqlalchemy.dialects.postgresql import insert as insert_pg
from sqlalchemy.engine import Row
from sqlalchemy.exc import IntegrityError

from app.adapters.persistence.modelos import (
    WhatsmktAdjunto,
    WhatsmktConfiguracion,
    WhatsmktSegmento,
)
from app.core.entities.whatsmkt import (
    AdjuntoWhatsmkt,
    ConfiguracionWhatsmkt,
    DefinicionDefectoNoExiste,
    Horario,
    SegmentoWhatsmkt,
    TipoAdjunto,
)
from app.core.ports.repositorio_whatsmkt_port import RepositorioWhatsmktPort

_CONFIGURACION = WhatsmktConfiguracion.__table__
_SEGMENTO = WhatsmktSegmento.__table__
_ADJUNTO = WhatsmktAdjunto.__table__
# Listar y devolver adjuntos nunca carga el contenido (RF-WM-30).
_SIN_CONTENIDO = [c for c in _ADJUNTO.c if c.name != "contenido"]
_FILA_CONFIGURACION = 1
# Explicito y de 63 caracteres o menos: PostgreSQL trunca el nombre largo que arma la convencion y
# `diag.constraint_name` ya no coincidiria (lo vigila test_whatsmkt_migracion.py).
_FK_DEFINICION = "fk_whatsmkt_configuracion_definicion_defecto"


def _configuracion(fila: Row) -> ConfiguracionWhatsmkt:
    return ConfiguracionWhatsmkt(
        horario_1=Horario(fila.horario_1_inicio, fila.horario_1_fin),
        horario_2=Horario(fila.horario_2_inicio, fila.horario_2_fin),
        plantilla_nombre=fila.plantilla_nombre,
        definicion_defecto_id=fila.definicion_defecto_id,
        tope_mensaje=fila.tope_mensaje,
        tope_video=fila.tope_video,
        tope_audio=fila.tope_audio,
        tope_pdf=fila.tope_pdf,
        actualizado_en=fila.actualizado_en,
    )


def _segmento(fila: Row) -> SegmentoWhatsmkt:
    return SegmentoWhatsmkt(fila.clave, fila.etiqueta, fila.desde, fila.hasta, fila.orden)


def _adjunto(fila: Row) -> AdjuntoWhatsmkt:
    return AdjuntoWhatsmkt(
        id=fila.id,
        tipo=TipoAdjunto(fila.tipo),
        nombre=fila.nombre,
        tamano=fila.tamano,
        huella=fila.huella,
        creado_en=fila.creado_en,
        archivado_en=fila.archivado_en,
    )


class RepositorioWhatsmktPostgres(RepositorioWhatsmktPort):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # --- Configuracion -------------------------------------------------

    def obtener_configuracion(self) -> ConfiguracionWhatsmkt:
        with self._engine.connect() as cx:
            fila = cx.execute(
                select(_CONFIGURACION).where(_CONFIGURACION.c.id == _FILA_CONFIGURACION)
            ).one_or_none()
        if fila is None:
            raise RuntimeError("Falta la configuracion de WhatsMKT: aplica las migraciones")
        return _configuracion(fila)

    def guardar_configuracion(self, configuracion: ConfiguracionWhatsmkt) -> ConfiguracionWhatsmkt:
        consulta = (
            update(_CONFIGURACION)
            .where(_CONFIGURACION.c.id == _FILA_CONFIGURACION)
            .values(
                horario_1_inicio=configuracion.horario_1.inicio,
                horario_1_fin=configuracion.horario_1.fin,
                horario_2_inicio=configuracion.horario_2.inicio,
                horario_2_fin=configuracion.horario_2.fin,
                plantilla_nombre=configuracion.plantilla_nombre,
                definicion_defecto_id=configuracion.definicion_defecto_id,
                tope_mensaje=configuracion.tope_mensaje,
                tope_video=configuracion.tope_video,
                tope_audio=configuracion.tope_audio,
                tope_pdf=configuracion.tope_pdf,
                actualizado_en=func.clock_timestamp(),
            )
            .returning(*_CONFIGURACION.c)
        )
        try:
            with self._engine.begin() as cx:
                fila = cx.execute(consulta).one_or_none()
        except IntegrityError as exc:
            diagnostico = getattr(exc.orig, "diag", None)
            if getattr(diagnostico, "constraint_name", None) == _FK_DEFINICION:
                raise DefinicionDefectoNoExiste(configuracion.definicion_defecto_id or 0) from exc
            raise
        if fila is None:
            raise RuntimeError("Falta la configuracion de WhatsMKT: aplica las migraciones")
        return _configuracion(fila)

    # --- Segmentos -----------------------------------------------------

    def listar_segmentos(self) -> list[SegmentoWhatsmkt]:
        with self._engine.connect() as cx:
            filas = cx.execute(select(_SEGMENTO).order_by(_SEGMENTO.c.orden)).all()
        return [_segmento(f) for f in filas]

    def reemplazar_segmentos(self, segmentos: list[SegmentoWhatsmkt]) -> list[SegmentoWhatsmkt]:
        # Los segmentos son fijos: se actualizan por clave, no se borran (B3 les cuelga una FK).
        with self._engine.begin() as cx:
            for s in segmentos:
                cx.execute(
                    update(_SEGMENTO)
                    .where(_SEGMENTO.c.clave == s.clave)
                    .values(etiqueta=s.etiqueta, desde=s.desde, hasta=s.hasta, orden=s.orden)
                )
            filas = cx.execute(select(_SEGMENTO).order_by(_SEGMENTO.c.orden)).all()
        return [_segmento(f) for f in filas]

    # --- Adjuntos ------------------------------------------------------

    def guardar_adjunto(self, tipo: TipoAdjunto, nombre: str, contenido: bytes) -> AdjuntoWhatsmkt:
        huella = hashlib.sha256(contenido).hexdigest()
        alta = (
            insert_pg(_ADJUNTO)
            .values(
                tipo=tipo.value,
                nombre=nombre,
                tamano=len(contenido),
                huella=huella,
                contenido=contenido,
            )
            .on_conflict_do_nothing(index_elements=["huella"])
            .returning(*_SIN_CONTENIDO)
        )
        with self._engine.begin() as cx:
            fila = cx.execute(alta).one_or_none()
            if fila is None:  # la huella ya estaba (o la gano otra peticion a la vez)
                fila = cx.execute(select(*_SIN_CONTENIDO).where(_ADJUNTO.c.huella == huella)).one()
        return _adjunto(fila)

    def listar_adjuntos(self, archivados: bool = False) -> list[AdjuntoWhatsmkt]:
        columna = _ADJUNTO.c.archivado_en
        consulta = (
            select(*_SIN_CONTENIDO)
            .where(columna.is_not(None) if archivados else columna.is_(None))
            .order_by(_ADJUNTO.c.creado_en.desc(), _ADJUNTO.c.id.desc())
        )
        with self._engine.connect() as cx:
            return [_adjunto(f) for f in cx.execute(consulta).all()]

    def obtener_adjunto(self, adjunto_id: int) -> AdjuntoWhatsmkt | None:
        with self._engine.connect() as cx:
            fila = cx.execute(
                select(*_SIN_CONTENIDO).where(_ADJUNTO.c.id == adjunto_id)
            ).one_or_none()
        return _adjunto(fila) if fila else None

    def leer_contenido_adjunto(self, adjunto_id: int) -> bytes | None:
        with self._engine.connect() as cx:
            return cx.execute(
                select(_ADJUNTO.c.contenido).where(_ADJUNTO.c.id == adjunto_id)
            ).scalar_one_or_none()

    def archivar_adjunto(self, adjunto_id: int) -> AdjuntoWhatsmkt | None:
        # Repetirlo no pisa la fecha: archivar uno archivado conserva la primera.
        return self._cambiar_archivo(adjunto_id, archivar=True)

    def desarchivar_adjunto(self, adjunto_id: int) -> AdjuntoWhatsmkt | None:
        return self._cambiar_archivo(adjunto_id, archivar=False)

    def _cambiar_archivo(self, adjunto_id: int, archivar: bool) -> AdjuntoWhatsmkt | None:
        consulta = update(_ADJUNTO).where(_ADJUNTO.c.id == adjunto_id)
        if archivar:
            consulta = consulta.where(_ADJUNTO.c.archivado_en.is_(None))
        valor = func.clock_timestamp() if archivar else None
        with self._engine.begin() as cx:
            cx.execute(consulta.values(archivado_en=valor))
            fila = cx.execute(
                select(*_SIN_CONTENIDO).where(_ADJUNTO.c.id == adjunto_id)
            ).one_or_none()
        return _adjunto(fila) if fila else None

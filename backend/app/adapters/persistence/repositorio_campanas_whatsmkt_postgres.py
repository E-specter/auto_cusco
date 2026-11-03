"""Campanas de WhatsMKT sobre PostgreSQL (T-WM-B4b1).

El lote se crea entero en una sola transaccion: el lote, cada campana con su archivo, sus filas y
sus exclusiones, y las exclusiones que quedan fuera de todas. Al terminar, la version del texto y
la de la definicion que se usaron quedan marcadas como usadas (ya no se modifican).
"""

from collections.abc import Iterable, Sequence
from datetime import date, time, timedelta
from typing import Any

from sqlalchemy import Connection, Engine, delete, exists, func, insert, select, update
from sqlalchemy.engine import Row

from app.adapters.persistence.modelos import (
    DefinicionCargaVersion,
    TextoGuardadoVersion,
    WhatsmktArchivo,
    WhatsmktCampana,
    WhatsmktExclusion,
    WhatsmktFilaCargada,
    WhatsmktLote,
    WhatsmktReporte,
    WhatsmktReporteFila,
)
from app.core.entities.whatsmkt import CodigoWhatsmkt, ExclusionContacto, ModoCampana, TipoEnvio
from app.core.entities.whatsmkt_campana import (
    ArchivoGuardado,
    CampanaNueva,
    CampanaWhatsmkt,
    EstadoCampana,
    HorarioElegido,
    LoteCreado,
    LoteNuevo,
    PaginaCampanas,
    PaginaExclusiones,
)
from app.core.entities.whatsmkt_informe import (
    FilaCargadaWhatsmkt,
    InformeWhatsmkt,
    ReporteGuardado,
    ReporteNuevo,
)
from app.core.ports.repositorio_campanas_whatsmkt_port import RepositorioCampanasWhatsmktPort

_LOTE = WhatsmktLote.__table__
_CAMPANA = WhatsmktCampana.__table__
_ARCHIVO = WhatsmktArchivo.__table__
_FILA = WhatsmktFilaCargada.__table__
_EXCLUSION = WhatsmktExclusion.__table__
_REPORTE = WhatsmktReporte.__table__
_REPORTE_FILA = WhatsmktReporteFila.__table__
_TEXTO_VERSION = TextoGuardadoVersion.__table__
_DEFINICION_VERSION = DefinicionCargaVersion.__table__
_TAMANO_DE_LOTE = 1_000  # filas por INSERT


def _en_lotes(valores: Sequence[dict[str, Any]]) -> Iterable[Sequence[dict[str, Any]]]:
    for desde in range(0, len(valores), _TAMANO_DE_LOTE):
        yield valores[desde : desde + _TAMANO_DE_LOTE]


def _insertar(cx: Connection, tabla, valores: Sequence[dict[str, Any]]) -> None:
    for lote in _en_lotes(valores):
        cx.execute(insert(tabla), list(lote))


def _horario(h: HorarioElegido) -> dict[str, str]:
    return {
        "nombre": h.nombre,
        "inicio": h.inicio.strftime("%H:%M"),
        "fin": h.fin.strftime("%H:%M"),
    }


def _valores_campana(lote_id: int, c: CampanaNueva) -> dict[str, Any]:
    return {
        "lote_id": lote_id,
        "nombre": c.nombre,
        "segmento": c.segmento,
        "segmento_etiqueta": c.segmento_etiqueta,
        "definicion_id": c.definicion_id,
        "definicion_nombre": c.definicion_nombre,
        "definicion_version": c.definicion_version,
        "texto_guardado_id": c.texto_guardado_id,
        "texto_version": c.texto_version,
        "mensaje_texto": c.mensaje_texto,
        "whatsapp_contacto": c.whatsapp_contacto,
        "fecha_corte": c.fecha_corte,
        "filtros": list(c.filtros),
        "orden": c.orden,
        "cantidad_pedida": c.cantidad_pedida,
        "fecha_envio": c.fecha_envio,
        "horarios": [_horario(h) for h in c.horarios],
        "lo_antes_posible": c.lo_antes_posible,
        "tipo_envio": c.tipo_envio.value,
        "foto_id": c.foto_id,
        "adjunto_id": c.adjunto_id,
        "etiqueta_vcard": c.etiqueta_vcard,
        "cantidad": c.cantidad,
        "productos": c.productos,
        "supervisores": list(c.supervisores),
    }


def _valores_exclusion(
    lote_id: int, campana_id: int | None, exclusiones: Iterable[ExclusionContacto]
) -> list[dict[str, Any]]:
    return [
        {
            "lote_id": lote_id,
            "campana_id": campana_id,
            "fila": e.fila,
            "pagare": e.pagare,
            "codigo": e.codigo.value,
            "detalle": e.detalle,
            "macro": e.macro,
            "etiqueta": e.etiqueta,
        }
        for e in exclusiones
    ]


def _campana(fila: Row) -> CampanaWhatsmkt:
    return CampanaWhatsmkt(
        id=fila.id,
        lote_id=fila.lote_id,
        nombre=fila.nombre,
        segmento=fila.segmento,
        segmento_etiqueta=fila.segmento_etiqueta,
        definicion_id=fila.definicion_id,
        definicion_nombre=fila.definicion_nombre,
        definicion_version=fila.definicion_version,
        texto_guardado_id=fila.texto_guardado_id,
        texto_version=fila.texto_version,
        mensaje_texto=fila.mensaje_texto,
        whatsapp_contacto=fila.whatsapp_contacto,
        fecha_corte=fila.fecha_corte,
        filtros=tuple(fila.filtros),
        orden=fila.orden,
        cantidad_pedida=fila.cantidad_pedida,
        fecha_envio=fila.fecha_envio,
        horarios=tuple(
            HorarioElegido(
                h["nombre"], time.fromisoformat(h["inicio"]), time.fromisoformat(h["fin"])
            )
            for h in fila.horarios
        ),
        lo_antes_posible=fila.lo_antes_posible,
        tipo_envio=TipoEnvio(fila.tipo_envio),
        foto_id=fila.foto_id,
        adjunto_id=fila.adjunto_id,
        etiqueta_vcard=fila.etiqueta_vcard,
        cantidad=fila.cantidad,
        productos=fila.productos,
        supervisores=tuple(fila.supervisores),
        creado_en=fila.creado_en,
        descartada_en=fila.descartada_en,
        archivo_nombre=fila.archivo_nombre,
        archivo_tamano=fila.archivo_tamano,
        con_informe=fila.con_informe,
    )


def _mes_siguiente(primero: date) -> date:
    return (primero.replace(day=28) + timedelta(days=4)).replace(day=1)


def consulta_de_campanas():
    """Las campanas con el nombre y el tamano de su archivo (sin sus bytes)."""
    return select(
        *_CAMPANA.c,
        _ARCHIVO.c.nombre.label("archivo_nombre"),
        _ARCHIVO.c.tamano.label("archivo_tamano"),
        exists().where(_REPORTE.c.campana_id == _CAMPANA.c.id).label("con_informe"),
    ).join(_ARCHIVO, _ARCHIVO.c.campana_id == _CAMPANA.c.id)


class RepositorioCampanasWhatsmktPostgres(RepositorioCampanasWhatsmktPort):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def crear_lote(self, lote: LoteNuevo) -> LoteCreado:
        with self._engine.begin() as cx:
            lote_id = cx.execute(
                insert(_LOTE).values(modo=lote.modo.value).returning(_LOTE.c.id)
            ).scalar_one()
            ids = [self._crear_campana(cx, lote_id, c) for c in lote.campanas]
            _insertar(
                cx, _EXCLUSION, _valores_exclusion(lote_id, None, lote.exclusiones_sin_campana)
            )
            for c in lote.campanas:
                self._marcar_usadas(cx, c)
            filas = cx.execute(
                consulta_de_campanas().where(_CAMPANA.c.id.in_(ids)).order_by(_CAMPANA.c.id)
            ).all()
        return LoteCreado(lote_id, ModoCampana(lote.modo), tuple(_campana(f) for f in filas))

    @staticmethod
    def _crear_campana(cx: Connection, lote_id: int, c: CampanaNueva) -> int:
        campana_id = cx.execute(
            insert(_CAMPANA).values(**_valores_campana(lote_id, c)).returning(_CAMPANA.c.id)
        ).scalar_one()
        cx.execute(
            insert(_ARCHIVO).values(
                campana_id=campana_id,
                nombre=c.archivo_nombre,
                contenido=c.archivo_contenido,
                tamano=len(c.archivo_contenido),
                filas=c.cantidad,
            )
        )
        _insertar(
            cx,
            _FILA,
            [
                {
                    "campana_id": campana_id,
                    "posicion": f.posicion,
                    "numero": f.numero,
                    "pagare": f.pagare,
                    "supervision": f.supervision,
                    "macros": list(f.macros),
                }
                for f in c.filas
            ],
        )
        _insertar(cx, _EXCLUSION, _valores_exclusion(lote_id, campana_id, c.exclusiones))
        return campana_id

    @staticmethod
    def _marcar_usadas(cx: Connection, c: CampanaNueva) -> None:
        """La version del texto y la de la definicion que se usaron ya no se modifican."""
        cx.execute(
            update(_TEXTO_VERSION)
            .where(
                _TEXTO_VERSION.c.texto_id == c.texto_guardado_id,
                _TEXTO_VERSION.c.numero == c.texto_version,
                _TEXTO_VERSION.c.usada_en.is_(None),
            )
            .values(usada_en=func.clock_timestamp())
        )
        cx.execute(
            update(_DEFINICION_VERSION)
            .where(
                _DEFINICION_VERSION.c.definicion_id == c.definicion_id,
                _DEFINICION_VERSION.c.numero == c.definicion_version,
                _DEFINICION_VERSION.c.usada_en.is_(None),
            )
            .values(usada_en=func.clock_timestamp())
        )

    def obtener_archivo(self, campana_id: int) -> ArchivoGuardado | None:
        with self._engine.connect() as cx:
            fila = cx.execute(
                select(_ARCHIVO.c.nombre, _ARCHIVO.c.contenido).where(
                    _ARCHIVO.c.campana_id == campana_id
                )
            ).one_or_none()
        return None if fila is None else ArchivoGuardado(fila.nombre, bytes(fila.contenido))

    def listar(
        self,
        limite: int,
        desplazamiento: int,
        lote_id: int | None = None,
        mes: date | None = None,
        estado: EstadoCampana = EstadoCampana.ACTIVAS,
    ) -> PaginaCampanas:
        descartada = _CAMPANA.c.descartada_en.is_not(None)
        filtros = [descartada if estado is EstadoCampana.DESCARTADAS else ~descartada]
        if lote_id is not None:
            filtros.append(_CAMPANA.c.lote_id == lote_id)
        if mes is not None:
            primero = mes.replace(day=1)
            filtros += [
                _CAMPANA.c.fecha_envio >= primero,
                _CAMPANA.c.fecha_envio < _mes_siguiente(primero),
            ]
        with self._engine.connect() as cx:
            total = cx.execute(
                select(func.count()).select_from(_CAMPANA).where(*filtros)
            ).scalar_one()
            sin_informe = ~exists().where(_REPORTE.c.campana_id == _CAMPANA.c.id)
            activas, descartadas, pendientes = cx.execute(
                select(
                    func.count().filter(~descartada),
                    func.count().filter(descartada),
                    func.count().filter(~descartada & sin_informe),
                ).select_from(_CAMPANA)
            ).one()
            filas = cx.execute(
                consulta_de_campanas()
                .where(*filtros)
                .order_by(_CAMPANA.c.creado_en.desc(), _CAMPANA.c.id.desc())
                .limit(limite)
                .offset(desplazamiento)
            ).all()
        return PaginaCampanas(
            total, tuple(_campana(f) for f in filas), activas, descartadas, pendientes
        )

    def obtener(self, campana_id: int) -> CampanaWhatsmkt | None:
        with self._engine.connect() as cx:
            fila = cx.execute(
                consulta_de_campanas().where(_CAMPANA.c.id == campana_id)
            ).one_or_none()
        return None if fila is None else _campana(fila)

    def modo_del_lote(self, lote_id: int) -> ModoCampana:
        with self._engine.connect() as cx:
            return ModoCampana(
                cx.execute(select(_LOTE.c.modo).where(_LOTE.c.id == lote_id)).scalar_one()
            )

    def listar_exclusiones(
        self, lote_id: int, campana_id: int | None, limite: int, desplazamiento: int
    ) -> PaginaExclusiones:
        donde = (
            _EXCLUSION.c.lote_id == lote_id,
            _EXCLUSION.c.campana_id.is_(None)
            if campana_id is None
            else _EXCLUSION.c.campana_id == campana_id,
        )
        with self._engine.connect() as cx:
            total = cx.execute(
                select(func.count()).select_from(_EXCLUSION).where(*donde)
            ).scalar_one()
            filas = cx.execute(
                select(*_EXCLUSION.c)
                .where(*donde)
                .order_by(_EXCLUSION.c.fila, _EXCLUSION.c.id)
                .limit(limite)
                .offset(desplazamiento)
            ).all()
        return PaginaExclusiones(
            total,
            tuple(
                ExclusionContacto(
                    fila=f.fila,
                    pagare=f.pagare,
                    codigo=CodigoWhatsmkt(f.codigo),
                    detalle=f.detalle,
                    macro=f.macro,
                    etiqueta=f.etiqueta,
                )
                for f in filas
            ),
        )

    def descartar(self, campana_id: int) -> CampanaWhatsmkt | None:
        return self._cambiar_descarte(campana_id, func.now(), _CAMPANA.c.descartada_en.is_(None))

    def restaurar(self, campana_id: int) -> CampanaWhatsmkt | None:
        return self._cambiar_descarte(campana_id, None, _CAMPANA.c.descartada_en.is_not(None))

    def _cambiar_descarte(self, campana_id: int, valor, solo_si) -> CampanaWhatsmkt | None:
        with self._engine.begin() as cx:
            cx.execute(
                update(_CAMPANA)
                .where(_CAMPANA.c.id == campana_id, solo_si)
                .values(descartada_en=valor)
            )
            fila = cx.execute(
                consulta_de_campanas().where(_CAMPANA.c.id == campana_id)
            ).one_or_none()
        return None if fila is None else _campana(fila)

    def eliminar_descartada(self, campana_id: int) -> bool:
        with self._engine.begin() as cx:
            lote_id = cx.execute(
                select(_CAMPANA.c.lote_id)
                .where(_CAMPANA.c.id == campana_id, _CAMPANA.c.descartada_en.is_not(None))
                .with_for_update()
            ).scalar_one_or_none()
            if lote_id is None:
                return False
            # Dos eliminaciones del mismo lote a la vez se turnan: la ultima ve que no queda nadie.
            cx.execute(select(_LOTE.c.id).where(_LOTE.c.id == lote_id).with_for_update())
            cx.execute(delete(_CAMPANA).where(_CAMPANA.c.id == campana_id))
            quedan = cx.execute(
                select(func.count()).select_from(_CAMPANA).where(_CAMPANA.c.lote_id == lote_id)
            ).scalar_one()
            if quedan == 0:
                cx.execute(delete(_LOTE).where(_LOTE.c.id == lote_id))
        return True

    def obtener_reporte(self, campana_id: int) -> ReporteGuardado | None:
        with self._engine.connect() as cx:
            fila = cx.execute(
                select(*_REPORTE.c).where(_REPORTE.c.campana_id == campana_id)
            ).one_or_none()
            if fila is None:
                return None
            numeros = cx.execute(
                select(_REPORTE_FILA.c.numero)
                .where(_REPORTE_FILA.c.reporte_id == fila.id)
                .order_by(_REPORTE_FILA.c.posicion)
            ).scalars()
            return _reporte(fila, tuple(numeros))

    def reemplazar_reporte(self, campana_id: int, reporte: ReporteNuevo) -> ReporteGuardado:
        informe = reporte.informe
        with self._engine.begin() as cx:
            cx.execute(delete(_REPORTE).where(_REPORTE.c.campana_id == campana_id))
            fila = cx.execute(
                insert(_REPORTE)
                .values(
                    campana_id=campana_id,
                    archivo_nombre=reporte.archivo_nombre,
                    huella=reporte.huella,
                    fecha_informada=informe.fecha_informada,
                    total_informado=informe.total_informado,
                    campana_informada=informe.campana,
                    tipo_envio_informado=informe.tipo_envio,
                )
                .returning(*_REPORTE.c)
            ).one()
            _insertar(
                cx,
                _REPORTE_FILA,
                [
                    {"reporte_id": fila.id, "posicion": i, "numero": n}
                    for i, n in enumerate(informe.numeros, 1)
                ],
            )
        return _reporte(fila, informe.numeros)

    def filas_cargadas(self, campana_id: int) -> tuple[FilaCargadaWhatsmkt, ...]:
        with self._engine.connect() as cx:
            filas = cx.execute(
                select(_FILA.c.numero, _FILA.c.pagare, _FILA.c.supervision)
                .where(_FILA.c.campana_id == campana_id)
                .order_by(_FILA.c.posicion)
            ).all()
        return tuple(FilaCargadaWhatsmkt(f.numero, f.pagare, f.supervision) for f in filas)


def _reporte(fila: Row, numeros: tuple[str, ...]) -> ReporteGuardado:
    return ReporteGuardado(
        id=fila.id,
        campana_id=fila.campana_id,
        archivo_nombre=fila.archivo_nombre,
        huella=fila.huella,
        importado_en=fila.importado_en,
        informe=InformeWhatsmkt(
            fecha_informada=fila.fecha_informada,
            total_informado=fila.total_informado,
            campana=fila.campana_informada,
            tipo_envio=fila.tipo_envio_informado,
            numeros=numeros,
        ),
    )

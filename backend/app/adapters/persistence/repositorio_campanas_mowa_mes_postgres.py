"""Campanas de MOWA MES y sus reportes de enviados, sobre PostgreSQL.

La creacion va entera en una transaccion: si algo falla no queda una campana
sin archivos ni una version de speech marcada sin campana. La version se
bloquea con FOR UPDATE antes de comparar su huella, asi una edicion concurrente
no puede colarse entre la comprobacion y la marca de uso.
"""

from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime
from itertools import islice
from typing import Any

from sqlalchemy import Engine, delete, func, insert, select, update
from sqlalchemy.engine import Connection, Row

from app.adapters.persistence.modelos import (
    MowaMesArchivo,
    MowaMesCampana,
    MowaMesExclusion,
    MowaMesFilaCargada,
    MowaMesReporte,
    MowaMesReporteFila,
    MowaMesSpeechVersion,
)
from app.core.entities.mowa_mes import (
    CodigoMowaMes,
    PartesSegmento,
    Programacion,
    Segmento,
    SpeechNoEncontrado,
)
from app.core.entities.mowa_mes_campana import (
    ArchivoCarga,
    ArchivoResumen,
    CampanaArmada,
    CampanaRegistrada,
    Exclusion,
    FilaCarga,
    Herramientas,
    Salida,
    SpeechCambiado,
    SupervisorAsignado,
    TipoCarga,
)
from app.core.entities.mowa_mes_reporte import FilaReporte, ReporteImportado
from app.core.ports.repositorio_campanas_mowa_mes_port import RepositorioCampanasMowaMesPort
from app.core.services.plataformas.mowa_mes.campana import huella_speech

_CAMPANA = MowaMesCampana.__table__
_ARCHIVO = MowaMesArchivo.__table__
_FILA = MowaMesFilaCargada.__table__
_EXCLUSION = MowaMesExclusion.__table__
_REPORTE = MowaMesReporte.__table__
_REPORTE_FILA = MowaMesReporteFila.__table__
_SPEECH = MowaMesSpeechVersion.__table__
_LOTE = 5_000


def _lotes(valores: Iterable[dict[str, Any]]) -> Iterable[list[dict[str, Any]]]:
    iterador = iter(valores)
    while lote := list(islice(iterador, _LOTE)):
        yield lote


def _insertar(cx: Connection, tabla, valores: Iterable[dict[str, Any]]) -> None:
    for lote in _lotes(valores):
        cx.execute(insert(tabla), lote)


def _valores_campana(armada: CampanaArmada) -> dict[str, Any]:
    p = armada.peticion
    return {
        "fecha_corte": p.fecha_corte,
        "filtros": list(p.filtros),
        "orden": p.orden,
        "cantidad": p.cantidad,
        "seleccion_id": p.seleccion_id,
        "tipo_carga": p.tipo_carga.value,
        "descripcion": armada.descripcion,
        "salida": p.salida.value,
        "herramientas": {
            "keyword": p.herramientas.keyword,
            "respuesta_automatica": p.herramientas.respuesta_automatica,
            "blacklist_indecopi": p.herramientas.blacklist_indecopi,
            "speech_optimizado": p.herramientas.speech_optimizado,
        },
        "programacion": p.programacion.value,
        "envios": [momento.isoformat() for momento in p.envios],
        "fecha_generacion": armada.fecha_generacion,
        "fecha_envio": armada.fecha_envio,
        "mes_imputacion": armada.consumo.mes,
        "speech_version_id": armada.speech.id,
        "speech_huella": armada.speech_huella,
        "whatsapp": armada.whatsapp,
        "supervisores": [
            {"numero": s.numero, "procedencia": s.procedencia, "documento": s.documento}
            for s in armada.supervisores
        ],
        "disponibles": armada.disponibles,
        "evaluados": armada.evaluados,
        "productos_cargados": armada.productos_cargados,
        "supervision_cargados": armada.supervision_cargados,
        "total_cargados": armada.total_cargados,
        "excluidos": len(armada.exclusiones),
        "advertencias": sum(armada.advertencias_por_codigo().values()),
        "confirmo_limite": armada.peticion.confirmar_limite,
    }


def _filas_cargadas(
    campana_id: int, filas: Sequence[FilaCarga], archivos: Sequence[ArchivoCarga]
) -> Iterable[dict[str, Any]]:
    posicion = 0
    for archivo in archivos:
        for fila in filas[posicion : posicion + archivo.filas]:
            posicion += 1
            yield {
                "campana_id": campana_id,
                "posicion": posicion,
                "archivo": archivo.numero,
                "numero": fila.numero,
                "dni": fila.dni,
                "mensaje": fila.mensaje,
                "supervision": fila.supervision,
                "pagare": fila.pagare,
                "segmento": fila.segmento.value if fila.segmento else None,
                "advertencias": [codigo.value for codigo in fila.advertencias],
            }


def _campana(fila: Row, archivos: Sequence[ArchivoResumen]) -> CampanaRegistrada:
    return CampanaRegistrada(
        id=fila.id,
        creado_en=fila.creado_en,
        fecha_corte=fila.fecha_corte,
        filtros=tuple(fila.filtros),
        orden=fila.orden,
        cantidad=fila.cantidad,
        seleccion_id=fila.seleccion_id,
        tipo_carga=TipoCarga(fila.tipo_carga),
        descripcion=fila.descripcion,
        salida=Salida(fila.salida),
        herramientas=Herramientas(**fila.herramientas),
        programacion=Programacion(fila.programacion),
        envios=tuple(datetime.fromisoformat(momento) for momento in fila.envios),
        fecha_envio=fila.fecha_envio,
        speech_id=fila.speech_version_id,
        speech_nombre=fila.speech_nombre,
        whatsapp=fila.whatsapp,
        supervisores=tuple(SupervisorAsignado(**s) for s in fila.supervisores),
        disponibles=fila.disponibles,
        evaluados=fila.evaluados,
        productos_cargados=fila.productos_cargados,
        supervision_cargados=fila.supervision_cargados,
        excluidos=fila.excluidos,
        advertencias=fila.advertencias,
        confirmo_limite=fila.confirmo_limite,
        archivos=tuple(archivos),
    )


class RepositorioCampanasMowaMesPostgres(RepositorioCampanasMowaMesPort):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def cargados_en_mes(self, mes: date) -> int:
        consulta = select(func.coalesce(func.sum(_CAMPANA.c.total_cargados), 0)).where(
            _CAMPANA.c.mes_imputacion == mes
        )
        with self._engine.connect() as cx:
            return int(cx.execute(consulta).scalar_one())

    def crear(self, armada: CampanaArmada, archivos: Sequence[ArchivoCarga]) -> CampanaRegistrada:
        with self._engine.begin() as cx:
            version = cx.execute(
                select(_SPEECH.c.partes).where(_SPEECH.c.id == armada.speech.id).with_for_update()
            ).one_or_none()
            if version is None:
                raise SpeechNoEncontrado(armada.speech.id)
            partes = tuple(
                PartesSegmento(Segmento(p["segmento"]), p["parte_1"], p["parte_2"])
                for p in version.partes
            )
            if huella_speech(partes) != armada.speech_huella:
                raise SpeechCambiado(armada.speech.id)
            cx.execute(
                update(_SPEECH)
                .where(_SPEECH.c.id == armada.speech.id, _SPEECH.c.usada_en.is_(None))
                .values(usada_en=func.clock_timestamp())
            )
            campana_id = cx.execute(
                insert(_CAMPANA).values(**_valores_campana(armada)).returning(_CAMPANA.c.id)
            ).scalar_one()
            _insertar(
                cx,
                _ARCHIVO,
                (
                    {
                        "campana_id": campana_id,
                        "numero": a.numero,
                        "filas": a.filas,
                        "supervision": a.supervision,
                        "bytes": a.bytes,
                        "contenido": a.contenido,
                    }
                    for a in archivos
                ),
            )
            _insertar(cx, _FILA, _filas_cargadas(campana_id, armada.filas, archivos))
            _insertar(
                cx,
                _EXCLUSION,
                (
                    {"campana_id": campana_id, "pagare": e.pagare, "orden": i, "codigo": e.codigo}
                    for i, e in enumerate(armada.exclusiones, start=1)
                ),
            )
        registrada = self.obtener(campana_id)
        assert registrada is not None
        return registrada

    def _consulta_campanas(self):
        return select(*_CAMPANA.c, _SPEECH.c.nombre.label("speech_nombre")).join(
            _SPEECH, _SPEECH.c.id == _CAMPANA.c.speech_version_id
        )

    def _archivos(self, cx: Connection, ids: Sequence[int]) -> dict[int, list[ArchivoResumen]]:
        por_campana: dict[int, list[ArchivoResumen]] = {i: [] for i in ids}
        if not ids:
            return por_campana
        filas = cx.execute(
            select(
                _ARCHIVO.c.campana_id,
                _ARCHIVO.c.numero,
                _ARCHIVO.c.filas,
                _ARCHIVO.c.supervision,
                _ARCHIVO.c.bytes,
            )
            .where(_ARCHIVO.c.campana_id.in_(ids))
            .order_by(_ARCHIVO.c.campana_id, _ARCHIVO.c.numero)
        )
        for fila in filas:
            por_campana[fila.campana_id].append(
                ArchivoResumen(fila.numero, fila.filas, fila.supervision, fila.bytes)
            )
        return por_campana

    def listar(self, limite: int, desplazamiento: int) -> tuple[int, list[CampanaRegistrada]]:
        with self._engine.connect() as cx:
            total = cx.execute(select(func.count()).select_from(_CAMPANA)).scalar_one()
            filas = cx.execute(
                self._consulta_campanas()
                .order_by(_CAMPANA.c.creado_en.desc(), _CAMPANA.c.id.desc())
                .limit(limite)
                .offset(desplazamiento)
            ).all()
            archivos = self._archivos(cx, [fila.id for fila in filas])
        return total, [_campana(fila, archivos[fila.id]) for fila in filas]

    def obtener(self, campana_id: int) -> CampanaRegistrada | None:
        with self._engine.connect() as cx:
            fila = cx.execute(
                self._consulta_campanas().where(_CAMPANA.c.id == campana_id)
            ).one_or_none()
            if fila is None:
                return None
            archivos = self._archivos(cx, [campana_id])
        return _campana(fila, archivos[campana_id])

    def exclusiones(
        self, campana_id: int, codigo: CodigoMowaMes | None, limite: int, desplazamiento: int
    ) -> tuple[int, list[Exclusion]]:
        condiciones = [_EXCLUSION.c.campana_id == campana_id]
        if codigo is not None:
            condiciones.append(_EXCLUSION.c.codigo == codigo.value)
        with self._engine.connect() as cx:
            total = cx.execute(
                select(func.count()).select_from(_EXCLUSION).where(*condiciones)
            ).scalar_one()
            filas = cx.execute(
                select(_EXCLUSION.c.pagare, _EXCLUSION.c.codigo)
                .where(*condiciones)
                .order_by(_EXCLUSION.c.orden)
                .limit(limite)
                .offset(desplazamiento)
            ).all()
        return total, [Exclusion(fila.pagare, CodigoMowaMes(fila.codigo)) for fila in filas]

    def archivo(self, campana_id: int, numero: int) -> ArchivoCarga | None:
        with self._engine.connect() as cx:
            fila = cx.execute(
                select(_ARCHIVO).where(
                    _ARCHIVO.c.campana_id == campana_id, _ARCHIVO.c.numero == numero
                )
            ).one_or_none()
        if fila is None:
            return None
        return ArchivoCarga(fila.numero, fila.filas, fila.supervision, bytes(fila.contenido))

    def filas_cargadas(self, campana_id: int) -> list[FilaCarga]:
        with self._engine.connect() as cx:
            filas = cx.execute(
                select(_FILA).where(_FILA.c.campana_id == campana_id).order_by(_FILA.c.posicion)
            )
            return [
                FilaCarga(
                    numero=fila.numero,
                    mensaje=fila.mensaje,
                    dni=fila.dni,
                    supervision=fila.supervision,
                    pagare=fila.pagare,
                    segmento=Segmento(fila.segmento) if fila.segmento else None,
                    advertencias=tuple(CodigoMowaMes(codigo) for codigo in fila.advertencias),
                )
                for fila in filas
            ]

    # --- Reporte de enviados ------------------------------------------

    def reportes_ya_importados(self, mes_ids: Sequence[int]) -> tuple[int, ...]:
        if not mes_ids:
            return ()
        with self._engine.connect() as cx:
            existentes = cx.execute(
                select(_REPORTE.c.mes_id)
                .where(_REPORTE.c.mes_id.in_(list(mes_ids)))
                .order_by(_REPORTE.c.mes_id)
            ).scalars()
            return tuple(existentes)

    def guardar_reportes(
        self,
        campana_id: int,
        nombre_archivo: str,
        filas_por_id: Mapping[int, Sequence[FilaReporte]],
    ) -> None:
        with self._engine.begin() as cx:
            cx.execute(delete(_REPORTE).where(_REPORTE.c.mes_id.in_(list(filas_por_id))))
            for mes_id, filas in sorted(filas_por_id.items()):
                reporte_id = cx.execute(
                    insert(_REPORTE)
                    .values(
                        campana_id=campana_id,
                        mes_id=mes_id,
                        nombre_archivo=nombre_archivo,
                        filas=len(filas),
                    )
                    .returning(_REPORTE.c.id)
                ).scalar_one()
                _insertar(
                    cx,
                    _REPORTE_FILA,
                    (
                        {
                            "reporte_id": reporte_id,
                            "fila": f.fila,
                            "celular": f.celular,
                            "mensaje": f.mensaje,
                            "fecha_envio": f.fecha_envio,
                            "dni": f.dni,
                            "estado": f.estado,
                            "salida": f.salida,
                            "usuario": f.usuario,
                        }
                        for f in filas
                    ),
                )

    def reportes(self, campana_id: int) -> list[ReporteImportado]:
        with self._engine.connect() as cx:
            filas = cx.execute(
                select(_REPORTE)
                .where(_REPORTE.c.campana_id == campana_id)
                .order_by(_REPORTE.c.mes_id)
            ).all()
        return [
            ReporteImportado(fila.mes_id, fila.nombre_archivo, fila.filas, fila.importado_en)
            for fila in filas
        ]

    def filas_reporte(self, campana_id: int) -> list[FilaReporte]:
        consulta = (
            select(_REPORTE.c.mes_id, *_REPORTE_FILA.c)
            .join(_REPORTE, _REPORTE.c.id == _REPORTE_FILA.c.reporte_id)
            .where(_REPORTE.c.campana_id == campana_id)
            .order_by(_REPORTE.c.mes_id, _REPORTE_FILA.c.fila)
        )
        with self._engine.connect() as cx:
            return [
                FilaReporte(
                    fila=f.fila,
                    mes_id=f.mes_id,
                    celular=f.celular,
                    mensaje=f.mensaje,
                    fecha_envio=f.fecha_envio,
                    dni=f.dni,
                    estado=f.estado,
                    salida=f.salida,
                    usuario=f.usuario,
                )
                for f in cx.execute(consulta)
            ]

"""Caso de uso: registrar, procesar y elegir versiones de sabana (RF-01 a RF-03).

Implementa el flujo de docs/versionado-sabanas.md, seccion 4.4:

1. `registrar_carga`: crea la version en cola junto con su archivo original.
2. `procesar_carga`: lee, normaliza y guarda filas e incidencias en una sola
   transaccion. Si la fecha no tenia vigente, la nueva queda vigente (V-3);
   si ya tenia, la vigente se mantiene y el resultado pide confirmacion (V-4, C-1).
3. `asignar_vigente`: cambia la version vigente de una fecha (V-7).

No depende de infraestructura: solo de los puertos de lectura y persistencia.
"""

import hashlib
import logging
import math
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import replace
from datetime import date
from typing import Any

from app.core.entities.borrador import BorradorNoEncontrado, MapeoConProblemas
from app.core.entities.carga import (
    CargaDetalle,
    CargaNoEncontrada,
    CargaNoProcesable,
    CargaRegistrada,
    DatosCarga,
    EliminacionNoPermitida,
    EstadoCarga,
    EventoAuditoria,
    FilaParaGuardar,
    FormatoCarga,
    NuevaCarga,
    ResultadoProcesamiento,
    ResumenProcesamiento,
    VigenciaNoPermitida,
)
from app.core.entities.lectura_tabla import CodigoAdvertenciaLectura, TablaLeida
from app.core.entities.mapeador import Asignacion
from app.core.entities.sabana import (
    HOJA_DATOS_POR_DEFECTO,
    ArchivoSabanaError,
    Incidencia,
    MapeoCabeceras,
    Severidad,
)
from app.core.ports.lector_tabla_port import LectorTablaPort
from app.core.ports.repositorio_cargas_port import RepositorioCargasPort
from app.core.services.borradores_carga.servicio import Reloj, ahora_utc, opciones_de_lectura
from app.core.services.ingesta_sabana.cabeceras import (
    describir_mapeo,
    huella_formato,
    mapear_cabeceras,
)
from app.core.services.ingesta_sabana.catalogo import CATALOGO_SABANA
from app.core.services.ingesta_sabana.mapeo_explicito import (
    MapeoGuardadoInvalido,
    mapeo_desde_asignaciones,
)
from app.core.services.ingesta_sabana.normalizador import normalizar_fila
from app.core.services.mapeador.serializacion import (
    analisis_desde_dict,
    asignaciones_a_dict,
    recordados_de,
)
from app.core.services.mapeador.validacion import resolver_asignaciones, validar

logger = logging.getLogger(__name__)


def _huella(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


def _valor_json(valor: Any) -> Any:
    if valor is None or isinstance(valor, (str, bool, int)):
        return valor
    if isinstance(valor, float):
        return valor if math.isfinite(valor) else str(valor)
    if isinstance(valor, date):  # incluye datetime
        return valor.isoformat()
    return str(valor)


def _extras(celdas: Sequence[Any], desconocidas: dict[int, str]) -> dict[str, Any] | None:
    """Valores de columnas no catalogadas, para no perder informacion."""
    extras: dict[str, Any] = {}
    for indice, cabecera in desconocidas.items():
        valor = celdas[indice] if indice < len(celdas) else None
        if valor is None or (isinstance(valor, str) and valor.strip() == ""):
            continue
        clave = cabecera if cabecera not in extras else f"{cabecera} (columna {indice + 1})"
        extras[clave] = _valor_json(valor)
    return extras or None


def _contar_incidencias(incidencias: Iterable[Incidencia], resumen: ResumenProcesamiento) -> None:
    conteo = dict.fromkeys(Severidad, 0)
    for incidencia in incidencias:
        conteo[incidencia.severidad] += 1
    resumen.incidencias_error = conteo[Severidad.ERROR]
    resumen.incidencias_advertencia = conteo[Severidad.ADVERTENCIA]
    resumen.incidencias_info = conteo[Severidad.INFO]


def _filas_para_guardar(
    hoja: TablaLeida,
    mapeo: MapeoCabeceras,
    incidencias: list[Incidencia],
    resumen: ResumenProcesamiento,
) -> Iterator[FilaParaGuardar]:
    """Normaliza fila por fila mientras el repositorio las va guardando.

    Acumula las incidencias en `incidencias` y los contadores en `resumen`,
    por eso ambos quedan completos solo cuando el iterador se consumio entero.
    """
    vistos: set[str] = set()
    for cruda in hoja.filas:
        fila = normalizar_fila(cruda.celdas, mapeo, cruda.numero_fila)
        incidencias.extend(fila.incidencias)
        if not fila.ingestable:
            continue
        if fila.clave in vistos:
            # Regla V-10 (confirmada): se conserva la primera aparicion del pagare.
            incidencias.append(
                Incidencia(
                    cruda.numero_fila,
                    "pagare",
                    "pagare_repetido",
                    Severidad.ERROR,
                    "Pagare ya presente en una fila anterior; se conserva la primera aparicion",
                    fila.clave,
                )
            )
            continue
        vistos.add(fila.clave)
        resumen.filas_ingestadas += 1
        yield FilaParaGuardar(
            numero_fila=cruda.numero_fila,
            valores=fila.valores,
            extras=_extras(cruda.celdas, mapeo.desconocidas),
        )


def _incidencias_de_lectura(tabla: TablaLeida) -> list[Incidencia]:
    """Lo que el lector aviso de una fila (un JSON con un valor objeto o lista) como incidencias."""
    incidencias = []
    for aviso in tabla.advertencias:
        if aviso.codigo is CodigoAdvertenciaLectura.VALOR_NO_ESCALAR:
            incidencias.append(
                Incidencia(
                    aviso.numero_fila,
                    aviso.columna,
                    "valor_no_escalar",
                    Severidad.ADVERTENCIA,
                    "El valor es un objeto o una lista; se guardo como texto JSON",
                )
            )
    return incidencias


class IngestaSabanaService:
    def __init__(
        self,
        repositorio: RepositorioCargasPort,
        lector: LectorTablaPort,
        reloj: Reloj = ahora_utc,
    ) -> None:
        self._repositorio = repositorio
        self._lector = lector
        self._reloj = reloj

    # ---------- 1. registrar ----------

    def buscar_versiones_identicas(self, fecha_corte: date, contenido: bytes) -> list[int]:
        """V-6: versiones de la fecha con el mismo archivo, para avisar antes de subirlo."""
        with self._repositorio.transaccion() as sesion:
            return sesion.versiones_con_huella(fecha_corte, _huella(contenido))

    def registrar_carga(
        self,
        fecha_corte: date,
        nombre_archivo: str,
        contenido: bytes,
        hoja: str = HOJA_DATOS_POR_DEFECTO,
    ) -> CargaRegistrada:
        huella = _huella(contenido)
        with self._repositorio.transaccion() as sesion:
            sesion.bloquear_fecha(fecha_corte)
            identicas = sesion.versiones_con_huella(fecha_corte, huella)
            carga = sesion.crear_carga(
                NuevaCarga(
                    fecha_corte=fecha_corte,
                    version=sesion.siguiente_version(fecha_corte),
                    nombre_archivo=nombre_archivo,
                    huella_archivo=huella,
                    tamano_bytes=len(contenido),
                    hoja=hoja,
                    opciones_lectura={"hoja": hoja},
                )
            )
            sesion.guardar_archivo(carga.id, contenido)
            sesion.auditar(
                carga,
                EventoAuditoria.CARGA_CREADA,
                detalle={"tamano_bytes": len(contenido), "versiones_identicas": identicas},
            )
        return CargaRegistrada(carga=carga, versiones_identicas=identicas)

    def registrar_desde_borrador(
        self, borrador_id: int, fecha_corte: date, asignaciones: Sequence[Asignacion]
    ) -> CargaRegistrada:
        """Confirma un borrador del mapeador (RF-60, RF-61): UNA transaccion que lo bloquea, valida
        las asignaciones contra el analisis que se mostro, crea la carga (con las asignaciones ya
        resueltas y las opciones de lectura), guarda lo recordado y borra el borrador.

        `BorradorNoEncontrado` si no existe, venció o ya se confirmo (la segunda confirmacion no lo
        encuentra) y `MapeoConProblemas`, con la lista, si las asignaciones no se pueden confirmar.
        """
        with self._repositorio.transaccion() as sesion:
            sesion.bloquear_fecha(fecha_corte)
            borrador = sesion.obtener_borrador(borrador_id, bloquear=True)
            vence = None if borrador is None else borrador.vence_en()
            if borrador is None or vence is None or self._reloj() >= vence:
                raise BorradorNoEncontrado(borrador_id)
            if borrador.catalogo_id != CATALOGO_SABANA.id:
                raise BorradorNoEncontrado(borrador_id)
            analisis = analisis_desde_dict(borrador.analisis)
            problemas = validar(asignaciones, analisis)
            if problemas:
                raise MapeoConProblemas(problemas)
            resueltas = resolver_asignaciones(asignaciones, analisis)
            contenido = sesion.contenido_de_borrador(borrador_id)
            identicas = sesion.versiones_con_huella(fecha_corte, borrador.huella)
            hoja = borrador.opciones.get("hoja") or ""
            carga = sesion.crear_carga(
                NuevaCarga(
                    fecha_corte=fecha_corte,
                    version=sesion.siguiente_version(fecha_corte),
                    nombre_archivo=borrador.nombre_archivo,
                    huella_archivo=borrador.huella,
                    tamano_bytes=borrador.tamano_bytes,
                    hoja=hoja,
                    opciones_lectura=dict(borrador.opciones),
                    asignaciones=asignaciones_a_dict(resueltas, analisis),
                )
            )
            sesion.guardar_archivo(carga.id, contenido)
            sesion.guardar_recordados(
                borrador.catalogo_id, recordados_de(resueltas, analisis), self._reloj()
            )
            sesion.borrar_borrador(borrador_id)
            sesion.auditar(
                carga,
                EventoAuditoria.CARGA_CREADA,
                detalle={
                    "tamano_bytes": borrador.tamano_bytes,
                    "versiones_identicas": identicas,
                    "desde_borrador": True,
                },
            )
        return CargaRegistrada(carga=carga, versiones_identicas=identicas)

    # ---------- 2. procesar ----------

    def procesar_carga(self, carga_id: int) -> ResultadoProcesamiento:
        with self._repositorio.transaccion() as sesion:
            carga = sesion.tomar_para_procesar(carga_id)
            if carga is None:
                if sesion.obtener_carga(carga_id) is None:
                    raise CargaNoEncontrada(carga_id)
                raise CargaNoProcesable(f"La carga {carga_id} no esta en cola")
            contenido = sesion.obtener_archivo(carga_id)

        try:
            opciones = opciones_de_lectura(carga.opciones_lectura, carga.hoja)
            hoja = self._lector.leer(contenido, carga.nombre_archivo, opciones)
        except ArchivoSabanaError as exc:
            return self._fallar(carga, str(exc))
        del contenido

        if carga.asignaciones is None:
            mapeo, origenes = mapear_cabeceras(hoja.cabeceras), None
        else:
            try:
                mapeo, origenes, _ = mapeo_desde_asignaciones(hoja.cabeceras, carga.asignaciones)
            except MapeoGuardadoInvalido as exc:
                return self._fallar(
                    carga,
                    str(exc),
                    formato=FormatoCarga(
                        fila_cabecera=hoja.fila_cabecera,
                        cabeceras_originales=[str(c) for c in hoja.cabeceras],
                        huella_formato=huella_formato(hoja.cabeceras),
                        mapeo={},
                    ),
                    resumen=ResumenProcesamiento(filas_total=len(hoja.filas)),
                )
        formato = FormatoCarga(
            fila_cabecera=hoja.fila_cabecera,
            cabeceras_originales=[str(c) for c in hoja.cabeceras],
            huella_formato=huella_formato(hoja.cabeceras),
            mapeo=describir_mapeo(mapeo, origenes),
        )
        if mapeo.bloqueante:
            return self._fallar(
                carga,
                "Falta una columna requerida del catalogo (ver incidencias)",
                incidencias=mapeo.incidencias,
                formato=formato,
                resumen=ResumenProcesamiento(filas_total=len(hoja.filas)),
            )

        incidencias = [*mapeo.incidencias, *_incidencias_de_lectura(hoja)]
        resumen = ResumenProcesamiento(filas_total=len(hoja.filas))
        try:
            with self._repositorio.transaccion() as sesion:
                sesion.bloquear_fecha(carga.fecha_corte)
                sesion.guardar_filas(
                    carga.id, _filas_para_guardar(hoja, mapeo, incidencias, resumen)
                )
                sesion.guardar_incidencias(carga.id, incidencias)
                _contar_incidencias(incidencias, resumen)
                sesion.finalizar_carga(carga.id, EstadoCarga.TERMINADA, resumen, formato)
                sesion.auditar(
                    carga,
                    EventoAuditoria.PROCESAMIENTO_TERMINADO,
                    filas_total=resumen.filas_total,
                    detalle={
                        "filas_ingestadas": resumen.filas_ingestadas,
                        "huella_formato": formato.huella_formato,
                    },
                )
                vigente_actual = sesion.id_vigente(carga.fecha_corte)
                queda_vigente = vigente_actual is None
                if queda_vigente:
                    sesion.marcar_vigente(carga.id, True)
                    sesion.auditar(
                        carga,
                        EventoAuditoria.VIGENTE_ASIGNADA,
                        detalle={"motivo": "primera_version_terminada_de_la_fecha"},
                    )
        except Exception as exc:
            # Solo el tipo: los mensajes del driver pueden incluir valores de la fila.
            logger.error("Fallo al guardar la carga %s (%s)", carga.id, type(exc).__name__)
            return self._fallar(
                carga,
                f"Error inesperado al guardar ({type(exc).__name__})",
                formato=formato,
                resumen=ResumenProcesamiento(filas_total=len(hoja.filas)),
            )

        return ResultadoProcesamiento(
            carga_id=carga.id,
            estado=EstadoCarga.TERMINADA,
            vigente=queda_vigente,
            resumen=resumen,
            id_vigente_actual=carga.id if queda_vigente else vigente_actual,
        )

    def _fallar(
        self,
        carga: DatosCarga,
        motivo: str,
        incidencias: Iterable[Incidencia] = (),
        formato: FormatoCarga | None = None,
        resumen: ResumenProcesamiento | None = None,
    ) -> ResultadoProcesamiento:
        resumen = resumen or ResumenProcesamiento()
        incidencias = list(incidencias)
        _contar_incidencias(incidencias, resumen)
        with self._repositorio.transaccion() as sesion:
            sesion.guardar_incidencias(carga.id, incidencias)
            sesion.finalizar_carga(carga.id, EstadoCarga.FALLIDA, resumen, formato, motivo)
            sesion.auditar(
                carga,
                EventoAuditoria.PROCESAMIENTO_FALLIDO,
                filas_total=resumen.filas_total or None,
                detalle={"motivo": motivo},
            )
        return ResultadoProcesamiento(
            carga_id=carga.id,
            estado=EstadoCarga.FALLIDA,
            vigente=False,
            resumen=resumen,
            motivo_fallo=motivo,
        )

    # ---------- 3. elegir la vigente ----------

    def asignar_vigente(self, carga_id: int) -> DatosCarga:
        with self._repositorio.transaccion() as sesion:
            carga = sesion.obtener_carga(carga_id)
            if carga is None:
                raise CargaNoEncontrada(carga_id)
            sesion.bloquear_fecha(carga.fecha_corte)
            carga = sesion.obtener_carga(carga_id)  # releer tras obtener el bloqueo
            if carga is None:
                raise CargaNoEncontrada(carga_id)
            if carga.estado is not EstadoCarga.TERMINADA:
                raise VigenciaNoPermitida(
                    f"La carga {carga_id} esta en estado {carga.estado.value}; "
                    "solo una version terminada puede ser vigente"
                )
            actual = sesion.id_vigente(carga.fecha_corte)
            if actual == carga.id:
                return carga
            if actual is not None:
                anterior = sesion.obtener_carga(actual)
                sesion.marcar_vigente(actual, False)
                if anterior is not None:
                    sesion.auditar(
                        anterior,
                        EventoAuditoria.VIGENTE_RETIRADA,
                        detalle={"reemplazada_por": carga.id},
                    )
            sesion.marcar_vigente(carga.id, True)
            sesion.auditar(carga, EventoAuditoria.VIGENTE_ASIGNADA, detalle={"reemplaza_a": actual})
        return replace(carga, vigente=True)

    # ---------- 4. consultar ----------

    def listar_versiones(
        self, fecha_corte: date | None = None, limite: int = 50, desplazamiento: int = 0
    ) -> list[CargaDetalle]:
        with self._repositorio.transaccion() as sesion:
            return sesion.listar(fecha_corte, limite, desplazamiento)

    def obtener(self, carga_id: int) -> CargaDetalle:
        with self._repositorio.transaccion() as sesion:
            detalle = sesion.obtener_detalle(carga_id)
            if detalle is None:
                raise CargaNoEncontrada(carga_id)
            return detalle

    def incidencias(
        self,
        carga_id: int,
        severidad: Severidad | None = None,
        limite: int = 100,
        desplazamiento: int = 0,
    ) -> tuple[int, list[Incidencia]]:
        """Total de incidencias y la pagina pedida, en el orden en que se detectaron."""
        with self._repositorio.transaccion() as sesion:
            if sesion.obtener_carga(carga_id) is None:
                raise CargaNoEncontrada(carga_id)
            total = sesion.contar_incidencias(carga_id, severidad)
            return total, sesion.listar_incidencias(carga_id, severidad, limite, desplazamiento)

    # ---------- 5. eliminar y recuperar ----------

    def eliminar_version(self, carga_id: int, dejar_fecha_sin_vigente: bool = False) -> None:
        """Regla V-8: la version vigente solo se elimina confirmandolo explicitamente."""
        with self._repositorio.transaccion() as sesion:
            carga = sesion.obtener_carga(carga_id)
            if carga is None:
                raise CargaNoEncontrada(carga_id)
            sesion.bloquear_fecha(carga.fecha_corte)
            carga = sesion.obtener_carga(carga_id)  # releer tras obtener el bloqueo
            if carga is None:
                raise CargaNoEncontrada(carga_id)
            if carga.vigente and not dejar_fecha_sin_vigente:
                raise EliminacionNoPermitida(
                    f"La carga {carga_id} es la version vigente del {carga.fecha_corte}; "
                    "elige otra version vigente antes de eliminarla o confirma que la "
                    "fecha quede sin version vigente"
                )
            sesion.auditar(
                carga,
                EventoAuditoria.CARGA_ELIMINADA,
                detalle={"era_vigente": carga.vigente, "estado": carga.estado.value},
            )
            sesion.eliminar_carga(carga_id)

    def recuperar_interrumpidas(self) -> list[int]:
        """Devuelve a la cola las versiones que quedaron en procesando.

        El guardado es una sola transaccion, asi que una version interrumpida no
        dejo filas a medias y puede procesarse otra vez desde cero. Pensado para
        el arranque de la aplicacion, cuando no hay otro proceso trabajando.
        """
        with self._repositorio.transaccion() as sesion:
            reencoladas = sesion.reencolar_interrumpidas()
        if reencoladas:
            logger.warning("Versiones devueltas a la cola tras una interrupcion: %s", reencoladas)
        return reencoladas

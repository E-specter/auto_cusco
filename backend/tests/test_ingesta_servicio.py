"""Pruebas del caso de uso de ingesta con versionado (sin base de datos).

Se usa un repositorio en memoria que imita las garantias de PostgreSQL que el
caso de uso necesita: transacciones todo-o-nada, una vigente por fecha y solo
versiones terminadas como vigentes. Solo datos sinteticos.
"""

import copy
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import date
from typing import Any

import pytest

from app.core.entities.carga import (
    CargaNoEncontrada,
    CargaNoProcesable,
    DatosCarga,
    EstadoCarga,
    EventoAuditoria,
    FilaParaGuardar,
    FormatoCarga,
    NuevaCarga,
    ResumenProcesamiento,
    VigenciaNoPermitida,
)
from app.core.entities.sabana import ArchivoIlegible, FilaCruda, HojaSabana, Incidencia, Severidad
from app.core.services.ingesta_sabana.cabeceras import huella_formato
from app.core.services.ingesta_sabana.servicio import IngestaSabanaService
from tests.test_sabana_cabeceras import CABECERAS_10_09
from tests.test_sabana_normalizador import _fila_sintetica

FECHA = date(2026, 9, 10)


class RepositorioEnMemoria:
    """Repositorio y sesion a la vez; `transaccion` revierte todo ante una excepcion."""

    def __init__(self) -> None:
        self.cargas: dict[int, dict[str, Any]] = {}
        self.archivos: dict[int, bytes] = {}
        self.filas: dict[int, list[FilaParaGuardar]] = {}
        self.incidencias: dict[int, list[Incidencia]] = {}
        self.auditoria: list[tuple[int, EventoAuditoria, dict | None]] = []
        self.fallar_en: str | None = None

    @contextmanager
    def transaccion(self):
        # `fallar_en` simula un fallo ajeno a los datos: no se revierte con la transaccion.
        respaldo = copy.deepcopy({k: v for k, v in self.__dict__.items() if k != "fallar_en"})
        try:
            yield self
        except BaseException:
            fallar_en = self.fallar_en
            self.__dict__.clear()
            self.__dict__.update(respaldo, fallar_en=fallar_en)
            raise

    # --- sesion ---

    def _datos(self, carga_id: int) -> DatosCarga:
        c = self.cargas[carga_id]
        return DatosCarga(
            c["id"], c["fecha_corte"], c["version"], c["estado"], c["vigente"],
            c["nombre_archivo"], c["huella_archivo"], c["hoja"],
        )  # fmt: skip

    def bloquear_fecha(self, fecha_corte: date) -> None:
        pass

    def siguiente_version(self, fecha_corte: date) -> int:
        versiones = [c["version"] for c in self.cargas.values() if c["fecha_corte"] == fecha_corte]
        return max(versiones, default=0) + 1

    def versiones_con_huella(self, fecha_corte: date, huella_archivo: str) -> list[int]:
        return sorted(
            c["version"]
            for c in self.cargas.values()
            if c["fecha_corte"] == fecha_corte and c["huella_archivo"] == huella_archivo
        )

    def crear_carga(self, nueva: NuevaCarga) -> DatosCarga:
        carga_id = len(self.cargas) + 1
        self.cargas[carga_id] = {
            "id": carga_id,
            "estado": EstadoCarga.EN_COLA,
            "vigente": False,
            **vars(nueva),
        }
        return self._datos(carga_id)

    def guardar_archivo(self, carga_id: int, contenido: bytes) -> None:
        self.archivos[carga_id] = contenido

    def obtener_carga(self, carga_id: int) -> DatosCarga | None:
        return self._datos(carga_id) if carga_id in self.cargas else None

    def tomar_para_procesar(self, carga_id: int) -> DatosCarga | None:
        carga = self.cargas.get(carga_id)
        if carga is None or carga["estado"] is not EstadoCarga.EN_COLA:
            return None
        carga["estado"] = EstadoCarga.PROCESANDO
        return self._datos(carga_id)

    def obtener_archivo(self, carga_id: int) -> bytes:
        return self.archivos[carga_id]

    def guardar_filas(self, carga_id: int, filas: Iterable[FilaParaGuardar]) -> int:
        guardadas = self.filas.setdefault(carga_id, [])
        for fila in filas:
            if any(f.valores["pagare"] == fila.valores["pagare"] for f in guardadas):
                raise AssertionError("clave primaria (carga_id, pagare) violada")
            guardadas.append(fila)
            if self.fallar_en == "guardar_filas":
                self.fallar_en = None  # falla una sola vez
                raise RuntimeError("fallo simulado a mitad del guardado")
        return len(guardadas)

    def guardar_incidencias(self, carga_id: int, incidencias: Iterable[Incidencia]) -> int:
        if self.fallar_en == "guardar_incidencias":
            self.fallar_en = None  # falla una sola vez
            raise RuntimeError("fallo simulado")
        self.incidencias.setdefault(carga_id, []).extend(incidencias)
        return len(self.incidencias[carga_id])

    def finalizar_carga(
        self,
        carga_id: int,
        estado: EstadoCarga,
        resumen: ResumenProcesamiento,
        formato: FormatoCarga | None = None,
        motivo_fallo: str | None = None,
    ) -> None:
        self.cargas[carga_id] |= {
            "estado": estado,
            "resumen": resumen,
            "formato": formato,
            "motivo_fallo": motivo_fallo,
        }

    def id_vigente(self, fecha_corte: date) -> int | None:
        return next(
            (
                c["id"]
                for c in self.cargas.values()
                if c["fecha_corte"] == fecha_corte and c["vigente"]
            ),
            None,
        )

    def marcar_vigente(self, carga_id: int, vigente: bool) -> None:
        carga = self.cargas[carga_id]
        if vigente:
            assert carga["estado"] is EstadoCarga.TERMINADA, "restriccion vigente_terminada"
            otra = self.id_vigente(carga["fecha_corte"])
            assert otra in (None, carga_id), "indice unico de vigente por fecha"
        carga["vigente"] = vigente

    def auditar(self, carga, evento, filas_total=None, detalle=None) -> None:
        self.auditoria.append((carga.id, evento, detalle))


class LectorFalso:
    def __init__(self, hoja: HojaSabana | None = None, error: Exception | None = None) -> None:
        self.hoja = hoja
        self.error = error

    def leer_hoja(self, contenido: bytes, hoja: str = "VENCIDA") -> HojaSabana:
        if self.error is not None:
            raise self.error
        return self.hoja


def _hoja(*filas: list, cabeceras: list | None = None) -> HojaSabana:
    return HojaSabana(
        nombre="VENCIDA",
        fila_cabecera=1,
        cabeceras=list(cabeceras or CABECERAS_10_09),
        filas=[FilaCruda(numero_fila=i + 2, celdas=celdas) for i, celdas in enumerate(filas)],
    )


def _servicio(hoja: HojaSabana | None = None, error: Exception | None = None):
    repo = RepositorioEnMemoria()
    return IngestaSabanaService(repo, LectorFalso(hoja, error)), repo


def _eventos(repo: RepositorioEnMemoria, carga_id: int) -> list[EventoAuditoria]:
    return [evento for cid, evento, _ in repo.auditoria if cid == carga_id]


def _pagare(n: int) -> str:
    return f"{n:018d}"


# ---------- registrar ----------


def test_registrar_numera_versiones_por_fecha_y_detecta_archivo_identico() -> None:
    servicio, repo = _servicio()

    v1 = servicio.registrar_carga(FECHA, "sabana.xlsb", b"contenido")
    v2 = servicio.registrar_carga(FECHA, "sabana.xlsb", b"contenido")
    otra_fecha = servicio.registrar_carga(date(2026, 9, 9), "sabana.xlsb", b"contenido")

    assert (v1.carga.version, v1.versiones_identicas) == (1, [])
    assert (v2.carga.version, v2.versiones_identicas) == (2, [1])
    assert (otra_fecha.carga.version, otra_fecha.versiones_identicas) == (1, [])
    assert v1.carga.estado is EstadoCarga.EN_COLA and not v1.carga.vigente
    assert repo.archivos[v1.carga.id] == b"contenido"
    assert _eventos(repo, v2.carga.id) == [EventoAuditoria.CARGA_CREADA]
    assert servicio.buscar_versiones_identicas(FECHA, b"contenido") == [1, 2]


# ---------- procesar ----------


def test_primera_version_se_guarda_y_queda_vigente() -> None:
    hoja = _hoja(_fila_sintetica(Pagare=_pagare(1)), _fila_sintetica(Pagare=_pagare(2)))
    servicio, repo = _servicio(hoja)
    carga = servicio.registrar_carga(FECHA, "sabana.xlsb", b"x").carga

    resultado = servicio.procesar_carga(carga.id)

    assert resultado.estado is EstadoCarga.TERMINADA
    assert resultado.vigente and not resultado.requiere_confirmacion
    assert [f.valores["pagare"] for f in repo.filas[carga.id]] == [_pagare(1), _pagare(2)]
    assert [f.numero_fila for f in repo.filas[carga.id]] == [2, 3]
    assert (resultado.resumen.filas_total, resultado.resumen.filas_ingestadas) == (2, 2)
    assert resultado.resumen.incidencias_info == 2  # DNI completados con ceros
    assert repo.cargas[carga.id]["formato"].huella_formato == huella_formato(CABECERAS_10_09)
    assert _eventos(repo, carga.id) == [
        EventoAuditoria.CARGA_CREADA,
        EventoAuditoria.PROCESAMIENTO_TERMINADO,
        EventoAuditoria.VIGENTE_ASIGNADA,
    ]


def test_nueva_version_de_una_fecha_con_vigente_no_la_reemplaza_por_defecto() -> None:
    servicio, repo = _servicio(_hoja(_fila_sintetica()))
    v1 = servicio.registrar_carga(FECHA, "a.xlsb", b"a").carga
    servicio.procesar_carga(v1.id)
    v2 = servicio.registrar_carga(FECHA, "b.xlsb", b"b").carga

    resultado = servicio.procesar_carga(v2.id)

    assert resultado.estado is EstadoCarga.TERMINADA
    assert not resultado.vigente
    assert resultado.requiere_confirmacion
    assert resultado.id_vigente_actual == v1.id
    assert repo.id_vigente(FECHA) == v1.id
    assert EventoAuditoria.VIGENTE_ASIGNADA not in _eventos(repo, v2.id)


def test_pagare_repetido_conserva_la_primera_aparicion() -> None:
    hoja = _hoja(
        _fila_sintetica(Pagare=_pagare(7), **{"Monto Cuota": 100.0}),
        _fila_sintetica(Pagare=_pagare(7), **{"Monto Cuota": 200.0}),
    )
    servicio, repo = _servicio(hoja)
    carga = servicio.registrar_carga(FECHA, "a.xlsb", b"a").carga

    resultado = servicio.procesar_carga(carga.id)

    (guardada,) = repo.filas[carga.id]
    assert guardada.numero_fila == 2
    assert str(guardada.valores["monto_cuota"]) == "100.00"
    repetida = [i for i in repo.incidencias[carga.id] if i.codigo == "pagare_repetido"]
    assert [(i.fila, i.severidad) for i in repetida] == [(3, Severidad.ERROR)]
    assert (resultado.resumen.filas_total, resultado.resumen.filas_ingestadas) == (2, 1)
    assert resultado.resumen.incidencias_error == 1


def test_fila_sin_pagare_no_se_guarda_pero_queda_su_incidencia() -> None:
    servicio, repo = _servicio(_hoja(_fila_sintetica(Pagare=None), _fila_sintetica()))
    carga = servicio.registrar_carga(FECHA, "a.xlsb", b"a").carga

    resultado = servicio.procesar_carga(carga.id)

    assert len(repo.filas[carga.id]) == 1
    assert any(i.codigo == "clave_vacia" and i.fila == 2 for i in repo.incidencias[carga.id])
    assert resultado.estado is EstadoCarga.TERMINADA


def test_columnas_no_catalogadas_se_guardan_en_extras() -> None:
    cabeceras = [*CABECERAS_10_09, "Columna Nueva", "Fecha Nueva"]
    hoja = _hoja([*_fila_sintetica(), "valor libre", date(2026, 9, 1)], cabeceras=cabeceras)
    servicio, repo = _servicio(hoja)
    carga = servicio.registrar_carga(FECHA, "a.xlsb", b"a").carga

    servicio.procesar_carga(carga.id)

    assert repo.filas[carga.id][0].extras == {
        "Columna Nueva": "valor libre",
        "Fecha Nueva": "2026-09-01",
    }
    assert {i.codigo for i in repo.incidencias[carga.id] if i.fila is None} == {
        "cabecera_desconocida"
    }


def test_archivo_ilegible_deja_la_version_fallida() -> None:
    servicio, repo = _servicio(
        error=ArchivoIlegible("El archivo no es una hoja de calculo legible")
    )
    carga = servicio.registrar_carga(FECHA, "roto.xlsb", b"no es excel").carga

    resultado = servicio.procesar_carga(carga.id)

    assert resultado.estado is EstadoCarga.FALLIDA and not resultado.vigente
    assert resultado.motivo_fallo == "El archivo no es una hoja de calculo legible"
    assert repo.cargas[carga.id]["estado"] is EstadoCarga.FALLIDA
    assert carga.id not in repo.filas
    assert _eventos(repo, carga.id)[-1] is EventoAuditoria.PROCESAMIENTO_FALLIDO
    assert repo.id_vigente(FECHA) is None


def test_falta_pagare_deja_fallida_con_formato_e_incidencias_de_cabecera() -> None:
    cabeceras = [c for c in CABECERAS_10_09 if c.lower() != "pagare"]
    servicio, repo = _servicio(_hoja(["x"] * len(cabeceras), cabeceras=cabeceras))
    carga = servicio.registrar_carga(FECHA, "a.xlsb", b"a").carga

    resultado = servicio.procesar_carga(carga.id)

    assert resultado.estado is EstadoCarga.FALLIDA
    errores = [i for i in repo.incidencias[carga.id] if i.severidad is Severidad.ERROR]
    assert [(i.codigo, i.columna) for i in errores] == [("columna_faltante", "pagare")]
    assert repo.cargas[carga.id]["formato"].cabeceras_originales == cabeceras


@pytest.mark.parametrize("etapa", ["guardar_filas", "guardar_incidencias"])
def test_error_al_guardar_revierte_todo_y_deja_fallida(etapa) -> None:
    servicio, repo = _servicio(_hoja(_fila_sintetica(Pagare=_pagare(1)), _fila_sintetica()))
    carga = servicio.registrar_carga(FECHA, "a.xlsb", b"a").carga
    repo.fallar_en = etapa

    resultado = servicio.procesar_carga(carga.id)

    assert resultado.estado is EstadoCarga.FALLIDA
    assert resultado.motivo_fallo == "Error inesperado al guardar (RuntimeError)"
    assert repo.filas.get(carga.id, []) == []  # nada a medias
    assert not repo.cargas[carga.id]["vigente"]
    assert _eventos(repo, carga.id) == [
        EventoAuditoria.CARGA_CREADA,
        EventoAuditoria.PROCESAMIENTO_FALLIDO,
    ]


def test_una_version_no_se_procesa_dos_veces() -> None:
    servicio, _ = _servicio(_hoja(_fila_sintetica()))
    carga = servicio.registrar_carga(FECHA, "a.xlsb", b"a").carga
    servicio.procesar_carga(carga.id)

    with pytest.raises(CargaNoProcesable):
        servicio.procesar_carga(carga.id)


def test_carga_inexistente() -> None:
    servicio, _ = _servicio()

    with pytest.raises(CargaNoEncontrada):
        servicio.procesar_carga(99)
    with pytest.raises(CargaNoEncontrada):
        servicio.asignar_vigente(99)


# ---------- elegir la vigente ----------


def test_asignar_vigente_cambia_de_version_y_audita_ambas() -> None:
    servicio, repo = _servicio(_hoja(_fila_sintetica()))
    v1 = servicio.registrar_carga(FECHA, "a.xlsb", b"a").carga
    servicio.procesar_carga(v1.id)
    v2 = servicio.registrar_carga(FECHA, "b.xlsb", b"b").carga
    servicio.procesar_carga(v2.id)

    nueva = servicio.asignar_vigente(v2.id)
    eventos_antes = len(repo.auditoria)
    servicio.asignar_vigente(v2.id)  # ya es vigente: no cambia nada

    assert nueva.vigente
    assert repo.id_vigente(FECHA) == v2.id
    assert not repo.cargas[v1.id]["vigente"]
    assert _eventos(repo, v1.id)[-1] is EventoAuditoria.VIGENTE_RETIRADA
    assert _eventos(repo, v2.id)[-1] is EventoAuditoria.VIGENTE_ASIGNADA
    assert len(repo.auditoria) == eventos_antes


@pytest.mark.parametrize("estado", ["en_cola", "fallida"])
def test_solo_una_version_terminada_puede_ser_vigente(estado) -> None:
    error = ArchivoIlegible("ilegible") if estado == "fallida" else None
    servicio, _ = _servicio(error=error)
    carga = servicio.registrar_carga(FECHA, "a.xlsb", b"a").carga
    if estado == "fallida":
        servicio.procesar_carga(carga.id)

    with pytest.raises(VigenciaNoPermitida):
        servicio.asignar_vigente(carga.id)


# ---------- huella de formato ----------


def test_huella_de_formato_ignora_tildes_mayusculas_y_espacios() -> None:
    variante = [c.upper().replace("Í", "I").replace("é", "e") + "  " for c in CABECERAS_10_09]

    assert huella_formato(variante) == huella_formato(CABECERAS_10_09)


def test_huella_de_formato_cambia_si_se_renombra_una_columna() -> None:
    renombrada = ["PAGARE2" if c == "PAGARE" else c for c in CABECERAS_10_09]

    assert huella_formato(renombrada) != huella_formato(CABECERAS_10_09)

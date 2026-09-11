"""Pruebas de los endpoints de cargas, con un doble de prueba del caso de uso.

No tocan base de datos ni archivos reales: sustituyen la dependencia del
servicio, igual que tests/test_health_api.py.
"""

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.cargas import obtener_servicio
from app.core.entities.carga import (
    CargaDetalle,
    CargaNoEncontrada,
    CargaRegistrada,
    DatosCarga,
    EliminacionNoPermitida,
    EstadoCarga,
    ResultadoProcesamiento,
    ResumenProcesamiento,
    VigenciaNoPermitida,
)
from app.core.entities.sabana import Incidencia, Severidad
from app.main import app

FECHA = date(2026, 9, 10)


def _detalle(carga_id: int = 1, **cambios) -> CargaDetalle:
    valores = {
        "id": carga_id,
        "fecha_corte": FECHA,
        "version": 1,
        "estado": EstadoCarga.TERMINADA,
        "vigente": True,
        "nombre_archivo": "sabana.xlsb",
        "huella_archivo": "a" * 64,
        "tamano_bytes": 1024,
        "hoja": "VENCIDA",
        "creado_en": datetime(2026, 9, 10, 8, 0),
        "procesado_en": datetime(2026, 9, 10, 8, 1),
        "filas_total": 3,
        "filas_ingestadas": 2,
        "incidencias_error": 1,
        "incidencias_advertencia": 0,
        "incidencias_info": 2,
    }
    return CargaDetalle(**(valores | cambios))


class ServicioFalso:
    def __init__(self, **comportamiento) -> None:
        self.comportamiento = comportamiento
        self.procesadas: list[int] = []
        self.registros: list[tuple] = []
        self.listados: list[tuple] = []
        self.eliminadas: list[tuple[int, bool]] = []
        self.vigentes: list[int] = []

    def _quizas_fallar(self, operacion: str) -> None:
        error = self.comportamiento.get(operacion)
        if error is not None:
            raise error

    def registrar_carga(self, fecha_corte, nombre_archivo, contenido, hoja="VENCIDA"):
        self.registros.append((fecha_corte, nombre_archivo, len(contenido), hoja))
        carga = DatosCarga(
            id=7,
            fecha_corte=fecha_corte,
            version=2,
            estado=EstadoCarga.EN_COLA,
            vigente=False,
            nombre_archivo=nombre_archivo,
            huella_archivo="b" * 64,
            hoja=hoja,
        )
        return CargaRegistrada(
            carga=carga, versiones_identicas=self.comportamiento.get("identicas", [])
        )

    def procesar_carga(self, carga_id: int):
        self.procesadas.append(carga_id)
        return ResultadoProcesamiento(
            carga_id=carga_id,
            estado=EstadoCarga.TERMINADA,
            vigente=True,
            resumen=ResumenProcesamiento(filas_total=2, filas_ingestadas=2),
        )

    def listar_versiones(self, fecha_corte=None, limite=50, desplazamiento=0):
        self.listados.append((fecha_corte, limite, desplazamiento))
        return [_detalle(1), _detalle(2, version=2, vigente=False)]

    def obtener(self, carga_id: int):
        self._quizas_fallar("obtener")
        return _detalle(carga_id)

    def incidencias(self, carga_id, severidad=None, limite=100, desplazamiento=0):
        self._quizas_fallar("incidencias")
        incidencia = Incidencia(
            fila=3,
            columna="telefono",
            codigo="telefono_invalido",
            severidad=severidad or Severidad.ADVERTENCIA,
            detalle="Se esperaban 9 digitos iniciando en 9",
            valor_original=98765432.0,
        )
        return 5, [incidencia]

    def asignar_vigente(self, carga_id: int):
        self._quizas_fallar("asignar_vigente")
        self.vigentes.append(carga_id)

    def eliminar_version(self, carga_id: int, dejar_fecha_sin_vigente: bool = False):
        self._quizas_fallar("eliminar_version")
        self.eliminadas.append((carga_id, dejar_fecha_sin_vigente))


@pytest.fixture
def cliente():
    servicio = ServicioFalso()
    app.dependency_overrides[obtener_servicio] = lambda: servicio
    try:
        yield TestClient(app), servicio
    finally:
        app.dependency_overrides.clear()


def _con_servicio(servicio: ServicioFalso) -> TestClient:
    app.dependency_overrides[obtener_servicio] = lambda: servicio
    return TestClient(app)


def test_subir_sabana_registra_y_procesa_en_segundo_plano(cliente) -> None:
    client, servicio = cliente

    respuesta = client.post(
        "/cargas",
        data={"fecha_corte": "2026-09-10"},
        files={"archivo": ("sabana.xlsb", b"contenido binario", "application/octet-stream")},
    )

    assert respuesta.status_code == 202
    cuerpo = respuesta.json()
    assert (cuerpo["id"], cuerpo["version"], cuerpo["estado"]) == (7, 2, "en_cola")
    assert cuerpo["aviso"] is None
    assert servicio.registros == [(FECHA, "sabana.xlsb", 17, "VENCIDA")]
    assert servicio.procesadas == [7]  # la tarea de fondo corre al cerrar la respuesta


def test_subir_avisa_si_el_archivo_ya_se_cargo_para_esa_fecha() -> None:
    servicio = ServicioFalso(identicas=[1])
    client = _con_servicio(servicio)
    try:
        respuesta = client.post(
            "/cargas",
            data={"fecha_corte": "2026-09-10"},
            files={"archivo": ("sabana.xlsb", b"contenido", "application/octet-stream")},
        )
    finally:
        app.dependency_overrides.clear()

    assert respuesta.json()["versiones_identicas"] == [1]
    assert "identico" in respuesta.json()["aviso"]


def test_subir_archivo_vacio_o_sin_fecha(cliente) -> None:
    client, _ = cliente

    vacio = client.post(
        "/cargas",
        data={"fecha_corte": "2026-09-10"},
        files={"archivo": ("sabana.xlsb", b"", "application/octet-stream")},
    )
    sin_fecha = client.post(
        "/cargas", files={"archivo": ("sabana.xlsb", b"x", "application/octet-stream")}
    )

    assert vacio.status_code == 400
    assert sin_fecha.status_code == 422


def test_listar_versiones_por_fecha(cliente) -> None:
    client, servicio = cliente

    respuesta = client.get("/cargas", params={"fecha_corte": "2026-09-10", "limite": 10})

    assert respuesta.status_code == 200
    assert [v["id"] for v in respuesta.json()] == [1, 2]
    assert servicio.listados == [(FECHA, 10, 0)]


def test_consultar_estado_de_una_version(cliente) -> None:
    client, _ = cliente

    respuesta = client.get("/cargas/1")

    cuerpo = respuesta.json()
    assert respuesta.status_code == 200
    assert cuerpo["estado"] == "terminada" and cuerpo["vigente"] is True
    assert (cuerpo["filas_total"], cuerpo["filas_ingestadas"]) == (3, 2)
    assert cuerpo["incidencias_error"] == 1


def test_consultar_una_version_inexistente() -> None:
    client = _con_servicio(ServicioFalso(obtener=CargaNoEncontrada(9)))
    try:
        respuesta = client.get("/cargas/9")
    finally:
        app.dependency_overrides.clear()

    assert respuesta.status_code == 404


def test_incidencias_con_total_y_filtro(cliente) -> None:
    client, _ = cliente

    respuesta = client.get("/cargas/1/incidencias", params={"severidad": "error", "limite": 1})

    cuerpo = respuesta.json()
    assert cuerpo["total"] == 5
    assert cuerpo["incidencias"][0]["severidad"] == "error"
    assert cuerpo["incidencias"][0]["valor_original"] == "98765432.0"


def test_asignar_vigente(cliente) -> None:
    client, servicio = cliente

    respuesta = client.post("/cargas/3/vigente")

    assert respuesta.status_code == 200
    assert servicio.vigentes == [3]


def test_asignar_vigente_a_una_version_no_terminada() -> None:
    client = _con_servicio(ServicioFalso(asignar_vigente=VigenciaNoPermitida("esta fallida")))
    try:
        respuesta = client.post("/cargas/3/vigente")
    finally:
        app.dependency_overrides.clear()

    assert respuesta.status_code == 409


def test_eliminar_version(cliente) -> None:
    client, servicio = cliente

    respuesta = client.delete("/cargas/4", params={"dejar_fecha_sin_vigente": "true"})

    assert respuesta.status_code == 204
    assert servicio.eliminadas == [(4, True)]


def test_eliminar_la_vigente_sin_confirmar_devuelve_conflicto() -> None:
    client = _con_servicio(ServicioFalso(eliminar_version=EliminacionNoPermitida("es la vigente")))
    try:
        respuesta = client.delete("/cargas/4")
    finally:
        app.dependency_overrides.clear()

    assert respuesta.status_code == 409
    assert "vigente" in respuesta.json()["detail"]

"""Pruebas de la supervision de campanas digitales (RF-37 a RF-41), sin plataforma concreta.

Numeros sinteticos del rango 900000xxx: nunca numeros reales.
"""

import pytest

from app.core.entities.gestiones_digitales import (
    ConfiguracionSupervision,
    SinProductosCargables,
    SinSupervisores,
    SupervisionInvalida,
    Supervisor,
)
from app.core.services.gestiones_digitales import supervision
from app.core.services.gestiones_digitales.servicio import SupervisionService

CAJA = "Caja Cusco"
EMPRESA = "nuestra empresa"
PROCEDENCIAS = (CAJA, EMPRESA)

# Mezclados a proposito: el orden de asignacion lo da la procedencia, no la lista.
SUPERVISORES = (
    Supervisor("900000001", CAJA),
    Supervisor("900000004", EMPRESA),
    Supervisor("900000002", CAJA),
    Supervisor("900000005", EMPRESA),
    Supervisor("900000003", CAJA),
)

PLANTILLA = {"numero": 900000999, "mensaje": "ZZPRUEBA mensaje sintetico", "dni": "12345678"}


class RepositorioSupervisionFalso:
    def __init__(self) -> None:
        self.configuracion = ConfiguracionSupervision(PROCEDENCIAS, ())
        self.escrituras = 0

    def obtener(self):
        return self.configuracion

    def reemplazar(self, configuracion):
        self.escrituras += 1
        self.configuracion = configuracion
        return configuracion


def test_la_distribucion_por_defecto_asigna_primero_caja_cusco_y_luego_nuestra_empresa() -> None:
    asignados = supervision.documentos_asignados(SUPERVISORES, PROCEDENCIAS)

    assert [(s.numero, documento) for s, documento in asignados] == [
        ("900000001", "00000001"),
        ("900000002", "00000002"),
        ("900000003", "00000003"),
        ("900000004", "00000004"),
        ("900000005", "00000005"),
    ]


def test_los_documentos_por_posicion_respetan_la_lista_tal_como_viene() -> None:
    documentos = supervision.documentos_por_posicion(SUPERVISORES, PROCEDENCIAS)

    assert documentos == ["00000001", "00000004", "00000002", "00000005", "00000003"]


def test_el_orden_de_procedencias_cambia_la_asignacion() -> None:
    documentos = supervision.documentos_por_posicion(SUPERVISORES, (EMPRESA, CAJA))

    assert documentos == ["00000003", "00000001", "00000004", "00000002", "00000005"]


def test_la_secuencia_se_extiende_con_mas_supervisores() -> None:
    muchos = [Supervisor(f"9000000{i:02d}", CAJA) for i in range(11)]

    documentos = supervision.documentos_por_posicion(muchos, PROCEDENCIAS)

    assert documentos[0] == "00000001"
    assert documentos[-1] == "00000011"


def test_un_supervisor_repetido_recibe_su_propio_documento() -> None:
    repetidos = [Supervisor("900000001", CAJA), Supervisor("900000001", CAJA)]

    assert supervision.documentos_por_posicion(repetidos, PROCEDENCIAS) == [
        "00000001",
        "00000002",
    ]


def test_las_filas_copian_la_plantilla_salvo_numero_y_documento() -> None:
    filas = supervision.filas_supervision(SUPERVISORES, PROCEDENCIAS, PLANTILLA, "numero", "dni")

    assert [(f["numero"], f["dni"]) for f in filas] == [
        ("900000001", "00000001"),
        ("900000002", "00000002"),
        ("900000003", "00000003"),
        ("900000004", "00000004"),
        ("900000005", "00000005"),
    ]
    assert {f["mensaje"] for f in filas} == {PLANTILLA["mensaje"]}
    assert PLANTILLA["dni"] == "12345678"  # la plantilla no se modifica


def test_sin_productos_cargables_no_hay_supervision() -> None:
    with pytest.raises(SinProductosCargables):
        supervision.filas_supervision(SUPERVISORES, PROCEDENCIAS, None, "numero", "dni")


def test_sin_supervisores_no_hay_supervision() -> None:
    with pytest.raises(SinSupervisores):
        supervision.filas_supervision((), PROCEDENCIAS, PLANTILLA, "numero", "dni")


def test_un_supervisor_de_procedencia_sin_orden_se_rechaza() -> None:
    with pytest.raises(SupervisionInvalida):
        supervision.documentos_asignados([Supervisor("900000001", "otra")], PROCEDENCIAS)


@pytest.mark.parametrize(
    ("numero", "valido"),
    [
        ("900000001", True),
        ("800000001", False),  # no empieza con 9
        ("90000001", False),  # 8 digitos
        ("9000000011", False),  # 10 digitos
        ("90000000a", False),
        ("", False),
    ],
)
def test_el_numero_sigue_rf02(numero, valido) -> None:
    assert supervision.numero_valido(numero) is valido


def test_guardar_recorta_espacios_y_conserva_el_orden() -> None:
    repositorio = RepositorioSupervisionFalso()
    configuracion = ConfiguracionSupervision(
        procedencias=(f" {CAJA} ", EMPRESA),
        supervisores=(Supervisor(" 900000004 ", EMPRESA), Supervisor("900000001", f"{CAJA} ")),
    )

    guardada = SupervisionService(repositorio).reemplazar(configuracion)

    assert guardada == ConfiguracionSupervision(
        PROCEDENCIAS, (Supervisor("900000004", EMPRESA), Supervisor("900000001", CAJA))
    )


@pytest.mark.parametrize(
    ("configuracion", "fragmento"),
    [
        (ConfiguracionSupervision((), ()), "al menos una procedencia"),
        (ConfiguracionSupervision((CAJA, "caja cusco"), ()), "repetida"),
        (ConfiguracionSupervision((CAJA, " "), ()), "entre 1 y"),
        (ConfiguracionSupervision(PROCEDENCIAS, (Supervisor("800000001", CAJA),)), "9 digitos"),
        (ConfiguracionSupervision(PROCEDENCIAS, (Supervisor("900000001", "otra"),)), "'otra'"),
    ],
)
def test_una_configuracion_invalida_no_se_guarda(configuracion, fragmento) -> None:
    repositorio = RepositorioSupervisionFalso()

    with pytest.raises(SupervisionInvalida) as error:
        SupervisionService(repositorio).reemplazar(configuracion)

    assert fragmento in str(error.value)
    assert repositorio.escrituras == 0

"""El SQL que escribe el repositorio de campanas, sin base (T-MM-C11, M-B1).

Un motor falso que solo anota cada sentencia ya compilada para PostgreSQL. Fija que cada agregado
usa el predicado de las activas (`descartada_en IS NULL`) y que el DELETE solo borra una descartada:
lo mismo que comprueban las `@postgres`, pero sin base, para que una consulta que se olvide del
predicado falle en cualquier maquina.
"""

from datetime import date

import pytest
from sqlalchemy.dialects import postgresql

from app.adapters.persistence.repositorio_campanas_mowa_mes_postgres import (
    RepositorioCampanasMowaMesPostgres,
)

ACTIVA = "descartada_en IS NULL"
DESCARTADA = "descartada_en IS NOT NULL"
PENDIENTE = "enviados_conciliados IS NULL"


class _Resultado:
    rowcount = 0

    def scalar_one(self):
        return 0

    def one(self):
        return (0, 0)

    def all(self):
        return []

    def scalars(self):
        return iter(())


class _Conexion:
    def __init__(self, sentencias: list[str]) -> None:
        self._sentencias = sentencias

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sentencia, *_args, **_kwargs):
        self._sentencias.append(str(sentencia.compile(dialect=postgresql.dialect())))
        return _Resultado()


class _Motor:
    def __init__(self) -> None:
        self.sentencias: list[str] = []

    def connect(self):
        return _Conexion(self.sentencias)

    begin = connect


@pytest.fixture
def repositorio():
    motor = _Motor()
    return RepositorioCampanasMowaMesPostgres(motor), motor.sentencias


def test_cargados_en_mes_solo_cuenta_las_activas(repositorio) -> None:
    repo, sentencias = repositorio

    repo.cargados_en_mes(date(2026, 9, 1))

    assert len(sentencias) == 1 and ACTIVA in sentencias[0]


def test_costo_del_mes_solo_suma_las_activas(repositorio) -> None:
    repo, sentencias = repositorio

    repo.costo_del_mes(date(2026, 9, 1))

    assert len(sentencias) == 1 and ACTIVA in sentencias[0]


def test_listar_cuenta_y_trae_solo_las_activas_y_cuenta_las_pendientes_activas(
    repositorio,
) -> None:
    repo, sentencias = repositorio

    repo.listar(50, 0)

    pendientes, total, filas = sentencias
    assert ACTIVA in pendientes and PENDIENTE in pendientes  # activas Y sin reporte
    assert ACTIVA in total and PENDIENTE not in total
    assert ACTIVA in filas
    assert f"{PENDIENTE} AS pendiente_reporte" in filas  # fila y total: la misma expresion


def test_listar_descartadas_solo_trae_descartadas(repositorio) -> None:
    repo, sentencias = repositorio

    repo.listar_descartadas(date(2026, 9, 1))

    filas, meses, total = sentencias
    assert all(DESCARTADA in sentencia for sentencia in (filas, meses, total))
    assert "mes_imputacion =" in filas and "mes_imputacion =" not in meses  # el filtro no recorta


def test_eliminar_solo_borra_una_descartada(repositorio) -> None:
    repo, sentencias = repositorio

    assert repo.eliminar(1) is False  # el motor falso no borra nada

    (borrado,) = sentencias
    assert borrado.startswith("DELETE FROM mowa_mes_campana") and DESCARTADA in borrado


def test_descartar_no_pisa_la_fecha_de_una_ya_descartada(repositorio) -> None:
    repo, sentencias = repositorio

    repo.descartar(1)

    (actualizacion,) = sentencias
    assert actualizacion.startswith("UPDATE mowa_mes_campana") and ACTIVA in actualizacion

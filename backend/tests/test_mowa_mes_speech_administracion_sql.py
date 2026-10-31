"""El SQL de la administracion de speeches, sin base (T-MM-C11, M-B2).

Un motor falso que anota cada sentencia compilada para PostgreSQL. Fija que el DELETE lleva las tres
condiciones de RF-MM-30 en la misma sentencia, que deshabilitar no pisa la fecha de una ya
deshabilitada, que renombrar no toca el contenido y que editar excluye a las deshabilitadas: lo
mismo que comprueban las `@postgres`, pero en cualquier maquina.
"""

import pytest
from sqlalchemy.dialects import postgresql

from app.adapters.persistence.repositorio_mowa_mes_postgres import RepositorioMowaMesPostgres
from app.core.entities.mowa_mes import DatosSpeech, FormatoSpeech


class _Resultado:
    rowcount = 0

    def one_or_none(self):
        return None

    def one(self):
        raise AssertionError("no se esperaba una fila")


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
    return RepositorioMowaMesPostgres(motor), motor.sentencias


def test_el_delete_lleva_las_tres_condiciones_en_la_misma_sentencia(repositorio) -> None:
    repo, sentencias = repositorio

    assert repo.eliminar_speech(7) is False  # el motor falso no borra nada

    (borrado,) = sentencias
    assert borrado.startswith("DELETE FROM mowa_mes_speech_version")
    assert "deshabilitada_en IS NOT NULL" in borrado
    assert "usada_en IS NULL" in borrado
    assert "original IS false" in borrado


def test_deshabilitar_no_pisa_la_fecha_de_una_ya_deshabilitada(repositorio) -> None:
    repo, sentencias = repositorio

    repo.cambiar_habilitacion(7, habilitada=False)

    actualizacion = sentencias[0]
    assert actualizacion.startswith("UPDATE mowa_mes_speech_version SET deshabilitada_en=")
    assert "clock_timestamp()" in actualizacion
    assert "deshabilitada_en IS NULL" in actualizacion


def test_habilitar_limpia_la_marca_sin_mas_condicion(repositorio) -> None:
    repo, sentencias = repositorio

    repo.cambiar_habilitacion(7, habilitada=True)

    actualizacion = sentencias[0]
    assert "SET deshabilitada_en=%(deshabilitada_en)s" in actualizacion
    assert "deshabilitada_en IS NULL" not in actualizacion
    assert "clock_timestamp" not in actualizacion


def test_renombrar_solo_toca_el_nombre_y_su_clave(repositorio) -> None:
    repo, sentencias = repositorio

    assert repo.renombrar_speech(7, "Otro") is None

    (renombrado,) = sentencias
    asignaciones = renombrado.split(" SET ")[1].split(" WHERE ")[0]
    assert sorted(parte.split("=")[0] for parte in asignaciones.split(", ")) == [
        "nombre",
        "nombre_normalizado",
    ]
    assert "usada_en IS NULL" not in renombrado  # se renombra la usada y el original


def test_editar_excluye_a_las_deshabilitadas(repositorio) -> None:
    repo, sentencias = repositorio

    repo.actualizar_speech(7, DatosSpeech("x", formato=FormatoSpeech.V2))

    (edicion,) = sentencias
    assert "deshabilitada_en IS NULL" in edicion
    assert "usada_en IS NULL" in edicion and "original IS false" in edicion

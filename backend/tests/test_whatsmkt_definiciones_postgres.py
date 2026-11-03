"""La definicion por defecto de WhatsMKT contra PostgreSQL real (T-WM-B2; RF-WM-04, RF-72).

La corre `architec` con `-ConBase` (AUTO_CUSCO_DB_TESTS=1 y la base `_test` migrada, que
`conftest.py` exige). Lo que solo se ve con la base: que la plataforma se lea de lo realmente
guardado, y que borrar la definicion elegida deje la configuracion sin definicion por defecto
(`ON DELETE SET NULL`). La configuracion es una sola fila: cada prueba la restituye al terminar.
"""

import os
from dataclasses import replace

import pytest
from sqlalchemy import delete

from app.adapters.persistence.db import get_engine
from app.adapters.persistence.modelos import DefinicionCargaGuardada
from app.adapters.persistence.repositorio_definiciones_postgres import (
    RepositorioDefinicionesPostgres,
)
from app.adapters.persistence.repositorio_textos_guardados_postgres import (
    RepositorioTextosGuardadosPostgres,
)
from app.adapters.persistence.repositorio_whatsmkt_postgres import RepositorioWhatsmktPostgres
from app.core.entities.nombres import normalizar_nombre
from app.core.entities.whatsmkt import CodigoWhatsmkt, DefinicionDefectoNoExiste, ErrorWhatsmkt
from app.core.services.plataformas.whatsmkt.administracion import ConfiguracionWhatsmktService

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        os.environ.get("AUTO_CUSCO_DB_TESTS") != "1",
        reason="Requiere AUTO_CUSCO_DB_TESTS=1 y PostgreSQL migrado",
    ),
]

PREFIJO = "zz prueba whatsmkt "
_DEFINICION = DefinicionCargaGuardada.__table__
CONTENIDO = {
    "proteger_formulas": True,
    "columnas": [
        {
            "nombre": "número",
            "orden": 0,
            "tipo": "texto",
            "expresion": {"nodos": [{"tipo": "texto", "valor": "x"}]},
        }
    ],
}
INEXISTENTE = 2_000_000_000


@pytest.fixture
def entorno():
    """El servicio real, las definiciones y la configuracion restituida al terminar."""
    engine = get_engine()
    repo = RepositorioWhatsmktPostgres(engine)
    definiciones = RepositorioDefinicionesPostgres(engine)
    original = repo.obtener_configuracion()
    try:
        servicio = ConfiguracionWhatsmktService(
            repo, definiciones, RepositorioTextosGuardadosPostgres(engine)
        )
        yield servicio, repo, definiciones
    finally:
        repo.guardar_configuracion(original)
        with engine.begin() as cx:
            cx.execute(
                delete(_DEFINICION).where(
                    _DEFINICION.c.nombre_normalizado.startswith(normalizar_nombre(PREFIJO))
                )
            )


def _crear(definiciones, nombre: str, plataforma: str | None):
    return definiciones.crear(PREFIJO + nombre, CONTENIDO, plataforma)


def test_una_definicion_de_whatsmkt_se_acepta_y_queda_guardada(entorno) -> None:
    servicio, repo, definiciones = entorno
    definicion = _crear(definiciones, "whatsmkt", "whatsmkt")

    guardada = servicio.guardar_configuracion(
        replace(servicio.obtener_configuracion(), definicion_defecto_id=definicion.id)
    )

    assert guardada.definicion_defecto_id == definicion.id
    assert repo.obtener_configuracion().definicion_defecto_id == definicion.id


@pytest.mark.parametrize("plataforma", [None, "mowa_mes"])
def test_una_definicion_libre_o_de_otra_plataforma_se_rechaza_sin_guardar(
    entorno, plataforma
) -> None:
    servicio, repo, definiciones = entorno
    antes = repo.obtener_configuracion()
    definicion = _crear(definiciones, f"otra {plataforma}", plataforma)

    with pytest.raises(ErrorWhatsmkt) as error:
        servicio.guardar_configuracion(replace(antes, definicion_defecto_id=definicion.id))

    assert error.value.codigo is CodigoWhatsmkt.DEFINICION_NO_WHATSMKT
    assert repo.obtener_configuracion() == antes


def test_una_definicion_que_no_existe_se_rechaza_sin_guardar(entorno) -> None:
    servicio, repo, _ = entorno
    antes = repo.obtener_configuracion()

    with pytest.raises(DefinicionDefectoNoExiste):
        servicio.guardar_configuracion(replace(antes, definicion_defecto_id=INEXISTENTE))

    assert repo.obtener_configuracion() == antes


def test_borrar_la_definicion_elegida_deja_la_configuracion_sin_definicion_por_defecto(
    entorno,
) -> None:
    servicio, repo, definiciones = entorno
    definicion = _crear(definiciones, "para borrar", "whatsmkt")
    servicio.guardar_configuracion(
        replace(servicio.obtener_configuracion(), definicion_defecto_id=definicion.id)
    )

    with get_engine().begin() as cx:
        cx.execute(delete(_DEFINICION).where(_DEFINICION.c.id == definicion.id))

    assert repo.obtener_configuracion().definicion_defecto_id is None

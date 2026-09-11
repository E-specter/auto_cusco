"""Pruebas de consulta, eliminacion y recuperacion de versiones (sin base de datos).

Reutiliza el repositorio en memoria de tests/test_ingesta_servicio.py.
"""

import pytest

from app.core.entities.carga import (
    CargaNoEncontrada,
    EliminacionNoPermitida,
    EstadoCarga,
    EventoAuditoria,
)
from app.core.entities.sabana import Severidad
from tests.test_ingesta_servicio import FECHA, _eventos, _fila_sintetica, _hoja, _pagare, _servicio


def _version_procesada(servicio, repo, pagares=(1,), nombre="sabana.xlsb"):
    carga = servicio.registrar_carga(FECHA, nombre, nombre.encode()).carga
    servicio.procesar_carga(carga.id)
    return carga


def test_listar_versiones_de_una_fecha_de_la_mas_nueva_a_la_mas_vieja() -> None:
    servicio, repo = _servicio(_hoja(_fila_sintetica()))
    v1 = _version_procesada(servicio, repo, nombre="a.xlsb")
    v2 = _version_procesada(servicio, repo, nombre="b.xlsb")

    versiones = servicio.listar_versiones(FECHA)

    assert [v.id for v in versiones] == [v2.id, v1.id]
    assert [v.version for v in versiones] == [2, 1]
    assert versiones[1].vigente and not versiones[0].vigente
    assert versiones[0].filas_ingestadas == 1


def test_obtener_version_devuelve_el_resumen_y_falla_si_no_existe() -> None:
    servicio, repo = _servicio(_hoja(_fila_sintetica(), _fila_sintetica(Pagare=_pagare(2))))
    carga = _version_procesada(servicio, repo)

    detalle = servicio.obtener(carga.id)

    assert detalle.estado is EstadoCarga.TERMINADA
    assert (detalle.filas_total, detalle.filas_ingestadas) == (2, 2)
    assert detalle.incidencias_info == 2
    with pytest.raises(CargaNoEncontrada):
        servicio.obtener(999)


def test_incidencias_se_pueden_filtrar_y_paginar() -> None:
    # Las dos filas son coherentes (misma clave en la columna duplicada), asi que
    # las unicas incidencias son los dos DNI completados con ceros.
    segunda = _fila_sintetica(Pagare=_pagare(2), PAGARE=_pagare(2))
    servicio, repo = _servicio(_hoja(_fila_sintetica(), segunda))
    carga = _version_procesada(servicio, repo)

    total, pagina = servicio.incidencias(carga.id, severidad=Severidad.INFO, limite=1)
    total_sin_filtro, _ = servicio.incidencias(carga.id)

    assert (total, len(pagina)) == (2, 1)
    assert pagina[0].codigo == "dni_completado_con_ceros"
    assert total_sin_filtro == 2
    with pytest.raises(CargaNoEncontrada):
        servicio.incidencias(999)


def test_eliminar_version_no_vigente_borra_todo_y_deja_la_auditoria() -> None:
    servicio, repo = _servicio(_hoja(_fila_sintetica()))
    vigente = _version_procesada(servicio, repo, nombre="a.xlsb")
    otra = _version_procesada(servicio, repo, nombre="b.xlsb")

    servicio.eliminar_version(otra.id)

    assert otra.id not in repo.cargas
    assert otra.id not in repo.filas and otra.id not in repo.incidencias
    assert repo.id_vigente(FECHA) == vigente.id
    assert _eventos(repo, otra.id)[-1] is EventoAuditoria.CARGA_ELIMINADA


def test_eliminar_la_vigente_exige_confirmacion() -> None:
    servicio, repo = _servicio(_hoja(_fila_sintetica()))
    vigente = _version_procesada(servicio, repo)

    with pytest.raises(EliminacionNoPermitida):
        servicio.eliminar_version(vigente.id)
    assert vigente.id in repo.cargas

    servicio.eliminar_version(vigente.id, dejar_fecha_sin_vigente=True)

    assert vigente.id not in repo.cargas
    assert repo.id_vigente(FECHA) is None


def test_eliminar_una_version_inexistente() -> None:
    servicio, _ = _servicio()

    with pytest.raises(CargaNoEncontrada):
        servicio.eliminar_version(999)


def test_recuperar_devuelve_a_la_cola_las_versiones_interrumpidas() -> None:
    servicio, repo = _servicio(_hoja(_fila_sintetica()))
    interrumpida = servicio.registrar_carga(FECHA, "a.xlsb", b"a").carga
    terminada = _version_procesada(servicio, repo, nombre="b.xlsb")
    repo.cargas[interrumpida.id]["estado"] = EstadoCarga.PROCESANDO  # simula el corte

    reencoladas = servicio.recuperar_interrumpidas()

    assert reencoladas == [interrumpida.id]
    assert repo.cargas[interrumpida.id]["estado"] is EstadoCarga.EN_COLA
    assert repo.cargas[terminada.id]["estado"] is EstadoCarga.TERMINADA

    resultado = servicio.procesar_carga(interrumpida.id)  # ya se puede reprocesar

    assert resultado.estado is EstadoCarga.TERMINADA


def test_recuperar_sin_versiones_interrumpidas_no_hace_nada() -> None:
    servicio, _ = _servicio()

    assert servicio.recuperar_interrumpidas() == []

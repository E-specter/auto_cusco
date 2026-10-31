"""Campanas descartadas, nucleo (T-MM-C11, M-B1; RF-MM-31, RF-MM-32 y RF-MM-01).

Servicios reales sobre repositorios en memoria, que aplican la misma regla que `_ACTIVA` del
repositorio de PostgreSQL. Datos sinteticos.
"""

from dataclasses import replace
from datetime import date, datetime

import pytest

from app.core.entities.mowa_mes import Programacion
from app.core.entities.mowa_mes_campana import (
    CampanaDescartada,
    CampanaNoDescartada,
    CampanaNoEncontrada,
    PeticionCampana,
)
from app.core.services.plataformas.mowa_mes.reportes import ReportesMowaMesService
from tests.test_mowa_mes_campana import (
    FECHA_CORTE,
    HUELLA_ORIGINAL,
    MOMENTO,
    armar_servicio,
    producto,
)

MES = date(2026, 9, 1)


def _peticion(envio: datetime | None = None) -> PeticionCampana:
    return PeticionCampana(
        fecha_corte=FECHA_CORTE,
        cantidad=100,
        programacion=Programacion.HORA_DETERMINADA,
        envios=(envio or datetime(2026, 9, 14, 9, 0),),
        speech_huella=HUELLA_ORIGINAL,
    )


def _servicio_con_dos_campanas():
    servicio, repositorio, _ = armar_servicio([producto(1)])
    primera = servicio.crear(_peticion())
    segunda = servicio.crear(_peticion())
    return servicio, repositorio, primera, segunda


def test_una_descartada_deja_de_sumar_al_limite_y_al_costo_del_mes() -> None:
    servicio, repositorio, primera, segunda = _servicio_con_dos_campanas()
    antes = servicio.limite_mensual(MES)

    servicio.descartar(primera.id)
    despues = servicio.limite_mensual(MES)

    assert despues.cargados_mes == antes.cargados_mes - primera.total_cargados
    assert despues.costo_mes == antes.costo_mes - primera.costo_estimado
    assert repositorio.cargados_en_mes(MES) == segunda.total_cargados


def test_una_descartada_no_aparece_entre_las_activas_pero_sigue_visible() -> None:
    servicio, _, primera, segunda = _servicio_con_dos_campanas()

    descartada = servicio.descartar(primera.id)
    pagina = servicio.listar(50, 0)

    assert descartada.descartada_en == MOMENTO
    assert (pagina.total, [c.id for c in pagina.campanas]) == (1, [segunda.id])
    assert servicio.obtener(primera.id).descartada_en == MOMENTO  # RF-MM-32: se puede ver


def test_el_total_de_pendientes_cuenta_solo_las_activas_sin_reporte() -> None:
    servicio, repositorio, primera, segunda = _servicio_con_dos_campanas()

    assert servicio.listar(50, 0).total_pendientes == 2
    servicio.descartar(primera.id)
    assert servicio.listar(50, 0).total_pendientes == 1
    repositorio.informes[990001] = (segunda.id, "reporte.xlsx", [])
    repositorio.campanas[segunda.id] = replace(
        repositorio.campanas[segunda.id], enviados_conciliados=3, pendiente_reporte=False
    )

    pagina = servicio.listar(50, 0)

    assert (pagina.total, pagina.total_pendientes) == (1, 0)
    assert [c.pendiente_reporte for c in pagina.campanas] == [False]


def test_descartar_es_logico_y_conserva_todo() -> None:
    servicio, repositorio, primera, _ = _servicio_con_dos_campanas()

    servicio.descartar(primera.id)

    assert repositorio.filas_cargadas(primera.id)
    assert servicio.archivo(primera.id, 1)[1].contenido
    assert servicio.exclusiones(primera.id, None, 10, 0) is not None


def test_descartar_una_ya_descartada_no_cambia_la_fecha() -> None:
    servicio, repositorio, primera, _ = _servicio_con_dos_campanas()
    servicio.descartar(primera.id)
    repositorio.campanas[primera.id] = replace(
        repositorio.campanas[primera.id], descartada_en=datetime(2026, 9, 1)
    )

    otra_vez = servicio.descartar(primera.id)

    assert otra_vez.descartada_en == datetime(2026, 9, 1)


def test_restaurar_la_devuelve_a_las_activas_y_a_los_calculos() -> None:
    servicio, _, primera, _ = _servicio_con_dos_campanas()
    antes = servicio.limite_mensual(MES)
    servicio.descartar(primera.id)

    restaurada = servicio.restaurar(primera.id)

    assert restaurada.descartada_en is None
    assert servicio.limite_mensual(MES) == antes
    assert primera.id in [c.id for c in servicio.listar(50, 0).campanas]


def test_restaurar_una_activa_no_hace_nada() -> None:
    servicio, _, primera, _ = _servicio_con_dos_campanas()

    assert servicio.restaurar(primera.id).descartada_en is None


def test_solo_se_elimina_una_descartada() -> None:
    servicio, _, primera, _ = _servicio_con_dos_campanas()

    with pytest.raises(CampanaNoDescartada):
        servicio.eliminar(primera.id)

    assert servicio.obtener(primera.id).id == primera.id  # no se borro


def test_el_servicio_no_elimina_una_activa_aunque_el_repositorio_lo_permita() -> None:
    # Defensa en profundidad: el DELETE del repositorio lleva el predicado, pero el servicio no
    # depende de eso para negarse.
    servicio, repositorio, primera, _ = _servicio_con_dos_campanas()
    repositorio.eliminar = lambda campana_id: True  # un repositorio sin el predicado

    with pytest.raises(CampanaNoDescartada):
        servicio.eliminar(primera.id)


def test_eliminar_una_descartada_la_borra_con_sus_archivos_filas_y_reportes() -> None:
    servicio, repositorio, primera, segunda = _servicio_con_dos_campanas()
    servicio.descartar(primera.id)
    repositorio.informes[990001] = (primera.id, "reporte.xlsx", [])

    servicio.eliminar(primera.id)

    with pytest.raises(CampanaNoEncontrada):
        servicio.obtener(primera.id)
    assert primera.id not in repositorio.guardadas and 990001 not in repositorio.informes
    assert servicio.obtener(segunda.id).id == segunda.id


@pytest.mark.parametrize("operacion", ["descartar", "restaurar", "eliminar"])
def test_una_campana_que_no_existe_es_404(operacion) -> None:
    servicio, _, _, _ = _servicio_con_dos_campanas()

    with pytest.raises(CampanaNoEncontrada):
        getattr(servicio, operacion)(999)


def test_las_descartadas_se_filtran_por_mes_de_gestion_y_traen_los_meses() -> None:
    servicio, _, _ = armar_servicio([producto(1)])
    septiembre = servicio.crear(_peticion(datetime(2026, 9, 14, 9, 0)))
    octubre = servicio.crear(_peticion(datetime(2026, 10, 2, 9, 0)))
    activa = servicio.crear(_peticion(datetime(2026, 10, 3, 9, 0)))
    servicio.descartar(septiembre.id)
    servicio.descartar(octubre.id)

    de_octubre = servicio.listar_descartadas(date(2026, 10, 15))
    todas = servicio.listar_descartadas(None)

    assert [c.id for c in de_octubre.campanas] == [octubre.id]  # el dia se lleva al primero
    assert de_octubre.meses == (date(2026, 10, 1), date(2026, 9, 1))  # solo los que tienen
    assert de_octubre.total_descartadas == 2
    assert [c.id for c in todas.campanas] == [octubre.id, septiembre.id]
    assert activa.id not in [c.id for c in todas.campanas]


def test_sin_descartadas_no_hay_meses() -> None:
    servicio, _, _, _ = _servicio_con_dos_campanas()

    vacio = servicio.listar_descartadas(None)

    assert (vacio.campanas, vacio.meses, vacio.total_descartadas) == ([], (), 0)


def test_importar_un_reporte_a_una_descartada_se_rechaza_y_no_guarda_nada() -> None:
    servicio, repositorio, primera, _ = _servicio_con_dos_campanas()
    servicio.descartar(primera.id)
    reportes = ReportesMowaMesService(repositorio, _LectorQueNoDebeLlamarse())

    with pytest.raises(CampanaDescartada, match="restaurala primero"):
        reportes.importar(primera.id, "reporte.xlsx", b"x")

    assert repositorio.informes == {}


def test_restaurada_si_acepta_el_reporte() -> None:
    servicio, repositorio, primera, _ = _servicio_con_dos_campanas()
    servicio.descartar(primera.id)
    servicio.restaurar(primera.id)
    reportes = ReportesMowaMesService(repositorio, _LectorQueNoDebeLlamarse())

    with pytest.raises(AssertionError):  # llega a leer el archivo: ya no la frena el descarte
        reportes.importar(primera.id, "reporte.xlsx", b"x")


class _LectorQueNoDebeLlamarse:
    def leer(self, contenido, nombre_archivo):
        raise AssertionError("se leyo el archivo")

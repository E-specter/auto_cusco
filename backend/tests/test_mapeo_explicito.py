"""El mapeo confirmado como el `MapeoCabeceras` de la ingesta (T-MAP-B3a, RF-60, RF-62)."""

import pytest

from app.core.entities.sabana import Severidad
from app.core.services.ingesta_sabana.cabeceras import describir_mapeo, mapear_cabeceras
from app.core.services.ingesta_sabana.mapeo_explicito import (
    MapeoGuardadoInvalido,
    mapeo_desde_asignaciones,
)
from app.core.services.mapeador.similitud import normalizar_cabecera
from tests.test_sabana_cabeceras import CABECERAS_10_09


def asignacion(indice, cabecera, campo, origen="coincide"):
    return {
        "indice": indice,
        "encabezado_normalizado": normalizar_cabecera(str(cabecera)),
        "campo": campo,
        "origen": origen,
    }


def de_alias(cabeceras):
    """Las asignaciones que dan los alias: lo que confirmaria un usuario sin tocar nada."""
    mapeo = mapear_cabeceras(cabeceras)
    return [
        asignacion(i, c, mapeo.columnas[i].nombre if i in mapeo.columnas else None)
        for i, c in enumerate(cabeceras)
    ]


def test_las_asignaciones_de_los_alias_dan_el_mismo_mapeo_que_los_alias() -> None:
    cabeceras = [*CABECERAS_10_09, "Columna inventada"]

    antes = mapear_cabeceras(cabeceras)
    ahora, origenes, ignoradas = mapeo_desde_asignaciones(cabeceras, de_alias(cabeceras))

    assert ahora.columnas == antes.columnas
    assert ahora.desconocidas == antes.desconocidas == ignoradas
    assert ahora.faltantes == antes.faltantes
    assert ahora.incidencias == antes.incidencias
    assert describir_mapeo(ahora) == describir_mapeo(antes)
    assert set(origenes) == {c.nombre for c in antes.columnas.values()}


def test_describir_con_origenes_suma_dos_claves_y_no_toca_las_de_siempre() -> None:
    cabeceras = ["Pagare", "Dato libre"]
    mapeo, origenes, _ = mapeo_desde_asignaciones(cabeceras, de_alias(cabeceras))

    descrito = describir_mapeo(mapeo, origenes)

    assert descrito["columnas"] == {"pagare": 1}
    assert descrito["desconocidas"] == descrito["ignoradas"] == {"2": "Dato libre"}
    assert descrito["origenes"] == {"pagare": "coincide"}
    assert set(describir_mapeo(mapeo)) == {"columnas", "desconocidas", "faltantes"}


def test_una_columna_que_coincidia_y_el_usuario_dejo_sin_cargar_no_avisa() -> None:
    cabeceras = ["Pagare", "Titular"]
    asignaciones = [asignacion(0, "Pagare", "pagare"), asignacion(1, "Titular", None, "manual")]

    mapeo, _, ignoradas = mapeo_desde_asignaciones(cabeceras, asignaciones)

    assert ignoradas == {1: "Titular"}
    assert [i.codigo for i in mapeo.incidencias if i.codigo.startswith("cabecera_")] == []
    assert "titular" in [c.nombre for c in mapeo.faltantes]


def test_una_columna_sin_nada_que_ver_con_el_catalogo_avisa_como_siempre() -> None:
    cabeceras = ["Pagare", "Dato libre"]

    mapeo, _, _ = mapeo_desde_asignaciones(cabeceras, de_alias(cabeceras))

    [aviso] = [i for i in mapeo.incidencias if i.codigo == "cabecera_desconocida"]
    assert (aviso.columna, aviso.severidad) == ("Dato libre", Severidad.ADVERTENCIA)
    assert aviso.detalle == "La cabecera de la posicion 2 no esta en el catalogo"


def test_una_columna_que_repite_un_campo_ya_tomado_avisa_como_duplicada() -> None:
    cabeceras = ["Pagare", "PAGARE", "Pagare"]
    asignaciones = [
        asignacion(0, "Pagare", "pagare"),
        asignacion(1, "PAGARE", "pagare_duplicado"),
        asignacion(2, "Pagare", None, "manual"),
    ]

    mapeo, _, _ = mapeo_desde_asignaciones(cabeceras, asignaciones)

    assert [i.codigo for i in mapeo.incidencias if i.codigo.startswith("cabecera_")] == [
        "cabecera_duplicada"
    ]


def test_faltar_el_pagare_es_un_error_y_los_demas_campos_una_advertencia() -> None:
    mapeo, _, _ = mapeo_desde_asignaciones(["Titular"], [asignacion(0, "Titular", "titular")])

    severidades = {
        i.columna: i.severidad for i in mapeo.incidencias if i.codigo == "columna_faltante"
    }
    assert severidades["pagare"] is Severidad.ERROR
    assert severidades["region"] is Severidad.ADVERTENCIA
    assert mapeo.bloqueante


@pytest.mark.parametrize(
    ("cabeceras", "asignaciones", "fragmento"),
    [
        (["Pagare"], [asignacion(1, "x", None)], "usa la columna 2"),
        (["Pagare"], [asignacion(-1, "x", None)], "usa la columna 0"),
        (["Pagare", "Otro"], [asignacion(0, "Pagare", "pagare")], "columna 2 ('Otro')"),
        (
            ["Pagare"],
            [asignacion(0, "Region", "pagare")],
            "esperaba 'region' y el archivo leido trae 'pagare'",
        ),
        (["Pagare"], [asignacion(0, "Pagare", "no_existe")], "'no_existe'"),
    ],
)
def test_los_motivos_de_un_mapeo_que_no_corresponde(cabeceras, asignaciones, fragmento) -> None:
    with pytest.raises(MapeoGuardadoInvalido) as error:
        mapeo_desde_asignaciones(cabeceras, asignaciones)

    assert fragmento in str(error.value)


def test_un_encabezado_vacio_del_archivo_no_necesita_asignacion() -> None:
    cabeceras = ["Pagare", None, "", "NULL", "Titular"]
    asignaciones = [asignacion(0, "Pagare", "pagare"), asignacion(4, "Titular", "titular")]

    mapeo, _, _ = mapeo_desde_asignaciones(cabeceras, asignaciones)

    assert set(mapeo.columnas) == {0, 4}

"""El mapeador frente a la sabana (T-MAP-B1): su catalogo, la paridad del camino viejo y la
arquitectura (el mapeador no conoce la sabana).

Los encabezados son los del propio catalogo de la sabana (`docs/sabana-schema.md`, seccion 4) o
inventados; no hay datos personales.
"""

import ast
import re
from pathlib import Path

import pytest

from app.core.entities.sabana import Severidad, TipoCampo
from app.core.services.ingesta_sabana import reglas
from app.core.services.ingesta_sabana.cabeceras import describir_mapeo, mapear_cabeceras
from app.core.services.ingesta_sabana.catalogo import CATALOGO_SABANA, CATALOGO_VENCIDA
from app.core.services.mapeador import similitud
from app.core.services.mapeador.analisis import analizar
from tests.test_sabana_cabeceras import CABECERAS_10_09

RAIZ = Path(__file__).resolve().parents[1] / "app" / "core"

# --- El catalogo de la sabana -------------------------------------------------------------------


def test_el_catalogo_de_la_sabana_se_deriva_del_vigente_sin_duplicar_datos() -> None:
    assert CATALOGO_SABANA.id == "sabana_vencida"
    assert len(CATALOGO_SABANA.campos) == len(CATALOGO_VENCIDA)
    for destino, columna in zip(CATALOGO_SABANA.campos, CATALOGO_VENCIDA, strict=True):
        assert destino.nombre == columna.nombre
        assert destino.alias == columna.patrones
        assert destino.obligatorio is columna.requerida
        assert destino.tipo == columna.tipo.value
        assert destino.clave_etiqueta == f"campo.{columna.nombre}"


def test_el_unico_campo_obligatorio_de_la_sabana_es_pagare() -> None:
    assert [c.nombre for c in CATALOGO_SABANA.campos if c.obligatorio] == ["pagare"]


def test_el_tipo_de_un_campo_es_un_texto_y_no_un_tipo_de_la_sabana() -> None:
    assert {type(c.tipo) for c in CATALOGO_SABANA.campos} == {str}
    assert {c.tipo for c in CATALOGO_SABANA.campos} <= {t.value for t in TipoCampo}


# --- La normalizacion se movio, no se copio ----------------------------------------------------


def test_la_ingesta_usa_la_normalizacion_del_mapeador_sin_copia() -> None:
    assert reglas.normalizar_cabecera is similitud.normalizar_cabecera
    assert reglas.sin_tildes is similitud.sin_tildes


def test_la_ingesta_ya_no_define_su_propia_normalizacion() -> None:
    fuente = (RAIZ / "services" / "ingesta_sabana" / "reglas.py").read_text(encoding="utf-8")

    assert "def normalizar_cabecera" not in fuente and "def sin_tildes" not in fuente


# --- Paridad con el camino viejo ----------------------------------------------------------------


def _mapeo_de_antes(cabeceras):
    """`mapear_cabeceras` como era antes de B1: solo los patrones, con `fullmatch`."""
    compilado = [(c, tuple(re.compile(p) for p in c.patrones)) for c in CATALOGO_VENCIDA]
    columnas, desconocidas, asignadas = {}, {}, set()
    for indice, cabecera in enumerate(cabeceras):
        if (
            cabecera is None
            or not str(cabecera).strip()
            or str(cabecera).strip().casefold() == "null"
        ):
            continue
        normal = similitud.normalizar_cabecera(str(cabecera))
        candidatas = [c for c, pats in compilado if any(p.fullmatch(normal) for p in pats)]
        libre = next((c for c in candidatas if c.nombre not in asignadas), None)
        if libre is None:
            desconocidas[indice] = str(cabecera)
            continue
        columnas[indice] = libre.nombre
        asignadas.add(libre.nombre)
    faltantes = [c.nombre for c in CATALOGO_VENCIDA if c.nombre not in asignadas]
    return columnas, desconocidas, faltantes


def _mapeo_de_ahora(cabeceras):
    mapeo = mapear_cabeceras(cabeceras)
    return (
        {i: c.nombre for i, c in mapeo.columnas.items()},
        mapeo.desconocidas,
        [c.nombre for c in mapeo.faltantes],
    )


VARIANTES = [
    list(CABECERAS_10_09),
    list(reversed(CABECERAS_10_09)),
    [c.upper() for c in CABECERAS_10_09],
    [c.lower() for c in CABECERAS_10_09],
    [c for c in CABECERAS_10_09 if c.lower() != "pagare"],
    [*CABECERAS_10_09, "Columna inventada", "Pagare"],
    [*CABECERAS_10_09[:6], None, "", "   ", *CABECERAS_10_09[6:]],
    ["PAGARE2" if c == "PAGARE" else c for c in CABECERAS_10_09],
    ["Pagare", "Pagare", "Pagare"],
]


@pytest.mark.parametrize("cabeceras", VARIANTES)
def test_los_archivos_que_ya_coincidian_por_alias_dan_el_mismo_mapeo(cabeceras) -> None:
    assert _mapeo_de_ahora(cabeceras) == _mapeo_de_antes(cabeceras)


def test_dias_atraso_con_espacio_ahora_coincide_con_dias_atraso() -> None:
    # M-6 (a): el camino viejo tambien gana la coincidencia por nombre.
    cabeceras = ["Pagare", "DIAS ATRASO"]

    antes = _mapeo_de_antes(cabeceras)
    mapeo = mapear_cabeceras(cabeceras)

    assert antes[1] == {1: "DIAS ATRASO"}  # desconocida
    assert mapeo.columnas[1].nombre == "dias_atraso"
    assert mapeo.desconocidas == {}


def test_el_mapeador_y_el_camino_viejo_coinciden_en_los_encabezados_de_la_sabana() -> None:
    mapeo = mapear_cabeceras(CABECERAS_10_09)
    analisis = analizar(CABECERAS_10_09, [], CATALOGO_SABANA, {})

    nuevo = {c.indice: c.sugerido for c in analisis.columnas if c.sugerido}
    assert nuevo == {i: col.nombre for i, col in mapeo.columnas.items()}
    assert {c.estado.value for c in analisis.columnas} == {"coincide"}
    assert analisis.problemas_iniciales == ()


def test_el_mapeo_viejo_conserva_sus_claves_y_sus_posiciones_en_base_1() -> None:
    descrito = describir_mapeo(mapear_cabeceras(["Pagare", "Columna inventada", "Zona libre"]))

    assert set(descrito) == {"columnas", "desconocidas", "faltantes"}
    assert descrito["columnas"] == {"pagare": 1}
    assert descrito["desconocidas"] == {"2": "Columna inventada", "3": "Zona libre"}


def test_pagare_faltante_sigue_bloqueando_por_el_camino_viejo() -> None:
    mapeo = mapear_cabeceras(["Region", "Agencia"])

    assert mapeo.bloqueante
    assert [i.codigo for i in mapeo.incidencias if i.severidad is Severidad.ERROR] == [
        "columna_faltante"
    ]


# --- Arquitectura -------------------------------------------------------------------------------


def _archivos_del_mapeador() -> list[Path]:
    return [
        RAIZ / "entities" / "mapeador.py",
        *sorted((RAIZ / "services" / "mapeador").glob("*.py")),
    ]


def _importados(archivo: Path) -> set[str]:
    arbol = ast.parse(archivo.read_text(encoding="utf-8"))
    modulos: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.update(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            base = nodo.module or ""
            modulos.add(base)
            modulos.update(f"{base}.{alias.name}" for alias in nodo.names)
    return modulos


def test_el_mapeador_existe_donde_el_diseno_dice() -> None:
    nombres = {a.name for a in _archivos_del_mapeador()}

    assert {"mapeador.py", "similitud.py", "analisis.py", "validacion.py"} <= nombres


@pytest.mark.parametrize("archivo", _archivos_del_mapeador(), ids=lambda a: a.name)
def test_el_mapeador_no_importa_la_sabana_ni_la_ingesta(archivo) -> None:
    prohibidos = [m for m in _importados(archivo) if "sabana" in m]

    assert prohibidos == []


@pytest.mark.parametrize("archivo", _archivos_del_mapeador(), ids=lambda a: a.name)
def test_el_mapeador_no_importa_adaptadores_ni_api(archivo) -> None:
    prohibidos = [m for m in _importados(archivo) if m.startswith(("app.adapters", "app.api"))]

    assert prohibidos == []


def test_el_mapeador_solo_depende_de_la_biblioteca_estandar_y_de_si_mismo() -> None:
    permitidos = (
        "app.core.entities.mapeador",
        "app.core.services.mapeador",
    )
    for archivo in _archivos_del_mapeador():
        for modulo in _importados(archivo):
            if modulo.startswith("app."):
                assert modulo.startswith(permitidos), (archivo.name, modulo)

"""Contrato: el Speech original sembrado coincide con la tabla de RF-MM-18.

Lee las dos fuentes de verdad —la tabla del documento de requerimientos y la
semilla de la migracion— en vez de una copia guardada en la prueba. Si alguna
deja de encontrarse, la prueba falla con un mensaje, no pasa en verde vacia.
"""

import importlib.util
import re
from pathlib import Path

from app.core.entities.mowa_mes import RANGOS_SEGMENTO, PartesSegmento, Segmento

RAIZ = Path(__file__).resolve().parents[2]
DOCUMENTO = RAIZ / "docs" / "requerimientos-mowa-mes.md"
MIGRACION = RAIZ / "backend" / "migrations" / "versions" / "a4c8e2f6b913_configuracion_mowa_mes.py"

_ETIQUETAS = {rango.etiqueta: rango.segmento for rango in RANGOS_SEGMENTO}
_FILA = re.compile(r"^\s*\| (?P<etiqueta>[^|`]+?) \| `(?P<p1>[^`]*)` \| `(?P<p2>[^`]*)` \|\s*$")


def speech_del_documento() -> tuple[PartesSegmento, ...]:
    texto = DOCUMENTO.read_text(encoding="utf-8")
    inicio = texto.index("**RF-MM-18")
    fin = texto.index("**RF-MM-19")
    partes = [
        PartesSegmento(_ETIQUETAS[m["etiqueta"]], m["p1"], m["p2"])
        for linea in texto[inicio:fin].splitlines()
        if (m := _FILA.match(linea)) and m["etiqueta"] in _ETIQUETAS
    ]
    assert len(partes) == len(RANGOS_SEGMENTO), (
        f"No se encontro la tabla de RF-MM-18 en {DOCUMENTO}"
    )
    return tuple(partes)


def speech_de_la_migracion() -> tuple[PartesSegmento, ...]:
    assert MIGRACION.exists(), f"No se encontro la migracion {MIGRACION}"
    spec = importlib.util.spec_from_file_location("migracion_mowa_mes", MIGRACION)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return tuple(
        PartesSegmento(Segmento(p["segmento"]), p["parte_1"], p["parte_2"])
        for p in modulo.SPEECH_ORIGINAL
    )


def test_la_semilla_de_la_migracion_es_el_texto_exacto_de_rf_mm_18() -> None:
    assert speech_de_la_migracion() == speech_del_documento()


def test_el_documento_trae_los_seis_segmentos_en_orden() -> None:
    assert [p.segmento for p in speech_del_documento()] == [r.segmento for r in RANGOS_SEGMENTO]

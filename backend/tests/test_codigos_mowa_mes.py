"""Contrato: cada codigo de MOWA MES tiene su traduccion en el frontend.

Lee los diccionarios de verdad (`frontend/src/i18n/es.json` y `en.json`), no una
copia. El frontend traduce por codigo con la clave plana
`mowaMes.codigo.<codigo>`; las claves las agrega `dev_frontend_modulo_mowa_mes`
en su bloque `mowaMes.*`. La prueba espejo del frontend comprueba la otra
direccion: que no queden claves de codigos que ya no existen.
"""

import json
from pathlib import Path

import pytest

from app.core.entities.mowa_mes import TIPO_CODIGO, CodigoMowaMes, TipoCodigo

I18N = Path(__file__).resolve().parents[2] / "frontend" / "src" / "i18n"


def _clave(codigo: CodigoMowaMes) -> str:
    return f"mowaMes.codigo.{codigo.value}"


@pytest.mark.parametrize("idioma", ["es", "en"])
def test_cada_codigo_tiene_su_traduccion(idioma) -> None:
    ruta = I18N / f"{idioma}.json"
    assert ruta.exists(), f"No se encontro el diccionario del frontend {ruta}"
    claves = json.loads(ruta.read_text(encoding="utf-8"))

    faltan = [_clave(codigo) for codigo in CodigoMowaMes if _clave(codigo) not in claves]
    vacias = [_clave(c) for c in CodigoMowaMes if _clave(c) in claves and not claves[_clave(c)]]

    assert not faltan, (
        f"Faltan traducciones en {ruta.name}: {faltan}. Las agrega dev_frontend en el bloque "
        "mowaMes.* del diccionario (ver docs/mowa-mes.md, catalogo de codigos)."
    )
    assert not vacias, f"Traducciones vacias en {ruta.name}: {vacias}"


def test_cada_codigo_tiene_tipo() -> None:
    assert set(TIPO_CODIGO) == set(CodigoMowaMes)


def test_las_exclusiones_siguen_el_orden_de_evaluacion() -> None:
    exclusiones = [c for c in CodigoMowaMes if TIPO_CODIGO[c] is TipoCodigo.EXCLUSION]

    assert exclusiones == [
        CodigoMowaMes.TELEFONO_INVALIDO,
        CodigoMowaMes.FALTA_DOCUMENTO,
        CodigoMowaMes.SIN_SPEECH,
        CodigoMowaMes.FALTA_TITULAR,
        CodigoMowaMes.FALTA_VENCIMIENTO,
        CodigoMowaMes.MENSAJE_EXCEDE_160,
    ]

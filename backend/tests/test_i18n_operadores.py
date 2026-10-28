"""Cada operador del backend tiene su texto en el frontend (prueba espejo, T-FV-B2).

El menu de operadores pinta lo que manda `GET /cartera/campos` con `t("op.<operador>")`. Con B1,
`no_en` salio con la clave cruda en el menu porque nadie comprobaba que el texto existiera. Esta
prueba lee los diccionarios de verdad (`frontend/src/i18n/es.json` y `en.json`): un operador nuevo
sin su `op.<operador>` pone la prueba en rojo.
"""

import json
from pathlib import Path

import pytest

from app.core.entities.cartera import OPERADORES_POR_TIPO, Operador
from app.core.services.seleccion_cartera.campos import CatalogoCartera

I18N = Path(__file__).resolve().parents[2] / "frontend" / "src" / "i18n"
IDIOMAS = ["es", "en"]


def _diccionario(idioma: str) -> dict[str, str]:
    return json.loads((I18N / f"{idioma}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("idioma", IDIOMAS)
@pytest.mark.parametrize("operador", list(Operador), ids=lambda o: o.value)
def test_cada_operador_tiene_su_texto_en_el_menu(operador, idioma) -> None:
    clave = f"op.{operador.value}"

    texto = _diccionario(idioma).get(clave, "")

    assert texto.strip(), f"Falta {clave} en {idioma}.json"
    assert texto != clave, f"{clave} en {idioma}.json es la propia clave"


def test_los_operadores_que_manda_la_api_son_los_de_la_prueba() -> None:
    """Lo que llega al menu sale de `catalogo_publico`: todos son `Operador`."""
    enviados = {
        o for campo in CatalogoCartera().catalogo_publico().values() for o in campo["operadores"]
    }

    assert enviados <= {o.value for o in Operador}
    assert enviados <= {o.value for tipo in OPERADORES_POR_TIPO.values() for o in tipo}

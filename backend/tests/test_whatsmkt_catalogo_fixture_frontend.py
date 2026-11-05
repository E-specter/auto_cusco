"""El catalogo de `whatsmkt.mensaje` del fixture del frontend es el que da el backend (T-WM-F4).

El frontend prueba su editor del mensaje contra `frontend/e2e/datos/catalogo-whatsmkt-mensaje.json`:
la respuesta de `GET /texto-enriquecido/catalogo?contexto=whatsmkt.mensaje`, capturada de esta
API y no escrita a mano. Esa copia no se entera sola de un cambio de forma (una variable nueva,
otro campo, otra funcion): esta prueba la compara con la respuesta viva, con el mismo montaje con
que se capturo (dos macros con etiqueta y el tope de 4096), y falla diciendo como regenerarla.
Solo lectura y sin base de datos: el contexto se arma en memoria.
"""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.texto_enriquecido import obtener_registro_contextos, registro_de_contextos
from app.core.services.plataformas.whatsmkt.contexto_texto import contexto_mensaje_texto
from app.core.services.seleccion_cartera.campos import CatalogoCartera
from app.main import app

NOMBRE = "whatsmkt.mensaje"
ETIQUETAS = ("Nombres del titular", "Vencimiento de la cuota")
TOPE = 4096
FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "frontend"
    / "e2e"
    / "datos"
    / "catalogo-whatsmkt-mensaje.json"
)
REGENERAR = (
    "Cambio la respuesta del catalogo de whatsmkt.mensaje: regenera el fixture del frontend con "
    '`cd backend && python -c "from tests.test_whatsmkt_catalogo_fixture_frontend '
    'import regenerar; regenerar()"` '
    "y revisa que solo tenga datos sinteticos (macros de ejemplo y el enlace 900000xxx)."
)


def _respuesta_viva() -> dict:
    contexto = contexto_mensaje_texto(ETIQUETAS, tope=TOPE)
    app.dependency_overrides[obtener_registro_contextos] = lambda: registro_de_contextos(
        CatalogoCartera(), lambda: contexto
    )
    try:
        respuesta = TestClient(app).get("/texto-enriquecido/catalogo", params={"contexto": NOMBRE})
    finally:
        app.dependency_overrides.clear()
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def regenerar() -> None:
    """Escribe el fixture con la respuesta viva: se llama a mano si la forma cambia."""
    texto = json.dumps(_respuesta_viva(), ensure_ascii=False, indent=2)
    FIXTURE.write_text(f"{texto}\n", encoding="utf-8", newline="\n")


def test_el_fixture_del_frontend_es_la_respuesta_viva_del_catalogo_del_mensaje() -> None:
    guardado = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert _respuesta_viva() == guardado, REGENERAR

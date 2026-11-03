"""POST /textos-guardados con el contexto `whatsmkt.mensaje`, sin base (T-WM-B3, paso 2).

El servicio real de textos guardados sobre un repositorio en memoria y el contexto de WhatsMKT con
un tope que la prueba puede cambiar: lo que se comprueba es que las reglas del mensaje (sin emojis
y largo) llegan al usuario como `regla_del_contexto` con el codigo de WhatsMKT y sus parametros, y
que el tope se lee en CADA pedido. Datos sinteticos (telefonos 900000xxx).
"""

import pytest
from fastapi.testclient import TestClient

from app.api.textos_guardados import (
    obtener_registro_contextos_guardados,
    obtener_servicio_textos_guardados,
)
from app.core.services.plataformas.whatsmkt.contexto import (
    CLAVE_CONTEXTO_MENSAJE,
    contexto_mensaje,
)
from app.core.services.textos_guardados.contextos import RegistroContextosGuardados
from app.core.services.textos_guardados.servicio import TextosGuardadosService
from app.main import app
from tests.textos_memoria import RepositorioTextosEnMemoria


@pytest.fixture
def cliente():
    tope = {"valor": 100}
    registro = RegistroContextosGuardados([contexto_mensaje(lambda: tope["valor"])])
    servicio = TextosGuardadosService(RepositorioTextosEnMemoria(), registro)
    app.dependency_overrides[obtener_servicio_textos_guardados] = lambda: servicio
    app.dependency_overrides[obtener_registro_contextos_guardados] = lambda: registro
    try:
        yield TestClient(app), tope
    finally:
        app.dependency_overrides.clear()


def guardar(http, texto, nombre="Mensaje de prueba"):
    return http.post(
        "/textos-guardados",
        json={"contexto": CLAVE_CONTEXTO_MENSAJE, "nombre": nombre, "contenido": {"texto": texto}},
    )


def problemas_de(respuesta) -> list[dict]:
    assert respuesta.status_code == 400
    assert respuesta.json()["codigo"] == "texto_guardado_invalido"
    return respuesta.json()["problemas"]


# --- Lo que se guarda -------------------------------------------------------------------------


def test_un_mensaje_valido_se_guarda(cliente) -> None:
    http, _ = cliente

    respuesta = guardar(http, "Hola [$MACRO1$], tu cuota vence el [$MACRO2$]. INFO por [whatsapp]")

    assert respuesta.status_code == 201
    assert respuesta.json()["contexto"] == "whatsmkt.mensaje"


def test_una_macro_inexistente_se_guarda_igual_porque_no_se_valida_aqui(cliente) -> None:
    # Al guardar no se sabe que definicion se usara: las macros se revisan en la previsualizacion.
    http, _ = cliente

    assert guardar(http, "Hola [$MACRO9$] y [$MACRO0$]").status_code == 201


def test_un_texto_vacio_se_rechaza_con_el_codigo_generico(cliente) -> None:
    http, _ = cliente

    [problema] = problemas_de(guardar(http, "   "))

    assert problema["codigo"] == "texto_guardado_invalido"
    assert problema["campo"] == "contenido"


# --- Emojis -----------------------------------------------------------------------------------


def test_un_emoji_responde_regla_del_contexto_con_su_codigo_y_sus_parametros(cliente) -> None:
    http, _ = cliente

    [problema] = problemas_de(guardar(http, "Hola 😀 gracias"))

    assert problema["codigo"] == "regla_del_contexto"
    assert problema["codigo_contexto"] == "mensaje_con_emoji"
    assert problema["parametros"] == {"caracter": "😀", "posicion": 6}
    assert isinstance(problema["detalle"], str)
    assert problema["campo"] == "contenido"


def test_las_tildes_la_enie_y_los_signos_de_apertura_se_guardan(cliente) -> None:
    http, _ = cliente

    assert guardar(http, "¡Hola! ¿Qué tal, ñandú? Camión © ✓").status_code == 201


# --- Largo con el tope de la configuracion ----------------------------------------------------


def test_un_texto_que_pasa_el_tope_responde_mensaje_largo_con_largo_y_maximo(cliente) -> None:
    http, tope = cliente

    guardar(http, "a" * 100, "Justo")  # el tope exacto se guarda
    [problema] = problemas_de(guardar(http, "a" * 101, "Pasado"))

    assert problema["codigo"] == "regla_del_contexto"
    assert problema["codigo_contexto"] == "mensaje_largo"
    assert problema["parametros"] == {"largo": 101, "maximo": 100}
    assert tope["valor"] == 100


def test_el_tope_se_lee_en_cada_pedido(cliente) -> None:
    http, tope = cliente
    texto = "a" * 150

    antes = guardar(http, texto, "Uno")
    tope["valor"] = 200  # cambia la configuracion: no hace falta reiniciar nada
    despues = guardar(http, texto, "Dos")
    tope["valor"] = 149
    otra_vez = guardar(http, texto, "Tres")

    assert antes.status_code == 400
    assert despues.status_code == 201
    assert problemas_de(otra_vez)[0]["parametros"] == {"largo": 150, "maximo": 149}


def test_whatsapp_cuenta_como_26_caracteres_para_el_tope(cliente) -> None:
    http, _ = cliente

    cabe = guardar(http, "a" * 74 + "[whatsapp]", "Cabe")  # 84 literales, 100 contados
    [problema] = problemas_de(guardar(http, "a" * 75 + "[whatsapp]", "Se pasa"))  # 101 contados

    assert cabe.status_code == 201
    assert problema["codigo_contexto"] == "mensaje_largo"
    assert problema["parametros"] == {"largo": 101, "maximo": 100}


def test_las_macros_cuentan_tal_como_estan_escritas_para_el_tope(cliente) -> None:
    http, _ = cliente

    cabe = guardar(http, "a" * 90 + "[$MACRO1$]", "Cabe")
    se_pasa = guardar(http, "a" * 91 + "[$MACRO1$]", "Se pasa")

    assert (cabe.status_code, se_pasa.status_code) == (201, 400)


def test_un_emoji_y_un_largo_pasado_se_informan_los_dos_en_ese_orden(cliente) -> None:
    http, _ = cliente

    problemas = problemas_de(guardar(http, "😀" + "a" * 120))

    assert [p["codigo_contexto"] for p in problemas] == ["mensaje_con_emoji", "mensaje_largo"]


# --- Versiones y forma del problema -----------------------------------------------------------


def test_una_version_nueva_tambien_pasa_por_las_reglas(cliente) -> None:
    http, _ = cliente
    creado = guardar(http, "Hola").json()

    respuesta = http.post(
        f"/textos-guardados/{creado['id']}/versiones", json={"contenido": {"texto": "Hola 🔥"}}
    )

    [problema] = problemas_de(respuesta)
    assert problema["codigo_contexto"] == "mensaje_con_emoji"


def test_los_campos_ausentes_no_se_serializan_en_un_problema_comun(cliente) -> None:
    # codigo_contexto y parametros son de `regla_del_contexto`: un problema generico no los trae.
    http, _ = cliente

    [problema] = problemas_de(guardar(http, ""))

    assert "codigo_contexto" not in problema and "parametros" not in problema

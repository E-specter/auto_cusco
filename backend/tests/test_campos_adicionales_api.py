"""La API de los campos adicionales sin base de datos (T-CA-B2, RF-64 a RF-66).

Mismo montaje que `test_api_mapeador.py`: un repositorio en memoria y el lector real. Cada codigo de
estado tiene su prueba. Archivos y valores sinteticos.
"""

from tests.test_api_mapeador import Entorno, api  # noqa: F401  (el fixture)

BASE = "/mapeador/borradores"
NUEVO = {"indice": 4, "nombre_legible": "Observación libre", "tipo": "texto"}


def borrador(api: Entorno) -> int:  # noqa: F811
    return api.subir().json()["borrador_id"]


def crear(api: Entorno, borrador_id: int, **cambios):  # noqa: F811
    return api.cliente.post(f"{BASE}/{borrador_id}/campos-adicionales", json={**NUEVO, **cambios})


def test_crear_devuelve_el_campo_y_los_campos_con_los_que_ya_cuenta_el_borrador(api) -> None:  # noqa: F811
    respuesta = crear(api, borrador(api))

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["campo"] == {
        "nombre": "ad_observacion_libre",
        "clave_etiqueta": "campo.ad_observacion_libre",
        "tipo": "texto",
        "obligatorio": False,
        "alias": ["observacion libre"],
        "etiqueta": "Observación libre",
        "adicional": True,
    }
    assert cuerpo["campos"][-1] == cuerpo["campo"]
    assert cuerpo["campos"][0]["adicional"] is False and cuerpo["campos"][0]["etiqueta"] is None


def test_el_campo_creado_se_puede_asignar_y_validar(api) -> None:  # noqa: F811
    analisis = api.subir().json()
    crear(api, analisis["borrador_id"])
    asignaciones = api.asignaciones(analisis)
    asignaciones[4]["campo"] = "ad_observacion_libre"

    respuesta = api.cliente.post(
        f"{BASE}/{analisis['borrador_id']}/validacion", json={"asignaciones": asignaciones}
    )

    assert respuesta.json() == {"problemas": []}


def test_el_catalogo_trae_el_campo_creado_con_su_etiqueta(api) -> None:  # noqa: F811
    crear(api, borrador(api))

    campos = api.cliente.get("/mapeador/catalogos/sabana_vencida").json()["campos"]

    assert campos[-1]["nombre"] == "ad_observacion_libre" and campos[-1]["adicional"] is True


def test_un_nombre_de_un_campo_base_es_un_409_con_ese_campo(api) -> None:  # noqa: F811
    respuesta = crear(api, borrador(api), nombre_legible="Región")

    assert respuesta.status_code == 409
    cuerpo = respuesta.json()
    assert cuerpo["codigo"] == "nombre_repetido" and "detail" in cuerpo
    assert cuerpo["campo"]["nombre"] == "region" and cuerpo["campo"]["adicional"] is False
    assert api.repo.adicionales("sabana_vencida") == ()


def test_un_nombre_de_otro_adicional_es_un_409_con_ese_adicional(api) -> None:  # noqa: F811
    identificador = borrador(api)
    crear(api, identificador)

    respuesta = crear(api, identificador, indice=3, nombre_legible="  OBSERVACION   libre ")

    assert respuesta.status_code == 409
    assert respuesta.json()["campo"]["nombre"] == "ad_observacion_libre"
    assert respuesta.json()["campo"]["adicional"] is True


def test_una_columna_que_no_existe_es_un_404_con_su_codigo(api) -> None:  # noqa: F811
    respuesta = crear(api, borrador(api), indice=40)

    assert respuesta.status_code == 404 and respuesta.json()["codigo"] == "columna_inexistente"


def test_un_borrador_que_no_existe_es_un_404_con_su_codigo(api) -> None:  # noqa: F811
    respuesta = crear(api, 999)

    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "borrador_no_encontrado"


def test_un_tipo_invalido_o_un_nombre_vacio_es_un_422(api) -> None:  # noqa: F811
    identificador = borrador(api)

    assert crear(api, identificador, tipo="booleano").status_code == 422
    assert crear(api, identificador, nombre_legible="   ").status_code == 422
    assert crear(api, identificador, nombre_legible="x" * 81).status_code == 422
    assert crear(api, identificador, indice=-1).status_code == 422
    assert api.repo.adicionales("sabana_vencida") == ()


def test_listar_trae_las_definiciones_con_sus_archivadas(api) -> None:  # noqa: F811
    crear(api, borrador(api))
    api.cliente.patch(
        "/mapeador/sabana_vencida/campos-adicionales/ad_observacion_libre",
        json={"archivado": True},
    )

    respuesta = api.cliente.get("/mapeador/sabana_vencida/campos-adicionales")

    assert respuesta.json() == [
        {
            "nombre": "ad_observacion_libre",
            "nombre_legible": "Observación libre",
            "tipo": "texto",
            "encabezado_origen": "observacion libre",
            "archivado": True,
        }
    ]


def test_renombrar_archivar_y_reactivar(api) -> None:  # noqa: F811
    crear(api, borrador(api))
    url = "/mapeador/sabana_vencida/campos-adicionales/ad_observacion_libre"

    renombrado = api.cliente.patch(url, json={"nombre_legible": "Nota"})
    archivado = api.cliente.patch(url, json={"archivado": True})
    reactivado = api.cliente.patch(url, json={"archivado": False})

    assert renombrado.json()["nombre_legible"] == "Nota"
    assert renombrado.json()["nombre"] == "ad_observacion_libre"
    assert archivado.json()["archivado"] is True and archivado.json()["nombre_legible"] == "Nota"
    assert reactivado.json()["archivado"] is False


def test_renombrar_a_un_nombre_ocupado_es_un_409(api) -> None:  # noqa: F811
    crear(api, borrador(api))

    respuesta = api.cliente.patch(
        "/mapeador/sabana_vencida/campos-adicionales/ad_observacion_libre",
        json={"nombre_legible": "Titular"},
    )

    assert respuesta.status_code == 409 and respuesta.json()["campo"]["nombre"] == "titular"


def test_cambiar_un_campo_o_un_catalogo_que_no_existen_es_un_404(api) -> None:  # noqa: F811
    sin_campo = api.cliente.patch(
        "/mapeador/sabana_vencida/campos-adicionales/ad_nada", json={"nombre_legible": "x"}
    )
    sin_catalogo = api.cliente.patch(
        "/mapeador/otro/campos-adicionales/ad_nada", json={"nombre_legible": "x"}
    )
    listado = api.cliente.get("/mapeador/otro/campos-adicionales")

    assert sin_campo.json()["codigo"] == "campo_adicional_no_encontrado"
    assert sin_catalogo.json()["codigo"] == "catalogo_desconocido"
    assert (sin_campo.status_code, sin_catalogo.status_code, listado.status_code) == (404, 404, 404)


def test_un_cambio_vacio_es_un_422(api) -> None:  # noqa: F811
    respuesta = api.cliente.patch(
        "/mapeador/sabana_vencida/campos-adicionales/ad_observacion_libre", json={}
    )

    assert respuesta.status_code == 422

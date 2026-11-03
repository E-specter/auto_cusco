"""Endpoints de la biblioteca de adjuntos de WhatsMKT, sin base (T-WM-B5).

Sustituyen la dependencia del caso de uso por el servicio real sobre un repositorio en memoria: se
prueba la traduccion HTTP (multipart, codigos con sus parametros, descarga, 404, contrato).
"""

import hashlib
from dataclasses import replace
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from app.api.whatsmkt_adjuntos import obtener_servicio_biblioteca
from app.core.entities.whatsmkt import ConfiguracionWhatsmkt
from app.core.services.plataformas.whatsmkt.biblioteca import BibliotecaWhatsmktService
from app.main import app
from tests.ayudas import adjuntos_sinteticos as sint
from tests.ayudas.repositorio_whatsmkt_falso import RepositorioAdjuntosFalso
from tests.test_api_whatsmkt import PARAMETROS_NULOS

RUTA = "/whatsmkt/adjuntos"


@pytest.fixture
def cliente():
    repositorio = RepositorioAdjuntosFalso()
    app.dependency_overrides[obtener_servicio_biblioteca] = lambda: BibliotecaWhatsmktService(
        repositorio
    )
    try:
        yield TestClient(app), repositorio
    finally:
        app.dependency_overrides.clear()


def _subir(client, contenido: bytes, nombre: str = "archivo.bin", **campos):
    return client.post(RUTA, files={"archivo": (nombre, contenido)}, data=campos)


# --- POST /whatsmkt/adjuntos ----------------------------------------------------------------


def test_subir_una_imagen_responde_201_con_el_adjunto_ya_limpio(cliente) -> None:
    client, repositorio = cliente

    respuesta = _subir(client, sint.jpeg(1080, 1350, metadatos=True), "afiche octubre.jpg")

    assert respuesta.status_code == 201
    limpio = sint.jpeg(1080, 1350)
    assert respuesta.json() == {
        "id": 1,
        "tipo": "imagen_jpeg",
        "nombre": "afiche octubre.jpg",
        "tamano": len(limpio),
        "huella": hashlib.sha256(limpio).hexdigest(),
        "creado_en": "2026-11-02T12:00:00Z",
        "archivado_en": None,
        "ya_existia": False,
    }
    assert repositorio.contenidos[1] == limpio
    assert not any(marca in repositorio.contenidos[1] for marca in sint.MARCAS)


@pytest.mark.parametrize(
    ("contenido", "tipo"),
    [
        (sint.png(), "imagen_png"),
        (sint.PDF, "pdf"),
        (sint.MP4, "video"),
        (sint.MP3_ID3, "audio"),
    ],
)
def test_el_tipo_sale_de_la_firma_y_no_de_la_extension(cliente, contenido, tipo) -> None:
    client, _ = cliente

    respuesta = _subir(client, contenido, "engano.txt")

    assert respuesta.status_code == 201
    assert respuesta.json()["tipo"] == tipo


def test_subir_dos_veces_lo_mismo_devuelve_el_existente_con_ya_existia(cliente) -> None:
    client, repositorio = cliente
    primero = _subir(client, sint.jpeg(metadatos=True), "uno.jpg").json()

    segundo = _subir(
        client, sint.jpeg(metadatos=True).replace(sint.GPS, b"x" * len(sint.GPS)), "dos.jpg"
    )

    assert segundo.status_code == 201
    assert segundo.json() == {**primero, "ya_existia": True}
    assert len(repositorio.adjuntos) == 1


def test_un_nombre_con_ruta_pierde_la_ruta(cliente) -> None:
    client, _ = cliente

    respuesta = _subir(client, sint.PDF, "C:\\Users\\yo\\Desktop\\informe.pdf")

    assert respuesta.json()["nombre"] == "informe.pdf"


NULOS = {**PARAMETROS_NULOS}


@pytest.mark.parametrize(
    ("contenido", "propositos", "codigo", "parametros"),
    [
        (b"hola, esto es texto", "adjunto", "adjunto_tipo", {}),
        (b"hola, esto es texto", "foto", "foto_formato", {}),
        (sint.png(200, 200), "foto", "foto_formato", {}),
        (sint.jpeg(sin_eoi=True), "adjunto", "adjunto_danado", {}),
        (sint.png()[:-4], "adjunto", "adjunto_danado", {}),
        (sint.jpeg(201, 200), "foto", "foto_medidas", {"ancho": 201, "alto": 200}),
        (sint.jpeg(200, 201), "foto", "foto_medidas", {"ancho": 200, "alto": 201}),
        (
            sint.jpeg(relleno=1_000_001 - len(sint.jpeg())),
            "foto",
            "foto_peso",
            {"peso": 1_000_001},
        ),
    ],
    # Sin ids propios, pytest usaria los bytes del archivo (1 MB) como nombre de la prueba.
    ids=[
        "adjunto_tipo",
        "foto_formato_texto",
        "foto_formato_png",
        "danado_jpeg",
        "danado_png",
        "foto_medidas_ancho",
        "foto_medidas_alto",
        "foto_peso",
    ],
)
def test_cada_regla_rota_responde_422_con_su_codigo_y_parametros(
    cliente, contenido, propositos, codigo, parametros
) -> None:
    client, repositorio = cliente

    respuesta = _subir(client, contenido, "x.jpg", proposito=propositos)

    assert respuesta.status_code == 422
    cuerpo = respuesta.json()
    assert cuerpo["codigo"] == codigo
    assert isinstance(cuerpo["detail"], str)
    assert {k: v for k, v in cuerpo.items() if k not in ("detail", "codigo")} == {
        **NULOS,
        **parametros,
    }
    assert repositorio.escrituras == 0


def test_el_peso_de_un_adjunto_responde_con_peso_tipo_y_maximo(cliente) -> None:
    client, repositorio = cliente
    repositorio.configuracion = replace(ConfiguracionWhatsmkt(), tope_pdf=len(sint.PDF) - 1)

    respuesta = _subir(client, sint.PDF, "informe.pdf")

    assert respuesta.status_code == 422
    cuerpo = respuesta.json()
    assert cuerpo["codigo"] == "adjunto_peso"
    assert (cuerpo["peso"], cuerpo["tipo"], cuerpo["maximo"]) == (
        len(sint.PDF),
        "pdf",
        len(sint.PDF) - 1,
    )
    assert repositorio.escrituras == 0


def test_con_el_tope_exacto_se_acepta(cliente) -> None:
    client, repositorio = cliente
    repositorio.configuracion = replace(ConfiguracionWhatsmkt(), tope_pdf=len(sint.PDF))

    assert _subir(client, sint.PDF, "informe.pdf").status_code == 201


def test_una_foto_de_200_x_200_de_hasta_1_mb_se_acepta_como_foto(cliente) -> None:
    client, _ = cliente
    justa = sint.jpeg(relleno=1_000_000 - len(sint.jpeg()))

    respuesta = _subir(client, justa, "yo.jpg", proposito="foto")

    assert respuesta.status_code == 201
    assert respuesta.json()["tamano"] == 1_000_000


def test_un_jpeg_de_otras_medidas_es_adjunto_pero_no_foto(cliente) -> None:
    client, _ = cliente
    grande = sint.jpeg(1080, 1350)

    como_adjunto = _subir(client, grande, "afiche.jpg")
    como_foto = _subir(client, grande, "afiche.jpg", proposito="foto")

    assert como_adjunto.status_code == 201
    assert como_foto.status_code == 422
    assert (como_foto.json()["codigo"], como_foto.json()["ancho"], como_foto.json()["alto"]) == (
        "foto_medidas",
        1080,
        1350,
    )


def test_un_proposito_desconocido_o_sin_archivo_es_el_422_de_validacion(cliente) -> None:
    client, _ = cliente

    desconocido = _subir(client, sint.PDF, "a.pdf", proposito="avatar")
    sin_archivo = client.post(RUTA, data={"proposito": "foto"})

    for respuesta in (desconocido, sin_archivo):
        assert respuesta.status_code == 422
        assert isinstance(respuesta.json()["detail"], list)


# --- GET /whatsmkt/adjuntos -----------------------------------------------------------------


def test_la_biblioteca_lista_activos_y_archivados_sin_contenido(cliente) -> None:
    client, _ = cliente
    uno = _subir(client, sint.PDF, "a.pdf").json()
    dos = _subir(client, sint.MP4, "b.mp4").json()
    client.post(f"{RUTA}/{uno['id']}/archivar")

    activos = client.get(RUTA)
    archivados = client.get(RUTA, params={"archivados": "true"})

    assert [a["id"] for a in activos.json()] == [dos["id"]]
    assert [a["id"] for a in archivados.json()] == [uno["id"]]
    assert archivados.json()[0]["archivado_en"] is not None
    assert all("contenido" not in a for a in activos.json() + archivados.json())


def test_la_biblioteca_vacia_es_una_lista_vacia(cliente) -> None:
    client, _ = cliente

    assert client.get(RUTA).json() == []


# --- Descarga -------------------------------------------------------------------------------


def test_la_descarga_devuelve_el_archivo_guardado_con_su_nombre_original(cliente) -> None:
    client, _ = cliente
    adjunto = _subir(client, sint.jpeg(metadatos=True), "Afiche Año nuevo.jpg").json()

    respuesta = client.get(f"{RUTA}/{adjunto['id']}/contenido")

    assert respuesta.status_code == 200
    assert respuesta.content == sint.jpeg()  # sin metadatos
    assert respuesta.headers["content-type"] == "image/jpeg"
    disposicion = respuesta.headers["content-disposition"]
    assert disposicion.startswith("attachment;")
    assert 'filename="Afiche Ano nuevo.jpg"' in disposicion
    assert f"filename*=UTF-8''{quote('Afiche Año nuevo.jpg')}" in disposicion


@pytest.mark.parametrize(
    ("contenido", "mime"),
    [
        (sint.png(), "image/png"),
        (sint.PDF, "application/pdf"),
        (sint.MP4, "application/octet-stream"),
        (sint.WAV, "application/octet-stream"),
    ],
)
def test_el_tipo_de_contenido_sigue_al_tipo_del_adjunto(cliente, contenido, mime) -> None:
    client, _ = cliente
    adjunto = _subir(client, contenido, "x").json()

    assert client.get(f"{RUTA}/{adjunto['id']}/contenido").headers["content-type"] == mime


# --- Archivar y desarchivar -----------------------------------------------------------------


def test_archivar_y_desarchivar(cliente) -> None:
    client, _ = cliente
    adjunto = _subir(client, sint.PDF, "a.pdf").json()

    archivado = client.post(f"{RUTA}/{adjunto['id']}/archivar")
    repetido = client.post(f"{RUTA}/{adjunto['id']}/archivar")
    restaurado = client.post(f"{RUTA}/{adjunto['id']}/desarchivar")

    assert archivado.status_code == 200
    assert archivado.json()["archivado_en"] is not None
    assert repetido.json() == archivado.json()
    assert restaurado.status_code == 200
    assert restaurado.json()["archivado_en"] is None
    assert "ya_existia" not in restaurado.json()


@pytest.mark.parametrize(
    ("metodo", "ruta"),
    [
        ("get", "/99/contenido"),
        ("post", "/99/archivar"),
        ("post", "/99/desarchivar"),
    ],
)
def test_un_adjunto_que_no_existe_responde_404(cliente, metodo: str, ruta: str) -> None:
    client, _ = cliente

    respuesta = getattr(client, metodo)(RUTA + ruta)

    assert respuesta.status_code == 404
    assert isinstance(respuesta.json()["detail"], str)


# --- Contrato -------------------------------------------------------------------------------


def test_el_contrato_declara_el_multipart_los_codigos_y_la_descarga() -> None:
    esquema = app.openapi()
    rutas = esquema["paths"]

    subida = rutas[RUTA]["post"]
    assert set(subida["responses"]) >= {"201", "422"}
    assert subida["responses"]["422"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ErrorWhatsmktRespuesta"
    )
    assert "multipart/form-data" in subida["requestBody"]["content"]
    assert set(rutas) >= {
        RUTA,
        f"{RUTA}/{{adjunto_id}}/contenido",
        f"{RUTA}/{{adjunto_id}}/archivar",
        f"{RUTA}/{{adjunto_id}}/desarchivar",
    }
    error = esquema["components"]["schemas"]["ErrorWhatsmktRespuesta"]
    assert set(error["required"]) >= {"detail", "codigo", "peso", "maximo", "tipo", "ancho", "alto"}
    descarga = rutas[f"{RUTA}/{{adjunto_id}}/contenido"]["get"]["responses"]["200"]
    assert "Content-Disposition" in descarga["headers"]

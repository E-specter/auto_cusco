"""Adjuntos de WhatsMKT: firma, tamano, limpieza de metadatos y foto, sin base (T-WM-B5).

Los archivos se arman en la prueba (`tests/ayudas/adjuntos_sinteticos.py`), nunca se leen de disco.
"""

import hashlib
from dataclasses import replace

import pytest

from app.core.entities.whatsmkt import (
    AdjuntoNoEncontrado,
    CodigoWhatsmkt,
    ConfiguracionWhatsmkt,
    ErrorWhatsmkt,
    TipoAdjunto,
)
from app.core.services.plataformas.whatsmkt import adjuntos
from app.core.services.plataformas.whatsmkt.biblioteca import (
    BibliotecaWhatsmktService,
    nombre_de_archivo,
)
from tests.ayudas import adjuntos_sinteticos as sint
from tests.ayudas.repositorio_whatsmkt_falso import RepositorioAdjuntosFalso


def _servicio(**tope) -> tuple[BibliotecaWhatsmktService, RepositorioAdjuntosFalso]:
    repositorio = RepositorioAdjuntosFalso(replace(ConfiguracionWhatsmkt(), **tope))
    return BibliotecaWhatsmktService(repositorio), repositorio


def _error(llamada, *args) -> ErrorWhatsmkt:
    with pytest.raises(ErrorWhatsmkt) as error:
        llamada(*args)
    return error.value


# --- Tipo por firma -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("contenido", "tipo"),
    [
        (sint.jpeg(), TipoAdjunto.IMAGEN_JPEG),
        (sint.png(), TipoAdjunto.IMAGEN_PNG),
        (sint.PDF, TipoAdjunto.PDF),
        (sint.MP4, TipoAdjunto.VIDEO),
        (sint.MOV, TipoAdjunto.VIDEO),
        (sint.GP3, TipoAdjunto.VIDEO),
        (sint.M4A, TipoAdjunto.AUDIO),
        (sint.MP3_ID3, TipoAdjunto.AUDIO),
        (sint.MP3_CUADRO, TipoAdjunto.AUDIO),
        (sint.AAC_ADTS, TipoAdjunto.AUDIO),
        (sint.OGG, TipoAdjunto.AUDIO),
        (sint.WAV, TipoAdjunto.AUDIO),
        (sint.AMR, TipoAdjunto.AUDIO),
        (sint.AMR_WB, TipoAdjunto.AUDIO),
    ],
)
def test_el_tipo_se_reconoce_por_la_firma(contenido: bytes, tipo: TipoAdjunto) -> None:
    assert adjuntos.tipo_por_firma(contenido[: adjuntos.LARGO_CABECERA]) is tipo


@pytest.mark.parametrize(
    "contenido",
    [
        b"",
        b"hola, esto es texto",
        b"MZ\x90\x00" + bytes(28),  # un ejecutable
        b"PK\x03\x04" + bytes(28),  # un zip (xlsx, docx)
        b"GIF89a" + bytes(26),
        b"RIFF\x24\x00\x00\x00AVI " + bytes(16),  # RIFF que no es WAVE
        b"\xff\xd8",  # JPEG sin el tercer byte de la firma
        b"\xff\xe0\x00\x00",  # sincronia con la capa y la version reservadas
    ],
)
def test_lo_que_no_se_reconoce_no_tiene_tipo(contenido: bytes) -> None:
    assert adjuntos.tipo_por_firma(contenido) is None


def test_un_tipo_desconocido_es_adjunto_tipo_y_como_foto_es_foto_formato() -> None:
    servicio, _ = _servicio()

    como_adjunto = _error(servicio.admitir, b"texto plano", 11, False)
    como_foto = _error(servicio.admitir, b"texto plano", 11, True)

    assert como_adjunto.codigo is CodigoWhatsmkt.ADJUNTO_TIPO
    assert como_foto.codigo is CodigoWhatsmkt.FOTO_FORMATO


def test_la_extension_no_cuenta_el_servicio_ni_la_ve() -> None:
    servicio, repositorio = _servicio()

    # Un PDF "llamado" foto.jpg y un PNG "llamado" informe.pdf: el tipo sale del contenido.
    pdf, _ = servicio.guardar("foto.jpg", sint.PDF)
    imagen, _ = servicio.guardar("informe.pdf", sint.png())

    assert (pdf.tipo, pdf.nombre) == (TipoAdjunto.PDF, "foto.jpg")
    assert (imagen.tipo, imagen.nombre) == (TipoAdjunto.IMAGEN_PNG, "informe.pdf")
    assert len(repositorio.adjuntos) == 2


# --- Tamano ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tipo", "campo", "contenido"),
    [
        (TipoAdjunto.PDF, "tope_pdf", sint.PDF),
        (TipoAdjunto.VIDEO, "tope_video", sint.MP4),
        (TipoAdjunto.AUDIO, "tope_audio", sint.WAV),
    ],
)
def test_el_tope_exacto_pasa_y_un_byte_mas_no(tipo, campo, contenido) -> None:
    servicio, _ = _servicio(**{campo: 1000})
    justo = contenido.ljust(1000, b"\x00")

    assert servicio.admitir(justo[:32], 1000) is tipo
    error = _error(servicio.admitir, justo[:32], 1001, False)

    assert error.codigo is CodigoWhatsmkt.ADJUNTO_PESO
    assert error.parametros == {"peso": 1001, "tipo": tipo.value, "maximo": 1000}


def test_el_tamano_se_controla_con_la_cabecera_sin_leer_el_resto() -> None:
    servicio, repositorio = _servicio(tope_pdf=1000)

    # `admitir` solo recibe la cabecera y el tamano declarado: no hay contenido que leer.
    error = _error(servicio.admitir, sint.PDF[:32], 10_000_000_000, False)

    assert error.codigo is CodigoWhatsmkt.ADJUNTO_PESO
    assert repositorio.escrituras == 0


def test_los_topes_de_la_configuracion_se_leen_en_cada_subida() -> None:
    servicio, repositorio = _servicio()
    assert servicio.admitir(sint.PDF[:32], 5000) is TipoAdjunto.PDF

    repositorio.configuracion = replace(repositorio.configuracion, tope_pdf=4999)

    assert _error(servicio.admitir, sint.PDF[:32], 5000, False).parametros["maximo"] == 4999


def test_la_imagen_tiene_el_tope_fijo_de_imagen() -> None:
    servicio, _ = _servicio()
    cabecera = sint.png()[:32]

    assert servicio.admitir(cabecera, adjuntos.TOPE_IMAGEN_BYTES) is TipoAdjunto.IMAGEN_PNG
    error = _error(servicio.admitir, cabecera, adjuntos.TOPE_IMAGEN_BYTES + 1, False)

    assert error.parametros["maximo"] == adjuntos.TOPE_IMAGEN_BYTES


def test_guardar_vuelve_a_comprobar_el_tamano_con_los_bytes_reales() -> None:
    servicio, repositorio = _servicio(tope_pdf=len(sint.PDF) - 1)

    error = _error(servicio.guardar, "a.pdf", sint.PDF)

    assert error.codigo is CodigoWhatsmkt.ADJUNTO_PESO
    assert repositorio.escrituras == 0


# --- Limpieza de JPEG -----------------------------------------------------------------------


def test_la_limpieza_del_jpeg_quita_exif_xmp_iptc_y_comentario_y_deja_el_resto_byte_a_byte() -> (
    None
):
    sucio = sint.jpeg(metadatos=True)

    limpio = adjuntos.limpiar_jpeg(sucio)

    # Es exactamente el mismo archivo armado sin metadatos: JFIF, ICC, tablas, SOF, SOS, los datos
    # comprimidos (con su FF00 y su RST0) y el EOI no cambian ni un byte.
    assert limpio == sint.jpeg(metadatos=False)
    assert not any(marca in limpio for marca in sint.MARCAS)
    assert sint.ICC in limpio
    assert len(limpio) < len(sucio)


def test_la_limpieza_deja_el_perfil_de_color_aunque_haya_metadatos() -> None:
    limpio = adjuntos.limpiar_jpeg(sint.jpeg(metadatos=True, icc=True))

    assert sint.segmento_jpeg(0xE2, sint.ICC) in limpio


def test_un_jpeg_sin_metadatos_queda_igual() -> None:
    plano = sint.jpeg()

    assert adjuntos.limpiar_jpeg(plano) == plano
    assert adjuntos.limpiar_jpeg(adjuntos.limpiar_jpeg(plano)) == plano  # idempotente


def test_lo_que_hay_despues_del_eoi_se_descarta() -> None:
    assert adjuntos.limpiar_jpeg(sint.jpeg(cola=b"MINIATURA-SINTETICA")) == sint.jpeg()


def test_un_ff_dentro_de_los_datos_comprimidos_no_se_toma_por_un_marcador_a_quitar() -> None:
    # Un `FF E1` literal en los datos comprimidos iria como `FF 00 E1`: no es un APP1.
    con_ff = sint.jpeg().replace(b"\x12\x34\xff\x00\x56", b"\x12\x34\xff\x00\xe1\x56")

    assert adjuntos.limpiar_jpeg(con_ff) == con_ff


@pytest.mark.parametrize("corte", [1, 2, 10, 60, 120, 150])
def test_un_jpeg_cortado_es_adjunto_danado(corte: int) -> None:
    completo = sint.jpeg(metadatos=True)
    assert corte < len(completo)

    error = _error(adjuntos.limpiar_jpeg, completo[:corte])

    assert error.codigo is CodigoWhatsmkt.ADJUNTO_DANADO


def test_un_jpeg_sin_eoi_o_cortado_en_los_datos_es_adjunto_danado() -> None:
    assert _error(adjuntos.limpiar_jpeg, sint.jpeg(sin_eoi=True)).codigo is (
        CodigoWhatsmkt.ADJUNTO_DANADO
    )
    sin_final = sint.jpeg()[:-2]
    assert _error(adjuntos.limpiar_jpeg, sin_final).codigo is CodigoWhatsmkt.ADJUNTO_DANADO


def test_un_segmento_con_un_largo_que_se_sale_del_archivo_es_adjunto_danado() -> None:
    roto = b"\xff\xd8\xff\xe1\xff\xff" + b"\x00" * 20

    assert _error(adjuntos.limpiar_jpeg, roto).codigo is CodigoWhatsmkt.ADJUNTO_DANADO


# --- Limpieza de PNG ------------------------------------------------------------------------


def test_la_limpieza_del_png_quita_texto_exif_y_fecha_y_deja_el_resto_con_sus_crc() -> None:
    sucio = sint.png(metadatos=True)

    limpio = adjuntos.limpiar_png(sucio)

    assert limpio == sint.png(metadatos=False)
    assert not any(marca in limpio for marca in sint.MARCAS)
    assert b"iCCP" in limpio
    assert b"pHYs" in limpio
    assert b"IDAT" in limpio


def test_un_png_sin_metadatos_queda_igual_y_lo_de_despues_del_iend_se_descarta() -> None:
    plano = sint.png()

    assert adjuntos.limpiar_png(plano) == plano
    assert adjuntos.limpiar_png(sint.png(cola=b"BASURA")) == plano


@pytest.mark.parametrize("corte", [4, 8, 12, 20, 40, 70])
def test_un_png_cortado_es_adjunto_danado(corte: int) -> None:
    completo = sint.png(metadatos=True)

    assert _error(adjuntos.limpiar_png, completo[:corte]).codigo is CodigoWhatsmkt.ADJUNTO_DANADO


def test_un_png_sin_iend_es_adjunto_danado() -> None:
    sin_iend = sint.png()[: -len(sint.bloque_png(b"IEND", b""))]

    assert _error(adjuntos.limpiar_png, sin_iend).codigo is CodigoWhatsmkt.ADJUNTO_DANADO


def test_un_png_con_un_bloque_alterado_es_adjunto_danado() -> None:
    alterado = bytearray(sint.png())
    alterado[sint.png().index(b"IDAT") + 6] ^= 0xFF  # un byte de los datos: el CRC ya no cuadra

    assert _error(adjuntos.limpiar_png, bytes(alterado)).codigo is CodigoWhatsmkt.ADJUNTO_DANADO


def test_un_png_que_no_empieza_con_ihdr_es_adjunto_danado() -> None:
    sin_ihdr = b"\x89PNG\r\n\x1a\n" + sint.bloque_png(b"IDAT", b"x") + sint.bloque_png(b"IEND", b"")

    assert _error(adjuntos.limpiar_png, sin_ihdr).codigo is CodigoWhatsmkt.ADJUNTO_DANADO


# --- Video, audio y PDF ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tipo", "contenido"),
    [
        (TipoAdjunto.PDF, sint.PDF),
        (TipoAdjunto.VIDEO, sint.MP4),
        (TipoAdjunto.AUDIO, sint.WAV),
    ],
)
def test_video_audio_y_pdf_se_guardan_tal_como_llegan(tipo, contenido) -> None:
    assert adjuntos.limpiar(tipo, contenido) is contenido


def test_las_imagenes_se_guardan_sin_metadatos_en_la_biblioteca() -> None:
    servicio, repositorio = _servicio()

    guardado, _ = servicio.guardar("a.jpg", sint.jpeg(metadatos=True))

    assert repositorio.contenidos[guardado.id] == sint.jpeg()
    assert guardado.tamano == len(sint.jpeg())


# --- Foto de perfil -------------------------------------------------------------------------


def test_la_medida_se_lee_del_marcador_sof() -> None:
    assert adjuntos.medidas_jpeg(sint.jpeg(200, 200)) == (200, 200)
    assert adjuntos.medidas_jpeg(sint.jpeg(640, 480, metadatos=True)) == (640, 480)


def test_un_jpeg_sin_sof_es_adjunto_danado_al_medirlo() -> None:
    sin_sof = b"\xff\xd8" + sint.segmento_jpeg(0xE0, b"JFIF\x00") + b"\xff\xd9"

    assert _error(adjuntos.medidas_jpeg, sin_sof).codigo is CodigoWhatsmkt.ADJUNTO_DANADO


def test_una_foto_de_200_x_200_pasa() -> None:
    servicio, _ = _servicio()

    guardada, ya_existia = servicio.guardar("yo.jpg", sint.jpeg(200, 200), como_foto=True)

    assert guardada.tipo is TipoAdjunto.IMAGEN_JPEG
    assert not ya_existia


@pytest.mark.parametrize(("ancho", "alto"), [(201, 200), (200, 201), (199, 200), (1, 1)])
def test_una_foto_de_otras_medidas_es_foto_medidas_con_las_leidas(ancho, alto) -> None:
    servicio, repositorio = _servicio()

    error = _error(servicio.guardar, "yo.jpg", sint.jpeg(ancho, alto), True)

    assert error.codigo is CodigoWhatsmkt.FOTO_MEDIDAS
    assert error.parametros == {"ancho": ancho, "alto": alto}
    assert repositorio.escrituras == 0


def test_un_jpeg_de_otras_medidas_si_es_un_adjunto_de_imagen() -> None:
    servicio, _ = _servicio()

    guardado, _ = servicio.guardar("afiche.jpg", sint.jpeg(1080, 1350))

    assert guardado.tipo is TipoAdjunto.IMAGEN_JPEG


def test_una_foto_que_no_es_jpeg_es_foto_formato() -> None:
    servicio, _ = _servicio()

    for contenido in (sint.png(200, 200), sint.PDF):
        assert _error(servicio.guardar, "yo", contenido, True).codigo is CodigoWhatsmkt.FOTO_FORMATO


def test_la_foto_de_1_mb_pasa_y_con_un_byte_mas_es_foto_peso() -> None:
    servicio, repositorio = _servicio()
    base = len(sint.jpeg())
    justa = sint.jpeg(relleno=1_000_000 - base)
    pasada = sint.jpeg(relleno=1_000_001 - base)
    assert (len(justa), len(pasada)) == (1_000_000, 1_000_001)

    guardada, _ = servicio.guardar("yo.jpg", justa, como_foto=True)
    error = _error(servicio.guardar, "yo2.jpg", pasada, True)

    assert guardada.tamano == 1_000_000
    assert error.codigo is CodigoWhatsmkt.FOTO_PESO
    assert error.parametros == {"peso": 1_000_001}
    assert len(repositorio.adjuntos) == 1


def test_la_foto_se_mide_aunque_el_archivo_traiga_otra_cosa_en_el_exif() -> None:
    servicio, _ = _servicio()
    mentirosa = sint.jpeg(300, 300, metadatos=True)

    assert _error(servicio.guardar, "yo.jpg", mentirosa, True).parametros == {
        "ancho": 300,
        "alto": 300,
    }


# --- Huella y biblioteca --------------------------------------------------------------------


def test_dos_fotos_iguales_con_distinto_exif_se_guardan_una_sola_vez() -> None:
    servicio, repositorio = _servicio()
    con_gps = sint.jpeg(metadatos=True)
    otra_camara = sint.jpeg(metadatos=True).replace(
        sint.CAMARA, b"OTRA-CAMARA-SINT"
    )  # mismo largo: no rompe el segmento
    assert con_gps != otra_camara

    primero, repetido_antes = servicio.guardar("uno.jpg", con_gps)
    segundo, repetido_despues = servicio.guardar("dos.jpg", otra_camara)

    assert (repetido_antes, repetido_despues) == (False, True)
    assert segundo == primero
    assert len(repositorio.adjuntos) == 1
    assert primero.huella == hashlib.sha256(sint.jpeg()).hexdigest()  # la huella es del limpio
    assert primero.nombre == "uno.jpg"


def test_un_archivo_repetido_devuelve_el_existente_aunque_este_archivado() -> None:
    servicio, repositorio = _servicio()
    original, _ = servicio.guardar("a.pdf", sint.PDF)
    servicio.archivar(original.id)

    de_nuevo, ya_existia = servicio.guardar("b.pdf", sint.PDF)

    assert ya_existia
    assert de_nuevo.archivado_en is not None
    assert len(repositorio.adjuntos) == 1


def test_archivar_desarchivar_y_listar() -> None:
    servicio, _ = _servicio()
    uno, _ = servicio.guardar("a.pdf", sint.PDF)
    dos, _ = servicio.guardar("b.mp4", sint.MP4)

    archivado = servicio.archivar(uno.id)
    otra_vez = servicio.archivar(uno.id)

    assert archivado.archivado_en is not None
    assert otra_vez.archivado_en == archivado.archivado_en
    assert [a.id for a in servicio.listar()] == [dos.id]
    assert [a.id for a in servicio.listar(archivados=True)] == [uno.id]
    assert servicio.desarchivar(uno.id).archivado_en is None
    assert {a.id for a in servicio.listar()} == {uno.id, dos.id}


def test_el_contenido_se_descarga_con_su_adjunto() -> None:
    servicio, _ = _servicio()
    guardado, _ = servicio.guardar("a.pdf", sint.PDF)

    adjunto, contenido = servicio.contenido(guardado.id)

    assert (adjunto, contenido) == (guardado, sint.PDF)


@pytest.mark.parametrize("operacion", ["obtener", "contenido", "archivar", "desarchivar"])
def test_un_adjunto_que_no_existe_lanza_adjunto_no_encontrado(operacion: str) -> None:
    servicio, _ = _servicio()

    with pytest.raises(AdjuntoNoEncontrado) as error:
        getattr(servicio, operacion)(99)

    assert error.value.adjunto_id == 99


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("afiche octubre.jpg", "afiche octubre.jpg"),
        ("C:\\Users\\yo\\Desktop\\afiche.jpg", "afiche.jpg"),
        ("/tmp/x/afiche.jpg", "afiche.jpg"),
        ("  ", "adjunto"),
        (None, "adjunto"),
        ("a" * 400, "a" * 255),
    ],
)
def test_el_nombre_pierde_la_ruta_y_nunca_queda_vacio(entrada, esperado) -> None:
    assert nombre_de_archivo(entrada) == esperado


# --- La foto como regla reutilizable ----------------------------------------------------------


def test_validar_foto_de_es_la_regla_sobre_los_bytes_sin_importar_como_se_subio() -> None:
    assert adjuntos.validar_foto_de(sint.jpeg(200, 200)) is None
    assert adjuntos.validar_foto_de(sint.jpeg(200, 200, metadatos=True)) is None

    assert _error(adjuntos.validar_foto_de, sint.jpeg(201, 200)).parametros == {
        "ancho": 201,
        "alto": 200,
    }
    assert _error(adjuntos.validar_foto_de, sint.png(200, 200)).codigo is (
        CodigoWhatsmkt.FOTO_FORMATO
    )
    assert _error(adjuntos.validar_foto_de, b"texto").codigo is CodigoWhatsmkt.FOTO_FORMATO
    grande = sint.jpeg(relleno=1_000_001 - len(sint.jpeg()))
    assert _error(adjuntos.validar_foto_de, grande).codigo is CodigoWhatsmkt.FOTO_PESO
    assert _error(adjuntos.validar_foto_de, sint.jpeg(sin_eoi=True)).codigo is (
        CodigoWhatsmkt.ADJUNTO_DANADO
    )


def test_un_adjunto_subido_sin_proposito_se_valida_despues_como_foto() -> None:
    servicio, _ = _servicio()
    buena, _ = servicio.guardar("yo.jpg", sint.jpeg(200, 200))
    mala, _ = servicio.guardar("afiche.jpg", sint.jpeg(1080, 1350))
    png, _ = servicio.guardar("logo.png", sint.png(200, 200))

    assert servicio.validar_como_foto(buena.id) == buena
    assert _error(servicio.validar_como_foto, mala.id).codigo is CodigoWhatsmkt.FOTO_MEDIDAS
    assert _error(servicio.validar_como_foto, png.id).codigo is CodigoWhatsmkt.FOTO_FORMATO
    with pytest.raises(AdjuntoNoEncontrado):
        servicio.validar_como_foto(99)


def test_subir_como_foto_un_archivo_ya_subido_como_adjunto_devuelve_el_mismo() -> None:
    servicio, repositorio = _servicio()
    como_adjunto, _ = servicio.guardar("yo.jpg", sint.jpeg(200, 200, metadatos=True))

    como_foto, ya_existia = servicio.guardar("yo2.jpg", sint.jpeg(200, 200), como_foto=True)

    assert ya_existia
    assert como_foto == como_adjunto
    assert len(repositorio.adjuntos) == 1


# --- Orientacion del JPEG (DU-WM-12) ----------------------------------------------------------

# El APP1 minimo, escrito a mano: `Exif`, TIFF, un IFD0 con la entrada Orientation = 6 y sin IFD
# siguiente. Uno por orden de bytes.
EXIF_MINIMO_II_6 = (
    b"Exif\x00\x00" + b"II*\x00\x08\x00\x00\x00" + b"\x01\x00"
    b"\x12\x01\x03\x00\x01\x00\x00\x00\x06\x00\x00\x00" + b"\x00\x00\x00\x00"
)
EXIF_MINIMO_MM_6 = (
    b"Exif\x00\x00" + b"MM\x00*\x00\x00\x00\x08" + b"\x00\x01"
    b"\x01\x12\x00\x03\x00\x00\x00\x01\x00\x06\x00\x00" + b"\x00\x00\x00\x00"
)


def _exif_minimo(orientacion: int, orden: str) -> bytes:
    """Lo mismo, armado aparte del codigo de produccion, para cualquier orientacion."""
    e = "little" if orden == "II" else "big"
    tiff = orden.encode() + (42).to_bytes(2, e) + (8).to_bytes(4, e) + (1).to_bytes(2, e)
    tiff += (0x0112).to_bytes(2, e) + (3).to_bytes(2, e) + (1).to_bytes(4, e)
    tiff += orientacion.to_bytes(2, e) + b"\x00\x00" + (0).to_bytes(4, e)
    return b"Exif\x00\x00" + tiff


@pytest.mark.parametrize("orden", ["II", "MM"])
@pytest.mark.parametrize("orientacion", [2, 3, 4, 5, 6, 7, 8])
def test_la_limpieza_deja_solo_la_orientacion_y_el_resto_byte_a_byte(orientacion, orden) -> None:
    sucio = sint.jpeg(metadatos=True, exif=sint.exif_tiff(orientacion, orden))
    assert sint.GPS in sucio
    assert sint.CAMARA in sucio

    limpio = adjuntos.limpiar_jpeg(sucio)

    # Es el archivo armado con ese unico APP1 en el mismo lugar: JFIF, ICC, tablas, SOF, SOS y datos
    # comprimidos no cambian ni un byte, y no queda GPS, camara, XMP, IPTC ni comentario.
    assert limpio == sint.jpeg(exif=_exif_minimo(orientacion, orden))
    assert not any(marca in limpio for marca in sint.MARCAS)
    assert sint.ICC in limpio


def test_el_app1_de_orientacion_es_el_minimo_exacto_en_los_dos_ordenes() -> None:
    ii = adjuntos.limpiar_jpeg(sint.jpeg(exif=sint.exif_tiff(6, "II")))
    mm = adjuntos.limpiar_jpeg(sint.jpeg(exif=sint.exif_tiff(6, "MM")))

    assert ii == sint.jpeg(exif=EXIF_MINIMO_II_6)
    assert mm == sint.jpeg(exif=EXIF_MINIMO_MM_6)
    assert sint.segmento_jpeg(0xE1, EXIF_MINIMO_II_6) in ii
    assert len(EXIF_MINIMO_II_6) == len(EXIF_MINIMO_MM_6) == 32


@pytest.mark.parametrize("orden", ["II", "MM"])
def test_orientacion_1_o_sin_orientacion_no_deja_app1(orden) -> None:
    for exif in (sint.exif_tiff(1, orden), sint.exif_tiff(None, orden)):
        limpio = adjuntos.limpiar_jpeg(sint.jpeg(metadatos=True, exif=exif))

        assert limpio == sint.jpeg()
        assert b"Exif" not in limpio


def _tiff_con(orientacion: int | None = 6, **cambios) -> bytes:
    """El EXIF valido (orden II) con bytes cambiados: `pN` es la posicion N contada desde el
    `Exif` (el TIFF empieza en 6, el IFD0 en 14 y la entrada Orientation en 28)."""
    base = bytearray(sint.exif_tiff(orientacion, "II"))
    for posicion, valor in cambios.items():
        indice = int(posicion.removeprefix("p"))
        base[indice : indice + len(valor)] = valor
    return bytes(base)


@pytest.mark.parametrize(
    "exif",
    [
        pytest.param(b"Exif\x00\x00", id="sin_tiff"),
        pytest.param(b"Exif\x00\x00" + b"basura" * 5, id="basura"),
        pytest.param(sint.exif_tiff(6, "II")[:20], id="cortado_en_el_ifd"),
        pytest.param(sint.exif_tiff(6, "II")[:12], id="cortado_antes_del_ifd"),
        pytest.param(_tiff_con(p8=b"\x00"), id="magico_distinto_de_42"),
        pytest.param(_tiff_con(p10=b"\xff\xff\xff\x7f"), id="ifd_fuera_del_archivo"),
        pytest.param(_tiff_con(p10=b"\x02\x00\x00\x00"), id="ifd_dentro_del_encabezado"),
        # Sin orientacion que encontrar, una cuenta enorme de entradas se sale del archivo.
        pytest.param(_tiff_con(None, p14=b"\xff\xff"), id="entradas_de_mas_que_se_salen"),
        pytest.param(_tiff_con(p30=b"\x04"), id="orientacion_que_no_es_short"),
        pytest.param(_tiff_con(p32=b"\x02"), id="orientacion_con_cuenta_2"),
        pytest.param(_tiff_con(p36=b"\x00"), id="orientacion_0"),
        pytest.param(_tiff_con(p36=b"\x09"), id="orientacion_9"),
    ],
)
def test_un_exif_ilegible_se_quita_entero_sin_error(exif: bytes) -> None:
    limpio = adjuntos.limpiar_jpeg(sint.jpeg(exif=exif))

    assert limpio == sint.jpeg()


def test_el_xmp_se_quita_siempre_aunque_traiga_orientacion() -> None:
    xmp = b"http://ns.adobe.com/xap/1.0/\x00" + sint.XMP + b' tiff:Orientation="6"'
    sucio = b"\xff\xd8" + sint.segmento_jpeg(0xE1, xmp) + sint.jpeg()[2:]

    limpio = adjuntos.limpiar_jpeg(sucio)

    assert limpio == sint.jpeg()
    assert sint.XMP not in limpio


def test_la_orientacion_es_estable_y_no_rompe_la_foto_ni_la_huella() -> None:
    sucio = sint.jpeg(metadatos=True, exif=sint.exif_tiff(6, "II"))

    una_vez = adjuntos.limpiar_jpeg(sucio)

    assert adjuntos.limpiar_jpeg(una_vez) == una_vez  # idempotente: la huella no cambia
    assert adjuntos.medidas_jpeg(una_vez) == (200, 200)
    adjuntos.validar_foto_de(una_vez)  # sigue sirviendo de foto de perfil


def test_dos_fotos_con_la_misma_orientacion_y_distinta_camara_o_gps_son_un_adjunto() -> None:
    servicio, repositorio = _servicio()
    una = sint.jpeg(exif=sint.exif_tiff(6, "II"))
    otra = sint.jpeg(exif=sint.exif_tiff(6, "II").replace(sint.CAMARA, b"OTRA-CAMARA-SINT"))
    girada = sint.jpeg(exif=sint.exif_tiff(8, "II"))

    primera, _ = servicio.guardar("a.jpg", una)
    segunda, repetida = servicio.guardar("b.jpg", otra)
    tercera, _ = servicio.guardar("c.jpg", girada)

    assert repetida
    assert segunda == primera
    assert tercera.huella != primera.huella  # otra orientacion es otro archivo
    assert len(repositorio.adjuntos) == 2

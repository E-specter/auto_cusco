"""Archivos sinteticos para las pruebas de adjuntos de WhatsMKT.

Armados byte a byte, sin Pillow: un JPEG y un PNG con la estructura correcta (no se pueden
decodificar a una imagen, ni hace falta) y con metadatos sinteticos que la limpieza debe quitar.
"""

import zlib

# Marcas que no existen en ningun otro lado: si sobreviven a la limpieza, se ve.
GPS = b"GPS-SINTETICO-12.34S-76.54W"
CAMARA = b"CAMARA-SINTETICA"
COMENTARIO = b"COMENTARIO-SINTETICO"
IPTC = b"IPTC-SINTETICO"
XMP = b"XMP-SINTETICO"
TEXTO = b"AUTOR-SINTETICO"
ICC = b"ICC_PROFILE\x00\x01\x01" + bytes(range(60, 120))
MARCAS = (GPS, CAMARA, COMENTARIO, IPTC, XMP, TEXTO)


def segmento_jpeg(marcador: int, datos: bytes) -> bytes:
    return b"\xff" + bytes([marcador]) + (len(datos) + 2).to_bytes(2, "big") + datos


def exif_tiff(orientacion: int | None, orden: str = "II") -> bytes:
    """Un APP1 EXIF valido (`Exif`, TIFF y tres entradas en el IFD0: Make, Orientation y un puntero
    al IFD de GPS), con la camara y el GPS sinteticos. Sin `orientacion` no lleva la entrada.

    `orden` es `II` (little-endian) o `MM` (big-endian). Devuelve el contenido del APP1, sin el
    marcador ni el largo.
    """
    e = "little" if orden == "II" else "big"

    def corto(n: int) -> bytes:
        return n.to_bytes(2, e)

    def largo(n: int) -> bytes:
        return n.to_bytes(4, e)

    entradas = 3 if orientacion is not None else 2
    inicio_datos = 8 + 2 + 12 * entradas + 4  # tras el encabezado, el IFD0 y su "siguiente IFD"
    make = CAMARA + b"\x00"
    gps_ifd = inicio_datos + len(make)
    ifd0 = corto(entradas)
    ifd0 += corto(0x010F) + corto(2) + largo(len(make)) + largo(inicio_datos)  # Make (ASCII)
    if orientacion is not None:
        ifd0 += corto(0x0112) + corto(3) + largo(1) + corto(orientacion) + b"\x00\x00"
    ifd0 += corto(0x8825) + corto(4) + largo(1) + largo(gps_ifd)  # puntero al IFD de GPS
    gps = corto(1) + corto(0x0001) + corto(2) + largo(2) + b"S\x00\x00\x00" + largo(0) + GPS
    return b"Exif\x00\x00" + orden.encode() + corto(42) + largo(8) + ifd0 + largo(0) + make + gps


def jpeg(
    ancho: int = 200,
    alto: int = 200,
    *,
    metadatos: bool = False,
    icc: bool = True,
    relleno: int = 0,
    cola: bytes = b"",
    sin_eoi: bool = False,
    exif: bytes | None = None,
) -> bytes:
    """Un JPEG con JFIF, perfil de color, tablas, SOF0, un SOS y datos comprimidos con `FF00` y
    un reinicio `RST0`. Con `metadatos` suma EXIF, XMP, IPTC y un comentario (lo que se quita).

    `relleno` agrega esa cantidad de bytes a los datos comprimidos (sin `FF`), para dar al archivo
    un tamano exacto; `cola` son bytes despues del EOI.
    """
    partes = [b"\xff\xd8", segmento_jpeg(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")]
    # El EXIF va primero; sin uno propio, `metadatos` pone uno ilegible (no es un TIFF).
    if exif is None and metadatos:
        exif = b"Exif\x00\x00" + CAMARA + GPS
    if exif is not None:
        partes.append(segmento_jpeg(0xE1, exif))
    if metadatos:
        partes.append(segmento_jpeg(0xE1, b"http://ns.adobe.com/xap/1.0/\x00" + XMP))
    if icc:
        partes.append(segmento_jpeg(0xE2, ICC))
    if metadatos:
        partes += [
            segmento_jpeg(0xED, b"Photoshop 3.0\x00" + IPTC),
            segmento_jpeg(0xFE, COMENTARIO),
        ]
    partes += [
        segmento_jpeg(0xDB, b"\x00" + bytes(range(64))),
        segmento_jpeg(
            0xC0, b"\x08" + alto.to_bytes(2, "big") + ancho.to_bytes(2, "big") + b"\x01\x01\x11\x00"
        ),
        segmento_jpeg(0xC4, b"\x00" + bytes(range(16)) + bytes(range(12))),
        segmento_jpeg(0xDA, b"\x01\x01\x00\x00\x3f\x00"),
        b"\x12\x34\xff\x00\x56\xff\xd0\x78\x9a" + b"\x55" * relleno,
    ]
    if not sin_eoi:
        partes.append(b"\xff\xd9")
    return b"".join(partes) + cola


def bloque_png(tipo: bytes, datos: bytes) -> bytes:
    crc = zlib.crc32(tipo + datos).to_bytes(4, "big")
    return len(datos).to_bytes(4, "big") + tipo + datos + crc


def png(ancho: int = 2, alto: int = 2, *, metadatos: bool = False, cola: bytes = b"") -> bytes:
    """Un PNG con IHDR, perfil de color, IDAT y IEND. Con `metadatos` suma tEXt, zTXt, iTXt, eXIf
    y tIME (lo que se quita)."""
    ihdr = ancho.to_bytes(4, "big") + alto.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00"
    crudo = (b"\x00" + b"\x7f\x80\x81" * ancho) * alto
    partes = [
        b"\x89PNG\r\n\x1a\n",
        bloque_png(b"IHDR", ihdr),
        bloque_png(b"iCCP", b"perfil\x00\x00" + zlib.compress(ICC)),
    ]
    if metadatos:
        partes += [
            bloque_png(b"tEXt", b"Author\x00" + TEXTO),
            bloque_png(b"zTXt", b"Comment\x00\x00" + zlib.compress(TEXTO)),
            bloque_png(b"iTXt", b"XML:com.adobe.xmp\x00\x00\x00\x00\x00" + TEXTO),
            bloque_png(b"eXIf", b"MM\x00*" + GPS),
            bloque_png(b"tIME", b"\x07\xea\x0b\x02\x0c\x00\x00"),
        ]
    partes += [
        bloque_png(b"pHYs", b"\x00\x00\x0b\x13\x00\x00\x0b\x13\x01"),
        bloque_png(b"IDAT", zlib.compress(crudo)),
        bloque_png(b"IEND", b""),
    ]
    return b"".join(partes) + cola


# Una firma de cada tipo que no es imagen, con lo justo para reconocerla.
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
MP4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 16
MOV = b"\x00\x00\x00\x14ftypqt  \x00\x00\x00\x00qt  " + b"\x00" * 16
GP3 = b"\x00\x00\x00\x14ftyp3gp4\x00\x00\x00\x00" + b"3gp4" + b"\x00" * 16
M4A = b"\x00\x00\x00\x18ftypM4A \x00\x00\x00\x00M4A mp42" + b"\x00" * 16
MP3_ID3 = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 24
MP3_CUADRO = b"\xff\xfb\x90\x00" + b"\x00" * 28
AAC_ADTS = b"\xff\xf1\x50\x80" + b"\x00" * 28
OGG = b"OggS\x00\x02" + b"\x00" * 26
WAV = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 16
AMR = b"#!AMR\n" + b"\x00" * 26
AMR_WB = b"#!AMR-WB\n" + b"\x00" * 23

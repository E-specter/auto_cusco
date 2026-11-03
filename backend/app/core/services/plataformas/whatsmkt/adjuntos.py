"""Adjuntos de WhatsMKT: tipo por firma, tamano, limpieza de metadatos y foto (RF-WM-28 a 32).

Todo es puro y sin dependencias: ni Pillow ni nada que recodifique. Una imagen se limpia quitando
bloques del propio archivo, asi los datos de la imagen quedan byte a byte (sin perdida de calidad).
"""

import struct
import zlib
from collections.abc import Iterator
from typing import Literal

from app.core.entities.whatsmkt import (
    CodigoWhatsmkt,
    ConfiguracionWhatsmkt,
    ErrorWhatsmkt,
    TipoAdjunto,
)

# Bytes que alcanzan para reconocer cualquier firma de abajo.
LARGO_CABECERA = 32
# RF-WM-29 (decimal, como los topes de la configuracion: 1 MB = 1 000 000 bytes).
FOTO_PESO_MAXIMO = 1_000_000
FOTO_ANCHO = 200
FOTO_ALTO = 200
# DU: la configuracion (RF-WM-04) solo tiene topes de video, audio y PDF; la imagen que se envia
# como adjunto no tiene el suyo. 5 MB es el maximo de imagen de WhatsApp (no verificado en
# WhatsMKT); cambia esta linea o pasa a la configuracion cuando el usuario responda.
TOPE_IMAGEN_BYTES = 5_000_000

_FIRMA_JPEG = b"\xff\xd8\xff"
_FIRMA_PNG = b"\x89PNG\r\n\x1a\n"
# Marcas (brands) de `ftyp` que son solo audio; el resto de `ftyp` (isom, mp4x, qt, 3gp, 3g2) es
# video.
_FTYP_AUDIO = (b"M4A ", b"M4B ", b"M4P ")


def tipo_por_firma(cabecera: bytes) -> TipoAdjunto | None:
    """El tipo del archivo por sus primeros bytes, nunca por su extension (RF-WM-31).

    Reconoce JPEG, PNG, PDF, video (MP4, MOV y 3GP por `ftyp`) y audio (MP3 con ID3 o con cabecera
    de cuadro, AAC ADTS, M4A, OGG, WAV y AMR). Cualquier otra cosa es None.
    """
    if cabecera.startswith(_FIRMA_JPEG):
        return TipoAdjunto.IMAGEN_JPEG
    if cabecera.startswith(_FIRMA_PNG):
        return TipoAdjunto.IMAGEN_PNG
    if cabecera.startswith(b"%PDF-"):
        return TipoAdjunto.PDF
    if cabecera[4:8] == b"ftyp":
        return TipoAdjunto.AUDIO if cabecera[8:12] in _FTYP_AUDIO else TipoAdjunto.VIDEO
    if cabecera.startswith((b"ID3", b"OggS", b"#!AMR")):
        return TipoAdjunto.AUDIO
    if cabecera.startswith(b"RIFF") and cabecera[8:12] == b"WAVE":
        return TipoAdjunto.AUDIO
    if _es_cuadro_de_audio(cabecera):
        return TipoAdjunto.AUDIO
    return None


def _es_cuadro_de_audio(cabecera: bytes) -> bool:
    """Cabecera de cuadro MPEG (MP3) o ADTS (AAC): 11 bits de sincronia."""
    if len(cabecera) < 2 or cabecera[0] != 0xFF or cabecera[1] & 0xE0 != 0xE0:
        return False
    version, capa = (cabecera[1] >> 3) & 0b11, (cabecera[1] >> 1) & 0b11
    return version != 0b01 and (capa != 0b00 or cabecera[1] in (0xF1, 0xF9))  # ADTS: capa 00


def tope_de(tipo: TipoAdjunto, configuracion: ConfiguracionWhatsmkt) -> int:
    """Bytes que admite ese tipo: de la configuracion para video, audio y PDF (RF-WM-31)."""
    return {
        TipoAdjunto.VIDEO: configuracion.tope_video,
        TipoAdjunto.AUDIO: configuracion.tope_audio,
        TipoAdjunto.PDF: configuracion.tope_pdf,
    }.get(tipo, TOPE_IMAGEN_BYTES)


def _danado() -> ErrorWhatsmkt:
    return ErrorWhatsmkt(
        CodigoWhatsmkt.ADJUNTO_DANADO, "El archivo esta incompleto o danado: vuelve a descargarlo"
    )


# --- JPEG ---------------------------------------------------------------------------------------

# APP1 (EXIF y XMP), APP13 (IPTC) y COM (comentarios). APP2 (perfil de color) se conserva.
_JPEG_QUITAR = frozenset({0xE1, 0xED, 0xFE})
_JPEG_SIN_LARGO = frozenset({0x01, *range(0xD0, 0xD8)})  # TEM y RSTn
_JPEG_SOF = frozenset(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}  # lo que lleva alto y ancho
_SOS, _EOI = 0xDA, 0xD9


def _segmentos_jpeg(datos: bytes) -> Iterator[tuple[int, int, int]]:
    """(marcador, inicio, fin) de cada segmento con cabecera, hasta el EOI.

    Los datos comprimidos que siguen a un SOS no se devuelven: se saltan hasta el siguiente
    marcador (en ellos, `FF` va siempre seguido de `00` o de un reinicio `RSTn`). Lanza
    `adjunto_danado` si el archivo se corta antes del EOI o un largo se sale del archivo. Lo que
    venga despues del EOI no es parte de la imagen y no se recorre.
    """
    n = len(datos)
    if not datos.startswith(b"\xff\xd8"):
        raise _danado()
    i = 2
    while True:
        if i + 1 >= n or datos[i] != 0xFF:
            raise _danado()
        marcador = datos[i + 1]
        if marcador == 0xFF:  # byte de relleno antes de un marcador
            i += 1
            continue
        if marcador == _EOI:
            yield marcador, i, i + 2
            return
        if marcador in _JPEG_SIN_LARGO:
            yield marcador, i, i + 2
            i += 2
            continue
        if marcador == 0xD8 or i + 4 > n:  # un segundo SOI, o sin sitio para el largo
            raise _danado()
        largo = int.from_bytes(datos[i + 2 : i + 4], "big")
        fin = i + 2 + largo
        if largo < 2 or fin > n:
            raise _danado()
        yield marcador, i, fin
        i = fin
        if marcador == _SOS:
            i = _fin_de_datos_comprimidos(datos, i)


def _fin_de_datos_comprimidos(datos: bytes, desde: int) -> int:
    """Posicion del primer marcador despues de los datos comprimidos de un SOS."""
    n = len(datos)
    j = desde
    while True:
        k = datos.find(b"\xff", j)
        if k == -1 or k + 1 >= n:
            raise _danado()
        siguiente = datos[k + 1]
        if siguiente == 0x00 or 0xD0 <= siguiente <= 0xD7:  # byte con relleno, o reinicio
            j = k + 2
        elif siguiente == 0xFF:
            j = k + 1
        else:
            return k


Orden = Literal["little", "big"]
_ENCABEZADO_EXIF = b"Exif\x00\x00"
_TAG_ORIENTACION = 0x0112
_TIPO_SHORT = 3


def _orientacion_exif(tiff: bytes) -> tuple[int, Orden] | None:
    """(orientacion, orden de bytes) del IFD0 de un EXIF, o None si no hay, vale 1 o esta danado.

    Solo lee lo que necesita y comprueba cada limite: un EXIF ilegible no es un error, simplemente
    no aporta orientacion.
    """
    orden: Orden | None = {b"II": "little", b"MM": "big"}.get(tiff[:2])
    if orden is None or len(tiff) < 8 or int.from_bytes(tiff[2:4], orden) != 42:
        return None
    ifd = int.from_bytes(tiff[4:8], orden)
    if ifd < 8 or ifd + 2 > len(tiff):
        return None
    for i in range(int.from_bytes(tiff[ifd : ifd + 2], orden)):
        entrada = ifd + 2 + 12 * i
        if entrada + 12 > len(tiff):
            return None
        if int.from_bytes(tiff[entrada : entrada + 2], orden) != _TAG_ORIENTACION:
            continue
        tipo = int.from_bytes(tiff[entrada + 2 : entrada + 4], orden)
        cuenta = int.from_bytes(tiff[entrada + 4 : entrada + 8], orden)
        valor = int.from_bytes(tiff[entrada + 8 : entrada + 10], orden)
        return (valor, orden) if tipo == _TIPO_SHORT and cuenta == 1 and 2 <= valor <= 8 else None
    return None


def _exif_solo_orientacion(orientacion: int, orden: Orden) -> bytes:
    """APP1 minimo: `Exif`, cabecera TIFF en el orden del original, un IFD0 con solo Orientation
    y sin IFD siguiente."""

    def corto(n: int) -> bytes:
        return n.to_bytes(2, orden)

    def largo(n: int) -> bytes:
        return n.to_bytes(4, orden)

    marca = b"II" if orden == "little" else b"MM"
    tiff = marca + corto(42) + largo(8)
    tiff += corto(1) + corto(_TAG_ORIENTACION) + corto(_TIPO_SHORT) + largo(1)
    tiff += corto(orientacion) + b"\x00\x00" + largo(0)
    return (
        b"\xff\xe1"
        + (len(_ENCABEZADO_EXIF + tiff) + 2).to_bytes(2, "big")
        + _ENCABEZADO_EXIF
        + tiff
    )


def limpiar_jpeg(datos: bytes) -> bytes:
    """Quita APP1, APP13 y COM sin recodificar: lo demas queda byte a byte (RF-WM-32).

    DU-WM-12: del EXIF se conserva SOLO la orientacion (tag 0x0112), en un APP1 minimo en el mismo
    lugar. Sin ella una foto de celular tomada en vertical se veria girada, y no es un dato
    personal. Si el EXIF no trae orientacion, vale 1 o es ilegible, no se escribe APP1. El XMP
    (tambien APP1) se quita siempre.

    Lo que haya despues del EOI (miniaturas o videos pegados por algunas camaras) se descarta:
    no es parte de la imagen.
    """
    salida = bytearray(b"\xff\xd8")
    entropia_desde = 2
    orientacion_vista = False
    for marcador, inicio, fin in _segmentos_jpeg(datos):
        # Entre un SOS y el siguiente marcador estan los datos comprimidos: se copian enteros.
        salida += datos[entropia_desde:inicio]
        entropia_desde = fin
        if (
            marcador == 0xE1
            and not orientacion_vista
            and datos[inicio + 4 : inicio + 10] == _ENCABEZADO_EXIF
        ):
            orientacion_vista = True  # solo el primer EXIF cuenta
            if (orientacion := _orientacion_exif(datos[inicio + 10 : fin])) is not None:
                salida += _exif_solo_orientacion(*orientacion)
        if marcador not in _JPEG_QUITAR:
            salida += datos[inicio:fin]
    return bytes(salida)


def medidas_jpeg(datos: bytes) -> tuple[int, int]:
    """(ancho, alto) leidos del marcador SOF, no del nombre ni de nada que el archivo declare.

    Recorre el archivo entero: uno cortado antes del EOI es `adjunto_danado`, aunque el SOF
    este completo.
    """
    medidas = None
    for marcador, inicio, fin in _segmentos_jpeg(datos):
        if medidas is None and marcador in _JPEG_SOF:
            # marcador(2) largo(2) precision(1) alto(2) ancho(2)
            if fin - inicio < 9:
                raise _danado()
            alto, ancho = struct.unpack(">HH", datos[inicio + 5 : inicio + 9])
            medidas = (ancho, alto)
    if medidas is None:
        raise _danado()
    return medidas


# --- PNG ----------------------------------------------------------------------------------------

# Texto (tEXt, zTXt, iTXt), EXIF (eXIf) y fecha de modificacion (tIME).
_PNG_QUITAR = frozenset({b"tEXt", b"zTXt", b"iTXt", b"eXIf", b"tIME"})


def limpiar_png(datos: bytes) -> bytes:
    """Quita los bloques de texto, `eXIf` y `tIME`; conserva el resto con sus CRC (RF-WM-32).

    Comprueba el largo y el CRC de cada bloque, que el primero sea IHDR y que termine en IEND: un
    archivo cortado o alterado es `adjunto_danado`. Lo que venga despues del IEND se descarta.
    """
    n = len(datos)
    if not datos.startswith(_FIRMA_PNG):
        raise _danado()
    salida = bytearray(_FIRMA_PNG)
    i, primero = len(_FIRMA_PNG), True
    while i + 12 <= n:
        largo = int.from_bytes(datos[i : i + 4], "big")
        tipo = datos[i + 4 : i + 8]
        fin = i + 12 + largo
        if fin > n:
            raise _danado()
        crc = int.from_bytes(datos[fin - 4 : fin], "big")
        if zlib.crc32(datos[i + 4 : fin - 4]) != crc or (primero and tipo != b"IHDR"):
            raise _danado()
        primero = False
        if tipo not in _PNG_QUITAR:
            salida += datos[i:fin]
        if tipo == b"IEND":
            return bytes(salida)
        i = fin
    raise _danado()


# --- Foto de perfil -----------------------------------------------------------------------------


def validar_foto(tipo: TipoAdjunto | None, peso: int, contenido: bytes | None = None) -> None:
    """RF-WM-29: JPEG, hasta 1 MB y de 200 x 200 pixeles medidos en el propio archivo.

    Sin `contenido` solo comprueba el formato y el peso (se hace antes de leer el archivo); con el,
    comprueba tambien las medidas.
    """
    if tipo is not TipoAdjunto.IMAGEN_JPEG:
        raise ErrorWhatsmkt(CodigoWhatsmkt.FOTO_FORMATO, "La foto tiene que ser JPEG")
    if peso > FOTO_PESO_MAXIMO:
        raise ErrorWhatsmkt(
            CodigoWhatsmkt.FOTO_PESO,
            f"La foto pesa {peso} bytes: el maximo es {FOTO_PESO_MAXIMO}",
            peso=peso,
        )
    if contenido is not None:
        ancho, alto = medidas_jpeg(contenido)
        if (ancho, alto) != (FOTO_ANCHO, FOTO_ALTO):
            raise ErrorWhatsmkt(
                CodigoWhatsmkt.FOTO_MEDIDAS,
                f"La foto mide {ancho} x {alto} pixeles: tiene que medir "
                f"{FOTO_ANCHO} x {FOTO_ALTO}",
                ancho=ancho,
                alto=alto,
            )


def validar_foto_de(contenido: bytes) -> None:
    """La regla de la foto (RF-WM-29) sobre los bytes de un archivo: lanza el error o no hace nada.

    No depende de como se subio: la usa la subida con `proposito=foto` y la usara la campana al
    elegir un adjunto de la biblioteca como foto de perfil (una imagen de 200 x 200 subida antes
    como adjunto comun tambien sirve). Pasa los bytes tal como estan guardados.
    """
    validar_foto(tipo_por_firma(contenido[:LARGO_CABECERA]), len(contenido), contenido)


# --- Entrada ------------------------------------------------------------------------------------


def revisar_tamano(tipo: TipoAdjunto, tamano: int, configuracion: ConfiguracionWhatsmkt) -> None:
    """RF-WM-31: el tope del tipo, controlado con el tamano declarado, antes de leer el archivo."""
    maximo = tope_de(tipo, configuracion)
    if tamano > maximo:
        raise ErrorWhatsmkt(
            CodigoWhatsmkt.ADJUNTO_PESO,
            f"El archivo pesa {tamano} bytes: el maximo para {tipo.value} es {maximo}",
            peso=tamano,
            tipo=tipo.value,
            maximo=maximo,
        )


def reconocer(cabecera: bytes, como_foto: bool) -> TipoAdjunto | None:
    """El tipo por firma. Un tipo desconocido es `adjunto_tipo`, salvo que sea una foto
    (`foto_formato`, que lo dice `validar_foto`)."""
    tipo = tipo_por_firma(cabecera)
    if tipo is None and not como_foto:
        raise ErrorWhatsmkt(
            CodigoWhatsmkt.ADJUNTO_TIPO,
            "WhatsMKT no admite este tipo de archivo: sube una imagen, un video, un audio o un PDF",
        )
    return tipo


def limpiar(tipo: TipoAdjunto, contenido: bytes) -> bytes:
    """Imagenes sin metadatos; video, audio y PDF tal como llegan (RF-WM-32)."""
    if tipo is TipoAdjunto.IMAGEN_JPEG:
        return limpiar_jpeg(contenido)
    if tipo is TipoAdjunto.IMAGEN_PNG:
        return limpiar_png(contenido)
    return contenido

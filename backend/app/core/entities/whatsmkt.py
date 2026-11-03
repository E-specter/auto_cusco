"""Entidades del modulo WhatsMKT: configuracion, segmentos y adjuntos (T-WM-B1).

Los valores iniciales son los supuestos del documento de requerimientos (S-WM-1, S-WM-7 y S-WM-8)
y la duda DU-WM-6 (plantilla del nombre): viven aqui y en la siembra de la migracion, y cambian con
una linea cuando el usuario responda.
"""

from dataclasses import dataclass
from datetime import datetime, time
from enum import StrEnum

TOPE_MENSAJE_POR_DEFECTO = 4096  # S-WM-7, RF-WM-26
TOPE_ADJUNTO_POR_DEFECTO = 16_000_000  # S-WM-8, RF-WM-31: bytes de video, audio y PDF
# DU-WM-6: provisional. Variables admitidas: solo estas dos (RF-WM-33).
PLANTILLA_NOMBRE_POR_DEFECTO = "CUZCO_Vencida ({segmento}) whatsapp {fecha_corte}"
VARIABLES_PLANTILLA = ("fecha_corte", "segmento")


class CodigoWhatsmkt(StrEnum):
    """Codigos de error del modulo; el frontend los traduce como `whatsmkt.codigo.<codigo>`.

    Los de docs/whatsmkt-interfaz.md §7 (con `horario_invalido`, `sin_dias_atraso` y
    `sin_supervisores`), todos desde B1 para que la
    prueba espejo de i18n no cambie en cada corte. Un codigo por linea, con la forma
    `NOMBRE = "codigo"`: la prueba espejo lee esta clase. Un codigo nuevo se acuerda antes con
    designer. B1 emite solo `horario_invalido`, `variable_inexistente`, `segmentos_superpuestos`
    y `segmentos_con_hueco`; los demas los emiten B2 a B6.
    """

    SIN_TELEFONO = "sin_telefono"
    TELEFONO_INVALIDO = "telefono_invalido"
    MACRO_VACIA = "macro_vacia"
    MENSAJE_CON_EMOJI = "mensaje_con_emoji"
    MACRO_INEXISTENTE = "macro_inexistente"
    MENSAJE_LARGO = "mensaje_largo"
    MENSAJE_DESHABILITADO = "mensaje_deshabilitado"
    NOMBRE_LARGO = "nombre_largo"
    VARIABLE_INEXISTENTE = "variable_inexistente"
    FECHA_NO_GESTIONABLE = "fecha_no_gestionable"
    SIN_HORARIO = "sin_horario"
    SIN_PRODUCTOS = "sin_productos"
    DEFINICION_NO_WHATSMKT = "definicion_no_whatsmkt"
    FOTO_FORMATO = "foto_formato"
    FOTO_MEDIDAS = "foto_medidas"
    FOTO_PESO = "foto_peso"
    ADJUNTO_TIPO = "adjunto_tipo"
    ADJUNTO_PESO = "adjunto_peso"
    ADJUNTO_DANADO = "adjunto_danado"
    SEGMENTOS_SUPERPUESTOS = "segmentos_superpuestos"
    SEGMENTOS_CON_HUECO = "segmentos_con_hueco"
    INFORME_SIN_ENCABEZADOS = "informe_sin_encabezados"
    INFORME_SIN_FILAS = "informe_sin_filas"
    INFORME_YA_IMPORTADO = "informe_ya_importado"
    CAMPANA_DESCARTADA = "campana_descartada"
    CAMPANA_NO_DESCARTADA = "campana_no_descartada"
    HORARIO_INVALIDO = "horario_invalido"
    SIN_DIAS_ATRASO = "sin_dias_atraso"
    SIN_SUPERVISORES = "sin_supervisores"
    WHATSAPP_INVALIDO = "whatsapp_invalido"
    SIN_WHATSAPP = "sin_whatsapp"
    SIN_MENSAJE = "sin_mensaje"


class ModoCampana(StrEnum):
    """Como se reparte el mensaje (RF-WM-18): una campana para toda la seleccion, o un lote con una
    campana por segmento (RF-WM-23)."""

    GLOBAL = "global"
    POR_SEGMENTO = "por_segmento"


class ErrorWhatsmkt(Exception):
    """Un valor del modulo que no se puede guardar; `codigo` dice por que.

    `parametros` son los datos que el texto del codigo nombra (la franja que fallo, los dias sin
    segmento): viajan en el 422 junto al codigo y el frontend los pone en su frase.
    """

    def __init__(self, codigo: CodigoWhatsmkt, mensaje: str, **parametros: object) -> None:
        super().__init__(mensaje)
        self.codigo = codigo
        self.parametros = parametros


class DefinicionDefectoNoExiste(Exception):
    """La definicion elegida como la de por defecto no existe (RF-WM-04)."""

    def __init__(self, definicion_id: int) -> None:
        super().__init__(f"No existe la definicion {definicion_id}")
        self.definicion_id = definicion_id


class TextoDeSegmentoInvalido(Exception):
    """El texto elegido como mensaje de un segmento no existe o no es del contexto
    `whatsmkt.mensaje` (RF-WM-19)."""

    def __init__(self, clave: str, texto_id: int, motivo: str) -> None:
        super().__init__(f"El mensaje del segmento {clave!r}: {motivo}")
        self.clave = clave
        self.texto_id = texto_id


class AdjuntoNoEncontrado(Exception):
    def __init__(self, adjunto_id: int) -> None:
        super().__init__(f"No existe el adjunto {adjunto_id}")
        self.adjunto_id = adjunto_id


@dataclass(frozen=True)
class Horario:
    """Franja de envio (RF-WM-07): inicio estrictamente anterior al fin."""

    inicio: time
    fin: time


HORARIO_1_POR_DEFECTO = Horario(time(8, 0), time(14, 0))
HORARIO_2_POR_DEFECTO = Horario(time(14, 0), time(20, 0))


@dataclass(frozen=True)
class ConfiguracionWhatsmkt:
    """Configuracion de la plataforma, una sola fila (RF-WM-04). Sin dias de envio: son fijos."""

    horario_1: Horario = HORARIO_1_POR_DEFECTO
    horario_2: Horario = HORARIO_2_POR_DEFECTO
    plantilla_nombre: str = PLANTILLA_NOMBRE_POR_DEFECTO
    definicion_defecto_id: int | None = None
    tope_mensaje: int = TOPE_MENSAJE_POR_DEFECTO
    tope_video: int = TOPE_ADJUNTO_POR_DEFECTO
    tope_audio: int = TOPE_ADJUNTO_POR_DEFECTO
    tope_pdf: int = TOPE_ADJUNTO_POR_DEFECTO
    actualizado_en: datetime | None = None
    # DU-WM-11 (a): el numero de contacto que reemplaza a `[whatsapp]` en el mensaje; sin numero,
    # `[whatsapp]` queda tal cual. 9 digitos que empiezan con 9 (RF-02).
    whatsapp_contacto: str | None = None


@dataclass(frozen=True)
class SegmentoWhatsmkt:
    """Un tramo de dias de atraso ajustados (RF-WM-20); `None` es sin piso o sin tope."""

    clave: str
    etiqueta: str
    desde: int | None
    hasta: int | None
    orden: int
    # El texto guardado (contexto `whatsmkt.mensaje`) que es el mensaje de este segmento. Es el
    # texto, no la version: la campana congela la version al crearse.
    texto_guardado_id: int | None = None


# S-WM-1, el valor sembrado por la migracion. Los segmentos son fijos: se editan su etiqueta y sus
# limites, pero no se agregan ni se quitan.
SEGMENTOS_POR_DEFECTO = (
    SegmentoWhatsmkt("preventivo", "Preventivo", None, 0, 0),
    SegmentoWhatsmkt("tramo_2", "Tramo 2", 1, 8, 1),
    SegmentoWhatsmkt("mayores_2", "Tramos mayores al 2", 9, None, 2),
)
CLAVES_SEGMENTOS = frozenset(s.clave for s in SEGMENTOS_POR_DEFECTO)


class TipoEnvio(StrEnum):
    """Lo que lleva el mensaje (RF-WM-28): solo texto, un archivo de la biblioteca o una vCard."""

    SOLO_TEXTO = "solo_texto"
    ARCHIVO = "archivo"
    VCARD = "vcard"


class TipoAdjunto(StrEnum):
    IMAGEN_JPEG = "imagen_jpeg"
    IMAGEN_PNG = "imagen_png"
    VIDEO = "video"
    AUDIO = "audio"
    PDF = "pdf"


@dataclass(frozen=True)
class AdjuntoWhatsmkt:
    """Un archivo de la biblioteca (RF-WM-30). El contenido se lee aparte, no al listar."""

    id: int
    tipo: TipoAdjunto
    nombre: str
    tamano: int
    huella: str  # SHA-256 en hexadecimal
    creado_en: datetime
    archivado_en: datetime | None = None


@dataclass(frozen=True)
class ExclusionContacto:
    """Un producto que no sale en el archivo, con su unico codigo (RF-WM-15).

    `fila` es la posicion del producto entre los que genero la seleccion (desde 1). Para
    `macro_vacia`, `macro` es su numero (1 es la segunda columna) y `etiqueta`, la de la columna.
    """

    fila: int
    pagare: str | None
    codigo: CodigoWhatsmkt
    detalle: str
    macro: int | None = None
    etiqueta: str | None = None
    # El segmento al que pertenece el producto (solo en un lote por segmento; None si no tiene).
    segmento: str | None = None

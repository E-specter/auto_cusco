"""Entidades del conector SMS de MOWA MES (docs/requerimientos-mowa-mes.md).

Por ahora cubre la configuracion del conector, el speech versionado y sus
segmentos, y el catalogo de codigos de exclusion y advertencia que el frontend
traduce por codigo.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

LIMITE_MENSUAL_POR_DEFECTO = 2_500_000  # RF-MM-01
LARGO_ADVERTENCIA = 150  # RF-MM-19: se carga, pero se advierte
LARGO_MAXIMO = 160  # RF-MM-19: se excluye
LARGO_TITULAR = 8  # RF-MM-14: [titular 8]
FORMATO_VENCIMIENTO = "%d/%m/%Y"  # RF-MM-14: [fecha], dd/mm/yyyy en todos los segmentos
LARGO_VENCIMIENTO = 10
VARIABLE_WHATSAPP = "[whatsapp]"  # RF-MM-16
PREFIJO_WHATSAPP = "https://wa.me/+51"
LARGO_NUMERO_WHATSAPP = 9
LARGO_MAXIMO_NOMBRE_SPEECH = 120
NOMBRE_SPEECH_ORIGINAL = "Speech original"


class Segmento(StrEnum):
    PREVENTIVA = "preventiva"
    DE_1_A_8 = "1_a_8"
    DE_9_A_30 = "9_a_30"
    DE_31_A_60 = "31_a_60"
    DE_61_A_90 = "61_a_90"
    DE_91_A_120 = "91_a_120"


@dataclass(frozen=True)
class RangoSegmento:
    """Dias de atraso ajustados que cubre un segmento; `desde` None es sin limite inferior."""

    segmento: Segmento
    etiqueta: str
    desde: int | None
    hasta: int


# RF-MM-15, con S-MM-6 (0 es Preventiva). Son datos, no condiciones sueltas.
RANGOS_SEGMENTO: tuple[RangoSegmento, ...] = (
    RangoSegmento(Segmento.PREVENTIVA, "Preventiva", None, 0),
    RangoSegmento(Segmento.DE_1_A_8, "1 a 8", 1, 8),
    RangoSegmento(Segmento.DE_9_A_30, "9 a 30", 9, 30),
    RangoSegmento(Segmento.DE_31_A_60, "31 a 60", 31, 60),
    RangoSegmento(Segmento.DE_61_A_90, "61 a 90", 61, 90),
    RangoSegmento(Segmento.DE_91_A_120, "91 a 120", 91, 120),
)


class Programacion(StrEnum):
    """Modalidades de envio de RF-MM-07."""

    ENVIAR_AHORA = "enviar_ahora"
    HORA_DETERMINADA = "hora_determinada"
    DIFERENTES_HORAS = "diferentes_horas"


class TipoCodigo(StrEnum):
    EXCLUSION = "exclusion"
    ADVERTENCIA = "advertencia"
    ERROR = "error"


class CodigoMowaMes(StrEnum):
    """Catalogo de codigos que el frontend traduce como `mowaMes.codigo.<codigo>`.

    Las exclusiones van en el orden en que se evaluan: un producto excluido lleva
    un solo motivo, el primero que falla. Un codigo por linea, con la forma
    `NOMBRE = "codigo"`: la prueba espejo del frontend lee esta clase.
    """

    TELEFONO_INVALIDO = "telefono_invalido"
    FALTA_DOCUMENTO = "falta_documento"
    SIN_SPEECH = "sin_speech"
    FALTA_TITULAR = "falta_titular"
    FALTA_VENCIMIENTO = "falta_vencimiento"
    MENSAJE_EXCEDE_160 = "mensaje_excede_160"
    MENSAJE_EXCEDE_150 = "mensaje_excede_150"
    DOCUMENTO_NO_ESTANDAR = "documento_no_estandar"
    LIMITE_MENSUAL_EXCEDIDO = "limite_mensual_excedido"
    ID_SIN_CORRESPONDENCIA = "id_sin_correspondencia"
    FALTA_WHATSAPP = "falta_whatsapp"
    SIN_SUPERVISORES = "sin_supervisores"
    SIN_PRODUCTOS_CARGABLES = "sin_productos_cargables"


TIPO_CODIGO: dict[CodigoMowaMes, TipoCodigo] = {
    CodigoMowaMes.TELEFONO_INVALIDO: TipoCodigo.EXCLUSION,
    CodigoMowaMes.FALTA_DOCUMENTO: TipoCodigo.EXCLUSION,
    CodigoMowaMes.SIN_SPEECH: TipoCodigo.EXCLUSION,
    CodigoMowaMes.FALTA_TITULAR: TipoCodigo.EXCLUSION,
    CodigoMowaMes.FALTA_VENCIMIENTO: TipoCodigo.EXCLUSION,
    CodigoMowaMes.MENSAJE_EXCEDE_160: TipoCodigo.EXCLUSION,
    CodigoMowaMes.MENSAJE_EXCEDE_150: TipoCodigo.ADVERTENCIA,
    CodigoMowaMes.DOCUMENTO_NO_ESTANDAR: TipoCodigo.ADVERTENCIA,
    CodigoMowaMes.LIMITE_MENSUAL_EXCEDIDO: TipoCodigo.ADVERTENCIA,
    CodigoMowaMes.ID_SIN_CORRESPONDENCIA: TipoCodigo.ADVERTENCIA,
    CodigoMowaMes.FALTA_WHATSAPP: TipoCodigo.ERROR,
    CodigoMowaMes.SIN_SUPERVISORES: TipoCodigo.ERROR,
    CodigoMowaMes.SIN_PRODUCTOS_CARGABLES: TipoCodigo.ERROR,
}

# RF-MM-11. Son el maximo de la plataforma: la configuracion solo puede bajarlos.
REGISTROS_POR_ARCHIVO = 50_000
BYTES_POR_ARCHIVO = 2_000_000  # 2 MB, lectura conservadora
BYTES_POR_ARCHIVO_MINIMO = 100_000


@dataclass(frozen=True)
class ConfiguracionMowaMes:
    """Configuracion persistida del conector (RF-32). Sin numero de WhatsApp sembrado."""

    limite_mensual: int
    whatsapp_contacto: str | None
    actualizado_en: datetime | None = None
    registros_por_archivo: int = REGISTROS_POR_ARCHIVO
    bytes_por_archivo: int = BYTES_POR_ARCHIVO


@dataclass(frozen=True)
class PartesSegmento:
    """Texto de un segmento: mensaje = [titular 8] + parte_1 + [fecha] + parte_2 (RF-MM-14).

    Los espacios de los extremos son parte del texto y no se recortan.
    """

    segmento: Segmento
    parte_1: str
    parte_2: str


@dataclass(frozen=True)
class DatosSpeech:
    nombre: str
    partes: tuple[PartesSegmento, ...]


@dataclass(frozen=True)
class VersionSpeech:
    id: int
    datos: DatosSpeech
    original: bool
    basada_en_id: int | None
    usada_en: datetime | None
    creado_en: datetime

    @property
    def usada(self) -> bool:
        return self.usada_en is not None

    @property
    def editable(self) -> bool:
        """RF-MM-17: una version usada no se modifica; el Speech original tampoco."""
        return not self.original and not self.usada


@dataclass(frozen=True)
class ProblemaSpeech:
    """`segmento` None es un problema de la version entera (nombre, segmentos)."""

    segmento: Segmento | None
    campo: str  # "nombre", "segmentos", "parte_1" o "parte_2"
    detalle: str


@dataclass(frozen=True)
class LargoSegmento:
    """Largo maximo que puede alcanzar el mensaje de un segmento (RF-MM-19)."""

    rango: RangoSegmento
    usa_whatsapp: bool
    largo_maximo: int
    codigo: CodigoMowaMes | None  # MENSAJE_EXCEDE_150, MENSAJE_EXCEDE_160 o None
    ejemplo: str | None  # None si usa [whatsapp] y no hay numero: nunca un enlace roto


class ConfiguracionInvalida(Exception):
    """La configuracion del conector no se puede guardar tal como viene."""


class SpeechInvalido(Exception):
    def __init__(self, problemas: tuple[ProblemaSpeech, ...]) -> None:
        resumen = "; ".join(
            p.detalle if p.segmento is None else f"{p.segmento.value} {p.campo}: {p.detalle}"
            for p in problemas
        )
        super().__init__(f"El speech no se puede guardar. {resumen}")
        self.problemas = problemas


class SpeechNoEncontrado(Exception):
    def __init__(self, speech_id: int) -> None:
        super().__init__(f"No existe la version de speech {speech_id}")
        self.speech_id = speech_id


class SpeechInmutable(Exception):
    def __init__(self, version: VersionSpeech) -> None:
        motivo = "es el Speech original" if version.original else "ya se uso en una campana"
        super().__init__(
            f"La version {version.datos.nombre!r} no se modifica porque {motivo}; "
            "guarda el cambio como una version nueva"
        )
        self.speech_id = version.id


class NombreDeSpeechRepetido(Exception):
    def __init__(self, nombre: str) -> None:
        super().__init__(f"Ya existe una version de speech llamada {nombre!r}")
        self.nombre = nombre


class FaltaWhatsapp(Exception):
    """Un segmento usa [whatsapp] y no hay numero: no se genera un enlace roto."""

    def __init__(self, segmentos: tuple[Segmento, ...]) -> None:
        nombres = ", ".join(s.value for s in segmentos)
        super().__init__(f"Los segmentos {nombres} usan [whatsapp] y no hay numero configurado")
        self.segmentos = segmentos

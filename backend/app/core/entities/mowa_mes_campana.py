"""Entidades de la campana de MOWA MES (RF-MM-01 a RF-MM-13).

Una campana se arma desde una seleccion de cartera: cada producto queda cargado
o excluido con un solo motivo, los registros de supervision van al inicio y la
carga se divide en archivos por filas y por bytes reales del `.xlsx`. La
campana guarda la copia de todo con lo que se genero, porque la seleccion
guardada, el speech y los supervisores por defecto pueden cambiar despues.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum

from app.core.entities.gestiones_digitales import Supervisor
from app.core.entities.mowa_mes import CodigoMowaMes, Programacion, Segmento, VersionSpeech

CABECERAS_CARGA = ("numero", "mensaje", "dni")  # RF-MM-10
HOJA_CARGA = "Hoja1"
PREFIJO_DESCRIPCION = "CajaCusco"  # RF-MM-04


class TipoCarga(StrEnum):
    MASIVA = "masiva"
    PERSONALIZADA = "personalizada"  # visible y deshabilitada (RF-MM-03)


class Salida(StrEnum):
    NUMERO_LARGO = "numero_largo"
    NUMERO_CORTO = "numero_corto"  # visible y deshabilitada (RF-MM-05)
    NUMERO_CORTO_FLASH = "numero_corto_flash"  # visible y deshabilitada (RF-MM-05)


@dataclass(frozen=True)
class Herramientas:
    """RF-MM-06. `respuesta_automatica` esta deshabilitada mientras no se use."""

    keyword: bool = False
    respuesta_automatica: bool = False
    blacklist_indecopi: bool = False
    speech_optimizado: bool = False


@dataclass(frozen=True)
class PeticionCampana:
    """Lo que el usuario eligio. Filtros y orden en la sintaxis de texto de `/cartera`."""

    fecha_corte: date
    cantidad: int
    programacion: Programacion
    filtros: tuple[str, ...] = ()
    orden: str | None = None
    seleccion_id: int | None = None
    tipo_carga: TipoCarga = TipoCarga.MASIVA
    descripcion: str | None = None
    salida: Salida = Salida.NUMERO_LARGO
    herramientas: Herramientas = field(default_factory=Herramientas)
    envios: tuple[datetime, ...] = ()
    speech_id: int | None = None  # None: el Speech original
    speech_huella: str | None = None  # la que vio el usuario al previsualizar
    whatsapp: str | None = None  # None: el de la configuracion
    supervisores: tuple[Supervisor, ...] | None = None  # None: la lista por defecto
    confirmar_limite: bool = False


@dataclass(frozen=True)
class FilaCarga:
    """Una fila del archivo de carga: producto de la cartera o registro de supervision."""

    numero: str
    mensaje: str
    dni: str
    supervision: bool = False
    pagare: str | None = None
    segmento: Segmento | None = None
    advertencias: tuple[CodigoMowaMes, ...] = ()

    def celdas(self) -> dict[str, object]:
        """RF-MM-10: `numero` entero, `mensaje` y `dni` texto (conserva los ceros)."""
        return {"numero": int(self.numero), "mensaje": self.mensaje, "dni": self.dni}


@dataclass(frozen=True)
class Exclusion:
    pagare: str
    codigo: CodigoMowaMes


@dataclass(frozen=True)
class ErrorCampana:
    """Algo que impide crear la campana; la previsualizacion lo muestra."""

    codigo: CodigoMowaMes
    detalle: str


@dataclass(frozen=True)
class ConsumoLimite:
    """Consumo del limite mensual (RF-MM-01), imputado al mes de la fecha de envio (S-MM-7)."""

    mes: date  # primer dia del mes
    limite: int
    cargados_mes: int
    esta_campana: int = 0

    @property
    def total(self) -> int:
        return self.cargados_mes + self.esta_campana

    @property
    def disponible(self) -> int:
        return self.limite - self.total

    @property
    def excedido(self) -> bool:
        return self.total > self.limite


@dataclass(frozen=True)
class ArchivoPrevisto:
    numero: int
    filas: int
    supervision: int


@dataclass(frozen=True)
class ArchivoCarga:
    numero: int
    filas: int
    supervision: int
    contenido: bytes

    @property
    def bytes(self) -> int:
        return len(self.contenido)


@dataclass(frozen=True)
class ArchivoResumen:
    numero: int
    filas: int
    supervision: int
    bytes: int


@dataclass(frozen=True)
class SupervisorAsignado:
    numero: str
    procedencia: str
    documento: str


@dataclass(frozen=True)
class CampanaArmada:
    """La campana calculada, antes de escribir archivos o guardar nada."""

    peticion: PeticionCampana
    descripcion: str
    descripcion_sugerida: str
    fecha_generacion: date
    fecha_envio: date
    speech: VersionSpeech
    speech_huella: str
    whatsapp: str | None
    supervisores: tuple[SupervisorAsignado, ...]
    registros_por_archivo: int
    bytes_por_archivo: int
    disponibles: int
    evaluados: int
    filas: tuple[FilaCarga, ...]  # supervision primero, luego productos en orden
    exclusiones: tuple[Exclusion, ...]
    errores: tuple[ErrorCampana, ...]
    consumo: ConsumoLimite

    @property
    def productos_cargados(self) -> int:
        return sum(1 for fila in self.filas if not fila.supervision)

    @property
    def supervision_cargados(self) -> int:
        return sum(1 for fila in self.filas if fila.supervision)

    @property
    def total_cargados(self) -> int:
        return len(self.filas)

    def exclusiones_por_codigo(self) -> dict[CodigoMowaMes, int]:
        return _contar(e.codigo for e in self.exclusiones)

    def advertencias_por_codigo(self) -> dict[CodigoMowaMes, int]:
        return _contar(c for f in self.filas if not f.supervision for c in f.advertencias)

    def productos_por_segmento(self) -> dict[Segmento, int]:
        return _contar(f.segmento for f in self.filas if f.segmento and not f.supervision)


@dataclass(frozen=True)
class CampanaRegistrada:
    """Una campana guardada, con la copia de lo que se uso y sus cifras."""

    id: int
    creado_en: datetime
    fecha_corte: date
    filtros: tuple[str, ...]
    orden: str | None
    cantidad: int
    seleccion_id: int | None
    tipo_carga: TipoCarga
    descripcion: str
    salida: Salida
    herramientas: Herramientas
    programacion: Programacion
    envios: tuple[datetime, ...]
    fecha_envio: date
    speech_id: int
    speech_nombre: str
    whatsapp: str | None
    supervisores: tuple[SupervisorAsignado, ...]
    disponibles: int
    evaluados: int
    productos_cargados: int
    supervision_cargados: int
    excluidos: int
    advertencias: int
    confirmo_limite: bool
    archivos: tuple[ArchivoResumen, ...]

    @property
    def total_cargados(self) -> int:
        return self.productos_cargados + self.supervision_cargados

    @property
    def mes_imputacion(self) -> date:
        return self.fecha_envio.replace(day=1)


class PeticionCampanaInvalida(Exception):
    """Un input de la campana no se puede usar tal como viene."""


class CampanaInvalida(Exception):
    def __init__(self, errores: tuple[ErrorCampana, ...]) -> None:
        super().__init__("La campana no se puede crear. " + "; ".join(e.detalle for e in errores))
        self.errores = errores


class LimiteMensualExcedido(Exception):
    def __init__(self, consumo: ConsumoLimite) -> None:
        super().__init__(
            f"La campana suma {consumo.esta_campana} SMS y el mes {consumo.mes:%Y-%m} quedaria en "
            f"{consumo.total} de {consumo.limite}; confirma para crearla igual"
        )
        self.consumo = consumo


class SpeechCambiado(Exception):
    def __init__(self, speech_id: int) -> None:
        super().__init__(
            f"La version de speech {speech_id} cambio desde la previsualizacion; vuelve a "
            "previsualizar la campana"
        )
        self.speech_id = speech_id


class CampanaNoEncontrada(Exception):
    def __init__(self, campana_id: int) -> None:
        super().__init__(f"No existe la campana {campana_id}")
        self.campana_id = campana_id


class ArchivoNoEncontrado(Exception):
    def __init__(self, campana_id: int, numero: int) -> None:
        super().__init__(f"La campana {campana_id} no tiene el archivo {numero}")


class ArchivoDemasiadoGrande(Exception):
    """Una sola fila ya supera el tamano maximo: no hay division posible."""


def _contar(valores) -> dict:
    conteo: dict = {}
    for valor in valores:
        conteo[valor] = conteo.get(valor, 0) + 1
    return conteo

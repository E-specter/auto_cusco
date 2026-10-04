"""Configuracion y versiones de speech del conector MOWA MES, sobre PostgreSQL."""

from typing import Any

from sqlalchemy import Engine, func, insert, select, update
from sqlalchemy.engine import Row
from sqlalchemy.exc import IntegrityError

from app.adapters.persistence.modelos import MowaMesConfiguracion, MowaMesSpeechVersion
from app.core.entities.mowa_mes import (
    ConfiguracionMowaMes,
    DatosSpeech,
    ExpresionSegmento,
    FormatoSpeech,
    NombreDeSpeechRepetido,
    PartesSegmento,
    Segmento,
    VersionSpeech,
)
from app.core.ports.repositorio_mowa_mes_port import RepositorioMowaMesPort
from app.core.services.texto_enriquecido.serializacion import (
    expresion_a_dict,
    expresion_desde_dict,
)

_CONFIGURACION = MowaMesConfiguracion.__table__
_SPEECH = MowaMesSpeechVersion.__table__
_RESTRICCION_NOMBRE = "uq_mowa_mes_speech_version_nombre_normalizado"
_FILA_CONFIGURACION = 1


def normalizar_nombre(nombre: str) -> str:
    return nombre.strip().casefold()


def _partes_a_json(partes: tuple[PartesSegmento, ...]) -> list[dict[str, str]]:
    return [
        {"segmento": p.segmento.value, "parte_1": p.parte_1, "parte_2": p.parte_2} for p in partes
    ]


def _expresiones_a_json(expresiones: tuple[ExpresionSegmento, ...]) -> list[dict[str, Any]]:
    return [
        {"segmento": e.segmento.value, "expresion": expresion_a_dict(e.expresion)}
        for e in expresiones
    ]


def _valores_de_contenido(datos: DatosSpeech) -> dict[str, Any]:
    """Columnas del contenido: una v1 guarda `partes`; una v2, `expresiones` (y `partes` vacio)."""
    if datos.formato is FormatoSpeech.V2:
        return {
            "formato": FormatoSpeech.V2.value,
            "partes": [],
            "expresiones": _expresiones_a_json(datos.expresiones),
        }
    return {
        "formato": FormatoSpeech.V1.value,
        "partes": _partes_a_json(datos.partes),
        "expresiones": None,
    }


def datos_de_fila(
    nombre: str,
    partes: list[dict[str, Any]],
    formato: str,
    expresiones: list[dict[str, Any]] | None,
) -> DatosSpeech:
    """El contenido de una version tal como esta guardado (lo que la huella y los mensajes leen)."""
    if formato == FormatoSpeech.V2.value:
        return DatosSpeech(
            nombre=nombre,
            expresiones=tuple(
                ExpresionSegmento(Segmento(e["segmento"]), expresion_desde_dict(e["expresion"]))
                for e in expresiones or []
            ),
            formato=FormatoSpeech.V2,
        )
    return DatosSpeech(
        nombre=nombre,
        partes=tuple(
            PartesSegmento(Segmento(p["segmento"]), p["parte_1"], p["parte_2"]) for p in partes
        ),
    )


def _version(fila: Row) -> VersionSpeech:
    return VersionSpeech(
        id=fila.id,
        datos=datos_de_fila(fila.nombre, fila.partes, fila.formato, fila.expresiones),
        original=fila.original,
        basada_en_id=fila.basada_en_id,
        usada_en=fila.usada_en,
        creado_en=fila.creado_en,
    )


def _configuracion(fila: Row) -> ConfiguracionMowaMes:
    return ConfiguracionMowaMes(
        limite_mensual=fila.limite_mensual,
        whatsapp_contacto=fila.whatsapp_contacto,
        actualizado_en=fila.actualizado_en,
        registros_por_archivo=fila.registros_por_archivo,
        bytes_por_archivo=fila.bytes_por_archivo,
        tarifa_sms=fila.tarifa_sms,
        plantilla_nombre_archivo=fila.plantilla_nombre_archivo,
    )


def _es_nombre_repetido(exc: IntegrityError) -> bool:
    diagnostico = getattr(exc.orig, "diag", None)
    return getattr(diagnostico, "constraint_name", None) == _RESTRICCION_NOMBRE


class RepositorioMowaMesPostgres(RepositorioMowaMesPort):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def obtener_configuracion(self) -> ConfiguracionMowaMes:
        with self._engine.connect() as cx:
            fila = cx.execute(
                select(_CONFIGURACION).where(_CONFIGURACION.c.id == _FILA_CONFIGURACION)
            ).one_or_none()
        if fila is None:
            raise RuntimeError("Falta la configuracion de MOWA MES: aplica las migraciones")
        return _configuracion(fila)

    def guardar_configuracion(self, configuracion: ConfiguracionMowaMes) -> ConfiguracionMowaMes:
        consulta = (
            update(_CONFIGURACION)
            .where(_CONFIGURACION.c.id == _FILA_CONFIGURACION)
            .values(
                limite_mensual=configuracion.limite_mensual,
                whatsapp_contacto=configuracion.whatsapp_contacto,
                registros_por_archivo=configuracion.registros_por_archivo,
                bytes_por_archivo=configuracion.bytes_por_archivo,
                tarifa_sms=configuracion.tarifa_sms,
                plantilla_nombre_archivo=configuracion.plantilla_nombre_archivo,
                actualizado_en=func.clock_timestamp(),
            )
            .returning(*_CONFIGURACION.c)
        )
        with self._engine.begin() as cx:
            fila = cx.execute(consulta).one_or_none()
        if fila is None:
            raise RuntimeError("Falta la configuracion de MOWA MES: aplica las migraciones")
        return _configuracion(fila)

    def listar_speech(self) -> list[VersionSpeech]:
        consulta = select(_SPEECH).order_by(
            _SPEECH.c.original.desc(), _SPEECH.c.creado_en, _SPEECH.c.id
        )
        with self._engine.connect() as cx:
            return [_version(fila) for fila in cx.execute(consulta).all()]

    def obtener_speech(self, speech_id: int) -> VersionSpeech | None:
        with self._engine.connect() as cx:
            fila = cx.execute(select(_SPEECH).where(_SPEECH.c.id == speech_id)).one_or_none()
        return _version(fila) if fila else None

    def crear_speech(self, datos: DatosSpeech, basada_en_id: int | None) -> VersionSpeech:
        consulta = (
            insert(_SPEECH)
            .values(
                nombre=datos.nombre,
                nombre_normalizado=normalizar_nombre(datos.nombre),
                **_valores_de_contenido(datos),
                basada_en_id=basada_en_id,
            )
            .returning(*_SPEECH.c)
        )
        try:
            with self._engine.begin() as cx:
                fila = cx.execute(consulta).one()
        except IntegrityError as exc:
            if _es_nombre_repetido(exc):
                raise NombreDeSpeechRepetido(datos.nombre) from exc
            raise
        return _version(fila)

    def actualizar_speech(self, speech_id: int, datos: DatosSpeech) -> VersionSpeech | None:
        consulta = (
            update(_SPEECH)
            .where(
                _SPEECH.c.id == speech_id,
                _SPEECH.c.usada_en.is_(None),
                _SPEECH.c.original.is_(False),
                # El formato no cambia al editar: una v1 sigue siendo v1 y una v2, v2.
                _SPEECH.c.formato == datos.formato.value,
            )
            .values(
                nombre=datos.nombre,
                nombre_normalizado=normalizar_nombre(datos.nombre),
                **_valores_de_contenido(datos),
            )
            .returning(*_SPEECH.c)
        )
        try:
            with self._engine.begin() as cx:
                fila = cx.execute(consulta).one_or_none()
        except IntegrityError as exc:
            if _es_nombre_repetido(exc):
                raise NombreDeSpeechRepetido(datos.nombre) from exc
            raise
        return _version(fila) if fila else None

    def marcar_speech_usado(self, speech_id: int) -> None:
        with self._engine.begin() as cx:
            cx.execute(
                update(_SPEECH)
                .where(_SPEECH.c.id == speech_id, _SPEECH.c.usada_en.is_(None))
                .values(usada_en=func.clock_timestamp())
            )

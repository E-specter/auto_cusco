"""Modelos SQLAlchemy de la ingesta con versionado de sabanas.

Diseno en docs/versionado-sabanas.md (diseno A): una fila por version en
`carga`, el archivo original aparte, las filas normalizadas en columnas
tipadas y las incidencias y la auditoria en sus propias tablas.

Las columnas de `carga_fila` deben coincidir con los valores que produce el
normalizador (app/core/services/ingesta_sabana); tests/test_modelos_persistencia.py
lo verifica contra el catalogo.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.entities.calendario import TipoExcepcion
from app.core.entities.campos_adicionales import TipoAdicional
from app.core.entities.carga import EstadoCarga, EventoAuditoria
from app.core.entities.mowa_mes import FormatoSpeech, Programacion
from app.core.entities.mowa_mes_campana import Salida, TipoCarga
from app.core.entities.sabana import Severidad, TipoDocumento

# Nombres de restricciones estables: Alembic los necesita para migraciones reproducibles.
CONVENCION_NOMBRES = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

MONTO = Numeric(14, 2)  # PEN, supuesto S-1 de docs/sabana-schema.md


def _en(valores: type) -> str:
    return ", ".join(f"'{v.value}'" for v in valores)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCION_NOMBRES)


class Carga(Base):
    """Una version de sabana para una fecha de corte (reglas V-1 a V-9)."""

    __tablename__ = "carga"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    fecha_corte: Mapped[date] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer)
    vigente: Mapped[bool] = mapped_column(Boolean, server_default="false")
    estado: Mapped[str] = mapped_column(String(20), server_default=EstadoCarga.EN_COLA.value)
    nombre_archivo: Mapped[str] = mapped_column(Text)
    huella_archivo: Mapped[str] = mapped_column(String(64))  # SHA-256 hex (V-6)
    tamano_bytes: Mapped[int] = mapped_column(BigInteger)
    hoja: Mapped[str] = mapped_column(Text, server_default="VENCIDA")
    huella_formato: Mapped[str | None] = mapped_column(String(64))  # V-9
    fila_cabecera: Mapped[int | None] = mapped_column(Integer)
    cabeceras_originales: Mapped[list[Any] | None] = mapped_column(JSONB)
    mapeo: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # Como se lee el archivo al procesarlo: formato, hoja, separador y codificacion (RF-57, M-2).
    opciones_lectura: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )
    # El mapeo de encabezados confirmado (RF-60): una asignacion por columna, ya resuelta. NULL =
    # mapear por nombre y alias, como siempre. `none_as_null`: un None es NULL de SQL, no `null`.
    asignaciones: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB(none_as_null=True))
    filas_total: Mapped[int | None] = mapped_column(Integer)
    filas_ingestadas: Mapped[int | None] = mapped_column(Integer)
    incidencias_error: Mapped[int] = mapped_column(Integer, server_default="0")
    incidencias_advertencia: Mapped[int] = mapped_column(Integer, server_default="0")
    incidencias_info: Mapped[int] = mapped_column(Integer, server_default="0")
    motivo_fallo: Mapped[str | None] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    procesado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("fecha_corte", "version"),
        CheckConstraint("version >= 1", name="version_positiva"),
        CheckConstraint(f"estado IN ({_en(EstadoCarga)})", name="estado_valido"),
        # V-5: solo una version terminada puede ser vigente.
        CheckConstraint(
            f"NOT vigente OR estado = '{EstadoCarga.TERMINADA.value}'", name="vigente_terminada"
        ),
        # V-3/V-4: como maximo una version vigente por fecha de corte.
        Index(
            "uq_carga_vigente_por_fecha",
            "fecha_corte",
            unique=True,
            postgresql_where="vigente",
        ),
        Index(None, "fecha_corte", "huella_archivo"),
    )


class BorradorCargaArchivo(Base):
    """Archivo subido y analizado por el mapeador, a la espera de que se confirme (RF-57 a RF-60).

    Guarda el analisis que se le mostro al usuario: se valida contra ese al confirmar (M-4). Vence a
    las 24 horas; confirmarlo lo borra en la misma transaccion que crea la carga.
    """

    __tablename__ = "borrador_carga_archivo"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    catalogo_id: Mapped[str] = mapped_column(Text)
    nombre_archivo: Mapped[str] = mapped_column(Text)
    contenido: Mapped[bytes] = mapped_column(LargeBinary)
    huella: Mapped[str] = mapped_column(String(64))  # SHA-256 hex
    tamano_bytes: Mapped[int] = mapped_column(BigInteger)
    opciones: Mapped[dict[str, Any]] = mapped_column(JSONB)
    analisis: Mapped[dict[str, Any]] = mapped_column(JSONB)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("tamano_bytes >= 0", name="tamano_no_negativo"),
        Index(None, "creado_en"),
    )


class MapeoRecordado(Base):
    """Lo que se confirmo para un encabezado (RF-61): se aplica en las cargas siguientes.

    La clave incluye la ocurrencia entre los encabezados iguales del archivo (M-1): los dos «Pagare»
    de la sabana son las ocurrencias 1 y 2 y se recuerdan por separado. `campo` nulo es «No cargar».
    """

    __tablename__ = "mapeo_recordado"

    catalogo_id: Mapped[str] = mapped_column(Text, primary_key=True)
    encabezado_normalizado: Mapped[str] = mapped_column(Text, primary_key=True)
    ocurrencia: Mapped[int] = mapped_column(Integer, primary_key=True)
    campo: Mapped[str | None] = mapped_column(Text)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (CheckConstraint("ocurrencia >= 1", name="ocurrencia_positiva"),)


class CampoAdicional(Base):
    """Un campo adicional de la cartera (RF-64 a RF-66): lo crea el usuario desde el mapeo.

    El nombre tecnico (`ad_...`) es la clave: estable, global y nunca reutilizado, tambien despues
    de archivar. El nombre legible es unico por catalogo, comparado normalizado (sin tildes ni
    mayusculas). `encabezado_origen` es el encabezado de la sabana, normalizado: su alias literal.
    """

    __tablename__ = "campo_adicional"

    nombre: Mapped[str] = mapped_column(Text, primary_key=True)
    orden: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    catalogo_id: Mapped[str] = mapped_column(Text)
    nombre_legible: Mapped[str] = mapped_column(Text)
    nombre_legible_normalizado: Mapped[str] = mapped_column(Text)
    tipo: Mapped[str] = mapped_column(String(12))
    encabezado_origen: Mapped[str] = mapped_column(Text)
    archivado: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(f"tipo IN ({_en(TipoAdicional)})", name="tipo_valido"),
        UniqueConstraint("catalogo_id", "nombre_legible_normalizado"),
    )


class CargaArchivo(Base):
    """Archivo original de la version: trazabilidad completa (RF-21) y reproceso (RF-33)."""

    __tablename__ = "carga_archivo"

    carga_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("carga.id", ondelete="CASCADE"), primary_key=True
    )
    contenido: Mapped[bytes] = mapped_column(LargeBinary)


class CargaFila(Base):
    """Fila normalizada de una version (docs/sabana-schema.md, seccion 4)."""

    __tablename__ = "carga_fila"

    carga_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("carga.id", ondelete="CASCADE"), primary_key=True
    )
    pagare: Mapped[str] = mapped_column(Text, primary_key=True)
    numero_fila: Mapped[int] = mapped_column(Integer)

    region: Mapped[str | None] = mapped_column(Text)
    agencia: Mapped[str | None] = mapped_column(Text)
    analista_asignacion: Mapped[str | None] = mapped_column(Text)
    titular: Mapped[str | None] = mapped_column(Text)
    documento_tipo: Mapped[str | None] = mapped_column(String(12))
    documento_numero: Mapped[str | None] = mapped_column(Text)
    telefono: Mapped[str | None] = mapped_column(String(9))
    saldo_soles_corte: Mapped[Decimal | None] = mapped_column(MONTO)
    tipo_reprogramacion: Mapped[str | None] = mapped_column(Text)
    vencimiento_operativo_aplica: Mapped[bool | None] = mapped_column(Boolean)
    vencimiento_operativo_fecha: Mapped[date | None] = mapped_column(Date)
    dias_atraso: Mapped[int | None] = mapped_column(Integer)
    analista_actual: Mapped[str | None] = mapped_column(Text)
    saldo_capital_pendiente: Mapped[Decimal | None] = mapped_column(MONTO)
    monto_cuota: Mapped[Decimal | None] = mapped_column(MONTO)
    estado_credito: Mapped[str | None] = mapped_column(Text)
    fecha_vencimiento_cuota: Mapped[date | None] = mapped_column(Date)
    cliente_fallecido: Mapped[bool | None] = mapped_column(Boolean)
    dias_atraso_entidad: Mapped[int | None] = mapped_column(Integer)
    cuotas_aprobadas: Mapped[int | None] = mapped_column(Integer)
    cuotas_pagadas: Mapped[int | None] = mapped_column(Integer)
    cuotas_pendientes: Mapped[int | None] = mapped_column(Integer)
    tipo_basilea: Mapped[str | None] = mapped_column(Text)
    tipo_producto: Mapped[str | None] = mapped_column(Text)
    segmento_saldo: Mapped[str | None] = mapped_column(Text)
    moneda: Mapped[str | None] = mapped_column(Text)
    valor_cierre_mes_anterior: Mapped[Decimal | None] = mapped_column(MONTO)  # pregunta P-2
    saldo_cierre_actual: Mapped[Decimal | None] = mapped_column(MONTO)
    bpo: Mapped[str | None] = mapped_column(Text)
    cartera_tag: Mapped[str | None] = mapped_column(Text)
    mes_gestion: Mapped[str | None] = mapped_column(Text)
    segmento_actual: Mapped[str | None] = mapped_column(Text)
    segmento_financiero: Mapped[str | None] = mapped_column(Text)
    descuento_planilla: Mapped[bool | None] = mapped_column(Boolean)
    segmento_atraso: Mapped[str | None] = mapped_column(Text)
    tramo_actual: Mapped[str | None] = mapped_column(Text)
    provision_actual: Mapped[str | None] = mapped_column(Text)
    mora_impacto_actual: Mapped[bool | None] = mapped_column(Boolean)
    tramo_proyectado: Mapped[str | None] = mapped_column(Text)
    provision_proyectada: Mapped[str | None] = mapped_column(Text)
    mora_impacto_proyectada: Mapped[bool | None] = mapped_column(Boolean)
    cantidad_paralelos: Mapped[int | None] = mapped_column(Integer)
    celular_analista: Mapped[str | None] = mapped_column(String(9))

    # Columnas del archivo que no estan en el catalogo (normalmente vacio).
    extras: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Los campos adicionales (RF-64): nombre tecnico `ad_...` -> valor ya normalizado a su tipo
    # (numero como decimal canonico, fecha ISO, texto). NULL = la version no trae ninguno.
    adicionales: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))

    __table_args__ = (
        CheckConstraint(
            f"documento_tipo IS NULL OR documento_tipo IN ({_en(TipoDocumento)})",
            name="documento_tipo_valido",
        ),
        # Historial de un pagare a traves de las fechas (RF-22) y presencia (RF-23).
        Index(None, "pagare", "carga_id"),
    )


class CargaIncidencia(Base):
    __tablename__ = "carga_incidencia"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    carga_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("carga.id", ondelete="CASCADE"))
    fila: Mapped[int | None] = mapped_column(Integer)  # None = nivel archivo
    columna: Mapped[str | None] = mapped_column(Text)
    codigo: Mapped[str] = mapped_column(Text)
    severidad: Mapped[str] = mapped_column(String(12))
    detalle: Mapped[str] = mapped_column(Text)
    valor_original: Mapped[str | None] = mapped_column(Text)  # dato del usuario: nunca a logs

    __table_args__ = (
        CheckConstraint(f"severidad IN ({_en(Severidad)})", name="severidad_valida"),
        Index(None, "carga_id", "severidad", "codigo"),
    )


class CargaAuditoria(Base):
    """Rastro de versiones, sin datos de la sabana (V-8).

    Sin clave foranea: debe sobrevivir a la eliminacion de la version.
    Sin usuario hasta que exista autenticacion (decision C-3).
    """

    __tablename__ = "carga_auditoria"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    carga_id: Mapped[int] = mapped_column(BigInteger)
    fecha_corte: Mapped[date] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer)
    evento: Mapped[str] = mapped_column(String(30))
    nombre_archivo: Mapped[str | None] = mapped_column(Text)
    huella_archivo: Mapped[str | None] = mapped_column(String(64))
    filas_total: Mapped[int | None] = mapped_column(Integer)
    detalle: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ocurrido_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(f"evento IN ({_en(EventoAuditoria)})", name="evento_valido"),
        Index(None, "fecha_corte", "ocurrido_en"),
    )


class Seleccion(Base):
    """Seleccion de cartera guardada y compartida (docs/selecciones-guardadas.md).

    Filtros, orden e indicadores en la sintaxis de texto de la API. Sin usuario
    hasta que exista autenticacion (decision C-3).
    """

    __tablename__ = "seleccion"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    nombre: Mapped[str] = mapped_column(Text)
    # Sin espacios en los extremos y en minusculas: la unicidad no distingue mayusculas.
    nombre_normalizado: Mapped[str] = mapped_column(Text)
    filtros: Mapped[list[str]] = mapped_column(JSONB, server_default="[]")
    orden: Mapped[str | None] = mapped_column(Text)
    cantidad: Mapped[int | None] = mapped_column(Integer)
    indicadores: Mapped[list[str]] = mapped_column(JSONB, server_default="[]")
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("nombre_normalizado"),
        CheckConstraint("cantidad IS NULL OR cantidad >= 1", name="cantidad_positiva"),
    )


class DefinicionCargaGuardada(Base):
    """Definicion de columnas guardada y compartida (RF-51, docs/motor-texto-enriquecido.md).

    Solo el nombre y las marcas de tiempo; el contenido vive en sus versiones. Sin usuario hasta que
    exista autenticacion (como las selecciones).
    """

    __tablename__ = "definicion_carga"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    nombre: Mapped[str] = mapped_column(Text)
    # Sin espacios en los extremos y en minusculas: la unicidad no distingue mayusculas.
    nombre_normalizado: Mapped[str] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (UniqueConstraint("nombre_normalizado"),)


class DefinicionCargaVersion(Base):
    """Una version de una definicion: la forma JSON canonica del constructor, sin el nombre.

    Ninguna version se modifica: un cambio crea la siguiente (la vigente es la de mayor numero).
    `usada_en` marca la primera carga generada con ella; es informativo.
    """

    __tablename__ = "definicion_carga_version"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    definicion_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("definicion_carga.id", ondelete="CASCADE")
    )
    numero: Mapped[int] = mapped_column(Integer)
    contenido: Mapped[dict[str, Any]] = mapped_column(JSONB)
    usada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("definicion_id", "numero"),
        CheckConstraint("numero >= 1", name="numero_positivo"),
    )


# --- Calendario laboral (RF-MM-08) ---------------------------------------

_TELEFONO_RF02 = "'^9[0-9]{8}$'"


class CalendarioExcepcion(Base):
    """Excepcion a la regla de feriados: dia agregado por decreto o feriado retirado.

    Los feriados de ley no se guardan: se calculan para cualquier ano (S-MM-4).
    """

    __tablename__ = "calendario_excepcion"

    fecha: Mapped[date] = mapped_column(Date, primary_key=True)
    tipo: Mapped[str] = mapped_column(String(12))
    descripcion: Mapped[str] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (CheckConstraint(f"tipo IN ({_en(TipoExcepcion)})", name="tipo_valido"),)


# --- Supervision de campanas digitales (RF-37 a RF-41) -------------------


class SupervisorProcedencia(Base):
    """Procedencias de los supervisores, en el orden en que se asignan los DNIs (RF-39)."""

    __tablename__ = "supervisor_procedencia"

    nombre: Mapped[str] = mapped_column(Text, primary_key=True)
    posicion: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        UniqueConstraint("posicion"),
        CheckConstraint("posicion >= 0", name="posicion_no_negativa"),
    )


class SupervisorDigital(Base):
    """Lista de supervisores por defecto (RF-38). Sin numeros sembrados (RF-32)."""

    __tablename__ = "supervisor_digital"

    posicion: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    numero: Mapped[str] = mapped_column(String(9))
    procedencia: Mapped[str] = mapped_column(Text, ForeignKey("supervisor_procedencia.nombre"))

    __table_args__ = (
        CheckConstraint("posicion >= 0", name="posicion_no_negativa"),
        CheckConstraint(f"numero ~ {_TELEFONO_RF02}", name="numero_valido"),
    )


# --- Conector MOWA MES (docs/requerimientos-mowa-mes.md) -----------------


class MowaMesConfiguracion(Base):
    """Configuracion del conector: una sola fila (RF-MM-01, RF-MM-16)."""

    __tablename__ = "mowa_mes_configuracion"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    limite_mensual: Mapped[int] = mapped_column(BigInteger)
    whatsapp_contacto: Mapped[str | None] = mapped_column(String(9))
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # RF-MM-11: el maximo de la plataforma; la configuracion solo puede bajarlo.
    registros_por_archivo: Mapped[int] = mapped_column(Integer, server_default="50000")
    bytes_por_archivo: Mapped[int] = mapped_column(Integer, server_default="2000000")
    # RF-MM-23: soles por SMS, hasta 4 decimales. RF-MM-25: plantilla del nombre de los archivos.
    tarifa_sms: Mapped[Decimal] = mapped_column(Numeric(12, 4), server_default="0.02")
    plantilla_nombre_archivo: Mapped[str] = mapped_column(
        Text, server_default="mowa_mes_campana_{campana}_{archivo}_de_{total}"
    )

    __table_args__ = (
        CheckConstraint("id = 1", name="fila_unica"),
        CheckConstraint("limite_mensual > 0", name="limite_positivo"),
        CheckConstraint("tarifa_sms >= 0", name="tarifa_no_negativa"),
        CheckConstraint("length(btrim(plantilla_nombre_archivo)) > 0", name="plantilla_no_vacia"),
        CheckConstraint(
            "registros_por_archivo BETWEEN 1 AND 50000", name="registros_por_archivo_valido"
        ),
        CheckConstraint(
            "bytes_por_archivo BETWEEN 100000 AND 2000000", name="bytes_por_archivo_valido"
        ),
        CheckConstraint(
            f"whatsapp_contacto IS NULL OR whatsapp_contacto ~ {_TELEFONO_RF02}",
            name="whatsapp_valido",
        ),
    )


class MowaMesSpeechVersion(Base):
    """Version trazable del speech (RF-MM-17). `partes`: lista de {segmento, parte_1, parte_2}."""

    __tablename__ = "mowa_mes_speech_version"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    nombre: Mapped[str] = mapped_column(Text)
    nombre_normalizado: Mapped[str] = mapped_column(Text)
    partes: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    # M2 (B6): `v1` es la estructura fija de partes; `v2`, una expresion del motor por segmento
    # (`expresiones`: lista de {segmento, expresion}, nula en las v1; `partes` queda en `[]`).
    formato: Mapped[str] = mapped_column(String(2), server_default=FormatoSpeech.V1.value)
    # `none_as_null`: un None de Python es NULL de SQL, no el JSON `null` (que para el CHECK de
    # arriba no es NULL y rechazaria toda v1).
    expresiones: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB(none_as_null=True))
    original: Mapped[bool] = mapped_column(Boolean, server_default="false")
    basada_en_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("mowa_mes_speech_version.id", ondelete="SET NULL")
    )
    # La marca la campana que la usa, en su misma transaccion: desde ahi es inmutable.
    usada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("nombre_normalizado"),
        CheckConstraint(f"formato IN ({_en(FormatoSpeech)})", name="formato_valido"),
        CheckConstraint(
            "(formato = 'v1' AND expresiones IS NULL) "
            "OR (formato = 'v2' AND expresiones IS NOT NULL)",
            name="contenido_segun_formato",
        ),
        Index(
            "uq_mowa_mes_speech_version_original",
            "original",
            unique=True,
            postgresql_where="original",
        ),
    )


class MowaMesCampana(Base):
    """Campana de MOWA MES con la copia de lo que se uso y sus cifras (RF-MM-01 a RF-MM-13).

    Filtros y orden en la sintaxis de texto de `/cartera`; `seleccion_id` es solo
    una referencia informativa: la seleccion guardada puede cambiar o borrarse.
    """

    __tablename__ = "mowa_mes_campana"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    fecha_corte: Mapped[date] = mapped_column(Date)
    filtros: Mapped[list[str]] = mapped_column(JSONB, server_default="[]")
    orden: Mapped[str | None] = mapped_column(Text)
    cantidad: Mapped[int] = mapped_column(Integer)
    seleccion_id: Mapped[int | None] = mapped_column(BigInteger)
    tipo_carga: Mapped[str] = mapped_column(String(20))
    descripcion: Mapped[str] = mapped_column(Text)
    salida: Mapped[str] = mapped_column(String(20))
    herramientas: Mapped[dict[str, Any]] = mapped_column(JSONB)
    programacion: Mapped[str] = mapped_column(String(20))
    envios: Mapped[list[str]] = mapped_column(JSONB, server_default="[]")
    fecha_generacion: Mapped[date] = mapped_column(Date)
    fecha_envio: Mapped[date] = mapped_column(Date)
    mes_imputacion: Mapped[date] = mapped_column(Date)  # S-MM-7: mes de la fecha de envio
    speech_version_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mowa_mes_speech_version.id")
    )
    speech_huella: Mapped[str] = mapped_column(String(64))
    whatsapp: Mapped[str | None] = mapped_column(String(9))
    supervisores: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    disponibles: Mapped[int] = mapped_column(Integer)
    evaluados: Mapped[int] = mapped_column(Integer)
    productos_cargados: Mapped[int] = mapped_column(Integer)
    supervision_cargados: Mapped[int] = mapped_column(Integer)
    total_cargados: Mapped[int] = mapped_column(Integer)
    excluidos: Mapped[int] = mapped_column(Integer)
    advertencias: Mapped[int] = mapped_column(Integer)
    confirmo_limite: Mapped[bool] = mapped_column(Boolean, server_default="false")
    # RF-MM-23 y RF-MM-24: la tarifa vigente al crearla y el costo estimado con ella. NULL en
    # las campanas anteriores: su costo no esta disponible, no se les asigna la tarifa actual.
    tarifa_sms: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    costo_estimado: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    # DERIVADO, no un dato de la campana: los enviados de la conciliacion vigente (E-1),
    # supervision incluida. Lo actualiza la misma transaccion que importa o reemplaza un
    # reporte (y recalcula tambien la campana a la que ese reporte se le quita, si la hay).
    # NULL: sin reporte importado (costo real pendiente). 0: se importo y no se envio nada.
    # El costo real se calcula al leer como enviados_conciliados x tarifa_sms (D-3).
    enviados_conciliados: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint(f"tipo_carga IN ({_en(TipoCarga)})", name="tipo_carga_valido"),
        CheckConstraint(
            "enviados_conciliados IS NULL OR enviados_conciliados BETWEEN 0 AND total_cargados",
            name="enviados_conciliados_validos",
        ),
        CheckConstraint("tarifa_sms IS NULL OR tarifa_sms >= 0", name="tarifa_no_negativa"),
        CheckConstraint("(tarifa_sms IS NULL) = (costo_estimado IS NULL)", name="costo_con_tarifa"),
        CheckConstraint(f"salida IN ({_en(Salida)})", name="salida_valida"),
        CheckConstraint(f"programacion IN ({_en(Programacion)})", name="programacion_valida"),
        CheckConstraint("cantidad >= 1", name="cantidad_positiva"),
        CheckConstraint(
            "total_cargados = productos_cargados + supervision_cargados", name="total_cuadra"
        ),
        Index(None, "mes_imputacion"),
        Index(None, "creado_en"),
    )


class MowaMesArchivo(Base):
    """Archivo `.xlsx` generado: se guarda para que la descarga sea identica (C-6)."""

    __tablename__ = "mowa_mes_archivo"

    campana_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mowa_mes_campana.id", ondelete="CASCADE"), primary_key=True
    )
    numero: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    filas: Mapped[int] = mapped_column(Integer)
    supervision: Mapped[int] = mapped_column(Integer)
    bytes: Mapped[int] = mapped_column(Integer)
    contenido: Mapped[bytes] = mapped_column(LargeBinary)
    # RF-MM-25: el nombre resuelto al crear la campana, con extension. La descarga entrega
    # este mismo nombre aunque la plantilla de la configuracion cambie despues.
    nombre: Mapped[str] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("numero >= 1", name="numero_positivo"),
        CheckConstraint("length(btrim(nombre)) > 0", name="nombre_no_vacio"),
        UniqueConstraint("campana_id", "nombre"),
    )


class MowaMesFilaCargada(Base):
    """Cada fila cargada, en su orden: base de la conciliacion (RF-MM-22)."""

    __tablename__ = "mowa_mes_fila_cargada"

    campana_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mowa_mes_campana.id", ondelete="CASCADE"), primary_key=True
    )
    posicion: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    archivo: Mapped[int] = mapped_column(Integer)
    numero: Mapped[str] = mapped_column(String(9))
    dni: Mapped[str] = mapped_column(Text)
    mensaje: Mapped[str] = mapped_column(Text)
    supervision: Mapped[bool] = mapped_column(Boolean)
    pagare: Mapped[str | None] = mapped_column(Text)
    segmento: Mapped[str | None] = mapped_column(String(12))
    advertencias: Mapped[list[str]] = mapped_column(JSONB, server_default="[]")


class MowaMesExclusion(Base):
    """Producto excluido con su unico motivo (RF-MM-13), en el orden de la seleccion."""

    __tablename__ = "mowa_mes_exclusion"

    campana_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mowa_mes_campana.id", ondelete="CASCADE"), primary_key=True
    )
    pagare: Mapped[str] = mapped_column(Text, primary_key=True)
    orden: Mapped[int] = mapped_column(Integer)
    codigo: Mapped[str] = mapped_column(String(40))

    __table_args__ = (Index(None, "campana_id", "codigo", "orden"),)


class MowaMesReporte(Base):
    """Un `id` de MES importado y asociado a una campana (RF-MM-21, C-5)."""

    __tablename__ = "mowa_mes_reporte"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    campana_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mowa_mes_campana.id", ondelete="CASCADE")
    )
    mes_id: Mapped[int] = mapped_column(BigInteger)
    nombre_archivo: Mapped[str] = mapped_column(Text)
    filas: Mapped[int] = mapped_column(Integer)
    importado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (UniqueConstraint("mes_id"), Index(None, "campana_id"))


class MowaMesReporteFila(Base):
    """Fila del reporte de enviados tal como la entrega MES (RF-MM-20)."""

    __tablename__ = "mowa_mes_reporte_fila"

    reporte_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mowa_mes_reporte.id", ondelete="CASCADE"), primary_key=True
    )
    fila: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    celular: Mapped[str] = mapped_column(Text)
    mensaje: Mapped[str] = mapped_column(Text)
    fecha_envio: Mapped[str] = mapped_column(Text)
    dni: Mapped[str] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(Text)
    salida: Mapped[str] = mapped_column(Text)
    usuario: Mapped[str] = mapped_column(Text)

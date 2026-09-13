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
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.entities.carga import EstadoCarga, EventoAuditoria
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

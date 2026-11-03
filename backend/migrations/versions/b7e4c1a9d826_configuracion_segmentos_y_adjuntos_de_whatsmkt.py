"""configuracion, segmentos y adjuntos de WhatsMKT

Revision ID: b7e4c1a9d826
Revises: e2c6b4a8d195
Create Date: 2026-11-02 12:00:00.000000

T-WM-B1 (RF-WM-04, 07, 20, 26, 30, 31 y 33). Crea solo las tablas que no dependen de piezas
pendientes de herramientas: `whatsmkt_configuracion` (una fila, id 1), `whatsmkt_segmento` y
`whatsmkt_adjunto` (huella SHA-256 unica). La definicion por defecto es una FK nula a
`definicion_carga`; que sea de plataforma whatsmkt se chequea desde B2 (RF-72). La referencia del
segmento a su mensaje guardado entra con B3.

Siembra la configuracion por defecto y los 3 segmentos de S-WM-1. Los valores se copian aqui a
proposito: una migracion no importa codigo de la aplicacion, que puede cambiar despues.
Escrita a mano; los nombres de las restricciones van con `op.f(...)` (ya traen el prefijo de la
convencion de nombres).
"""

from collections.abc import Sequence
from datetime import time

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e4c1a9d826"
down_revision: str | Sequence[str] | None = "e2c6b4a8d195"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# S-WM-1, S-WM-7, S-WM-8 y DU-WM-6 (provisional).
PLANTILLA_POR_DEFECTO = "CUZCO_Vencida ({segmento}) whatsapp {fecha_corte}"
SEGMENTOS = (
    {"clave": "preventivo", "etiqueta": "Preventivo", "desde": None, "hasta": 0, "orden": 0},
    {"clave": "tramo_2", "etiqueta": "Tramo 2", "desde": 1, "hasta": 8, "orden": 1},
    {
        "clave": "mayores_2",
        "etiqueta": "Tramos mayores al 2",
        "desde": 9,
        "hasta": None,
        "orden": 2,
    },
)
TIPOS_ADJUNTO = "'imagen_jpeg', 'imagen_png', 'video', 'audio', 'pdf'"


def upgrade() -> None:
    """Crea las tres tablas y siembra la configuracion y los segmentos."""
    configuracion = op.create_table(
        "whatsmkt_configuracion",
        sa.Column("id", sa.SmallInteger(), autoincrement=False, nullable=False),
        sa.Column("horario_1_inicio", sa.Time(), nullable=False),
        sa.Column("horario_1_fin", sa.Time(), nullable=False),
        sa.Column("horario_2_inicio", sa.Time(), nullable=False),
        sa.Column("horario_2_fin", sa.Time(), nullable=False),
        sa.Column("plantilla_nombre", sa.Text(), nullable=False),
        sa.Column("definicion_defecto_id", sa.BigInteger(), nullable=True),
        sa.Column("tope_mensaje", sa.Integer(), nullable=False),
        sa.Column("tope_video", sa.BigInteger(), nullable=False),
        sa.Column("tope_audio", sa.BigInteger(), nullable=False),
        sa.Column("tope_pdf", sa.BigInteger(), nullable=False),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name=op.f("ck_whatsmkt_configuracion_fila_unica")),
        sa.CheckConstraint(
            "horario_1_inicio < horario_1_fin",
            name=op.f("ck_whatsmkt_configuracion_horario_1_valido"),
        ),
        sa.CheckConstraint(
            "horario_2_inicio < horario_2_fin",
            name=op.f("ck_whatsmkt_configuracion_horario_2_valido"),
        ),
        sa.CheckConstraint(
            "length(btrim(plantilla_nombre)) > 0",
            name=op.f("ck_whatsmkt_configuracion_plantilla_no_vacia"),
        ),
        sa.CheckConstraint(
            "tope_mensaje > 0", name=op.f("ck_whatsmkt_configuracion_tope_mensaje_positivo")
        ),
        sa.CheckConstraint(
            "tope_video > 0", name=op.f("ck_whatsmkt_configuracion_tope_video_positivo")
        ),
        sa.CheckConstraint(
            "tope_audio > 0", name=op.f("ck_whatsmkt_configuracion_tope_audio_positivo")
        ),
        sa.CheckConstraint(
            "tope_pdf > 0", name=op.f("ck_whatsmkt_configuracion_tope_pdf_positivo")
        ),
        sa.ForeignKeyConstraint(
            ["definicion_defecto_id"],
            ["definicion_carga.id"],
            name=op.f("fk_whatsmkt_configuracion_definicion_defecto"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_whatsmkt_configuracion")),
    )
    segmento = op.create_table(
        "whatsmkt_segmento",
        sa.Column("clave", sa.Text(), nullable=False),
        sa.Column("etiqueta", sa.Text(), nullable=False),
        sa.Column("desde", sa.Integer(), nullable=True),
        sa.Column("hasta", sa.Integer(), nullable=True),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "length(btrim(clave)) > 0", name=op.f("ck_whatsmkt_segmento_clave_no_vacia")
        ),
        sa.CheckConstraint(
            "length(btrim(etiqueta)) > 0", name=op.f("ck_whatsmkt_segmento_etiqueta_no_vacia")
        ),
        sa.CheckConstraint(
            "desde IS NULL OR hasta IS NULL OR desde <= hasta",
            name=op.f("ck_whatsmkt_segmento_rango_valido"),
        ),
        sa.PrimaryKeyConstraint("clave", name=op.f("pk_whatsmkt_segmento")),
    )
    op.create_table(
        "whatsmkt_adjunto",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("tipo", sa.String(length=16), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("tamano", sa.BigInteger(), nullable=False),
        sa.Column("huella", sa.String(length=64), nullable=False),
        sa.Column("contenido", sa.LargeBinary(), nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("archivado_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            f"tipo IN ({TIPOS_ADJUNTO})", name=op.f("ck_whatsmkt_adjunto_tipo_valido")
        ),
        sa.CheckConstraint("tamano >= 0", name=op.f("ck_whatsmkt_adjunto_tamano_no_negativo")),
        sa.CheckConstraint(
            "huella ~ '^[0-9a-f]{64}$'", name=op.f("ck_whatsmkt_adjunto_huella_valida")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_whatsmkt_adjunto")),
        sa.UniqueConstraint("huella", name=op.f("uq_whatsmkt_adjunto_huella")),
    )
    op.bulk_insert(
        configuracion,
        [
            {
                "id": 1,
                "horario_1_inicio": time(8, 0),
                "horario_1_fin": time(14, 0),
                "horario_2_inicio": time(14, 0),
                "horario_2_fin": time(20, 0),
                "plantilla_nombre": PLANTILLA_POR_DEFECTO,
                "tope_mensaje": 4096,
                "tope_video": 16_000_000,
                "tope_audio": 16_000_000,
                "tope_pdf": 16_000_000,
            }
        ],
    )
    op.bulk_insert(segmento, list(SEGMENTOS))


def downgrade() -> None:
    """Quita las tres tablas (con su siembra)."""
    op.drop_table("whatsmkt_adjunto")
    op.drop_table("whatsmkt_segmento")
    op.drop_table("whatsmkt_configuracion")

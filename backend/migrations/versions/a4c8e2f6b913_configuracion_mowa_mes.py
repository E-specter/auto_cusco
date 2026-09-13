"""configuracion mowa mes: calendario, supervision y speech

Revision ID: a4c8e2f6b913
Revises: 7c3e9a1d4b52
Create Date: 2026-09-13 18:00:00.000000

Primer corte del modulo mowa_mes (B6a). Siembra solo lo que no es dato
personal ni fecha de un ano: las procedencias iniciales (RF-38), la fila de
configuracion del conector con el limite por defecto y sin WhatsApp (RF-MM-01,
RF-MM-16) y el Speech original con el texto exacto de RF-MM-18. No siembra
numeros de supervisores (RF-32) ni feriados: los de ley se calculan (S-MM-4).

Los textos se copian aqui a proposito: una migracion no importa codigo de la
aplicacion, que puede cambiar despues. tests/test_speech_original.py comprueba
que coincidan con la tabla del documento de requerimientos.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a4c8e2f6b913"
down_revision: str | Sequence[str] | None = "7c3e9a1d4b52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROCEDENCIAS_INICIALES = ("Caja Cusco", "nuestra empresa")
LIMITE_MENSUAL_POR_DEFECTO = 2_500_000

# RF-MM-18. Los espacios de los extremos son parte del texto.
SPEECH_ORIGINAL = (
    {
        "segmento": "preventiva",
        "parte_1": " Caja Cusco te recuerda que tu cuota Vence el ",
        "parte_2": ". Si ya pagaste, omite este mensaje.",
    },
    {
        "segmento": "1_a_8",
        "parte_1": " Caja Cusco te informa que tu cuota venció el ",
        "parte_2": (
            ", acércate a pagar a nuestras agencias, agentes KASNET o a través de Wayki app."
        ),
    },
    {
        "segmento": "9_a_30",
        "parte_1": " Caja Cusco te informa que tu cuota venció el ",
        "parte_2": (
            ", evita estar mal calificado, acércate a pagar a nuestras agencias"
            " y/o canales alternativos."
        ),
    },
    {
        "segmento": "31_a_60",
        "parte_1": " Caja Cusco te informa que tu cuota venció el ",
        "parte_2": ", ponte al día y participa del sorteo de 06 autos. INFO por [whatsapp]",
    },
    {
        "segmento": "61_a_90",
        "parte_1": " cancela tu deuda CAJA CUSCO vencida el ",
        "parte_2": ", pague a tiempo y evite estar mal calificado. Más INFO por [whatsapp]",
    },
    {
        "segmento": "91_a_120",
        "parte_1": " cancela tu deuda CAJA CUSCO vencida el ",
        "parte_2": ", pague a tiempo y evite estar mal calificado. Más INFO por [whatsapp]",
    },
)


def upgrade() -> None:
    """Calendario, supervision por defecto, configuracion y speech de MOWA MES."""
    op.create_table(
        "calendario_excepcion",
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("tipo", sa.String(length=12), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "tipo IN ('agregado', 'retirado')", name=op.f("ck_calendario_excepcion_tipo_valido")
        ),
        sa.PrimaryKeyConstraint("fecha", name=op.f("pk_calendario_excepcion")),
    )
    procedencia = op.create_table(
        "supervisor_procedencia",
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("posicion", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "posicion >= 0", name=op.f("ck_supervisor_procedencia_posicion_no_negativa")
        ),
        sa.PrimaryKeyConstraint("nombre", name=op.f("pk_supervisor_procedencia")),
        sa.UniqueConstraint("posicion", name=op.f("uq_supervisor_procedencia_posicion")),
    )
    op.create_table(
        "supervisor_digital",
        sa.Column("posicion", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("numero", sa.String(length=9), nullable=False),
        sa.Column("procedencia", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "posicion >= 0", name=op.f("ck_supervisor_digital_posicion_no_negativa")
        ),
        sa.CheckConstraint(
            "numero ~ '^9[0-9]{8}$'", name=op.f("ck_supervisor_digital_numero_valido")
        ),
        sa.ForeignKeyConstraint(
            ["procedencia"],
            ["supervisor_procedencia.nombre"],
            name=op.f("fk_supervisor_digital_procedencia_supervisor_procedencia"),
        ),
        sa.PrimaryKeyConstraint("posicion", name=op.f("pk_supervisor_digital")),
    )
    configuracion = op.create_table(
        "mowa_mes_configuracion",
        sa.Column("id", sa.SmallInteger(), autoincrement=False, nullable=False),
        sa.Column("limite_mensual", sa.BigInteger(), nullable=False),
        sa.Column("whatsapp_contacto", sa.String(length=9), nullable=True),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name=op.f("ck_mowa_mes_configuracion_fila_unica")),
        sa.CheckConstraint(
            "limite_mensual > 0", name=op.f("ck_mowa_mes_configuracion_limite_positivo")
        ),
        sa.CheckConstraint(
            "whatsapp_contacto IS NULL OR whatsapp_contacto ~ '^9[0-9]{8}$'",
            name=op.f("ck_mowa_mes_configuracion_whatsapp_valido"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mowa_mes_configuracion")),
    )
    speech = op.create_table(
        "mowa_mes_speech_version",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("nombre_normalizado", sa.Text(), nullable=False),
        sa.Column("partes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("original", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("basada_en_id", sa.BigInteger(), nullable=True),
        sa.Column("usada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["basada_en_id"],
            ["mowa_mes_speech_version.id"],
            name=op.f("fk_mowa_mes_speech_version_basada_en_id_mowa_mes_speech_version"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mowa_mes_speech_version")),
        sa.UniqueConstraint(
            "nombre_normalizado", name=op.f("uq_mowa_mes_speech_version_nombre_normalizado")
        ),
    )
    op.create_index(
        "uq_mowa_mes_speech_version_original",
        "mowa_mes_speech_version",
        ["original"],
        unique=True,
        postgresql_where="original",
    )

    op.bulk_insert(
        procedencia,
        [{"nombre": nombre, "posicion": i} for i, nombre in enumerate(PROCEDENCIAS_INICIALES)],
    )
    op.bulk_insert(
        configuracion,
        [{"id": 1, "limite_mensual": LIMITE_MENSUAL_POR_DEFECTO, "whatsapp_contacto": None}],
    )
    op.bulk_insert(
        speech,
        [
            {
                "nombre": "Speech original",
                "nombre_normalizado": "speech original",
                "partes": list(SPEECH_ORIGINAL),
                "original": True,
            }
        ],
    )


def downgrade() -> None:
    """Quita calendario, supervision, configuracion y speech de MOWA MES."""
    op.drop_index(
        "uq_mowa_mes_speech_version_original",
        table_name="mowa_mes_speech_version",
        postgresql_where="original",
    )
    op.drop_table("mowa_mes_speech_version")
    op.drop_table("mowa_mes_configuracion")
    op.drop_table("supervisor_digital")
    op.drop_table("supervisor_procedencia")
    op.drop_table("calendario_excepcion")

"""campanas y reportes mowa mes

Revision ID: 7a91278726ae
Revises: a4c8e2f6b913
Create Date: 2026-09-13 18:31:04.208006

Segundo corte del modulo mowa_mes (B6b). Campanas con la copia de lo que se
uso, sus archivos .xlsx guardados en la base (C-6), cada fila cargada para la
conciliacion, las exclusiones con su motivo y los reportes de enviados por id
de MES (C-5). Agrega a la configuracion los limites por archivo de RF-MM-11.

Generada con autogenerate y revisada a mano: autogenerate no detecta los CHECK
que se agregan a una tabla existente, asi que los de la configuracion se crean
y se quitan explicitamente. No siembra datos.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "7a91278726ae"
down_revision: str | Sequence[str] | None = "a4c8e2f6b913"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Campanas, archivos, filas cargadas, exclusiones y reportes de MOWA MES."""
    op.create_table(
        "mowa_mes_campana",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("fecha_corte", sa.Date(), nullable=False),
        sa.Column(
            "filtros", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False
        ),
        sa.Column("orden", sa.Text(), nullable=True),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("seleccion_id", sa.BigInteger(), nullable=True),
        sa.Column("tipo_carga", sa.String(length=20), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("salida", sa.String(length=20), nullable=False),
        sa.Column("herramientas", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("programacion", sa.String(length=20), nullable=False),
        sa.Column(
            "envios", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False
        ),
        sa.Column("fecha_generacion", sa.Date(), nullable=False),
        sa.Column("fecha_envio", sa.Date(), nullable=False),
        sa.Column("mes_imputacion", sa.Date(), nullable=False),
        sa.Column("speech_version_id", sa.BigInteger(), nullable=False),
        sa.Column("speech_huella", sa.String(length=64), nullable=False),
        sa.Column("whatsapp", sa.String(length=9), nullable=True),
        sa.Column("supervisores", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("disponibles", sa.Integer(), nullable=False),
        sa.Column("evaluados", sa.Integer(), nullable=False),
        sa.Column("productos_cargados", sa.Integer(), nullable=False),
        sa.Column("supervision_cargados", sa.Integer(), nullable=False),
        sa.Column("total_cargados", sa.Integer(), nullable=False),
        sa.Column("excluidos", sa.Integer(), nullable=False),
        sa.Column("advertencias", sa.Integer(), nullable=False),
        sa.Column("confirmo_limite", sa.Boolean(), server_default="false", nullable=False),
        sa.CheckConstraint(
            "programacion IN ('enviar_ahora', 'hora_determinada', 'diferentes_horas')",
            name=op.f("ck_mowa_mes_campana_programacion_valida"),
        ),
        sa.CheckConstraint(
            "salida IN ('numero_largo', 'numero_corto', 'numero_corto_flash')",
            name=op.f("ck_mowa_mes_campana_salida_valida"),
        ),
        sa.CheckConstraint(
            "tipo_carga IN ('masiva', 'personalizada')",
            name=op.f("ck_mowa_mes_campana_tipo_carga_valido"),
        ),
        sa.CheckConstraint("cantidad >= 1", name=op.f("ck_mowa_mes_campana_cantidad_positiva")),
        sa.CheckConstraint(
            "total_cargados = productos_cargados + supervision_cargados",
            name=op.f("ck_mowa_mes_campana_total_cuadra"),
        ),
        sa.ForeignKeyConstraint(
            ["speech_version_id"],
            ["mowa_mes_speech_version.id"],
            name=op.f("fk_mowa_mes_campana_speech_version_id_mowa_mes_speech_version"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mowa_mes_campana")),
    )
    op.create_index(
        op.f("ix_mowa_mes_campana_creado_en"), "mowa_mes_campana", ["creado_en"], unique=False
    )
    op.create_index(
        op.f("ix_mowa_mes_campana_mes_imputacion"),
        "mowa_mes_campana",
        ["mes_imputacion"],
        unique=False,
    )
    op.create_table(
        "mowa_mes_archivo",
        sa.Column("campana_id", sa.BigInteger(), nullable=False),
        sa.Column("numero", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("filas", sa.Integer(), nullable=False),
        sa.Column("supervision", sa.Integer(), nullable=False),
        sa.Column("bytes", sa.Integer(), nullable=False),
        sa.Column("contenido", sa.LargeBinary(), nullable=False),
        sa.CheckConstraint("numero >= 1", name=op.f("ck_mowa_mes_archivo_numero_positivo")),
        sa.ForeignKeyConstraint(
            ["campana_id"],
            ["mowa_mes_campana.id"],
            name=op.f("fk_mowa_mes_archivo_campana_id_mowa_mes_campana"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("campana_id", "numero", name=op.f("pk_mowa_mes_archivo")),
    )
    op.create_table(
        "mowa_mes_exclusion",
        sa.Column("campana_id", sa.BigInteger(), nullable=False),
        sa.Column("pagare", sa.Text(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(
            ["campana_id"],
            ["mowa_mes_campana.id"],
            name=op.f("fk_mowa_mes_exclusion_campana_id_mowa_mes_campana"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("campana_id", "pagare", name=op.f("pk_mowa_mes_exclusion")),
    )
    op.create_index(
        op.f("ix_mowa_mes_exclusion_campana_id_codigo_orden"),
        "mowa_mes_exclusion",
        ["campana_id", "codigo", "orden"],
        unique=False,
    )
    op.create_table(
        "mowa_mes_fila_cargada",
        sa.Column("campana_id", sa.BigInteger(), nullable=False),
        sa.Column("posicion", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("archivo", sa.Integer(), nullable=False),
        sa.Column("numero", sa.String(length=9), nullable=False),
        sa.Column("dni", sa.Text(), nullable=False),
        sa.Column("mensaje", sa.Text(), nullable=False),
        sa.Column("supervision", sa.Boolean(), nullable=False),
        sa.Column("pagare", sa.Text(), nullable=True),
        sa.Column("segmento", sa.String(length=12), nullable=True),
        sa.Column(
            "advertencias",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["campana_id"],
            ["mowa_mes_campana.id"],
            name=op.f("fk_mowa_mes_fila_cargada_campana_id_mowa_mes_campana"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("campana_id", "posicion", name=op.f("pk_mowa_mes_fila_cargada")),
    )
    op.create_table(
        "mowa_mes_reporte",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("campana_id", sa.BigInteger(), nullable=False),
        sa.Column("mes_id", sa.BigInteger(), nullable=False),
        sa.Column("nombre_archivo", sa.Text(), nullable=False),
        sa.Column("filas", sa.Integer(), nullable=False),
        sa.Column(
            "importado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["campana_id"],
            ["mowa_mes_campana.id"],
            name=op.f("fk_mowa_mes_reporte_campana_id_mowa_mes_campana"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mowa_mes_reporte")),
        sa.UniqueConstraint("mes_id", name=op.f("uq_mowa_mes_reporte_mes_id")),
    )
    op.create_index(
        op.f("ix_mowa_mes_reporte_campana_id"), "mowa_mes_reporte", ["campana_id"], unique=False
    )
    op.create_table(
        "mowa_mes_reporte_fila",
        sa.Column("reporte_id", sa.BigInteger(), nullable=False),
        sa.Column("fila", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("celular", sa.Text(), nullable=False),
        sa.Column("mensaje", sa.Text(), nullable=False),
        sa.Column("fecha_envio", sa.Text(), nullable=False),
        sa.Column("dni", sa.Text(), nullable=False),
        sa.Column("estado", sa.Text(), nullable=False),
        sa.Column("salida", sa.Text(), nullable=False),
        sa.Column("usuario", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["reporte_id"],
            ["mowa_mes_reporte.id"],
            name=op.f("fk_mowa_mes_reporte_fila_reporte_id_mowa_mes_reporte"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("reporte_id", "fila", name=op.f("pk_mowa_mes_reporte_fila")),
    )
    op.add_column(
        "mowa_mes_configuracion",
        sa.Column("registros_por_archivo", sa.Integer(), server_default="50000", nullable=False),
    )
    op.add_column(
        "mowa_mes_configuracion",
        sa.Column("bytes_por_archivo", sa.Integer(), server_default="2000000", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_mowa_mes_configuracion_registros_por_archivo_valido"),
        "mowa_mes_configuracion",
        "registros_por_archivo BETWEEN 1 AND 50000",
    )
    op.create_check_constraint(
        op.f("ck_mowa_mes_configuracion_bytes_por_archivo_valido"),
        "mowa_mes_configuracion",
        "bytes_por_archivo BETWEEN 100000 AND 2000000",
    )


def downgrade() -> None:
    """Quita campanas, reportes y los limites por archivo de la configuracion."""
    op.drop_constraint(
        op.f("ck_mowa_mes_configuracion_bytes_por_archivo_valido"),
        "mowa_mes_configuracion",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_mowa_mes_configuracion_registros_por_archivo_valido"),
        "mowa_mes_configuracion",
        type_="check",
    )
    op.drop_column("mowa_mes_configuracion", "bytes_por_archivo")
    op.drop_column("mowa_mes_configuracion", "registros_por_archivo")
    op.drop_table("mowa_mes_reporte_fila")
    op.drop_index(op.f("ix_mowa_mes_reporte_campana_id"), table_name="mowa_mes_reporte")
    op.drop_table("mowa_mes_reporte")
    op.drop_table("mowa_mes_fila_cargada")
    op.drop_index(
        op.f("ix_mowa_mes_exclusion_campana_id_codigo_orden"), table_name="mowa_mes_exclusion"
    )
    op.drop_table("mowa_mes_exclusion")
    op.drop_table("mowa_mes_archivo")
    op.drop_index(op.f("ix_mowa_mes_campana_mes_imputacion"), table_name="mowa_mes_campana")
    op.drop_index(op.f("ix_mowa_mes_campana_creado_en"), table_name="mowa_mes_campana")
    op.drop_table("mowa_mes_campana")

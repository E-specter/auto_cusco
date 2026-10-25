"""mapeador de encabezados: borradores, mapeos recordados y opciones de lectura

Revision ID: b6e1d9c4a728
Revises: f2c8a4d7b915
Create Date: 2026-10-26 10:00:00.000000

T-MAP-B3a (RF-57 a RF-62, docs/mapeador-encabezados.md §5):

- `borrador_carga_archivo`: el archivo subido y analizado, con el analisis que se mostro (M-4).
- `mapeo_recordado`: lo confirmado por encabezado normalizado y ocurrencia (M-1), por catalogo.
- `carga.opciones_lectura`: como se vuelve a leer el archivo al procesarlo (M-2); las versiones
  existentes quedan con `{"hoja": hoja}`.
- `carga.asignaciones`: el mapeo confirmado de una carga (NULL = por nombre y alias, como siempre).

No siembra datos.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b6e1d9c4a728"
down_revision: str | Sequence[str] | None = "f2c8a4d7b915"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "borrador_carga_archivo",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("catalogo_id", sa.Text(), nullable=False),
        sa.Column("nombre_archivo", sa.Text(), nullable=False),
        sa.Column("contenido", sa.LargeBinary(), nullable=False),
        sa.Column("huella", sa.String(length=64), nullable=False),
        sa.Column("tamano_bytes", sa.BigInteger(), nullable=False),
        sa.Column("opciones", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("analisis", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "tamano_bytes >= 0", name=op.f("ck_borrador_carga_archivo_tamano_no_negativo")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_borrador_carga_archivo")),
    )
    op.create_index(
        op.f("ix_borrador_carga_archivo_creado_en"), "borrador_carga_archivo", ["creado_en"]
    )
    op.create_table(
        "mapeo_recordado",
        sa.Column("catalogo_id", sa.Text(), nullable=False),
        sa.Column("encabezado_normalizado", sa.Text(), nullable=False),
        sa.Column("ocurrencia", sa.Integer(), nullable=False),
        sa.Column("campo", sa.Text(), nullable=True),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("ocurrencia >= 1", name=op.f("ck_mapeo_recordado_ocurrencia_positiva")),
        sa.PrimaryKeyConstraint(
            "catalogo_id", "encabezado_normalizado", "ocurrencia", name=op.f("pk_mapeo_recordado")
        ),
    )
    op.add_column(
        "carga",
        sa.Column(
            "opciones_lectura",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.execute("UPDATE carga SET opciones_lectura = jsonb_build_object('hoja', hoja)")
    op.add_column(
        "carga",
        sa.Column(
            "asignaciones",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("carga", "asignaciones")
    op.drop_column("carga", "opciones_lectura")
    op.drop_table("mapeo_recordado")
    op.drop_index(op.f("ix_borrador_carga_archivo_creado_en"), table_name="borrador_carga_archivo")
    op.drop_table("borrador_carga_archivo")

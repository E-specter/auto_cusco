"""campos adicionales: definiciones y valores por fila

Revision ID: c8f1a3d6e254
Revises: b6e1d9c4a728
Create Date: 2026-10-27 15:00:00.000000

T-CA-B2 (RF-64 a RF-66, docs/mapeador-encabezados.md):

- `campo_adicional`: las definiciones que crea el usuario desde el mapeo (nombre tecnico `ad_...`
  estable, nombre legible unico por catalogo, tipo fijo, archivado).
- `carga_fila.adicionales`: el valor de cada adicional por fila, ya normalizado a su tipo. NULL en
  las versiones existentes y en las que no traen ninguno.

No siembra datos.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c8f1a3d6e254"
down_revision: str | Sequence[str] | None = "b6e1d9c4a728"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "campo_adicional",
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("orden", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("catalogo_id", sa.Text(), nullable=False),
        sa.Column("nombre_legible", sa.Text(), nullable=False),
        sa.Column("nombre_legible_normalizado", sa.Text(), nullable=False),
        sa.Column("tipo", sa.String(length=12), nullable=False),
        sa.Column("encabezado_origen", sa.Text(), nullable=False),
        sa.Column("archivado", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "tipo IN ('texto', 'numero', 'fecha')", name=op.f("ck_campo_adicional_tipo_valido")
        ),
        sa.PrimaryKeyConstraint("nombre", name=op.f("pk_campo_adicional")),
        sa.UniqueConstraint("orden", name=op.f("uq_campo_adicional_orden")),
        sa.UniqueConstraint(
            "catalogo_id",
            "nombre_legible_normalizado",
            name=op.f("uq_campo_adicional_catalogo_id_nombre_legible_normalizado"),
        ),
    )
    op.add_column(
        "carga_fila",
        sa.Column(
            "adicionales",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("carga_fila", "adicionales")
    op.drop_table("campo_adicional")

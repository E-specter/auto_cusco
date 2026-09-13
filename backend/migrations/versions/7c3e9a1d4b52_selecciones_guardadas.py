"""selecciones guardadas

Revision ID: 7c3e9a1d4b52
Revises: 1fe354a9a285
Create Date: 2026-09-12 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "7c3e9a1d4b52"
down_revision: str | Sequence[str] | None = "1fe354a9a285"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Selecciones de cartera guardadas y compartidas (docs/selecciones-guardadas.md)."""
    op.create_table(
        "seleccion",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("nombre_normalizado", sa.Text(), nullable=False),
        sa.Column(
            "filtros", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False
        ),
        sa.Column("orden", sa.Text(), nullable=True),
        sa.Column("cantidad", sa.Integer(), nullable=True),
        sa.Column(
            "indicadores",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
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
            "cantidad IS NULL OR cantidad >= 1", name=op.f("ck_seleccion_cantidad_positiva")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_seleccion")),
        sa.UniqueConstraint("nombre_normalizado", name=op.f("uq_seleccion_nombre_normalizado")),
    )


def downgrade() -> None:
    """Quita las selecciones guardadas."""
    op.drop_table("seleccion")

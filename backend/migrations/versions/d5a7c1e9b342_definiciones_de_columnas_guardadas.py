"""definiciones de columnas guardadas y versionadas

Revision ID: d5a7c1e9b342
Revises: c3d9f5a17e28
Create Date: 2026-10-02 12:00:00.000000

Definiciones de columnas del constructor (RF-51, T-MTE-B4b): la definicion con su nombre unico
normalizado y, aparte, sus versiones numeradas desde 1 con el contenido en JSONB. Ninguna version
se modifica; `usada_en` marca la primera carga generada con ella. No siembra datos.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d5a7c1e9b342"
down_revision: str | Sequence[str] | None = "c3d9f5a17e28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crea `definicion_carga` y `definicion_carga_version`."""
    op.create_table(
        "definicion_carga",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("nombre_normalizado", sa.Text(), nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_definicion_carga")),
        sa.UniqueConstraint(
            "nombre_normalizado", name=op.f("uq_definicion_carga_nombre_normalizado")
        ),
    )
    op.create_table(
        "definicion_carga_version",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("definicion_id", sa.BigInteger(), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("contenido", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("usada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint("numero >= 1", name=op.f("ck_definicion_carga_version_numero_positivo")),
        sa.ForeignKeyConstraint(
            ["definicion_id"],
            ["definicion_carga.id"],
            name=op.f("fk_definicion_carga_version_definicion_id_definicion_carga"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_definicion_carga_version")),
        sa.UniqueConstraint(
            "definicion_id",
            "numero",
            name=op.f("uq_definicion_carga_version_definicion_id_numero"),
        ),
    )


def downgrade() -> None:
    """Quita las definiciones guardadas y sus versiones."""
    op.drop_table("definicion_carga_version")
    op.drop_table("definicion_carga")

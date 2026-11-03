"""plataforma de la definicion de columnas

Revision ID: a4d8f2b6c713
Revises: b7e4c1a9d826
Create Date: 2026-11-02 22:00:00.000000

Plataforma de destino de una definicion de columnas (RF-72, T-HI-B2): `definicion_carga.plataforma`,
la clave de una plataforma registrada (`whatsmkt`, `mowa_mes`...). Se fija al crear la definicion y
no cambia; NULL es un archivo libre, como todo lo guardado hasta ahora (RF-54). La base no conoce
las plataformas: solo exige que la clave, si hay, no sea vacia. No siembra ni toca datos.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4d8f2b6c713"
down_revision: str | Sequence[str] | None = "b7e4c1a9d826"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Agrega `definicion_carga.plataforma` (NULL) con su CHECK de no vacia."""
    op.add_column("definicion_carga", sa.Column("plataforma", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_definicion_carga_plataforma_no_vacia"),
        "definicion_carga",
        "plataforma IS NULL OR length(btrim(plataforma)) > 0",
    )


def downgrade() -> None:
    """Quita la columna y su CHECK: las definiciones vuelven a ser archivos libres."""
    op.drop_constraint(
        op.f("ck_definicion_carga_plataforma_no_vacia"), "definicion_carga", type_="check"
    )
    op.drop_column("definicion_carga", "plataforma")

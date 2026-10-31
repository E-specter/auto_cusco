"""campanas descartadas de MOWA MES

Revision ID: b4e7a1c9d352
Revises: e9b3d2a7c561
Create Date: 2026-10-30 09:00:00.000000

T-MM-C11, M-B1 (RF-MM-31, RF-MM-32): `mowa_mes_campana.descartada_en` marca cuando se descarto una
campana; NULL es una campana activa. Descartar es logico: la campana conserva sus archivos, filas,
exclusiones y reportes, y queda fuera del limite mensual, del costo del mes y del listado de
activas. Eliminarla del todo la borra en cascada.

No siembra datos: toda campana existente queda activa.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4e7a1c9d352"
down_revision: str | Sequence[str] | None = "e9b3d2a7c561"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "mowa_mes_campana",
        sa.Column("descartada_en", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("mowa_mes_campana", "descartada_en")

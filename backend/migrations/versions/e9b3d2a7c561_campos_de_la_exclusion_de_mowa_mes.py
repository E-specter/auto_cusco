"""campos de la exclusion de MOWA MES

Revision ID: e9b3d2a7c561
Revises: c8f1a3d6e254
Create Date: 2026-10-28 09:00:00.000000

T-MM-B12 (RF-65, D-CA-2): `mowa_mes_exclusion.campos` guarda los nombres tecnicos (`ad_...`) de los
campos adicionales vacios que hicieron excluir al producto con `falta_campo_adicional`. NULL en las
exclusiones anteriores y en las de los demas codigos. El nombre legible no se guarda: se resuelve al
leer con el catalogo, asi renombrar un campo no deja textos viejos.

No siembra datos.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e9b3d2a7c561"
down_revision: str | Sequence[str] | None = "c8f1a3d6e254"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "mowa_mes_exclusion",
        sa.Column("campos", postgresql.ARRAY(sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("mowa_mes_exclusion", "campos")

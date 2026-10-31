"""deshabilitar versiones de speech de MOWA MES

Revision ID: c5d9f2a8e714
Revises: b4e7a1c9d352
Create Date: 2026-10-31 09:00:00.000000

T-MM-C11, M-B2 (RF-MM-29): `mowa_mes_speech_version.deshabilitada_en` marca cuando se deshabilito
una version; NULL es una version habilitada. Una deshabilitada no se puede elegir en una campana
nueva, pero conserva todo (contenido, huella, `usada_en`) y se puede volver a habilitar. Eliminarla
(RF-MM-30) es un borrado aparte, solo si ninguna campana la uso.

No siembra datos: toda version existente queda habilitada.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5d9f2a8e714"
down_revision: str | Sequence[str] | None = "b4e7a1c9d352"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "mowa_mes_speech_version",
        sa.Column("deshabilitada_en", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("mowa_mes_speech_version", "deshabilitada_en")

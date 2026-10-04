"""speech v2 con expresiones por segmento

Revision ID: f2c8a4d7b915
Revises: d5a7c1e9b342
Create Date: 2026-10-04 12:00:00.000000

MOWA MES M2 (T-MTE-B6): una version del speech puede ser v2, con una expresion del motor de texto
enriquecido por segmento (`expresiones`, JSONB) en lugar de las dos partes de siempre (`partes`).
Las versiones que ya existen, incluido el Speech original, quedan como `v1` con `partes` intacto:
la huella de cada una (la que registraron sus campanas) no cambia. No siembra datos.

Escrita a mano: autogenerate no detecta bien los CHECK que se agregan a una tabla existente.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f2c8a4d7b915"
down_revision: str | Sequence[str] | None = "d5a7c1e9b342"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """`formato` (v1 en lo existente) y `expresiones` (nula en las v1)."""
    op.add_column(
        "mowa_mes_speech_version",
        sa.Column("formato", sa.String(length=2), server_default="v1", nullable=False),
    )
    op.add_column(
        "mowa_mes_speech_version",
        sa.Column("expresiones", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_mowa_mes_speech_version_formato_valido"),
        "mowa_mes_speech_version",
        "formato IN ('v1', 'v2')",
    )
    op.create_check_constraint(
        op.f("ck_mowa_mes_speech_version_contenido_segun_formato"),
        "mowa_mes_speech_version",
        "(formato = 'v1' AND expresiones IS NULL) OR (formato = 'v2' AND expresiones IS NOT NULL)",
    )


def downgrade() -> None:
    """Quita el formato. Si ya hay versiones v2 no hay a donde volver: se niega, sin borrar nada."""
    hay_v2 = (
        not context.is_offline_mode()
        and op.get_bind()
        .execute(
            sa.text("SELECT EXISTS (SELECT 1 FROM mowa_mes_speech_version WHERE formato = 'v2')")
        )
        .scalar()
    )
    if hay_v2:
        raise RuntimeError(
            "Hay versiones de speech v2: no se puede volver al esquema anterior sin perderlas. "
            "Borra esas versiones (y las campanas que las usaron) a conciencia y repite."
        )
    op.drop_constraint(
        op.f("ck_mowa_mes_speech_version_contenido_segun_formato"),
        "mowa_mes_speech_version",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_mowa_mes_speech_version_formato_valido"), "mowa_mes_speech_version", type_="check"
    )
    op.drop_column("mowa_mes_speech_version", "expresiones")
    op.drop_column("mowa_mes_speech_version", "formato")

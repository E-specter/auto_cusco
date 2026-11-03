"""textos guardados y versionados por contexto

Revision ID: c9e5a1d7b384
Revises: a4d8f2b6c713
Create Date: 2026-11-02 23:00:00.000000

Textos guardados por contexto (RF-69, T-HI-B4): `texto_guardado`, con su nombre unico dentro del
contexto (sobre el nombre normalizado) y `deshabilitado_en`, y `texto_guardado_version`, con las
versiones numeradas desde 1 y el contenido en JSONB. Ninguna version se modifica; `usada_en` marca
la primera vez que algo la uso, y con alguna usada el texto no se elimina.

`contenido` es NOT NULL y ademas lleva el CHECK `contenido_es_un_objeto`
(`jsonb_typeof(contenido) = 'object'`): NOT NULL no basta, porque el JSON `null`, una lista o un
numero no son NULL de SQL y pasan. La base no conoce los contextos ni sus validadores: eso lo hace
el servicio. No siembra datos. Los nombres de restriccion van con `op.f(...)` (ya traen el prefijo
de la convencion) y miden 63 caracteres o menos.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c9e5a1d7b384"
down_revision: str | Sequence[str] | None = "a4d8f2b6c713"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crea `texto_guardado` y `texto_guardado_version`."""
    op.create_table(
        "texto_guardado",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("contexto", sa.Text(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("nombre_normalizado", sa.Text(), nullable=False),
        sa.Column("deshabilitado_en", sa.DateTime(timezone=True), nullable=True),
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
            "length(btrim(contexto)) > 0", name=op.f("ck_texto_guardado_contexto_no_vacio")
        ),
        sa.CheckConstraint(
            "length(btrim(nombre)) > 0", name=op.f("ck_texto_guardado_nombre_no_vacio")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_texto_guardado")),
        sa.UniqueConstraint(
            "contexto",
            "nombre_normalizado",
            name=op.f("uq_texto_guardado_contexto_nombre_normalizado"),
        ),
    )
    op.create_table(
        "texto_guardado_version",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("texto_id", sa.BigInteger(), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column(
            "contenido", postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=False
        ),
        sa.Column("usada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint("numero >= 1", name=op.f("ck_texto_guardado_version_numero_positivo")),
        sa.CheckConstraint(
            "jsonb_typeof(contenido) = 'object'",
            name=op.f("ck_texto_guardado_version_contenido_es_un_objeto"),
        ),
        sa.ForeignKeyConstraint(
            ["texto_id"],
            ["texto_guardado.id"],
            name=op.f("fk_texto_guardado_version_texto_id_texto_guardado"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_texto_guardado_version")),
        sa.UniqueConstraint(
            "texto_id", "numero", name=op.f("uq_texto_guardado_version_texto_id_numero")
        ),
    )


def downgrade() -> None:
    """Quita los textos guardados y sus versiones."""
    op.drop_table("texto_guardado_version")
    op.drop_table("texto_guardado")

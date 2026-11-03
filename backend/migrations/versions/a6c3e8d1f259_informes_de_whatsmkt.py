"""informes de WhatsMKT: el informe importado de una campana y sus numeros

Revision ID: a6c3e8d1f259
Revises: e8a2c6f1b937
Create Date: 2026-11-03 20:00:00.000000

T-WM-B6 (RF-WM-37, 38 y 39):

- `whatsmkt_reporte`: el informe vigente de una campana. `campana_id` es UNICO: un informe vigente
  por campana, y reemplazarlo es borrar el anterior e insertar el nuevo en una transaccion. Guarda
  lo que el informe informa (fecha, total, el nombre de campana y el tipo de envio tal como lo
  escribe WhatsMKT, que solo se muestran) y la huella SHA-256 del archivo.
- `whatsmkt_reporte_fila`: un numero por fila de detalle, en el orden del informe. Un numero
  repetido se conserva repetido (el total informado se compara con las filas); la clave es
  (reporte, posicion).

Las dos cuelgan de la campana con ON DELETE CASCADE: eliminar una campana descartada se lleva sus
informes. Sin siembra. Los nombres de las restricciones miden 63 caracteres o menos.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a6c3e8d1f259"
down_revision: str | Sequence[str] | None = "e8a2c6f1b937"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AHORA = sa.text("now()")


def upgrade() -> None:
    """Crea las dos tablas."""
    op.create_table(
        "whatsmkt_reporte",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("campana_id", sa.BigInteger(), nullable=False),
        sa.Column("archivo_nombre", sa.Text(), nullable=False),
        sa.Column("huella", sa.String(length=64), nullable=False),
        sa.Column("fecha_informada", sa.Date(), nullable=True),
        sa.Column("total_informado", sa.Integer(), nullable=True),
        sa.Column("campana_informada", sa.Text(), nullable=True),
        sa.Column("tipo_envio_informado", sa.Text(), nullable=True),
        sa.Column("importado_en", sa.DateTime(timezone=True), server_default=AHORA, nullable=False),
        sa.CheckConstraint("length(huella) = 64", name=op.f("ck_whatsmkt_reporte_huella_valida")),
        sa.CheckConstraint(
            "total_informado IS NULL OR total_informado >= 0",
            name=op.f("ck_whatsmkt_reporte_total_no_negativo"),
        ),
        sa.ForeignKeyConstraint(
            ["campana_id"],
            ["whatsmkt_campana.id"],
            name=op.f("fk_whatsmkt_reporte_campana_id_whatsmkt_campana"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_whatsmkt_reporte")),
        sa.UniqueConstraint("campana_id", name=op.f("uq_whatsmkt_reporte_campana_id")),
    )
    op.create_table(
        "whatsmkt_reporte_fila",
        sa.Column("reporte_id", sa.BigInteger(), nullable=False),
        sa.Column("posicion", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("numero", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "posicion >= 1", name=op.f("ck_whatsmkt_reporte_fila_posicion_positiva")
        ),
        sa.CheckConstraint(
            "numero ~ '^[0-9]+$'", name=op.f("ck_whatsmkt_reporte_fila_numero_de_digitos")
        ),
        sa.ForeignKeyConstraint(
            ["reporte_id"],
            ["whatsmkt_reporte.id"],
            name=op.f("fk_whatsmkt_reporte_fila_reporte_id_whatsmkt_reporte"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("reporte_id", "posicion", name=op.f("pk_whatsmkt_reporte_fila")),
    )


def downgrade() -> None:
    """Quita las dos tablas, de la hija a la madre."""
    op.drop_table("whatsmkt_reporte_fila")
    op.drop_table("whatsmkt_reporte")

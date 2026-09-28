"""tarifa, costos y nombre de archivos de mowa mes

Revision ID: c3d9f5a17e28
Revises: 7a91278726ae
Create Date: 2026-09-28 12:00:00.000000

Corte B8 del modulo mowa_mes (RF-MM-23 a RF-MM-25).

- `mowa_mes_configuracion`: `tarifa_sms` (soles por SMS, 4 decimales, 0.02 por
  defecto) y `plantilla_nombre_archivo` (la que el sistema ya usaba de facto).
- `mowa_mes_campana`: `tarifa_sms` y `costo_estimado`, congelados al crearla. Las
  campanas existentes quedan con NULL en los dos: su costo no esta disponible y no
  se les asigna la tarifa actual. Ademas `enviados_conciliados`, un valor DERIVADO
  (los enviados de la conciliacion vigente, regla E-1) que actualiza la misma
  transaccion que importa o reemplaza un reporte; NULL es "sin reporte" (pendiente),
  0 es "se importo y no se envio nada". Sin backfill: las campanas existentes no
  tienen tarifa, asi que su costo real es "no disponible" con o sin reportes.
- `mowa_mes_archivo`: `nombre`, el nombre resuelto al crear la campana. Las campanas
  existentes se completan con el nombre que ya tenia su descarga
  (`mowa_mes_campana_<id>_<n>_de_<total>.xlsx`), asi que no cambia ninguna descarga.

Escrita a mano: autogenerate no detecta los CHECK que se agregan a una tabla
existente. No siembra datos.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d9f5a17e28"
down_revision: str | Sequence[str] | None = "7a91278726ae"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PLANTILLA_POR_DEFECTO = "mowa_mes_campana_{campana}_{archivo}_de_{total}"


def upgrade() -> None:
    """Tarifa y plantilla en la configuracion; tarifa y costo en la campana; nombre por archivo."""
    op.add_column(
        "mowa_mes_configuracion",
        sa.Column("tarifa_sms", sa.Numeric(12, 4), server_default="0.02", nullable=False),
    )
    op.add_column(
        "mowa_mes_configuracion",
        sa.Column(
            "plantilla_nombre_archivo",
            sa.Text(),
            server_default=_PLANTILLA_POR_DEFECTO,
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_mowa_mes_configuracion_tarifa_no_negativa"),
        "mowa_mes_configuracion",
        "tarifa_sms >= 0",
    )
    op.create_check_constraint(
        op.f("ck_mowa_mes_configuracion_plantilla_no_vacia"),
        "mowa_mes_configuracion",
        "length(btrim(plantilla_nombre_archivo)) > 0",
    )

    op.add_column("mowa_mes_campana", sa.Column("tarifa_sms", sa.Numeric(12, 4), nullable=True))
    op.add_column("mowa_mes_campana", sa.Column("costo_estimado", sa.Numeric(18, 4), nullable=True))
    op.add_column(
        "mowa_mes_campana", sa.Column("enviados_conciliados", sa.Integer(), nullable=True)
    )
    op.create_check_constraint(
        op.f("ck_mowa_mes_campana_enviados_conciliados_validos"),
        "mowa_mes_campana",
        "enviados_conciliados IS NULL OR enviados_conciliados BETWEEN 0 AND total_cargados",
    )
    op.create_check_constraint(
        op.f("ck_mowa_mes_campana_tarifa_no_negativa"),
        "mowa_mes_campana",
        "tarifa_sms IS NULL OR tarifa_sms >= 0",
    )
    op.create_check_constraint(
        op.f("ck_mowa_mes_campana_costo_con_tarifa"),
        "mowa_mes_campana",
        "(tarifa_sms IS NULL) = (costo_estimado IS NULL)",
    )

    op.add_column("mowa_mes_archivo", sa.Column("nombre", sa.Text(), nullable=True))
    op.execute(
        """
        UPDATE mowa_mes_archivo AS a
        SET nombre = 'mowa_mes_campana_' || a.campana_id::text || '_' || a.numero::text
            || '_de_'
            || (SELECT count(*) FROM mowa_mes_archivo AS b WHERE b.campana_id = a.campana_id)::text
            || '.xlsx'
        """
    )
    op.alter_column("mowa_mes_archivo", "nombre", nullable=False)
    op.create_check_constraint(
        op.f("ck_mowa_mes_archivo_nombre_no_vacio"),
        "mowa_mes_archivo",
        "length(btrim(nombre)) > 0",
    )
    op.create_unique_constraint(
        op.f("uq_mowa_mes_archivo_campana_id_nombre"), "mowa_mes_archivo", ["campana_id", "nombre"]
    )


def downgrade() -> None:
    """Quita lo agregado; la tarifa, el costo y los nombres guardados se pierden."""
    op.drop_constraint(
        op.f("uq_mowa_mes_archivo_campana_id_nombre"), "mowa_mes_archivo", type_="unique"
    )
    op.drop_constraint(
        op.f("ck_mowa_mes_archivo_nombre_no_vacio"), "mowa_mes_archivo", type_="check"
    )
    op.drop_column("mowa_mes_archivo", "nombre")

    op.drop_constraint(
        op.f("ck_mowa_mes_campana_costo_con_tarifa"), "mowa_mes_campana", type_="check"
    )
    op.drop_constraint(
        op.f("ck_mowa_mes_campana_tarifa_no_negativa"), "mowa_mes_campana", type_="check"
    )
    op.drop_constraint(
        op.f("ck_mowa_mes_campana_enviados_conciliados_validos"),
        "mowa_mes_campana",
        type_="check",
    )
    op.drop_column("mowa_mes_campana", "enviados_conciliados")
    op.drop_column("mowa_mes_campana", "costo_estimado")
    op.drop_column("mowa_mes_campana", "tarifa_sms")

    op.drop_constraint(
        op.f("ck_mowa_mes_configuracion_plantilla_no_vacia"),
        "mowa_mes_configuracion",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_mowa_mes_configuracion_tarifa_no_negativa"),
        "mowa_mes_configuracion",
        type_="check",
    )
    op.drop_column("mowa_mes_configuracion", "plantilla_nombre_archivo")
    op.drop_column("mowa_mes_configuracion", "tarifa_sms")

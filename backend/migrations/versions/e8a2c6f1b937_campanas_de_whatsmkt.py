"""campanas de WhatsMKT: lote, campana, archivo, filas cargadas y exclusiones

Revision ID: e8a2c6f1b937
Revises: d3f7a1b9c524
Create Date: 2026-11-03 16:00:00.000000

T-WM-B4b1, parte 2 (RF-WM-05 a 08, 16, 22, 23, 33 a 36). Cada tabla nace con sus claves foraneas
reales, sin columnas «para despues»:

- `whatsmkt_lote`: el lote que se crea de una vez (todas las campanas o ninguna). Es una TABLA y no
  un `lote_id` suelto porque las exclusiones de los productos que quedan fuera de todas las
  campanas cuelgan del lote (con `campana_id` nulo) y necesitan algo a lo que apuntar.
- `whatsmkt_campana`: la campana con todo lo que uso, CONGELADO: la version de la definicion, el
  texto guardado con su version y una copia del texto, la fecha de envio, los horarios con sus
  horas, el tipo de envio, la foto, el adjunto, los supervisores, la seleccion y las cifras.
- `whatsmkt_archivo`: el .xlsx tal como se genero (la descarga da siempre los mismos bytes).
- `whatsmkt_fila_cargada`: las filas del archivo, con las macros en JSONB (`none_as_null` y un
  CHECK de lista), que es lo que concilia el informe.
- `whatsmkt_exclusion`: los productos excluidos, cada uno con su unico codigo.

Sin siembra. Los nombres de las restricciones miden 63 caracteres o menos (los vigila una prueba
sobre toda la metadata `whatsmkt_*`). Escrita a mano; los nombres van con `op.f(...)`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e8a2c6f1b937"
down_revision: str | Sequence[str] | None = "d3f7a1b9c524"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TELEFONO = "'^9[0-9]{8}$'"
JSONB = postgresql.JSONB(none_as_null=True, astext_type=sa.Text())
AHORA = sa.text("now()")


def upgrade() -> None:
    """Crea las cinco tablas."""
    op.create_table(
        "whatsmkt_lote",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("modo", sa.String(length=16), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=AHORA, nullable=False),
        sa.CheckConstraint(
            "modo IN ('global', 'por_segmento')", name=op.f("ck_whatsmkt_lote_modo_valido")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_whatsmkt_lote")),
    )
    op.create_table(
        "whatsmkt_campana",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("lote_id", sa.BigInteger(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("segmento", sa.String(length=40), nullable=True),
        sa.Column("segmento_etiqueta", sa.Text(), nullable=True),
        sa.Column("definicion_id", sa.BigInteger(), nullable=True),
        sa.Column("definicion_nombre", sa.Text(), nullable=False),
        sa.Column("definicion_version", sa.Integer(), nullable=False),
        sa.Column("texto_guardado_id", sa.BigInteger(), nullable=True),
        sa.Column("texto_version", sa.Integer(), nullable=False),
        sa.Column("mensaje_texto", sa.Text(), nullable=False),
        sa.Column("whatsapp_contacto", sa.String(length=9), nullable=True),
        sa.Column("fecha_corte", sa.Date(), nullable=False),
        sa.Column("filtros", JSONB, nullable=False),
        sa.Column("orden", sa.Text(), nullable=True),
        sa.Column("cantidad_pedida", sa.Integer(), nullable=False),
        sa.Column("fecha_envio", sa.Date(), nullable=False),
        sa.Column("horarios", JSONB, nullable=False),
        sa.Column("lo_antes_posible", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("tipo_envio", sa.String(length=16), nullable=False),
        sa.Column("foto_id", sa.BigInteger(), nullable=True),
        sa.Column("adjunto_id", sa.BigInteger(), nullable=True),
        sa.Column("etiqueta_vcard", sa.Text(), nullable=True),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("productos", sa.Integer(), nullable=False),
        sa.Column("supervisores", JSONB, nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=AHORA, nullable=False),
        sa.Column("descartada_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "length(btrim(nombre)) BETWEEN 1 AND 75", name=op.f("ck_whatsmkt_campana_nombre_valido")
        ),
        sa.CheckConstraint(
            "tipo_envio IN ('solo_texto', 'archivo', 'vcard')",
            name=op.f("ck_whatsmkt_campana_tipo_envio_valido"),
        ),
        sa.CheckConstraint(
            "(tipo_envio = 'archivo') = (adjunto_id IS NOT NULL)",
            name=op.f("ck_whatsmkt_campana_adjunto_segun_tipo"),
        ),
        sa.CheckConstraint(
            "(tipo_envio = 'vcard') = (etiqueta_vcard IS NOT NULL)",
            name=op.f("ck_whatsmkt_campana_vcard_segun_tipo"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(filtros) = 'array'", name=op.f("ck_whatsmkt_campana_filtros_es_una_lista")
        ),
        sa.CheckConstraint(
            "jsonb_typeof(horarios) = 'array' AND jsonb_array_length(horarios) >= 1",
            name=op.f("ck_whatsmkt_campana_horarios_con_al_menos_uno"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(supervisores) = 'array'",
            name=op.f("ck_whatsmkt_campana_supervisores_es_una_lista"),
        ),
        sa.CheckConstraint(
            "cantidad = productos + jsonb_array_length(supervisores)",
            name=op.f("ck_whatsmkt_campana_cantidad_es_la_suma"),
        ),
        sa.CheckConstraint(
            "fecha_envio >= fecha_corte",
            name=op.f("ck_whatsmkt_campana_envio_no_anterior_al_corte"),
        ),
        sa.CheckConstraint(
            "definicion_version >= 1 AND texto_version >= 1",
            name=op.f("ck_whatsmkt_campana_versiones_validas"),
        ),
        sa.CheckConstraint(
            f"whatsapp_contacto IS NULL OR whatsapp_contacto ~ {TELEFONO}",
            name=op.f("ck_whatsmkt_campana_whatsapp_valido"),
        ),
        sa.ForeignKeyConstraint(
            ["lote_id"],
            ["whatsmkt_lote.id"],
            name=op.f("fk_whatsmkt_campana_lote_id_whatsmkt_lote"),
        ),
        sa.ForeignKeyConstraint(
            ["definicion_id"],
            ["definicion_carga.id"],
            name=op.f("fk_whatsmkt_campana_definicion_id_definicion_carga"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["texto_guardado_id"],
            ["texto_guardado.id"],
            name=op.f("fk_whatsmkt_campana_texto_guardado_id_texto_guardado"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["foto_id"],
            ["whatsmkt_adjunto.id"],
            name=op.f("fk_whatsmkt_campana_foto_id_whatsmkt_adjunto"),
        ),
        sa.ForeignKeyConstraint(
            ["adjunto_id"],
            ["whatsmkt_adjunto.id"],
            name=op.f("fk_whatsmkt_campana_adjunto_id_whatsmkt_adjunto"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_whatsmkt_campana")),
    )
    op.create_index(op.f("ix_whatsmkt_campana_lote_id"), "whatsmkt_campana", ["lote_id"])
    op.create_index(op.f("ix_whatsmkt_campana_fecha_envio"), "whatsmkt_campana", ["fecha_envio"])
    op.create_table(
        "whatsmkt_archivo",
        sa.Column("campana_id", sa.BigInteger(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("contenido", sa.LargeBinary(), nullable=False),
        sa.Column("tamano", sa.Integer(), nullable=False),
        sa.Column("filas", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "tamano >= 0 AND filas >= 0", name=op.f("ck_whatsmkt_archivo_cifras_validas")
        ),
        sa.ForeignKeyConstraint(
            ["campana_id"],
            ["whatsmkt_campana.id"],
            name=op.f("fk_whatsmkt_archivo_campana_id_whatsmkt_campana"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("campana_id", name=op.f("pk_whatsmkt_archivo")),
    )
    op.create_table(
        "whatsmkt_fila_cargada",
        sa.Column("campana_id", sa.BigInteger(), nullable=False),
        sa.Column("posicion", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("numero", sa.Text(), nullable=False),
        sa.Column("pagare", sa.Text(), nullable=True),
        sa.Column("supervision", sa.Boolean(), nullable=False),
        sa.Column("macros", JSONB, nullable=False),
        sa.CheckConstraint(
            "posicion >= 1", name=op.f("ck_whatsmkt_fila_cargada_posicion_positiva")
        ),
        sa.CheckConstraint(
            "supervision = (pagare IS NULL)",
            name=op.f("ck_whatsmkt_fila_cargada_pagare_segun_supervision"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(macros) = 'array'",
            name=op.f("ck_whatsmkt_fila_cargada_macros_es_una_lista"),
        ),
        sa.ForeignKeyConstraint(
            ["campana_id"],
            ["whatsmkt_campana.id"],
            name=op.f("fk_whatsmkt_fila_cargada_campana_id_whatsmkt_campana"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("campana_id", "posicion", name=op.f("pk_whatsmkt_fila_cargada")),
    )
    op.create_table(
        "whatsmkt_exclusion",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("lote_id", sa.BigInteger(), nullable=False),
        sa.Column("campana_id", sa.BigInteger(), nullable=True),
        sa.Column("fila", sa.Integer(), nullable=False),
        sa.Column("pagare", sa.Text(), nullable=True),
        sa.Column("codigo", sa.String(length=40), nullable=False),
        sa.Column("detalle", sa.Text(), nullable=False),
        sa.Column("macro", sa.Integer(), nullable=True),
        sa.Column("etiqueta", sa.Text(), nullable=True),
        sa.CheckConstraint("fila >= 1", name=op.f("ck_whatsmkt_exclusion_fila_positiva")),
        sa.ForeignKeyConstraint(
            ["lote_id"],
            ["whatsmkt_lote.id"],
            name=op.f("fk_whatsmkt_exclusion_lote_id_whatsmkt_lote"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["campana_id"],
            ["whatsmkt_campana.id"],
            name=op.f("fk_whatsmkt_exclusion_campana_id_whatsmkt_campana"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_whatsmkt_exclusion")),
    )
    op.create_index(op.f("ix_whatsmkt_exclusion_lote_id"), "whatsmkt_exclusion", ["lote_id"])
    op.create_index(op.f("ix_whatsmkt_exclusion_campana_id"), "whatsmkt_exclusion", ["campana_id"])


def downgrade() -> None:
    """Quita las cinco tablas, de las hijas a las madres."""
    op.drop_index(op.f("ix_whatsmkt_exclusion_campana_id"), table_name="whatsmkt_exclusion")
    op.drop_index(op.f("ix_whatsmkt_exclusion_lote_id"), table_name="whatsmkt_exclusion")
    op.drop_table("whatsmkt_exclusion")
    op.drop_table("whatsmkt_fila_cargada")
    op.drop_table("whatsmkt_archivo")
    op.drop_index(op.f("ix_whatsmkt_campana_fecha_envio"), table_name="whatsmkt_campana")
    op.drop_index(op.f("ix_whatsmkt_campana_lote_id"), table_name="whatsmkt_campana")
    op.drop_table("whatsmkt_campana")
    op.drop_table("whatsmkt_lote")

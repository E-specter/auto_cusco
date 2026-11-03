"""mensaje de WhatsMKT: WhatsApp de contacto y mensaje de cada segmento

Revision ID: d3f7a1b9c524
Revises: c9e5a1d7b384
Create Date: 2026-11-03 10:00:00.000000

T-WM-B3 (RF-WM-19 a RF-WM-21, DU-WM-11):

- `whatsmkt_configuracion.whatsapp_contacto`: nulo, 9 digitos que empiezan con 9 (RF-02). Es el
  numero que reemplaza a `[whatsapp]` en el mensaje. No se siembra: el numero real no puede estar
  en el repositorio.
- `whatsmkt_segmento.texto_guardado_id`: el mensaje del segmento, FK nula a `texto_guardado` con
  ON DELETE SET NULL. Es el texto, no la version: la campana congela la version al crearse (B4b).
- Siembra, en el contexto `whatsmkt.mensaje`, de los tres mensajes de RF-WM-21 como version 1,
  TEXTUALES (con sus espacios dobles y los espacios antes de una coma: DU-WM-2), con `[whatsapp]`
  donde el speech original trae el enlace. Cada segmento queda apuntando al suyo.

Los textos se copian aqui a proposito: una migracion no importa codigo de la aplicacion.
`tests/test_whatsmkt_mensaje_migracion.py` comprueba que coincidan con RF-WM-21. La siembra va en
SQL puro (cuerpos con `$wm$`) para que `alembic upgrade --sql` tambien la muestre.

Escrita a mano; los nombres de las restricciones van con `op.f(...)`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3f7a1b9c524"
down_revision: str | Sequence[str] | None = "c9e5a1d7b384"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONTEXTO = "whatsmkt.mensaje"
CK_WHATSAPP = "ck_whatsmkt_configuracion_whatsapp_valido"
FK_TEXTO = "fk_whatsmkt_segmento_texto"

# (clave del segmento, nombre del texto, texto de la version 1)
MENSAJES = (
    (
        "preventivo",
        "Preventivo",
        "Hola [$MACRO1$] Caja Cusco te informa que tu cuota vence  el [$MACRO2$] , pague puntualmente en nuestras agencias, agentes  KASNET o a través de Wayki app. Si ya pagaste, omite este mensaje. INFO por [whatsapp]",  # noqa: E501
    ),
    (
        "tramo_2",
        "Tramo 2",
        "Hola [$MACRO1$] Caja Cusco te informa que tu cuota venció el [$MACRO2$] , ponte al día, te invitamos a pagar en nuestras agencias, agentes KASNET o a través de Wayki app. Si ya pagaste, omite este mensaje. INFO por [whatsapp]",  # noqa: E501
    ),
    (
        "mayores_2",
        "Tramos mayores al 2",
        "Hola [$MACRO1$] Caja Cusco te informa que tu cuota venció el [$MACRO2$] , evita estar mal calificado en el sistema financiero, el monto de tu cuota es [$MACRO3$] , acércate a pagar a nuestras agencias , agentes KASNET y/o canales alternativos. INFO por [whatsapp]",  # noqa: E501
    ),
)


def _literal(texto: str) -> str:
    """Un texto como literal de PostgreSQL entre dolares: sin escapes, tal cual."""
    assert "$wm$" not in texto
    return f"$wm${texto}$wm$"


def _sembrar(clave: str, nombre: str, texto: str) -> str:
    return (
        "WITH t AS ("
        "INSERT INTO texto_guardado (contexto, nombre, nombre_normalizado) "
        f"VALUES ({_literal(CONTEXTO)}, {_literal(nombre)}, {_literal(nombre.casefold())}) "
        "RETURNING id), "
        "v AS ("
        "INSERT INTO texto_guardado_version (texto_id, numero, contenido) "
        f"SELECT id, 1, jsonb_build_object('texto', {_literal(texto)}) FROM t) "
        f"UPDATE whatsmkt_segmento SET texto_guardado_id = (SELECT id FROM t) "
        f"WHERE clave = {_literal(clave)}"
    )


def upgrade() -> None:
    """Agrega el WhatsApp y el mensaje del segmento, y siembra los tres mensajes."""
    op.add_column(
        "whatsmkt_configuracion",
        sa.Column("whatsapp_contacto", sa.String(length=9), nullable=True),
    )
    op.create_check_constraint(
        op.f(CK_WHATSAPP),
        "whatsmkt_configuracion",
        "whatsapp_contacto IS NULL OR whatsapp_contacto ~ '^9[0-9]{8}$'",
    )
    op.add_column(
        "whatsmkt_segmento", sa.Column("texto_guardado_id", sa.BigInteger(), nullable=True)
    )
    op.create_foreign_key(
        op.f(FK_TEXTO),
        "whatsmkt_segmento",
        "texto_guardado",
        ["texto_guardado_id"],
        ["id"],
        ondelete="SET NULL",
    )
    for clave, nombre, texto in MENSAJES:
        op.execute(_sembrar(clave, nombre, texto))


def downgrade() -> None:
    """Quita los tres mensajes sembrados (con sus versiones) y las dos columnas."""
    nombres = ", ".join(_literal(nombre.casefold()) for _, nombre, _ in MENSAJES)
    op.execute(
        f"DELETE FROM texto_guardado WHERE contexto = {_literal(CONTEXTO)} "
        f"AND nombre_normalizado IN ({nombres})"
    )
    op.drop_constraint(op.f(FK_TEXTO), "whatsmkt_segmento", type_="foreignkey")
    op.drop_column("whatsmkt_segmento", "texto_guardado_id")
    op.drop_constraint(op.f(CK_WHATSAPP), "whatsmkt_configuracion", type_="check")
    op.drop_column("whatsmkt_configuracion", "whatsapp_contacto")

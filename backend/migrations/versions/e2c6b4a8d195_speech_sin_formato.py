"""las versiones de speech de MOWA MES pierden el formato: `partes` pasa a `texto_v1`

Revision ID: e2c6b4a8d195
Revises: d7a3e5b9c241
Create Date: 2026-11-02 09:00:00.000000

T-MM-C11, M-B4 (RF-MM-17): ya no queda ninguna version de dos partes (la migracion anterior las
paso todas a v2), asi que `formato` no distingue nada. Esta migracion:

- renombra `partes` a `texto_v1` y lo deja nulable. Las v2 nativas (`partes = '[]'`) pasan a NULL;
  las convertidas conservan su texto v1 tal cual, para trazabilidad y para el downgrade. Nada de
  la aplicacion lo lee;
- quita la columna `formato` y sus dos CHECK (`formato_valido` y `contenido_segun_formato`);
- deja `expresiones` NOT NULL, que es lo que `contenido_segun_formato` exigia, y le agrega el CHECK
  `expresiones_es_una_lista` (`jsonb_typeof(expresiones) = 'array'`): NOT NULL no basta, porque el
  JSON `null` no es NULL de SQL y pasa; el CHECK lo rechaza tambien por SQL directo.

Downgrade exacto: deja la tabla como la dejo `d7a3e5b9c241`. Primero quita el CHECK nuevo;
`expresiones` vuelve a ser nulable;
`formato` vuelve como `String(2) NOT NULL DEFAULT 'v2'` (todas las filas quedan en `v2`, como
estaban); vuelven los dos CHECK con su texto y sus nombres de entonces; `texto_v1` NULL vuelve a
`'[]'`, con `NOT NULL`, y se llama `partes` otra vez. Solo cambia el orden fisico de las columnas
(`formato` queda al final), que ninguna consulta usa.

Los nombres de los CHECK van con `op.f(...)`: ya traen el prefijo de la convencion de nombres y
Alembic lo duplicaria. Escrita a mano, como `f2c8a4d7b915` y `d7a3e5b9c241`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2c6b4a8d195"
down_revision: str | Sequence[str] | None = "d7a3e5b9c241"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLA = "mowa_mes_speech_version"
CK_FORMATO = "ck_mowa_mes_speech_version_formato_valido"
CK_CONTENIDO = "ck_mowa_mes_speech_version_contenido_segun_formato"
CK_FORMATO_TEXTO = "formato IN ('v1', 'v2')"
CK_CONTENIDO_TEXTO = "formato = 'v2' AND expresiones IS NOT NULL"
CK_LISTA = "ck_mowa_mes_speech_version_expresiones_es_una_lista"
CK_LISTA_TEXTO = "jsonb_typeof(expresiones) = 'array'"


def upgrade() -> None:
    op.drop_constraint(op.f(CK_CONTENIDO), TABLA, type_="check")
    op.drop_constraint(op.f(CK_FORMATO), TABLA, type_="check")
    op.alter_column(TABLA, "partes", new_column_name="texto_v1", nullable=True)
    op.execute(
        sa.text("UPDATE mowa_mes_speech_version SET texto_v1 = NULL WHERE texto_v1 = '[]'::jsonb")
    )
    op.drop_column(TABLA, "formato")
    op.alter_column(TABLA, "expresiones", nullable=False)
    op.create_check_constraint(op.f(CK_LISTA), TABLA, CK_LISTA_TEXTO)


def downgrade() -> None:
    op.drop_constraint(op.f(CK_LISTA), TABLA, type_="check")
    op.alter_column(TABLA, "expresiones", nullable=True)
    op.add_column(
        TABLA, sa.Column("formato", sa.String(length=2), server_default="v2", nullable=False)
    )
    op.create_check_constraint(op.f(CK_FORMATO), TABLA, CK_FORMATO_TEXTO)
    op.create_check_constraint(op.f(CK_CONTENIDO), TABLA, CK_CONTENIDO_TEXTO)
    op.execute(
        sa.text("UPDATE mowa_mes_speech_version SET texto_v1 = '[]'::jsonb WHERE texto_v1 IS NULL")
    )
    op.alter_column(TABLA, "texto_v1", new_column_name="partes", nullable=False)

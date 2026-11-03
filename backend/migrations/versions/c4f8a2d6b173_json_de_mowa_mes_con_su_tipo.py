"""las JSONB NOT NULL de MOWA MES exigen su tipo JSON

Revision ID: c4f8a2d6b173
Revises: a6c3e8d1f259
Create Date: 2026-11-03 09:00:00.000000

T-MM-B14: NOT NULL no basta en una columna JSONB, porque el JSON `null` no es NULL de SQL y pasa.
Un CHECK `jsonb_typeof(col) = '<tipo>'` por columna lo cierra, tambien por SQL directo (como
`expresiones_es_una_lista` de `e2c6b4a8d195`):

- `mowa_mes_campana.filtros`, `.envios` y `.supervisores`: `array`;
- `mowa_mes_campana.herramientas`: `object`;
- `mowa_mes_fila_cargada.advertencias`: `array`.

El modelo les pone ademas `JSONB(none_as_null=True)`: un `None` de Python viaja como NULL de SQL y
la base lo rechaza por NOT NULL. No se reescribe ningun dato: si alguna fila trae otro tipo, el
`upgrade` falla al crear el CHECK y hay que decidir antes que hacer con ella. El `downgrade` quita
los CHECK.

Los nombres van con `op.f(...)`: ya traen el prefijo de la convencion de nombres y Alembic lo
duplicaria. Escrita a mano, como `e2c6b4a8d195`.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4f8a2d6b173"
down_revision: str | Sequence[str] | None = "a6c3e8d1f259"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (tabla, columna, tipo de JSON, nombre completo del CHECK; todos de 63 caracteres o menos)
CHECKS = (
    ("mowa_mes_campana", "filtros", "array", "ck_mowa_mes_campana_filtros_es_una_lista"),
    ("mowa_mes_campana", "herramientas", "object", "ck_mowa_mes_campana_herramientas_es_un_objeto"),
    ("mowa_mes_campana", "envios", "array", "ck_mowa_mes_campana_envios_es_una_lista"),
    ("mowa_mes_campana", "supervisores", "array", "ck_mowa_mes_campana_supervisores_es_una_lista"),
    (
        "mowa_mes_fila_cargada",
        "advertencias",
        "array",
        "ck_mowa_mes_fila_cargada_advertencias_es_una_lista",
    ),
)


def upgrade() -> None:
    for tabla, columna, tipo, nombre in CHECKS:
        op.create_check_constraint(op.f(nombre), tabla, f"jsonb_typeof({columna}) = '{tipo}'")


def downgrade() -> None:
    for tabla, _, _, nombre in reversed(CHECKS):
        op.drop_constraint(op.f(nombre), tabla, type_="check")

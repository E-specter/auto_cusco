"""las versiones de speech de MOWA MES quedan todas en v2

Revision ID: d7a3e5b9c241
Revises: c5d9f2a8e714
Create Date: 2026-10-31 10:00:00.000000

T-MM-C11, M-B3 (RF-MM-17 modificado: solo v2). Cada version `v1` pasa a `v2` en su lugar: su
`expresiones` sale de sus dos partes, con el mismo mensaje que daba, y su `formato` pasa a `v2`.
Se conservan `id`, `nombre`, `nombre_normalizado`, `usada_en`, `basada_en_id`, `original`,
`creado_en` y `deshabilitada_en`: las campanas que usaron una version siguen apuntando a ella.
`partes` NO se toca: queda el texto v1, para trazabilidad y para el downgrade. Despues, el CHECK
`contenido_segun_formato` exige `formato = 'v2' AND expresiones IS NOT NULL` y el `formato` por
defecto de una fila nueva pasa a `v2`.

No importa nada de `app`: esta migracion tiene que dar lo mismo aunque el codigo cambie. Lleva dos
copias congeladas de la conversion, que una prueba compara contra `speech.convertir_a_v2` de la
aplicacion (200 juegos de partes sinteticos y el original):

- `_convertir(partes)`: lo que hace `expresion_de` mas `expresion_a_dict`. El titular lleva
  `primeros(8)` y es obligatorio; la parte 1, con cada `[whatsapp]` como `whatsapp_contacto |
  enlace_whatsapp`; la fecha con `formato_fecha("dd/mm/aaaa")`, obligatoria; y la parte 2.
- `EXPRESIONES_ORIGINAL`: el literal del Speech original convertido. Una base reconstruida desde
  cero siembra el original como v1 (migracion `a4c8e2f6b913`) y esta migracion lo convierte siempre
  igual, venga de donde venga su `partes`.

Downgrade exacto: las filas con `partes` no vacio eran v1 y vuelven a `formato = 'v1'` con
`expresiones = NULL`; las v2 nativas (`partes = []`) no se tocan. Una version convertida y despues
editada tiene `partes = []`, asi que se queda como v2: ya no es la v1 de antes.

Con `--sql` (modo offline) solo emite el DDL: la conversion de filas necesita la base. Escrita a
mano, como `f2c8a4d7b915`.
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision: str = "d7a3e5b9c241"
down_revision: str | Sequence[str] | None = "c5d9f2a8e714"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLA = "mowa_mes_speech_version"
CHECK = "ck_mowa_mes_speech_version_contenido_segun_formato"
CHECK_ANTERIOR = (
    "(formato = 'v1' AND expresiones IS NULL) OR (formato = 'v2' AND expresiones IS NOT NULL)"
)
CHECK_NUEVO = "formato = 'v2' AND expresiones IS NOT NULL"

MARCA_WHATSAPP = "[whatsapp]"

# El Speech original ya convertido (RF-MM-18 mas la conversion de arriba). Igual a
# `_convertir(SPEECH_ORIGINAL)` de a4c8e2f6b913: una prueba lo comprueba.
EXPRESIONES_ORIGINAL = [
    {
        "segmento": "preventiva",
        "expresion": {
            "nodos": [
                {
                    "tipo": "variable",
                    "nombre": "titular",
                    "funciones": [{"nombre": "primeros", "args": [8]}],
                    "obligatoria": True,
                },
                {"tipo": "texto", "valor": " Caja Cusco te recuerda que tu cuota Vence el "},
                {
                    "tipo": "variable",
                    "nombre": "fecha_vencimiento_cuota",
                    "funciones": [{"nombre": "formato_fecha", "args": ["dd/mm/aaaa"]}],
                    "obligatoria": True,
                },
                {"tipo": "texto", "valor": ". Si ya pagaste, omite este mensaje."},
            ]
        },
    },
    {
        "segmento": "1_a_8",
        "expresion": {
            "nodos": [
                {
                    "tipo": "variable",
                    "nombre": "titular",
                    "funciones": [{"nombre": "primeros", "args": [8]}],
                    "obligatoria": True,
                },
                {"tipo": "texto", "valor": " Caja Cusco te informa que tu cuota venció el "},
                {
                    "tipo": "variable",
                    "nombre": "fecha_vencimiento_cuota",
                    "funciones": [{"nombre": "formato_fecha", "args": ["dd/mm/aaaa"]}],
                    "obligatoria": True,
                },
                {
                    "tipo": "texto",
                    "valor": ", acércate a pagar a nuestras agencias, agentes KASNET o "
                    "a través de Wayki app.",
                },
            ]
        },
    },
    {
        "segmento": "9_a_30",
        "expresion": {
            "nodos": [
                {
                    "tipo": "variable",
                    "nombre": "titular",
                    "funciones": [{"nombre": "primeros", "args": [8]}],
                    "obligatoria": True,
                },
                {"tipo": "texto", "valor": " Caja Cusco te informa que tu cuota venció el "},
                {
                    "tipo": "variable",
                    "nombre": "fecha_vencimiento_cuota",
                    "funciones": [{"nombre": "formato_fecha", "args": ["dd/mm/aaaa"]}],
                    "obligatoria": True,
                },
                {
                    "tipo": "texto",
                    "valor": ", evita estar mal calificado, acércate a pagar a nuestras "
                    "agencias y/o canales alternativos.",
                },
            ]
        },
    },
    {
        "segmento": "31_a_60",
        "expresion": {
            "nodos": [
                {
                    "tipo": "variable",
                    "nombre": "titular",
                    "funciones": [{"nombre": "primeros", "args": [8]}],
                    "obligatoria": True,
                },
                {"tipo": "texto", "valor": " Caja Cusco te informa que tu cuota venció el "},
                {
                    "tipo": "variable",
                    "nombre": "fecha_vencimiento_cuota",
                    "funciones": [{"nombre": "formato_fecha", "args": ["dd/mm/aaaa"]}],
                    "obligatoria": True,
                },
                {
                    "tipo": "texto",
                    "valor": ", ponte al día y participa del sorteo de 06 autos. INFO por ",
                },
                {
                    "tipo": "variable",
                    "nombre": "whatsapp_contacto",
                    "funciones": [{"nombre": "enlace_whatsapp", "args": []}],
                    "obligatoria": False,
                },
            ]
        },
    },
    {
        "segmento": "61_a_90",
        "expresion": {
            "nodos": [
                {
                    "tipo": "variable",
                    "nombre": "titular",
                    "funciones": [{"nombre": "primeros", "args": [8]}],
                    "obligatoria": True,
                },
                {"tipo": "texto", "valor": " cancela tu deuda CAJA CUSCO vencida el "},
                {
                    "tipo": "variable",
                    "nombre": "fecha_vencimiento_cuota",
                    "funciones": [{"nombre": "formato_fecha", "args": ["dd/mm/aaaa"]}],
                    "obligatoria": True,
                },
                {
                    "tipo": "texto",
                    "valor": ", pague a tiempo y evite estar mal calificado. Más INFO por ",
                },
                {
                    "tipo": "variable",
                    "nombre": "whatsapp_contacto",
                    "funciones": [{"nombre": "enlace_whatsapp", "args": []}],
                    "obligatoria": False,
                },
            ]
        },
    },
    {
        "segmento": "91_a_120",
        "expresion": {
            "nodos": [
                {
                    "tipo": "variable",
                    "nombre": "titular",
                    "funciones": [{"nombre": "primeros", "args": [8]}],
                    "obligatoria": True,
                },
                {"tipo": "texto", "valor": " cancela tu deuda CAJA CUSCO vencida el "},
                {
                    "tipo": "variable",
                    "nombre": "fecha_vencimiento_cuota",
                    "funciones": [{"nombre": "formato_fecha", "args": ["dd/mm/aaaa"]}],
                    "obligatoria": True,
                },
                {
                    "tipo": "texto",
                    "valor": ", pague a tiempo y evite estar mal calificado. Más INFO por ",
                },
                {
                    "tipo": "variable",
                    "nombre": "whatsapp_contacto",
                    "funciones": [{"nombre": "enlace_whatsapp", "args": []}],
                    "obligatoria": False,
                },
            ]
        },
    },
]


def _variable(nombre: str, funciones: list[dict[str, Any]], obligatoria: bool) -> dict[str, Any]:
    return {
        "tipo": "variable",
        "nombre": nombre,
        "funciones": funciones,
        "obligatoria": obligatoria,
    }


def _texto_y_enlaces(texto: str) -> list[dict[str, Any]]:
    """El texto de una parte, con cada `[whatsapp]` convertido en la variable del enlace."""
    nodos: list[dict[str, Any]] = []
    for posicion, trozo in enumerate(texto.split(MARCA_WHATSAPP)):
        if posicion:
            enlace = [{"nombre": "enlace_whatsapp", "args": []}]
            nodos.append(_variable("whatsapp_contacto", enlace, False))
        if trozo:
            nodos.append({"tipo": "texto", "valor": trozo})
    return nodos


def _convertir(partes: Sequence[dict[str, str]]) -> list[dict[str, Any]]:
    """Las expresiones de una v2 que dan el mismo mensaje que estas partes v1."""
    convertidas: list[dict[str, Any]] = []
    for p in partes:
        nodos = [
            _variable("titular", [{"nombre": "primeros", "args": [8]}], True),
            *_texto_y_enlaces(p["parte_1"]),
            _variable(
                "fecha_vencimiento_cuota",
                [{"nombre": "formato_fecha", "args": ["dd/mm/aaaa"]}],
                True,
            ),
            *_texto_y_enlaces(p["parte_2"]),
        ]
        convertidas.append({"segmento": p["segmento"], "expresion": {"nodos": nodos}})
    return convertidas


def _pasar_filas_a_v2(bind: Connection) -> None:
    """Cada v1 queda v2 con `expresiones`; `partes` y todo lo demas no se tocan."""
    filas = bind.execute(
        sa.text(
            "SELECT id, original, partes FROM mowa_mes_speech_version "
            "WHERE formato = 'v1' ORDER BY id"
        )
    ).all()
    convertir = sa.text(
        "UPDATE mowa_mes_speech_version SET formato = 'v2', expresiones = :expresiones "
        "WHERE id = :id"
    ).bindparams(sa.bindparam("expresiones", type_=postgresql.JSONB(none_as_null=True)))
    for fila in filas:
        expresiones = EXPRESIONES_ORIGINAL if fila.original else _convertir(fila.partes)
        bind.execute(convertir, {"id": fila.id, "expresiones": expresiones})


def _devolver_filas_a_v1(bind: Connection) -> None:
    """Las que tienen `partes` eran v1: vuelven a v1 sin `expresiones`. Las v2 nativas no."""
    bind.execute(
        sa.text(
            "UPDATE mowa_mes_speech_version SET formato = 'v1', expresiones = NULL "
            "WHERE formato = 'v2' AND partes <> CAST('[]' AS jsonb)"
        )
    )


def upgrade() -> None:
    if not context.is_offline_mode():
        _pasar_filas_a_v2(op.get_bind())
    op.drop_constraint(op.f(CHECK), TABLA, type_="check")
    op.create_check_constraint(op.f(CHECK), TABLA, CHECK_NUEVO)
    op.alter_column(TABLA, "formato", server_default="v2")


def downgrade() -> None:
    op.drop_constraint(op.f(CHECK), TABLA, type_="check")
    if not context.is_offline_mode():
        _devolver_filas_a_v1(op.get_bind())
    op.create_check_constraint(op.f(CHECK), TABLA, CHECK_ANTERIOR)
    op.alter_column(TABLA, "formato", server_default="v1")

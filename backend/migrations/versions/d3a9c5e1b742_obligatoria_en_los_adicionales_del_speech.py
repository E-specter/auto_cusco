"""los adicionales del speech de MOWA MES quedan marcados Obligatoria

Revision ID: d3a9c5e1b742
Revises: c4f8a2d6b173
Create Date: 2026-11-04 12:00:00.000000

T-HI-B7, parte 2 (D-CA-2, opcion a). Hasta ahora un campo adicional vacio que el speech leia
EXCLUIA el producto, marcado o no. Desde esta version el speech ofrece todos los campos de la
cartera y un campo vacio sigue la regla Obligatoria del motor (RF-45): solo excluye si el nodo esta
marcado. Para que lo de hoy quede igual, esta migracion de DATOS marca `obligatoria = true` en los
nodos de adicionales de los speeches ya guardados:

- solo los nodos `variable` cuyo nombre es un campo adicional del catalogo (`campo_adicional`,
  archivados incluidos), en TODAS las versiones de `mowa_mes_speech_version.expresiones`, no solo
  la vigente;
- un adicional usado como ARGUMENTO de una funcion no se marca: un argumento no tiene la marca y,
  si llega vacio, deja un hueco, asi que el speech lo sigue exigiendo siempre (no cambia nada);
- el titular, el vencimiento, el contacto y los dias ajustados no se tocan;
- idempotente: un nodo ya marcado no cambia y el resto del JSON del nodo (orden de claves y
  funciones) queda como estaba.

La logica de recorrer el JSON es de ESTA migracion (no importa codigo de la aplicacion: una
migracion no puede cambiar si cambia la app). Una prueba sin base cubre la transformacion.

Guardia. Antes de escribir nada, `upgrade` comprueba que ningun nodo de adicional este YA marcado:
la sintaxis de texto no permite marcar Obligatoria, asi que hoy no deberia haber ninguno. Si hay
alguno, `upgrade` se detiene con un error y no toca datos: el `downgrade` no sabria cuales marco
esta migracion y cuales ya venian marcados. Si pasa, hay que decidir antes que hacer con ellos.

Downgrade. Con la guardia cumplida, todo nodo de adicional marcado lo marco esta migracion, asi que
`downgrade` los devuelve a `obligatoria = false`. Si despues del upgrade alguien marco otros a mano
desde el editor, tambien vuelven a false: el downgrade vuelve al estado anterior, en que ninguno
estaba marcado. Es reversible y no cambia el esquema. No corre en modo offline (`--sql`): lee y
escribe filas.

Efecto sobre la huella: la huella de un speech sale de su JSON, asi que cambia al reescribirlo. Solo
se compara entre la previsualizacion y la creacion de una campana (las ya creadas guardan la suya y
nadie la recalcula): una previsualizacion abierta mientras se aplica esta migracion da
`SpeechCambiado` al crear, y basta con previsualizar de nuevo.

Para ver cuantos nodos va a cambiar ANTES de aplicarla (solo lectura, para architec):
`backend/scripts/contar_obligatorias_speech.sql`.
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision: str = "d3a9c5e1b742"
down_revision: str | Sequence[str] | None = "c4f8a2d6b173"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLA = "mowa_mes_speech_version"


class AdicionalYaMarcado(RuntimeError):
    """Un nodo de adicional ya tenia `obligatoria = true`: el downgrade no sabria que marco esta
    migracion. Se detiene sin tocar datos."""


def _nodos_de_adicionales(expresiones: Any, adicionales: set[str]) -> list[dict[str, Any]]:
    """Los nodos `variable` cuyo nombre es un adicional, de cada segmento de una version."""
    nodos: list[dict[str, Any]] = []
    for item in expresiones or ():
        for nodo in (item.get("expresion") or {}).get("nodos") or ():
            if nodo.get("tipo") == "variable" and nodo.get("nombre") in adicionales:
                nodos.append(nodo)
    return nodos


def marcar_obligatorios(expresiones: Any, adicionales: set[str]) -> int:
    """Marca `obligatoria = true` en los nodos de adicionales, en el lugar; devuelve cuantos
    cambio. Un nodo ya marcado no cuenta; la clave se asigna sin tocar el orden de las demas."""
    cambiados = 0
    for nodo in _nodos_de_adicionales(expresiones, adicionales):
        if nodo.get("obligatoria") is not True:
            nodo["obligatoria"] = True
            cambiados += 1
    return cambiados


def desmarcar_obligatorios(expresiones: Any, adicionales: set[str]) -> int:
    """Lo inverso: `obligatoria = false` en los nodos de adicionales marcados."""
    cambiados = 0
    for nodo in _nodos_de_adicionales(expresiones, adicionales):
        if nodo.get("obligatoria") is True:
            nodo["obligatoria"] = False
            cambiados += 1
    return cambiados


def hay_marcados(expresiones: Any, adicionales: set[str]) -> bool:
    return any(
        n.get("obligatoria") is True for n in _nodos_de_adicionales(expresiones, adicionales)
    )


def _adicionales(bind: Connection) -> set[str]:
    return {fila.nombre for fila in bind.execute(sa.text("SELECT nombre FROM campo_adicional"))}


def _filas(bind: Connection) -> list[Any]:
    return list(bind.execute(sa.text(f"SELECT id, expresiones FROM {TABLA} ORDER BY id")).all())


def _guardar(bind: Connection, id_: int, expresiones: Any) -> None:
    bind.execute(
        sa.text(f"UPDATE {TABLA} SET expresiones = :expresiones WHERE id = :id").bindparams(
            sa.bindparam("expresiones", type_=postgresql.JSONB(none_as_null=True))
        ),
        {"id": id_, "expresiones": expresiones},
    )


def upgrade() -> None:
    if context.is_offline_mode():
        return
    bind = op.get_bind()
    adicionales = _adicionales(bind)
    filas = [f for f in _filas(bind) if f.expresiones is not None]
    if any(hay_marcados(f.expresiones, adicionales) for f in filas):
        raise AdicionalYaMarcado(
            "Hay nodos de campos adicionales ya marcados Obligatoria en los speeches guardados: "
            "el downgrade no sabria cuales marco esta migracion. No se toco ningun dato."
        )
    for fila in filas:
        if marcar_obligatorios(fila.expresiones, adicionales):
            _guardar(bind, fila.id, fila.expresiones)


def downgrade() -> None:
    if context.is_offline_mode():
        return
    bind = op.get_bind()
    adicionales = _adicionales(bind)
    for fila in _filas(bind):
        if fila.expresiones is not None and desmarcar_obligatorios(fila.expresiones, adicionales):
            _guardar(bind, fila.id, fila.expresiones)

"""Textos guardados y sus versiones, sobre PostgreSQL (RF-69).

La unicidad del nombre dentro del contexto la impone la base sobre el nombre normalizado, y la de
(texto, numero) de version tambien: una version nueva toma el siguiente numero con la fila del texto
bloqueada, asi dos personas guardando a la vez no se pisan ni repiten numero. Eliminar bloquea la
fila y mira las versiones en la misma transaccion, para que una version que se marca como usada
justo ahora no se pierda.
"""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import Engine, and_, delete, func, insert, select, update
from sqlalchemy.engine import Row
from sqlalchemy.exc import IntegrityError

from app.adapters.persistence.modelos import TextoGuardado as TextoGuardadoModelo
from app.adapters.persistence.modelos import TextoGuardadoVersion
from app.core.entities.nombres import normalizar_nombre
from app.core.entities.textos_guardados import (
    NombreDeTextoRepetido,
    ResumenTexto,
    TextoConVersionesUsadas,
    TextoDeshabilitado,
    TextoGuardado,
    VersionTexto,
)
from app.core.ports.repositorio_textos_guardados_port import RepositorioTextosGuardadosPort

_TEXTO = TextoGuardadoModelo.__table__
_VERSION = TextoGuardadoVersion.__table__
_RESTRICCION_NOMBRE = "uq_texto_guardado_contexto_nombre_normalizado"


def _version(fila: Row) -> VersionTexto:
    return VersionTexto(
        numero=fila.numero,
        contenido=fila.contenido,
        usada_en=fila.usada_en,
        creado_en=fila.creado_en,
    )


def _texto(fila: Row, versiones: list[Row]) -> TextoGuardado:
    return TextoGuardado(
        id=fila.id,
        contexto=fila.contexto,
        nombre=fila.nombre,
        creado_en=fila.creado_en,
        actualizado_en=fila.actualizado_en,
        deshabilitado_en=fila.deshabilitado_en,
        versiones=tuple(_version(v) for v in versiones),
    )


def _es_nombre_repetido(exc: IntegrityError) -> bool:
    diagnostico = getattr(exc.orig, "diag", None)
    return getattr(diagnostico, "constraint_name", None) == _RESTRICCION_NOMBRE


class RepositorioTextosGuardadosPostgres(RepositorioTextosGuardadosPort):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def listar(self, contexto: str, incluir_deshabilitados: bool = False) -> list[ResumenTexto]:
        por_texto = (
            select(
                _VERSION.c.texto_id,
                func.max(_VERSION.c.numero).label("vigente"),
                func.count().label("cantidad"),
                func.bool_and(_VERSION.c.usada_en.is_(None)).label("eliminable"),
            )
            .group_by(_VERSION.c.texto_id)
            .subquery()
        )
        consulta = (
            select(
                _TEXTO.c.id,
                _TEXTO.c.contexto,
                _TEXTO.c.nombre,
                _TEXTO.c.actualizado_en,
                _TEXTO.c.deshabilitado_en,
                por_texto.c.vigente,
                por_texto.c.cantidad,
                por_texto.c.eliminable,
                _VERSION.c.usada_en.is_not(None).label("vigente_usada"),
            )
            .join(por_texto, por_texto.c.texto_id == _TEXTO.c.id)
            .join(
                _VERSION,
                and_(
                    _VERSION.c.texto_id == _TEXTO.c.id,
                    _VERSION.c.numero == por_texto.c.vigente,
                ),
            )
            .where(_TEXTO.c.contexto == contexto)
            .order_by(_TEXTO.c.nombre_normalizado, _TEXTO.c.id)
        )
        if not incluir_deshabilitados:
            consulta = consulta.where(_TEXTO.c.deshabilitado_en.is_(None))
        with self._engine.connect() as cx:
            return [
                ResumenTexto(
                    id=fila.id,
                    contexto=fila.contexto,
                    nombre=fila.nombre,
                    version_vigente=fila.vigente,
                    cantidad_versiones=fila.cantidad,
                    actualizado_en=fila.actualizado_en,
                    vigente_usada=fila.vigente_usada,
                    deshabilitado_en=fila.deshabilitado_en,
                    eliminable=fila.eliminable,
                )
                for fila in cx.execute(consulta).all()
            ]

    def obtener(self, texto_id: int) -> TextoGuardado | None:
        with self._engine.connect() as cx:
            texto = cx.execute(select(_TEXTO).where(_TEXTO.c.id == texto_id)).one_or_none()
            if texto is None:
                return None
            versiones = cx.execute(
                select(_VERSION).where(_VERSION.c.texto_id == texto_id).order_by(_VERSION.c.numero)
            ).all()
        return _texto(texto, list(versiones))

    def crear(self, contexto: str, nombre: str, contenido: Mapping[str, Any]) -> TextoGuardado:
        try:
            with self._engine.begin() as cx:
                texto = cx.execute(
                    insert(_TEXTO)
                    .values(
                        contexto=contexto,
                        nombre=nombre,
                        nombre_normalizado=normalizar_nombre(nombre),
                    )
                    .returning(*_TEXTO.c)
                ).one()
                version = cx.execute(
                    insert(_VERSION)
                    .values(texto_id=texto.id, numero=1, contenido=dict(contenido))
                    .returning(*_VERSION.c)
                ).one()
        except IntegrityError as exc:
            if _es_nombre_repetido(exc):
                raise NombreDeTextoRepetido(contexto, nombre) from exc
            raise
        return _texto(texto, [version])

    def agregar_version(self, texto_id: int, contenido: Mapping[str, Any]) -> VersionTexto | None:
        with self._engine.begin() as cx:
            # Bloquea el texto: dos versiones nuevas a la vez toman numeros distintos.
            texto = cx.execute(
                select(_TEXTO.c.deshabilitado_en).where(_TEXTO.c.id == texto_id).with_for_update()
            ).one_or_none()
            if texto is None:
                return None
            if texto.deshabilitado_en is not None:
                raise TextoDeshabilitado(texto_id)
            siguiente = cx.execute(
                select(func.coalesce(func.max(_VERSION.c.numero), 0) + 1).where(
                    _VERSION.c.texto_id == texto_id
                )
            ).scalar_one()
            fila = cx.execute(
                insert(_VERSION)
                .values(texto_id=texto_id, numero=siguiente, contenido=dict(contenido))
                .returning(*_VERSION.c)
            ).one()
            cx.execute(
                update(_TEXTO)
                .where(_TEXTO.c.id == texto_id)
                # clock_timestamp: la hora real del cambio, no la del inicio de la transaccion.
                .values(actualizado_en=func.clock_timestamp())
            )
        return _version(fila)

    def renombrar(self, texto_id: int, nombre: str) -> TextoGuardado | None:
        try:
            with self._engine.begin() as cx:
                actual = cx.execute(
                    select(_TEXTO.c.nombre, _TEXTO.c.contexto)
                    .where(_TEXTO.c.id == texto_id)
                    .with_for_update()
                ).one_or_none()
                if actual is None:
                    return None
                if actual.nombre != nombre:
                    cx.execute(
                        update(_TEXTO)
                        .where(_TEXTO.c.id == texto_id)
                        .values(
                            nombre=nombre,
                            nombre_normalizado=normalizar_nombre(nombre),
                            actualizado_en=func.clock_timestamp(),
                        )
                    )
        except IntegrityError as exc:
            if _es_nombre_repetido(exc):
                raise NombreDeTextoRepetido(actual.contexto, nombre) from exc
            raise
        return self.obtener(texto_id)

    def deshabilitar(self, texto_id: int) -> TextoGuardado | None:
        with self._engine.begin() as cx:
            cx.execute(
                update(_TEXTO)
                .where(_TEXTO.c.id == texto_id, _TEXTO.c.deshabilitado_en.is_(None))
                .values(
                    deshabilitado_en=func.clock_timestamp(),
                    actualizado_en=func.clock_timestamp(),
                )
            )
        return self.obtener(texto_id)

    def habilitar(self, texto_id: int) -> TextoGuardado | None:
        with self._engine.begin() as cx:
            cx.execute(
                update(_TEXTO)
                .where(_TEXTO.c.id == texto_id, _TEXTO.c.deshabilitado_en.is_not(None))
                .values(deshabilitado_en=None, actualizado_en=func.clock_timestamp())
            )
        return self.obtener(texto_id)

    def eliminar(self, texto_id: int) -> bool:
        with self._engine.begin() as cx:
            existe = cx.execute(
                select(_TEXTO.c.id).where(_TEXTO.c.id == texto_id).with_for_update()
            ).one_or_none()
            if existe is None:
                return False
            usada = cx.execute(
                select(_VERSION.c.id)
                .where(_VERSION.c.texto_id == texto_id, _VERSION.c.usada_en.is_not(None))
                .limit(1)
            ).one_or_none()
            if usada is not None:
                raise TextoConVersionesUsadas(texto_id)
            cx.execute(delete(_TEXTO).where(_TEXTO.c.id == texto_id))  # las versiones, en cascada
        return True

    def marcar_version_usada(self, texto_id: int, numero: int) -> bool:
        with self._engine.begin() as cx:
            # Bloquea el texto, como eliminar: una version no se marca justo mientras se borra.
            bloqueado = cx.execute(
                select(_TEXTO.c.id).where(_TEXTO.c.id == texto_id).with_for_update()
            ).one_or_none()
            if bloqueado is None:
                return False
            cx.execute(
                update(_VERSION)
                .where(
                    _VERSION.c.texto_id == texto_id,
                    _VERSION.c.numero == numero,
                    _VERSION.c.usada_en.is_(None),
                )
                .values(usada_en=func.clock_timestamp())
            )
            existe = cx.execute(
                select(_VERSION.c.id).where(
                    _VERSION.c.texto_id == texto_id, _VERSION.c.numero == numero
                )
            ).one_or_none()
        return existe is not None

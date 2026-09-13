"""Configuracion de supervision por defecto, sobre PostgreSQL.

Se reemplaza completa en una transaccion: nadie puede leer una lista de
supervisores a medio escribir ni un supervisor sin su procedencia.
"""

from sqlalchemy import Engine, delete, insert, select

from app.adapters.persistence.modelos import SupervisorDigital, SupervisorProcedencia
from app.core.entities.gestiones_digitales import ConfiguracionSupervision, Supervisor
from app.core.ports.repositorio_supervision_port import RepositorioSupervisionPort

_PROCEDENCIA = SupervisorProcedencia.__table__
_SUPERVISOR = SupervisorDigital.__table__


class RepositorioSupervisionPostgres(RepositorioSupervisionPort):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def obtener(self) -> ConfiguracionSupervision:
        with self._engine.connect() as cx:
            procedencias = cx.execute(
                select(_PROCEDENCIA.c.nombre).order_by(_PROCEDENCIA.c.posicion)
            ).scalars()
            procedencias = tuple(procedencias)
            supervisores = cx.execute(
                select(_SUPERVISOR.c.numero, _SUPERVISOR.c.procedencia).order_by(
                    _SUPERVISOR.c.posicion
                )
            ).all()
        return ConfiguracionSupervision(
            procedencias=procedencias,
            supervisores=tuple(Supervisor(fila.numero, fila.procedencia) for fila in supervisores),
        )

    def reemplazar(self, configuracion: ConfiguracionSupervision) -> ConfiguracionSupervision:
        with self._engine.begin() as cx:
            cx.execute(delete(_SUPERVISOR))
            cx.execute(delete(_PROCEDENCIA))
            if configuracion.procedencias:
                cx.execute(
                    insert(_PROCEDENCIA),
                    [
                        {"nombre": nombre, "posicion": posicion}
                        for posicion, nombre in enumerate(configuracion.procedencias)
                    ],
                )
            if configuracion.supervisores:
                cx.execute(
                    insert(_SUPERVISOR),
                    [
                        {"posicion": posicion, "numero": s.numero, "procedencia": s.procedencia}
                        for posicion, s in enumerate(configuracion.supervisores)
                    ],
                )
        return self.obtener()

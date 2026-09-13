"""Caso de uso: leer y reemplazar la configuracion de supervision por defecto (RF-38)."""

from app.core.entities.gestiones_digitales import ConfiguracionSupervision
from app.core.ports.repositorio_supervision_port import RepositorioSupervisionPort
from app.core.services.gestiones_digitales import supervision


class SupervisionService:
    def __init__(self, repositorio: RepositorioSupervisionPort) -> None:
        self._repositorio = repositorio

    def obtener(self) -> ConfiguracionSupervision:
        return self._repositorio.obtener()

    def reemplazar(self, configuracion: ConfiguracionSupervision) -> ConfiguracionSupervision:
        return self._repositorio.reemplazar(supervision.validar(configuracion))

"""Puerto de persistencia de la configuracion de supervision por defecto."""

from typing import Protocol

from app.core.entities.gestiones_digitales import ConfiguracionSupervision


class RepositorioSupervisionPort(Protocol):
    def obtener(self) -> ConfiguracionSupervision:
        """Procedencias y supervisores, cada lista en su orden guardado."""
        ...

    def reemplazar(self, configuracion: ConfiguracionSupervision) -> ConfiguracionSupervision:
        """Reemplaza las dos listas completas, de forma atomica."""
        ...

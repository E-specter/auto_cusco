"""Puerto de lectura de las definiciones de campos adicionales (T-CA-B1).

Por ahora solo se lee; crear, renombrar y archivar llegan con la persistencia (T-CA-B2).
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.core.entities.campos_adicionales import CampoAdicional


class RepositorioCamposAdicionalesPort(ABC):
    @abstractmethod
    def listar(self) -> Sequence[CampoAdicional]:
        """Todas las definiciones, archivadas incluidas, en el orden en que se crearon."""

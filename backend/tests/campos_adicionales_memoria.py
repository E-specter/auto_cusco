"""Un doble en memoria del puerto de campos adicionales y tres adicionales de prueba (T-CA-B1).

Datos sinteticos: un adicional de cada tipo y uno archivado.
"""

from collections.abc import Sequence

from app.core.entities.campos_adicionales import CampoAdicional, TipoAdicional
from app.core.ports.repositorio_campos_adicionales_port import RepositorioCamposAdicionalesPort
from app.core.services.seleccion_cartera.campos import CatalogoCartera

TEXTO = CampoAdicional("ad_zona_comercial", "Zona comercial", TipoAdicional.TEXTO, "zona comercial")
NUMERO = CampoAdicional("ad_monto_extra", "Monto extra", TipoAdicional.NUMERO, "monto extra")
FECHA = CampoAdicional("ad_fecha_visita", "Fecha de visita", TipoAdicional.FECHA, "fecha visita")
ARCHIVADO = CampoAdicional(
    "ad_antiguo", "Campo antiguo", TipoAdicional.NUMERO, "campo antiguo", archivado=True
)
TODOS = (TEXTO, NUMERO, FECHA, ARCHIVADO)


class CamposAdicionalesEnMemoria(RepositorioCamposAdicionalesPort):
    def __init__(self, campos: Sequence[CampoAdicional] = TODOS) -> None:
        self.campos = list(campos)

    def listar(self) -> Sequence[CampoAdicional]:
        return tuple(self.campos)


def catalogo_con(*campos: CampoAdicional) -> CatalogoCartera:
    return CatalogoCartera(CamposAdicionalesEnMemoria(campos or TODOS))

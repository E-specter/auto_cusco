"""La sabana como catalogo del mapeador (RF-63): sus campos y su criterio de vacio."""

from app.core.services.borradores_carga.servicio import CatalogoMapeable
from app.core.services.ingesta_sabana.catalogo import CATALOGO_SABANA
from app.core.services.ingesta_sabana.reglas import es_vacio

CATALOGO_SABANA_MAPEABLE = CatalogoMapeable(CATALOGO_SABANA, es_vacio)

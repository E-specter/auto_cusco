"""El nombre tecnico de un campo adicional (RF-64): `ad_` y un slug ASCII del nombre legible.

El prefijo lo separa de los campos base, de los que vengan despues y de las variables que un
conector pone en cada fila. Igual se valida contra `RESERVADOS`, la lista de los nombres que ya
usan los contextos del motor y los conectores: un nombre nunca puede taparlos.
"""

import re
from collections.abc import Iterable

from app.core.services.mapeador.similitud import sin_tildes

PREFIJO = "ad_"
LARGO_MAXIMO_SLUG = 40

# Las variables que un contexto o un conector agrega a cada fila (fecha_envio y los dias
# ajustados del motor; titular, vencimiento, WhatsApp y dias ajustados de MOWA MES). Una prueba
# comprueba que cada variable de los contextos conocidos este aqui o en el catalogo base.
RESERVADOS = frozenset(
    {
        "titular",
        "fecha_vencimiento_cuota",
        "whatsapp_contacto",
        "fecha_envio",
        "dias_atraso_ajustados",
    }
)


def slug(nombre_legible: str) -> str:
    """Minusculas ASCII, con `_` en lugar de cualquier otra cosa; nunca vacio ni con `_` sueltos."""
    plano = re.sub(r"[^a-z0-9]+", "_", sin_tildes(nombre_legible).casefold()).strip("_")
    return plano[:LARGO_MAXIMO_SLUG].strip("_") or "campo"


def nombre_tecnico(nombre_legible: str, usados: Iterable[str]) -> str:
    """`ad_<slug>` o, si choca, `ad_<slug>_2`, `_3`... `usados` debe traer TODOS los nombres que
    hayan existido (archivados incluidos), para que un tecnico nunca se reutilice."""
    ocupados = set(usados) | RESERVADOS
    base = f"{PREFIJO}{slug(nombre_legible)}"
    candidato, n = base, 2
    while candidato in ocupados:
        candidato = f"{base}_{n}"
        n += 1
    return candidato

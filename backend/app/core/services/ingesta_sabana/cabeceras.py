"""Mapeo de cabeceras por nombre y alias, no por posicion (regla N-1)."""

import hashlib
import re
from collections.abc import Sequence
from typing import Any

from app.core.entities.sabana import ColumnaSabana, Incidencia, MapeoCabeceras, Severidad
from app.core.services.ingesta_sabana.catalogo import CATALOGO_VENCIDA
from app.core.services.ingesta_sabana.reglas import es_vacio, normalizar_cabecera


def mapear_cabeceras(
    cabeceras: Sequence[Any], catalogo: Sequence[ColumnaSabana] = CATALOGO_VENCIDA
) -> MapeoCabeceras:
    """Asigna cada cabecera del archivo a una columna del catalogo.

    - Cada cabecera toma la primera columna del catalogo (en orden) cuyo patron
      coincide y que aun no fue asignada.
    - Cabeceras sin coincidencia: `cabecera_desconocida` (advertencia); sus
      datos se conservan solo en el registro crudo.
    - Cabeceras que coinciden solo con columnas ya asignadas: `cabecera_duplicada`.
    - Columnas del catalogo sin cabecera: `columna_faltante`, con severidad
      error si la columna es requerida (archivo bloqueado) o advertencia si no.
    """
    compilado = [(col, tuple(re.compile(p) for p in col.patrones)) for col in catalogo]
    columnas: dict[int, ColumnaSabana] = {}
    desconocidas: dict[int, str] = {}
    incidencias: list[Incidencia] = []
    asignadas: set[str] = set()

    for indice, cabecera in enumerate(cabeceras):
        if es_vacio(cabecera):
            continue
        original = str(cabecera)
        normal = normalizar_cabecera(original)
        candidatas = [col for col, pats in compilado if any(p.fullmatch(normal) for p in pats)]
        libre = next((col for col in candidatas if col.nombre not in asignadas), None)
        if libre is not None:
            columnas[indice] = libre
            asignadas.add(libre.nombre)
            continue
        desconocidas[indice] = original
        codigo = "cabecera_duplicada" if candidatas else "cabecera_desconocida"
        detalle = (
            f"La cabecera de la posicion {indice + 1} repite una columna ya asignada"
            if candidatas
            else f"La cabecera de la posicion {indice + 1} no esta en el catalogo"
        )
        incidencias.append(Incidencia(None, original, codigo, Severidad.ADVERTENCIA, detalle))

    faltantes = [col for col in catalogo if col.nombre not in asignadas]
    for col in faltantes:
        severidad = Severidad.ERROR if col.requerida else Severidad.ADVERTENCIA
        incidencias.append(
            Incidencia(None, col.nombre, "columna_faltante", severidad, "Columna esperada ausente")
        )

    return MapeoCabeceras(
        columnas=columnas, desconocidas=desconocidas, faltantes=faltantes, incidencias=incidencias
    )


def huella_formato(cabeceras: Sequence[Any]) -> str:
    """SHA-256 de las cabeceras normalizadas, en orden (regla V-9).

    Cambia si se agrega, quita, renombra o reordena una columna (p. ej.
    PAGARE2 -> PAGARE); no cambia por tildes, mayusculas o espacios sobrantes.
    """
    normalizadas = ["" if es_vacio(c) else normalizar_cabecera(str(c)) for c in cabeceras]
    return hashlib.sha256("\x1f".join(normalizadas).encode("utf-8")).hexdigest()


def describir_mapeo(mapeo: MapeoCabeceras) -> dict[str, Any]:
    """Resumen serializable del mapeo, para guardarlo con la version (V-9).

    Posiciones en base 1, como las columnas de la hoja.
    """
    return {
        "columnas": {col.nombre: indice + 1 for indice, col in sorted(mapeo.columnas.items())},
        "desconocidas": {str(i + 1): cab for i, cab in sorted(mapeo.desconocidas.items())},
        "faltantes": [col.nombre for col in mapeo.faltantes],
    }

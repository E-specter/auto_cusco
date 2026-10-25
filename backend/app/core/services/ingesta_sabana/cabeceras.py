"""Mapeo de cabeceras por nombre y alias, no por posicion (regla N-1)."""

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

from app.core.entities.sabana import ColumnaSabana, Incidencia, MapeoCabeceras, Severidad
from app.core.services.ingesta_sabana.catalogo import CATALOGO_VENCIDA, campo_destino
from app.core.services.ingesta_sabana.reglas import es_vacio
from app.core.services.mapeador.similitud import coincide, normalizar_cabecera


def mapear_cabeceras(
    cabeceras: Sequence[Any], catalogo: Sequence[ColumnaSabana] = CATALOGO_VENCIDA
) -> MapeoCabeceras:
    """Asigna cada cabecera del archivo a una columna del catalogo.

    - Cada cabecera toma la primera columna del catalogo (en orden) que coincide (un patron
      o su nombre, con `_` como espacio: `mapeador.coincide`) y que aun no fue asignada.
    - Cabeceras sin coincidencia: `cabecera_desconocida` (advertencia); sus
      datos se conservan solo en el registro crudo.
    - Cabeceras que coinciden solo con columnas ya asignadas: `cabecera_duplicada`.
    - Columnas del catalogo sin cabecera: `columna_faltante`, con severidad
      error si la columna es requerida (archivo bloqueado) o advertencia si no.
    """
    campos = [(col, campo_destino(col)) for col in catalogo]
    columnas: dict[int, ColumnaSabana] = {}
    desconocidas: dict[int, str] = {}
    incidencias: list[Incidencia] = []
    asignadas: set[str] = set()

    for indice, cabecera in enumerate(cabeceras):
        if es_vacio(cabecera):
            continue
        original = str(cabecera)
        normal = normalizar_cabecera(original)
        candidatas = [col for col, campo in campos if coincide(normal, campo)]
        libre = next((col for col in candidatas if col.nombre not in asignadas), None)
        if libre is not None:
            columnas[indice] = libre
            asignadas.add(libre.nombre)
            continue
        desconocidas[indice] = original
        # Codigo literal en cada rama: asi el catalogo de codigos se puede verificar
        # (ver tests/test_codigos_incidencia.py).
        if candidatas:
            incidencias.append(
                Incidencia(
                    None,
                    original,
                    "cabecera_duplicada",
                    Severidad.ADVERTENCIA,
                    f"La cabecera de la posicion {indice + 1} repite una columna ya asignada",
                )
            )
        else:
            incidencias.append(
                Incidencia(
                    None,
                    original,
                    "cabecera_desconocida",
                    Severidad.ADVERTENCIA,
                    f"La cabecera de la posicion {indice + 1} no esta en el catalogo",
                )
            )

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


def describir_mapeo(
    mapeo: MapeoCabeceras, origenes: Mapping[str, str] | None = None
) -> dict[str, Any]:
    """Resumen serializable del mapeo, para guardarlo con la version (V-9).

    Posiciones en base 1, como las columnas de la hoja. Con `origenes` (el mapeo lo confirmo el
    usuario, RF-62) suma, sin cambiar lo demas: `origenes` (`{campo: origen}`) e `ignoradas`
    (`{posicion: encabezado}`, las columnas en «No cargar»). Sin `origenes` queda como siempre.
    """
    descrito: dict[str, Any] = {
        "columnas": {col.nombre: indice + 1 for indice, col in sorted(mapeo.columnas.items())},
        "desconocidas": {str(i + 1): cab for i, cab in sorted(mapeo.desconocidas.items())},
        "faltantes": [col.nombre for col in mapeo.faltantes],
    }
    if origenes is not None:
        descrito["origenes"] = dict(origenes)
        descrito["ignoradas"] = dict(descrito["desconocidas"])
    return descrito

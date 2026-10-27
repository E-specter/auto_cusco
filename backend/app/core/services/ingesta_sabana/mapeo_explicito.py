"""El mapeo de cabeceras confirmado por el usuario (RF-60 a RF-62), en lugar del de nombre y alias.

Una carga confirmada desde un borrador guarda una asignacion por columna (`carga.asignaciones`). Al
procesarla se arma el mismo `MapeoCabeceras` que arma `mapear_cabeceras`, con las mismas incidencias
para que un archivo que hoy carga por alias de la misma version por los dos caminos. Las columnas en
«No cargar» van a `desconocidas`, y de ahi al registro crudo de cada fila (`_extras`).

Antes de usarlo se comprueba que cada columna siga siendo la misma: el archivo se vuelve a leer al
procesar (y al reprocesar), y si la columna N ya no tiene ESE encabezado, la carga falla con un
motivo claro en vez de cargar una columna en el campo equivocado.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from app.core.entities.mapeador import OrigenAsignacion
from app.core.entities.sabana import (
    ColumnaSabana,
    Incidencia,
    MapeoCabeceras,
    Severidad,
)
from app.core.services.ingesta_sabana.adicionales import CONVERSORES_ADICIONALES
from app.core.services.ingesta_sabana.catalogo import CATALOGO_VENCIDA, campo_destino
from app.core.services.ingesta_sabana.reglas import es_vacio
from app.core.services.mapeador.similitud import coincide, normalizar_cabecera


class MapeoGuardadoInvalido(Exception):
    """El mapeo guardado con la carga no corresponde al archivo leido: `str(error)` es el motivo."""


def _verificar(cabeceras: Sequence[Any], asignaciones: Sequence[Mapping[str, Any]]) -> None:
    por_indice: dict[int, Mapping[str, Any]] = {}
    for asignacion in asignaciones:
        indice = asignacion["indice"]
        if not 0 <= indice < len(cabeceras):
            raise MapeoGuardadoInvalido(
                f"El mapeo guardado usa la columna {indice + 1}, pero el archivo leido tiene "
                f"{len(cabeceras)} columnas"
            )
        leido = normalizar_cabecera(str(cabeceras[indice]))
        if leido != asignacion["encabezado_normalizado"]:
            raise MapeoGuardadoInvalido(
                f"La columna {indice + 1} ya no es la misma: el mapeo guardado esperaba "
                f"{asignacion['encabezado_normalizado']!r} y el archivo leido trae {leido!r}"
            )
        por_indice[indice] = asignacion
    for indice, cabecera in enumerate(cabeceras):
        if not es_vacio(cabecera) and indice not in por_indice:
            raise MapeoGuardadoInvalido(
                f"La columna {indice + 1} ({str(cabecera)!r}) no tiene asignacion en el mapeo "
                "guardado"
            )


def mapeo_desde_asignaciones(
    cabeceras: Sequence[Any],
    asignaciones: Sequence[Mapping[str, Any]],
    catalogo: Sequence[ColumnaSabana] = CATALOGO_VENCIDA,
) -> tuple[MapeoCabeceras, dict[str, str], dict[int, str]]:
    """El `MapeoCabeceras`, los origenes (`{campo: origen}`) y las columnas ignoradas
    (`{indice: encabezado}`) de las asignaciones guardadas.

    Lanza `MapeoGuardadoInvalido` si una columna ya no es la misma o el campo ya no esta en el
    catalogo.
    """
    _verificar(cabeceras, asignaciones)
    por_nombre = {columna.nombre: columna for columna in catalogo}
    columnas: dict[int, ColumnaSabana] = {}
    origenes: dict[str, str] = {}
    ignoradas: dict[int, str] = {}
    for asignacion in sorted(asignaciones, key=lambda a: a["indice"]):
        indice, campo = asignacion["indice"], asignacion["campo"]
        if campo is None:
            ignoradas[indice] = str(cabeceras[indice])
        elif campo not in por_nombre:
            raise MapeoGuardadoInvalido(
                f"El campo {campo!r} del mapeo guardado ya no esta en el catalogo"
            )
        else:
            columnas[indice] = por_nombre[campo]
            origenes[campo] = OrigenAsignacion(asignacion["origen"]).value
    asignados = {columna.nombre for columna in columnas.values()}

    # Los adicionales no se buscan ni se echan en falta: su alias es el encabezado de origen.
    base = [columna for columna in catalogo if columna.tipo not in CONVERSORES_ADICIONALES]
    campos = [(columna, campo_destino(columna)) for columna in base]
    incidencias: list[Incidencia] = []
    for indice, cabecera in ignoradas.items():
        candidatas = [c for c, campo in campos if coincide(normalizar_cabecera(cabecera), campo)]
        if not candidatas:
            incidencias.append(_incidencia_desconocida(indice, cabecera))
        elif all(c.nombre in asignados for c in candidatas):
            incidencias.append(_incidencia_duplicada(indice, cabecera))
        # Si el usuario dejo sin cargar una columna que si coincidia con un campo libre, es suyo.
    faltantes = [columna for columna in base if columna.nombre not in asignados]
    for columna in faltantes:
        severidad = Severidad.ERROR if columna.requerida else Severidad.ADVERTENCIA
        incidencias.append(
            Incidencia(
                None, columna.nombre, "columna_faltante", severidad, "Columna esperada ausente"
            )
        )
    mapeo = MapeoCabeceras(
        columnas=columnas, desconocidas=ignoradas, faltantes=faltantes, incidencias=incidencias
    )
    return mapeo, origenes, ignoradas


def _incidencia_desconocida(indice: int, cabecera: str) -> Incidencia:
    return Incidencia(
        None,
        cabecera,
        "cabecera_desconocida",
        Severidad.ADVERTENCIA,
        f"La cabecera de la posicion {indice + 1} no esta en el catalogo",
    )


def _incidencia_duplicada(indice: int, cabecera: str) -> Incidencia:
    return Incidencia(
        None,
        cabecera,
        "cabecera_duplicada",
        Severidad.ADVERTENCIA,
        f"La cabecera de la posicion {indice + 1} repite una columna ya asignada",
    )

"""Validacion de las asignaciones del usuario contra el analisis que se le mostro (RF-60, M-4, M-5).

Funciones puras. El analisis es el que se guardo con el borrador, no uno nuevo: si otro usuario
recordo algo en el medio, un analisis nuevo daria otros estados y la validacion no coincidiria con
lo que se vio. La carga se confirma solo si no hay problemas; una columna en «No cargar» no genera
ninguno.
"""

from collections import Counter
from collections.abc import Sequence

from app.core.entities.mapeador import (
    AnalisisEncabezados,
    Asignacion,
    CodigoMapeo,
    ColumnaAnalizada,
    EstadoEncabezado,
    OrigenAsignacion,
    ProblemaMapeo,
)

_REVISADOS = frozenset({OrigenAsignacion.PARECIDO_ACEPTADO, OrigenAsignacion.MANUAL})


def _origen_recalculado(asignacion: Asignacion, columna: ColumnaAnalizada) -> OrigenAsignacion:
    """El origen que vale para guardar la asignacion: el backend no confia en la etiqueta (3.4).

    - En un `parecido`: con otro campo (o «No cargar») es `manual`; con el sugerido se queda la
      etiqueta (`parecido_aceptado` o `manual` revisan; otra, no).
    - En una columna que no era `parecido`: si el campo no cambio, `recordado` o `coincide` segun su
      estado; si cambio, `manual`. Una columna `sin_coincidencia` sin cambio (sigue en «No
      cargar») no tiene origen automatico: la confirmo el usuario, es `manual`.
    """
    sin_cambio = asignacion.campo == columna.sugerido
    if columna.estado is EstadoEncabezado.PARECIDO:
        # Con otro campo, sea cual sea la etiqueta, el usuario eligio: manual. Con el sugerido solo
        # cuenta como revisado si dice `parecido_aceptado` o `manual`; si no, queda sin revisar.
        return asignacion.origen if sin_cambio else OrigenAsignacion.MANUAL
    if not sin_cambio:
        return OrigenAsignacion.MANUAL
    if columna.estado is EstadoEncabezado.RECORDADO:
        return OrigenAsignacion.RECORDADO
    if columna.estado is EstadoEncabezado.COINCIDE:
        return OrigenAsignacion.COINCIDE
    return OrigenAsignacion.MANUAL


def resolver_asignaciones(
    asignaciones: Sequence[Asignacion], analisis: AnalisisEncabezados
) -> tuple[Asignacion, ...]:
    """Las asignaciones con el origen recalculado desde el analisis (la entrada, en el mismo orden).

    Las que apuntan a una columna que no esta en el analisis quedan como llegaron: `validar` las
    informa. Es idempotente: resolver lo ya resuelto no cambia nada.
    """
    columnas = {c.indice: c for c in analisis.columnas}
    resueltas = []
    for asignacion in asignaciones:
        columna = columnas.get(asignacion.indice)
        if columna is None:
            resueltas.append(asignacion)
            continue
        origen = _origen_recalculado(asignacion, columna)
        resueltas.append(
            asignacion
            if origen is asignacion.origen
            else Asignacion(asignacion.indice, asignacion.campo, origen)
        )
    return tuple(resueltas)


def validar(
    asignaciones: Sequence[Asignacion], analisis: AnalisisEncabezados
) -> tuple[ProblemaMapeo, ...]:
    """Los problemas de las asignaciones; vacio si la carga se puede confirmar.

    Primero los de proteccion de la API (`indice_repetido` e `indice_fuera_de_rango`), despues los
    de cada columna en el orden de las columnas y por ultimo los obligatorios sin columna, en el
    orden del catalogo. Con dos asignaciones para una misma columna se valida la primera.
    """
    problemas: list[ProblemaMapeo] = []
    columnas = {c.indice: c for c in analisis.columnas}
    nombres = {c.nombre for c in analisis.campos}

    veces = Counter(a.indice for a in asignaciones)
    for indice, cuantas in sorted(veces.items()):
        if cuantas > 1:
            problemas.append(
                ProblemaMapeo(
                    indice,
                    CodigoMapeo.INDICE_REPETIDO,
                    f"La columna {indice} tiene {cuantas} asignaciones",
                )
            )
    primeras: dict[int, Asignacion] = {}
    for asignacion in resolver_asignaciones(asignaciones, analisis):
        primeras.setdefault(asignacion.indice, asignacion)

    for indice in sorted(primeras):
        if indice not in columnas:
            problemas.append(
                ProblemaMapeo(
                    indice,
                    CodigoMapeo.INDICE_FUERA_DE_RANGO,
                    f"La columna {indice} no esta en el archivo analizado",
                )
            )
    por_campo: dict[str, list[int]] = {}
    for columna in analisis.columnas:
        asignacion = primeras.get(columna.indice)
        if asignacion is None:
            problemas.append(
                ProblemaMapeo(
                    columna.indice,
                    CodigoMapeo.ASIGNACION_FALTANTE,
                    f"La columna {columna.indice} no trae asignacion",
                )
            )
            continue
        if asignacion.campo is not None:
            if asignacion.campo not in nombres:
                problemas.append(
                    ProblemaMapeo(
                        columna.indice,
                        CodigoMapeo.CAMPO_DESCONOCIDO,
                        f"El campo {asignacion.campo!r} no esta en el catalogo",
                        asignacion.campo,
                    )
                )
            else:
                por_campo.setdefault(asignacion.campo, []).append(columna.indice)
        if columna.estado is EstadoEncabezado.PARECIDO and asignacion.origen not in _REVISADOS:
            problemas.append(
                ProblemaMapeo(
                    columna.indice,
                    CodigoMapeo.PARECIDO_SIN_REVISAR,
                    f"La columna {columna.indice} es un parecido que nadie acepto ni cambio",
                    columna.sugerido,
                )
            )
    for campo, indices in por_campo.items():
        if len(indices) > 1:
            for indice in indices:
                problemas.append(
                    ProblemaMapeo(
                        indice,
                        CodigoMapeo.CAMPO_REPETIDO,
                        f"El campo {campo!r} esta en {len(indices)} columnas",
                        campo,
                    )
                )
    for campo in analisis.campos:
        if campo.obligatorio and campo.nombre not in por_campo:
            problemas.append(
                ProblemaMapeo(
                    None,
                    CodigoMapeo.OBLIGATORIO_SIN_COLUMNA,
                    f"El campo obligatorio {campo.nombre!r} no tiene columna",
                    campo.nombre,
                )
            )
    return tuple(problemas)

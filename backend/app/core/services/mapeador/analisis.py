"""Analisis de los encabezados de un archivo contra un catalogo de campos (RF-58, RF-59).

`analizar` es una funcion pura. Por cada encabezado decide un estado y sugiere un campo, en este
orden de precedencia: recordado, coincide, parecido, sin coincidencia. Son TRES PASADAS sobre todas
las columnas, de izquierda a derecha en cada una, para que un recordado gane siempre a una
coincidencia aunque esta quede mas a la izquierda (M-3).

La tercera pasada (los parecidos) es «mejor primero», no de izquierda a derecha: asi la sugerencia
de una columna no depende de cuantas columnas la preceden.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

from app.core.entities.mapeador import (
    AnalisisEncabezados,
    Asignacion,
    CatalogoCampos,
    ColumnaAnalizada,
    EstadoEncabezado,
    OrigenAsignacion,
)
from app.core.services.mapeador.similitud import (
    DIFERENCIA_DE_EMPATE,
    UMBRAL_PARECIDO,
    coincide,
    normalizar_cabecera,
    similitud,
)
from app.core.services.mapeador.validacion import validar

MAXIMO_EJEMPLOS = 3  # valores de ejemplo por columna
FILAS_DE_MUESTRA = 200  # las primeras filas con datos de las que salen los ejemplos

# Los mapeos recordados: (encabezado normalizado, ocurrencia) -> campo, o None para «No cargar». La
# ocurrencia evita que dos encabezados iguales compartan un recordado (M-1).
Recordados = Mapping[tuple[str, int], str | None]

_ORIGEN_SUGERIDO = {
    EstadoEncabezado.RECORDADO: OrigenAsignacion.RECORDADO,
    EstadoEncabezado.COINCIDE: OrigenAsignacion.COINCIDE,
    # Un parecido y una columna sin coincidencia no son una revision del usuario: `validar` ve un
    # parecido con este origen como «sin revisar».
    EstadoEncabezado.PARECIDO: OrigenAsignacion.COINCIDE,
    EstadoEncabezado.SIN_COINCIDENCIA: OrigenAsignacion.MANUAL,
}


EsVacio = Callable[[Any], bool]


def es_vacio(valor: Any) -> bool:
    """Vacio para el mapeador: `None` o un texto en blanco. Cada consumidor puede pasar el suyo a
    `analizar` (la sabana, que ademas toma el literal NULL por vacio)."""
    return valor is None or (isinstance(valor, str) and not valor.strip())


def _ejemplos(
    filas: Iterable[Sequence[Any]], indices: Sequence[int], vacio: EsVacio
) -> dict[int, tuple[str, ...]]:
    """Hasta `MAXIMO_EJEMPLOS` valores no vacios por columna, como texto, de las primeras
    `FILAS_DE_MUESTRA` filas con datos (una fila sin ningun valor no cuenta)."""
    encontrados: dict[int, list[str]] = {i: [] for i in indices}
    con_datos = 0
    for fila in filas:
        if all(vacio(valor) for valor in fila):
            continue
        for indice, ejemplos in encontrados.items():
            if len(ejemplos) < MAXIMO_EJEMPLOS and indice < len(fila) and not vacio(fila[indice]):
                ejemplos.append(str(fila[indice]))
        con_datos += 1
        if con_datos >= FILAS_DE_MUESTRA or all(
            len(e) >= MAXIMO_EJEMPLOS for e in encontrados.values()
        ):
            break
    return {i: tuple(e) for i, e in encontrados.items()}


def _parecidos(
    pendientes: Sequence[tuple[int, str]],
    catalogo: CatalogoCampos,
    tomados: set[str],
    decididas: dict[int, tuple[EstadoEncabezado, str | None, float | None]],
) -> None:
    """Tercera pasada, «mejor primero»: asigna los pares (columna, campo libre) de mayor similitud.

    Se arman todos los pares con similitud >= `UMBRAL_PARECIDO` y se ordenan de mayor a menor
    similitud (a igual similitud, por indice de columna y despues por orden del catalogo). Se
    recorren saltando las columnas ya decididas y los campos ya tomados. El empate se mantiene
    por columna: si en el momento de asignarla sus dos mejores campos LIBRES difieren en menos de
    `DIFERENCIA_DE_EMPATE`, la columna queda sin sugerencia y no toma ningun campo.
    """
    libres = [(orden, c) for orden, c in enumerate(catalogo.campos) if c.nombre not in tomados]
    puntajes = {(i, c.nombre): similitud(n, c) for i, n in pendientes for _, c in libres}
    pares = sorted(
        (-puntajes[(i, c.nombre)], i, orden)
        for i, _ in pendientes
        for orden, c in libres
        if puntajes[(i, c.nombre)] >= UMBRAL_PARECIDO
    )
    for menos_puntaje, indice, orden in pares:
        campo = catalogo.campos[orden]
        if indice in decididas or campo.nombre in tomados:
            continue
        libres_ahora = sorted(
            (puntajes[(indice, c.nombre)] for _, c in libres if c.nombre not in tomados),
            reverse=True,
        )
        if len(libres_ahora) > 1 and libres_ahora[0] - libres_ahora[1] < DIFERENCIA_DE_EMPATE:
            decididas[indice] = (EstadoEncabezado.SIN_COINCIDENCIA, None, None)
            continue
        tomados.add(campo.nombre)
        decididas[indice] = (EstadoEncabezado.PARECIDO, campo.nombre, -menos_puntaje)
    for indice, _ in pendientes:
        decididas.setdefault(indice, (EstadoEncabezado.SIN_COINCIDENCIA, None, None))


def analizar(
    cabeceras: Sequence[Any],
    filas_muestra: Iterable[Sequence[Any]],
    catalogo: CatalogoCampos,
    recordados: Recordados,
    vacio: EsVacio = es_vacio,
) -> AnalisisEncabezados:
    """El analisis de `cabeceras` (las del archivo, en su orden) contra `catalogo`.

    Los encabezados vacios no se listan, pero el `indice` de los demas se conserva. `filas_muestra`
    solo aporta los ejemplos. Un recordado que apunta a un campo que ya no esta en el catalogo se
    ignora; uno que apunta a un campo ya tomado por otro recordado queda en `sin_coincidencia`.
    `vacio` dice que encabezados y que valores son vacios (por defecto, `None` o un texto en
    blanco).
    """
    visibles: list[tuple[int, str, str, int]] = []  # (indice, encabezado, normalizado, ocurrencia)
    vistos: dict[str, int] = {}
    for indice, cabecera in enumerate(cabeceras):
        if vacio(cabecera):
            continue
        texto = str(cabecera)
        normalizado = normalizar_cabecera(texto)
        vistos[normalizado] = vistos.get(normalizado, 0) + 1
        visibles.append((indice, texto, normalizado, vistos[normalizado]))

    nombres = {c.nombre for c in catalogo.campos}
    decididas: dict[int, tuple[EstadoEncabezado, str | None, float | None]] = {}
    tomados: set[str] = set()

    # 1. Los recordados, todos, antes que cualquier coincidencia.
    for indice, _, normalizado, ocurrencia in visibles:
        clave = (normalizado, ocurrencia)
        if clave not in recordados:
            continue
        campo = recordados[clave]
        if campo is None:
            decididas[indice] = (EstadoEncabezado.RECORDADO, None, None)
        elif campo not in nombres:
            continue
        elif campo in tomados:
            decididas[indice] = (EstadoEncabezado.SIN_COINCIDENCIA, None, None)
        else:
            tomados.add(campo)
            decididas[indice] = (EstadoEncabezado.RECORDADO, campo, None)

    # 2. Las coincidencias: el primer campo del catalogo, en su orden, que este libre.
    for indice, _, normalizado, _ in visibles:
        if indice in decididas:
            continue
        for campo in catalogo.campos:
            if campo.nombre not in tomados and coincide(normalizado, campo):
                tomados.add(campo.nombre)
                decididas[indice] = (EstadoEncabezado.COINCIDE, campo.nombre, None)
                break

    # 3. Los parecidos, mejor primero, entre los campos que quedan libres.
    _parecidos(
        [(i, n) for i, _, n, _ in visibles if i not in decididas], catalogo, tomados, decididas
    )

    ejemplos = _ejemplos(filas_muestra, [v[0] for v in visibles], vacio)
    columnas = tuple(
        ColumnaAnalizada(
            indice=indice,
            encabezado=texto,
            normalizado=normalizado,
            ocurrencia=ocurrencia,
            ejemplos=ejemplos[indice],
            estado=decididas[indice][0],
            sugerido=decididas[indice][1],
            similitud=decididas[indice][2],
        )
        for indice, texto, normalizado, ocurrencia in visibles
    )
    analisis = AnalisisEncabezados(catalogo.id, columnas, catalogo.campos, ())
    sugeridas = [Asignacion(c.indice, c.sugerido, _ORIGEN_SUGERIDO[c.estado]) for c in columnas]
    return AnalisisEncabezados(catalogo.id, columnas, catalogo.campos, validar(sugeridas, analisis))

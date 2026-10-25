"""La validacion de las asignaciones del mapeador (T-MAP-B1, RF-60, RF-62, M-4, M-5)."""

import random

import pytest

from app.core.entities.mapeador import (
    AnalisisEncabezados,
    Asignacion,
    CodigoMapeo,
    EstadoEncabezado,
    OrigenAsignacion,
)
from app.core.services.mapeador.analisis import analizar
from app.core.services.mapeador.validacion import resolver_asignaciones, validar
from tests.test_mapeador_analisis import (
    CAT,
    SEMILLA,
    _catalogo_al_azar,
    _encabezados_al_azar,
    _recordados_al_azar,
)

C = CodigoMapeo
O = OrigenAsignacion  # noqa: E741
E = EstadoEncabezado

# 0 coincide (clave), 1 parecido (fecha_pago), 2 coincide (zona), 3 sin coincidencia, 4 recordado.
CABECERAS = ["Clave", "Fecha de pagos", "Zona", "Zzxqv", "Dato raro"]
RECORDADOS = {("dato raro", 1): "monto"}
ANALISIS = analizar(CABECERAS, [], CAT, RECORDADOS)


def sugeridas() -> list[Asignacion]:
    """Lo que la pantalla manda sin tocar nada, con el parecido aceptado."""
    origenes = {
        E.RECORDADO: O.RECORDADO,
        E.COINCIDE: O.COINCIDE,
        E.PARECIDO: O.PARECIDO_ACEPTADO,
        E.SIN_COINCIDENCIA: O.MANUAL,
    }
    return [Asignacion(c.indice, c.sugerido, origenes[c.estado]) for c in ANALISIS.columnas]


def con(asignaciones: list[Asignacion], indice: int, **cambios) -> list[Asignacion]:
    nuevas = []
    for a in asignaciones:
        if a.indice == indice:
            a = Asignacion(a.indice, cambios.get("campo", a.campo), cambios.get("origen", a.origen))
        nuevas.append(a)
    return nuevas


def codigos(problemas) -> list[CodigoMapeo]:
    return [p.codigo for p in problemas]


def test_el_analisis_de_partida_es_el_que_dice_el_comentario() -> None:
    assert [c.estado for c in ANALISIS.columnas] == [
        E.COINCIDE,
        E.PARECIDO,
        E.COINCIDE,
        E.SIN_COINCIDENCIA,
        E.RECORDADO,
    ]


def test_las_sugerencias_aceptadas_no_tienen_problemas() -> None:
    assert validar(sugeridas(), ANALISIS) == ()


# --- Cada codigo ----------------------------------------------------------------------------------


def test_parecido_sin_revisar() -> None:
    asignaciones = con(sugeridas(), 1, origen=O.COINCIDE)

    [problema] = validar(asignaciones, ANALISIS)

    assert (problema.indice, problema.codigo, problema.campo) == (
        1,
        C.PARECIDO_SIN_REVISAR,
        "fecha_pago",
    )


@pytest.mark.parametrize("origen", [O.PARECIDO_ACEPTADO, O.MANUAL])
def test_un_parecido_aceptado_o_cambiado_a_mano_esta_revisado(origen) -> None:
    assert validar(con(sugeridas(), 1, origen=origen), ANALISIS) == ()


def test_un_parecido_cambiado_a_otro_campo_esta_revisado_aunque_la_etiqueta_mienta() -> None:
    asignaciones = con(sugeridas(), 1, campo="observacion", origen=O.COINCIDE)

    assert validar(asignaciones, ANALISIS) == ()


def test_un_parecido_pasado_a_no_cargar_esta_revisado() -> None:
    assert validar(con(sugeridas(), 1, campo=None, origen=O.MANUAL), ANALISIS) == ()


def test_obligatorio_sin_columna() -> None:
    asignaciones = con(sugeridas(), 0, campo=None, origen=O.MANUAL)

    [problema] = validar(asignaciones, ANALISIS)

    assert (problema.indice, problema.codigo, problema.campo) == (
        None,
        C.OBLIGATORIO_SIN_COLUMNA,
        "clave",
    )


def test_campo_repetido_se_informa_en_cada_columna() -> None:
    asignaciones = con(sugeridas(), 2, campo="clave", origen=O.MANUAL)

    problemas = validar(asignaciones, ANALISIS)

    assert [(p.indice, p.codigo, p.campo) for p in problemas] == [
        (0, C.CAMPO_REPETIDO, "clave"),
        (2, C.CAMPO_REPETIDO, "clave"),
    ]


def test_tres_columnas_con_el_mismo_campo_dan_tres_problemas() -> None:
    asignaciones = con(con(sugeridas(), 2, campo="clave"), 3, campo="clave", origen=O.MANUAL)

    assert codigos(validar(asignaciones, ANALISIS)) == [C.CAMPO_REPETIDO] * 3


def test_campo_desconocido() -> None:
    asignaciones = con(sugeridas(), 2, campo="no_existe", origen=O.MANUAL)

    problemas = validar(asignaciones, ANALISIS)

    assert (problemas[0].indice, problemas[0].codigo, problemas[0].campo) == (
        2,
        C.CAMPO_DESCONOCIDO,
        "no_existe",
    )


def test_indice_fuera_de_rango() -> None:
    asignaciones = [*sugeridas(), Asignacion(99, "zona", O.MANUAL), Asignacion(-1, None, O.MANUAL)]

    problemas = validar(asignaciones, ANALISIS)

    assert [(p.indice, p.codigo) for p in problemas] == [
        (-1, C.INDICE_FUERA_DE_RANGO),
        (99, C.INDICE_FUERA_DE_RANGO),
    ]


def test_un_indice_de_un_encabezado_vacio_esta_fuera_de_rango() -> None:
    analisis = analizar(["Clave", None, "Zona"], [], CAT, {})
    asignaciones = [
        Asignacion(0, "clave", O.COINCIDE),
        Asignacion(1, None, O.MANUAL),
        Asignacion(2, "zona", O.COINCIDE),
    ]

    assert [(p.indice, p.codigo) for p in validar(asignaciones, analisis)] == [
        (1, C.INDICE_FUERA_DE_RANGO)
    ]


def test_asignacion_faltante() -> None:
    asignaciones = [a for a in sugeridas() if a.indice != 3]

    [problema] = validar(asignaciones, ANALISIS)

    assert (problema.indice, problema.codigo) == (3, C.ASIGNACION_FALTANTE)


def test_sin_ninguna_asignacion_falta_una_por_columna_y_los_obligatorios() -> None:
    problemas = validar([], ANALISIS)

    assert codigos(problemas) == [C.ASIGNACION_FALTANTE] * 5 + [C.OBLIGATORIO_SIN_COLUMNA]


def test_indice_repetido_valida_la_primera_asignacion() -> None:
    asignaciones = [*sugeridas(), Asignacion(2, "clave", O.MANUAL)]

    problemas = validar(asignaciones, ANALISIS)

    assert [(p.indice, p.codigo) for p in problemas] == [(2, C.INDICE_REPETIDO)]


def test_no_cargar_no_genera_problema() -> None:
    asignaciones = con(sugeridas(), 2, campo=None, origen=O.MANUAL)

    assert validar(asignaciones, ANALISIS) == ()


def test_el_orden_de_los_problemas() -> None:
    asignaciones = [
        Asignacion(0, None, O.MANUAL),  # deja la clave sin columna
        Asignacion(1, "fecha_pago", O.COINCIDE),  # parecido sin revisar, y repite `fecha_pago`
        Asignacion(2, "fecha_pago", O.MANUAL),
        Asignacion(7, None, O.MANUAL),  # fuera de rango
    ]

    problemas = validar(asignaciones, ANALISIS)

    assert [(p.indice, p.codigo) for p in problemas] == [
        (7, C.INDICE_FUERA_DE_RANGO),
        (1, C.PARECIDO_SIN_REVISAR),
        (3, C.ASIGNACION_FALTANTE),
        (4, C.ASIGNACION_FALTANTE),
        (1, C.CAMPO_REPETIDO),
        (2, C.CAMPO_REPETIDO),
        (None, C.OBLIGATORIO_SIN_COLUMNA),
    ]


# --- Contra el analisis guardado (M-4) ------------------------------------------------------------


def test_se_valida_contra_el_analisis_que_se_mostro_aunque_los_recordados_hayan_cambiado() -> None:
    mostrado = analizar(["Clave", "Dato raro"], [], CAT, {})  # `Dato raro` no se parece a nada
    asignaciones = [Asignacion(0, "clave", O.COINCIDE), Asignacion(1, "zona", O.MANUAL)]
    # Mientras tanto otro usuario recordo `Dato raro` -> `monto`.
    despues = analizar(["Clave", "Dato raro"], [], CAT, {("dato raro", 1): "monto"})

    assert validar(asignaciones, mostrado) == ()
    # Contra el analisis nuevo la misma asignacion ya es otra cosa: no se usa.
    assert despues.columnas[1].estado is E.RECORDADO
    assert [r.origen for r in resolver_asignaciones(asignaciones, despues)] == [
        O.COINCIDE,
        O.MANUAL,
    ]


# --- El origen que se guarda (RF-62) --------------------------------------------------------------


def origenes(asignaciones: list[Asignacion]) -> list[OrigenAsignacion]:
    return [a.origen for a in resolver_asignaciones(asignaciones, ANALISIS)]


def test_el_origen_de_lo_que_no_cambio_sale_del_estado() -> None:
    mentiras = [Asignacion(c.indice, c.sugerido, O.PARECIDO_ACEPTADO) for c in ANALISIS.columnas]

    assert origenes(mentiras) == [
        O.COINCIDE,
        O.PARECIDO_ACEPTADO,  # el parecido aceptado se queda
        O.COINCIDE,
        O.MANUAL,  # sin coincidencia y sin cambio: lo confirmo el usuario
        O.RECORDADO,
    ]


def test_el_origen_de_lo_que_cambio_es_manual() -> None:
    asignaciones = [
        Asignacion(0, "zona", O.COINCIDE),
        Asignacion(1, "observacion", O.PARECIDO_ACEPTADO),
        Asignacion(2, None, O.COINCIDE),
        Asignacion(3, "monto", O.COINCIDE),
        Asignacion(4, "clave", O.RECORDADO),
    ]

    assert origenes(asignaciones) == [O.MANUAL] * 5


def test_resolver_es_idempotente_y_no_cambia_lo_que_validar_dice() -> None:
    azar = random.Random(SEMILLA + 2)
    for _ in range(300):
        asignaciones = [
            Asignacion(
                azar.randint(-1, 6),
                azar.choice([None, "clave", "zona", "monto", "fecha_pago", "nada"]),
                azar.choice(list(O)),
            )
            for _ in range(azar.randint(0, 8))
        ]

        una_vez = resolver_asignaciones(asignaciones, ANALISIS)

        assert resolver_asignaciones(una_vez, ANALISIS) == una_vez
        assert validar(una_vez, ANALISIS) == validar(asignaciones, ANALISIS)
        assert len(una_vez) == len(asignaciones)
        assert [(a.indice, a.campo) for a in una_vez] == [(a.indice, a.campo) for a in asignaciones]


def test_validar_es_idempotente() -> None:
    asignaciones = [Asignacion(1, "zona", O.COINCIDE), Asignacion(2, "zona", O.COINCIDE)]

    assert validar(asignaciones, ANALISIS) == validar(asignaciones, ANALISIS)


# --- Propiedad: sin problemas, la carga es consistente --------------------------------------


def _asignaciones_al_azar(azar: random.Random, analisis: AnalisisEncabezados) -> list[Asignacion]:
    """Casi las sugeridas, con cambios al azar: asi hay muchas listas sin problemas y muchas con."""
    nombres = [c.nombre for c in analisis.campos]
    asignaciones = []
    for c in analisis.columnas:
        campo = c.sugerido
        origen = azar.choice(list(O))
        if azar.random() < 0.25:
            campo = azar.choice([None, *nombres, "desconocido"])
        asignaciones.append(Asignacion(c.indice, campo, origen))
    if azar.random() < 0.1 and asignaciones:
        asignaciones.pop(azar.randrange(len(asignaciones)))
    if azar.random() < 0.1:
        asignaciones.append(Asignacion(azar.randint(0, 12), None, azar.choice(list(O))))
    return asignaciones


def test_sin_problemas_los_campos_son_distintos_y_los_obligatorios_estan_todos() -> None:
    azar = random.Random(SEMILLA + 3)
    sin_problemas = 0
    for _ in range(1500):
        catalogo = _catalogo_al_azar(azar, azar.randint(2, 6))
        cabeceras = _encabezados_al_azar(azar, catalogo)
        analisis = analizar(cabeceras, [], catalogo, _recordados_al_azar(azar, catalogo, cabeceras))
        asignaciones = _asignaciones_al_azar(azar, analisis)

        if validar(asignaciones, analisis):
            continue

        sin_problemas += 1
        asignados = [a.campo for a in asignaciones if a.campo is not None]
        assert len(asignados) == len(set(asignados))
        assert {c.nombre for c in analisis.campos if c.obligatorio} <= set(asignados)
        assert sorted(a.indice for a in asignaciones) == [c.indice for c in analisis.columnas]
        assert set(asignados) <= {c.nombre for c in analisis.campos}
        for columna in analisis.columnas:
            if columna.estado is E.PARECIDO:
                [propia] = [
                    a
                    for a in resolver_asignaciones(asignaciones, analisis)
                    if a.indice == columna.indice
                ]
                assert propia.origen in (O.PARECIDO_ACEPTADO, O.MANUAL)

    assert sin_problemas > 100  # la propiedad se ejercita, no pasa por vacia

"""El analisis de encabezados del mapeador (T-MAP-B1, RF-58, RF-59): estados y precedencia.

Todos los encabezados y valores son sinteticos. El catalogo de prueba imita lo que importa del de la
sabana (un campo obligatorio, uno que repite el alias del primero, uno con alias de expresion
regular), sin usar sus nombres reales salvo en la prueba de los dos «Pagare».
"""

import random

import pytest

from app.core.entities.mapeador import (
    Asignacion,
    CampoDestino,
    CatalogoCampos,
    CodigoMapeo,
    EstadoEncabezado,
    OrigenAsignacion,
)
from app.core.services.ingesta_sabana.catalogo import CATALOGO_SABANA
from app.core.services.mapeador import analisis as modulo
from app.core.services.mapeador.analisis import (
    FILAS_DE_MUESTRA,
    MAXIMO_EJEMPLOS,
    analizar,
)
from app.core.services.mapeador.similitud import (
    DIFERENCIA_DE_EMPATE,
    UMBRAL_PARECIDO,
    coincide,
    similitud,
)
from app.core.services.mapeador.validacion import validar

E = EstadoEncabezado
SEMILLA = 20261024


def campo(nombre: str, *alias: str, obligatorio: bool = False) -> CampoDestino:
    return CampoDestino(nombre, f"campo.{nombre}", "texto", obligatorio, alias)


CAT = CatalogoCampos(
    "prueba",
    (
        campo("clave", "clave", obligatorio=True),
        campo("clave_extra", "clave", "clave2?"),  # como pagare y pagare_duplicado
        campo("monto", "monto total", "importe"),
        campo("fecha_pago", "fecha de pago"),
        campo("zona", "zona"),
        campo("observacion", r"obs(ervacion)?"),  # un alias con metacaracteres
    ),
)


def estados(analisis) -> list[tuple[int, E, str | None]]:
    return [(c.indice, c.estado, c.sugerido) for c in analisis.columnas]


def codigos(problemas) -> list[CodigoMapeo]:
    return [p.codigo for p in problemas]


# --- Cada estado ----------------------------------------------------------------------------------


def test_un_alias_coincide() -> None:
    analisis = analizar(["Clave", "IMPORTE", "Zona"], [], CAT, {})

    assert estados(analisis) == [
        (0, E.COINCIDE, "clave"),
        (1, E.COINCIDE, "monto"),
        (2, E.COINCIDE, "zona"),
    ]
    assert all(c.similitud is None for c in analisis.columnas)


def test_un_encabezado_con_tildes_y_espacios_de_mas_coincide_igual() -> None:
    analisis = analizar(["  Fecha   de PAGO "], [], CAT, {})

    assert estados(analisis) == [(0, E.COINCIDE, "fecha_pago")]
    assert analisis.columnas[0].normalizado == "fecha de pago"
    assert analisis.columnas[0].encabezado == "  Fecha   de PAGO "


def test_un_encabezado_igual_al_nombre_del_campo_con_espacios_coincide() -> None:
    analisis = analizar(["fecha pago"], [], CAT, {})

    assert estados(analisis) == [(0, E.COINCIDE, "fecha_pago")]


def test_un_encabezado_parecido_se_sugiere_con_su_similitud() -> None:
    analisis = analizar(["Fecha de pagos"], [], CAT, {})

    [columna] = analisis.columnas
    assert (columna.estado, columna.sugerido) == (E.PARECIDO, "fecha_pago")
    assert columna.similitud is not None and columna.similitud >= UMBRAL_PARECIDO


def test_un_encabezado_sin_nada_parecido_no_sugiere_nada() -> None:
    analisis = analizar(["Zzxqv"], [], CAT, {})

    [columna] = analisis.columnas
    assert (columna.estado, columna.sugerido, columna.similitud) == (E.SIN_COINCIDENCIA, None, None)


def test_un_recordado_gana_a_lo_demas_y_puede_ser_no_cargar() -> None:
    recordados = {("importe", 1): "zona", ("zona", 1): None}

    analisis = analizar(["Importe", "Zona"], [], CAT, recordados)

    assert estados(analisis) == [(0, E.RECORDADO, "zona"), (1, E.RECORDADO, None)]


def test_el_orden_de_los_estados_en_una_misma_carga() -> None:
    analisis = analizar(
        ["Dato raro", "Clave", "Fecha de pagos", "Zzxqv"], [], CAT, {("dato raro", 1): "zona"}
    )

    assert [c.estado for c in analisis.columnas] == [
        E.RECORDADO,
        E.COINCIDE,
        E.PARECIDO,
        E.SIN_COINCIDENCIA,
    ]


# --- Precedencia ---------------------------------------------------------------------------------


def test_un_recordado_a_la_derecha_le_gana_a_una_coincidencia_a_la_izquierda() -> None:
    # M-3: «Importe» coincide con `monto`, pero la columna 2 lo tiene recordado y se lo queda.
    analisis = analizar(["Importe", "Dato raro"], [], CAT, {("dato raro", 1): "monto"})

    assert estados(analisis) == [(0, E.SIN_COINCIDENCIA, None), (1, E.RECORDADO, "monto")]


def test_un_recordado_contra_un_campo_ya_tomado_pasa_a_sin_coincidencia() -> None:
    recordados = {("uno", 1): "zona", ("dos", 1): "zona"}

    analisis = analizar(["Uno", "Dos"], [], CAT, recordados)

    assert estados(analisis) == [(0, E.RECORDADO, "zona"), (1, E.SIN_COINCIDENCIA, None)]


def test_un_recordado_hacia_un_campo_que_ya_no_existe_se_ignora() -> None:
    analisis = analizar(["Zona"], [], CAT, {("zona", 1): "campo_borrado"})

    assert estados(analisis) == [(0, E.COINCIDE, "zona")]


def test_la_coincidencia_toma_el_primer_campo_del_catalogo_y_el_segundo_toma_el_siguiente() -> None:
    # `clave` va antes que `clave_extra`, como `pagare` antes que `pagare_duplicado`.
    analisis = analizar(["Clave", "Clave"], [], CAT, {})

    assert estados(analisis) == [(0, E.COINCIDE, "clave"), (1, E.COINCIDE, "clave_extra")]


def test_pagare_va_antes_que_pagare_duplicado_en_el_catalogo_de_la_sabana() -> None:
    analisis = analizar(["Pagare", "PAGARE"], [], CATALOGO_SABANA, {})

    assert [(c.estado, c.sugerido) for c in analisis.columnas] == [
        (E.COINCIDE, "pagare"),
        (E.COINCIDE, "pagare_duplicado"),
    ]


def test_un_campo_tomado_no_se_sugiere_como_parecido() -> None:
    # `fecha_pago` ya lo tomo la coincidencia exacta: la segunda columna no puede parecerse a el.
    analisis = analizar(["Fecha de pago", "Fecha de pagos"], [], CAT, {})

    assert estados(analisis) == [(0, E.COINCIDE, "fecha_pago"), (1, E.SIN_COINCIDENCIA, None)]


# --- Dos encabezados iguales (M-1) ----------------------------------------------------------------


def test_dos_encabezados_iguales_tienen_ocurrencia_1_y_2() -> None:
    analisis = analizar(["Pagare", "Otro", " PAGARE "], [], CATALOGO_SABANA, {})

    assert [(c.normalizado, c.ocurrencia) for c in analisis.columnas] == [
        ("pagare", 1),
        ("otro", 1),
        ("pagare", 2),
    ]


def _confirmar(analisis) -> dict[tuple[str, int], str | None]:
    """Lo que se recuerda al confirmar sin cambios: una entrada por columna."""
    return {(c.normalizado, c.ocurrencia): c.sugerido for c in analisis.columnas}


def test_los_dos_pagare_confirmados_y_vueltos_a_analizar_dan_pagare_y_pagare_duplicado() -> None:
    cabeceras = ["Pagare", "Zona", "Pagare"]
    primero = analizar(cabeceras, [], CATALOGO_SABANA, {})

    segundo = analizar(cabeceras, [], CATALOGO_SABANA, _confirmar(primero))

    assert [(c.estado, c.sugerido) for c in segundo.columnas][0::2] == [
        (E.RECORDADO, "pagare"),
        (E.RECORDADO, "pagare_duplicado"),
    ]
    sugeridas = [(c.indice, c.sugerido) for c in segundo.columnas]
    assert (0, "pagare") in sugeridas and (2, "pagare_duplicado") in sugeridas


def test_los_dos_pagare_recordados_se_pueden_confirmar_la_segunda_vez() -> None:
    cabeceras = ["Pagare", "Pagare"]
    segundo = analizar(
        cabeceras, [], CATALOGO_SABANA, _confirmar(analizar(cabeceras, [], CATALOGO_SABANA, {}))
    )
    asignaciones = [
        Asignacion(c.indice, c.sugerido, OrigenAsignacion.RECORDADO) for c in segundo.columnas
    ]

    # `pagare` es el unico obligatorio de la sabana: con las dos columnas no falta nada.
    assert [p.codigo for p in validar(asignaciones, segundo)] == []


def test_el_recordado_solo_por_el_normalizado_no_alcanza_para_dos_encabezados_iguales() -> None:
    # Con la ocurrencia, recordar la segunda columna no toca la primera.
    analisis = analizar(["Pagare", "Pagare"], [], CATALOGO_SABANA, {("pagare", 2): None})

    assert estados(analisis) == [(0, E.COINCIDE, "pagare"), (1, E.RECORDADO, None)]


# --- Encabezados vacios y orden ----------------------------------------------------------------


def test_los_encabezados_vacios_no_se_listan_pero_el_indice_se_conserva() -> None:
    analisis = analizar(["Clave", None, "", "   ", "Zona"], [], CAT, {})

    assert [(c.indice, c.sugerido) for c in analisis.columnas] == [(0, "clave"), (4, "zona")]


def test_las_columnas_salen_en_el_orden_del_archivo() -> None:
    analisis = analizar(["Zona", "Clave", "Importe"], [], CAT, {})

    assert [c.indice for c in analisis.columnas] == [0, 1, 2]
    assert [c.encabezado for c in analisis.columnas] == ["Zona", "Clave", "Importe"]


# --- Parecido: umbral y empate -------------------------------------------------------------------


def _con_similitudes(monkeypatch, valores: dict[str, float]) -> None:
    monkeypatch.setattr(
        modulo, "similitud", lambda normalizado, campo: valores.get(campo.nombre, 0.0)
    )


def test_el_umbral_es_inclusivo(monkeypatch) -> None:
    _con_similitudes(monkeypatch, {"zona": UMBRAL_PARECIDO})
    justo = analizar(["Zzxqv"], [], CAT, {})
    _con_similitudes(monkeypatch, {"zona": UMBRAL_PARECIDO - 0.0001})
    debajo = analizar(["Zzxqv"], [], CAT, {})

    assert estados(justo) == [(0, E.PARECIDO, "zona")]
    assert estados(debajo) == [(0, E.SIN_COINCIDENCIA, None)]


def test_el_umbral_y_la_diferencia_de_empate_estan_en_un_solo_lugar() -> None:
    assert (UMBRAL_PARECIDO, DIFERENCIA_DE_EMPATE) == (0.75, 0.02)


def test_dos_candidatos_a_menos_de_la_diferencia_de_empate_no_sugieren_ninguno(monkeypatch) -> None:
    _con_similitudes(monkeypatch, {"zona": 0.90, "monto": 0.89})

    assert estados(analizar(["Zzxqv"], [], CAT, {})) == [(0, E.SIN_COINCIDENCIA, None)]


def test_dos_candidatos_separados_por_mas_de_la_diferencia_sugieren_el_mejor(monkeypatch) -> None:
    _con_similitudes(monkeypatch, {"zona": 0.90, "monto": 0.85})

    assert estados(analizar(["Zzxqv"], [], CAT, {})) == [(0, E.PARECIDO, "zona")]


def test_el_empate_se_decide_con_los_campos_libres(monkeypatch) -> None:
    # `monto` ya esta tomado por la coincidencia: sin el, `zona` no tiene con quien empatar.
    _con_similitudes(monkeypatch, {"zona": 0.90, "monto": 0.90})

    analisis = analizar(["Importe", "Zzxqv"], [], CAT, {})

    assert estados(analisis) == [(0, E.COINCIDE, "monto"), (1, E.PARECIDO, "zona")]


def test_un_empate_real_entre_dos_campos_con_el_mismo_alias_no_sugiere_nada() -> None:
    gemelos = CatalogoCampos("gemelos", (campo("uno", "zona norte"), campo("dos", "zona norte")))

    analisis = analizar(["Zona nort"], [], gemelos, {})

    assert estados(analisis) == [(0, E.SIN_COINCIDENCIA, None)]


def test_los_alias_con_metacaracteres_no_participan_en_la_similitud() -> None:
    # `observacion` solo tiene un alias con expresion regular: se compara contra su nombre.
    analisis = analizar(["Observaciones"], [], CAT, {})

    [columna] = analisis.columnas
    assert (columna.estado, columna.sugerido) == (E.PARECIDO, "observacion")


# --- Ejemplos -----------------------------------------------------------------------------------


def test_los_ejemplos_son_hasta_tres_valores_no_vacios_como_texto() -> None:
    filas = [
        [None, "a", 1],
        ["", "b", 2.5],
        ["  ", "c", None],
        ["x", "d", "z"],
        ["y", "e", "w"],
        ["z", "f", "v"],
    ]

    analisis = analizar(["Uno", "Dos", "Tres"], filas, CAT, {})

    assert [c.ejemplos for c in analisis.columnas] == [
        ("x", "y", "z"),
        ("a", "b", "c"),
        ("1", "2.5", "z"),
    ]
    assert MAXIMO_EJEMPLOS == 3


def test_las_filas_sin_ningun_valor_no_cuentan_para_las_primeras_200() -> None:
    vacias = [[None, ""] for _ in range(FILAS_DE_MUESTRA * 2)]
    con_datos = [["v", None] for _ in range(FILAS_DE_MUESTRA - 1)]

    analisis = analizar(["Uno", "Dos"], [*vacias, *con_datos, [None, "tarde"]], CAT, {})

    # Las 199 filas con datos y la que trae «tarde» son 200: entra.
    assert analisis.columnas[1].ejemplos == ("tarde",)


def test_los_ejemplos_salen_solo_de_las_primeras_200_filas_con_datos() -> None:
    filas = [["v", None] for _ in range(FILAS_DE_MUESTRA)] + [[None, "demasiado tarde"]]

    analisis = analizar(["Uno", "Dos"], filas, CAT, {})

    assert analisis.columnas[1].ejemplos == ()


def test_la_muestra_se_lee_de_a_una_fila_y_se_corta_a_las_200() -> None:
    leidas = 0

    def filas():
        nonlocal leidas
        while True:
            leidas += 1
            yield [None, None, "x"] if leidas % 2 else ["a", None, None]

    analizar(["Uno", "Dos", "Tres"], filas(), CAT, {})

    assert leidas <= FILAS_DE_MUESTRA


def test_una_fila_mas_corta_que_los_encabezados_no_falla() -> None:
    analisis = analizar(["Uno", "Dos", "Tres"], [["a"], []], CAT, {})

    assert [c.ejemplos for c in analisis.columnas] == [("a",), (), ()]


# --- Problemas iniciales --------------------------------------------------------------------------


def test_sin_problemas_si_todo_coincide() -> None:
    assert analizar(["Clave", "Zona"], [], CAT, {}).problemas_iniciales == ()


def test_un_parecido_sin_revisar_es_un_problema_inicial_de_su_columna() -> None:
    analisis = analizar(["Clave", "Fecha de pagos"], [], CAT, {})

    assert [(p.indice, p.codigo, p.campo) for p in analisis.problemas_iniciales] == [
        (1, CodigoMapeo.PARECIDO_SIN_REVISAR, "fecha_pago")
    ]


def test_un_obligatorio_sin_columna_es_un_problema_inicial_sin_indice() -> None:
    analisis = analizar(["Zona"], [], CAT, {})

    [problema] = analisis.problemas_iniciales
    assert (problema.indice, problema.codigo, problema.campo) == (
        None,
        CodigoMapeo.OBLIGATORIO_SIN_COLUMNA,
        "clave",
    )


def test_el_analisis_trae_el_catalogo_con_el_que_se_hizo() -> None:
    analisis = analizar(["Clave"], [], CAT, {})

    assert (analisis.catalogo_id, analisis.campos) == ("prueba", CAT.campos)


# --- Propiedades con semilla -----------------------------------------------------------------

PALABRAS = ["alfa", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta", "iota", "kappa"]


def _catalogo_al_azar(azar: random.Random, cuantos: int) -> CatalogoCampos:
    """Campos con un alias propio cada uno (ninguno coincide con dos), algunos obligatorios."""
    nombres = azar.sample(PALABRAS, cuantos)
    return CatalogoCampos(
        "azar",
        tuple(
            campo(
                f"campo_{n}", f"{n} {azar.choice(['uno', 'dos'])}", obligatorio=azar.random() < 0.3
            )
            for n in nombres
        ),
    )


def _encabezados_al_azar(azar: random.Random, catalogo: CatalogoCampos) -> list[str | None]:
    cabeceras: list[str | None] = []
    for _ in range(azar.randint(1, 9)):
        campo_ = azar.choice(catalogo.campos)
        base = azar.choice([*campo_.alias, campo_.nombre.replace("_", " ")])
        cabeceras.append(
            azar.choice(
                [base, base.upper(), base + "s", base[:-1], "zzz " + base, None, "", "sin relacion"]
            )
        )
    return cabeceras


def _recordados_al_azar(azar, catalogo, cabeceras) -> dict[tuple[str, int], str | None]:
    recordados: dict[tuple[str, int], str | None] = {}
    for cabecera in cabeceras:
        if cabecera and azar.random() < 0.3:
            clave = (cabecera.strip().casefold(), azar.randint(1, 2))
            recordados[clave] = azar.choice([None, *(c.nombre for c in catalogo.campos)])
    return recordados


def test_el_analisis_no_depende_del_orden_de_los_campos_del_catalogo() -> None:
    azar = random.Random(SEMILLA)
    for _ in range(400):
        catalogo = _catalogo_al_azar(azar, azar.randint(2, 6))
        cabeceras = _encabezados_al_azar(azar, catalogo)
        recordados = _recordados_al_azar(azar, catalogo, cabeceras)
        campos = list(catalogo.campos)
        azar.shuffle(campos)

        a = analizar(cabeceras, [], catalogo, recordados)
        b = analizar(cabeceras, [], CatalogoCampos("azar", tuple(campos)), recordados)

        assert a.columnas == b.columnas, (cabeceras, recordados)


def test_cada_campo_se_sugiere_a_lo_sumo_una_vez() -> None:
    azar = random.Random(SEMILLA + 1)
    for _ in range(400):
        catalogo = _catalogo_al_azar(azar, azar.randint(2, 6))
        cabeceras = _encabezados_al_azar(azar, catalogo)
        recordados = _recordados_al_azar(azar, catalogo, cabeceras)

        analisis = analizar(cabeceras, [], catalogo, recordados)

        sugeridos = [c.sugerido for c in analisis.columnas if c.sugerido is not None]
        assert len(sugeridos) == len(set(sugeridos)), (cabeceras, recordados)
        # los estados con un campo siempre lo traen, y solo los parecidos traen similitud
        for c in analisis.columnas:
            assert (c.estado is E.PARECIDO) == (c.similitud is not None)
            if c.estado in (E.COINCIDE, E.PARECIDO):
                assert c.sugerido is not None
            if c.estado is E.SIN_COINCIDENCIA:
                assert c.sugerido is None


def test_el_analisis_es_el_mismo_las_veces_que_se_repita() -> None:
    cabeceras = ["Clave", "Fecha de pagos", "Zzxqv", None, "Importe"]

    assert analizar(cabeceras, [], CAT, {}) == analizar(cabeceras, [], CAT, {})


@pytest.mark.parametrize("cuantas", [0, 1, 3])
def test_un_archivo_sin_encabezados_validos_no_lista_columnas(cuantas) -> None:
    analisis = analizar([None] * cuantas, [], CAT, {})

    assert analisis.columnas == ()
    assert codigos(analisis.problemas_iniciales) == [CodigoMapeo.OBLIGATORIO_SIN_COLUMNA]


# --- Parecidos: mejor primero, no de izquierda a derecha ------------------------------------------


def _con_tabla(monkeypatch, tabla: dict[tuple[str, str], float]) -> None:
    monkeypatch.setattr(
        modulo, "similitud", lambda normalizado, campo: tabla.get((normalizado, campo.nombre), 0.0)
    )


def test_el_parecido_de_mayor_similitud_se_queda_el_campo_aunque_este_mas_a_la_derecha(
    monkeypatch,
) -> None:
    # La columna 2 se parece 0,76 a `monto`; la 9, 0,95. Gana la 9, no la primera que pasa.
    cabeceras = [f"col{i}" for i in range(10)]
    _con_tabla(monkeypatch, {("col2", "monto"): 0.76, ("col9", "monto"): 0.95})

    analisis = analizar(cabeceras, [], CAT, {})

    por_indice = {c.indice: c for c in analisis.columnas}
    assert (por_indice[9].estado, por_indice[9].sugerido, por_indice[9].similitud) == (
        E.PARECIDO,
        "monto",
        0.95,
    )
    assert (por_indice[2].estado, por_indice[2].sugerido) == (E.SIN_COINCIDENCIA, None)


def test_la_columna_que_pierde_un_campo_toma_el_siguiente_si_lo_supera_el_umbral(
    monkeypatch,
) -> None:
    _con_tabla(
        monkeypatch,
        {("col2", "monto"): 0.76, ("col9", "monto"): 0.95, ("col2", "zona"): 0.80},
    )

    analisis = analizar([f"col{i}" for i in range(10)], [], CAT, {})

    por_indice = {c.indice: c.sugerido for c in analisis.columnas}
    assert (por_indice[9], por_indice[2]) == ("monto", "zona")


def test_a_igual_similitud_gana_la_columna_de_menor_indice(monkeypatch) -> None:
    _con_tabla(monkeypatch, {("uno", "monto"): 0.9, ("dos", "monto"): 0.9})

    analisis = analizar(["Dos", "Uno"], [], CAT, {})

    # `dos` esta en la columna 0 y `uno` en la 1: la columna 0 se queda `monto`.
    assert [(c.normalizado, c.sugerido) for c in analisis.columnas] == [
        ("dos", "monto"),
        ("uno", None),
    ]


def test_el_empate_se_mide_entre_los_campos_libres_en_el_momento_de_asignar(monkeypatch) -> None:
    # La columna 0 se parece 0,90 a `zona`, 0,80 a `monto` y 0,795 a `fecha_pago`: sola, se queda
    # `zona`. Pero la columna 1 (0,95 a `zona`) la toma antes; entonces sus dos mejores libres son
    # `monto` y `fecha_pago`, que empatan: la columna 0 queda sin sugerencia y sin tomar nada.
    tabla = {
        ("a", "zona"): 0.90,
        ("a", "monto"): 0.80,
        ("a", "fecha_pago"): 0.795,
        ("b", "zona"): 0.95,
    }
    _con_tabla(monkeypatch, tabla)

    sola = analizar(["A"], [], CAT, {})
    juntas = analizar(["A", "B"], [], CAT, {})

    assert estados(sola) == [(0, E.PARECIDO, "zona")]
    assert estados(juntas) == [(0, E.SIN_COINCIDENCIA, None), (1, E.PARECIDO, "zona")]


def test_la_columna_que_empata_no_toma_ningun_campo(monkeypatch) -> None:
    _con_tabla(monkeypatch, {("a", "zona"): 0.9, ("a", "monto"): 0.9, ("b", "monto"): 0.8})

    analisis = analizar(["A", "B"], [], CAT, {})

    # `a` empata entre `zona` y `monto` y se queda sin nada; `monto` queda libre para `b`.
    assert estados(analisis) == [(0, E.SIN_COINCIDENCIA, None), (1, E.PARECIDO, "monto")]


def _typo(azar: random.Random, palabra: str) -> str:
    return azar.choice([palabra + "s", palabra[:-1], palabra + "x", "x" + palabra])


def test_permutar_las_columnas_no_cambia_el_campo_de_cada_encabezado_parecido() -> None:
    azar = random.Random(SEMILLA + 5)
    ejercidos = 0
    for _ in range(600):
        catalogo = _catalogo_al_azar(azar, azar.randint(2, 6))
        alias = [a for c in catalogo.campos for a in c.alias]
        cabeceras = list(
            dict.fromkeys(_typo(azar, azar.choice(alias)) for _ in range(azar.randint(2, 8)))
        )
        normalizados = [h.casefold() for h in cabeceras]
        if any(coincide(n, c) for n in normalizados for c in catalogo.campos):
            continue
        if _hay_empate_exacto_entre_columnas(normalizados, catalogo):
            continue
        permutadas = list(cabeceras)
        azar.shuffle(permutadas)

        a = analizar(cabeceras, [], catalogo, {})
        b = analizar(permutadas, [], catalogo, {})

        por_encabezado = lambda analisis: {  # noqa: E731
            c.normalizado: (c.estado, c.sugerido, c.similitud) for c in analisis.columnas
        }
        assert por_encabezado(a) == por_encabezado(b), (cabeceras, permutadas)
        ejercidos += sum(c.estado is E.PARECIDO for c in a.columnas)
    assert ejercidos > 300  # hay parecidos de verdad en las muestras


def _hay_empate_exacto_entre_columnas(normalizados: list[str], catalogo: CatalogoCampos) -> bool:
    """Dos columnas con exactamente la misma similitud (sobre el umbral) hacia un mismo campo: el
    indice desempata, y por eso la permutacion si puede cambiar el resultado."""
    for campo_ in catalogo.campos:
        valores = [similitud(n, campo_) for n in normalizados]
        valores = [v for v in valores if v >= UMBRAL_PARECIDO]
        if len(valores) != len(set(valores)):
            return True
    return False


# --- Que es «vacio» -------------------------------------------------------------------------------


def test_el_mapeador_lista_un_encabezado_null_como_cualquier_otro() -> None:
    analisis = analizar(["Clave", "NULL"], [], CAT, {})

    assert estados(analisis) == [(0, E.COINCIDE, "clave"), (1, E.SIN_COINCIDENCIA, None)]


def test_un_consumidor_puede_pasar_su_propio_criterio_de_vacio() -> None:
    from app.core.services.ingesta_sabana.reglas import es_vacio as vacio_de_la_sabana

    analisis = analizar(
        ["Clave", "NULL", "Zona"],
        [["x", "NULL", "y"], ["NULL", "NULL", "z"]],
        CAT,
        {},
        vacio=vacio_de_la_sabana,
    )

    assert [(c.indice, c.ejemplos) for c in analisis.columnas] == [(0, ("x",)), (2, ("y", "z"))]


def test_con_el_criterio_de_la_sabana_se_listan_las_mismas_columnas_que_en_el_viejo() -> None:
    from app.core.services.ingesta_sabana.cabeceras import mapear_cabeceras
    from app.core.services.ingesta_sabana.catalogo import CATALOGO_SABANA
    from app.core.services.ingesta_sabana.reglas import es_vacio as vacio_de_la_sabana

    cabeceras = ["Pagare", "NULL", "", None, "Zona libre"]

    analisis = analizar(cabeceras, [], CATALOGO_SABANA, {}, vacio=vacio_de_la_sabana)
    viejo = mapear_cabeceras(cabeceras)

    listadas = {c.indice for c in analisis.columnas}
    assert listadas == set(viejo.columnas) | set(viejo.desconocidas)

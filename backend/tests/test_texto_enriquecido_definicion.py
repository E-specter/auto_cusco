"""La definicion de carga como JSON, su diagnostico y el detalle por fila (B4a).

Son las piezas que la previsualizacion une: `definicion_desde_dict` lee la forma JSON sin reventar
con lo imposible, `diagnosticar` junta todos los problemas de compilacion con su columna y su
variante, y `detallar_fila` da, para una fila, lo mismo que `generar_fila` mas lo que necesita la
interfaz (segmento, texto por nodo, cota).
"""

import random
from datetime import date
from decimal import Decimal

import pytest

from app.core.entities.mapeo import CampoSalida, DefinicionCarga, TipoSalida, VarianteCampo
from app.core.entities.segmentacion import (
    TABLA_RANGOS_POR_DEFECTO,
    CriterioCalculado,
    CriterioCampo,
    PoliticaSinSegmento,
    Segmentacion,
)
from app.core.entities.texto_enriquecido import (
    CodigoTexto,
    Expresion,
    LlamadaFuncion,
    NodoTexto,
    NodoVariable,
    TipoValor,
)
from app.core.services.mapeo_campos.diagnostico import diagnosticar
from app.core.services.mapeo_campos.generador import GeneradorCargas
from app.core.services.mapeo_campos.serializacion import (
    DefinicionIlegible,
    ProblemaDeDefinicion,
    definicion_desde_dict,
)

VARIABLES = {
    "titular": TipoValor.TEXTO,
    "saldo": TipoValor.NUMERO,
    "vence": TipoValor.FECHA,
    "dias_atraso": TipoValor.NUMERO,
    "region": TipoValor.TEXTO,
}


def _leer(dato):
    return definicion_desde_dict(dato, TABLA_RANGOS_POR_DEFECTO, "dias_atraso")


def _problemas(dato) -> tuple[ProblemaDeDefinicion, ...]:
    with pytest.raises(DefinicionIlegible) as error:
        _leer(dato)
    return error.value.problemas


def _ubicaciones(dato) -> set[tuple]:
    return {(p.columna, p.segmento, p.campo) for p in _problemas(dato)}


# --- Lectura ------------------------------------------------------------------------------------

VACIA = {"nodos": []}


def _col(nombre: str = "a", orden: int = 0, **extra) -> dict:
    return {"nombre": nombre, "orden": orden, "expresion": VACIA, **extra}


def _def(*columnas: dict, **extra) -> dict:
    return {"columnas": list(columnas), **extra}


def test_una_definicion_minima_se_lee_con_los_valores_por_defecto() -> None:
    leida = _leer(_def(_col()))

    assert leida.definicion.nombre == ""
    assert leida.definicion.segmentacion is None
    assert leida.definicion.proteger_formulas is True
    assert leida.definicion.campos == (CampoSalida("a", "", expresion=Expresion()),)
    assert leida.posiciones == (0,)


def test_una_definicion_completa_se_lee_en_sus_entidades() -> None:
    leida = _leer(
        {
            "nombre": "SMS",
            "proteger_formulas": False,
            "columnas": [
                {
                    "nombre": "m",
                    "orden": 3,
                    "expresion": {"nodos": [{"tipo": "texto", "valor": "x"}]},
                    "tipo": "financiero",
                    "formato_financiero": {"separador_miles": ".", "decimales": 0},
                    "valor_por_defecto": "0",
                    "variantes": [
                        {
                            "segmento": "1_a_8",
                            "expresion": {"nodos": [{"tipo": "texto", "valor": "hola"}]},
                        }
                    ],
                },
                _col("f", 4, tipo="fecha", formato_fecha="dd/mm/aaaa"),
            ],
            "segmentacion": {
                "criterio": {"tipo": "campo", "campo": "region"},
                "politica": "usar_por_defecto",
            },
        }
    )

    definicion = leida.definicion
    assert (definicion.nombre, definicion.proteger_formulas) == ("SMS", False)
    campo, fecha = definicion.campos
    assert campo.tipo is TipoSalida.FINANCIERO
    assert campo.expresion == Expresion((NodoTexto("x"),))
    assert (campo.formato_financiero.separador_miles, campo.formato_financiero.decimales) == (
        ".",
        0,
    )
    assert campo.valor_por_defecto == "0"
    assert campo.variantes == (VarianteCampo("1_a_8", None, Expresion((NodoTexto("hola"),))),)
    assert (fecha.patron_fecha, fecha.formato_fecha) == ("dd/mm/aaaa", None)
    assert definicion.segmentacion == Segmentacion(
        CriterioCampo("region"), PoliticaSinSegmento.USAR_POR_DEFECTO
    )


def test_las_columnas_salen_ordenadas_por_su_orden_y_se_recuerda_su_posicion_en_el_pedido() -> None:
    leida = _leer(_def(_col("c", 20), _col("a", 0), _col("b", 7)))

    assert [c.nombre for c in leida.definicion.campos] == ["a", "b", "c"]
    assert leida.posiciones == (1, 2, 0)


def test_la_segmentacion_vacia_o_calculada_sin_tabla_usa_la_del_contexto() -> None:
    tabla = TABLA_RANGOS_POR_DEFECTO[:2]

    vacia = definicion_desde_dict(_def(_col(), segmentacion={}), tabla, "dias")
    calculada = definicion_desde_dict(
        _def(_col(), segmentacion={"criterio": {"tipo": "calculado"}}), tabla, "dias"
    )

    esperada = Segmentacion(CriterioCalculado(tabla, "dias"), PoliticaSinSegmento.EXCLUIR)
    assert vacia.definicion.segmentacion == calculada.definicion.segmentacion == esperada


def test_una_tabla_propia_en_la_definicion_manda_sobre_la_del_contexto() -> None:
    leida = _leer(
        _def(
            _col(),
            segmentacion={
                "criterio": {
                    "tipo": "calculado",
                    "variable_dias": "otros",
                    "tabla": [{"clave": "a", "etiqueta": "A", "desde": None, "hasta": 3}],
                }
            },
        )
    )

    criterio = leida.definicion.segmentacion.criterio  # type: ignore[union-attr]
    assert criterio.variable_dias == "otros"
    assert [(r.clave, r.desde, r.hasta) for r in criterio.tabla] == [("a", None, 3)]


def _segmentada(**segmentacion) -> dict:
    return _def(_col(), segmentacion=segmentacion)


@pytest.mark.parametrize(
    ("dato", "esperadas"),
    [
        (None, {(None, None, "definicion")}),
        ([], {(None, None, "definicion")}),
        ({"columnas": "x"}, {(None, None, "columnas")}),
        ({"campos": []}, {(None, None, "definicion"), (None, None, "columnas")}),
        ({"columnas": [], "otra": 1}, {(None, None, "definicion")}),
        ({"columnas": [], "nombre": 5}, {(None, None, "nombre")}),
        ({"columnas": [], "proteger_formulas": "si"}, {(None, None, "proteger_formulas")}),
        (_def(5), {(0, None, None)}),
        (_def(_col(), {"orden": 1, "expresion": VACIA}), {(1, None, "nombre")}),
        (_def(_col(nombre="")), {(0, None, "nombre")}),
        (_def(_col(nombre="   ")), {(0, None, "nombre")}),
        (_def(_col(nombre=5)), {(0, None, "nombre")}),
        (_def(_col("a", 0), _col("a", 1)), {(1, None, "nombre")}),
        (_def({"nombre": "a", "expresion": VACIA}), {(0, None, "orden")}),
        (_def(_col(orden=True)), {(0, None, "orden")}),
        (_def(_col(orden=-1)), {(0, None, "orden")}),
        (_def(_col(orden="1")), {(0, None, "orden")}),
        (_def(_col("a", 4), _col("b", 4)), {(1, None, "orden")}),
        (_def(_col(tipo="raro")), {(0, None, "tipo")}),
        (_def(_col(extra=1)), {(0, None, None)}),
        (_def({"nombre": "a", "orden": 0}), {(0, None, "expresion")}),
        (_def(_col(expresion=None)), {(0, None, "expresion")}),
        (_def(_col(plantilla="x")), {(0, None, None)}),  # ya no hay plantilla: solo expresion
        (_def(_col(valor_por_defecto=3)), {(0, None, "valor_por_defecto")}),
        (_def(_col(formato_fecha=5)), {(0, None, "formato_fecha")}),
        (_def(_col(formato_fecha="solo texto")), {(0, None, "formato_fecha")}),
        (_def(_col(formato_financiero={"decimales": 9})), {(0, None, "formato_financiero")}),
        (_def(_col(formato_financiero={"decimales": True})), {(0, None, "formato_financiero")}),
        (
            _def(_col(formato_financiero={"separador_miles": "ab"})),
            {(0, None, "formato_financiero")},
        ),
        (
            _def(_col(formato_financiero={"separador_decimal": ""})),
            {(0, None, "formato_financiero")},
        ),
        (_def(_col(formato_financiero={"otra": 1})), {(0, None, "formato_financiero")}),
        (_def(_col(formato_financiero=3)), {(0, None, "formato_financiero")}),
        (_def(_col(variantes=3)), {(0, None, "variantes")}),
        (_def(_col(variantes=[3])), {(0, None, "variantes")}),
        (_def(_col(variantes=[{"expresion": VACIA}])), {(0, None, "variantes")}),
        (_def(_col(variantes=[{"segmento": "", "expresion": VACIA}])), {(0, None, "variantes")}),
        (_def(_col(variantes=[{"segmento": "s"}])), {(0, "s", "expresion")}),
        (
            _def(_col(variantes=[{"segmento": "s", "expresion": VACIA, "otra": 1}])),
            {(0, "s", None)},
        ),
        (
            _def(_col(variantes=[{"segmento": "s", "plantilla": "x"}])),
            {(0, "s", None), (0, "s", "expresion")},
        ),
        (_def(_col(variantes=[{"segmento": "s", "expresion": {"nodos": [{}]}}])), {(0, "s", None)}),
        (_def(_col(), segmentacion=3), {(None, None, "segmentacion")}),
        (_segmentada(otra=1), {(None, None, "segmentacion")}),
        (_segmentada(criterio={"tipo": "raro"}), {(None, None, "segmentacion")}),
        (_segmentada(criterio={"tipo": "campo"}), {(None, None, "segmentacion")}),
        (
            _segmentada(criterio={"tipo": "campo", "campo": "x", "otra": 1}),
            {(None, None, "segmentacion")},
        ),
        (
            _segmentada(criterio={"tipo": "calculado", "tabla": [{"clave": 1}]}),
            {(None, None, "segmentacion")},
        ),
        (
            _segmentada(
                criterio={
                    "tipo": "calculado",
                    "tabla": [{"clave": "a", "etiqueta": "A", "desde": "x"}],
                }
            ),
            {(None, None, "segmentacion")},
        ),
        (
            _segmentada(
                criterio={
                    "tipo": "calculado",
                    "tabla": [{"clave": "a", "etiqueta": "A", "desde": True}],
                }
            ),
            {(None, None, "segmentacion")},
        ),
        (_segmentada(politica="nunca"), {(None, None, "segmentacion")}),
    ],
)
def test_lo_imposible_es_definicion_invalida_con_su_ubicacion(dato, esperadas) -> None:
    problemas = _problemas(dato)

    assert {p.problema.codigo for p in problemas} <= {
        CodigoTexto.DEFINICION_INVALIDA,
        CodigoTexto.EXPRESION_INVALIDA,
        CodigoTexto.PARAMETRO_INVALIDO,
    }
    assert {(p.columna, p.segmento, p.campo) for p in problemas} == esperadas


def test_el_formato_de_fecha_sin_ninguna_marca_es_parametro_invalido_de_su_columna() -> None:
    [problema] = _problemas(_def(_col("a", 0), _col("f", 1, formato_fecha="%d/%m/%Y")))

    assert problema.problema.codigo is CodigoTexto.PARAMETRO_INVALIDO
    assert problema.problema.parametro == "formato_fecha"
    assert (problema.columna, problema.campo) == (1, "formato_fecha")


def test_el_formato_de_fecha_con_una_sola_marca_es_valido_y_el_vacio_es_no_tenerlo() -> None:
    leida = _leer(
        _def(_col("a", 0, formato_fecha="aaaa"), _col("b", 1, formato_fecha=""), _col("c", 2))
    )

    assert [c.patron_fecha for c in leida.definicion.campos] == ["aaaa", None, None]


def test_una_columna_recien_creada_da_un_problema_ubicado_y_no_un_error() -> None:
    """El constructor agrega una columna con nombre vacio y expresion vacia antes de nombrarla."""
    problemas = _problemas(_def(_col("a", 0), {"nombre": "", "orden": 1, "expresion": VACIA}))

    assert [(p.problema.codigo, p.columna, p.campo) for p in problemas] == [
        (CodigoTexto.DEFINICION_INVALIDA, 1, "nombre")
    ]


def test_una_expresion_vacia_no_es_un_problema() -> None:
    assert _leer(_def(_col("a", 0))).definicion.campos[0].expresion == Expresion()


def test_todos_los_problemas_se_informan_juntos_y_no_solo_el_primero() -> None:
    dato = _def(
        _col("a", 0, tipo="raro"),
        _col("b", 1, valor_por_defecto=1),
        _col("c", 2, expresion={"nodos": [{"tipo": "texto"}, {"tipo": "x"}]}),
        segmentacion={"politica": "nunca"},
    )

    ubicaciones = [(p.columna, p.campo, p.problema.nodo) for p in _problemas(dato)]

    assert ubicaciones == [
        (0, "tipo", None),
        (1, "valor_por_defecto", None),
        (2, None, 0),
        (2, None, 1),
        (None, "segmentacion", None),
    ]


def test_un_problema_de_la_expresion_de_una_columna_trae_su_nodo_y_su_columna() -> None:
    dato = _def(_col("a", 0), _col("b", 1, expresion={"nodos": [{"tipo": "texto", "valor": 3}]}))

    [problema] = _problemas(dato)

    assert (problema.columna, problema.problema.nodo) == (1, 0)
    assert problema.problema.codigo is CodigoTexto.EXPRESION_INVALIDA


def test_la_posicion_de_un_problema_es_la_del_pedido_aunque_el_orden_cambie_las_columnas() -> None:
    dato = _def(_col("c", 9), _col("a", 0, tipo="raro"), _col("b", 5))

    assert [p.columna for p in _problemas(dato)] == [1]


# --- Formato de fecha con marcas ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("patron", "esperado"),
    [
        ("dd/mm/aaaa", "05/10/2026"),
        ("aaaa-mm-dd", "2026-10-05"),
        ("dd de nombre_mes de aaaa", "05 de octubre de 2026"),
        ("dd/mm/aa", "05/10/26"),
        ("mm/aaaa", "10/2026"),
    ],
)
def test_una_columna_de_fecha_se_escribe_con_las_marcas_como_formato_fecha_del_motor(
    patron, esperado
) -> None:
    from app.core.services.mapeo_campos import formatos

    campo = CampoSalida("f", "", TipoSalida.FECHA, patron_fecha=patron)

    assert formatos.convertir(campo, "2026-10-05", date(2026, 10, 5)) == esperado


def test_el_patron_de_marcas_manda_sobre_el_strftime() -> None:
    from app.core.services.mapeo_campos import formatos

    campo = CampoSalida("f", "", TipoSalida.FECHA, formato_fecha="%Y", patron_fecha="dd/mm/aaaa")

    assert formatos.convertir(campo, "2026-10-05", date(2026, 10, 5)) == "05/10/2026"


def test_sin_patron_de_marcas_el_strftime_de_siempre_sigue_igual() -> None:
    from app.core.services.mapeo_campos import formatos

    campo = CampoSalida("f", "", TipoSalida.FECHA, formato_fecha="%d/%m/%Y")

    assert formatos.convertir(campo, "2026-10-05", date(2026, 10, 5)) == "05/10/2026"


# --- Diagnostico --------------------------------------------------------------------------------


def _variable(nombre: str, *funciones: LlamadaFuncion) -> Expresion:
    return Expresion((NodoVariable(nombre, funciones),))


def test_una_definicion_valida_no_tiene_problemas() -> None:
    definicion = DefinicionCarga(
        "d",
        (
            CampoSalida("a", "[@titular | mayusculas]"),
            CampoSalida("b", "", expresion=_variable("saldo")),
        ),
        Segmentacion(),
    )

    assert diagnosticar(definicion, VARIABLES) == ()


def test_el_diagnostico_junta_los_problemas_de_todas_las_columnas_y_variantes() -> None:
    definicion = DefinicionCarga(
        "d",
        (
            CampoSalida("ok", "[@titular]"),
            CampoSalida("mal", "[@inventada]"),
            CampoSalida(
                "variante",
                "[@titular]",
                variantes=(
                    VarianteCampo(
                        "1_a_8", None, _variable("titular", LlamadaFuncion("primeros", (0,)))
                    ),
                    VarianteCampo("9_a_30", "[@otra]"),
                ),
            ),
        ),
        Segmentacion(),
    )

    problemas = diagnosticar(definicion, VARIABLES)

    assert [(p.columna, p.segmento, p.problema.codigo) for p in problemas] == [
        (1, None, CodigoTexto.VARIABLE_DESCONOCIDA),
        (2, "1_a_8", CodigoTexto.PARAMETRO_INVALIDO),
        (2, "9_a_30", CodigoTexto.VARIABLE_DESCONOCIDA),
    ]
    assert problemas[1].problema.funcion == 0
    assert problemas[1].problema.parametro == "n"


def test_una_plantilla_mal_escrita_es_sintaxis_invalida_en_su_columna() -> None:
    definicion = DefinicionCarga("d", (CampoSalida("a", "x"), CampoSalida("b", "[@titular")))

    [problema] = diagnosticar(definicion, VARIABLES)

    assert (problema.columna, problema.problema.codigo) == (1, CodigoTexto.SINTAXIS_INVALIDA)


def test_las_plantillas_largas_conservan_sus_limites_crecientes_en_el_diagnostico() -> None:
    larga = "x" * 6000  # mas que `largo_literal`: una plantilla (RF-54) no se rechaza por eso

    assert diagnosticar(DefinicionCarga("d", (CampoSalida("a", larga),)), VARIABLES) == ()
    explicita = CampoSalida("a", "", expresion=Expresion((NodoTexto(larga),)))
    [problema] = diagnosticar(DefinicionCarga("d", (explicita,)), VARIABLES)
    assert problema.problema.codigo is CodigoTexto.LIMITE_EXCEDIDO


@pytest.mark.parametrize(
    "definicion",
    [
        DefinicionCarga("d", ()),
        DefinicionCarga("d", (CampoSalida("a", "x"), CampoSalida("a", "y"))),
        DefinicionCarga("d", (CampoSalida("", "x"),)),
        DefinicionCarga("d", (CampoSalida("a", "x", variantes=(VarianteCampo("1_a_8", "y"),)),)),
        DefinicionCarga(
            "d",
            (CampoSalida("a", "x", variantes=(VarianteCampo("no_es_rango", "y"),)),),
            Segmentacion(),
        ),
        DefinicionCarga(
            "d", (CampoSalida("a", "x"),), Segmentacion(CriterioCalculado(variable_dias="nada"))
        ),
    ],
)
def test_lo_que_el_generador_rechaza_es_definicion_invalida_de_toda_la_definicion(
    definicion,
) -> None:
    problemas = diagnosticar(definicion, VARIABLES)

    assert [(p.columna, p.campo, p.problema.codigo) for p in problemas] == [
        (None, "definicion", CodigoTexto.DEFINICION_INVALIDA)
    ]


def test_el_diagnostico_vacio_es_exactamente_cuando_el_generador_acepta() -> None:
    definiciones = [
        DefinicionCarga("d", (CampoSalida("a", "[@titular | primeros(2)]"),), Segmentacion()),
        DefinicionCarga("d", (CampoSalida("a", "[@nada]"),)),
        DefinicionCarga("d", ()),
        DefinicionCarga(
            "d", (CampoSalida("a", "x", variantes=(VarianteCampo("zz", "y"),)),), Segmentacion()
        ),
    ]

    for definicion in definiciones:
        try:
            GeneradorCargas(definicion, VARIABLES)
            acepta = True
        except Exception:
            acepta = False
        assert (diagnosticar(definicion, VARIABLES) == ()) is acepta


# --- Detalle por fila ---------------------------------------------------------------------------


DEFINICION = DefinicionCarga(
    "d",
    (
        CampoSalida(
            "mensaje",
            "[@titular | primeros(5)]",
            variantes=(VarianteCampo("1_a_8", "pronto [@titular]"),),
        ),
        CampoSalida("monto", "[@saldo]", TipoSalida.FINANCIERO, valor_por_defecto="0"),
        CampoSalida("vence", "[@vence]", TipoSalida.FECHA, formato_fecha="%d/%m/%Y"),
        CampoSalida("n", "[@saldo]", TipoSalida.NUMERO),
        CampoSalida("raro", "[@titular]", TipoSalida.NUMERO),
        CampoSalida("fijo", "1010"),
    ),
    Segmentacion(politica=PoliticaSinSegmento.USAR_POR_DEFECTO),
)


def _producto(azar: random.Random) -> dict:
    return {
        "titular": azar.choice(["UNO", "TITULAR/SINTETICO,DOS", "", None, "  "]),
        "saldo": azar.choice([Decimal("1500.5"), Decimal("3"), 7, None]),
        "vence": azar.choice([date(2026, 9, 18), None]),
        "dias_atraso": azar.choice([None, -3, 0, 1, 8, 9, 45, 120, 121, "x"]),
        "region": "CUSCO",
    }


def test_el_detalle_de_una_fila_da_las_mismas_celdas_y_errores_que_la_generacion() -> None:
    azar = random.Random(20261001)
    generador = GeneradorCargas(DEFINICION, VARIABLES)

    for numero in range(1, 301):
        producto = _producto(azar)
        fila, errores = generador.generar_fila(producto, numero)
        detalle = generador.detallar_fila(producto, numero)

        assert detalle.exclusion is None
        assert {c.campo.nombre: c.valor for c in detalle.celdas} == fila
        previstos = [(c.campo.nombre, p.detalle) for c in detalle.celdas for p in c.problemas]
        assert previstos == [(e.campo, e.detalle) for e in errores]


def test_el_detalle_informa_el_segmento_y_si_la_celda_uso_su_variante() -> None:
    generador = GeneradorCargas(DEFINICION, VARIABLES)

    en_rango = generador.detallar_fila({"titular": "UNO", "dias_atraso": 5}, 1)
    fuera = generador.detallar_fila({"titular": "UNO", "dias_atraso": 500}, 1)

    assert (en_rango.segmento, [c.usa_variante for c in en_rango.celdas][:2]) == (
        "1_a_8",
        [True, False],
    )
    assert en_rango.celdas[0].texto == "pronto UNO"
    assert fuera.segmento is None and not any(c.usa_variante for c in fuera.celdas)


def test_el_detalle_excluye_como_la_generacion_cuando_la_politica_es_excluir() -> None:
    definicion = DefinicionCarga("d", DEFINICION.campos, Segmentacion())
    generador = GeneradorCargas(definicion, VARIABLES)

    detalle = generador.detallar_fila({"titular": "UNO", "dias_atraso": 500}, 3)

    assert detalle.celdas == ()
    assert (detalle.exclusion.fila, detalle.exclusion.codigo) == (3, "sin_segmento")  # type: ignore[union-attr]
    assert generador.generar_fila({"titular": "UNO", "dias_atraso": 500}, 3) == (None, [])


def test_una_celda_con_valor_por_defecto_trae_el_texto_ya_aplicado() -> None:
    generador = GeneradorCargas(DEFINICION, VARIABLES)

    celda = generador.detallar_fila({"titular": "UNO", "saldo": None, "dias_atraso": 5}, 1).celdas[
        1
    ]

    assert (celda.texto, celda.valor) == ("0", "0.00")


def test_la_cota_y_el_motivo_viajan_por_celda() -> None:
    generador = GeneradorCargas(DEFINICION, VARIABLES)

    celdas = generador.detallar_fila({"titular": "UNO", "dias_atraso": 500}, 1).celdas

    assert celdas[0].cota == 5 and celdas[0].motivo_sin_cota is None
    assert celdas[5].cota == 4
    assert (
        celdas[1].cota is None and celdas[1].motivo_sin_cota.codigo is CodigoTexto.SIN_COTA_VARIABLE
    )  # type: ignore[union-attr]


def test_cada_celda_trae_la_cota_de_su_contenido_y_no_la_del_de_la_columna() -> None:
    definicion = DefinicionCarga(
        "d",
        (
            CampoSalida(
                "m",
                "[@titular | primeros(2)]",
                variantes=(VarianteCampo("1_a_8", "[@titular]"),),
            ),
        ),
        Segmentacion(),
    )
    generador = GeneradorCargas(definicion, VARIABLES)

    por_defecto = generador.detallar_fila({"titular": "UNO", "dias_atraso": 20}, 1).celdas[0]
    variante = generador.detallar_fila({"titular": "UNO", "dias_atraso": 5}, 1).celdas[0]

    assert (por_defecto.cota, por_defecto.motivo_sin_cota) == (2, None)
    assert variante.cota is None
    assert variante.motivo_sin_cota.codigo is CodigoTexto.SIN_COTA_VARIABLE  # type: ignore[union-attr]

"""Columnas dinamicas y segmentacion en `GeneradorCargas` (B2, RF-42, RF-49, RF-50).

Una columna puede llevar una expresion del motor (o una plantilla con tuberias), un valor por
defecto y contenidos por segmento; la definicion declara el criterio de segmentacion y que hacer
con un producto sin segmento. Todo opcional: sin ello nada cambia (ver test_generador_paridad.py).
Datos sinteticos.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.core.entities.mapeo import (
    CampoSalida,
    DefinicionCarga,
    PlantillaInvalida,
    TipoSalida,
    VarianteCampo,
)
from app.core.entities.segmentacion import (
    CriterioCalculado,
    CriterioCampo,
    PoliticaSinSegmento,
    RangoDias,
    Segmentacion,
)
from app.core.entities.texto_enriquecido import (
    CodigoTexto,
    Expresion,
    LlamadaFuncion,
    NodoTexto,
    NodoVariable,
)
from app.core.services.mapeo_campos.generador import GeneradorCargas

T, N, F, FIN = TipoSalida.TEXTO, TipoSalida.NUMERO, TipoSalida.FECHA, TipoSalida.FINANCIERO

CAMPOS = {
    "pagare": "texto",
    "titular": "texto",
    "telefono": "texto",
    "saldo": "numero",
    "vence": "fecha",
    "dias_atraso": "numero",
    "dias_atraso_ajustados": "numero",
    "segmento_financiero": "texto",
}


def _definicion(*campos, segmentacion=None, nombre="d") -> DefinicionCarga:
    return DefinicionCarga(nombre, tuple(campos), segmentacion)


def _generar(definicion, *productos, campos=CAMPOS):
    return GeneradorCargas(definicion, campos).generar(productos)


def _producto(**cambios) -> dict:
    datos = {
        "pagare": "P1",
        "titular": "Ana Quispe",
        "telefono": "900000001",
        "saldo": Decimal("1500.5"),
        "vence": date(2026, 9, 18),
        "dias_atraso": 4,
    }
    return {**datos, **cambios}


# --- Expresiones y funciones ------------------------------------------------------------------


def test_una_columna_puede_traer_su_expresion_en_lugar_de_la_plantilla() -> None:
    expresion = Expresion(
        (
            NodoVariable("titular", (LlamadaFuncion("primeros", (3,)),)),
            NodoTexto(" [@ no es variable"),
        )
    )

    carga = _generar(_definicion(CampoSalida("c", "", expresion=expresion)), _producto())

    assert carga.filas[0]["c"] == "Ana [@ no es variable"


def test_la_expresion_manda_sobre_la_plantilla() -> None:
    expresion = Expresion((NodoTexto("de la expresion"),))

    carga = _generar(_definicion(CampoSalida("c", "[@titular]", expresion=expresion)), _producto())

    assert carga.filas[0]["c"] == "de la expresion"


def test_una_plantilla_admite_funciones_con_tuberia() -> None:
    definicion = _definicion(
        CampoSalida("corto", "[@titular | primeros(3) | mayusculas]"),
        CampoSalida("vence", '[@vence | sumar_dias(3) | formato_fecha("dd/mm/aaaa")]'),
    )

    fila = _generar(definicion, _producto()).filas[0]

    assert fila == {"corto": "ANA", "vence": "21/09/2026"}


def test_una_columna_de_una_sola_variable_con_funciones_conserva_el_tipo_final() -> None:
    definicion = _definicion(
        CampoSalida("fecha", "[@vence | sumar_dias(3)]", F),
        CampoSalida("fecha_con_formato", "[@vence | sumar_dias(3)]", F, formato_fecha="%d/%m/%Y"),
        CampoSalida("monto", "[@saldo | redondear(0)]", N),
        CampoSalida("financiero", "[@saldo | multiplicar(2)]", FIN),
    )

    fila = _generar(definicion, _producto()).filas[0]

    assert fila["fecha"] == date(2026, 9, 21)  # D11: sigue siendo fecha nativa
    assert fila["fecha_con_formato"] == "21/09/2026"
    assert fila["monto"] == 1501 and isinstance(fila["monto"], int)
    assert fila["financiero"] == "3,001.00"


def test_las_funciones_se_comprueban_al_compilar_y_no_por_fila() -> None:
    definicion = _definicion(CampoSalida("c", '[@titular | formato_fecha("dd")]'))

    with pytest.raises(PlantillaInvalida) as error:
        GeneradorCargas(definicion, CAMPOS)

    assert "formato_fecha" in str(error.value) and "texto" in str(error.value)


@pytest.mark.parametrize(
    "plantilla", ["[@titular | no_existe]", "[@titular | primeros(0)]", "[@titular | primeros]"]
)
def test_una_funcion_mal_usada_es_una_definicion_invalida(plantilla) -> None:
    with pytest.raises(PlantillaInvalida):
        GeneradorCargas(_definicion(CampoSalida("c", plantilla)), CAMPOS)


# --- Problemas de fila --------------------------------------------------------------------------


def test_un_problema_de_fila_del_motor_es_un_error_de_generacion_y_la_celda_queda_vacia() -> None:
    definicion = _definicion(
        CampoSalida("mitad", "[@saldo | dividir(@dias_atraso)]", N),
        CampoSalida("otra", "[@titular]"),
    )

    carga = _generar(definicion, _producto(dias_atraso=0), _producto(dias_atraso=2))

    assert carga.filas[0] == {"mitad": None, "otra": "Ana Quispe"}
    assert carga.filas[1]["mitad"] == Decimal("750.25")
    (error,) = carga.errores
    assert (error.fila, error.campo, error.codigo) == (1, "mitad", "division_por_cero")
    assert "cero" in error.detalle
    assert not carga.completa


def test_una_variable_obligatoria_vacia_se_informa_por_fila() -> None:
    expresion = Expresion((NodoVariable("telefono", obligatoria=True),))
    definicion = _definicion(CampoSalida("numero", "", expresion=expresion))

    carga = _generar(definicion, _producto(), _producto(telefono=None), _producto(telefono="  "))

    assert [e.fila for e in carga.errores] == [2, 3]
    assert {e.codigo for e in carga.errores} == {CodigoTexto.VARIABLE_OBLIGATORIA_VACIA.value}
    assert carga.filas[0]["numero"] == "900000001"
    assert carga.filas[1]["numero"] is None


def test_un_problema_y_un_error_de_tipo_en_la_misma_carga_se_informan_juntos() -> None:
    definicion = _definicion(
        CampoSalida("a", "[@saldo | dividir(0)]", N),
        CampoSalida("b", "[@titular]", N),  # "Ana Quispe" no es un numero
    )

    carga = _generar(definicion, _producto())

    assert [(e.campo, e.codigo) for e in carga.errores] == [
        ("a", "division_por_cero"),
        ("b", None),
    ]


# --- Valor por defecto --------------------------------------------------------------------------


def test_el_valor_por_defecto_entra_cuando_todo_el_resultado_queda_vacio() -> None:
    definicion = _definicion(
        CampoSalida("nota", "[@titular]", valor_por_defecto="sin titular"),
        CampoSalida("cantidad", "[@saldo]", N, valor_por_defecto="0"),
        CampoSalida("fija", "", valor_por_defecto="vacio"),
    )

    carga = _generar(definicion, _producto(titular=None, saldo=None), _producto(titular="  "))

    assert carga.filas[0] == {"nota": "sin titular", "cantidad": 0, "fija": "vacio"}
    assert carga.filas[1]["nota"] == "  "  # RF-12: un campo en blanco conserva sus espacios
    assert carga.completa


def test_el_valor_por_defecto_no_tapa_un_resultado_con_contenido_ni_un_problema() -> None:
    definicion = _definicion(
        CampoSalida("a", "x[@titular]", valor_por_defecto="defecto"),
        CampoSalida("b", "[@saldo | dividir(0)]", N, valor_por_defecto="9"),
    )

    carga = _generar(definicion, _producto(titular=None))

    assert carga.filas[0] == {"a": "x", "b": None}
    assert [e.campo for e in carga.errores] == ["b"]


def test_el_valor_por_defecto_pasa_por_el_tipo_de_la_columna() -> None:
    definicion = _definicion(
        CampoSalida("f", "[@vence]", F, formato_fecha="%d/%m/%Y", valor_por_defecto="2026-01-31"),
        CampoSalida("m", "[@saldo]", FIN, valor_por_defecto="1234.5"),
        CampoSalida("mal", "[@saldo]", N, valor_por_defecto="abc"),
    )

    carga = _generar(definicion, _producto(vence=None, saldo=None))

    assert carga.filas[0]["f"] == "31/01/2026"
    assert carga.filas[0]["m"] == "1,234.50"
    assert carga.filas[0]["mal"] is None
    assert [e.campo for e in carga.errores] == ["mal"]


# --- Segmentacion: variantes por segmento ------------------------------------------------------


def _por_segmento(politica=PoliticaSinSegmento.EXCLUIR, criterio=None) -> DefinicionCarga:
    return _definicion(
        CampoSalida(
            "mensaje",
            "general [@titular]",
            variantes=(
                VarianteCampo("1_a_8", plantilla="temprano [@titular | primeros(3)]"),
                VarianteCampo(
                    "31_a_60", expresion=Expresion((NodoTexto("tardio "), NodoVariable("pagare")))
                ),
            ),
        ),
        CampoSalida("pagare", "[@pagare]"),
        segmentacion=Segmentacion(criterio or CriterioCalculado(), politica),
    )


def test_cada_producto_usa_el_contenido_de_su_segmento() -> None:
    carga = _generar(
        _por_segmento(),
        _producto(dias_atraso=4),  # 1 a 8
        _producto(dias_atraso=45),  # 31 a 60
        _producto(dias_atraso=20),  # 9 a 30: un segmento valido sin variante propia
    )

    assert [f["mensaje"] for f in carga.filas] == [
        "temprano Ana",
        "tardio P1",
        "general Ana Quispe",
    ]
    assert carga.exclusiones == ()


def test_un_segmento_de_la_tabla_sin_variante_usa_el_contenido_por_defecto() -> None:
    carga = _generar(_por_segmento(), _producto(dias_atraso=0), _producto(dias_atraso=120))

    assert [f["mensaje"] for f in carga.filas] == ["general Ana Quispe"] * 2


def test_sin_segmento_y_politica_excluir_la_fila_no_sale_y_se_informa() -> None:
    carga = _generar(
        _por_segmento(),
        _producto(dias_atraso=4),
        _producto(dias_atraso=121, pagare="P2"),  # mas de 120: sin segmento
        _producto(dias_atraso=None, pagare="P3"),  # sin dato
        _producto(dias_atraso=45, pagare="P4"),
    )

    assert [f["pagare"] for f in carga.filas] == ["P1", "P4"]
    assert [(e.fila, e.codigo) for e in carga.exclusiones] == [
        (2, CodigoTexto.SIN_SEGMENTO.value),
        (3, CodigoTexto.SIN_SEGMENTO.value),
    ]
    assert all("segmento" in e.detalle for e in carga.exclusiones)
    assert carga.errores == ()


def test_los_errores_de_una_fila_cuentan_desde_el_producto_aunque_haya_exclusiones() -> None:
    definicion = _definicion(
        CampoSalida("n", "[@titular]", N),  # "Ana Quispe" no es un numero
        segmentacion=Segmentacion(CriterioCalculado(), PoliticaSinSegmento.EXCLUIR),
    )

    carga = _generar(definicion, _producto(dias_atraso=500), _producto(dias_atraso=4))

    assert len(carga.filas) == 1
    assert [e.fila for e in carga.errores] == [2]  # la fila 2 del pedido, no la 1 de la salida
    assert [e.fila for e in carga.exclusiones] == [1]


def test_sin_segmento_y_politica_usar_por_defecto_sale_con_el_contenido_por_defecto() -> None:
    definicion = _por_segmento(PoliticaSinSegmento.USAR_POR_DEFECTO)

    carga = _generar(definicion, _producto(dias_atraso=500), _producto(dias_atraso=None))

    assert [f["mensaje"] for f in carga.filas] == ["general Ana Quispe"] * 2
    assert carga.exclusiones == ()


def test_el_criterio_calculado_puede_leer_una_variable_de_contexto_ya_ajustada() -> None:
    criterio = CriterioCalculado(variable_dias="dias_atraso_ajustados")

    carga = _generar(
        _por_segmento(criterio=criterio),
        _producto(dias_atraso=4, dias_atraso_ajustados=45),
    )

    assert carga.filas[0]["mensaje"] == "tardio P1"


def test_el_criterio_calculado_usa_la_tabla_de_la_definicion() -> None:
    tabla = (RangoDias("al_dia", "Al dia", None, 0), RangoDias("mora", "Mora", 1, None))
    definicion = _definicion(
        CampoSalida(
            "m",
            "otro",
            variantes=(
                VarianteCampo("al_dia", plantilla="bien"),
                VarianteCampo("mora", plantilla="mal"),
            ),
        ),
        segmentacion=Segmentacion(CriterioCalculado(tabla=tabla)),
    )

    carga = _generar(definicion, _producto(dias_atraso=-5), _producto(dias_atraso=9999))

    assert [f["m"] for f in carga.filas] == ["bien", "mal"]


# --- Segmentacion por un campo categorico -------------------------------------------------------


def _por_campo(politica: PoliticaSinSegmento) -> DefinicionCarga:
    return _definicion(
        CampoSalida(
            "m",
            "por defecto",
            variantes=(
                VarianteCampo("Vigente", plantilla="vigente"),
                VarianteCampo("Vencido", plantilla="vencido"),
            ),
        ),
        segmentacion=Segmentacion(CriterioCampo("segmento_financiero"), politica),
    )


def test_el_criterio_por_campo_usa_el_valor_tal_cual() -> None:
    carga = _generar(
        _por_campo(PoliticaSinSegmento.EXCLUIR),
        _producto(segmento_financiero="Vigente"),
        _producto(segmento_financiero="Vencido"),
        _producto(segmento_financiero="vigente"),  # distinto: no se normaliza
        _producto(segmento_financiero=None),
    )

    assert [f["m"] for f in carga.filas] == ["vigente", "vencido"]
    assert [e.fila for e in carga.exclusiones] == [3, 4]
    assert "'vigente'" in carga.exclusiones[0].detalle


def test_un_valor_de_campo_sin_variante_sigue_la_politica() -> None:
    productos = [_producto(segmento_financiero="Castigado"), _producto(segmento_financiero=None)]

    usar = _generar(_por_campo(PoliticaSinSegmento.USAR_POR_DEFECTO), *productos)

    assert [f["m"] for f in usar.filas] == ["por defecto", "por defecto"]


# --- Segmentacion sin variantes y definiciones invalidas ---------------------------------------


def test_una_segmentacion_sin_variantes_solo_excluye_lo_que_no_tiene_segmento() -> None:
    definicion = _definicion(
        CampoSalida("m", "[@titular]"), segmentacion=Segmentacion(CriterioCalculado())
    )

    carga = _generar(definicion, _producto(dias_atraso=4), _producto(dias_atraso=400))

    assert len(carga.filas) == 1 and len(carga.exclusiones) == 1


@pytest.mark.parametrize(
    ("campos", "segmentacion", "motivo"),
    [
        (
            (CampoSalida("m", "x", variantes=(VarianteCampo("a", plantilla="y"),)),),
            None,
            "variantes sin segmentacion",
        ),
        (
            (CampoSalida("m", "x", variantes=(VarianteCampo("inventado", plantilla="y"),)),),
            Segmentacion(CriterioCalculado()),
            "clave que no esta en la tabla",
        ),
        (
            (
                CampoSalida(
                    "m",
                    "x",
                    variantes=(
                        VarianteCampo("1_a_8", plantilla="a"),
                        VarianteCampo("1_a_8", plantilla="b"),
                    ),
                ),
            ),
            Segmentacion(CriterioCalculado()),
            "variante repetida",
        ),
        (
            (CampoSalida("m", "x", variantes=(VarianteCampo("1_a_8"),)),),
            Segmentacion(CriterioCalculado()),
            "variante sin contenido",
        ),
        (
            (CampoSalida("m", "x", variantes=(VarianteCampo("1_a_8", plantilla="[@no_existe]"),)),),
            Segmentacion(CriterioCalculado()),
            "variante con campo inexistente",
        ),
        (
            (CampoSalida("m", "x"),),
            Segmentacion(CriterioCalculado(variable_dias="no_existe")),
            "variable de dias inexistente",
        ),
        (
            (CampoSalida("m", "x"),),
            Segmentacion(CriterioCampo("no_existe")),
            "campo del criterio inexistente",
        ),
        (
            (CampoSalida("m", "x"),),
            Segmentacion(CriterioCampo("segmento_financiero")),
            "criterio por campo sin ninguna variante",
        ),
        (
            (CampoSalida("m", "x"),),
            Segmentacion(CriterioCalculado(tabla=(RangoDias("a", "A", 5, 1),))),
            "tabla mal armada",
        ),
        (
            (
                CampoSalida(
                    "m",
                    "x",
                    variantes=(VarianteCampo("1_a_8", plantilla="a", expresion=Expresion(())),),
                ),
            ),
            Segmentacion(CriterioCalculado()),
            "plantilla y expresion a la vez",
        ),
    ],
)
def test_las_definiciones_de_segmentacion_mal_armadas_se_rechazan_al_compilar(
    campos, segmentacion, motivo
) -> None:
    with pytest.raises(PlantillaInvalida):
        GeneradorCargas(_definicion(*campos, segmentacion=segmentacion), CAMPOS)


def test_una_variante_se_comprueba_como_cualquier_expresion() -> None:
    definicion = _definicion(
        CampoSalida(
            "m",
            "x",
            variantes=(VarianteCampo("1_a_8", plantilla='[@titular | formato_fecha("dd")]'),),
        ),
        segmentacion=Segmentacion(CriterioCalculado()),
    )

    with pytest.raises(PlantillaInvalida) as error:
        GeneradorCargas(definicion, CAMPOS)

    assert "1_a_8" in str(error.value)


def test_los_campos_de_origen_incluyen_los_de_las_variantes_y_el_del_criterio() -> None:
    generador = GeneradorCargas(_por_segmento(), CAMPOS)

    assert generador.campos_de_origen() == ("titular", "pagare", "dias_atraso")


def test_la_tabla_por_defecto_hace_que_dias_atraso_sea_el_criterio() -> None:
    assert Segmentacion().criterio == CriterioCalculado()
    assert Segmentacion().criterio.variable_dias == "dias_atraso"


def test_generar_una_carga_segmentada_tambien_sirve_para_generar_fila() -> None:
    generador = GeneradorCargas(_por_segmento(), CAMPOS)

    fila, errores = generador.generar_fila(_producto(dias_atraso=4), 1)
    excluida, _ = generador.generar_fila(_producto(dias_atraso=400), 2)

    assert fila["mensaje"] == "temprano Ana" and errores == []
    assert excluida is None  # una fila excluida no tiene celdas


def test_una_columna_de_variable_directa_tambien_puede_tener_variantes() -> None:
    definicion = _definicion(
        CampoSalida("c", "[@titular]", variantes=(VarianteCampo("1_a_8", plantilla="temprano"),)),
        segmentacion=Segmentacion(CriterioCalculado(), PoliticaSinSegmento.USAR_POR_DEFECTO),
    )

    carga = _generar(definicion, _producto(dias_atraso=4), _producto(dias_atraso=45))

    assert [f["c"] for f in carga.filas] == ["temprano", "Ana Quispe"]


def test_una_columna_de_texto_fijo_tambien_puede_tener_variantes() -> None:
    definicion = _definicion(
        CampoSalida("c", "general", variantes=(VarianteCampo("1_a_8", plantilla="temprano"),)),
        segmentacion=Segmentacion(CriterioCalculado()),
    )

    carga = _generar(definicion, _producto(dias_atraso=4), _producto(dias_atraso=45))

    assert [f["c"] for f in carga.filas] == ["temprano", "general"]


def test_los_campos_de_origen_incluyen_los_que_solo_usa_una_variante() -> None:
    definicion = _definicion(
        CampoSalida(
            "c", "[@titular]", variantes=(VarianteCampo("1_a_8", plantilla="[@telefono]"),)
        ),
        segmentacion=Segmentacion(CriterioCalculado()),
    )

    assert GeneradorCargas(definicion, CAMPOS).campos_de_origen() == (
        "titular",
        "telefono",
        "dias_atraso",
    )

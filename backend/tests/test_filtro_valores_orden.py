r"""El orden de los filtros se conserva, y MOWA MES resume cada operador (T-FV-B1, RF-67/RF-68).

- Ida y vuelta del orden de `filtros`, con un orden NO alfabetico, en selecciones guardadas y en
  campanas de MOWA MES: el que se guarda es el que se lee.
- `resumen_filtro` tiene una rama explicita por operador (un operador nuevo lanza, no cae en
  «con»), y el vacio sale como «(vacio)», nunca «None».
- `descripcion_sugerida` sigue el orden de la lista, con una_linea y el limite de 100 UTF-16.

Datos sinteticos.
"""

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from app.core.entities.cartera import Filtro, Operador
from app.core.entities.mowa_mes_campana import LARGO_MAXIMO_DESCRIPCION, largo_utf16
from app.core.services.plataformas.mowa_mes.campana import descripcion_sugerida, resumen_filtro
from app.core.services.seleccion_cartera import expresiones
from app.core.services.seleccion_cartera.campos import CatalogoCartera
from tests.campos_adicionales_memoria import catalogo_con
from tests.test_mowa_mes_campana import armar_servicio, peticion, producto
from tests.test_selecciones_servicio import VALIDA, _servicio

CATALOGO = CatalogoCartera()
BARRA = chr(92)
# Un orden que NO es el alfabetico ni el de los campos del catalogo.
FILTROS_DESORDENADOS = (
    "telefono:no_vacio",
    "region:no_en:PUNO SUR|CUSCO SUR|",
    "dias_atraso:mayor:5",
    "agencia:en:|ZONA 9|ZONA 1",
    f"titular:no_en:A{BARRA}|B",
)


# --- Ida y vuelta del orden ----------------------------------------------------------------------


def test_una_seleccion_guardada_conserva_el_orden_de_sus_filtros() -> None:
    servicio, repositorio = _servicio()

    guardada = servicio.crear(replace(VALIDA, filtros=FILTROS_DESORDENADOS))
    leida = servicio.obtener(guardada.seleccion.id)

    assert guardada.seleccion.datos.filtros == FILTROS_DESORDENADOS
    assert leida.seleccion.datos.filtros == FILTROS_DESORDENADOS
    assert repositorio.selecciones[guardada.seleccion.id].datos.filtros == FILTROS_DESORDENADOS
    assert leida.aplicable  # no_en, el vacio y el escape son validos para el servicio


def test_actualizar_una_seleccion_con_otro_orden_guarda_el_nuevo_orden() -> None:
    servicio, _ = _servicio()
    guardada = servicio.crear(replace(VALIDA, filtros=FILTROS_DESORDENADOS))

    al_reves = tuple(reversed(FILTROS_DESORDENADOS))
    actualizada = servicio.actualizar(
        guardada.seleccion.id, replace(guardada.seleccion.datos, filtros=al_reves)
    )

    assert actualizada.seleccion.datos.filtros == al_reves
    assert servicio.obtener(guardada.seleccion.id).seleccion.datos.filtros == al_reves


def test_el_texto_de_un_filtro_con_vacio_o_escape_se_guarda_tal_cual() -> None:
    servicio, _ = _servicio()
    textos = ("region:en:", "region:no_en:|", f"titular:en:A{BARRA}|B|C{BARRA}{BARRA}")

    guardada = servicio.crear(replace(VALIDA, filtros=textos))

    assert guardada.seleccion.datos.filtros == textos  # el servicio no reescribe la sintaxis


def test_una_seleccion_con_no_en_invalido_no_se_guarda() -> None:
    servicio, repositorio = _servicio()

    with pytest.raises(Exception) as error:  # SeleccionInvalida
        servicio.crear(replace(VALIDA, filtros=("dias_atraso:no_en:5|",)))  # vacio en un numero

    assert error.type.__name__ == "SeleccionInvalida"
    assert repositorio.escrituras == 0


def test_una_campana_conserva_el_orden_de_sus_filtros_y_su_descripcion_lo_sigue() -> None:
    servicio, campanas, _ = armar_servicio([producto(1)])
    filtros = ("region:no_en:PUNO SUR|", "dias_atraso:mayor:5", "agencia:en:ZONA 9|ZONA 1")

    armada = servicio.previsualizar(peticion(filtros=filtros))
    servicio.crear(peticion(filtros=filtros))

    assert campanas.campanas[1].filtros == filtros  # el que se guarda es el que se lee
    assert armada.descripcion == (
        "CajaCusco region no es PUNO SUR/(vacío), dias atraso > 5, agencia en ZONA 9/ZONA 1"
    )


def test_otro_orden_de_los_mismos_filtros_cambia_solo_la_descripcion_sugerida() -> None:
    servicio, campanas, _ = armar_servicio([producto(1)])
    filtros = ("region:no_en:PUNO SUR|", "dias_atraso:mayor:5")

    una = servicio.previsualizar(peticion(filtros=filtros))
    otra = servicio.previsualizar(peticion(filtros=tuple(reversed(filtros))))

    assert una.descripcion != otra.descripcion  # resume en el orden de la lista
    assert (una.disponibles, una.evaluados) == (otra.disponibles, otra.evaluados)
    assert campanas.campanas == {}


# --- resumen_filtro ------------------------------------------------------------------------------

VALORES = {
    Operador.IGUAL: ("A",),
    Operador.DISTINTO: ("A",),
    Operador.MAYOR: (Decimal(5),),
    Operador.MAYOR_IGUAL: (Decimal(5),),
    Operador.MENOR: (Decimal(5),),
    Operador.MENOR_IGUAL: (Decimal(5),),
    Operador.CONTIENE: ("A",),
    Operador.EMPIEZA_CON: ("A",),
    Operador.EN: ("A", "B"),
    Operador.NO_EN: ("A", "B"),
    Operador.ENTRE: (Decimal(1), Decimal(9)),
    Operador.VACIO: (),
    Operador.NO_VACIO: (),
}


def test_la_tabla_de_la_prueba_cubre_todos_los_operadores() -> None:
    assert set(VALORES) == set(Operador)  # un operador nuevo obliga a sumarlo aqui


@pytest.mark.parametrize("operador", list(Operador), ids=lambda o: o.value)
def test_cada_operador_tiene_su_resumen(operador) -> None:
    resumen = resumen_filtro(Filtro("region", operador, VALORES[operador]), CATALOGO)

    assert resumen and "region" in resumen
    assert "None" not in resumen


@pytest.mark.parametrize(
    ("operador", "valores", "esperado"),
    [
        (Operador.NO_VACIO, (), "con region"),  # su rama propia, no un «de lo contrario»
        (Operador.VACIO, (), "sin region"),
        (Operador.EN, ("A", "B"), "region en A/B"),
        (Operador.EN, ("A", None), "region en A/(vacío)"),
        (Operador.EN, (None, "A"), "region en (vacío)/A"),  # en el orden guardado
        (Operador.EN, (None,), "region en (vacío)"),
        (Operador.NO_EN, ("A", "B"), "region no es A/B"),
        (Operador.NO_EN, ("B", "A", None), "region no es B/A/(vacío)"),
        (Operador.NO_EN, (None,), "region no es (vacío)"),
    ],
)
def test_los_textos_del_resumen(operador, valores, esperado) -> None:
    assert resumen_filtro(Filtro("region", operador, valores), CATALOGO) == esperado


def test_un_operador_sin_rama_lanza_en_lugar_de_caer_en_con() -> None:
    class Operador2(str):
        value = "nuevo"

    with pytest.raises(ValueError, match="no tiene resumen"):
        resumen_filtro(Filtro("region", Operador2("nuevo"), ("A",)), CATALOGO)  # type: ignore[arg-type]


def test_el_resumen_de_un_adicional_usa_su_nombre_legible_tambien_con_no_en() -> None:
    filtro = Filtro("ad_zona_comercial", Operador.NO_EN, ("SUR", None))

    assert resumen_filtro(filtro, catalogo_con()) == "Zona comercial no es SUR/(vacío)"


def test_un_valor_de_fecha_o_numero_en_no_en_sale_como_siempre() -> None:
    assert (
        resumen_filtro(
            Filtro("fecha_vencimiento_cuota", Operador.NO_EN, (date(2099, 8, 3),)), CATALOGO
        )
        == "fecha vencimiento cuota no es 2099-08-03"
    )
    assert resumen_filtro(
        Filtro("dias_atraso", Operador.NO_EN, (Decimal(5), Decimal(9))), CATALOGO
    ) == ("dias atraso no es 5/9")


def test_la_descripcion_sugerida_con_no_en_y_vacio_es_de_una_linea_y_cabe() -> None:
    salto = chr(10)
    filtros = [
        expresiones.parsear_filtro(f"region:no_en:A{salto}B|", CATALOGO),
        expresiones.parsear_filtro("dias_atraso:mayor:5", CATALOGO),
    ]

    sugerida = descripcion_sugerida(filtros, CATALOGO)

    assert sugerida == "CajaCusco region no es A B/(vacío), dias atraso > 5"
    assert salto not in sugerida and largo_utf16(sugerida) <= LARGO_MAXIMO_DESCRIPCION


def test_la_descripcion_larga_con_no_en_se_corta_a_100_unidades_por_filtros_enteros() -> None:
    valores = "|".join(f"VALOR LARGO NUMERO {i}" for i in range(12))
    filtros = [
        expresiones.parsear_filtro("dias_atraso:mayor:5", CATALOGO),
        expresiones.parsear_filtro(f"region:no_en:{valores}|", CATALOGO),
    ]

    sugerida = descripcion_sugerida(filtros, CATALOGO)

    assert sugerida == "CajaCusco dias atraso > 5..."
    assert largo_utf16(sugerida) <= LARGO_MAXIMO_DESCRIPCION

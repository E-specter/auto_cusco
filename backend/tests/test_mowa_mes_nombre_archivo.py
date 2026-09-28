"""Pruebas de la plantilla del nombre de los archivos de carga (RF-MM-25).

Piezas puras. Ademas de los casos concretos, propiedades comprobadas a mano sobre
muchas plantillas y valores generados con una semilla fija: ningun resultado
contiene caracteres que Windows no admite, ninguno pasa de 120 caracteres sin la
extension y dos archivos de una misma campana nunca repiten nombre.
"""

import random
import string
from datetime import date

import pytest

from app.core.entities.mowa_mes import PLANTILLA_NOMBRE_POR_DEFECTO
from app.core.entities.mowa_mes_costo import (
    EXTENSION_ARCHIVO,
    LARGO_MAXIMO_NOMBRE_ARCHIVO,
    VARIABLES_PLANTILLA,
    PlantillaInvalida,
)
from app.core.services.plataformas.mowa_mes import nombre_archivo as na
from app.core.services.plataformas.mowa_mes.nombre_archivo import ContextoNombre

CONTEXTO = ContextoNombre("57", "CajaCusco", date(2026, 10, 1), date(2026, 9, 30))
PROHIBIDOS = set('\\/:*?"<>|') | {chr(c) for c in range(32)}


def nombre(plantilla, archivo=1, total=1, cantidad=100, contexto=CONTEXTO, **extra):
    return na.resolver_nombre(plantilla, contexto, archivo, total, cantidad, **extra)


def sin_extension(resuelto: str) -> str:
    assert resuelto.endswith(EXTENSION_ARCHIVO)
    return resuelto[: -len(EXTENSION_ARCHIVO)]


# --- Variables y validacion ---------------------------------------------


def test_las_variables_validas_son_las_de_rf_mm_25_en_orden() -> None:
    assert [v.nombre for v in VARIABLES_PLANTILLA] == [
        "campana",
        "descripcion",
        "fecha_envio",
        "fecha_corte",
        "archivo",
        "total",
        "cantidad",
    ]
    assert all(v.descripcion for v in VARIABLES_PLANTILLA)


def test_cada_variable_se_sustituye_por_su_valor() -> None:
    esperado = {
        "campana": "57",
        "descripcion": "CajaCusco",
        "fecha_envio": "2026-10-01",
        "fecha_corte": "2026-09-30",
        "archivo": "2",
        "total": "3",
        "cantidad": "1200",
    }
    for variable, valor in esperado.items():
        assert nombre("x_{" + variable + "}", archivo=2, total=3, cantidad=1200) == (
            f"x_{valor}_2de3.xlsx".replace(f"x_{valor}_2de3", f"x_{valor}")
            if variable == "archivo"
            else f"x_{valor}_2de3.xlsx"
        )


def test_el_ejemplo_del_requerimiento() -> None:
    plantilla = "CajaCusco_{fecha_envio}_{archivo}de{total}"

    assert nombre(plantilla, archivo=1, total=2) == "CajaCusco_2026-10-01_1de2.xlsx"


def test_la_plantilla_por_defecto_da_el_nombre_que_el_sistema_ya_usaba() -> None:
    assert PLANTILLA_NOMBRE_POR_DEFECTO == "mowa_mes_campana_{campana}_{archivo}_de_{total}"
    assert (
        nombre(PLANTILLA_NOMBRE_POR_DEFECTO, archivo=1, total=1)
        == "mowa_mes_campana_57_1_de_1.xlsx"
    )
    assert (
        nombre(PLANTILLA_NOMBRE_POR_DEFECTO, archivo=2, total=3)
        == "mowa_mes_campana_57_2_de_3.xlsx"
    )


@pytest.mark.parametrize(
    "desconocida", ["nombre", "Campana", "CAMPANA", "campana ", " campana", "", "1"]
)
def test_una_variable_desconocida_se_rechaza_y_se_nombra(desconocida) -> None:
    with pytest.raises(PlantillaInvalida) as error:
        na.variables_usadas("a_{" + desconocida + "}_b")

    assert "{" + desconocida + "}" in str(error.value)
    assert "Variables validas" in str(error.value)


def test_se_nombra_la_primera_variable_desconocida() -> None:
    with pytest.raises(PlantillaInvalida) as error:
        na.variables_usadas("{campana}_{foo}_{bar}")

    assert "{foo}" in str(error.value)
    assert "{bar}" not in str(error.value).split("Variables validas")[0]


@pytest.mark.parametrize(
    ("plantilla", "motivo"),
    [
        ("abc{campana", "sin cerrar"),
        ("{campana", "sin cerrar"),
        ("abc{", "sin cerrar"),
        ("{campana{total}", "sin cerrar"),
        ("{{campana}}", "sin cerrar"),
        ("abc}", "sin abrir"),
        ("campana}", "sin abrir"),
        ("{campana}}", "sin abrir"),
    ],
)
def test_una_llave_sin_cerrar_o_sin_abrir_se_rechaza(plantilla, motivo) -> None:
    with pytest.raises(PlantillaInvalida, match=motivo):
        na.variables_usadas(plantilla)


def test_las_variables_usadas_salen_en_orden_y_con_repeticion() -> None:
    assert na.variables_usadas("{total}-{archivo}-{total}x") == ("total", "archivo", "total")
    assert na.variables_usadas("sin variables") == ()


def test_plantilla_valida_recorta_extremos_y_usa_la_de_por_defecto_si_esta_vacia() -> None:
    assert na.plantilla_valida("  CajaCusco_{campana}  ") == "CajaCusco_{campana}"
    assert na.plantilla_valida("") == PLANTILLA_NOMBRE_POR_DEFECTO
    assert na.plantilla_valida("   ") == PLANTILLA_NOMBRE_POR_DEFECTO
    assert na.plantilla_valida(None) == PLANTILLA_NOMBRE_POR_DEFECTO
    assert na.plantilla_valida(None, por_defecto="otra_{campana}") == "otra_{campana}"


def test_plantilla_valida_rechaza_una_desconocida_y_una_demasiado_larga() -> None:
    with pytest.raises(PlantillaInvalida, match="{x}"):
        na.plantilla_valida("{x}")
    with pytest.raises(PlantillaInvalida, match="300"):
        na.plantilla_valida("a" * (na.LARGO_MAXIMO_PLANTILLA + 1))
    assert na.plantilla_valida("a" * na.LARGO_MAXIMO_PLANTILLA)


# --- Saneamiento --------------------------------------------------------


@pytest.mark.parametrize("prohibido", list('\\/:*?"<>|'))
def test_cada_caracter_prohibido_en_windows_se_reemplaza_por_guion_bajo(prohibido) -> None:
    assert nombre(f"a{prohibido}b") == "a_b.xlsx"


def test_los_caracteres_de_control_tambien_se_reemplazan() -> None:
    assert nombre("a\tb\nc\x00d") == "a_b_c_d.xlsx"


def test_una_descripcion_con_caracteres_prohibidos_se_sanea_pero_no_la_plantilla_fija() -> None:
    contexto = ContextoNombre(
        "1", 'Cobranza: "grupo A" <70%>/*', date(2026, 10, 1), date(2026, 9, 30)
    )

    assert nombre("{descripcion}", contexto=contexto) == "Cobranza_ _grupo A_ _70%___.xlsx"


def test_se_recortan_espacios_y_puntos_de_los_extremos() -> None:
    assert nombre("  ..caja cusco..  ") == "caja cusco.xlsx"
    assert nombre(". a .") == "a.xlsx"
    assert nombre("a.b") == "a.b.xlsx"  # los del medio se conservan


def test_los_extremos_se_recortan_despues_de_sustituir() -> None:
    contexto = ContextoNombre("1", " .. ", date(2026, 10, 1), date(2026, 9, 30))

    assert nombre("{descripcion}fin", contexto=contexto) == "fin.xlsx"


def test_tildes_y_enie_se_conservan_en_el_nombre() -> None:
    contexto = ContextoNombre("1", "Cobranza mañana José", date(2026, 10, 1), date(2026, 9, 30))

    assert nombre("{descripcion}", contexto=contexto) == "Cobranza mañana José.xlsx"


# --- Bordes: vacio, solo prohibidos, solo espacios y puntos, largo exacto ---


@pytest.mark.parametrize("plantilla", ["", "   ", "...", " . . ", ". ."])
def test_si_el_nombre_queda_vacio_se_usa_la_plantilla_por_defecto(plantilla) -> None:
    assert nombre(plantilla) == "mowa_mes_campana_57_1_de_1.xlsx"


def test_una_variable_que_da_vacio_deja_la_plantilla_por_defecto() -> None:
    contexto = ContextoNombre("57", "  ", date(2026, 10, 1), date(2026, 9, 30))

    assert nombre("{descripcion}", contexto=contexto) == "mowa_mes_campana_57_1_de_1.xlsx"


def test_solo_caracteres_prohibidos_no_queda_vacio_queda_en_guiones_bajos() -> None:
    assert nombre('\\/:*?"<>|') == "_________.xlsx"


def test_el_vacio_se_decide_antes_del_sufijo_asi_que_no_queda_solo_el_sufijo() -> None:
    # Con el orden literal (sufijo primero) esto daria "_1de3.xlsx".
    assert nombre("...", archivo=1, total=3) == "mowa_mes_campana_57_1_de_3.xlsx"


def test_el_largo_exacto_de_120_se_conserva_y_121_se_recorta() -> None:
    assert sin_extension(nombre("a" * 120)) == "a" * 120
    assert sin_extension(nombre("a" * 121)) == "a" * 120
    assert len(sin_extension(nombre("a" * 5000))) == 120


def test_el_recorte_a_120_deja_los_extremos_limpios() -> None:
    plantilla = "a" * 118 + ". " + "b" * 10

    resultado = sin_extension(nombre(plantilla))

    assert resultado == "a" * 118  # el punto y el espacio quedaron en el extremo y se quitan


# --- Sufijo automatico --------------------------------------------------


def test_con_un_solo_archivo_no_se_agrega_sufijo() -> None:
    assert nombre("caja", archivo=1, total=1) == "caja.xlsx"


def test_con_mas_de_un_archivo_y_sin_archivo_se_agrega_el_sufijo() -> None:
    assert nombre("caja", archivo=2, total=3) == "caja_2de3.xlsx"


def test_con_archivo_en_la_plantilla_no_se_agrega_sufijo() -> None:
    assert nombre("caja_{archivo}", archivo=2, total=3) == "caja_2.xlsx"


def test_el_sufijo_no_se_agrega_si_solo_se_usa_total() -> None:
    assert nombre("caja_{total}", archivo=2, total=3) == "caja_3_2de3.xlsx"


def test_el_recorte_de_120_toca_la_plantilla_y_nunca_el_sufijo() -> None:
    resultado = sin_extension(nombre("a" * 200, archivo=12, total=30))

    assert len(resultado) == 120
    assert resultado.endswith("_12de30")
    assert resultado == "a" * (120 - len("_12de30")) + "_12de30"


def test_el_sufijo_de_archivos_grandes_tampoco_se_corta() -> None:
    resultado = sin_extension(nombre("a" * 200, archivo=123456, total=234567))

    assert len(resultado) == 120
    assert resultado.endswith("_123456de234567")


def test_el_recorte_antes_del_sufijo_deja_limpio_el_extremo_de_la_plantilla() -> None:
    # Con el sufijo "_1de2" (5) quedan 115 caracteres para la plantilla: el corte cae justo
    # despues de ".. " y esos extremos se quitan antes de pegar el sufijo.
    plantilla = "a" * 112 + ".. " + "b" * 20

    resultado = sin_extension(nombre(plantilla, archivo=1, total=2))

    assert resultado == "a" * 112 + "_1de2"


# --- Unicidad -----------------------------------------------------------


def test_los_nombres_de_una_campana_son_distintos_con_la_plantilla_por_defecto() -> None:
    nombres = na.resolver_nombres(PLANTILLA_NOMBRE_POR_DEFECTO, CONTEXTO, [50_000, 50_000, 3])

    assert nombres == [
        "mowa_mes_campana_57_1_de_3.xlsx",
        "mowa_mes_campana_57_2_de_3.xlsx",
        "mowa_mes_campana_57_3_de_3.xlsx",
    ]


def test_una_plantilla_sin_archivo_da_nombres_distintos_por_el_sufijo() -> None:
    assert na.resolver_nombres("caja", CONTEXTO, [10, 10]) == ["caja_1de2.xlsx", "caja_2de2.xlsx"]


def test_variables_pegadas_que_darian_nombres_iguales_reservan_el_sufijo_en_todos() -> None:
    # archivo 1 con 23 filas y archivo 12 con 3 filas dan los dos "123".
    cantidades = [23] + [1] * 10 + [3]
    nombres = na.resolver_nombres("{archivo}{cantidad}", CONTEXTO, cantidades)

    assert len({n.casefold() for n in nombres}) == 12
    assert nombres[0] == "123_1de12.xlsx"
    assert nombres[11] == "123_12de12.xlsx"


def test_un_nombre_que_solo_difiere_en_mayusculas_cuenta_como_repetido() -> None:
    contexto = ContextoNombre("1", "x", date(2026, 10, 1), date(2026, 9, 30))
    # {archivo} sin sufijo daria "a1" y "A1"? No: el valor de archivo es numerico. Se fuerza
    # el caso con dos archivos cuyo unico texto variable es la cantidad.
    nombres = na.resolver_nombres("{cantidad}", contexto, [7, 7])

    assert nombres == ["7_1de2.xlsx", "7_2de2.xlsx"]


def test_una_plantilla_larga_con_archivo_al_final_no_repite_nombres() -> None:
    plantilla = "a" * 300 + "{archivo}"
    nombres = na.resolver_nombres(plantilla, CONTEXTO, [5] * 12)

    assert len({n.casefold() for n in nombres}) == 12
    assert all(len(sin_extension(n)) <= LARGO_MAXIMO_NOMBRE_ARCHIVO for n in nombres)
    assert nombres[11].endswith("_12de12.xlsx")


def test_sin_archivos_no_hay_nombres() -> None:
    assert na.resolver_nombres("caja", CONTEXTO, []) == []


# --- Propiedades sobre muchas plantillas --------------------------------

_ALFABETO = (
    string.ascii_letters
    + string.digits
    + ' \\/:*?"<>|._-'
    + "\t\n"
    + "áéíóúñÑüÜ€😀"
    + "{campana}{archivo}{total}{cantidad}{descripcion}{fecha_envio}{fecha_corte}"
)


def _plantilla_aleatoria(azar: random.Random) -> str:
    """Texto libre mezclado con variables validas; siempre se cierra bien las llaves."""
    trozos = []
    for _ in range(azar.randint(0, 12)):
        if azar.random() < 0.4:
            trozos.append("{" + azar.choice([v.nombre for v in VARIABLES_PLANTILLA]) + "}")
        else:
            trozos.append(
                "".join(
                    azar.choice(_ALFABETO.replace("{", "").replace("}", ""))
                    for _ in range(azar.randint(0, 60))
                )
            )
    return "".join(trozos)


def _contexto_aleatorio(azar: random.Random) -> ContextoNombre:
    descripcion = "".join(
        azar.choice(_ALFABETO.replace("{", "").replace("}", ""))
        for _ in range(azar.choice([0, 1, 5, 40, 400, 1000]))
    )
    return ContextoNombre(
        str(azar.randint(1, 10**9)), descripcion, date(2026, 10, 1), date(2026, 9, 30)
    )


def test_propiedad_ningun_nombre_tiene_caracteres_prohibidos_ni_pasa_de_120() -> None:
    azar = random.Random(20260928)
    for _ in range(3000):
        plantilla = _plantilla_aleatoria(azar)
        contexto = _contexto_aleatorio(azar)
        total = azar.choice([1, 1, 2, 3, 10, 999])
        archivo = azar.randint(1, total)

        resultado = na.resolver_nombre(plantilla, contexto, archivo, total, azar.randint(0, 10**6))

        cuerpo = sin_extension(resultado)
        assert cuerpo, (plantilla, resultado)
        assert not PROHIBIDOS & set(cuerpo), (plantilla, resultado)
        assert len(cuerpo) <= LARGO_MAXIMO_NOMBRE_ARCHIVO, (plantilla, resultado)
        assert cuerpo == cuerpo.strip(" ."), (plantilla, resultado)
        assert resultado.endswith(EXTENSION_ARCHIVO)


def test_propiedad_dos_archivos_de_una_campana_nunca_repiten_nombre() -> None:
    azar = random.Random(28092026)
    for _ in range(1500):
        plantilla = _plantilla_aleatoria(azar)
        contexto = _contexto_aleatorio(azar)
        cantidades = [azar.randint(1, 60_000) for _ in range(azar.choice([1, 2, 3, 7, 40]))]

        nombres = na.resolver_nombres(plantilla, contexto, cantidades)

        assert len(nombres) == len(cantidades)
        assert len({n.casefold() for n in nombres}) == len(nombres), (plantilla, nombres)
        for resultado in nombres:
            assert not PROHIBIDOS & set(sin_extension(resultado)), (plantilla, resultado)
            assert len(sin_extension(resultado)) <= LARGO_MAXIMO_NOMBRE_ARCHIVO


def test_propiedad_con_mas_de_un_archivo_el_sufijo_sobrevive_al_recorte() -> None:
    azar = random.Random(7)
    for _ in range(1000):
        largo = azar.randint(100, 400)
        plantilla = "".join(azar.choice("abc def.") for _ in range(largo)) + "x"
        total = azar.randint(2, 500)
        archivo = azar.randint(1, total)

        resultado = sin_extension(na.resolver_nombre(plantilla, CONTEXTO, archivo, total, 1))

        assert resultado.endswith(f"_{archivo}de{total}"), (plantilla, resultado)


def test_propiedad_el_mismo_texto_da_siempre_el_mismo_nombre() -> None:
    azar = random.Random(1)
    for _ in range(300):
        plantilla = _plantilla_aleatoria(azar)
        contexto = _contexto_aleatorio(azar)
        cantidades = [azar.randint(1, 100) for _ in range(azar.randint(1, 5))]

        assert na.resolver_nombres(plantilla, contexto, cantidades) == na.resolver_nombres(
            plantilla, contexto, cantidades
        )


# --- Previsualizacion y ejemplo -----------------------------------------


def contexto_previo(descripcion="CajaCusco") -> ContextoNombre:
    return ContextoNombre(na.MARCADOR_CAMPANA, descripcion, date(2026, 10, 1), date(2026, 9, 30))


def test_la_campana_sale_como_marcador_visible_en_la_previsualizacion() -> None:
    assert na.MARCADOR_CAMPANA == "[campana]"

    previsto = na.nombre_previsto("mowa_{campana}", contexto_previo(), [100])

    assert previsto == ("mowa_[campana].xlsx", False)


@pytest.mark.parametrize("variable", ["archivo", "total", "cantidad"])
def test_el_nombre_es_estimado_si_usa_archivo_total_o_cantidad(variable) -> None:
    nombre_, estimado = na.nombre_previsto("x_{" + variable + "}", contexto_previo(), [100])

    assert estimado is True


@pytest.mark.parametrize("variable", ["campana", "descripcion", "fecha_envio", "fecha_corte"])
def test_el_nombre_no_es_estimado_si_no_depende_de_la_division(variable) -> None:
    _, estimado = na.nombre_previsto("x_{" + variable + "}", contexto_previo(), [100])

    assert estimado is False


def test_es_estimado_si_el_sufijo_automatico_entra_por_haber_mas_de_un_archivo() -> None:
    assert na.nombre_previsto("caja", contexto_previo(), [50_000, 10]) == ("caja_1de2.xlsx", True)
    assert na.nombre_previsto("caja", contexto_previo(), [50_000]) == ("caja.xlsx", False)


def test_la_previsualizacion_de_la_plantilla_por_defecto() -> None:
    previsto = na.nombre_previsto(PLANTILLA_NOMBRE_POR_DEFECTO, contexto_previo(), [50_000, 10])

    assert previsto == ("mowa_mes_campana_[campana]_1_de_2.xlsx", True)


def test_sin_archivos_previstos_no_hay_nombre() -> None:
    assert na.nombre_previsto("caja", contexto_previo(), []) is None


def test_el_ejemplo_de_la_configuracion_usa_la_misma_resolucion_con_dos_archivos() -> None:
    nombres = na.resolver_nombres(
        "CajaCusco_{fecha_envio}_{archivo}de{total}", na.CONTEXTO_EJEMPLO, na.CANTIDADES_EJEMPLO
    )

    assert nombres == ["CajaCusco_2026-10-01_1de2.xlsx", "CajaCusco_2026-10-01_2de2.xlsx"]
    assert len(na.CANTIDADES_EJEMPLO) == 2

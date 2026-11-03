"""El nombre de la campana y el de su archivo, sin base (T-WM-B4b1, parte 2; RF-WM-33)."""

from datetime import date

import pytest

from app.core.entities.whatsmkt import PLANTILLA_NOMBRE_POR_DEFECTO, CodigoWhatsmkt, ErrorWhatsmkt
from app.core.services.plataformas.whatsmkt import nombres

CORTE = date(2026, 11, 2)


def test_la_plantilla_por_defecto_da_el_nombre_con_la_fecha_y_el_segmento() -> None:
    nombre = nombres.nombre_de_campana(PLANTILLA_NOMBRE_POR_DEFECTO, CORTE, "Tramo 2", varias=True)

    assert nombre == "CUZCO_Vencida (Tramo 2) whatsapp 2026.11.02"


def test_en_una_campana_global_el_segmento_queda_vacio_y_sin_parentesis_vacios() -> None:
    nombre = nombres.nombre_de_campana(PLANTILLA_NOMBRE_POR_DEFECTO, CORTE, None, varias=False)

    assert nombre == "CUZCO_Vencida whatsapp 2026.11.02"


def test_en_un_lote_con_varias_campanas_se_agrega_el_segmento_si_la_plantilla_no_lo_usa() -> None:
    plantilla = "Cobranza {fecha_corte}"

    varias = nombres.nombre_de_campana(plantilla, CORTE, "Preventivo", varias=True)
    una = nombres.nombre_de_campana(plantilla, CORTE, None, varias=False)
    con_segmento = nombres.nombre_de_campana("{segmento} {fecha_corte}", CORTE, "Preventivo", True)

    assert varias == "Cobranza 2026.11.02 Preventivo"
    assert una == "Cobranza 2026.11.02"
    assert con_segmento == "Preventivo 2026.11.02"  # ya lo usa: no se agrega otra vez


def test_los_espacios_de_mas_se_compactan() -> None:
    assert nombres.nombre_de_campana("A   {segmento}  B", CORTE, "X", True) == "A X B"


def test_un_nombre_de_75_caracteres_pasa_y_uno_de_76_es_nombre_largo() -> None:
    assert nombres.validar_nombre("a" * 75) == "a" * 75
    with pytest.raises(ErrorWhatsmkt) as error:
        nombres.validar_nombre("a" * 76)

    assert error.value.codigo is CodigoWhatsmkt.NOMBRE_LARGO
    assert error.value.parametros == {"largo": 76}


def test_el_largo_se_mide_sin_los_espacios_de_mas() -> None:
    assert nombres.validar_nombre("  " + "a" * 75 + "   ") == "a" * 75


def test_el_archivo_se_llama_como_la_campana_mas_xlsx() -> None:
    assert nombres.nombre_del_archivo("CUZCO_Vencida (Tramo 2) whatsapp 2026.11.02") == (
        "CUZCO_Vencida (Tramo 2) whatsapp 2026.11.02.xlsx"
    )


def test_los_caracteres_que_windows_no_admite_pasan_a_guion_bajo_y_las_tildes_se_conservan() -> (
    None
):
    assert nombres.nombre_del_archivo('Año: "a/b" <c>|d?*\\e') == "Año_ _a_b_ _c__d___e.xlsx"


def test_el_archivo_nunca_queda_sin_nombre_ni_con_espacios_o_puntos_al_final() -> None:
    assert nombres.nombre_del_archivo("   ") == "campana.xlsx"
    assert nombres.nombre_del_archivo("...") == "campana.xlsx"
    assert nombres.nombre_del_archivo("nombre. ") == "nombre.xlsx"

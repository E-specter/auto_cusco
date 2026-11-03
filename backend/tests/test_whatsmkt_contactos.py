"""Armado del archivo de contactos de WhatsMKT, sin base (T-WM-B2; RF-WM-13 a RF-WM-15, RF-WM-23).

Usa el `GeneracionCargasService` de verdad sobre un repositorio de cartera en memoria: lo que se
prueba es lo que WhatsMKT agrega (exclusiones, supervisores, reparto por segmento), no el generador.
Telefonos sinteticos 900000xxx.
"""

from datetime import date

import pytest

from app.core.entities.gestiones_digitales import Supervisor
from app.core.entities.mapeo import CampoSalida, DefinicionCarga
from app.core.entities.whatsmkt import SEGMENTOS_POR_DEFECTO, CodigoWhatsmkt
from app.core.services.generacion_cargas.servicio import GeneracionCargasService
from app.core.services.plataformas.whatsmkt.archivo_contactos import (
    ArchivoContactosService,
    SeleccionCampana,
)
from app.core.services.seleccion_cartera.servicio import ConsultaCarteraService

CORTE = date(2026, 11, 2)
PROCEDENCIAS = ("Caja Cusco", "nuestra empresa")
SUPERVISORES = (
    Supervisor("900000901", "nuestra empresa"),
    Supervisor("900000902", "Caja Cusco"),
)


class RepositorioCartera:
    """Devuelve los productos tal como se le dan, respetando limite y desplazamiento."""

    def __init__(self, productos: list[dict]) -> None:
        self.productos = productos

    def hay_version_vigente(self, fecha_corte):
        return True

    def consultar(self, fecha_corte, filtros, orden, limite, desplazamiento):
        pagina = self.productos[desplazamiento : desplazamiento + limite]
        return len(self.productos), [dict(p) for p in pagina]

    def metricas(self, fecha_corte, filtros, indicadores):  # pragma: no cover
        raise AssertionError("el archivo no pide metricas")

    def segmentar(self, fecha_corte, campo, filtros):  # pragma: no cover
        raise AssertionError("el archivo no segmenta")


def producto(i: int, dias: int | None = 0, **cambios) -> dict:
    base = {
        "pagare": f"{i:018d}",
        "telefono": f"900000{i:03d}",
        "titular": f"Titular {i}",
        "dias_atraso": dias,
    }
    return {**base, **cambios}


def definicion(*, defecto: str | None = None, celda_texto: bool = False) -> DefinicionCarga:
    """`número` y dos macros: el titular (con valor por defecto opcional) y el pagare."""
    return DefinicionCarga(
        nombre="WhatsMKT prueba",
        campos=(
            CampoSalida(nombre="número", plantilla="51[@telefono]", celda_texto=celda_texto),
            CampoSalida(
                nombre="[$MARCRO1$]",
                plantilla="[@titular]",
                valor_por_defecto=defecto,
                etiqueta="Nombres del titular",
            ),
            CampoSalida(nombre="[$MARCRO2$]", plantilla="[@pagare]"),
        ),
    )


def armar(productos, *, por_segmento=False, supervisores=SUPERVISORES, definicion_=None, **sel):
    servicio = ArchivoContactosService(
        GeneracionCargasService(ConsultaCarteraService(RepositorioCartera(productos)))
    )
    seleccion = SeleccionCampana(
        fecha_corte=CORTE, fecha_envio=sel.pop("fecha_envio", CORTE), cantidad=1000, **sel
    )
    return servicio.armar(
        seleccion,
        definicion_ or definicion(),
        SEGMENTOS_POR_DEFECTO,
        supervisores,
        PROCEDENCIAS,
        por_segmento,
    )


def numeros(archivo) -> list[str]:
    return [fila["número"] for fila in archivo.tabla.filas]


# --- Una fila por producto ------------------------------------------------------------------


def test_sale_una_fila_por_producto_y_un_telefono_repetido_sale_dos_veces() -> None:
    productos = [producto(1), producto(2, telefono="900000001"), producto(3)]

    resultado = armar(productos, supervisores=())

    [archivo] = resultado.archivos
    assert archivo.segmento is None
    assert numeros(archivo) == ["51900000001", "51900000001", "51900000003"]
    assert archivo.productos == 3
    assert resultado.exclusiones == ()
    assert (resultado.disponibles, resultado.solicitados) == (3, 1000)


def test_las_columnas_auxiliares_no_salen_en_el_archivo() -> None:
    [archivo] = armar([producto(1)]).archivos

    assert archivo.tabla.cabeceras == ("número", "[$MARCRO1$]", "[$MARCRO2$]")
    assert all(set(fila) == set(archivo.tabla.cabeceras) for fila in archivo.tabla.filas)


def test_sin_productos_no_hay_archivo_ni_supervisores_sueltos() -> None:
    resultado = armar([])

    assert resultado.archivos == ()


# --- Exclusiones ------------------------------------------------------------------------------


def test_sin_telefono_telefono_invalido_y_macro_vacia_con_un_solo_codigo_cada_uno() -> None:
    productos = [
        producto(1, telefono=None),
        producto(2, telefono="  "),
        producto(3, telefono="12345"),
        producto(4, telefono="800000004"),
        producto(5, titular=None),
        producto(6),
    ]

    resultado = armar(productos, supervisores=())

    assert [(e.fila, e.codigo) for e in resultado.exclusiones] == [
        (1, CodigoWhatsmkt.SIN_TELEFONO),
        (2, CodigoWhatsmkt.SIN_TELEFONO),
        (3, CodigoWhatsmkt.TELEFONO_INVALIDO),
        (4, CodigoWhatsmkt.TELEFONO_INVALIDO),
        (5, CodigoWhatsmkt.MACRO_VACIA),
    ]
    [archivo] = resultado.archivos
    assert numeros(archivo) == ["51900000006"]
    assert [e.pagare for e in resultado.exclusiones][0] == f"{1:018d}"


def test_el_orden_de_los_motivos_es_telefono_invalido_y_macro_y_solo_se_reporta_uno() -> None:
    # Sin telefono Y con la macro vacia: sale `sin_telefono`, no los dos.
    sin_nada = producto(1, telefono=None, titular=None)
    invalido_y_macro = producto(2, telefono="12345", titular=None)

    resultado = armar([sin_nada, invalido_y_macro], supervisores=())

    assert [e.codigo for e in resultado.exclusiones] == [
        CodigoWhatsmkt.SIN_TELEFONO,
        CodigoWhatsmkt.TELEFONO_INVALIDO,
    ]
    assert resultado.archivos == ()


def test_una_macro_vacia_dice_cual_es_y_su_etiqueta() -> None:
    resultado = armar([producto(1, titular="")], supervisores=())

    [exclusion] = resultado.exclusiones
    assert exclusion.codigo is CodigoWhatsmkt.MACRO_VACIA
    assert (exclusion.macro, exclusion.etiqueta) == (1, "Nombres del titular")


def test_una_macro_vacia_sin_etiqueta_usa_el_encabezado() -> None:
    sin_etiqueta = DefinicionCarga(
        nombre="x",
        campos=(
            CampoSalida(nombre="número", plantilla="51[@telefono]"),
            CampoSalida(nombre="[$MARCRO1$]", plantilla="[@titular]"),
        ),
    )

    resultado = armar([producto(1, titular=None)], supervisores=(), definicion_=sin_etiqueta)

    assert resultado.exclusiones[0].etiqueta == "[$MARCRO1$]"


def test_con_valor_por_defecto_la_macro_vacia_no_excluye_y_se_usa_el_valor() -> None:
    resultado = armar(
        [producto(1, titular=None)], supervisores=(), definicion_=definicion(defecto="Cliente")
    )

    assert resultado.exclusiones == ()
    [archivo] = resultado.archivos
    assert archivo.tabla.filas[0]["[$MARCRO1$]"] == "Cliente"


def test_un_producto_con_telefono_invalido_no_cuenta_aunque_la_macro_tenga_defecto() -> None:
    resultado = armar(
        [producto(1, telefono="12345")], supervisores=(), definicion_=definicion(defecto="Cliente")
    )

    assert [e.codigo for e in resultado.exclusiones] == [CodigoWhatsmkt.TELEFONO_INVALIDO]


# --- Supervisores -----------------------------------------------------------------------------


def test_los_supervisores_van_primero_con_51_y_las_macros_de_la_primera_fila() -> None:
    resultado = armar([producto(1), producto(2)])

    [archivo] = resultado.archivos
    filas = archivo.tabla.filas
    assert numeros(archivo) == ["51900000902", "51900000901", "51900000001", "51900000002"]
    primera = filas[2]
    for supervisor in filas[:2]:
        assert {k: v for k, v in supervisor.items() if k != "número"} == {
            k: v for k, v in primera.items() if k != "número"
        }
    assert (archivo.supervisores, archivo.productos, archivo.cantidad) == (2, 2, 4)


def test_las_macros_de_los_supervisores_son_las_del_primer_producto_que_si_sale() -> None:
    # El primer producto se excluye: la primera fila del archivo es la del segundo.
    resultado = armar([producto(1, telefono=None), producto(2, titular="Bea")])

    [archivo] = resultado.archivos
    assert archivo.tabla.filas[0]["[$MARCRO1$]"] == "Bea"


def test_las_procedencias_dan_el_orden_de_los_supervisores() -> None:
    [archivo] = armar([producto(1)]).archivos

    # `Caja Cusco` va antes que `nuestra empresa`, aunque el supervisor de esta se dio primero.
    assert numeros(archivo)[:2] == ["51900000902", "51900000901"]


def test_sin_supervisores_el_archivo_trae_solo_productos() -> None:
    [archivo] = armar([producto(1)], supervisores=()).archivos

    assert archivo.supervisores == 0
    assert numeros(archivo) == ["51900000001"]


# --- Reparto por segmento ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("dias", "segmento"),
    [
        (-5, "preventivo"),
        (0, "preventivo"),
        (1, "tramo_2"),
        (8, "tramo_2"),
        (9, "mayores_2"),
        (500, "mayores_2"),
    ],
)
def test_el_reparto_respeta_los_bordes_de_los_dias_ajustados(dias, segmento) -> None:
    resultado = armar([producto(1, dias)], por_segmento=True, supervisores=())

    [archivo] = resultado.archivos
    assert archivo.segmento == segmento


def test_los_dias_se_ajustan_a_la_fecha_de_envio_y_no_a_la_de_corte() -> None:
    # 7 dias al corte: enviado 2 dias despues son 9 (`mayores_2`); al corte serian 7 (`tramo_2`).
    enviado_tarde = armar(
        [producto(1, 7)], por_segmento=True, supervisores=(), fecha_envio=date(2026, 11, 4)
    )
    enviado_al_corte = armar([producto(1, 7)], por_segmento=True, supervisores=())

    assert [a.segmento for a in enviado_tarde.archivos] == ["mayores_2"]
    assert [a.segmento for a in enviado_al_corte.archivos] == ["tramo_2"]


def test_un_archivo_por_segmento_con_productos_en_el_orden_de_los_segmentos() -> None:
    productos = [producto(1, 20), producto(2, -3), producto(3, 20), producto(4, 5)]

    resultado = armar(productos, por_segmento=True, supervisores=())

    assert [(a.segmento, a.productos) for a in resultado.archivos] == [
        ("preventivo", 1),
        ("tramo_2", 1),
        ("mayores_2", 2),
    ]
    # Cada producto esta en un solo archivo.
    assert sorted(n for a in resultado.archivos for n in numeros(a)) == [
        "51900000001",
        "51900000002",
        "51900000003",
        "51900000004",
    ]


def test_un_segmento_sin_productos_no_genera_archivo() -> None:
    resultado = armar([producto(1, 2), producto(2, 3)], por_segmento=True, supervisores=())

    assert [a.segmento for a in resultado.archivos] == ["tramo_2"]


def test_los_supervisores_van_primero_en_cada_archivo_con_la_primera_fila_de_ese_archivo() -> None:
    productos = [producto(1, 20), producto(2, 5), producto(3, 20), producto(4, 5)]

    resultado = armar(productos, por_segmento=True)

    assert [a.segmento for a in resultado.archivos] == ["tramo_2", "mayores_2"]
    for archivo in resultado.archivos:
        filas = archivo.tabla.filas
        assert numeros(archivo)[:2] == ["51900000902", "51900000901"]
        primera_de_productos = filas[archivo.supervisores]
        for supervisor in filas[: archivo.supervisores]:
            assert supervisor["[$MARCRO2$]"] == primera_de_productos["[$MARCRO2$]"]
    tramo_2, mayores_2 = resultado.archivos
    assert tramo_2.tabla.filas[0]["[$MARCRO2$]"] == f"{2:018d}"  # el producto 2 abre su archivo
    assert mayores_2.tabla.filas[0]["[$MARCRO2$]"] == f"{1:018d}"  # y el 1 abre el suyo


def test_las_exclusiones_se_reportan_una_vez_en_todo_el_lote() -> None:
    productos = [producto(1, 20, telefono=None), producto(2, 5), producto(3, 5, titular=None)]

    resultado = armar(productos, por_segmento=True, supervisores=())

    assert [(e.fila, e.codigo) for e in resultado.exclusiones] == [
        (1, CodigoWhatsmkt.SIN_TELEFONO),
        (3, CodigoWhatsmkt.MACRO_VACIA),
    ]
    assert [a.segmento for a in resultado.archivos] == ["tramo_2"]


def test_un_producto_sin_dias_de_atraso_no_cae_en_ningun_segmento() -> None:
    productos = [producto(1, None), producto(2, 5)]

    por_segmento = armar(productos, por_segmento=True, supervisores=())
    global_ = armar(productos, supervisores=())

    assert [(s.fila, s.pagare) for s in por_segmento.sin_segmento] == [(1, f"{1:018d}")]
    assert [a.segmento for a in por_segmento.archivos] == ["tramo_2"]
    assert por_segmento.exclusiones == ()  # no es una exclusion del catalogo
    assert global_.sin_segmento == () and global_.archivos[0].productos == 2


def test_en_modo_global_sale_un_solo_archivo_sin_segmento() -> None:
    productos = [producto(1, 20), producto(2, -3)]

    resultado = armar(productos, supervisores=())

    [archivo] = resultado.archivos
    assert archivo.segmento is None and archivo.productos == 2


# --- Celda de texto (RF-73) -------------------------------------------------------------------


def test_numero_va_siempre_en_celda_de_texto_aunque_la_definicion_no_lo_diga() -> None:
    [sin_celda] = armar([producto(1)], definicion_=definicion(celda_texto=False)).archivos
    [con_celda] = armar([producto(1)], definicion_=definicion(celda_texto=True)).archivos

    assert sin_celda.columnas_texto == frozenset({"número"})
    assert con_celda.columnas_texto == frozenset({"número"})


def test_las_otras_columnas_con_celda_de_texto_se_conservan() -> None:
    con_macro_en_texto = DefinicionCarga(
        nombre="x",
        campos=(
            CampoSalida(nombre="número", plantilla="51[@telefono]"),
            CampoSalida(nombre="[$MARCRO1$]", plantilla="[@pagare]", celda_texto=True),
        ),
    )

    [archivo] = armar([producto(1)], definicion_=con_macro_en_texto).archivos

    assert archivo.columnas_texto == frozenset({"número", "[$MARCRO1$]"})


def test_una_definicion_con_nombres_reservados_se_rechaza() -> None:
    reservada = DefinicionCarga(
        nombre="x",
        campos=(
            CampoSalida(nombre="número", plantilla="51[@telefono]"),
            CampoSalida(nombre="__whatsmkt_telefono", plantilla="[@titular]"),
        ),
    )

    with pytest.raises(ValueError, match="reservados"):
        armar([producto(1)], definicion_=reservada)

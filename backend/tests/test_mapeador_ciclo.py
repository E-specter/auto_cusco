"""El ciclo del mapeador de encabezados sin base de datos (T-MAP-B3a, RF-57 a RF-62).

Un mismo repositorio en memoria sirve al servicio de borradores y a la ingesta, como la sesion de
PostgreSQL: crear -> validar -> confirmar -> volver a analizar. Archivos y valores sinteticos.
"""

import copy
import dataclasses
from datetime import UTC, date, datetime, timedelta

import pytest

from app.adapters.input.lector_tabla import LectorTabla
from app.core.entities.borrador import (
    VIGENCIA_DEL_BORRADOR,
    BorradorNoEncontrado,
    CatalogoDesconocido,
    MapeoConProblemas,
)
from app.core.entities.carga import EstadoCarga
from app.core.entities.lectura_tabla import OpcionesLectura
from app.core.entities.mapeador import (
    Asignacion,
    CodigoMapeo,
    EstadoEncabezado,
    OrigenAsignacion,
)
from app.core.entities.sabana import ArchivoIlegible, HojaVacia
from app.core.services.borradores_carga.servicio import MapeadorService
from app.core.services.ingesta_sabana.mapeable import CATALOGO_SABANA_MAPEABLE
from app.core.services.ingesta_sabana.servicio import IngestaSabanaService
from app.core.services.mapeador.serializacion import analisis_desde_dict
from tests.test_ingesta_servicio import RepositorioEnMemoria

E = EstadoEncabezado
O = OrigenAsignacion  # noqa: E741
FECHA = date(2026, 9, 10)
INICIO = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)
SABANA = "sabana_vencida"


class Reloj:
    def __init__(self) -> None:
        self.ahora = INICIO

    def __call__(self) -> datetime:
        return self.ahora

    def avanzar(self, **delta) -> None:
        self.ahora += timedelta(**delta)


def csv_de(filas: list[list[str]], *, separador: str = ";", codificacion: str = "cp1252") -> bytes:
    return "\n".join(separador.join(f) for f in filas).encode(codificacion) + b"\n"


CSV_SABANA = csv_de(
    [
        ["Pagare", "Titular", "Teléfono", "Región", "Observación libre"],
        [
            "000000000000000001",
            "APELLIDO/NOMBRE FICTICIO",
            "900000001",
            "REGION PRUEBA",
            "nota uno",
        ],
        ["000000000000000002", "OTRO/FICTICIO", "900000002", "REGION PRUEBA", "nota dos"],
    ]
)


class Entorno:
    def __init__(self) -> None:
        self.reloj = Reloj()
        self.repo = RepositorioEnMemoria()
        self.mapeador = MapeadorService(
            self.repo, LectorTabla(), [CATALOGO_SABANA_MAPEABLE], self.reloj
        )
        self.ingesta = IngestaSabanaService(self.repo, LectorTabla(), self.reloj)


@pytest.fixture
def entorno() -> Entorno:
    return Entorno()


def aceptar_todo(analizado) -> list[Asignacion]:
    """Lo que manda la pantalla sin tocar nada, con los parecidos aceptados."""
    origenes = {
        E.RECORDADO: O.RECORDADO,
        E.COINCIDE: O.COINCIDE,
        E.PARECIDO: O.PARECIDO_ACEPTADO,
        E.SIN_COINCIDENCIA: O.MANUAL,
    }
    return [
        Asignacion(c.indice, c.sugerido, origenes[c.estado]) for c in analizado.analisis.columnas
    ]


def estados(analizado) -> list[tuple[str, E, str | None]]:
    return [(c.encabezado, c.estado, c.sugerido) for c in analizado.analisis.columnas]


# --- Crear el borrador --------------------------------------------------------------------------


def test_un_borrador_se_crea_con_el_analisis_y_lo_detectado(entorno) -> None:
    analizado = entorno.mapeador.crear_borrador(SABANA, "datos.csv", CSV_SABANA)

    assert estados(analizado) == [
        ("Pagare", E.COINCIDE, "pagare"),
        ("Titular", E.COINCIDE, "titular"),
        ("Teléfono", E.COINCIDE, "telefono"),
        ("Región", E.COINCIDE, "region"),
        ("Observación libre", E.SIN_COINCIDENCIA, None),
    ]
    assert (analizado.formato.value, analizado.separador, analizado.codificacion) == (
        "csv",
        ";",
        "windows-1252",
    )
    assert (analizado.filas, analizado.hojas, analizado.hoja) == (2, (), None)
    assert analizado.analisis.problemas_iniciales == ()
    assert analizado.analisis.columnas[0].ejemplos == ("000000000000000001", "000000000000000002")
    borrador = entorno.repo.borradores[analizado.borrador.id]
    assert borrador.opciones == {
        "formato": "csv",
        "hoja": None,
        "separador": ";",
        "codificacion": "windows-1252",
    }
    assert borrador.tamano_bytes == len(CSV_SABANA) and len(borrador.huella) == 64
    assert entorno.repo.contenidos_de_borradores[borrador.id] == CSV_SABANA
    assert borrador.creado_en == INICIO


def test_el_analisis_guardado_es_el_que_se_mostro(entorno) -> None:
    analizado = entorno.mapeador.crear_borrador(SABANA, "datos.csv", CSV_SABANA)

    guardado = analisis_desde_dict(entorno.repo.borradores[analizado.borrador.id].analisis)

    assert guardado.columnas == analizado.analisis.columnas
    assert guardado.campos == analizado.analisis.campos
    assert guardado.catalogo_id == SABANA


def test_un_catalogo_desconocido_o_un_archivo_ilegible_no_dejan_borrador(entorno) -> None:
    with pytest.raises(CatalogoDesconocido):
        entorno.mapeador.crear_borrador("otro", "datos.csv", CSV_SABANA)
    with pytest.raises(ArchivoIlegible):
        entorno.mapeador.crear_borrador(SABANA, "datos.xlsx", b"no es una hoja de calculo")
    with pytest.raises(HojaVacia):
        entorno.mapeador.crear_borrador(SABANA, "datos.csv", b"\n\n")

    assert entorno.repo.borradores == {}


def test_el_criterio_de_vacio_del_catalogo_manda(entorno) -> None:
    # En la sabana un encabezado «NULL» es vacio y no se lista.
    contenido = csv_de([["Pagare", "NULL", "Titular"], ["000000000000000001", "x", "NOMBRE"]])

    analizado = entorno.mapeador.crear_borrador(SABANA, "datos.csv", contenido)

    assert [c.indice for c in analizado.analisis.columnas] == [0, 2]


def test_los_recordados_del_catalogo_entran_al_analisis_y_los_de_otro_no(entorno) -> None:
    entorno.repo.guardar_recordados(
        SABANA, {("observacion libre", 1): "region", ("region", 1): None}, INICIO
    )
    entorno.repo.guardar_recordados("otro_catalogo", {("titular", 1): "pagare"}, INICIO)

    analizado = entorno.mapeador.crear_borrador(SABANA, "datos.csv", CSV_SABANA)

    por_nombre = {c.encabezado: (c.estado, c.sugerido) for c in analizado.analisis.columnas}
    assert por_nombre["Observación libre"] == (E.RECORDADO, "region")
    assert por_nombre["Región"] == (E.RECORDADO, None)  # recordado «No cargar»
    assert por_nombre["Titular"] == (E.COINCIDE, "titular")  # el de otro catalogo no cuenta


# --- Volver a analizar --------------------------------------------------------------------------


def test_volver_a_analizar_cambia_la_lectura_sin_volver_a_subir(entorno) -> None:
    contenido = csv_de([["Pagare", "Titular"], ["1", "A"]], separador=";")
    analizado = entorno.mapeador.crear_borrador(SABANA, "datos.csv", contenido)

    como_coma = entorno.mapeador.reanalizar(analizado.borrador.id, OpcionesLectura(separador=","))

    assert [c.encabezado for c in como_coma.analisis.columnas] == ["Pagare;Titular"]
    assert como_coma.borrador.id == analizado.borrador.id and len(entorno.repo.borradores) == 1
    guardado = entorno.repo.borradores[analizado.borrador.id]
    assert guardado.opciones["separador"] == ","
    assert analisis_desde_dict(guardado.analisis).columnas == como_coma.analisis.columnas
    assert entorno.repo.bloqueos_de_borradores == [analizado.borrador.id]  # lo tomo con FOR UPDATE


def test_volver_a_analizar_un_borrador_que_no_existe_o_vencio(entorno) -> None:
    analizado = entorno.mapeador.crear_borrador(SABANA, "datos.csv", CSV_SABANA)
    with pytest.raises(BorradorNoEncontrado):
        entorno.mapeador.reanalizar(999, OpcionesLectura())

    entorno.reloj.avanzar(hours=24)

    with pytest.raises(BorradorNoEncontrado):
        entorno.mapeador.reanalizar(analizado.borrador.id, OpcionesLectura())


def test_volver_a_analizar_ve_lo_recordado_desde_entonces(entorno) -> None:
    analizado = entorno.mapeador.crear_borrador(SABANA, "datos.csv", CSV_SABANA)
    entorno.repo.guardar_recordados(SABANA, {("observacion libre", 1): "agencia"}, INICIO)

    de_nuevo = entorno.mapeador.reanalizar(analizado.borrador.id, OpcionesLectura())

    ultima = de_nuevo.analisis.columnas[-1]
    assert (ultima.estado, ultima.sugerido) == (E.RECORDADO, "agencia")


# --- Validar contra el analisis guardado (M-4) --------------------------------------------------


def test_se_valida_contra_el_analisis_que_se_mostro_aunque_cambien_los_recordados(entorno) -> None:
    analizado = entorno.mapeador.crear_borrador(SABANA, "datos.csv", CSV_SABANA)
    asignaciones = aceptar_todo(analizado)
    # Otra persona recuerda algo en el medio: un analisis nuevo daria otros estados.
    entorno.repo.guardar_recordados(SABANA, {("observacion libre", 1): "agencia"}, INICIO)

    problemas = entorno.mapeador.validar(analizado.borrador.id, asignaciones)

    assert problemas == ()
    nuevo = MapeadorService(
        entorno.repo, LectorTabla(), [CATALOGO_SABANA_MAPEABLE], entorno.reloj
    ).crear_borrador(SABANA, "datos.csv", CSV_SABANA)
    assert nuevo.analisis.columnas[-1].estado is E.RECORDADO  # lo que veria un analisis nuevo


def test_validar_informa_los_problemas_de_las_asignaciones(entorno) -> None:
    analizado = entorno.mapeador.crear_borrador(SABANA, "datos.csv", CSV_SABANA)
    sin_pagare = [Asignacion(0, None, O.MANUAL), *aceptar_todo(analizado)[1:]]

    problemas = entorno.mapeador.validar(analizado.borrador.id, sin_pagare)

    assert [(p.indice, p.codigo, p.campo) for p in problemas] == [
        (None, CodigoMapeo.OBLIGATORIO_SIN_COLUMNA, "pagare")
    ]


def test_validar_un_borrador_que_no_existe(entorno) -> None:
    with pytest.raises(BorradorNoEncontrado):
        entorno.mapeador.validar(1, [])


# --- Vencimiento y descarte ---------------------------------------------------------------------


def test_un_borrador_vive_24_horas(entorno) -> None:
    assert VIGENCIA_DEL_BORRADOR == timedelta(hours=24)
    analizado = entorno.mapeador.crear_borrador(SABANA, "datos.csv", CSV_SABANA)
    entorno.reloj.avanzar(hours=23, minutes=59)

    entorno.mapeador.validar(analizado.borrador.id, [])  # sigue ahi

    entorno.reloj.avanzar(minutes=1)
    with pytest.raises(BorradorNoEncontrado):
        entorno.mapeador.validar(analizado.borrador.id, [])
    with pytest.raises(BorradorNoEncontrado):
        entorno.mapeador.analisis_guardado(analizado.borrador.id)


def test_un_borrador_vencido_no_se_puede_confirmar(entorno) -> None:
    analizado = entorno.mapeador.crear_borrador(SABANA, "datos.csv", CSV_SABANA)
    asignaciones = aceptar_todo(analizado)
    entorno.reloj.avanzar(hours=24)

    with pytest.raises(BorradorNoEncontrado):
        entorno.ingesta.registrar_desde_borrador(analizado.borrador.id, FECHA, asignaciones)

    assert entorno.repo.cargas == {} and entorno.repo.mapeos_recordados == {}


def test_crear_un_borrador_borra_los_vencidos(entorno) -> None:
    viejo = entorno.mapeador.crear_borrador(SABANA, "viejo.csv", CSV_SABANA)
    entorno.reloj.avanzar(hours=25)

    nuevo = entorno.mapeador.crear_borrador(SABANA, "nuevo.csv", CSV_SABANA)

    assert list(entorno.repo.borradores) == [nuevo.borrador.id]
    assert viejo.borrador.id not in entorno.repo.contenidos_de_borradores


def test_descartar_vencidos_al_arrancar_cuenta_los_borrados(entorno) -> None:
    entorno.mapeador.crear_borrador(SABANA, "a.csv", CSV_SABANA)
    entorno.reloj.avanzar(hours=10)
    entorno.mapeador.crear_borrador(SABANA, "b.csv", CSV_SABANA)
    entorno.reloj.avanzar(hours=15)  # el primero tiene 25 h y el segundo, 15

    assert entorno.mapeador.descartar_vencidos() == 1
    assert [b.nombre_archivo for b in entorno.repo.borradores.values()] == ["b.csv"]
    assert entorno.mapeador.descartar_vencidos() == 0


def test_descartar_borra_el_borrador_y_su_contenido(entorno) -> None:
    analizado = entorno.mapeador.crear_borrador(SABANA, "datos.csv", CSV_SABANA)

    entorno.mapeador.descartar(analizado.borrador.id)

    assert entorno.repo.borradores == {} and entorno.repo.contenidos_de_borradores == {}
    with pytest.raises(BorradorNoEncontrado):
        entorno.mapeador.descartar(analizado.borrador.id)


# --- Confirmar: una transaccion -----------------------------------------------------------------


def test_confirmar_crea_la_carga_guarda_lo_recordado_y_borra_el_borrador(entorno) -> None:
    analizado = entorno.mapeador.crear_borrador(SABANA, "datos.csv", CSV_SABANA)

    registrada = entorno.ingesta.registrar_desde_borrador(
        analizado.borrador.id, FECHA, aceptar_todo(analizado)
    )

    carga = entorno.repo.cargas[registrada.carga.id]
    assert (carga["fecha_corte"], carga["version"], carga["estado"]) == (
        FECHA,
        1,
        EstadoCarga.EN_COLA,
    )
    assert carga["opciones_lectura"] == {
        "formato": "csv",
        "hoja": None,
        "separador": ";",
        "codificacion": "windows-1252",
    }
    assert carga["hoja"] == ""
    assert carga["asignaciones"] == [
        {"indice": 0, "encabezado_normalizado": "pagare", "campo": "pagare", "origen": "coincide"},
        {
            "indice": 1,
            "encabezado_normalizado": "titular",
            "campo": "titular",
            "origen": "coincide",
        },
        {
            "indice": 2,
            "encabezado_normalizado": "telefono",
            "campo": "telefono",
            "origen": "coincide",
        },
        {"indice": 3, "encabezado_normalizado": "region", "campo": "region", "origen": "coincide"},
        {
            "indice": 4,
            "encabezado_normalizado": "observacion libre",
            "campo": None,
            "origen": "manual",
        },
    ]
    assert entorno.repo.archivos[registrada.carga.id] == CSV_SABANA
    assert entorno.repo.borradores == {} and entorno.repo.contenidos_de_borradores == {}
    assert entorno.repo.recordados(SABANA) == {
        ("pagare", 1): "pagare",
        ("titular", 1): "titular",
        ("telefono", 1): "telefono",
        ("region", 1): "region",
        ("observacion libre", 1): None,
    }
    assert entorno.repo.bloqueos_de_borradores == [analizado.borrador.id]


def test_las_asignaciones_se_guardan_con_el_origen_resuelto_por_el_backend(entorno) -> None:
    analizado = entorno.mapeador.crear_borrador(SABANA, "datos.csv", CSV_SABANA)
    # La etiqueta miente: dice parecido aceptado pero cambia el campo.
    asignaciones = [
        Asignacion(0, "pagare", O.PARECIDO_ACEPTADO),
        Asignacion(1, "agencia", O.COINCIDE),
        *aceptar_todo(analizado)[2:],
    ]

    registrada = entorno.ingesta.registrar_desde_borrador(
        analizado.borrador.id, FECHA, asignaciones
    )

    guardadas = entorno.repo.cargas[registrada.carga.id]["asignaciones"]
    assert [(a["indice"], a["campo"], a["origen"]) for a in guardadas[:2]] == [
        (0, "pagare", "coincide"),  # coincide y no cambio
        (1, "agencia", "manual"),  # cambio
    ]


def test_confirmar_con_problemas_no_crea_nada_y_conserva_el_borrador(entorno) -> None:
    analizado = entorno.mapeador.crear_borrador(SABANA, "datos.csv", CSV_SABANA)
    repetido = [*aceptar_todo(analizado)[:-1], Asignacion(4, "pagare", O.MANUAL)]

    with pytest.raises(MapeoConProblemas) as error:
        entorno.ingesta.registrar_desde_borrador(analizado.borrador.id, FECHA, repetido)

    assert [p.codigo for p in error.value.problemas] == [
        CodigoMapeo.CAMPO_REPETIDO,
        CodigoMapeo.CAMPO_REPETIDO,
    ]
    assert entorno.repo.cargas == {} and entorno.repo.mapeos_recordados == {}
    assert list(entorno.repo.borradores) == [analizado.borrador.id]


def test_dos_confirmaciones_la_segunda_no_encuentra_el_borrador(entorno) -> None:
    analizado = entorno.mapeador.crear_borrador(SABANA, "datos.csv", CSV_SABANA)
    asignaciones = aceptar_todo(analizado)
    entorno.ingesta.registrar_desde_borrador(analizado.borrador.id, FECHA, asignaciones)

    with pytest.raises(BorradorNoEncontrado):
        entorno.ingesta.registrar_desde_borrador(analizado.borrador.id, FECHA, asignaciones)

    assert len(entorno.repo.cargas) == 1


def test_confirmar_es_todo_o_nada(entorno, monkeypatch) -> None:
    analizado = entorno.mapeador.crear_borrador(SABANA, "datos.csv", CSV_SABANA)
    asignaciones = aceptar_todo(analizado)

    def falla(*args, **kwargs):
        raise RuntimeError("fallo simulado al guardar lo recordado")

    monkeypatch.setattr(entorno.repo, "guardar_recordados", falla)
    antes = copy.deepcopy(entorno.repo.borradores)

    with pytest.raises(RuntimeError):
        entorno.ingesta.registrar_desde_borrador(analizado.borrador.id, FECHA, asignaciones)

    assert entorno.repo.cargas == {} and entorno.repo.archivos == {}
    assert entorno.repo.borradores == antes  # el borrador sigue ahi


def test_un_borrador_de_otro_catalogo_no_se_confirma_como_sabana(entorno) -> None:
    analizado = entorno.mapeador.crear_borrador(SABANA, "datos.csv", CSV_SABANA)
    entorno.repo.borradores[analizado.borrador.id] = dataclasses.replace(
        entorno.repo.borradores[analizado.borrador.id], catalogo_id="otro"
    )

    with pytest.raises(BorradorNoEncontrado):
        entorno.ingesta.registrar_desde_borrador(
            analizado.borrador.id, FECHA, aceptar_todo(analizado)
        )


def test_el_mismo_archivo_se_avisa_como_version_identica(entorno) -> None:
    primero = entorno.mapeador.crear_borrador(SABANA, "a.csv", CSV_SABANA)
    entorno.ingesta.registrar_desde_borrador(primero.borrador.id, FECHA, aceptar_todo(primero))
    segundo = entorno.mapeador.crear_borrador(SABANA, "b.csv", CSV_SABANA)

    registrada = entorno.ingesta.registrar_desde_borrador(
        segundo.borrador.id, FECHA, aceptar_todo(segundo)
    )

    assert (registrada.carga.version, registrada.versiones_identicas) == (2, [1])


# --- El ciclo completo (M-1) --------------------------------------------------------------------


def test_el_siguiente_analisis_llega_recordado(entorno) -> None:
    primero = entorno.mapeador.crear_borrador(SABANA, "datos.csv", CSV_SABANA)
    asignaciones = [*aceptar_todo(primero)[:-1], Asignacion(4, "agencia", O.MANUAL)]
    entorno.ingesta.registrar_desde_borrador(primero.borrador.id, FECHA, asignaciones)

    segundo = entorno.mapeador.crear_borrador(SABANA, "datos.csv", CSV_SABANA)

    assert [c.estado for c in segundo.analisis.columnas] == [E.RECORDADO] * 5
    assert segundo.analisis.columnas[-1].sugerido == "agencia"
    assert entorno.mapeador.validar(segundo.borrador.id, aceptar_todo(segundo)) == ()


def test_los_dos_pagare_confirmados_llegan_recordados_y_se_pueden_confirmar_otra_vez(
    entorno,
) -> None:
    contenido = csv_de(
        [["Pagare", "Zona", "Pagare"], ["000000000000000001", "x", "000000000000000001"]]
    )
    primero = entorno.mapeador.crear_borrador(SABANA, "datos.csv", contenido)
    assert [(c.sugerido, c.ocurrencia) for c in primero.analisis.columnas] == [
        ("pagare", 1),
        (None, 1),
        ("pagare_duplicado", 2),
    ]
    entorno.ingesta.registrar_desde_borrador(primero.borrador.id, FECHA, aceptar_todo(primero))

    segundo = entorno.mapeador.crear_borrador(SABANA, "datos.csv", contenido)

    assert [(c.estado, c.sugerido) for c in segundo.analisis.columnas] == [
        (E.RECORDADO, "pagare"),
        (E.RECORDADO, None),
        (E.RECORDADO, "pagare_duplicado"),
    ]
    registrada = entorno.ingesta.registrar_desde_borrador(
        segundo.borrador.id, FECHA, aceptar_todo(segundo)
    )
    assert registrada.carga.version == 2
    assert entorno.repo.recordados(SABANA)[("pagare", 2)] == "pagare_duplicado"


def test_lo_que_se_recuerda_se_actualiza_y_no_se_duplica(entorno) -> None:
    primero = entorno.mapeador.crear_borrador(SABANA, "datos.csv", CSV_SABANA)
    entorno.ingesta.registrar_desde_borrador(primero.borrador.id, FECHA, aceptar_todo(primero))
    segundo = entorno.mapeador.crear_borrador(SABANA, "datos.csv", CSV_SABANA)
    cambiadas = [*aceptar_todo(segundo)[:-1], Asignacion(4, "agencia", O.MANUAL)]

    entorno.ingesta.registrar_desde_borrador(segundo.borrador.id, FECHA, cambiadas)

    recordados = entorno.repo.recordados(SABANA)
    assert len(recordados) == 5 and recordados[("observacion libre", 1)] == "agencia"

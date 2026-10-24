"""Definiciones de columnas guardadas y versionadas, en el nucleo y sin base (B4b, RF-51, RF-46).

El repositorio es un doble en memoria (`tests/definiciones_memoria.py`); el de PostgreSQL tiene sus
pruebas en `test_definiciones_columnas_postgres.py`.
"""

import random
from dataclasses import replace

import pytest

from app.core.entities.definiciones_columnas import (
    MAXIMO_COLUMNAS,
    MAXIMO_VARIANTES,
    DefinicionNoEncontrada,
    NombreDeDefinicionRepetido,
    VersionNoEncontrada,
)
from app.core.entities.mapeo import TipoSalida
from app.core.entities.segmentacion import RangoDias
from app.core.entities.texto_enriquecido import CodigoTexto
from app.core.services.contextos_texto import contexto_cartera
from app.core.services.definiciones_columnas.servicio import (
    DefinicionesColumnasService,
    DefinicionInvalida,
)
from app.core.services.mapeo_campos.serializacion import (
    definicion_a_dict,
    definicion_desde_dict,
)
from tests.definiciones_memoria import RepositorioEnMemoria

CARTERA = contexto_cartera()


def _servicio(contexto=CARTERA) -> tuple[DefinicionesColumnasService, RepositorioEnMemoria]:
    repositorio = RepositorioEnMemoria()
    return DefinicionesColumnasService(repositorio, contexto), repositorio


def _texto(valor: str) -> dict:
    return {"tipo": "texto", "valor": valor}


def _variable(nombre: str, *funciones: dict) -> dict:
    return {"tipo": "variable", "nombre": nombre, "funciones": list(funciones)}


def _columna(nombre: str, orden: int, *nodos: dict, **extra) -> dict:
    return {"nombre": nombre, "orden": orden, "expresion": {"nodos": list(nodos)}, **extra}


def _definicion(nombre: str | None = "SMS", *columnas: dict, **extra) -> dict:
    cuerpo = {"columnas": list(columnas) or [_columna("a", 0, _variable("titular"))], **extra}
    if nombre is not None:
        cuerpo["nombre"] = nombre
    return cuerpo


def _problemas(dato) -> list[tuple]:
    servicio, repositorio = _servicio()
    with pytest.raises(DefinicionInvalida) as error:
        servicio.crear(dato)
    assert repositorio.definiciones == {}  # con problemas no se guarda nada
    return [(p.problema.codigo, p.columna, p.segmento, p.campo) for p in error.value.problemas]


# --- Guardar ------------------------------------------------------------------------------------


def test_se_guarda_con_su_version_1_vigente_y_sin_usar() -> None:
    servicio, _ = _servicio()

    vista = servicio.crear(_definicion("SMS preventiva"))

    assert vista.definicion.nombre == "SMS preventiva"
    assert (vista.version.numero, vista.version.usada_en) == (1, None)
    assert vista.definicion.vigente == vista.version
    assert [c["nombre"] for c in vista.version.contenido["columnas"]] == ["a"]
    assert (
        "nombre" not in vista.version.contenido
    )  # el nombre es de la definicion, no de la version


def test_el_nombre_se_guarda_sin_espacios_en_los_extremos() -> None:
    servicio, _ = _servicio()

    assert servicio.crear(_definicion("  SMS  ")).definicion.nombre == "SMS"


def test_lo_guardado_es_la_forma_canonica_con_la_segmentacion_resuelta() -> None:
    servicio, _ = _servicio()

    contenido = servicio.crear(_definicion(segmentacion={})).version.contenido

    assert contenido["proteger_formulas"] is True
    assert contenido["segmentacion"]["politica"] == "excluir"
    criterio = contenido["segmentacion"]["criterio"]
    assert criterio["tipo"] == "calculado"
    assert criterio["variable_dias"] == "dias_atraso_ajustados"  # RF-55: una definicion nueva
    assert [r["clave"] for r in criterio["tabla"]][:2] == ["preventiva", "1_a_8"]
    assert criterio["tabla"][0] == {
        "clave": "preventiva",
        "etiqueta": "Preventiva",
        "desde": None,
        "hasta": 0,
    }


def test_una_definicion_guardada_no_cambia_si_cambia_la_tabla_por_defecto() -> None:
    servicio, repositorio = _servicio()
    id_ = servicio.crear(_definicion(segmentacion={})).definicion.id
    otra = replace(
        CARTERA, tabla_rangos=(RangoDias("unica", "Unica", None, None),), variable_dias="otros"
    )

    cargada = DefinicionesColumnasService(repositorio, otra).cargar(id_)

    criterio = cargada.definicion.segmentacion.criterio  # type: ignore[union-attr]
    assert criterio.variable_dias == "dias_atraso_ajustados"
    assert [r.clave for r in criterio.tabla][0] == "preventiva"


def test_una_version_guardada_con_dias_atraso_no_se_reinterpreta_con_los_dias_ajustados() -> None:
    # RF-55 / D-C3-1: antes del cambio la cartera segmentaba por `dias_atraso`. Esa version sigue
    # segmentando por `dias_atraso` aunque hoy el contexto resuelva `dias_atraso_ajustados`.
    anterior = replace(CARTERA, variable_dias="dias_atraso")
    repositorio = RepositorioEnMemoria()
    creada = DefinicionesColumnasService(repositorio, anterior).crear(_definicion(segmentacion={}))
    cargada = DefinicionesColumnasService(repositorio, CARTERA).cargar(creada.definicion.id)

    assert creada.version.contenido["segmentacion"]["criterio"]["variable_dias"] == "dias_atraso"
    criterio = cargada.definicion.segmentacion.criterio  # type: ignore[union-attr]
    assert criterio.variable_dias == "dias_atraso"
    # y una nueva, hoy, guarda la ajustada: la diferencia es solo de lo que se guarda al crear
    nueva = DefinicionesColumnasService(repositorio, CARTERA).crear(
        _definicion("Otra", segmentacion={})
    )
    assert nueva.version.contenido["segmentacion"]["criterio"]["variable_dias"] == (
        "dias_atraso_ajustados"
    )


def test_una_plantilla_se_convierte_a_expresion_y_se_devuelve_expresion() -> None:
    servicio, _ = _servicio()
    dato = {
        "nombre": "con plantilla",
        "columnas": [
            {
                "nombre": "m",
                "orden": 0,
                "plantilla": "Hola [@titular | primeros(4)]!",
                "variantes": [{"segmento": "1_a_8", "plantilla": "[@titular]"}],
            }
        ],
        "segmentacion": {},
    }

    columna = servicio.crear(dato).version.contenido["columnas"][0]

    assert "plantilla" not in columna
    assert [n["tipo"] for n in columna["expresion"]["nodos"]] == ["texto", "variable", "texto"]
    assert columna["expresion"]["nodos"][1]["funciones"] == [{"nombre": "primeros", "args": [4]}]
    assert columna["variantes"] == [
        {
            "segmento": "1_a_8",
            "expresion": {
                "nodos": [
                    {"tipo": "variable", "nombre": "titular", "funciones": [], "obligatoria": False}
                ]
            },
        }
    ]


def test_el_formato_de_fecha_se_guarda_con_marcas_y_la_carga_lo_usa() -> None:
    servicio, _ = _servicio()
    columna = _columna(
        "v", 0, _variable("fecha_vencimiento_cuota"), tipo="fecha", formato_fecha="dd/mm/aaaa"
    )

    vista = servicio.crear(_definicion("fechas", columna))

    assert vista.version.contenido["columnas"][0]["formato_fecha"] == "dd/mm/aaaa"
    campo = servicio.cargar(vista.definicion.id).definicion.campos[0]
    assert (campo.tipo, campo.patron_fecha, campo.formato_fecha) == (
        TipoSalida.FECHA,
        "dd/mm/aaaa",
        None,
    )


def test_el_nombre_repetido_se_rechaza_sin_distinguir_mayusculas() -> None:
    servicio, _ = _servicio()
    servicio.crear(_definicion("SMS"))

    with pytest.raises(NombreDeDefinicionRepetido):
        servicio.crear(_definicion("  sms "))


# --- Problemas al guardar -------------------------------------------------------------------------


@pytest.mark.parametrize("nombre", [None, "", "   ", "x" * 121])
def test_el_nombre_es_obligatorio_y_cabe(nombre) -> None:
    assert _problemas(_definicion(nombre)) == [
        (CodigoTexto.DEFINICION_INVALIDA, None, None, "nombre")
    ]


def test_una_variable_inexistente_se_ubica_en_su_columna_y_su_nodo() -> None:
    dato = _definicion(
        "x",
        _columna("ok", 0, _variable("titular")),
        _columna("mal", 1, _texto("a"), _variable("inventada")),
    )

    assert _problemas(dato) == [(CodigoTexto.VARIABLE_DESCONOCIDA, 1, None, None)]


def test_la_posicion_del_problema_es_la_del_pedido_y_no_la_del_orden() -> None:
    dato = _definicion(
        "x", _columna("c", 9, _variable("titular")), _columna("mal", 1, _variable("inventada"))
    )

    assert _problemas(dato) == [(CodigoTexto.VARIABLE_DESCONOCIDA, 1, None, None)]


def test_un_formato_de_fecha_sin_marcas_es_parametro_invalido_de_su_columna() -> None:
    columna = _columna(
        "v", 0, _variable("fecha_vencimiento_cuota"), tipo="fecha", formato_fecha="%d/%m/%Y"
    )

    assert _problemas(_definicion("x", columna)) == [
        (CodigoTexto.PARAMETRO_INVALIDO, 0, None, "formato_fecha")
    ]


def test_se_informan_juntos_el_nombre_la_lectura_y_el_diagnostico() -> None:
    dato = _definicion(
        "",
        _columna("a", 0, _variable("inventada")),
        _columna("b", 1, _texto("x"), tipo="raro"),
    )

    assert _problemas(dato) == [
        (CodigoTexto.DEFINICION_INVALIDA, None, None, "nombre"),
        (CodigoTexto.DEFINICION_INVALIDA, 1, None, "tipo"),
    ]


def test_una_definicion_sin_columnas_no_se_guarda() -> None:
    assert _problemas({"nombre": "x", "columnas": []}) == [
        (CodigoTexto.DEFINICION_INVALIDA, None, None, "columnas"),
        (CodigoTexto.DEFINICION_INVALIDA, None, None, "definicion"),
    ]


def test_el_limite_de_columnas() -> None:
    columnas = [_columna(f"c{i}", i, _texto("x")) for i in range(MAXIMO_COLUMNAS + 1)]

    assert _problemas(_definicion("x", *columnas)) == [
        (CodigoTexto.LIMITE_EXCEDIDO, None, None, "columnas")
    ]
    servicio, _ = _servicio()
    assert servicio.crear(_definicion("ok", *columnas[:MAXIMO_COLUMNAS]))


def test_el_limite_de_variantes_por_columna() -> None:
    def variantes(n: int) -> list[dict]:
        return [{"segmento": f"v{i}", "expresion": {"nodos": []}} for i in range(n)]

    segmentacion = {"criterio": {"tipo": "campo", "campo": "region"}}
    columna = _columna("a", 0, _texto("x"), variantes=variantes(MAXIMO_VARIANTES + 1))

    assert _problemas(_definicion("x", columna, segmentacion=segmentacion)) == [
        (CodigoTexto.LIMITE_EXCEDIDO, 0, None, "variantes")
    ]
    servicio, _ = _servicio()
    ok = _columna("a", 0, _texto("x"), variantes=variantes(MAXIMO_VARIANTES))
    assert servicio.crear(_definicion("ok", ok, segmentacion=segmentacion))


def test_una_plantilla_mal_escrita_es_sintaxis_invalida_en_su_columna() -> None:
    dato = {"nombre": "x", "columnas": [{"nombre": "a", "orden": 0, "plantilla": "[@titular"}]}

    assert _problemas(dato) == [(CodigoTexto.SINTAXIS_INVALIDA, 0, None, "plantilla")]


def test_plantilla_y_expresion_a_la_vez_es_un_problema_de_la_columna() -> None:
    dato = _definicion("x", _columna("a", 0, _texto("x"), plantilla="y"))

    assert _problemas(dato) == [(CodigoTexto.DEFINICION_INVALIDA, 0, None, "plantilla")]


# --- Versiones ------------------------------------------------------------------------------------


def test_una_version_nueva_es_la_vigente_y_las_anteriores_quedan_intactas() -> None:
    servicio, _ = _servicio()
    id_ = servicio.crear(_definicion("SMS", _columna("a", 0, _texto("uno")))).definicion.id

    vista = servicio.agregar_version(id_, _definicion("SMS", _columna("a", 0, _texto("dos"))))

    assert vista.version.numero == 2
    assert vista.definicion.vigente.numero == 2
    assert [v.numero for v in vista.definicion.versiones] == [1, 2]
    antigua = servicio.obtener(id_, 1).version
    assert antigua.contenido["columnas"][0]["expresion"]["nodos"][0]["valor"] == "uno"
    assert servicio.obtener(id_).version.numero == 2


def test_una_version_nueva_puede_omitir_el_nombre_o_repetirlo_con_otras_mayusculas() -> None:
    servicio, _ = _servicio()
    id_ = servicio.crear(_definicion("SMS")).definicion.id

    sin = servicio.agregar_version(id_, _definicion(None)).version.numero
    con = servicio.agregar_version(id_, _definicion(" sms ")).version.numero

    assert (sin, con) == (2, 3)
    assert servicio.obtener(id_).definicion.nombre == "SMS"


def test_el_nombre_no_cambia_con_una_version_nueva() -> None:
    servicio, _ = _servicio()
    id_ = servicio.crear(_definicion("SMS")).definicion.id

    with pytest.raises(DefinicionInvalida) as error:
        servicio.agregar_version(id_, _definicion("Otro nombre"))

    assert [(p.columna, p.campo) for p in error.value.problemas] == [(None, "nombre")]
    assert servicio.obtener(id_).definicion.vigente.numero == 1


def test_una_version_con_problemas_no_se_guarda() -> None:
    servicio, _ = _servicio()
    id_ = servicio.crear(_definicion("SMS")).definicion.id

    with pytest.raises(DefinicionInvalida):
        servicio.agregar_version(id_, _definicion(None, _columna("a", 0, _variable("inventada"))))

    assert len(servicio.obtener(id_).definicion.versiones) == 1


def test_lo_que_no_existe_se_informa() -> None:
    servicio, _ = _servicio()
    id_ = servicio.crear(_definicion("SMS")).definicion.id

    with pytest.raises(DefinicionNoEncontrada):
        servicio.obtener(999)
    with pytest.raises(DefinicionNoEncontrada):
        servicio.agregar_version(999, _definicion(None))
    with pytest.raises(DefinicionNoEncontrada):
        servicio.cargar(999)
    with pytest.raises(VersionNoEncontrada) as error:
        servicio.obtener(id_, 7)
    assert (error.value.definicion_id, error.value.numero) == (id_, 7)
    with pytest.raises(VersionNoEncontrada):
        servicio.cargar(id_, 7)


def test_el_listado_trae_lo_de_c7_ordenado_por_nombre() -> None:
    servicio, _ = _servicio()
    b = servicio.crear(_definicion("b segunda")).definicion.id
    servicio.crear(_definicion("A primera"))
    servicio.agregar_version(b, _definicion(None))
    servicio.marcar_usada(b, 2)

    resumen = servicio.listar()

    assert [
        (r.nombre, r.version_vigente, r.cantidad_versiones, r.vigente_usada) for r in resumen
    ] == [
        ("A primera", 1, 1, False),
        ("b segunda", 2, 2, True),
    ]
    assert resumen[1].actualizado_en > resumen[0].actualizado_en


# --- usada_en -------------------------------------------------------------------------------------


def test_marcar_usada_fija_usada_en_una_vez_y_solo_en_esa_version() -> None:
    servicio, _ = _servicio()
    id_ = servicio.crear(_definicion("SMS")).definicion.id
    servicio.agregar_version(id_, _definicion(None))

    servicio.marcar_usada(id_, 1)
    primera = servicio.obtener(id_, 1).version.usada_en
    servicio.marcar_usada(id_, 1)

    assert primera is not None
    assert servicio.obtener(id_, 1).version.usada_en == primera  # la segunda vez no la cambia
    assert servicio.obtener(id_, 2).version.usada_en is None
    assert servicio.obtener(id_, 1).version.usada


def test_marcar_usada_una_version_inexistente_se_informa() -> None:
    servicio, _ = _servicio()
    id_ = servicio.crear(_definicion("SMS")).definicion.id

    with pytest.raises(VersionNoEncontrada):
        servicio.marcar_usada(id_, 5)
    with pytest.raises(VersionNoEncontrada):
        servicio.marcar_usada(404, 1)


# --- Cargar ---------------------------------------------------------------------------------------


def test_cargar_da_la_definicion_lista_para_generar_con_las_columnas_en_su_orden() -> None:
    servicio, _ = _servicio()
    dato = _definicion(
        "SMS",
        _columna("tercera", 20, _texto("c")),
        _columna("primera", 5, _texto("a")),
        proteger_formulas=False,
    )
    id_ = servicio.crear(dato).definicion.id

    cargada = servicio.cargar(id_)

    assert (cargada.id, cargada.numero, cargada.nombre) == (id_, 1, "SMS")
    assert [c.nombre for c in cargada.definicion.campos] == ["primera", "tercera"]
    assert cargada.definicion.proteger_formulas is False
    assert cargada.definicion.nombre == "SMS"


def test_cargar_una_version_antigua_o_la_vigente() -> None:
    servicio, _ = _servicio()
    id_ = servicio.crear(_definicion("SMS", _columna("v1", 0, _texto("x")))).definicion.id
    servicio.agregar_version(id_, _definicion(None, _columna("v2", 0, _texto("y"))))

    assert servicio.cargar(id_, 1).definicion.campos[0].nombre == "v1"
    assert servicio.cargar(id_).definicion.campos[0].nombre == "v2"
    assert servicio.cargar(id_).numero == 2


# --- Forma canonica: ida y vuelta -----------------------------------------------------------------


def _azar_definicion(azar: random.Random) -> dict:
    nodos = [
        _texto("x"),
        _variable("titular", {"nombre": "primeros", "args": [3]}),
        _variable("saldo_capital_pendiente", {"nombre": "redondear", "args": [2]}),
        _variable(
            "fecha_vencimiento_cuota",
            {"nombre": "sumar_dias", "args": [{"variable": "dias_atraso"}]},
        ),
    ]
    columnas = []
    ordenes = azar.sample(range(0, 40), azar.randint(1, 5))
    for i, orden in enumerate(ordenes):
        extra: dict = {}
        if azar.random() < 0.4:
            extra["valor_por_defecto"] = azar.choice(["0", "-", "sin dato"])
        if azar.random() < 0.4:
            extra["tipo"] = azar.choice(["texto", "numero", "financiero"])
        if azar.random() < 0.3:
            extra["formato_financiero"] = {
                "separador_miles": ".",
                "separador_decimal": ",",
                "decimales": azar.randint(0, 4),
            }
        if azar.random() < 0.3:
            extra["variantes"] = [
                {"segmento": s, "expresion": {"nodos": azar.sample(nodos, azar.randint(0, 2))}}
                for s in azar.sample(["preventiva", "1_a_8", "9_a_30"], azar.randint(1, 3))
            ]
        columnas.append(_columna(f"c{i}", orden, *azar.sample(nodos, azar.randint(0, 3)), **extra))
    return {
        "nombre": "azar",
        "columnas": columnas,
        "segmentacion": azar.choice([None, {}, {"politica": "usar_por_defecto"}]),
        "proteger_formulas": azar.choice([True, False]),
    }


def test_la_forma_canonica_vuelve_a_leerse_igual_ida_y_vuelta() -> None:
    azar = random.Random(20261002)
    tabla, dias = CARTERA.tabla_rangos, CARTERA.variable_dias

    for _ in range(200):
        dato = _azar_definicion(azar)
        leida = definicion_desde_dict(dato, tabla, dias)
        canonica = definicion_a_dict(leida)
        otra = definicion_desde_dict(canonica, tabla, dias)

        assert otra.definicion == leida.definicion
        assert otra.ordenes == leida.ordenes
        assert definicion_a_dict(otra) == canonica
        assert canonica["columnas"] == sorted(canonica["columnas"], key=lambda c: c["orden"])


def test_el_orden_explicito_se_guarda_tal_cual_y_no_se_renumera() -> None:
    servicio, _ = _servicio()
    dato = _definicion("x", _columna("b", 20, _texto("b")), _columna("a", 5, _texto("a")))

    contenido = servicio.crear(dato).version.contenido

    assert [(c["nombre"], c["orden"]) for c in contenido["columnas"]] == [("a", 5), ("b", 20)]


def test_el_limite_de_variantes_se_ubica_en_la_posicion_del_pedido_y_no_en_la_del_orden() -> None:
    segmentacion = {"criterio": {"tipo": "campo", "campo": "region"}}
    variantes = [
        {"segmento": f"v{i}", "expresion": {"nodos": []}} for i in range(MAXIMO_VARIANTES + 1)
    ]
    dato = _definicion(
        "x",
        _columna("posicion_0", 9, _texto("a")),  # primera del pedido, la ultima por orden
        _columna("posicion_1", 1, _texto("b"), variantes=variantes),
        segmentacion=segmentacion,
    )

    assert _problemas(dato) == [(CodigoTexto.LIMITE_EXCEDIDO, 1, None, "variantes")]


# --- Renombrar (RF-56) -----------------------------------------------------------------------


def _versiones(guardada) -> list[tuple]:
    return [(v.numero, dict(v.contenido), v.usada_en, v.creado_en) for v in guardada.versiones]


def test_renombrar_cambia_solo_el_nombre_y_deja_intactas_las_versiones() -> None:
    servicio, _ = _servicio()
    id_ = servicio.crear(_definicion("SMS")).definicion.id
    servicio.agregar_version(id_, _definicion("SMS"))
    servicio.marcar_usada(id_, 1)
    antes = servicio.obtener(id_).definicion

    despues = servicio.renombrar(id_, "SMS preventiva")

    assert despues.nombre == "SMS preventiva"
    assert _versiones(despues) == _versiones(antes)  # ni una version nueva ni una tocada
    assert despues.vigente.numero == antes.vigente.numero == 2
    assert despues.creado_en == antes.creado_en
    assert despues.actualizado_en > antes.actualizado_en
    assert servicio.cargar(id_).nombre == "SMS preventiva"


def test_renombrar_recorta_los_espacios_de_los_extremos() -> None:
    servicio, _ = _servicio()
    id_ = servicio.crear(_definicion("SMS")).definicion.id

    assert servicio.renombrar(id_, "   Cobranza  ").nombre == "Cobranza"


def test_renombrar_a_un_nombre_ajeno_es_nombre_repetido_sin_distinguir_mayusculas() -> None:
    servicio, repositorio = _servicio()
    servicio.crear(_definicion("Preventiva"))
    id_ = servicio.crear(_definicion("Mora")).definicion.id
    antes = repositorio.obtener(id_)

    for ajeno in ("Preventiva", "  PREVENTIVA ", "preventiva"):
        with pytest.raises(NombreDeDefinicionRepetido):
            servicio.renombrar(id_, ajeno)

    assert repositorio.obtener(id_) == antes  # nada cambio


def test_renombrar_al_mismo_nombre_no_es_un_error_ni_cambia_nada() -> None:
    servicio, repositorio = _servicio()
    id_ = servicio.crear(_definicion("SMS")).definicion.id
    antes = repositorio.obtener(id_)

    iguales = [servicio.renombrar(id_, "SMS"), servicio.renombrar(id_, "  SMS  ")]

    assert all(d == antes for d in iguales)
    assert repositorio.obtener(id_).actualizado_en == antes.actualizado_en  # no hubo cambio


def test_renombrar_cambiando_solo_las_mayusculas_si_es_un_cambio() -> None:
    servicio, repositorio = _servicio()
    id_ = servicio.crear(_definicion("sms preventiva")).definicion.id
    antes = repositorio.obtener(id_)

    despues = servicio.renombrar(id_, "SMS Preventiva")  # no choca con ella misma

    assert despues.nombre == "SMS Preventiva"
    assert despues.actualizado_en > antes.actualizado_en
    assert repositorio.obtener(id_).nombre == "SMS Preventiva"


@pytest.mark.parametrize("nombre", ["", "   ", "x" * 121, None, 5])
def test_renombrar_con_un_nombre_vacio_largo_o_que_no_es_texto_es_invalido(nombre) -> None:
    servicio, repositorio = _servicio()
    id_ = servicio.crear(_definicion("SMS")).definicion.id

    with pytest.raises(DefinicionInvalida) as error:
        servicio.renombrar(id_, nombre)

    (problema,) = error.value.problemas
    assert (problema.campo, problema.columna) == ("nombre", None)
    assert problema.problema.codigo is CodigoTexto.DEFINICION_INVALIDA
    assert repositorio.obtener(id_).nombre == "SMS"


def test_renombrar_acepta_un_nombre_de_exactamente_120_caracteres() -> None:
    servicio, _ = _servicio()
    id_ = servicio.crear(_definicion("SMS")).definicion.id

    assert len(servicio.renombrar(id_, "n" * 120).nombre) == 120


def test_renombrar_una_definicion_que_no_existe_es_404_antes_que_validar_el_nombre() -> None:
    servicio, _ = _servicio()

    with pytest.raises(DefinicionNoEncontrada):
        servicio.renombrar(999, "Otro")
    with pytest.raises(DefinicionNoEncontrada):
        servicio.renombrar(999, "")


def test_despues_de_renombrar_las_versiones_nuevas_siguen_el_nombre_nuevo() -> None:
    servicio, _ = _servicio()
    id_ = servicio.crear(_definicion("Viejo")).definicion.id
    servicio.renombrar(id_, "Nuevo")

    servicio.agregar_version(
        id_, _definicion("NUEVO")
    )  # el mismo nombre, sin distinguir mayusculas
    with pytest.raises(DefinicionInvalida):
        servicio.agregar_version(id_, _definicion("Viejo"))  # el de antes ya no es el suyo

    assert servicio.obtener(id_).definicion.nombre == "Nuevo"


def test_el_nombre_que_se_deja_queda_libre_para_otra_definicion() -> None:
    servicio, _ = _servicio()
    id_ = servicio.crear(_definicion("Viejo")).definicion.id
    servicio.renombrar(id_, "Nuevo")

    otra = servicio.crear(_definicion("viejo"))

    assert otra.definicion.nombre == "viejo"


def test_si_la_definicion_desaparece_entre_la_lectura_y_el_cambio_es_404(monkeypatch) -> None:
    servicio, repositorio = _servicio()
    id_ = servicio.crear(_definicion("SMS")).definicion.id
    monkeypatch.setattr(repositorio, "renombrar", lambda *_: None)  # ya no estaba al escribir

    with pytest.raises(DefinicionNoEncontrada):
        servicio.renombrar(id_, "Otro")

"""Los campos adicionales de la cartera en el nucleo (T-CA-B1, RF-64 a RF-66).

Sin base de datos: el puerto es un doble en memoria. Lo que se prueba:
- el nombre tecnico (`ad_` + slug), sus colisiones y los reservados;
- el catalogo (base + adicionales), los archivados que resuelven pero no se ofrecen;
- la «capacidad nueva» (RF-66): un consumidor que recibe el catalogo ve un adicional sin codigo
  propio, y un adicional de cada tipo en filtros, segmentacion, indicadores, variables del motor,
  columnas de carga, el mapeador y el resumen de MOWA MES;
- una prueba de arquitectura: nadie fuera de `campos.py` importa la constante de la base.
"""

import ast
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.core.entities.campos_adicionales import CampoAdicional, TipoAdicional
from app.core.entities.cartera import (
    ConsultaInvalida,
    Filtro,
    Funcion,
    Indicador,
    MetricasCartera,
    Operador,
    Orden,
    TipoDato,
)
from app.core.entities.mapeo import CampoSalida, DefinicionCarga
from app.core.entities.texto_enriquecido import Expresion, NodoVariable, TipoValor
from app.core.services.contextos_texto import contexto_cartera
from app.core.services.generacion_cargas.servicio import GeneracionCargasService
from app.core.services.ingesta_sabana.catalogo import CATALOGO_SABANA, armar_catalogo_sabana
from app.core.services.mapeador.analisis import analizar
from app.core.services.mapeador.similitud import alias_legibles, coincide
from app.core.services.plataformas.mowa_mes.campana import descripcion_sugerida, resumen_filtro
from app.core.services.seleccion_cartera import expresiones
from app.core.services.seleccion_cartera.campos import CAMPOS_BASE, CatalogoCartera
from app.core.services.seleccion_cartera.nombres_adicionales import (
    RESERVADOS,
    nombre_tecnico,
    slug,
)
from app.core.services.seleccion_cartera.servicio import ConsultaCarteraService
from app.core.services.selecciones.servicio import problemas_de
from app.core.services.texto_enriquecido import evaluador
from app.core.services.texto_enriquecido.tipos import variables_desde_campos
from tests.campos_adicionales_memoria import (
    NUMERO,
    TEXTO,
    catalogo_con,
)

APP = Path(__file__).resolve().parents[1] / "app"
FECHA_CORTE = date(2026, 9, 10)  # anterior a hoy: la generacion no la rechaza por la fecha de envio


# --- El nombre tecnico ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("legible", "esperado"),
    [
        ("Zona comercial", "zona_comercial"),
        ("  Ñandú — 2ª ronda!! ", "nandu_2a_ronda"),
        ("Monto (S/.)", "monto_s"),
        ("%%%", "campo"),  # sin nada aprovechable
        ("a" * 80, "a" * 40),  # largo acotado
    ],
)
def test_el_slug_es_ascii_en_minusculas_y_sin_guiones_sueltos(legible, esperado) -> None:
    assert slug(legible) == esperado


def test_el_nombre_tecnico_lleva_el_prefijo() -> None:
    assert nombre_tecnico("Zona comercial", []) == "ad_zona_comercial"


def test_si_choca_suma_un_numero_y_nunca_reutiliza_uno_que_existio() -> None:
    usados = ["ad_zona", "ad_zona_2"]  # el segundo puede estar archivado: tambien cuenta

    assert nombre_tecnico("Zona", usados) == "ad_zona_3"
    assert nombre_tecnico("Zona", []) == "ad_zona"
    assert nombre_tecnico("ZONA!", usados) == "ad_zona_3"  # el slug iguala los nombres parecidos


def test_un_nombre_nunca_tapa_un_reservado() -> None:
    # Aunque el prefijo ya los separa, el nombre se valida contra la lista.
    assert nombre_tecnico("Titular", []) == "ad_titular"
    assert "ad_titular" not in RESERVADOS
    assert (
        nombre_tecnico(
            "x",
            ["ad_x"],
        )
        == "ad_x_2"
    )


def test_un_reservado_nunca_se_devuelve_aunque_el_slug_lo_produzca(monkeypatch) -> None:
    from app.core.services.seleccion_cartera import nombres_adicionales

    monkeypatch.setattr(
        nombres_adicionales, "RESERVADOS", frozenset({"ad_zona", "ad_zona_2"})
    )  # un reservado futuro que si empiece por el prefijo

    assert nombre_tecnico("Zona", []) == "ad_zona_3"


def test_cada_variable_que_un_contexto_o_un_conector_pone_esta_reservada_o_es_de_la_base() -> None:
    from app.core.services.fecha_envio import VARIABLES_DE_ENVIO
    from app.core.services.plataformas.mowa_mes.speech import VARIABLES_V2

    nombres = set(VARIABLES_DE_ENVIO) | set(VARIABLES_V2)

    assert nombres <= RESERVADOS | set(CAMPOS_BASE)
    assert {"titular", "fecha_vencimiento_cuota", "whatsapp_contacto"} <= RESERVADOS


def test_ningun_nombre_tecnico_se_parece_a_un_campo_base_ni_a_un_reservado() -> None:
    for legible in ("Región", "Titular", "Fecha de envío", "Días de atraso ajustados", "pagare"):
        tecnico = nombre_tecnico(legible, [])
        assert tecnico.startswith("ad_") and tecnico not in set(CAMPOS_BASE) | RESERVADOS


# --- El catalogo ---------------------------------------------------------------------------------


def test_sin_adicionales_el_catalogo_es_la_base_de_siempre() -> None:
    catalogo = CatalogoCartera()

    assert catalogo.tipos() == CAMPOS_BASE
    assert not any(c.adicional for c in catalogo.campos().values())


def test_el_catalogo_suma_los_adicionales_a_la_base_con_su_tipo_y_su_etiqueta() -> None:
    campos = catalogo_con().campos()

    assert set(CAMPOS_BASE) < set(campos)
    assert (campos["ad_zona_comercial"].tipo, campos["ad_monto_extra"].tipo) == (
        TipoDato.TEXTO,
        TipoDato.NUMERO,
    )
    assert campos["ad_fecha_visita"].tipo is TipoDato.FECHA
    assert campos["ad_zona_comercial"].etiqueta == "Zona comercial"
    assert campos["ad_zona_comercial"].adicional and not campos["region"].adicional
    assert campos["region"].clave_etiqueta == "campo.region" and campos["region"].etiqueta is None


def test_un_archivado_se_resuelve_para_leer_pero_no_se_ofrece() -> None:
    catalogo = catalogo_con()

    assert catalogo.tipo_de("ad_antiguo") is TipoDato.NUMERO  # resuelve
    assert catalogo.convertir("ad_antiguo", "5") == Decimal(5)
    catalogo.validar_filtro(Filtro("ad_antiguo", Operador.MAYOR, (Decimal(1),)))  # y valida
    catalogo.validar_indicador(Indicador("total", Funcion.SUMA, "ad_antiguo"))
    assert "ad_antiguo" in catalogo.campos() and "ad_antiguo" not in catalogo.ofrecidos()
    assert "ad_antiguo" not in catalogo.catalogo_publico()
    assert catalogo.tipos()["ad_antiguo"] is TipoDato.NUMERO  # el motor y las columnas lo leen


def test_se_puede_saber_cuales_de_los_campos_usados_estan_archivados() -> None:
    catalogo = catalogo_con()

    usados = ["region", "ad_antiguo", "ad_zona_comercial", "ad_antiguo", "inexistente"]

    assert catalogo.archivados_entre(usados) == ("ad_antiguo",)


def test_el_catalogo_publico_marca_los_adicionales_y_no_cambia_los_de_la_base() -> None:
    publico = catalogo_con().catalogo_publico()

    assert publico["ad_monto_extra"] == {
        "tipo": "numero",
        "operadores": publico["dias_atraso"]["operadores"],
        "adicional": True,
        "etiqueta": "Monto extra",
    }
    assert publico["region"] == CatalogoCartera().catalogo_publico()["region"]
    assert "adicional" not in publico["region"]


def test_la_etiqueta_de_un_adicional_es_su_nombre_legible_y_la_de_los_demas_su_nombre() -> None:
    catalogo = catalogo_con()

    assert catalogo.etiqueta_de("ad_zona_comercial") == "Zona comercial"
    assert catalogo.etiqueta_de("ad_antiguo") == "Campo antiguo"  # un archivado tambien se lee
    assert catalogo.etiqueta_de("dias_atraso") == "dias_atraso"
    assert catalogo.etiqueta_de("inexistente") == "inexistente"


def test_un_campo_que_no_existe_se_rechaza_como_siempre() -> None:
    with pytest.raises(ConsultaInvalida, match="no existe"):
        catalogo_con().tipo_de("ad_inventado")


# --- Un adicional de cada tipo en filtros, orden, segmentacion e indicadores ---------------------


class RepositorioFalso:
    """Un repositorio que solo anota lo que le piden: lo que se prueba es la validacion."""

    def __init__(self) -> None:
        self.pedidos: list[tuple] = []

    def hay_version_vigente(self, fecha_corte):
        return True

    def consultar(self, fecha_corte, filtros, orden, limite, desplazamiento):
        self.pedidos.append(("consultar", filtros, orden))
        return 0, []

    def metricas(self, fecha_corte, filtros, indicadores, recorte=None):
        self.pedidos.append(("metricas", filtros, indicadores))
        return MetricasCartera(0, Decimal(0), None, None, {})

    def segmentar(self, fecha_corte, campo, filtros, recorte=None):
        self.pedidos.append(("segmentar", campo))
        return []


@pytest.fixture
def servicio() -> ConsultaCarteraService:
    return ConsultaCarteraService(RepositorioFalso(), catalogo_con())


@pytest.mark.parametrize(
    ("crudo", "valor"),
    [
        ("ad_zona_comercial:igual:SUR", "SUR"),
        ("ad_monto_extra:mayor:150.5", Decimal("150.5")),
        ("ad_fecha_visita:menor:2099-08-01", date(2099, 8, 1)),
    ],
)
def test_un_filtro_sobre_un_adicional_de_cada_tipo_se_parsea_y_se_consulta(
    servicio, crudo, valor
) -> None:
    filtro = expresiones.parsear_filtro(crudo, servicio.catalogo)

    servicio.consultar(FECHA_CORTE, [filtro])

    assert filtro.valores == (valor,)
    assert servicio._repositorio.pedidos[-1][1] == (filtro,)


def test_un_valor_que_no_es_del_tipo_del_adicional_se_rechaza() -> None:
    with pytest.raises(ConsultaInvalida, match="numero valido"):
        expresiones.parsear_filtro("ad_monto_extra:mayor:mucho", catalogo_con())
    with pytest.raises(ConsultaInvalida, match="fecha valido"):
        expresiones.parsear_filtro("ad_fecha_visita:menor:ayer", catalogo_con())


def test_los_operadores_de_un_adicional_son_los_de_su_tipo(servicio) -> None:
    with pytest.raises(ConsultaInvalida, match="no aplica a un campo numero"):
        servicio.consultar(FECHA_CORTE, [Filtro("ad_monto_extra", Operador.CONTIENE, ("1",))])
    servicio.consultar(FECHA_CORTE, [Filtro("ad_zona_comercial", Operador.CONTIENE, ("su",))])
    servicio.consultar(FECHA_CORTE, [Filtro("ad_fecha_visita", Operador.VACIO)])


@pytest.mark.parametrize("campo", ["ad_zona_comercial", "ad_monto_extra", "ad_fecha_visita"])
def test_se_ordena_y_se_segmenta_por_un_adicional_de_cada_tipo(servicio, campo) -> None:
    servicio.consultar(FECHA_CORTE, orden=Orden(campo, descendente=True))
    servicio.segmentar(FECHA_CORTE, campo)
    servicio.resumen(FECHA_CORTE, segmento=campo, orden=Orden(campo))

    pedidos = servicio._repositorio.pedidos
    assert ("segmentar", campo) in pedidos and pedidos[0][2] == Orden(campo, descendente=True)


@pytest.mark.parametrize(
    "funcion", [Funcion.SUMA, Funcion.PROMEDIO, Funcion.MINIMO, Funcion.MAXIMO]
)
def test_suma_promedio_minimo_y_maximo_de_un_adicional_numero_se_aceptan(servicio, funcion) -> None:
    servicio.metricas(FECHA_CORTE, indicadores=[Indicador("x", funcion, "ad_monto_extra")])

    assert servicio._repositorio.pedidos[-1][0] == "metricas"


@pytest.mark.parametrize("campo", ["ad_zona_comercial", "ad_fecha_visita"])
@pytest.mark.parametrize(
    "funcion", [Funcion.SUMA, Funcion.PROMEDIO, Funcion.MINIMO, Funcion.MAXIMO]
)
def test_con_un_adicional_texto_o_fecha_las_funciones_numericas_se_rechazan(
    servicio, campo, funcion
) -> None:
    with pytest.raises(ConsultaInvalida, match="solo aplica a campos numericos"):
        servicio.metricas(FECHA_CORTE, indicadores=[Indicador("x", funcion, campo)])


@pytest.mark.parametrize("campo", ["ad_zona_comercial", "ad_monto_extra", "ad_fecha_visita"])
def test_el_conteo_de_un_adicional_de_cualquier_tipo_se_acepta(servicio, campo) -> None:
    servicio.metricas(FECHA_CORTE, indicadores=[Indicador("n", Funcion.CONTEO, campo)])


def test_un_campo_base_de_fecha_sigue_aceptando_minimo_y_maximo() -> None:
    # La regla estricta de RF-27 es de los adicionales: lo que ya funcionaba no cambia.
    catalogo = CatalogoCartera()

    catalogo.validar_indicador(Indicador("antes", Funcion.MINIMO, "fecha_vencimiento_cuota"))


# --- Selecciones guardadas -----------------------------------------------------------------------


def test_una_seleccion_guardada_con_un_adicional_aplica_y_con_un_archivado_tambien() -> None:
    from app.core.entities.selecciones import DatosSeleccion

    datos = DatosSeleccion(
        nombre="Por zona",
        filtros=("ad_zona_comercial:igual:SUR", "ad_antiguo:mayor:1"),
        orden="-ad_monto_extra",
        cantidad=10,
        indicadores=("total:suma:ad_monto_extra",),
    )

    assert problemas_de(datos, catalogo_con()) == ()
    # sin el campo en el catalogo (nunca se creo) si se avisa: es lo que hacia antes de B1
    assert len(problemas_de(datos, CatalogoCartera())) == 4


# --- Variables del motor de texto ----------------------------------------------------------------


def test_las_variables_del_contexto_cartera_incluyen_los_adicionales_con_su_tipo() -> None:
    contexto = contexto_cartera(catalogo_con())

    tipos = {v.nombre: v.tipo for v in contexto.variables}
    assert (tipos["ad_zona_comercial"], tipos["ad_monto_extra"], tipos["ad_fecha_visita"]) == (
        TipoValor.TEXTO,
        TipoValor.NUMERO,
        TipoValor.FECHA,
    )
    assert tipos["ad_antiguo"] is TipoValor.NUMERO  # un archivado sigue compilando
    assert contexto_cartera(CatalogoCartera()).variables != contexto.variables


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("ad_zona_comercial", "SUR"),
        ("ad_monto_extra", Decimal("12.5")),
        ("ad_fecha_visita", date(2099, 8, 1)),
    ],
)
def test_un_adicional_de_cada_tipo_se_usa_como_variable_de_una_expresion(campo, valor) -> None:
    variables = variables_desde_campos(catalogo_con().tipos())

    compilada = evaluador.compilar(Expresion((NodoVariable(campo),)), variables)

    assert compilada.evaluar({campo: valor}).problemas == ()


# --- Columnas de carga ---------------------------------------------------------------------------


class RepositorioConAdicionales(RepositorioFalso):
    """Productos que traen el valor de cada adicional, como los devolveria la base."""

    def consultar(self, fecha_corte, filtros, orden, limite, desplazamiento):
        return 1, [
            {
                "pagare": "000000000000000001",
                "ad_zona_comercial": "SUR",
                "ad_monto_extra": Decimal("12.50"),
                "ad_fecha_visita": date(2099, 8, 1),
            }
        ]


def test_las_columnas_de_carga_toman_un_adicional_de_cada_tipo_sin_codigo_propio() -> None:
    consulta = ConsultaCarteraService(RepositorioConAdicionales(), catalogo_con())
    servicio = GeneracionCargasService(consulta)
    definicion = DefinicionCarga(
        "con adicionales",
        (
            CampoSalida("zona", "[@ad_zona_comercial]"),
            CampoSalida("monto", "[@ad_monto_extra]"),
            CampoSalida("visita", "[@ad_fecha_visita]"),
        ),
    )

    resultado = servicio.generar(FECHA_CORTE, definicion, cantidad=1)

    assert resultado.errores == ()
    assert [f for f in resultado.tabla.filas][0]["zona"] == "SUR"
    assert resultado.tabla.cabeceras == ("zona", "monto", "visita")


def test_sin_el_adicional_en_el_catalogo_la_columna_no_compila() -> None:
    from app.core.entities.mapeo import PlantillaInvalida

    servicio = GeneracionCargasService(ConsultaCarteraService(RepositorioConAdicionales()))
    definicion = DefinicionCarga("sin", (CampoSalida("zona", "[@ad_zona_comercial]"),))

    with pytest.raises(PlantillaInvalida):
        servicio.generar(FECHA_CORTE, definicion, cantidad=1)


# --- «Capacidad nueva» (RF-66) -------------------------------------------------------------------


def test_un_consumidor_nuevo_que_recibe_el_catalogo_ve_los_adicionales_sin_codigo_propio() -> None:
    """Una capacidad que aun no existe: lista los campos que ofrece segun el catalogo. Nadie le
    ensena los adicionales; los ve porque pide `ofrecidos()`."""

    def campos_que_ofrece(catalogo: CatalogoCartera) -> list[str]:
        return sorted(catalogo.ofrecidos())

    con = campos_que_ofrece(catalogo_con())

    assert {"ad_zona_comercial", "ad_monto_extra", "ad_fecha_visita"} <= set(con)
    assert "ad_antiguo" not in con
    assert campos_que_ofrece(CatalogoCartera()) == sorted(CAMPOS_BASE)


# --- El mapeador ---------------------------------------------------------------------------------


def test_el_catalogo_de_la_sabana_suma_los_adicionales_activos_al_final() -> None:
    catalogo = armar_catalogo_sabana(catalogo_con()._adicionales.listar())

    nombres = [c.nombre for c in catalogo.campos]
    assert nombres[: len(CATALOGO_SABANA.campos)] == [c.nombre for c in CATALOGO_SABANA.campos]
    assert nombres[len(CATALOGO_SABANA.campos) :] == [
        "ad_zona_comercial",
        "ad_monto_extra",
        "ad_fecha_visita",
    ]  # el archivado no se ofrece
    assert catalogo.id == "sabana_vencida"


def test_un_adicional_del_mapeador_nunca_es_obligatorio_y_trae_etiqueta_literal() -> None:
    campo = armar_catalogo_sabana([TEXTO]).campos[-1]

    assert (campo.obligatorio, campo.adicional, campo.etiqueta) == (False, True, "Zona comercial")
    assert campo.alias == ("zona comercial",) and campo.tipo == "texto"


def test_el_alias_de_un_adicional_es_su_encabezado_y_sale_por_alias_legible() -> None:
    raro = CampoAdicional("ad_raro", "Raro", TipoAdicional.TEXTO, "tipo (nuevo) v1.2_a")
    campo = armar_catalogo_sabana([raro]).campos[-1]

    # un alias de la base con parentesis seria una regex y no saldria; el de un adicional es texto
    assert alias_legibles(campo) == ("tipo (nuevo) v1.2 a",)
    assert coincide("tipo (nuevo) v1.2_a", campo) and not coincide("tipo nuevo v1x2 a", campo)


def test_el_encabezado_de_origen_de_un_adicional_cuenta_para_la_similitud_aunque_lleve_signos() -> (
    None
):
    from app.core.services.mapeador.similitud import candidatos_de_similitud, similitud

    raro = CampoAdicional("ad_raro", "Raro", TipoAdicional.TEXTO, "tipo (nuevo) v1.2_a")
    campo = armar_catalogo_sabana([raro]).campos[-1]

    assert candidatos_de_similitud(campo) == ("raro", "tipo (nuevo) v1.2_a")
    assert similitud("tipo (nuevo) v1.2_a", campo) == 1.0  # una regex con parentesis no lo diria


def test_un_encabezado_igual_al_nombre_legible_o_al_de_origen_coincide() -> None:
    campo = armar_catalogo_sabana([TEXTO]).campos[-1]

    assert coincide("zona comercial", campo)  # el nombre legible, normalizado, y el de origen
    assert not coincide("ad zona comercial", campo)  # el tecnico no es algo que un archivo diga


def test_el_mapeador_asigna_la_columna_de_un_adicional_por_su_encabezado() -> None:
    catalogo = armar_catalogo_sabana([TEXTO, NUMERO])

    analisis = analizar(
        ["Pagare", "Zona Comercial", "MONTO EXTRA"], [], catalogo, {}, lambda v: False
    )

    estados = {c.encabezado: (c.estado.value, c.sugerido) for c in analisis.columnas}
    assert estados["Zona Comercial"] == ("coincide", "ad_zona_comercial")
    assert estados["MONTO EXTRA"] == ("coincide", "ad_monto_extra")


# --- El resumen de MOWA MES ----------------------------------------------------------------------


def test_el_resumen_de_un_filtro_muestra_el_nombre_legible_del_adicional() -> None:
    catalogo = catalogo_con()
    adicional = expresiones.parsear_filtro("ad_zona_comercial:igual:SUR", catalogo)
    base = expresiones.parsear_filtro("dias_atraso:mayor:30", catalogo)

    assert resumen_filtro(adicional, catalogo) == "Zona comercial = SUR"
    assert resumen_filtro(base, catalogo) == "dias atraso > 30"  # como siempre
    assert resumen_filtro(base, CatalogoCartera()) == resumen_filtro(base, catalogo)
    assert "Zona comercial = SUR" in descripcion_sugerida([adicional, base], catalogo)


def test_renombrar_un_adicional_cambia_el_resumen_pero_no_el_filtro_guardado() -> None:
    antes = catalogo_con(TEXTO)
    despues = catalogo_con(
        CampoAdicional(TEXTO.nombre, "Region comercial", TEXTO.tipo, TEXTO.encabezado_origen)
    )
    filtro = expresiones.parsear_filtro("ad_zona_comercial:igual:SUR", antes)

    assert filtro == expresiones.parsear_filtro("ad_zona_comercial:igual:SUR", despues)
    assert resumen_filtro(filtro, despues) == "Region comercial = SUR"


# --- Arquitectura: la constante de la base no se importa fuera de campos.py ----------------------


def _importadores(nombre: str) -> list[str]:
    encontrados = []
    for ruta in sorted(APP.rglob("*.py")):
        if ruta.name == "campos.py" and ruta.parent.name == "seleccion_cartera":
            continue
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.ImportFrom) and any(a.name == nombre for a in nodo.names):
                encontrados.append(str(ruta.relative_to(APP)))
            if isinstance(nodo, ast.Name) and nodo.id == nombre:
                encontrados.append(str(ruta.relative_to(APP)))
    return encontrados


@pytest.mark.parametrize("constante", ["CAMPOS_BASE", "CAMPOS_CARTERA"])
def test_nadie_fuera_de_campos_py_usa_la_constante_de_la_base(constante) -> None:
    assert _importadores(constante) == []


def test_nadie_usa_las_funciones_de_modulo_que_ya_no_existen() -> None:
    from app.core.services.seleccion_cartera import campos

    for nombre in ("tipo_de", "convertir", "validar_filtro", "validar_orden", "validar_indicador"):
        assert not hasattr(campos, nombre), nombre
    texto = "\n".join(p.read_text(encoding="utf-8") for p in APP.rglob("*.py"))
    assert re.search(r"\bcampos\.(tipo_de|convertir|validar_\w+|catalogo_publico)\(", texto) is None

"""Catalogo de funciones del motor (B4a, RF-44): lo que la interfaz usa para armar sus menus.

Todo sale del registro: una funcion nueva aparece con sus parametros, sus tipos y sus claves
i18n sin tocar la API ni el frontend.
"""

from datetime import date

from app.core.entities.texto_enriquecido import TipoValor
from app.core.services.texto_enriquecido import catalogo
from app.core.services.texto_enriquecido.funciones import REGISTRO
from app.core.services.texto_enriquecido.funciones import fecha as modulo_fecha

FUNCIONES = {f.nombre: f for f in catalogo.catalogo_de_funciones()}


def test_estan_todas_las_funciones_del_registro_en_su_orden() -> None:
    assert [f.nombre for f in catalogo.catalogo_de_funciones()] == list(REGISTRO)
    assert len(FUNCIONES) == 23


def test_cada_funcion_trae_su_familia_y_sus_claves_i18n() -> None:
    for nombre, funcion in FUNCIONES.items():
        assert funcion.familia == REGISTRO[nombre].familia
        assert funcion.clave_familia == f"textoEnriquecido.familia.{funcion.familia}"
        assert funcion.clave_nombre == f"textoEnriquecido.funcion.{nombre}.nombre"
        assert funcion.clave_descripcion == f"textoEnriquecido.funcion.{nombre}.descripcion"


def test_los_tipos_de_entrada_y_salida_son_los_del_registro() -> None:
    assert FUNCIONES["formato_fecha"].recibe == ("fecha",)
    assert FUNCIONES["formato_fecha"].devuelve == "texto"
    assert FUNCIONES["a_texto"].recibe == ("numero", "fecha")
    assert FUNCIONES["sumar_dias"].devuelve == "fecha"
    assert FUNCIONES["a_numero"].devuelve == "numero"


def test_si_vacio_devuelve_el_mismo_tipo_que_recibe_y_acepta_nulo() -> None:
    funcion = FUNCIONES["si_vacio"]

    assert funcion.devuelve == "entrada"
    assert funcion.acepta_nulo is True
    assert set(funcion.recibe) == {"texto", "numero", "fecha", "booleano"}
    assert [f.nombre for f in FUNCIONES.values() if f.acepta_nulo] == ["si_vacio"]


def test_los_parametros_dicen_su_tipo_su_rango_y_si_admiten_una_variable() -> None:
    (n,) = FUNCIONES["primeros"].parametros

    assert (n.nombre, n.tipo, n.obligatorio, n.entero) == ("n", "numero", True, True)
    assert (n.minimo, n.maximo, n.acepta_variable) == (1, 10_000, False)
    assert n.clave_nombre == "textoEnriquecido.funcion.primeros.parametro.n"

    (dias,) = FUNCIONES["sumar_dias"].parametros
    assert dias.acepta_variable is True and (dias.minimo, dias.maximo) == (-100_000, 100_000)


def test_un_parametro_de_texto_dice_su_largo() -> None:
    buscar, reemplazo = FUNCIONES["reemplazar"].parametros

    assert (buscar.tipo, buscar.largo_minimo, buscar.largo_maximo) == ("texto", 1, 200)
    assert (reemplazo.largo_minimo, reemplazo.largo_maximo) == (None, 200)
    assert FUNCIONES["rellenar_izquierda"].parametros[1].largo_maximo == 1


def test_un_parametro_con_valor_por_defecto_no_es_obligatorio() -> None:
    decimales, miles, decimal = FUNCIONES["formato_numero"].parametros

    assert [(p.obligatorio, p.por_defecto) for p in (decimales, miles, decimal)] == [
        (False, 2),
        (False, ","),
        (False, "."),
    ]
    prefijo = FUNCIONES["enlace_whatsapp"].parametros[0]
    assert (prefijo.obligatorio, prefijo.por_defecto) == (False, "https://wa.me/+51")


def test_el_valor_alternativo_de_si_vacio_toma_el_tipo_de_la_entrada() -> None:
    (alternativo,) = FUNCIONES["si_vacio"].parametros

    assert (alternativo.tipo, alternativo.acepta_variable) == ("entrada", True)


def test_las_funciones_sin_parametros_no_los_declaran() -> None:
    for nombre in ("mayusculas", "recortar", "sin_tildes", "a_numero", "a_texto"):
        assert FUNCIONES[nombre].parametros == ()


def test_todo_parametro_del_registro_esta_en_el_catalogo_en_su_orden() -> None:
    for nombre, funcion in REGISTRO.items():
        assert [p.nombre for p in FUNCIONES[nombre].parametros] == [
            p.nombre for p in funcion.parametros
        ]


# --- Opciones de los enumerados ----------------------------------------------------------------


def test_el_patron_de_fecha_trae_los_patrones_frecuentes_con_su_ejemplo() -> None:
    for nombre in ("formato_fecha", "a_fecha"):
        (patron,) = FUNCIONES[nombre].parametros
        assert patron.opciones_cerradas is False  # tambien se admite uno personalizado
        assert [(o.valor, o.ejemplo) for o in patron.opciones][:2] == [
            ("dd/mm/aaaa", "05/10/2026"),
            ("aaaa-mm-dd", "2026-10-05"),
        ]


def test_los_separadores_de_formato_numero_son_opciones_cerradas() -> None:
    _, miles, decimal = FUNCIONES["formato_numero"].parametros

    assert [o.valor for o in miles.opciones] == [",", ".", " ", ""]
    assert [o.valor for o in decimal.opciones] == [".", ","]
    assert miles.opciones_cerradas and decimal.opciones_cerradas


def test_un_parametro_sin_opciones_no_las_declara() -> None:
    assert FUNCIONES["primeros"].parametros[0].opciones == ()
    assert FUNCIONES["primeros"].parametros[0].opciones_cerradas is False


def test_los_patrones_frecuentes_son_validos_y_su_ejemplo_se_calcula_con_la_funcion() -> None:
    muestra = catalogo.FECHA_DE_EJEMPLO
    assert muestra == date(2026, 10, 5)

    for patron in catalogo.patrones_de_fecha():
        convertido = modulo_fecha._convertir_patron(patron.patron)  # lo que acepta el motor
        assert patron.ejemplo == modulo_fecha._formato_fecha(muestra, convertido)
        assert patron.ejemplo


def test_las_marcas_de_fecha_son_las_del_motor_con_su_ejemplo() -> None:
    marcas = {m.marca: m for m in catalogo.marcas_de_fecha()}

    assert list(marcas) == ["dd", "mm", "aaaa", "aa", "nombre_mes"]
    assert [marcas[m].ejemplo for m in marcas] == ["05", "10", "2026", "26", "octubre"]
    assert marcas["nombre_mes"].clave == "textoEnriquecido.marcaFecha.nombre_mes"


def test_cada_marca_es_reconocida_por_el_motor() -> None:
    for marca in catalogo.marcas_de_fecha():
        convertido = modulo_fecha._convertir_patron(marca.marca)
        assert modulo_fecha._formato_fecha(catalogo.FECHA_DE_EJEMPLO, convertido) == marca.ejemplo


# --- Familias -----------------------------------------------------------------------------------


def test_las_familias_salen_del_registro_en_orden_de_aparicion() -> None:
    assert catalogo.familias() == ("texto", "numero", "conversion", "fecha", "nulos", "enlaces")


def test_los_tipos_del_catalogo_son_valores_de_tipovalor() -> None:
    usados = {t for f in FUNCIONES.values() for t in (*f.recibe, f.devuelve)} - {"entrada"}

    assert usados <= {t.value for t in TipoValor}

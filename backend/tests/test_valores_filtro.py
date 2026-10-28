"""La lista de valores de un campo de texto para el filtro (T-FV-B2, RF-67): nucleo y API.

Un repositorio en memoria hace de cartera: evalua los filtros de lista sobre productos inventados
(telefonos 900000xxx) y registra lo que le piden. Se comprueba:

- el umbral se decide sobre la FECHA ENTERA (sin filtros) y nunca se devuelve un valor de un campo
  que lo supera;
- la lista es contextual: cuenta lo que cumple los filtros de arriba (la cascada);
- el orden (D-FV-2): cantidad descendente, desempate alfabetico y «(vacio)» siempre al final;
- la comparacion es tal cual (D-FV-1);
- solo campos de texto (base o adicional, archivados incluidos); 400 y 404.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.cartera import obtener_catalogo_cartera, obtener_servicio_cartera
from app.core.config import UMBRAL_VALORES_FILTRO_POR_DEFECTO, Settings
from app.core.entities.campos_adicionales import CampoAdicional, TipoAdicional
from app.core.entities.cartera import (
    ConsultaInvalida,
    Filtro,
    Operador,
    SinVersionVigente,
    ValorDeFiltro,
)
from app.core.services.seleccion_cartera.campos import CatalogoCartera
from app.core.services.seleccion_cartera.expresiones import parsear_filtro
from app.core.services.seleccion_cartera.servicio import ConsultaCarteraService
from app.main import app
from tests.campos_adicionales_memoria import CamposAdicionalesEnMemoria, catalogo_con

FECHA = date(2026, 9, 10)


class CarteraEnMemoria:
    """Productos como dicts. Evalua `igual`, `en`, `no_en`, `vacio` y `no_vacio`: lo que la cascada
    de estas pruebas necesita."""

    def __init__(self, productos: list[dict], vigente: bool = True) -> None:
        self.productos = productos
        self.vigente = vigente
        self.distintos_pedidos: list[tuple] = []
        self.listas_pedidas: list[tuple] = []

    def hay_version_vigente(self, fecha_corte):
        return self.vigente

    @staticmethod
    def _cumple(producto: dict, filtro: Filtro) -> bool:
        valor = producto.get(filtro.campo)
        reales = [v for v in filtro.valores if v is not None]
        con_vacio = len(reales) != len(filtro.valores)
        match filtro.operador:
            case Operador.IGUAL:
                return valor == filtro.valores[0]
            case Operador.EN:
                return valor in reales or (valor is None and con_vacio)
            case Operador.NO_EN:
                return not (valor in reales or (valor is None and con_vacio))
            case Operador.VACIO:
                return valor is None
            case Operador.NO_VACIO:
                return valor is not None
        raise NotImplementedError(filtro.operador)

    def distintos_hasta(self, fecha_corte, campo, tope):
        self.distintos_pedidos.append((fecha_corte, campo, tope))
        distintos = {p.get(campo) for p in self.productos if p.get(campo) is not None}
        return min(len(distintos), tope)  # como el LIMIT: nunca cuenta mas de `tope`

    def valores_de(self, fecha_corte, campo, filtros):
        self.listas_pedidas.append((fecha_corte, campo, tuple(filtros)))
        cuentas: dict = {}
        for producto in self.productos:
            if all(self._cumple(producto, f) for f in filtros):
                cuentas[producto.get(campo)] = cuentas.get(producto.get(campo), 0) + 1
        return [ValorDeFiltro(valor, cantidad) for valor, cantidad in cuentas.items()]


def producto(i: int, **cambios) -> dict:
    datos = {
        "pagare": f"{i:018d}",
        "telefono": f"900000{i:03d}",
        "region": "CUSCO SUR",
        "agencia": "AG 1",
    }
    datos.update(cambios)
    return datos


def servicio_de(productos, umbral=100, catalogo=None, **kwargs):
    cartera = CarteraEnMemoria(productos, **kwargs)
    return ConsultaCarteraService(cartera, catalogo, umbral_valores=umbral), cartera


def lista(valores):
    return [(v.valor, v.cantidad) for v in valores.valores]


# --- El umbral y la lista ------------------------------------------------------------------------


def test_el_umbral_por_defecto_es_100_y_es_el_de_settings() -> None:
    servicio, _ = servicio_de([producto(1)])

    assert servicio.valores(FECHA, "region").umbral == UMBRAL_VALORES_FILTRO_POR_DEFECTO == 100
    assert Settings().umbral_valores_filtro == 100


@pytest.mark.parametrize("umbral", [2, 100, 1000])
def test_el_umbral_de_settings_acepta_de_2_a_1000(umbral) -> None:
    assert Settings(umbral_valores_filtro=umbral).umbral_valores_filtro == umbral


@pytest.mark.parametrize("umbral", [-1, 0, 1, 1001, 100_000])
def test_el_umbral_de_settings_fuera_de_rango_no_arranca(umbral) -> None:
    with pytest.raises(ValidationError):
        Settings(umbral_valores_filtro=umbral)


def test_un_campo_con_pocos_valores_ofrece_su_lista() -> None:
    productos = [producto(1), producto(2), producto(3, region="TACNA")]
    servicio, _ = servicio_de(productos)

    valores = servicio.valores(FECHA, "region")

    assert (valores.campo, valores.umbral, valores.ofrece_lista) == ("region", 100, True)
    assert lista(valores) == [("CUSCO SUR", 2), ("TACNA", 1)]


def test_justo_en_el_umbral_se_ofrece_y_con_uno_mas_no() -> None:
    en_el_umbral = [producto(i, region=f"R{i}") for i in range(1, 4)]
    uno_mas = [producto(i, region=f"R{i}") for i in range(1, 5)]

    justo, _ = servicio_de(en_el_umbral, umbral=3)
    pasado, _ = servicio_de(uno_mas, umbral=3)

    assert justo.valores(FECHA, "region").ofrece_lista is True
    assert pasado.valores(FECHA, "region").ofrece_lista is False


def test_la_decision_pide_umbral_mas_uno_distintos_y_sin_filtros() -> None:
    servicio, cartera = servicio_de([producto(1), producto(2, region="TACNA")], umbral=5)
    filtro = Filtro("agencia", Operador.IGUAL, ("AG 1",))

    servicio.valores(FECHA, "region", [filtro])

    assert cartera.distintos_pedidos == [(FECHA, "region", 6)]  # LIMIT umbral + 1, sin filtros


def test_un_campo_que_supera_el_umbral_no_devuelve_ningun_valor() -> None:
    """Un telefono sintetico (900000xxx) tiene un valor distinto por producto: no se lista."""
    productos = [producto(i) for i in range(1, 151)]
    servicio, cartera = servicio_de(productos)

    valores = servicio.valores(FECHA, "telefono")

    assert (valores.ofrece_lista, valores.valores) == (False, ())
    assert valores.umbral == 100
    assert cartera.listas_pedidas == []  # ni siquiera se consulta la lista


def test_un_documento_o_nombre_tampoco_se_lista_aunque_los_filtros_lo_reduzcan_a_pocos() -> None:
    productos = [producto(i, region="A" if i <= 3 else "B") for i in range(1, 201)]
    servicio, _ = servicio_de(productos)
    filtro = Filtro("region", Operador.IGUAL, ("A",))  # dejaria solo 3 productos

    valores = servicio.valores(FECHA, "telefono", [filtro])

    assert (
        valores.ofrece_lista is False and valores.valores == ()
    )  # se decide sobre la fecha entera


def test_el_control_no_cambia_con_los_filtros_de_arriba() -> None:
    productos = [producto(i, region=f"R{i}", agencia="A" if i < 3 else "B") for i in range(1, 8)]
    servicio, _ = servicio_de(productos, umbral=5)
    solo_a = [Filtro("agencia", Operador.IGUAL, ("A",))]  # dejaria 2 regiones

    sin = servicio.valores(FECHA, "region")
    con = servicio.valores(FECHA, "region", solo_a)

    assert sin.ofrece_lista is con.ofrece_lista is False


def test_los_nulos_no_cuentan_para_el_umbral() -> None:
    productos = [producto(1, region="A"), producto(2, region="B"), producto(3, region=None)]
    servicio, _ = servicio_de(productos, umbral=2)

    valores = servicio.valores(FECHA, "region")

    assert valores.ofrece_lista is True  # 2 distintos y el vacio


# --- La lista contextual y su orden --------------------------------------------------------------


def test_la_lista_cuenta_lo_que_cumple_los_filtros_de_arriba() -> None:
    productos = [
        producto(1, region="A", agencia="X"),
        producto(2, region="A", agencia="Y"),
        producto(3, region="B", agencia="X"),
        producto(4, region="C", agencia="Y"),
    ]
    servicio, cartera = servicio_de(productos)
    arriba = [Filtro("agencia", Operador.IGUAL, ("X",))]

    valores = servicio.valores(FECHA, "region", arriba)

    assert lista(valores) == [("A", 1), ("B", 1)]  # C no tiene productos en la agencia X
    assert cartera.listas_pedidas == [(FECHA, "region", tuple(arriba))]


def test_la_cascada_con_no_en_y_el_vacio_en_los_filtros_de_arriba() -> None:
    productos = [
        producto(1, region="A", agencia="X"),
        producto(2, region="B", agencia=None),
        producto(3, region="B", agencia="Y"),
        producto(4, region="C", agencia=None),
    ]
    servicio, _ = servicio_de(productos)
    sin_agencia_x = [Filtro("agencia", Operador.NO_EN, ("X",))]  # los vacios quedan
    solo_sin_agencia = [Filtro("agencia", Operador.EN, (None,))]

    assert lista(servicio.valores(FECHA, "region", sin_agencia_x)) == [
        ("B", 2),
        ("C", 1),
    ]
    assert lista(servicio.valores(FECHA, "region", solo_sin_agencia)) == [("B", 1), ("C", 1)]


def test_orden_por_cantidad_descendente_con_desempate_alfabetico() -> None:
    productos = [
        *[producto(i, region="B") for i in range(1, 4)],
        *[producto(i, region="Z") for i in range(4, 6)],
        *[producto(i, region="A") for i in range(6, 8)],
        producto(8, region="M"),
    ]
    servicio, _ = servicio_de(productos)

    valores = servicio.valores(FECHA, "region")

    assert lista(valores) == [("B", 3), ("A", 2), ("Z", 2), ("M", 1)]


def test_el_vacio_va_siempre_al_final_aunque_sea_el_mas_grande() -> None:
    productos = [producto(i, region=None) for i in range(1, 6)] + [
        producto(6, region="A"),
        producto(7, region="B"),
    ]
    servicio, _ = servicio_de(productos)

    valores = servicio.valores(FECHA, "region")

    assert lista(valores) == [("A", 1), ("B", 1), (None, 5)]


def test_la_comparacion_es_tal_cual_sin_unir_mayusculas_ni_tildes() -> None:
    productos = [
        producto(1, region="Primera asignación"),
        producto(2, region="PRIMERA ASIGNACION"),
        producto(3, region="Primera asignacion"),
    ]
    servicio, _ = servicio_de(productos)

    valores = servicio.valores(FECHA, "region")

    assert sorted(v.valor for v in valores.valores) == sorted(p["region"] for p in productos)
    assert (
        len(valores.valores) == 3
    )  # tres valores: lo corrige la sabana, la lista lo deja a la vista


def test_una_fecha_sin_productos_ofrece_una_lista_vacia() -> None:
    servicio, _ = servicio_de([])

    valores = servicio.valores(FECHA, "region")

    assert (valores.ofrece_lista, valores.valores) == (True, ())


# --- Que campos y que errores --------------------------------------------------------------------


@pytest.mark.parametrize(
    "campo",
    ["dias_atraso", "saldo_capital_pendiente", "fecha_vencimiento_cuota", "cliente_fallecido"],
)
def test_un_campo_que_no_es_de_texto_es_un_error(campo) -> None:
    servicio, cartera = servicio_de([producto(1)])

    with pytest.raises(ConsultaInvalida, match="solo los de texto"):
        servicio.valores(FECHA, campo)

    assert cartera.distintos_pedidos == []


def test_un_campo_inexistente_es_un_error() -> None:
    servicio, _ = servicio_de([producto(1)])

    with pytest.raises(ConsultaInvalida, match="no existe"):
        servicio.valores(FECHA, "campo_inventado")


def test_sin_version_vigente_es_un_404_y_no_consulta_nada() -> None:
    servicio, cartera = servicio_de([producto(1)], vigente=False)

    with pytest.raises(SinVersionVigente):
        servicio.valores(FECHA, "region")

    assert cartera.distintos_pedidos == [] and cartera.listas_pedidas == []


def test_un_filtro_de_arriba_invalido_es_un_error() -> None:
    servicio, _ = servicio_de([producto(1)])

    with pytest.raises(ConsultaInvalida):
        servicio.valores(FECHA, "region", [Filtro("dias_atraso", Operador.EN, (None,))])


def test_un_adicional_de_texto_tiene_lista_tambien_archivado() -> None:
    zona = CampoAdicional("ad_zona", "Zona", TipoAdicional.TEXTO, "zona")
    vieja = CampoAdicional("ad_vieja", "Vieja", TipoAdicional.TEXTO, "vieja", archivado=True)
    catalogo = CatalogoCartera(CamposAdicionalesEnMemoria([zona, vieja]))
    productos = [
        producto(1, ad_zona="SUR", ad_vieja="X"),
        producto(2, ad_zona="SUR", ad_vieja=None),
    ]
    servicio, _ = servicio_de(productos, catalogo=catalogo)

    assert lista(servicio.valores(FECHA, "ad_zona")) == [("SUR", 2)]
    assert lista(servicio.valores(FECHA, "ad_vieja")) == [("X", 1), (None, 1)]  # archivado: igual


def test_un_adicional_de_numero_no_tiene_lista() -> None:
    servicio, _ = servicio_de([producto(1)], catalogo=catalogo_con())

    with pytest.raises(ConsultaInvalida, match="solo los de texto"):
        servicio.valores(FECHA, "ad_monto_extra")


# --- La API --------------------------------------------------------------------------------------


@pytest.fixture
def api():
    productos = [
        producto(1, region="CUSCO SUR"),
        producto(2, region="CUSCO SUR"),
        producto(3, region="TACNA"),
        producto(4, region=None),
    ]
    servicio, cartera = servicio_de(productos, umbral=3)
    app.dependency_overrides[obtener_servicio_cartera] = lambda: servicio
    app.dependency_overrides[obtener_catalogo_cartera] = lambda: servicio.catalogo
    try:
        yield TestClient(app), cartera
    finally:
        app.dependency_overrides.clear()


def pedir(cliente, campo="region", filtros=(), fecha="2026-09-10"):
    params = [("fecha_corte", fecha), ("campo", campo), *(("filtro", f) for f in filtros)]
    return cliente.get("/cartera/valores", params=params)


def test_la_api_responde_la_lista_con_el_umbral_y_el_vacio_como_null(api) -> None:
    cliente, _ = api

    respuesta = pedir(cliente)

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "campo": "region",
        "umbral": 3,
        "ofrece_lista": True,
        "valores": [
            {"valor": "CUSCO SUR", "cantidad": 2},
            {"valor": "TACNA", "cantidad": 1},
            {"valor": None, "cantidad": 1},
        ],
    }


def test_la_api_pasa_los_filtros_de_arriba_con_la_sintaxis_de_siempre(api) -> None:
    cliente, cartera = api

    respuesta = pedir(cliente, filtros=["region:no_en:TACNA|", "telefono:no_vacio"])

    assert respuesta.status_code == 200
    [(_, campo, filtros)] = cartera.listas_pedidas
    assert campo == "region"
    assert filtros == (
        Filtro("region", Operador.NO_EN, ("TACNA", None)),
        Filtro("telefono", Operador.NO_VACIO),
    )
    # TACNA y los productos sin region quedan fuera: solo CUSCO SUR cuenta.
    assert respuesta.json()["valores"] == [{"valor": "CUSCO SUR", "cantidad": 2}]


def test_la_api_de_un_campo_que_supera_el_umbral_devuelve_la_lista_vacia(api) -> None:
    cliente, _ = api
    # El servicio de `api` tiene umbral 3 y 4 telefonos distintos.
    respuesta = pedir(cliente, campo="telefono")

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "campo": "telefono",
        "umbral": 3,
        "ofrece_lista": False,
        "valores": [],
    }


def test_la_api_rechaza_un_campo_que_no_es_de_texto_con_400(api) -> None:
    cliente, _ = api

    respuesta = pedir(cliente, campo="dias_atraso")

    assert respuesta.status_code == 400 and "solo los de texto" in respuesta.json()["detail"]


def test_la_api_rechaza_un_campo_inexistente_y_un_filtro_malo_con_400(api) -> None:
    cliente, _ = api

    assert pedir(cliente, campo="inventado").status_code == 400
    assert pedir(cliente, filtros=["region:no_existe:x"]).status_code == 400
    assert pedir(cliente, filtros=["dias_atraso:en:5|"]).status_code == 400  # vacio en un numero


def test_la_api_sin_version_vigente_responde_404() -> None:
    servicio, _ = servicio_de([producto(1)], vigente=False)
    app.dependency_overrides[obtener_servicio_cartera] = lambda: servicio
    app.dependency_overrides[obtener_catalogo_cartera] = lambda: servicio.catalogo
    try:
        respuesta = pedir(TestClient(app))
    finally:
        app.dependency_overrides.clear()

    assert respuesta.status_code == 404


def test_la_api_exige_fecha_y_campo() -> None:
    cliente = TestClient(app)

    assert cliente.get("/cartera/valores", params={"campo": "region"}).status_code == 422
    assert cliente.get("/cartera/valores", params={"fecha_corte": "2026-09-10"}).status_code == 422


def test_el_filtro_de_arriba_se_parsea_igual_que_en_el_resto_de_la_api() -> None:
    assert parsear_filtro("region:en:A|", CatalogoCartera()).valores == ("A", None)


def test_el_servicio_de_la_api_toma_el_umbral_de_settings(monkeypatch) -> None:
    from app.api import cartera as api_cartera

    monkeypatch.setattr(api_cartera, "get_settings", lambda: Settings(umbral_valores_filtro=7))

    servicio = api_cartera.crear_servicio_cartera()  # el motor se crea sin conectarse

    assert servicio._umbral_valores == 7

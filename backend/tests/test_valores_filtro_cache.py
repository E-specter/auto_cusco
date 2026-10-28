"""La memoria de la decision y de las listas de valores (T-FV-B3, RF-67).

- Una segunda llamada no repite la consulta del umbral ni la de la lista.
- Otra version vigente de la fecha vuelve a decidir (la clave lleva el id de la carga vigente).
- Es acotada (LRU) y segura entre hilos.
- Nunca guarda los valores de un campo que supera el umbral.
- El resultado es el mismo con y sin memoria.

Reutiliza la cartera en memoria de `test_valores_filtro.py`. Datos sinteticos.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest

from app.api import cartera as api_cartera
from app.core.entities.cartera import Filtro, Operador, SinVersionVigente
from app.core.services.seleccion_cartera.cache_valores import (
    ENTRADAS_POR_DEFECTO,
    CacheValoresFiltro,
)
from app.core.services.seleccion_cartera.servicio import ConsultaCarteraService
from tests.test_valores_filtro import CarteraEnMemoria, lista, producto

FECHA = date(2026, 9, 10)
PRODUCTOS = [
    producto(1, region="A", agencia="X"),
    producto(2, region="A", agencia="Y"),
    producto(3, region="B", agencia="X"),
    producto(4, region=None, agencia="Y"),
]


def servicio_con(cartera=None, cache=None, umbral=5):
    cartera = cartera or CarteraEnMemoria(list(PRODUCTOS))
    return ConsultaCarteraService(cartera, umbral_valores=umbral, cache_valores=cache), cartera


# --- Que no repite consultas ----------------------------------------------------------------------


def test_una_segunda_llamada_no_repite_ni_la_decision_ni_la_lista() -> None:
    servicio, cartera = servicio_con()

    primera = servicio.valores(FECHA, "region")
    segunda = servicio.valores(FECHA, "region")

    assert primera == segunda
    assert len(cartera.distintos_pedidos) == 1 and len(cartera.listas_pedidas) == 1


def test_la_decision_se_comparte_entre_listas_con_distintos_filtros_de_arriba() -> None:
    servicio, cartera = servicio_con()

    servicio.valores(FECHA, "region")
    servicio.valores(FECHA, "region", [Filtro("agencia", Operador.IGUAL, ("X",))])

    assert len(cartera.distintos_pedidos) == 1  # la decision es de la fecha entera
    assert len(cartera.listas_pedidas) == 2  # cada cascada tiene su lista


def test_la_misma_cascada_repetida_no_vuelve_a_consultar() -> None:
    servicio, cartera = servicio_con()
    arriba = [Filtro("agencia", Operador.NO_EN, ("X", None))]

    uno = servicio.valores(FECHA, "region", arriba)
    otro = servicio.valores(FECHA, "region", list(arriba))

    assert uno == otro and len(cartera.listas_pedidas) == 1


def test_otro_campo_u_otro_orden_de_filtros_es_otra_clave() -> None:
    servicio, cartera = servicio_con()
    f1, f2 = Filtro("agencia", Operador.IGUAL, ("X",)), Filtro("region", Operador.NO_VACIO)

    servicio.valores(FECHA, "region", [f1, f2])
    servicio.valores(FECHA, "region", [f2, f1])  # el orden es parte de la cascada
    servicio.valores(FECHA, "agencia")

    assert len(cartera.listas_pedidas) == 3
    assert len(cartera.distintos_pedidos) == 2  # region y agencia


def test_un_campo_que_supera_el_umbral_se_decide_una_vez_y_no_guarda_valores() -> None:
    cache = CacheValoresFiltro()
    servicio, cartera = servicio_con(
        CarteraEnMemoria([producto(i) for i in range(1, 30)]), cache, 5
    )

    primera = servicio.valores(FECHA, "telefono")
    segunda = servicio.valores(FECHA, "telefono")

    assert (primera.ofrece_lista, primera.valores) == (False, ())
    assert segunda == primera
    assert len(cartera.distintos_pedidos) == 1 and cartera.listas_pedidas == []
    assert cache.tamanos == (1, 0)  # la decision, y ninguna lista: nunca hubo valores que guardar


def test_la_memoria_no_cambia_el_resultado() -> None:
    con, _ = servicio_con()
    sin = [servicio_con()[0] for _ in range(3)]  # una memoria nueva en cada uno
    arriba = [Filtro("agencia", Operador.EN, ("X", "Y"))]

    esperado = [sin[i].valores(FECHA, "region", arriba) for i in range(3)]
    obtenido = [con.valores(FECHA, "region", arriba) for _ in range(3)]

    assert obtenido == esperado


# --- La version vigente es parte de la clave ------------------------------------------------------


def test_otra_version_vigente_vuelve_a_decidir_y_a_listar() -> None:
    servicio, cartera = servicio_con()
    servicio.valores(FECHA, "region")

    cartera.carga_id = 2  # la fecha pasa a otra version vigente
    cartera.productos = [producto(1, region="Z")]
    nueva = servicio.valores(FECHA, "region")

    assert lista(nueva) == [("Z", 1)]  # no sirve la lista de la version anterior
    assert len(cartera.distintos_pedidos) == 2 and len(cartera.listas_pedidas) == 2


def test_volver_a_la_version_anterior_reutiliza_lo_que_ya_se_calculo() -> None:
    servicio, cartera = servicio_con()
    servicio.valores(FECHA, "region")
    cartera.carga_id = 2
    servicio.valores(FECHA, "region")

    cartera.carga_id = 1
    servicio.valores(FECHA, "region")

    assert len(cartera.distintos_pedidos) == 2  # la version 1 no se repite


def test_el_umbral_es_parte_de_la_clave() -> None:
    cache = CacheValoresFiltro()
    cartera = CarteraEnMemoria([producto(i, region=f"R{i}") for i in range(1, 8)])
    chico = ConsultaCarteraService(cartera, umbral_valores=3, cache_valores=cache)
    grande = ConsultaCarteraService(cartera, umbral_valores=10, cache_valores=cache)

    assert chico.valores(FECHA, "region").ofrece_lista is False
    assert grande.valores(FECHA, "region").ofrece_lista is True  # no hereda el «no» del umbral 3


def test_sin_version_vigente_sigue_siendo_un_404_aunque_haya_memoria() -> None:
    servicio, cartera = servicio_con()
    servicio.valores(FECHA, "region")
    cartera.vigente = False

    with pytest.raises(SinVersionVigente):
        servicio.valores(FECHA, "region")


# --- Acotada y segura entre hilos -----------------------------------------------------------------


def test_la_memoria_es_acotada_y_descarta_la_menos_usada() -> None:
    cache = CacheValoresFiltro(entradas=2)
    cache.guardar_decision("a", True)
    cache.guardar_decision("b", False)
    assert cache.decision("a") is True  # «a» pasa a ser la mas reciente
    cache.guardar_decision("c", True)  # sale «b»

    assert cache.decision("b") is None
    assert (cache.decision("a"), cache.decision("c")) == (True, True)
    assert cache.tamanos[0] == 2


def test_las_listas_tambien_estan_acotadas() -> None:
    cache = CacheValoresFiltro(entradas=3)

    for i in range(10):
        cache.guardar_lista(i, ())

    assert cache.tamanos == (0, 3)
    assert cache.lista(9) == () and cache.lista(0) is None  # una lista vacia no es «ausente»


def test_un_false_guardado_no_se_confunde_con_ausente() -> None:
    cache = CacheValoresFiltro()
    cache.guardar_decision("k", False)

    assert cache.decision("k") is False and cache.decision("otra") is None


def test_el_tamano_por_defecto_es_unas_256_entradas() -> None:
    assert ENTRADAS_POR_DEFECTO == 256


def test_vaciar_deja_la_memoria_sin_nada() -> None:
    cache = CacheValoresFiltro()
    cache.guardar_decision("k", True)
    cache.guardar_lista("k", ())

    cache.vaciar()

    assert cache.tamanos == (0, 0)


def test_varios_hilos_a_la_vez_dan_el_mismo_resultado_y_no_rompen_la_memoria() -> None:
    cache = CacheValoresFiltro(entradas=8)
    servicio, _ = servicio_con(cache=cache)
    arribas = [[Filtro("agencia", Operador.IGUAL, (a,))] for a in ("X", "Y")] + [[]]

    def pedir(i):
        return lista(servicio.valores(FECHA, "region", arribas[i % 3]))

    with ThreadPoolExecutor(max_workers=8) as pool:
        resultados = list(pool.map(pedir, range(240)))

    for i, resultado in enumerate(resultados):
        assert resultado == lista(servicio_con()[0].valores(FECHA, "region", arribas[i % 3]))
    assert cache.tamanos[1] <= 8


# --- La API usa una memoria compartida ------------------------------------------------------------


def test_la_api_comparte_una_sola_memoria_entre_pedidos() -> None:
    primero = api_cartera.crear_servicio_cartera()
    segundo = api_cartera.crear_servicio_cartera()

    assert primero is not segundo  # un servicio por pedido...
    assert primero._cache_valores is segundo._cache_valores is api_cartera.CACHE_VALORES


# --- La clave usa los filtros parseados; la etiqueta no viaja en lo guardado -------------------


def test_los_espacios_alrededor_de_los_valores_dan_la_misma_clave() -> None:
    """La clave lleva los `Filtro` ya parseados (hashables): `A|B` y `A | B` son el mismo filtro."""
    from app.core.services.seleccion_cartera.expresiones import parsear_filtro

    servicio, cartera = servicio_con()
    catalogo = servicio.catalogo
    junto = parsear_filtro("region:no_en:A|B", catalogo)
    con_espacios = parsear_filtro("region:no_en: A | B ", catalogo)

    servicio.valores(FECHA, "agencia", [junto])
    servicio.valores(FECHA, "agencia", [con_espacios])

    assert junto == con_espacios and hash(junto) == hash(con_espacios)
    assert len(cartera.listas_pedidas) == 1  # la segunda salio de la memoria


def test_un_adicional_archivado_o_renombrado_despues_de_guardar_la_lista_no_rompe_nada() -> None:
    """Los valores no cambian al archivar o renombrar, y la etiqueta no viaja dentro de lo guardado:
    la lista guardada son solo (valor, cantidad)."""
    from app.core.entities.campos_adicionales import CampoAdicional, TipoAdicional
    from app.core.entities.cartera import ValorDeFiltro
    from app.core.services.seleccion_cartera.campos import CatalogoCartera
    from tests.campos_adicionales_memoria import CamposAdicionalesEnMemoria

    zona = CampoAdicional("ad_zona", "Zona", TipoAdicional.TEXTO, "zona")
    definiciones = CamposAdicionalesEnMemoria([zona])
    cartera = CarteraEnMemoria([producto(1, ad_zona="SUR"), producto(2, ad_zona="SUR")])
    cache = CacheValoresFiltro()

    def servicio():  # un catalogo por pedido, como la API: lee las definiciones de ese momento
        return ConsultaCarteraService(
            cartera, CatalogoCartera(definiciones), umbral_valores=5, cache_valores=cache
        )

    antes = servicio().valores(FECHA, "ad_zona")
    definiciones.campos[0] = CampoAdicional(
        "ad_zona", "Zona comercial", TipoAdicional.TEXTO, "zona", archivado=True
    )  # renombrado y archivado
    despues = servicio().valores(FECHA, "ad_zona")

    assert lista(antes) == lista(despues) == [("SUR", 2)]
    assert len(cartera.listas_pedidas) == 1  # la lista siguio sirviendo desde la memoria
    guardado = cache.lista((1, "ad_zona", (), 5))
    assert guardado == (ValorDeFiltro("SUR", 2),)  # solo valor y cantidad: ni nombre ni etiqueta
    assert not any("Zona" in repr(x) for x in guardado)

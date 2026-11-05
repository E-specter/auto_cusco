"""La migracion de datos d3a9c5e1b742 (T-HI-B7, parte 2, D-CA-2 opcion a), sin base.

Marca `obligatoria = true` en los nodos de campos adicionales de los speeches guardados, para que
lo de hoy (un adicional vacio excluye) siga igual. Aqui se prueba su transformacion y su guardia
sobre JSON sintetico; la ida y vuelta contra PostgreSQL la corre `architec` con la base.
"""

import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).resolve().parents[1]
REVISION = "d3a9c5e1b742"
ADICIONALES = {"ad_zona", "ad_monto"}


def _migracion():
    ruta = next((BACKEND / "migrations" / "versions").glob(f"{REVISION}_*.py"))
    especificacion = importlib.util.spec_from_file_location("migracion_obligatorias", ruta)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


M = _migracion()


def _nodo(nombre: str, obligatoria: bool | None = False, funciones=()) -> dict:
    nodo = {"tipo": "variable", "nombre": nombre, "funciones": list(funciones)}
    if obligatoria is not None:
        nodo["obligatoria"] = obligatoria
    return nodo


def _texto(valor: str) -> dict:
    return {"tipo": "texto", "valor": valor}


def _version(*nodos: dict) -> list[dict]:
    return [{"segmento": "1_a_8", "expresion": {"nodos": list(nodos)}}]


def _nodos(expresiones: list[dict]) -> list[dict]:
    return expresiones[0]["expresion"]["nodos"]


# --- La transformacion: los tres casos ----------------------------------------------------------


def test_un_adicional_como_variable_base_se_marca_y_su_funcion_queda_igual() -> None:
    primeros = {"nombre": "primeros", "args": [12]}
    expresiones = _version(_texto("Zona "), _nodo("ad_zona", False, [primeros]))

    cambiados = M.marcar_obligatorios(expresiones, ADICIONALES)

    assert cambiados == 1
    assert _nodos(expresiones)[1] == _nodo("ad_zona", True, [primeros])
    assert _nodos(expresiones)[0] == _texto("Zona ")


def test_un_adicional_como_argumento_no_marca_el_nodo_anfitrion() -> None:
    # `titular | sumar(@ad_monto)`: el adicional es argumento. No hay nodo `variable` de adicional
    # que marcar, y el titular no se toca; el speech sigue exigiendo el argumento por su cuenta.
    anfitrion = _nodo("titular", False, [{"nombre": "sumar", "args": [{"variable": "ad_monto"}]}])
    expresiones = _version(anfitrion)
    antes = copy.deepcopy(expresiones)

    assert M.marcar_obligatorios(expresiones, ADICIONALES) == 0
    assert expresiones == antes


def test_una_variable_propia_no_se_toca() -> None:
    propias = ("titular", "fecha_vencimiento_cuota", "whatsapp_contacto", "dias_atraso_ajustados")
    expresiones = _version(*(_nodo(n) for n in propias), _nodo("region"))
    antes = copy.deepcopy(expresiones)

    assert M.marcar_obligatorios(expresiones, ADICIONALES) == 0
    assert expresiones == antes  # tampoco un campo base que no es adicional


# --- Idempotencia, orden y todas las versiones --------------------------------------------------


def test_es_idempotente_y_no_cuenta_lo_ya_marcado() -> None:
    expresiones = _version(_nodo("ad_zona"), _nodo("ad_monto", True))

    assert M.marcar_obligatorios(expresiones, ADICIONALES) == 1
    una_vez = copy.deepcopy(expresiones)
    assert M.marcar_obligatorios(expresiones, ADICIONALES) == 0
    assert expresiones == una_vez


def test_el_orden_de_las_claves_del_nodo_se_conserva() -> None:
    sin_clave = _nodo("ad_zona", None)  # sin `obligatoria`: se agrega al final
    con_clave = {"tipo": "variable", "obligatoria": False, "nombre": "ad_monto", "funciones": []}
    expresiones = _version(sin_clave, con_clave)

    M.marcar_obligatorios(expresiones, ADICIONALES)

    assert list(_nodos(expresiones)[0]) == ["tipo", "nombre", "funciones", "obligatoria"]
    assert list(_nodos(expresiones)[1]) == ["tipo", "obligatoria", "nombre", "funciones"]
    assert [n["obligatoria"] for n in _nodos(expresiones)] == [True, True]


def test_recorre_todos_los_segmentos_de_una_version() -> None:
    expresiones = [
        {"segmento": s, "expresion": {"nodos": [_nodo("ad_zona")]}} for s in ("1_a_8", "9_a_30")
    ]

    assert M.marcar_obligatorios(expresiones, ADICIONALES) == 2
    assert all(e["expresion"]["nodos"][0]["obligatoria"] for e in expresiones)


def test_una_version_sin_expresiones_o_con_un_segmento_vacio_no_falla() -> None:
    assert M.marcar_obligatorios(None, ADICIONALES) == 0
    assert M.marcar_obligatorios([], ADICIONALES) == 0
    assert (
        M.marcar_obligatorios([{"segmento": "1_a_8", "expresion": {"nodos": []}}], ADICIONALES) == 0
    )


# --- La guardia y el downgrade -------------------------------------------------------------------


def test_hay_marcados_solo_mira_los_nodos_de_adicionales() -> None:
    assert not M.hay_marcados(
        _version(_nodo("ad_zona", False), _nodo("titular", True)), ADICIONALES
    )
    assert M.hay_marcados(_version(_nodo("ad_zona", True)), ADICIONALES)


def test_el_downgrade_devuelve_lo_marcado_a_false_y_ida_y_vuelta_da_lo_original() -> None:
    original = _version(_texto("a"), _nodo("ad_zona"), _nodo("titular"), _nodo("ad_monto"))
    expresiones = copy.deepcopy(original)

    M.marcar_obligatorios(expresiones, ADICIONALES)
    assert expresiones != original
    assert M.desmarcar_obligatorios(expresiones, ADICIONALES) == 2

    assert expresiones == original


class _Resultado:
    def __init__(self, filas) -> None:
        self._filas = filas

    def __iter__(self):
        return iter(self._filas)

    def all(self):
        return list(self._filas)


class _Conexion:
    """Una base de mentira: `campo_adicional`, las versiones y lo que se escribe."""

    def __init__(self, versiones: dict[int, list[dict]]) -> None:
        self.versiones = versiones
        self.escrito: dict[int, list[dict]] = {}

    def execute(self, sentencia, parametros=None):
        texto = str(sentencia)
        if "campo_adicional" in texto:
            return _Resultado([SimpleNamespace(nombre=n) for n in sorted(ADICIONALES)])
        if texto.startswith("SELECT id, expresiones"):
            return _Resultado(
                [SimpleNamespace(id=i, expresiones=e) for i, e in sorted(self.versiones.items())]
            )
        self.escrito[parametros["id"]] = parametros["expresiones"]
        return _Resultado([])


def _correr(monkeypatch, funcion: str, conexion: _Conexion) -> None:
    monkeypatch.setattr(M, "op", SimpleNamespace(get_bind=lambda: conexion))
    monkeypatch.setattr(M, "context", SimpleNamespace(is_offline_mode=lambda: False))
    getattr(M, funcion)()


def test_el_upgrade_marca_todas_las_versiones_y_solo_escribe_las_que_cambian(monkeypatch) -> None:
    conexion = _Conexion(
        {
            1: _version(_nodo("ad_zona")),
            2: _version(_nodo("titular")),  # nada que marcar: no se escribe
            3: _version(_nodo("ad_monto"), _nodo("ad_zona")),
        }
    )

    _correr(monkeypatch, "upgrade", conexion)

    assert sorted(conexion.escrito) == [1, 3]
    assert [n["obligatoria"] for n in _nodos(conexion.escrito[3])] == [True, True]


def test_el_upgrade_se_detiene_sin_escribir_si_ya_hay_un_adicional_marcado(monkeypatch) -> None:
    conexion = _Conexion({1: _version(_nodo("ad_zona")), 2: _version(_nodo("ad_monto", True))})

    with pytest.raises(M.AdicionalYaMarcado):
        _correr(monkeypatch, "upgrade", conexion)

    assert conexion.escrito == {}  # no toco ningun dato


def test_el_downgrade_desmarca_y_deja_el_resto(monkeypatch) -> None:
    conexion = _Conexion({1: _version(_nodo("ad_zona", True), _nodo("titular", True))})

    _correr(monkeypatch, "downgrade", conexion)

    nodos = _nodos(conexion.escrito[1])
    assert (nodos[0]["obligatoria"], nodos[1]["obligatoria"]) == (False, True)


def test_en_modo_offline_no_hace_nada(monkeypatch) -> None:
    monkeypatch.setattr(M, "context", SimpleNamespace(is_offline_mode=lambda: True))
    monkeypatch.setattr(M, "op", SimpleNamespace(get_bind=lambda: pytest.fail("no debe leer")))

    M.upgrade()
    M.downgrade()


def test_la_revision_cuelga_de_la_anterior_y_el_arbol_tiene_una_sola_cabeza() -> None:
    configuracion = Config(str(BACKEND / "alembic.ini"))
    configuracion.set_main_option("script_location", str(BACKEND / "migrations"))
    directorio = ScriptDirectory.from_config(configuracion)

    assert directorio.get_revision(REVISION).down_revision == "c4f8a2d6b173"
    assert len(directorio.get_heads()) == 1

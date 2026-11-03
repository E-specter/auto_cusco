"""Las reglas de una plataforma de destino y la etiqueta de una columna (T-HI-B2, RF-49, RF-72).

B2 no registra ninguna plataforma real: aqui hay una sintetica (`SINTETICA`) y otra de una sola
columna fija (`UNA_FIJA`). El repositorio es el doble en memoria; PostgreSQL, en
`test_definiciones_columnas_postgres.py`.
"""

import io
import random
import re
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.adapters.persistence.modelos import Base
from app.api.definiciones_columnas import (
    obtener_registro_plataformas,
    obtener_servicio_definiciones,
)
from app.core.entities.definiciones_columnas import LARGO_MAXIMO_ETIQUETA
from app.core.entities.mapeo import TipoSalida
from app.core.entities.plataformas import ColumnaFija, PlataformaDesconocida, ReglasPlataforma
from app.core.entities.texto_enriquecido import CodigoTexto
from app.core.services.contextos_texto import contexto_cartera
from app.core.services.definiciones_columnas.plataformas import (
    RegistroPlataformas,
    problemas_de_plataforma,
)
from app.core.services.definiciones_columnas.servicio import (
    DefinicionesColumnasService,
    DefinicionInvalida,
)
from app.core.services.mapeo_campos.serializacion import (
    DefinicionIlegible,
    definicion_a_dict,
    definicion_desde_dict,
)
from app.core.services.seleccion_cartera.campos import CatalogoCartera
from app.main import app
from tests.definiciones_memoria import RepositorioEnMemoria

CARTERA = contexto_cartera(CatalogoCartera())

SINTETICA = ReglasPlataforma(
    clave="sintetica",
    etiqueta="Sintetica",
    columnas_fijas=(
        ColumnaFija(1, "destino", "[@titular]", TipoSalida.TEXTO),
        ColumnaFija(2, "canal", "sms", TipoSalida.TEXTO, contenido_editable=False),
        ColumnaFija(3, "importe", None, TipoSalida.NUMERO, celda_texto=True),
    ),
    encabezado_por_posicion="[$VAR{n}$]",
    tipo_resto=TipoSalida.TEXTO,
)
UNA_FIJA = ReglasPlataforma(
    clave="una_fija",
    etiqueta="Una fija",
    columnas_fijas=(ColumnaFija(1, "destino", None, TipoSalida.TEXTO),),
    tipo_resto=TipoSalida.TEXTO,
    admite_mas_columnas=False,
)
SOLO_UNA_Y_MAS = ReglasPlataforma(
    clave="una_y_mas",
    etiqueta="Una y mas",
    columnas_fijas=(ColumnaFija(1, "destino", None, TipoSalida.TEXTO),),
    tipo_resto=TipoSalida.TEXTO,
)


def _columna(nombre: str, orden: int, tipo: str = "texto", **extra) -> dict:
    return {
        "nombre": nombre,
        "orden": orden,
        "tipo": tipo,
        "expresion": {"nodos": [{"tipo": "texto", "valor": "x"}]},
        **extra,
    }


def _dato(*columnas: dict, **extra) -> dict:
    return {"nombre": "Carga", "columnas": list(columnas), **extra}


def _leer(dato: dict):
    return definicion_desde_dict(
        dato, CARTERA.tabla_rangos, CARTERA.variable_dias, admitir_plantillas=True
    )


def _problemas(dato: dict, reglas: ReglasPlataforma) -> list[tuple]:
    return [
        (p.problema.codigo, p.columna, p.problema.nombre)
        for p in problemas_de_plataforma(_leer(dato), reglas)
    ]


def _cumple(reglas: ReglasPlataforma, rng: random.Random, extras: int) -> dict:
    """Una definicion que cumple las reglas: las fijas en su lugar y `extras` columnas del resto."""
    columnas = [_columna(f.nombre, i, f.tipo.value) for i, f in enumerate(reglas.columnas_fijas)]
    for j in range(extras):
        nombre = f"extra{j}_{rng.randrange(10_000)}"
        tipo = (reglas.tipo_resto or rng.choice(list(TipoSalida))).value
        columnas.append(_columna(nombre, len(columnas), tipo))
    return _dato(*columnas)


# --- Las reglas y el registro -------------------------------------------------------------------


def test_las_posiciones_de_las_fijas_son_consecutivas_desde_1() -> None:
    with pytest.raises(ValueError):
        ReglasPlataforma("x", "X", (ColumnaFija(2, "a", None, TipoSalida.TEXTO),))
    with pytest.raises(ValueError):
        ReglasPlataforma(
            "x",
            "X",
            (
                ColumnaFija(1, "a", None, TipoSalida.TEXTO),
                ColumnaFija(1, "b", None, TipoSalida.TEXTO),
            ),
        )


def test_dos_fijas_no_repiten_nombre_ni_la_plataforma_queda_sin_clave() -> None:
    with pytest.raises(ValueError):
        ReglasPlataforma(
            "x",
            "X",
            (
                ColumnaFija(1, "a", None, TipoSalida.TEXTO),
                ColumnaFija(2, "a", None, TipoSalida.TEXTO),
            ),
        )
    with pytest.raises(ValueError):
        ReglasPlataforma(" ", "X")
    with pytest.raises(ValueError):
        ReglasPlataforma("x", "X", encabezado_por_posicion="sin posicion")


def test_el_registro_conserva_el_orden_y_no_repite_ni_inventa_plataformas() -> None:
    registro = RegistroPlataformas([SINTETICA, UNA_FIJA])

    assert [r.clave for r in registro.disponibles()] == ["sintetica", "una_fija"]
    assert "sintetica" in registro and "otra" not in registro
    assert registro.obtener("una_fija") is UNA_FIJA
    with pytest.raises(PlataformaDesconocida) as error:
        registro.obtener("otra")
    assert error.value.clave == "otra"
    with pytest.raises(ValueError):
        registro.registrar(SINTETICA)


# --- Validar una definicion contra las reglas ---------------------------------------------------


def test_una_definicion_generada_con_las_reglas_no_tiene_problemas() -> None:
    rng = random.Random(72)
    for reglas in (SINTETICA, UNA_FIJA, SOLO_UNA_Y_MAS):
        for extras in range(4):
            if not reglas.admite_mas_columnas and extras:
                continue
            for _ in range(10):
                assert _problemas(_cumple(reglas, rng, extras), reglas) == [], (reglas, extras)


def test_quitar_la_unica_columna_fija_da_exactamente_un_problema() -> None:
    rng = random.Random(1)
    for extras in range(1, 5):
        dato = _cumple(SOLO_UNA_Y_MAS, rng, extras)
        dato["columnas"] = dato["columnas"][1:]

        assert [p[0] for p in _problemas(dato, SOLO_UNA_Y_MAS)] == [
            CodigoTexto.PLATAFORMA_COLUMNA_FIJA_AUSENTE
        ]


def test_mover_la_unica_columna_fija_da_exactamente_un_problema_en_la_columna_movida() -> None:
    rng = random.Random(2)
    for extras in range(1, 5):
        for destino in range(1, extras + 1):
            dato = _cumple(SOLO_UNA_Y_MAS, rng, extras)
            fija = dato["columnas"].pop(0)
            dato["columnas"].insert(destino, fija)
            for orden, columna in enumerate(dato["columnas"]):
                columna["orden"] = orden  # el `orden` manda sobre la posicion en el pedido

            assert _problemas(dato, SOLO_UNA_Y_MAS) == [
                (CodigoTexto.PLATAFORMA_COLUMNA_FIJA_MOVIDA, destino, "destino")
            ]


def test_cada_problema_lleva_su_columna() -> None:
    dato = _dato(
        _columna("destino", 0, "numero"),  # tipo de la fija
        _columna("canal", 1),
        _columna("importe", 2, "numero"),
        _columna("nota", 3, "numero"),  # tipo del resto
    )

    assert _problemas(dato, SINTETICA) == [
        (CodigoTexto.PLATAFORMA_TIPO_DE_COLUMNA_FIJA, 0, "destino"),
        (CodigoTexto.PLATAFORMA_TIPO_DEL_RESTO, 3, "nota"),
    ]


def test_una_fija_que_falta_se_ubica_en_la_columna_que_ocupa_su_lugar() -> None:
    dato = _dato(_columna("destino", 0), _columna("importe", 1, "numero"))

    assert _problemas(dato, SINTETICA) == [
        (CodigoTexto.PLATAFORMA_COLUMNA_FIJA_AUSENTE, 1, "canal"),
        (CodigoTexto.PLATAFORMA_COLUMNA_FIJA_MOVIDA, 1, "importe"),
    ]


def test_sin_admitir_mas_columnas_cada_columna_de_mas_es_un_problema() -> None:
    dato = _dato(_columna("destino", 0), _columna("a", 1), _columna("b", 2))

    assert _problemas(dato, UNA_FIJA) == [
        (CodigoTexto.PLATAFORMA_COLUMNAS_DE_MAS, 1, "a"),
        (CodigoTexto.PLATAFORMA_COLUMNAS_DE_MAS, 2, "b"),
    ]


def test_el_encabezado_por_posicion_no_se_valida() -> None:
    # `[$VAR{n}$]` es solo el nombre por defecto: el usuario lo puede cambiar y se conserva.
    dato = _cumple(SINTETICA, random.Random(3), 0)
    dato["columnas"] += [_columna("Mi nombre", 3), _columna("[$VAR9$]", 4)]

    assert _problemas(dato, SINTETICA) == []


def test_las_columnas_se_ubican_por_su_posicion_en_el_pedido_no_por_su_orden() -> None:
    # En el pedido la fija va segunda pero su `orden` la pone primera: la posicion que se informa
    # es la del pedido (RF-46).
    dato = _dato(_columna("a", 1), _columna("destino", 0))

    assert _problemas(dato, SOLO_UNA_Y_MAS) == []
    assert _problemas(_dato(_columna("a", 0), _columna("destino", 1)), SOLO_UNA_Y_MAS) == [
        (CodigoTexto.PLATAFORMA_COLUMNA_FIJA_MOVIDA, 1, "destino")
    ]


# --- La etiqueta de la columna (RF-49) ----------------------------------------------------------


def test_la_etiqueta_se_recorta_y_hace_el_viaje_de_ida_y_vuelta() -> None:
    dato = _dato(_columna("a", 0, etiqueta="  Telefono del titular  "))

    leida = _leer(dato)
    guardado = definicion_a_dict(leida, con_nombre=False)

    assert leida.definicion.campos[0].etiqueta == "Telefono del titular"
    assert guardado["columnas"][0]["etiqueta"] == "Telefono del titular"
    assert definicion_a_dict(_leer({**guardado, "nombre": "Carga"}), con_nombre=False) == guardado


def test_una_version_sin_etiqueta_se_guarda_sin_la_clave_y_da_la_misma_ida_y_vuelta() -> None:
    guardado = definicion_a_dict(_leer(_dato(_columna("a", 0))), con_nombre=False)

    assert "etiqueta" not in guardado["columnas"][0]
    assert definicion_a_dict(_leer({**guardado, "nombre": "Carga"}), con_nombre=False) == guardado


@pytest.mark.parametrize("etiqueta", ["", "   ", 7, "x" * (LARGO_MAXIMO_ETIQUETA + 1)])
def test_una_etiqueta_vacia_no_texto_o_larga_es_un_problema_de_su_columna(etiqueta) -> None:
    with pytest.raises(DefinicionIlegible) as error:
        _leer(_dato(_columna("a", 0), _columna("b", 1, etiqueta=etiqueta)))

    assert [(p.columna, p.campo) for p in error.value.problemas] == [(1, "etiqueta")]


def test_la_etiqueta_de_120_caracteres_cabe() -> None:
    leida = _leer(_dato(_columna("a", 0, etiqueta="x" * LARGO_MAXIMO_ETIQUETA)))

    assert len(leida.definicion.campos[0].etiqueta) == LARGO_MAXIMO_ETIQUETA


def test_la_etiqueta_no_cambia_la_carga_generada() -> None:
    # S-5: el encabezado es siempre `nombre`; la etiqueta no cuenta para el generador ni el archivo.
    con = _leer(_dato(_columna("a", 0, etiqueta="Una etiqueta"))).definicion.campos[0]
    sin = _leer(_dato(_columna("a", 0))).definicion.campos[0]

    assert (con.nombre, con.expresion, con.tipo) == (sin.nombre, sin.expresion, sin.tipo)


# --- El servicio --------------------------------------------------------------------------------


def _servicio(
    *reglas: ReglasPlataforma,
) -> tuple[DefinicionesColumnasService, RepositorioEnMemoria]:
    repositorio = RepositorioEnMemoria()
    return (
        DefinicionesColumnasService(repositorio, CARTERA, RegistroPlataformas(reglas)),
        repositorio,
    )


def _cuerpo(**extra) -> dict:
    return _dato(_columna("destino", 0), _columna("nota", 1), **extra)


def test_la_plataforma_se_guarda_al_crear_y_sale_en_el_listado_y_la_vista() -> None:
    servicio, _ = _servicio(SOLO_UNA_Y_MAS)

    vista = servicio.crear(_cuerpo(plataforma="una_y_mas"))

    assert vista.definicion.plataforma == "una_y_mas"
    assert "plataforma" not in vista.version.contenido  # no es parte del contenido de la version
    assert [r.plataforma for r in servicio.listar()] == ["una_y_mas"]
    assert servicio.obtener(vista.definicion.id).problemas == ()


def test_sin_plataforma_todo_sigue_como_antes() -> None:
    servicio, _ = _servicio(SOLO_UNA_Y_MAS)

    vista = servicio.crear(_dato(_columna("lo_que_sea", 0)))

    assert vista.definicion.plataforma is None
    assert servicio.obtener(vista.definicion.id).problemas == ()
    assert (
        servicio.agregar_version(vista.definicion.id, _dato(_columna("otra", 0))).version.numero
        == 2
    )


def test_una_plataforma_desconocida_al_crear_es_un_problema_y_no_se_guarda() -> None:
    servicio, repositorio = _servicio(SOLO_UNA_Y_MAS)

    with pytest.raises(DefinicionInvalida) as error:
        servicio.crear(_cuerpo(plataforma="inventada"))

    [problema] = error.value.problemas
    assert problema.problema.codigo is CodigoTexto.PLATAFORMA_DESCONOCIDA
    assert problema.campo == "plataforma"
    assert repositorio.definiciones == {}


def test_al_crear_se_exigen_las_reglas_de_la_plataforma_con_la_columna_de_cada_problema() -> None:
    servicio, repositorio = _servicio(SOLO_UNA_Y_MAS)

    with pytest.raises(DefinicionInvalida) as error:
        servicio.crear(_dato(_columna("nota", 0), plataforma="una_y_mas"))

    assert [(p.problema.codigo, p.columna) for p in error.value.problemas] == [
        (CodigoTexto.PLATAFORMA_COLUMNA_FIJA_AUSENTE, 0)
    ]
    assert repositorio.definiciones == {}


def test_una_plataforma_con_la_clave_vacia_o_que_no_es_texto_es_un_problema() -> None:
    servicio, _ = _servicio(SOLO_UNA_Y_MAS)

    for clave in ("", "  ", 3):
        with pytest.raises(DefinicionInvalida) as error:
            servicio.crear(_cuerpo(plataforma=clave))
        assert [p.campo for p in error.value.problemas] == ["plataforma"]


def test_una_version_nueva_no_toca_la_plataforma_y_se_valida_con_sus_reglas() -> None:
    servicio, _ = _servicio(SOLO_UNA_Y_MAS)
    definicion = servicio.crear(_cuerpo(plataforma="una_y_mas")).definicion

    sin_clave = servicio.agregar_version(definicion.id, _cuerpo())
    igual = servicio.agregar_version(definicion.id, _cuerpo(plataforma="una_y_mas"))

    assert sin_clave.definicion.plataforma == igual.definicion.plataforma == "una_y_mas"
    assert igual.version.numero == 3
    with pytest.raises(DefinicionInvalida) as otra:
        servicio.agregar_version(definicion.id, _cuerpo(plataforma="sintetica"))
    assert [p.campo for p in otra.value.problemas] == ["plataforma"]
    with pytest.raises(DefinicionInvalida) as incumple:
        servicio.agregar_version(definicion.id, _dato(_columna("nota", 0)))
    assert [p.problema.codigo for p in incumple.value.problemas] == [
        CodigoTexto.PLATAFORMA_COLUMNA_FIJA_AUSENTE
    ]
    assert servicio.obtener(definicion.id).version.numero == 3


def test_renombrar_no_toca_la_plataforma() -> None:
    servicio, _ = _servicio(SOLO_UNA_Y_MAS)
    definicion = servicio.crear(_cuerpo(plataforma="una_y_mas")).definicion

    renombrada = servicio.renombrar(definicion.id, "Otro nombre")

    assert renombrada.plataforma == "una_y_mas"


def test_lo_guardado_con_una_plataforma_que_ya_no_existe_se_lee_con_un_problema() -> None:
    servicio, repositorio = _servicio(SOLO_UNA_Y_MAS)
    definicion = servicio.crear(_cuerpo(plataforma="una_y_mas")).definicion
    despues = DefinicionesColumnasService(repositorio, CARTERA, RegistroPlataformas())

    vista = despues.obtener(definicion.id)

    assert [p.problema.codigo for p in vista.problemas] == [CodigoTexto.PLATAFORMA_DESCONOCIDA]
    assert vista.definicion.plataforma == "una_y_mas"
    cargada = despues.cargar(definicion.id)
    assert [c.nombre for c in cargada.definicion.campos] == ["destino", "nota"]


def test_lo_guardado_que_incumple_las_reglas_de_hoy_se_lee_con_sus_problemas() -> None:
    servicio, repositorio = _servicio(SOLO_UNA_Y_MAS)
    definicion = servicio.crear(_cuerpo(plataforma="una_y_mas")).definicion
    estricta = ReglasPlataforma(
        "una_y_mas", "Una y mas", SOLO_UNA_Y_MAS.columnas_fijas, admite_mas_columnas=False
    )
    despues = DefinicionesColumnasService(repositorio, CARTERA, RegistroPlataformas([estricta]))

    [problema] = despues.obtener(definicion.id).problemas

    assert (problema.problema.codigo, problema.columna) == (
        CodigoTexto.PLATAFORMA_COLUMNAS_DE_MAS,
        1,
    )


# --- La API -------------------------------------------------------------------------------------


@pytest.fixture
def cliente():
    registro = RegistroPlataformas([SINTETICA, SOLO_UNA_Y_MAS])
    repositorio = RepositorioEnMemoria()
    servicio = DefinicionesColumnasService(repositorio, CARTERA, registro)
    app.dependency_overrides[obtener_servicio_definiciones] = lambda: servicio
    app.dependency_overrides[obtener_registro_plataformas] = lambda: registro
    try:
        yield TestClient(app), servicio
    finally:
        app.dependency_overrides.clear()


def test_get_plataformas_devuelve_las_reglas_declarativas(cliente) -> None:
    http, _ = cliente

    respuesta = http.get("/definiciones-columnas/plataformas")

    assert respuesta.status_code == 200
    sintetica, una_y_mas = respuesta.json()
    assert sintetica["clave"] == "sintetica" and sintetica["etiqueta"] == "Sintetica"
    assert sintetica["encabezado_por_posicion"] == "[$VAR{n}$]"
    assert sintetica["tipo_resto"] == "texto" and sintetica["admite_mas_columnas"] is True
    assert [(f["posicion"], f["nombre"], f["tipo"]) for f in sintetica["columnas_fijas"]] == [
        (1, "destino", "texto"),
        (2, "canal", "texto"),
        (3, "importe", "numero"),
    ]
    assert sintetica["columnas_fijas"][1]["contenido_editable"] is False
    assert sintetica["columnas_fijas"][2]["celda_texto"] is True
    assert una_y_mas["encabezado_por_posicion"] is None


def test_sin_plataformas_registradas_la_lista_esta_vacia() -> None:
    app.dependency_overrides[obtener_registro_plataformas] = RegistroPlataformas
    try:
        respuesta = TestClient(app).get("/definiciones-columnas/plataformas")
    finally:
        app.dependency_overrides.clear()

    assert respuesta.status_code == 200 and respuesta.json() == []


def test_post_con_plataforma_la_devuelve_en_el_detalle_y_en_el_listado(cliente) -> None:
    http, _ = cliente

    creada = http.post("/definiciones-columnas", json=_cuerpo(plataforma="una_y_mas"))

    assert creada.status_code == 201
    assert creada.json()["plataforma"] == "una_y_mas" and creada.json()["problemas"] == []
    id_ = creada.json()["id"]
    assert http.get(f"/definiciones-columnas/{id_}").json()["plataforma"] == "una_y_mas"
    assert [d["plataforma"] for d in http.get("/definiciones-columnas").json()] == ["una_y_mas"]
    nueva = http.post(f"/definiciones-columnas/{id_}/versiones", json=_cuerpo())
    assert nueva.status_code == 201 and nueva.json()["plataforma"] == "una_y_mas"
    renombrada = http.patch(f"/definiciones-columnas/{id_}", json={"nombre": "Otra"})
    assert renombrada.json()["plataforma"] == "una_y_mas"


def test_post_con_plataforma_desconocida_es_400_con_el_campo(cliente) -> None:
    http, servicio = cliente

    respuesta = http.post("/definiciones-columnas", json=_cuerpo(plataforma="inventada"))

    assert respuesta.status_code == 400
    [problema] = respuesta.json()["problemas"]
    assert (problema["codigo"], problema["campo"]) == ("plataforma_desconocida", "plataforma")
    assert servicio.listar() == []


def test_post_que_incumple_las_reglas_es_400_con_la_columna(cliente) -> None:
    http, _ = cliente

    respuesta = http.post(
        "/definiciones-columnas", json=_dato(_columna("nota", 0), plataforma="una_y_mas")
    )

    assert respuesta.status_code == 400
    [problema] = respuesta.json()["problemas"]
    assert (problema["codigo"], problema["columna"], problema["campo"]) == (
        "plataforma_columna_fija_ausente",
        0,
        "plataforma",
    )


def test_la_etiqueta_viaja_en_el_pedido_y_en_la_respuesta(cliente) -> None:
    http, _ = cliente
    dato = _dato(_columna("a", 0, etiqueta="  Telefono  "), _columna("b", 1))

    creada = http.post("/definiciones-columnas", json=dato)

    columnas = creada.json()["version"]["contenido"]["columnas"]
    assert [c["etiqueta"] for c in columnas] == ["Telefono", None]
    malo = http.post("/definiciones-columnas", json=_dato(_columna("x", 0, etiqueta=" ")))
    assert malo.status_code == 400
    assert malo.json()["problemas"][0]["campo"] == "etiqueta"


def test_el_detalle_avisa_si_la_plataforma_ya_no_esta_registrada(cliente) -> None:
    http, servicio = cliente
    id_ = http.post("/definiciones-columnas", json=_cuerpo(plataforma="una_y_mas")).json()["id"]
    app.dependency_overrides[obtener_servicio_definiciones] = lambda: DefinicionesColumnasService(
        servicio._repositorio, CARTERA, RegistroPlataformas()
    )

    detalle = http.get(f"/definiciones-columnas/{id_}").json()

    assert [p["codigo"] for p in detalle["problemas"]] == ["plataforma_desconocida"]
    assert detalle["plataforma"] == "una_y_mas"


# --- La migracion y los nombres (<= 63 caracteres) ----------------------------------------------

BACKEND = Path(__file__).resolve().parents[1]
REVISION_ANTERIOR = "b7e4c1a9d826"
REVISION = "a4d8f2b6c713"
MAXIMO_IDENTIFICADOR = 63


def _configuracion() -> Config:
    configuracion = Config(str(BACKEND / "alembic.ini"))
    configuracion.set_main_option("script_location", str(BACKEND / "migrations"))
    return configuracion


def _sql(subir: bool) -> str:
    configuracion = _configuracion()
    configuracion.output_buffer = io.StringIO()
    if subir:
        command.upgrade(configuracion, f"{REVISION_ANTERIOR}:{REVISION}", sql=True)
    else:
        command.downgrade(configuracion, f"{REVISION}:{REVISION_ANTERIOR}", sql=True)
    return configuracion.output_buffer.getvalue()


def test_la_migracion_cuelga_de_la_anterior_y_el_arbol_tiene_una_sola_cabeza() -> None:
    directorio = ScriptDirectory.from_config(_configuracion())

    assert directorio.get_revision(REVISION).down_revision == REVISION_ANTERIOR
    assert len(directorio.get_heads()) == 1


def test_el_upgrade_agrega_la_columna_nula_y_su_check() -> None:
    sql = _sql(subir=True)

    assert "ALTER TABLE definicion_carga ADD COLUMN plataforma TEXT" in sql
    assert "plataforma TEXT NOT NULL" not in sql  # NULL = archivo libre
    assert "ck_definicion_carga_plataforma_no_vacia" in sql
    assert "ck_ck_" not in sql  # `op.f`: el nombre ya trae el prefijo de la convencion
    assert "INSERT INTO definicion_carga" not in sql  # no siembra ni toca datos


def test_el_downgrade_quita_el_check_y_despues_la_columna() -> None:
    sql = _sql(subir=False)

    assert sql.index("DROP CONSTRAINT ck_definicion_carga_plataforma_no_vacia") < sql.index(
        "DROP COLUMN plataforma"
    )


def test_ningun_nombre_de_restriccion_de_la_migracion_pasa_de_63_caracteres() -> None:
    fuente = next((BACKEND / "migrations" / "versions").glob(f"{REVISION}_*.py")).read_text("utf-8")

    nombres = re.findall(r'op\.f\(\s*"([^"]+)"', fuente)

    assert nombres  # la expresion encuentra los nombres
    assert {n: len(n) for n in nombres if len(n) > MAXIMO_IDENTIFICADOR} == {}


def test_ningun_nombre_de_restriccion_ni_de_indice_de_la_metadata_pasa_de_63_caracteres() -> None:
    # TODAS las tablas, no solo esta: atrapa tambien lo que venga. Un dialecto sin tope, para ver
    # el nombre completo que arma la convencion antes de que SQLAlchemy lo acorte con un hash.
    dialecto = postgresql.dialect()
    dialecto.max_identifier_length = 1000
    ddl = []
    for tabla in Base.metadata.sorted_tables:
        ddl.append(str(CreateTable(tabla).compile(dialect=dialecto)))
        ddl += [str(CreateIndex(i).compile(dialect=dialecto)) for i in tabla.indexes]

    nombres = [a or b for a, b in re.findall(r"CONSTRAINT (\w+)|INDEX (\w+)", " ".join(ddl))]

    assert len(nombres) > 50  # la expresion encuentra los nombres
    assert "ck_definicion_carga_plataforma_no_vacia" in nombres
    assert {n: len(n) for n in nombres if len(n) > MAXIMO_IDENTIFICADOR} == {}

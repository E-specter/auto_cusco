"""`mowa_mes_exclusion.campos` contra PostgreSQL (T-MM-B12, D-CA-2). La corre `architec`.

La campana se arma y se guarda con los repositorios de verdad (speech, supervision y campanas en
PostgreSQL) y la cartera en memoria, con los adicionales sinteticos. Lo que se comprueba:

- los campos de `falta_campo_adicional` se escriben y se leen, en el orden de los nodos;
- una exclusion anterior a la migracion (columna NULL) y las de los demas codigos se leen como `()`;
- el filtro por codigo y la API de exclusiones siguen funcionando con la columna.

Datos sinteticos; la fecha de corte y el nombre del speech son los que borra la limpieza de la
fixture `cliente` de las campanas.
"""

import os
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import insert

from app.adapters.output.plataformas.mowa_mes.archivo_carga import escribir_archivo_carga
from app.adapters.persistence.modelos import MowaMesExclusion
from app.adapters.persistence.repositorio_campanas_mowa_mes_postgres import (
    RepositorioCampanasMowaMesPostgres,
)
from app.adapters.persistence.repositorio_mowa_mes_postgres import RepositorioMowaMesPostgres
from app.adapters.persistence.repositorio_supervision_postgres import (
    RepositorioSupervisionPostgres,
)
from app.core.entities.mowa_mes import CodigoMowaMes, DatosSpeech
from app.core.entities.mowa_mes_campana import Exclusion
from app.core.services.plataformas.mowa_mes.campana import CampanasMowaMesService, huella_de
from app.core.services.seleccion_cartera.campos import CatalogoCartera
from app.core.services.seleccion_cartera.servicio import ConsultaCarteraService
from tests import test_mowa_mes_campanas_postgres as base
from tests.campos_adicionales_memoria import CamposAdicionalesEnMemoria
from tests.test_mowa_mes_adicionales import COMPLETO, MONTO, VISITA, ZONA
from tests.test_mowa_mes_campana import RepositorioCarteraFalso, peticion, producto

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        os.environ.get("AUTO_CUSCO_DB_TESTS") != "1",
        reason="Requiere AUTO_CUSCO_DB_TESTS=1 y PostgreSQL migrado",
    ),
]

# La fixture `cliente` (sabana, supervisores, configuracion y limpieza) es la de las campanas.
cliente = base.cliente

_EXCLUSION = MowaMesExclusion.__table__


def _campana_con_exclusiones(engine):
    """Crea una campana por el caso de uso real: un producto cargado y uno con campos vacios."""
    speech = RepositorioMowaMesPostgres(engine).crear_speech(
        DatosSpeech(
            f"{base.PREFIJO}adicionales", expresiones=COMPLETO.expresiones, formato=COMPLETO.formato
        ),
        None,
    )
    servicio = CampanasMowaMesService(
        ConsultaCarteraService(
            RepositorioCarteraFalso(
                [
                    producto(1, **{ZONA: "ZONA UNO", MONTO: Decimal("5"), VISITA: base.FECHA}),
                    producto(2, **{ZONA: None, MONTO: "", VISITA: base.FECHA}),
                    producto(3, telefono=None),
                ]
            ),
            CatalogoCartera(CamposAdicionalesEnMemoria()),
        ),
        RepositorioMowaMesPostgres(engine),
        RepositorioSupervisionPostgres(engine),
        RepositorioCampanasMowaMesPostgres(engine),
        escribir_archivo_carga,
    )
    return servicio.crear(
        peticion(
            fecha_corte=base.FECHA,
            envios=(datetime(2099, 6, 2, 9, 0),),
            speech_id=speech.id,
            speech_huella=huella_de(speech.datos),
        )
    )


def test_los_campos_van_y_vuelven_en_el_orden_de_los_nodos_y_las_demas_salen_vacias(
    cliente,
) -> None:
    _, engine = cliente
    campana = _campana_con_exclusiones(engine)

    total, exclusiones = RepositorioCampanasMowaMesPostgres(engine).exclusiones(
        campana.id, None, 50, 0
    )

    assert total == 2
    assert exclusiones == [
        Exclusion(producto(2)["pagare"], CodigoMowaMes.FALTA_CAMPO_ADICIONAL, campos=(ZONA, MONTO)),
        Exclusion(producto(3)["pagare"], CodigoMowaMes.TELEFONO_INVALIDO, campos=()),
    ]


def test_una_exclusion_anterior_a_la_migracion_se_lee_como_sin_campos(cliente) -> None:
    _, engine = cliente
    campana = _campana_con_exclusiones(engine)
    with engine.begin() as cx:
        # Como las filas de antes de la migracion: sin tocar la columna `campos` (queda NULL).
        cx.execute(
            insert(_EXCLUSION).values(
                campana_id=campana.id, pagare="anterior", orden=99, codigo="falta_titular"
            )
        )

    _, exclusiones = RepositorioCampanasMowaMesPostgres(engine).exclusiones(
        campana.id, CodigoMowaMes.FALTA_TITULAR, 50, 0
    )

    assert exclusiones == [Exclusion("anterior", CodigoMowaMes.FALTA_TITULAR, campos=())]


def test_la_api_devuelve_el_nombre_tecnico_de_cada_campo_y_filtra_por_codigo(cliente) -> None:
    client, engine = cliente
    campana = _campana_con_exclusiones(engine)

    pagina = client.get(
        f"/mowa-mes/campanas/{campana.id}/exclusiones", params={"codigo": "falta_campo_adicional"}
    ).json()

    assert pagina["total"] == 1
    exclusion = pagina["exclusiones"][0]
    assert exclusion["codigo"] == "falta_campo_adicional"
    # La etiqueta sale del catalogo de la base (no tiene estos campos): cae al nombre tecnico.
    assert [c["nombre"] for c in exclusion["campos"]] == [ZONA, MONTO]

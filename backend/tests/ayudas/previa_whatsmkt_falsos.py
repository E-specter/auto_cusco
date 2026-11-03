"""Dobles en memoria para la previsualizacion de campanas de WhatsMKT (T-WM-B4a).

El servicio real de previsualizacion se arma sobre ellos: una definicion guardada, los segmentos de
B1 y la configuracion de supervision. La cartera es la de `test_whatsmkt_contactos`.
"""

from types import SimpleNamespace

from app.core.entities.definiciones_columnas import DefinicionNoEncontrada, VersionNoEncontrada
from app.core.entities.gestiones_digitales import ConfiguracionSupervision, Supervisor
from app.core.entities.mapeo import DefinicionCarga
from app.core.entities.whatsmkt import SEGMENTOS_POR_DEFECTO
from app.core.services.generacion_cargas.servicio import GeneracionCargasService
from app.core.services.plataformas.whatsmkt.archivo_contactos import ArchivoContactosService
from app.core.services.plataformas.whatsmkt.previa import PrevisualizacionWhatsmktService
from app.core.services.seleccion_cartera.servicio import ConsultaCarteraService
from tests.test_whatsmkt_contactos import PROCEDENCIAS, SUPERVISORES, RepositorioCartera

DEFINICION_ID = 5


class DefinicionesGuardadasFalsas:
    """Una sola definicion guardada (id 5, version 1) con la plataforma que se le diga."""

    def __init__(self, definicion: DefinicionCarga, plataforma: str | None = "whatsmkt") -> None:
        self.definicion = definicion
        self.plataforma = plataforma

    def _revisar(self, definicion_id: int, numero: int | None) -> None:
        if definicion_id != DEFINICION_ID:
            raise DefinicionNoEncontrada(definicion_id)
        if numero not in (None, 1):
            raise VersionNoEncontrada(definicion_id, numero)

    def obtener(self, definicion_id: int, numero: int | None = None):
        self._revisar(definicion_id, numero)
        return SimpleNamespace(
            definicion=SimpleNamespace(nombre=self.definicion.nombre, plataforma=self.plataforma),
            version=SimpleNamespace(numero=1),
            problemas=(),
        )

    def cargar(self, definicion_id: int, numero: int | None = None):
        self._revisar(definicion_id, numero)
        return SimpleNamespace(
            id=DEFINICION_ID, numero=1, nombre=self.definicion.nombre, definicion=self.definicion
        )


class SegmentosFalsos:
    def listar_segmentos(self):
        return list(SEGMENTOS_POR_DEFECTO)


class SupervisionFalsa:
    def __init__(self, supervisores: tuple[Supervisor, ...] = SUPERVISORES) -> None:
        self.configuracion = ConfiguracionSupervision(PROCEDENCIAS, supervisores)

    def obtener(self) -> ConfiguracionSupervision:
        return self.configuracion


def servicio_de_previa(
    productos: list[dict],
    definicion: DefinicionCarga,
    *,
    plataforma: str | None = "whatsmkt",
    supervisores: tuple[Supervisor, ...] = SUPERVISORES,
) -> PrevisualizacionWhatsmktService:
    generacion = GeneracionCargasService(ConsultaCarteraService(RepositorioCartera(productos)))
    return PrevisualizacionWhatsmktService(
        ArchivoContactosService(generacion),
        SegmentosFalsos(),
        DefinicionesGuardadasFalsas(definicion, plataforma),
        SupervisionFalsa(supervisores),
    )

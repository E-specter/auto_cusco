"""Dobles en memoria para la previsualizacion de campanas de WhatsMKT (T-WM-B4a y B4b1).

El servicio real de previsualizacion se arma sobre ellos: una definicion guardada, los segmentos y
la configuracion de B1, la configuracion de supervision y los textos guardados. La cartera es la de
`test_whatsmkt_contactos`.
"""

from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace

from app.core.entities.definiciones_columnas import DefinicionNoEncontrada, VersionNoEncontrada
from app.core.entities.gestiones_digitales import ConfiguracionSupervision, Supervisor
from app.core.entities.mapeo import DefinicionCarga
from app.core.entities.whatsmkt import SEGMENTOS_POR_DEFECTO, ConfiguracionWhatsmkt
from app.core.services.generacion_cargas.servicio import GeneracionCargasService
from app.core.services.plataformas.whatsmkt.archivo_contactos import ArchivoContactosService
from app.core.services.plataformas.whatsmkt.previa import PrevisualizacionWhatsmktService
from app.core.services.plataformas.whatsmkt.programacion import ProgramacionWhatsmktService
from app.core.services.seleccion_cartera.servicio import ConsultaCarteraService
from tests.ayudas.calendario_falso import programacion_de_prueba
from tests.test_whatsmkt_contactos import PROCEDENCIAS, SUPERVISORES, RepositorioCartera

DEFINICION_ID = 5
MOMENTO = datetime(2026, 11, 2, 12, 0)
CONTEXTO_MENSAJE = "whatsmkt.mensaje"


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


class RepositorioWhatsmktFalso:
    """Los segmentos y la configuracion de WhatsMKT (lo unico que la previsualizacion lee)."""

    def __init__(self, segmentos=None, configuracion: ConfiguracionWhatsmkt | None = None) -> None:
        self.segmentos = list(segmentos if segmentos is not None else SEGMENTOS_POR_DEFECTO)
        self.configuracion = configuracion or ConfiguracionWhatsmkt(actualizado_en=MOMENTO)

    def listar_segmentos(self):
        return list(self.segmentos)

    def obtener_configuracion(self):
        return self.configuracion

    def con_texto_en(self, clave: str, texto_id: int | None) -> None:
        """El mensaje de un segmento, como lo deja la configuracion (RF-WM-22)."""
        self.segmentos = [
            replace(s, texto_guardado_id=texto_id) if s.clave == clave else s
            for s in self.segmentos
        ]


class SupervisionFalsa:
    def __init__(self, supervisores: tuple[Supervisor, ...] = SUPERVISORES) -> None:
        self.configuracion = ConfiguracionSupervision(PROCEDENCIAS, supervisores)

    def obtener(self) -> ConfiguracionSupervision:
        return self.configuracion


class TextosFalsos:
    """Los textos guardados. `agregar` crea uno con las versiones que se le den (1, 2, ...)."""

    def __init__(self) -> None:
        self.textos: dict[int, SimpleNamespace] = {}

    def agregar(
        self,
        texto_id: int,
        *versiones: str,
        nombre: str | None = None,
        contexto: str = CONTEXTO_MENSAJE,
        deshabilitado: bool = False,
    ) -> int:
        self.textos[texto_id] = SimpleNamespace(
            id=texto_id,
            contexto=contexto,
            nombre=nombre or f"Mensaje {texto_id}",
            deshabilitado=deshabilitado,
            versiones=tuple(
                SimpleNamespace(numero=i, contenido={"texto": t}, usada_en=None, creado_en=MOMENTO)
                for i, t in enumerate(versiones, 1)
            ),
        )
        return texto_id

    def obtener(self, texto_id: int):
        return self.textos.get(texto_id)


def servicio_de_previa(
    productos: list[dict],
    definicion: DefinicionCarga,
    *,
    plataforma: str | None = "whatsmkt",
    supervisores: tuple[Supervisor, ...] = SUPERVISORES,
    textos: TextosFalsos | None = None,
    whatsmkt: RepositorioWhatsmktFalso | None = None,
    programacion: ProgramacionWhatsmktService | None = None,
) -> PrevisualizacionWhatsmktService:
    generacion = GeneracionCargasService(ConsultaCarteraService(RepositorioCartera(productos)))
    return PrevisualizacionWhatsmktService(
        ArchivoContactosService(generacion),
        whatsmkt or RepositorioWhatsmktFalso(),
        DefinicionesGuardadasFalsas(definicion, plataforma),
        SupervisionFalsa(supervisores),
        textos or TextosFalsos(),
        programacion or programacion_de_prueba(),
    )

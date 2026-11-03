"""Puerto de persistencia de las campanas de WhatsMKT (T-WM-B4b1)."""

from datetime import date
from typing import Protocol

from app.core.entities.whatsmkt import ModoCampana
from app.core.entities.whatsmkt_campana import (
    ArchivoGuardado,
    CampanaWhatsmkt,
    EstadoCampana,
    LoteCreado,
    LoteNuevo,
    PaginaCampanas,
    PaginaExclusiones,
)
from app.core.entities.whatsmkt_informe import (
    FilaCargadaWhatsmkt,
    ReporteGuardado,
    ReporteNuevo,
)


class RepositorioCampanasWhatsmktPort(Protocol):
    def crear_lote(self, lote: LoteNuevo) -> LoteCreado:
        """Guarda el lote COMPLETO en una sola transaccion: el lote, cada campana con su archivo,
        sus filas y sus exclusiones, y las exclusiones sin campana. Marca como usadas la version
        del texto y la de la definicion. Si algo falla no queda nada."""
        ...

    def obtener_archivo(self, campana_id: int) -> ArchivoGuardado | None:
        """Los bytes guardados al crear la campana, o None si no existe."""
        ...

    def listar(
        self,
        limite: int,
        desplazamiento: int,
        lote_id: int | None = None,
        mes: date | None = None,
        estado: EstadoCampana = EstadoCampana.ACTIVAS,
    ) -> PaginaCampanas:
        """Las campanas del `estado` (activas por defecto), las mas recientes primero (desempate
        por id). `mes` es el primer dia del mes de la fecha de envio; `mes` y `lote_id` son
        opcionales. `total` cuenta las que cumplen los filtros, no solo las de la pagina; los
        otros tres totales son de todas las campanas."""
        ...

    def obtener(self, campana_id: int) -> CampanaWhatsmkt | None: ...

    def modo_del_lote(self, lote_id: int) -> ModoCampana: ...

    def listar_exclusiones(
        self, lote_id: int, campana_id: int | None, limite: int, desplazamiento: int
    ) -> PaginaExclusiones:
        """Las exclusiones de una campana o, con `campana_id=None`, las del lote que quedaron
        fuera de todas sus campanas. En el orden de la seleccion."""
        ...

    def descartar(self, campana_id: int) -> CampanaWhatsmkt | None:
        """Pone `descartada_en` (RF-WM-41). Descartar una ya descartada no cambia su fecha. None si
        no existe."""
        ...

    def restaurar(self, campana_id: int) -> CampanaWhatsmkt | None:
        """Limpia `descartada_en` (RF-WM-42). None si no existe."""
        ...

    def eliminar_descartada(self, campana_id: int) -> bool:
        """Borra una campana DESCARTADA con su archivo, filas, exclusiones e informes, en una
        transaccion; si era la ultima de su lote, borra tambien el lote y sus exclusiones fuera
        del lote. No toca adjuntos ni versiones de mensaje. False (sin borrar nada) si no existe
        o no esta descartada."""
        ...

    def obtener_reporte(self, campana_id: int) -> ReporteGuardado | None:
        """El informe vigente de la campana, con sus numeros en el orden del informe."""
        ...

    def reemplazar_reporte(self, campana_id: int, reporte: ReporteNuevo) -> ReporteGuardado:
        """Guarda el informe como el vigente de la campana: borra el anterior, si lo hay, y inserta
        el nuevo en una sola transaccion."""
        ...

    def filas_cargadas(self, campana_id: int) -> tuple[FilaCargadaWhatsmkt, ...]:
        """Las filas del archivo (supervisores y productos) en su orden, para conciliar."""
        ...

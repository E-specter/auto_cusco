"""Puerto de lectura de un reporte de enviados descargado de una plataforma."""

from typing import Protocol

from app.core.entities.mowa_mes_reporte import FilaReporte


class LectorReportePort(Protocol):
    def leer(self, contenido: bytes) -> tuple[FilaReporte, ...]:
        """Lanza ReporteInvalido con el motivo si el archivo no sirve."""
        ...

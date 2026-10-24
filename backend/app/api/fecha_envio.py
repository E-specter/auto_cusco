"""El rechazo de una fecha de envio anterior a la de corte, comun a las dos entradas que la reciben
(`/archivos-carga` y `/texto-enriquecido/previsualizacion`, RF-55).

El cuerpo es el de todo error con codigo (`detail`, `codigo`) y, con este codigo, las dos fechas
como campos propios (`fecha_envio` y `fecha_corte`, ISO), para que la interfaz las muestre sin leer
la prosa de `detail`.
"""

from datetime import date

from pydantic import ConfigDict

from app.api.errores import DetalleErrorConCodigo, ErrorConCodigo
from app.core.entities.texto_enriquecido import CodigoTexto
from app.core.services.fecha_envio import FechaEnvioAnterior


class DetalleErrorFechaEnvio(DetalleErrorConCodigo):
    """Un `400`: `fecha_envio` y `fecha_corte` solo viajan cuando el `codigo` es
    `fecha_envio_anterior`; en cualquier otro `400` de estas entradas no vienen."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=False)

    fecha_envio: date | None = None
    fecha_corte: date | None = None


def error_de_fecha_envio(error: FechaEnvioAnterior) -> ErrorConCodigo:
    return ErrorConCodigo(
        400,
        str(error),
        CodigoTexto.FECHA_ENVIO_ANTERIOR,
        {
            "fecha_envio": error.fecha_envio.isoformat(),
            "fecha_corte": error.fecha_corte.isoformat(),
        },
    )

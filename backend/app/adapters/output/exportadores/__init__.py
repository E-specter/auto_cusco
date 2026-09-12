"""Exportadores de una tabla a archivo (RF-13, RF-14).

Un adaptador por formato, todos con la misma firma
(`exportar(tabla, opciones) -> ArchivoGenerado`), registrados aqui. Agregar un
formato nuevo es agregar su modulo y una entrada en `EXPORTADORES`: ni el
nucleo ni los demas formatos cambian.

    from app.adapters.output import exportadores
    archivo = exportadores.exportar(tabla, FormatoArchivo.CSV)
"""

from app.adapters.output.exportadores import (
    comunes,
    exportador_csv,
    exportador_json,
    exportador_xlsx,
)
from app.core.entities.exportacion import (
    OPCIONES_POR_DEFECTO,
    ArchivoGenerado,
    FormatoArchivo,
    FormatoNoSoportado,
    OpcionesArchivo,
    Tabla,
)
from app.core.ports.exportador_tabla_port import ExportadorTablaPort

EXPORTADORES: dict[FormatoArchivo, ExportadorTablaPort] = {
    FormatoArchivo.XLSX: exportador_xlsx.exportar,
    FormatoArchivo.CSV: exportador_csv.exportar,
    FormatoArchivo.JSON: exportador_json.exportar,
}


def nombre_de_archivo(nombre: str, formato: FormatoArchivo) -> str:
    """Nombre que tendra el archivo de una tabla, sin llegar a generarlo."""
    return comunes.nombre_de_archivo(nombre, formato)


def formatos_soportados() -> tuple[str, ...]:
    return tuple(formato.value for formato in EXPORTADORES)


def obtener(formato: FormatoArchivo | str) -> ExportadorTablaPort:
    """Exportador de un formato, aceptando tambien su nombre como texto."""
    try:
        clave = FormatoArchivo(formato)
    except ValueError as exc:
        raise FormatoNoSoportado(formato, formatos_soportados()) from exc
    exportador = EXPORTADORES.get(clave)
    if exportador is None:  # formato declarado pero todavia sin adaptador
        raise FormatoNoSoportado(formato, formatos_soportados())
    return exportador


def exportar(
    tabla: Tabla,
    formato: FormatoArchivo | str,
    opciones: OpcionesArchivo = OPCIONES_POR_DEFECTO,
) -> ArchivoGenerado:
    return obtener(formato)(tabla, opciones)

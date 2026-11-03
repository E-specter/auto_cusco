"""La tabla del informe de WhatsMKT (RF-WM-37), leida con el lector general (RF-57).

El archivo lo lee `LectorTablaPort` en cualquiera de los formatos de la sabana: el formato se
reconoce por la extension y el contenido, como el reporte de MOWA (RF-MM-20). Aqui solo se elige
la hoja (`Informe` si existe, y si no la primera) y se traducen los archivos que no se pueden leer
al rechazo del informe, con el motivo. Lo que sigue (los rotulos, las filas) es del nucleo:
`leer_informe`.
"""

from app.adapters.input.lector_tabla import LectorTabla
from app.core.entities.lectura_tabla import OpcionesLectura, TablaLeida
from app.core.entities.sabana import ArchivoIlegible, HojaNoEncontrada, HojaVacia
from app.core.entities.whatsmkt import CodigoWhatsmkt, ErrorWhatsmkt
from app.core.ports.lector_tabla_port import LectorTablaPort
from app.core.services.lectura_tabla import detectar_formato
from app.core.services.plataformas.whatsmkt.informe import sin_marcas

NOMBRE_DE_LA_HOJA = "Informe"


def _rechazo(motivo: str) -> ErrorWhatsmkt:
    return ErrorWhatsmkt(
        CodigoWhatsmkt.INFORME_SIN_ENCABEZADOS, f"{motivo}: ¿es el informe de WhatsMKT?"
    )


def leer_tabla_del_informe(
    contenido: bytes, nombre_archivo: str, lector: LectorTablaPort | None = None
) -> TablaLeida:
    """La hoja `Informe` del archivo (o la primera). Lanza `ErrorWhatsmkt` con
    `informe_sin_encabezados` si el archivo no se puede leer o la hoja elegida esta vacia.

    La hoja se PIDE por su nombre en vez de leer la primera para ver cuales hay: una portada vacia
    antes de `Informe` no puede hacer fallar la lectura. Si no existe con ese nombre exacto, el
    lector dice cuales hay y se elige la que se llame igual sin tildes ni mayusculas o, si no, la
    primera.
    """
    lector = lector or LectorTabla()
    try:
        if not detectar_formato(contenido, nombre_archivo).es_hoja_de_calculo:
            return lector.leer(contenido, nombre_archivo)  # un CSV o un JSON no tiene hojas
        try:
            return lector.leer(contenido, nombre_archivo, OpcionesLectura(hoja=NOMBRE_DE_LA_HOJA))
        except HojaNoEncontrada as ausente:
            elegida = next(
                (h for h in ausente.disponibles if sin_marcas(h) == sin_marcas(NOMBRE_DE_LA_HOJA)),
                ausente.disponibles[0] if ausente.disponibles else None,
            )
            if elegida is None:
                raise
            return lector.leer(contenido, nombre_archivo, OpcionesLectura(hoja=elegida))
    except HojaVacia as exc:
        raise _rechazo("La hoja del informe no tiene cabecera ni filas") from exc
    except ArchivoIlegible as exc:
        raise _rechazo(str(exc).rstrip(".")) from exc

"""Informes de WhatsMKT sinteticos, como .xlsx, para las pruebas del seguimiento (T-WM-B6).

La estructura observada: FECHA y TOTAL DE ENVIO arriba, una fila vacia, los encabezados CAMPAÑA,
TIPO DE ENVIO y NUMERO, otra fila vacia y una fila por numero enviado. Numeros 51900000xxx.
"""

from io import BytesIO

from openpyxl import Workbook

CAMPANA_INFORMADA = "CUZCO_Vencida (sintetica) whatsapp 2026.11.03"
TIPO_INFORMADO = "CAMPAÑA DE IMAGEN + TEXTO"
MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def informe_xlsx(
    numeros,
    *,
    hoja: str = "Informe",
    hojas_antes: tuple[str, ...] = (),
    total="auto",
    fecha: str | None = "30-10-2026",
    encabezados: tuple[str, ...] = ("CAMPAÑA", "TIPO DE ENVIO", "NUMERO"),
) -> bytes:
    """El archivo. `total="auto"` informa tantos como numeros; `None` omite la fila del total."""
    libro = Workbook()
    for nombre in hojas_antes:  # otras hojas, antes de la del informe
        libro.create_sheet(nombre)
    informe = libro.create_sheet(hoja)
    libro.remove(libro.active)  # la hoja que openpyxl crea sola
    if fecha is not None:
        informe.append(["FECHA", fecha])
    if total is not None:
        informe.append(["TOTAL DE ENVIO", len(numeros) if total == "auto" else total])
    informe.append([])
    informe.append(list(encabezados))
    informe.append([])
    for numero in numeros:
        informe.append([CAMPANA_INFORMADA, TIPO_INFORMADO, int(numero)])
    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()

"""Lector del «Informe» de WhatsMKT (RF-WM-37), sobre la tabla ya leida por el lector comun.

Es nucleo puro: recibe la `TablaLeida` (la hoja con sus filas de celdas) y no abre archivos ni
conoce adaptadores. El informe observado:

    FECHA            | 30-10-2026
    TOTAL DE ENVIO   | 101
    (fila vacia)
    CAMPAÑA | TIPO DE ENVIO | NUMERO
    (fila vacia)
    <nombre> | CAMPAÑA DE IMAGEN + TEXTO | 51900000001
    ...

Las filas se buscan por su CONTENIDO, no por su numero: lo que cambia de un informe a otro (filas
vacias de mas o de menos) no lo rompe. Los rotulos se comparan sin tildes y sin distinguir
mayusculas (`CAMPAÑA` puede venir como `CAMPANA`). Las filas vacias se ignoran.

Lo unico que rechaza el informe es que falte un encabezado (`informe_sin_encabezados`) o que no
tenga ningun numero (`informe_sin_filas`). Un total que no coincide con las filas se informa, no
se rechaza (DU-WM-7).
"""

import math
import re
import unicodedata
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.entities.lectura_tabla import TablaLeida
from app.core.entities.valores import vacia
from app.core.entities.whatsmkt import CodigoWhatsmkt, ErrorWhatsmkt
from app.core.entities.whatsmkt_informe import InformeWhatsmkt

_FECHA, _TOTAL = "fecha", "total de envio"
_CAMPANA, _TIPO, _NUMERO = "campana", "tipo de envio", "numero"
_ENCABEZADOS = (_CAMPANA, _TIPO, _NUMERO)
_FORMATOS_DE_FECHA = ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d")
_ENTERO = re.compile(r"\d+(\.0+)?")
_CIENTIFICO = re.compile(r"\d+(\.\d+)?[eE]\+?\d+")


def sin_marcas(texto: str) -> str:
    """Sin tildes ni otras marcas, en minusculas y con los espacios compactados."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    limpio = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return " ".join(limpio.casefold().split())


def solo_digitos(valor: Any) -> str | None:
    """El numero de una celda como texto de digitos: `51900000001.0` es `51900000001`.

    Acepta un entero, un decimal sin parte fraccionaria, un texto con o sin `.0` o en notacion
    cientifica, y un texto con signos o espacios (`+51 900 000 001`). None si no hay digitos.
    """
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return str(valor)
    if isinstance(valor, (float, Decimal)):
        return str(int(valor)) if math.isfinite(valor) and valor == int(valor) else None
    texto = str(valor).strip()
    if _ENTERO.fullmatch(texto):
        return texto.split(".")[0]
    if _CIENTIFICO.fullmatch(texto):
        try:
            entero = Decimal(texto)
        except InvalidOperation:
            return None
        return str(int(entero)) if entero == int(entero) else None
    return "".join(re.findall(r"\d", texto)) or None


def _filas(tabla: TablaLeida) -> list[list[Any]]:
    """Todas las filas de la hoja: la que el lector tomo por cabecera y las demas."""
    return [list(tabla.cabeceras), *(list(f.celdas) for f in tabla.filas)]


def _posicion(fila: Sequence[Any], rotulo: str) -> int | None:
    return next(
        (
            i
            for i, celda in enumerate(fila)
            if not vacia(celda) and sin_marcas(str(celda)).rstrip(": ") == rotulo
        ),
        None,
    )


def _siguiente(fila: Sequence[Any], despues_de: int) -> Any:
    """La primera celda con valor despues del rotulo."""
    return next((c for c in fila[despues_de + 1 :] if not vacia(c)), None)


def _fecha(valor: Any) -> date | None:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if vacia(valor):
        return None
    for formato in _FORMATOS_DE_FECHA:
        try:
            return datetime.strptime(str(valor).strip(), formato).date()
        except ValueError:
            continue
    return None


def _total(valor: Any) -> int | None:
    if vacia(valor):
        return None
    if isinstance(valor, (int, float, Decimal)) and not isinstance(valor, bool):
        return int(valor) if math.isfinite(valor) and valor == int(valor) else None
    texto = str(valor).strip().replace(",", "").replace(" ", "")  # "1 205" o "1,205"
    return int(texto.split(".")[0]) if _ENTERO.fullmatch(texto) else None


def _texto(valor: Any) -> str | None:
    return None if vacia(valor) else str(valor).strip()


def _fila_de_encabezados(filas: Iterable[Sequence[Any]]) -> tuple[int, dict[str, int]]:
    """El indice de la fila de encabezados y la columna de cada uno. Lanza
    `informe_sin_encabezados` si no esta la fila o le falta alguno de los tres."""
    for indice, fila in enumerate(filas):
        columnas = {r: _posicion(fila, r) for r in _ENCABEZADOS}
        if any(posicion is not None for posicion in columnas.values()):
            faltan = [r.upper() for r, posicion in columnas.items() if posicion is None]
            if faltan:
                raise _sin_encabezados(f"Falta el encabezado {', '.join(faltan)}")
            return indice, {r: p for r, p in columnas.items() if p is not None}
    raise _sin_encabezados("No hay una fila con los encabezados CAMPAÑA, TIPO DE ENVIO y NUMERO")


def _sin_encabezados(motivo: str) -> ErrorWhatsmkt:
    return ErrorWhatsmkt(
        CodigoWhatsmkt.INFORME_SIN_ENCABEZADOS,
        f"{motivo}: ¿es el informe de WhatsMKT?",
    )


def leer_informe(tabla: TablaLeida) -> InformeWhatsmkt:
    """El informe de una tabla ya leida. Lanza `ErrorWhatsmkt` con `informe_sin_encabezados` o
    `informe_sin_filas`."""
    filas = _filas(tabla)
    donde, columnas = _fila_de_encabezados(filas)

    fecha = total = None
    for fila in filas[:donde]:  # los rotulos de arriba, donde esten
        if (p := _posicion(fila, _FECHA)) is not None and fecha is None:
            fecha = _fecha(_siguiente(fila, p))
        if (p := _posicion(fila, _TOTAL)) is not None and total is None:
            total = _total(_siguiente(fila, p))

    numeros: list[str] = []
    campana = tipo_envio = None
    for fila in filas[donde + 1 :]:
        celda = fila[columnas[_NUMERO]] if columnas[_NUMERO] < len(fila) else None
        numero = solo_digitos(celda)
        if numero is None:
            continue  # fila vacia, o sin un numero que leer
        numeros.append(numero)
        if campana is None and columnas[_CAMPANA] < len(fila):
            campana = _texto(fila[columnas[_CAMPANA]])
        if tipo_envio is None and columnas[_TIPO] < len(fila):
            tipo_envio = _texto(fila[columnas[_TIPO]])
    if not numeros:
        raise ErrorWhatsmkt(CodigoWhatsmkt.INFORME_SIN_FILAS, "El informe no trae numeros enviados")
    return InformeWhatsmkt(
        fecha_informada=fecha,
        total_informado=total,
        campana=campana,
        tipo_envio=tipo_envio,
        numeros=tuple(numeros),
    )

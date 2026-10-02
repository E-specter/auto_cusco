"""Funciones de fecha (seccion 6): sumar y restar dias, formato y lectura con marcas legibles.

El patron usa marcas legibles (`dd`, `mm`, `aaaa`, `aa`, `nombre_mes`) y no
`strftime`: el usuario no escribe `%`, y el nombre del mes no depende del idioma
del sistema. Un patron se convierte una vez, al compilar, en una tupla de
trozos; por fila solo se recorre esa tupla.
"""

from datetime import date, timedelta

from app.core.entities.texto_enriquecido import CodigoTexto, TipoValor

from .base import Funcion, Parametro, ValorInvalido

F, N, T = TipoValor.FECHA, TipoValor.NUMERO, TipoValor.TEXTO

MESES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)
_LARGO_FECHA_ISO = 10
_LARGO_MAXIMO_MES = max(len(m) for m in MESES)

_LITERAL, _DIA, _MES, _ANIO, _ANIO_CORTO, _NOMBRE_MES = range(6)
_MARCAS = (
    ("nombre_mes", _NOMBRE_MES),
    ("aaaa", _ANIO),
    ("aa", _ANIO_CORTO),
    ("dd", _DIA),
    ("mm", _MES),
)
_LARGO_DE_MARCA = {_DIA: 2, _MES: 2, _ANIO: 4, _ANIO_CORTO: 2, _NOMBRE_MES: _LARGO_MAXIMO_MES}

Patron = tuple[tuple[int, str], ...]

# Las marcas que el usuario ve (en el orden en que la interfaz las ofrece) y los patrones que se
# usan seguido. La interfaz tambien admite un patron propio armado con las marcas.
MARCAS_LEGIBLES = ("dd", "mm", "aaaa", "aa", "nombre_mes")
PATRONES_FRECUENTES = (
    "dd/mm/aaaa",
    "aaaa-mm-dd",
    "dd-mm-aaaa",
    "dd/mm/aa",
    "dd de nombre_mes de aaaa",
    "dd/mm",
    "mm/aaaa",
)


def _convertir_patron(patron: str) -> Patron:
    trozos: list[tuple[int, str]] = []
    literal: list[str] = []
    i = 0
    while i < len(patron):
        for marca, tipo in _MARCAS:
            if patron.startswith(marca, i):
                if literal:
                    trozos.append((_LITERAL, "".join(literal)))
                    literal = []
                trozos.append((tipo, marca))
                i += len(marca)
                break
        else:
            literal.append(patron[i])
            i += 1
    if literal:
        trozos.append((_LITERAL, "".join(literal)))
    if all(tipo == _LITERAL for tipo, _ in trozos):
        raise ValueError("debe tener al menos una marca: dd, mm, aaaa, aa o nombre_mes")
    return tuple(trozos)


def validar_marcas(patron: str) -> None:
    """Lanza `ValueError` si el patron no tiene ninguna marca (dd, mm, aaaa, aa, nombre_mes)."""
    _convertir_patron(patron)


def formatear_con_marcas(valor: date, patron: str) -> str:
    """La fecha escrita con un patron de marcas: lo mismo que `formato_fecha` del motor."""
    return _formato_fecha(valor, _convertir_patron(patron))


def _convertir_patron_de_lectura(patron: str) -> Patron:
    trozos = _convertir_patron(patron)
    tipos = {tipo for tipo, _ in trozos}
    if _DIA not in tipos or not tipos & {_MES, _NOMBRE_MES} or not tipos & {_ANIO, _ANIO_CORTO}:
        raise ValueError("para leer una fecha necesita dd, mm (o nombre_mes) y aaaa (o aa)")
    return trozos


def _formato_fecha(valor: date, patron: Patron) -> str:
    partes: list[str] = []
    for tipo, texto in patron:
        if tipo == _LITERAL:
            partes.append(texto)
        elif tipo == _DIA:
            partes.append(f"{valor.day:02d}")
        elif tipo == _MES:
            partes.append(f"{valor.month:02d}")
        elif tipo == _ANIO:
            partes.append(f"{valor.year:04d}")
        elif tipo == _ANIO_CORTO:
            partes.append(f"{valor.year % 100:02d}")
        else:
            partes.append(MESES[valor.month - 1])
    return "".join(partes)


def _cota_formato(_entrada: int | None, args: tuple) -> int | None:
    return sum(len(texto) if tipo == _LITERAL else _LARGO_DE_MARCA[tipo] for tipo, texto in args[0])


def _digitos(texto: str, posicion: int, cantidad: int) -> int | None:
    trozo = texto[posicion : posicion + cantidad]
    if len(trozo) == cantidad and trozo.isascii() and trozo.isdigit():
        return int(trozo)
    return None


def _a_fecha(valor: str, patron: Patron) -> date:
    texto = valor.strip()
    posicion = 0
    dia = mes = anio = None
    for tipo, marca in patron:
        if tipo == _LITERAL:
            if not texto.startswith(marca, posicion):
                return _no_es_fecha(valor)
            posicion += len(marca)
        elif tipo == _NOMBRE_MES:
            minuscula = texto.lower()
            for numero, nombre in enumerate(MESES, start=1):
                if minuscula.startswith(nombre, posicion):
                    mes = numero
                    posicion += len(nombre)
                    break
            else:
                return _no_es_fecha(valor)
        else:
            cantidad = _LARGO_DE_MARCA[tipo]
            leido = _digitos(texto, posicion, cantidad)
            if leido is None:
                return _no_es_fecha(valor)
            posicion += cantidad
            if tipo == _DIA:
                dia = leido
            elif tipo == _MES:
                mes = leido
            elif tipo == _ANIO:
                anio = leido
            else:
                anio = 2000 + leido
    if posicion != len(texto):
        return _no_es_fecha(valor)
    try:
        return date(anio, mes, dia)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return _no_es_fecha(valor)


def _no_es_fecha(valor: str) -> date:
    raise ValorInvalido(CodigoTexto.NO_ES_FECHA, f"{valor!r} no es una fecha con ese patron")


def _sumar_dias(valor: date, dias: int) -> date:
    return valor + timedelta(days=dias)


def _restar_dias(valor: date, dias: int) -> date:
    return valor - timedelta(days=dias)


def _cota_fecha(_entrada: int | None, _args: tuple) -> int | None:
    return _LARGO_FECHA_ISO


_DIAS = Parametro("dias", N, acepta_variable=True, entero=True, minimo=-100_000, maximo=100_000)
_PATRON = Parametro(
    "patron",
    T,
    largo_minimo=1,
    largo_maximo=64,
    convertir=_convertir_patron,
    opciones=PATRONES_FRECUENTES,
)
_PATRON_DE_LECTURA = Parametro(
    "patron",
    T,
    largo_minimo=1,
    largo_maximo=64,
    convertir=_convertir_patron_de_lectura,
    opciones=PATRONES_FRECUENTES,
)

FUNCIONES = (
    Funcion("sumar_dias", "fecha", (F,), F, _sumar_dias, (_DIAS,), cota=_cota_fecha),
    Funcion("restar_dias", "fecha", (F,), F, _restar_dias, (_DIAS,), cota=_cota_fecha),
    Funcion("formato_fecha", "fecha", (F,), T, _formato_fecha, (_PATRON,), cota=_cota_formato),
    Funcion("a_fecha", "conversion", (T,), F, _a_fecha, (_PATRON_DE_LECTURA,), cota=_cota_fecha),
)

"""GSM-7 en el motor de texto enriquecido (RF-MM-27, B16): normalizar, medir y listar lo borrado.

Un SMS cuyo texto sale del alfabeto GSM-7 pasa a UCS-2 y su limite de 160 caracteres baja a 70. Este
modulo es el unico dueno de esa tabla (3GPP TS 23.038); MOWA MES la usa para forzar el mensaje a
GSM-7 antes de medirlo. Tres funciones:

- `a_gsm7(texto)`: deja el texto dentro de GSM-7, en este orden (decision del usuario, 2026-10-19):
  1. NFD y se quitan las marcas combinantes (tildes, dieresis, la virgulilla de la n), como la
     conciliacion de MOWA MES, que hace lo mismo con el mensaje de los dos lados (sin el `strip`);
  2. se transliteran los signos tipograficos con equivalente simple (`TRANSLITERACION`): comillas,
     puntos suspensivos, guiones, `°`, `º` y `ª`. Puede ALARGAR: `…` pasa de 1 a 3 caracteres. Los
     espacios especiales (cualquier caracter Unicode de categoria Zs que no sea el espacio normal:
     el espacio duro, el fino, U+202F, U+3000...) y la tabulacion se cambian por un espacio normal
     (decision del usuario, 2026-10-20), para que las palabras no queden pegadas; no cuentan como
     borrados y no cambian el largo. Los separadores de linea y de parrafo (Zl, Zp) y la
     tabulacion vertical no tienen equivalente decidido y se borran;
  3. se borra lo que siga fuera del alfabeto basico y de la tabla extendida (por ejemplo, un emoji).
  Se conservan los extendidos (`€ [ ] { } \\ ~ ^ |` y el salto de pagina) y los saltos de linea.
  Es idempotente y se puede aplicar por pieza: darle `a_gsm7` a cada trozo y unirlos da lo mismo
  que dárselo al texto entero (cada paso trabaja caracter por caracter), siempre que se aplique
  DESPUES de un recorte como `primeros(8)`: recortar antes de normalizar cuenta como caracter la
  letra con tilde y puede cortar distinto.
- `largo_gsm7(texto)`: lo que mide el SMS en unidades GSM-7: 1 por caracter y 2 por cada extendido
  (supuesto S-MM-9: asi lo cuenta el estandar; falta confirmar como lo cobra MES). Pensado para
  texto que ya esta en GSM-7; un caracter fuera de la tabla cuenta 1.
- `caracteres_borrados(texto)`: los caracteres que `a_gsm7` BORRA, sin repetir y en orden de
  aparicion, para avisar al usuario. Lo transliterado y los diacriticos no cuentan: no se pierden.
"""

import unicodedata
from functools import lru_cache

# Tope de las dos caches (`_caracter` y la tabla de `a_gsm7`). Los datos de la sabana pueden traer
# cualquier caracter de Unicode (mas de un millon): sin tope las caches crecerian con cada uno. Con
# este, los caracteres de un texto en espanol caben de sobra y los demas se calculan sin guardarse.
TOPE_DE_CACHE = 4096

# Alfabeto basico de GSM-7, en el orden de la tabla (128 posiciones). La posicion 0x1B es el
# escape hacia la tabla extendida, no un caracter, y por eso no esta en el texto.
_BASICO = (
    "@£$¥èéùìòÇ\nØø\rÅå"  # 0x00 - 0x0F
    "Δ_ΦΓΛΩΠΨΣΘΞ"
    "ÆæßÉ"  # 0x10 - 0x1F (sin el escape de 0x1B)
    " !\"#¤%&'()*+,-./"  # 0x20 - 0x2F
    "0123456789:;<=>?"  # 0x30 - 0x3F
    "¡ABCDEFGHIJKLMNO"  # 0x40 - 0x4F
    "PQRSTUVWXYZÄÖÑÜ§"  # 0x50 - 0x5F
    "¿abcdefghijklmno"  # 0x60 - 0x6F
    "pqrstuvwxyzäöñüà"  # 0x70 - 0x7F
)
# Tabla extendida (se manda como escape + codigo): cada uno ocupa DOS unidades en el SMS.
EXTENDIDOS = "\f^{}\\[~]|€"

CARACTERES_GSM7 = frozenset(_BASICO) | frozenset(EXTENDIDOS)

# Decision del usuario (2026-10-19): signos con equivalente simple en lugar de borrarlos.
TRANSLITERACION: dict[str, str] = {
    "“": '"',  # comilla doble izquierda
    "”": '"',  # comilla doble derecha
    "«": '"',  # comilla angular izquierda
    "»": '"',  # comilla angular derecha
    "‘": "'",  # comilla simple izquierda
    "’": "'",  # comilla simple derecha
    "…": "...",  # puntos suspensivos
    "–": "-",  # raya corta
    "—": "-",  # raya larga
    "°": "o",  # signo de grado
    "º": "o",  # indicador ordinal masculino
    "ª": "a",  # indicador ordinal femenino
}


def _transliterar(c: str) -> str:
    """El equivalente de un caracter: el de la tabla, un espacio normal para los espacios
    especiales (categoria Zs) y la tabulacion, o el mismo caracter."""
    equivalente = TRANSLITERACION.get(c)
    if equivalente is not None:
        return equivalente
    if c == "\t" or (c != " " and unicodedata.category(c) == "Zs"):
        return " "
    return c


@lru_cache(maxsize=TOPE_DE_CACHE)
def _caracter(caracter: str) -> tuple[str, bool]:
    """(lo que queda de este caracter, si se borro algo de el). Con cache acotada por
    `TOPE_DE_CACHE`: deja la normalizacion de un texto en un lookup por letra."""
    base = "".join(
        c for c in unicodedata.normalize("NFD", caracter) if not unicodedata.combining(c)
    )
    salida: list[str] = []
    borrado = False
    for c in base:
        for t in _transliterar(c):
            if t in CARACTERES_GSM7:
                salida.append(t)
            else:
                borrado = True
    return "".join(salida), borrado


class _Tabla(dict):
    """Tabla de `str.translate` que se llena sola hasta `TOPE_DE_CACHE` caracteres distintos;
    pasado el tope sigue normalizando bien pero ya no guarda."""

    def __missing__(self, codigo: int) -> str:
        salida = _caracter(chr(codigo))[0]
        if len(self) < TOPE_DE_CACHE:
            self[codigo] = salida
        return salida


_TABLA = _Tabla()


def a_gsm7(texto: str) -> str:
    """El texto dentro de GSM-7: sin diacriticos, con los signos transliterados y sin lo demas."""
    return texto.translate(_TABLA)


def caracteres_borrados(texto: str) -> tuple[str, ...]:
    """Los caracteres del texto que `a_gsm7` borra, sin repetir y en orden de aparicion.

    Se informa el caracter tal como aparece en el texto (una `й` cirilica, no su base). Los
    diacriticos que se quitan y los signos que se transliteran no cuentan: no se pierden.
    """
    return tuple(dict.fromkeys(c for c in texto if _caracter(c)[1]))


# --- Lo borrado, agrupado como lo ve una persona (T-MM-B9) ---------------------------------

_ZWJ = "\N{ZERO WIDTH JOINER}"
_KEYCAP = "\N{COMBINING ENCLOSING KEYCAP}"
_INDICADORES_REGIONALES = range(0x1F1E6, 0x1F200)
_MODIFICADORES_DE_PIEL = range(0x1F3FB, 0x1F400)
_SELECTORES_DE_VARIACION = (range(0xFE00, 0xFE10), range(0xE0100, 0xE01F0))
_ETIQUETAS = range(0xE0020, 0xE0080)


def _extiende(c: str) -> bool:
    """Si `c` se pega al caracter anterior en un mismo grafema (UAX #29, reglas de emoji)."""
    codigo = ord(c)
    return (
        c in (_ZWJ, _KEYCAP)
        or codigo in _MODIFICADORES_DE_PIEL
        or codigo in _ETIQUETAS
        or any(codigo in selectores for selectores in _SELECTORES_DE_VARIACION)
        or unicodedata.category(c) in ("Mn", "Me", "Mc")
    )


def _se_pega(ultimo: str, regionales: int, c: str) -> bool:
    """Si `c` se pega al grupo en curso, cuyo ultimo caracter es `ultimo` y que lleva `regionales`
    indicadores regionales (la cuenta se arrastra: recontarlos por caracter seria cuadratico)."""
    if _extiende(c) or ultimo == _ZWJ:
        return True
    # Dos indicadores regionales seguidos son una bandera; el tercero empieza otra.
    return (
        ord(c) in _INDICADORES_REGIONALES
        and ord(ultimo) in _INDICADORES_REGIONALES
        and regionales % 2 == 1
    )


def grafemas_borrados(texto: str) -> tuple[str, ...]:
    """Lo que `a_gsm7` BORRA del texto, agrupado por grafema, sin repetir y en orden de aparicion.

    Un emoji compuesto (una mano con tono de piel, una familia con ZWJ, una bandera) es UN elemento
    y no varios: es lo que la persona escribio, y asi se le avisa. Si el grafema es mixto (una letra
    que se conserva seguida de un ZWJ suelto, un `1` con su selector y su keycap), solo se informa
    la parte que se borra. Lo transliterado, los diacriticos y los espacios que pasan a un espacio
    normal nunca aparecen.

    Entrada: el texto ORIGINAL (no la salida de `caracteres_borrados`, que ya quito repetidos y
    perdio las secuencias). Que se borra lo decide la misma regla por caracter (`_caracter`) que usa
    `a_gsm7`: no hay una tabla aparte; aqui solo se AGRUPAN las secuencias contiguas de caracteres
    borrados. La union de los puntos de codigo de los elementos es exactamente el conjunto que
    devuelve `caracteres_borrados`. Una pasada, lineal en el largo, sin caches nuevas.

    Alcance. Agrupa con las reglas de emoji de UAX #29 (ZWJ, selectores de variacion, modificadores
    de tono de piel, keycap, etiquetas, marcas combinantes y pares de indicadores regionales) y no
    con la `\\X` de la libreria `regex`, que el proyecto no usa. NO implementa el resto de UAX #29:
    ni las silabas de hangul ni los conjuntos de las escrituras indicas (virama): un caracter de
    esas escrituras fuera de GSM-7 se agrupa solo con las marcas que lo siguen. Para el aviso al
    usuario ("al enviar se borran: ...") basta: lo que importa es no partir un emoji.
    """
    grupos: list[str] = []
    actual: list[str] = []
    regionales = 0  # indicadores regionales del grupo en curso
    for c in texto:
        if not _caracter(c)[1]:  # se conserva, se transliteran o pierde solo su diacritico
            if actual:
                grupos.append("".join(actual))
                actual = []
        elif actual and _se_pega(actual[-1], regionales, c):
            actual.append(c)
            regionales += ord(c) in _INDICADORES_REGIONALES
        else:
            if actual:
                grupos.append("".join(actual))
            actual = [c]
            regionales = int(ord(c) in _INDICADORES_REGIONALES)
    if actual:
        grupos.append("".join(actual))
    return tuple(dict.fromkeys(grupos))


def largo_gsm7(texto: str) -> int:
    """Largo del SMS en unidades GSM-7: 1 por caracter y 2 por cada extendido."""
    return len(texto) + sum(texto.count(c) for c in EXTENDIDOS)


def largo_gsm7_normalizado(texto: str) -> int:
    """El largo en GSM-7 de lo que SALDRIA de `a_gsm7(texto)`: exacto para un texto fijo aunque
    todavia no este normalizado (la transliteracion puede alargarlo: `…` mide 3)."""
    return largo_gsm7(a_gsm7(texto))

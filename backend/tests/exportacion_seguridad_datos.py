"""Datos de la prueba de exportacion segura (B3, RF-53): tablas sinteticas y huellas.

Solo datos y dos funciones de huella, sin logica de prueba: los usan
`test_exportacion_segura.py` y el calculo de las constantes congeladas en HEAD 3e567d7
(`exportacion_seguridad_congelados.py`), antes de tocar los exportadores.

Ningun valor es real: titulares, numeros y textos inventados.
"""

import hashlib
import io
import re
import zipfile
from datetime import date, datetime
from decimal import Decimal

from app.core.entities.exportacion import Tabla
from app.core.entities.mowa_mes_campana import FilaCarga

CABECERAS = ("texto", "importe", "entero", "fecha", "fecha_hora", "vacio", "booleano", "otro")

# Ningun texto empieza con "=": el XLSX y el CSV con proteger_formulas=False tienen que salir igual
# que antes de B3. Si con "+", "-" o "@", que en el XLSX ya salian como texto literal.
TABLA_SIN_IGUAL = Tabla(
    nombre="Carga sintetica",
    cabeceras=CABECERAS,
    filas=(
        {
            "texto": "000000000000000001",
            "importe": Decimal("1500.50"),
            "entero": 12,
            "fecha": date(2026, 9, 18),
            "fecha_hora": datetime(2026, 9, 18, 10, 30),
            "vacio": None,
            "booleano": True,
            "otro": "APELLIDO, NOMBRE",
        },
        {
            "texto": "  espacios  ",
            "importe": Decimal("-1234.56"),
            "entero": -5,
            "fecha": date(2027, 1, 31),
            "fecha_hora": datetime(2026, 1, 1, 0, 0),
            "vacio": None,
            "booleano": False,
            "otro": "línea 1\nlínea 2",
        },
        {
            "texto": "+51900000001",
            "importe": Decimal("0"),
            "entero": 0,
            "fecha": None,
            "fecha_hora": None,
            "vacio": None,
            "booleano": None,
            "otro": "-2+3",
        },
        {
            "texto": "@usuario",
            "importe": Decimal("3.5"),
            "entero": 7,
            "fecha": date(2026, 12, 31),
            "fecha_hora": datetime(2026, 12, 31, 23, 59, 58),
            "vacio": None,
            "booleano": True,
            "otro": "ñandú ÁÉÍÓÚ ¡hola! a=b",
        },
        {
            "texto": "-5",
            "importe": Decimal("-0.5"),
            "entero": 100,
            "fecha": date(2026, 2, 28),
            "fecha_hora": None,
            "vacio": None,
            "booleano": False,
            "otro": "\tcon tabulacion",
        },
        {
            "texto": "'ya trae apostrofo",
            "importe": Decimal("10"),
            "entero": 1,
            "fecha": None,
            "fecha_hora": None,
            "vacio": None,
            "booleano": None,
            "otro": "\rcon retorno",
        },
    ),
)

# Los mensajes que empiezan con lo que el titular escriba: `titular[:8] + parte 1 + ...`.
FILAS_MOWA_SIN_IGUAL = (
    FilaCarga("900000001", "ZZPRUEBA supervision", "00000001", supervision=True),
    FilaCarga("900000101", "ZZPRUEBA vencio el 06/09/2026, acércate a pagar", "01234567"),
    FilaCarga("900000102", "-ZZPRUEB vencio el 06/09/2026, acércate a pagar", "20123456789"),
    FilaCarga("900000103", "+ZZPRUEB vencio el 06/09/2026", "00000009"),
    FilaCarga(
        "900000104", "@ZZPRUEB vencio el 06/09/2026 INFO por https://wa.me/+51900000123", "1"
    ),
    FilaCarga("900000105", "  Peña Ruiz vencio el 06/09/2026, línea\notra línea", "12345678"),
)


def huella_bytes(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


_MARCAS_DE_TIEMPO = re.compile(rb"(<dcterms:(?:created|modified)[^>]*>)[^<]*(</dcterms:)")


def huella_xlsx(contenido: bytes) -> str:
    """SHA-256 de todas las partes del .xlsx, sin las marcas de tiempo de `docProps/core.xml`.

    Un mismo libro escrito dos veces nunca es identico byte a byte: openpyxl guarda la fecha y
    hora de creacion en `core.xml` y en la cabecera de cada entrada del zip. Todo lo demas
    (`sheet1.xml`, los estilos, las relaciones) tiene que coincidir, y el largo total tambien.
    """
    resumen = hashlib.sha256()
    with zipfile.ZipFile(io.BytesIO(contenido)) as libro:
        for nombre in sorted(libro.namelist()):
            datos = libro.read(nombre)
            if nombre == "docProps/core.xml":
                datos = _MARCAS_DE_TIEMPO.sub(rb"\1\2", datos)
            resumen.update(nombre.encode("utf-8") + b"\0" + datos + b"\0")
    return resumen.hexdigest()


# Textos que una hoja de calculo podria tomar por formula, junto a los que no lo son. Es lo que se
# lee de vuelta en la prueba de exportacion segura; cada valor va con su tipo.
TABLA_PELIGROSA = Tabla(
    nombre="Peligrosa",
    cabeceras=("valor",),
    filas=tuple(
        {"valor": v}
        for v in (
            "=1+1",
            "=cmd|' /C calc'!A0",
            "+1+1",
            "-2+3",
            "@SUM(A1:A2)",
            "\t=1+1",
            "\r=1+1",
            "-",
            "+",
            "-1,234.56",
            "+51900000001",
            "-5",
            "3.5",
            "1.234,56",
            "-.5",
            "-5abc",
            "= texto con espacio",
            "normal",
            "línea 1\nlínea 2",
            "=línea 1\nlínea 2",
            "Ñandú =1+1",
            "",
            Decimal("-1234.56"),
            -5,
            0,
            Decimal("3.5"),
            True,
            date(2026, 9, 18),
            None,
        )
    ),
)


def largo_sin_comprimir_sin_core(contenido: bytes) -> int:
    """Suma del largo SIN comprimir (`ZipInfo.file_size`) de todas las partes menos `core.xml`.

    No depende de la compresion: el largo comprimido cambia con la implementacion de zlib (el
    clasico de CPython 3.13 y el zlib-ng de CPython 3.14 en Windows dan 5110 y 5118 bytes para las
    MISMAS partes con el mismo contenido) y el `core.xml` ademas lleva la fecha y la hora.

    Alcanza para la division por bytes de MOWA MES (`division.py`) porque esa division no usa un
    largo congelado: escribe cada tramo y mide su tamano REAL, comprimido, en cada corrida. Lo que
    estas pruebas deben garantizar es que el exportador escribe las mismas partes con el mismo
    contenido que en HEAD, de modo que cada fila pesa lo mismo antes de comprimir. Eso lo fijan la
    huella (el contenido de todas las partes) y este largo (que ademas avisa si se agrega o se quita
    una parte); el largo comprimido no se congela a proposito.
    """
    with zipfile.ZipFile(io.BytesIO(contenido)) as libro:
        return sum(
            len(libro.read(nombre)) for nombre in libro.namelist() if nombre != "docProps/core.xml"
        )

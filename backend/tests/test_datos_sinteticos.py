"""Los datos de prueba, los ejemplos del catalogo y la documentacion no llevan telefonos reales.

Regla del proyecto (AGENTS.md): datos sinteticos. Un telefono de prueba es 900000xxx (o con el
prefijo de pais, +51900000xxx). Un numero de 9 digitos que empieza con 9 y no es de ese rango puede
ser el de una persona: esta prueba lo busca en el codigo, las pruebas, la documentacion y las
pantallas, para que no vuelva a colarse uno parecido a un telefono real (T-MTE-B18).

El unico otro numero de 9 digitos permitido son los ids de MES de las pruebas de MOWA MES
(990000xxx), que no son telefonos.
"""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CARPETAS = [
    "backend/app",
    "backend/tests",
    "backend/scripts",
    "docs",
    "frontend/src",
    "frontend/e2e",
    "frontend/tests",
]
EXTENSIONES = {".py", ".md", ".ts", ".astro", ".json", ".mjs", ".sql"}
NUMERO = re.compile(r"(?<![0-9])(?:\+?51)?(9[0-9]{8})(?![0-9])")
PERMITIDO = re.compile(r"900000[0-9]{3}|990000[0-9]{3}")


def _archivos():
    for carpeta in CARPETAS:
        for ruta in sorted((RAIZ / carpeta).rglob("*")):
            if ruta.suffix in EXTENSIONES and "node_modules" not in ruta.parts and ruta.is_file():
                yield ruta


def test_ningun_dato_de_prueba_parece_un_telefono_real() -> None:
    sospechosos = []
    for ruta in _archivos():
        for numero_de_linea, linea in enumerate(
            ruta.read_text(encoding="utf-8").splitlines(), start=1
        ):
            for m in NUMERO.finditer(linea):
                if not PERMITIDO.fullmatch(m.group(1)):
                    sospechosos.append(f"{ruta.relative_to(RAIZ)}:{numero_de_linea}: {m.group(1)}")

    assert sospechosos == [], "Telefonos que no son del rango 900000xxx:\n" + "\n".join(sospechosos)


def test_la_busqueda_distingue_lo_real_de_lo_sintetico() -> None:
    # La propia busqueda tiene que reconocer un numero con y sin el prefijo del pais.
    real = "98" + "7000111"  # armado aqui para que esta propia prueba no lo contenga
    ejemplos = {real: True, "+51" + real: True, "51" + real: True, "900000123": False}
    for texto, sospechoso in ejemplos.items():
        encontrados = [m.group(1) for m in NUMERO.finditer(texto)]
        assert bool(encontrados and not PERMITIDO.fullmatch(encontrados[0])) is sospechoso, texto
    assert NUMERO.search("0000000000000000012") is None  # un pagare no es un telefono

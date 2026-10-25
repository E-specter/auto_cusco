"""Lector de archivos CSV (RF-57, ver docs/mapeador-encabezados.md, seccion 4).

- Codificacion, en este orden: UTF-8 con BOM (se quita), UTF-8, Windows-1252 (el «CSV» del Excel
  de Windows en espanol) y, solo si Windows-1252 no decodifica (los bytes 0x81, 0x8D, 0x8F, 0x90 y
  0x9D no estan definidos), Latin-1. La elegida gana.
- Separador: el primero de `;`, tabulacion y `,` que da el MISMO numero de campos (mas de uno) en
  todos los registros de la muestra (los primeros 50 de los primeros 64 KB). No se deja al
  desempate de `csv.Sniffer`, que prefiere la coma: un CSV del Excel en espanol usa `;` y coma
  decimal. Si ninguno es consistente, `csv.Sniffer` restringido a esos tres y, si tampoco decide,
  `;` si aparece en la primera linea y, si no, `,`. El elegido gana.
- La primera fila no vacia es la de encabezados. Las celdas salen como texto: no se convierte nada
  (el normalizador de la sabana interpreta los numeros). Los numeros de fila van en base 1 y una
  celda entrecomillada con saltos de linea cuenta como una sola fila, como en Excel.
"""

import codecs
import csv
import io

from app.adapters.input.celdas import recortar
from app.core.entities.lectura_tabla import FormatoTabla, OpcionesLectura, TablaLeida
from app.core.entities.sabana import (
    ArchivoIlegible,
    CodificacionInvalida,
    CodificacionNoCoincide,
    FilaCruda,
    HojaVacia,
    SeparadorInvalido,
)

MUESTRA_PARA_SEPARADOR = 64 * 1024
REGISTROS_PARA_SEPARADOR = 50
SEPARADORES = ",;\t"  # los que mira csv.Sniffer
# Los candidatos, en el orden en que se desempata cuando mas de uno es consistente.
CANDIDATOS_DE_SEPARADOR = (";", "\t", ",")
CODIFICACION_CON_BOM = "utf-8-sig"
# Las codificaciones que se detectan, en el orden en que se prueban: la lista de la pantalla.
CODIFICACIONES = (CODIFICACION_CON_BOM, "utf-8", "windows-1252", "latin-1")
_BOM = "﻿"


def _decodificar(contenido: bytes, elegida: str | None) -> tuple[str, str]:
    """El texto y el nombre de la codificacion usada."""
    if elegida:
        try:
            codecs.lookup(elegida)
        except LookupError as exc:
            raise CodificacionInvalida(f"La codificación {elegida!r} no existe") from exc
        try:
            return contenido.decode(elegida).removeprefix(_BOM), elegida
        except UnicodeDecodeError as exc:
            raise CodificacionNoCoincide(
                f"El archivo no se puede leer como {elegida}: el byte {exc.start} no es válido"
            ) from exc
    if contenido.startswith(codecs.BOM_UTF8):
        return contenido.decode(CODIFICACION_CON_BOM), CODIFICACION_CON_BOM
    for nombre in CODIFICACIONES[1:-1]:
        try:
            return contenido.decode(nombre), nombre
        except UnicodeDecodeError:
            continue
    return contenido.decode(CODIFICACIONES[-1]), CODIFICACIONES[-1]  # Latin-1 decodifica todo


def _campos_por_registro(muestra: str, separador: str, completa: bool) -> list[int]:
    """Cuantos campos tiene cada uno de los primeros registros de la muestra (sin los vacios).

    Si la muestra se corto a la mitad (`completa` es falso), el ultimo registro puede estar
    partido y no se cuenta.
    """
    registros: list[list[str]] = []
    try:
        for registro in csv.reader(io.StringIO(muestra, newline=""), delimiter=separador):
            registros.append(registro)
            if len(registros) > REGISTROS_PARA_SEPARADOR:
                break
    except csv.Error:
        return []
    if not completa and len(registros) <= REGISTROS_PARA_SEPARADOR:
        registros = registros[:-1]
    return [len(r) for r in registros[:REGISTROS_PARA_SEPARADOR] if r]


def _separador_consistente(muestra: str, completa: bool) -> str | None:
    """El primer candidato (`;`, tabulacion, `,`) con el mismo numero de campos (mas de uno) en
    todos los registros de la muestra; `None` si ninguno."""
    for candidato in CANDIDATOS_DE_SEPARADOR:
        campos = _campos_por_registro(muestra, candidato, completa)
        if campos and campos[0] > 1 and len(set(campos)) == 1:
            return candidato
    return None


def _detectar_separador(texto: str) -> str:
    muestra = texto[:MUESTRA_PARA_SEPARADOR]
    consistente = _separador_consistente(muestra, completa=len(texto) <= MUESTRA_PARA_SEPARADOR)
    if consistente is not None:
        return consistente
    try:
        return csv.Sniffer().sniff(muestra, delimiters=SEPARADORES).delimiter
    except csv.Error:
        primera = texto.lstrip("\r\n").split("\n", 1)[0]
        return ";" if ";" in primera else ","


def _validar_separador(separador: str) -> None:
    if len(separador) != 1 or separador in '\r\n"':
        raise SeparadorInvalido(
            "El separador debe ser un solo carácter (no un salto de línea ni comillas)"
        )


def leer_csv(contenido: bytes, opciones: OpcionesLectura = OpcionesLectura()) -> TablaLeida:  # noqa: B008
    texto, codificacion = _decodificar(contenido, opciones.codificacion)
    separador = opciones.separador or _detectar_separador(texto)
    _validar_separador(separador)

    cabecera: tuple[int, list[str]] | None = None
    filas: list[FilaCruda] = []
    try:
        for numero, celdas in enumerate(
            csv.reader(io.StringIO(texto, newline=""), delimiter=separador), 1
        ):
            celdas = recortar(celdas)
            if not celdas:
                continue
            if cabecera is None:
                cabecera = (numero, celdas)
            else:
                filas.append(FilaCruda(numero_fila=numero, celdas=celdas))
    except csv.Error as exc:
        raise ArchivoIlegible(f"El CSV no se pudo leer: {exc}") from exc
    if cabecera is None:
        raise HojaVacia("El archivo no tiene cabecera ni datos")
    return TablaLeida(
        formato=FormatoTabla.CSV,
        hojas=(),
        hoja=None,
        separador=separador,
        codificacion=codificacion,
        fila_cabecera=cabecera[0],
        cabeceras=cabecera[1],
        filas=filas,
    )

"""Reglas de una plataforma de destino para una definicion de columnas (RF-72, T-HI-B2).

Una plataforma (WhatsMKT, MOWA MES) declara aqui, de forma DECLARATIVA, lo que fija de un archivo
de carga. El constructor de columnas no conoce ninguna plataforma: cada modulo registra sus reglas
desde su propio paquete en un `RegistroPlataformas` (RF-14, RF-31), y tanto la validacion del
backend como la pantalla leen estas mismas reglas (`GET /definiciones-columnas/plataformas`).

La validacion exige solo cuatro cosas (`services/definiciones_columnas/plataformas.py`):

1. cada columna fija esta presente;
2. en su posicion;
3. con su tipo;
4. el resto de las columnas respeta `tipo_resto` y, si `admite_mas_columnas` es falso, no hay mas
   columnas que las fijas.

`encabezado_por_posicion` NO se valida: es solo el valor por defecto del nombre de una columna
nueva. `contenido_por_defecto`, `contenido_editable` y `celda_texto` los usa el constructor para
armar la columna fija (su contenido de partida, si se puede editar y si va en celda de texto,
RF-73); no se exigen al guardar.

Las posiciones cuentan desde 1 (la 1.ª columna), como las dice la pantalla; los problemas, en
cambio, ubican la columna por su posicion en el pedido desde 0, como todos los de una definicion
(RF-46).
"""

from dataclasses import dataclass

from app.core.entities.mapeo import TipoSalida


@dataclass(frozen=True)
class ColumnaFija:
    """Una columna que la plataforma fija: su nombre, su posicion (desde 1) y su tipo."""

    posicion: int
    nombre: str
    contenido_por_defecto: str | None
    tipo: TipoSalida
    celda_texto: bool = False
    contenido_editable: bool = True


@dataclass(frozen=True)
class ReglasPlataforma:
    """Lo que una plataforma fija de una definicion de columnas.

    - `clave`: el identificador estable que se guarda con la definicion (`whatsmkt`).
    - `etiqueta`: el nombre que ve el usuario («WhatsMKT»).
    - `columnas_fijas`: las columnas fijas, con posiciones distintas y consecutivas desde 1.
    - `encabezado_por_posicion`: un patron con `{n}` (por ejemplo `[$MARCRO{n}$]`) que da el nombre
      por defecto de las columnas que siguen a las fijas, desde `n = 1`. Solo un valor por defecto.
    - `tipo_resto`: el tipo que deben tener las demas columnas; `None` las deja libres.
    - `admite_mas_columnas`: falso si la definicion no puede tener mas columnas que las fijas.
    """

    clave: str
    etiqueta: str
    columnas_fijas: tuple[ColumnaFija, ...] = ()
    encabezado_por_posicion: str | None = None
    tipo_resto: TipoSalida | None = None
    admite_mas_columnas: bool = True

    def __post_init__(self) -> None:
        posiciones = [fija.posicion for fija in self.columnas_fijas]
        if posiciones != list(range(1, len(posiciones) + 1)):
            raise ValueError(
                f"Las columnas fijas de {self.clave!r} deben ir en las posiciones 1, 2, 3...: "
                f"{posiciones}"
            )
        nombres = [fija.nombre for fija in self.columnas_fijas]
        if len(set(nombres)) != len(nombres):
            raise ValueError(f"Las columnas fijas de {self.clave!r} repiten un nombre")
        if not self.clave.strip() or not self.etiqueta.strip():
            raise ValueError("Una plataforma necesita clave y etiqueta")
        if self.encabezado_por_posicion is not None and "{n}" not in self.encabezado_por_posicion:
            raise ValueError("`encabezado_por_posicion` lleva `{n}` donde va la posicion")


class PlataformaDesconocida(Exception):
    def __init__(self, clave: str) -> None:
        super().__init__(f"La plataforma {clave!r} no esta registrada")
        self.clave = clave

"""Regla de feriados nacionales de Peru, para cualquier ano (RF-MM-08, supuesto S-MM-4).

Lista vigente al 2026: articulo 6 del Decreto Legislativo 713, con las
modificaciones de la Ley 31530 (6 de agosto, Batalla de Junin), la Ley 31788
(7 de junio, Batalla de Arica y Dia de la Bandera) y la Ley 31822 (23 de julio,
Dia de la Fuerza Aerea del Peru). Contrastada el 2026-09-13 con la lista de
16 feriados de 2026 publicada en gob.pe/feriados y en la prensa. Debe revisarse
con el usuario (S-MM-4).

La regla refleja la ley vigente y no la historia: aplicada a un ano anterior a
2023 incluye feriados que todavia no existian. Un cambio de ley se ajusta con
las excepciones del calendario o, si es permanente, cambiando esta lista.
"""

from datetime import date, timedelta

from app.core.entities.calendario import Feriado

# (mes, dia, descripcion)
FERIADOS_FECHA_FIJA: tuple[tuple[int, int, str], ...] = (
    (1, 1, "Año Nuevo"),
    (5, 1, "Día del Trabajo"),
    (6, 7, "Batalla de Arica y Día de la Bandera"),
    (6, 29, "San Pedro y San Pablo"),
    (7, 23, "Día de la Fuerza Aérea del Perú"),
    (7, 28, "Fiestas Patrias"),
    (7, 29, "Fiestas Patrias"),
    (8, 6, "Batalla de Junín"),
    (8, 30, "Santa Rosa de Lima"),
    (10, 8, "Combate de Angamos"),
    (11, 1, "Día de Todos los Santos"),
    (12, 8, "Inmaculada Concepción"),
    (12, 9, "Batalla de Ayacucho"),
    (12, 25, "Navidad"),
)

# (dias respecto del domingo de Pascua, descripcion)
FERIADOS_DE_PASCUA: tuple[tuple[int, str], ...] = (
    (-3, "Jueves Santo"),
    (-2, "Viernes Santo"),
)


def domingo_de_pascua(anio: int) -> date:
    """Domingo de Pascua del calendario gregoriano (algoritmo de Meeus/Jones/Butcher)."""
    a = anio % 19
    b, c = divmod(anio, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    semana = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * semana) // 451
    mes, dia = divmod(h + semana - 7 * m + 114, 31)
    return date(anio, mes, dia + 1)


def feriados_de_ley(anio: int) -> tuple[Feriado, ...]:
    """Feriados nacionales del ano, ordenados por fecha."""
    pascua = domingo_de_pascua(anio)
    feriados = [Feriado(date(anio, mes, dia), nombre) for mes, dia, nombre in FERIADOS_FECHA_FIJA]
    feriados += [
        Feriado(pascua + timedelta(days=dias), nombre) for dias, nombre in FERIADOS_DE_PASCUA
    ]
    return tuple(sorted(feriados, key=lambda feriado: feriado.fecha))

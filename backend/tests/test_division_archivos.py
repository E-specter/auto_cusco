"""La division comun de una carga en archivos, sin ninguna plataforma (T-MM-C10, L-B9).

Filas sinteticas de un tipo propio: lo que se prueba es el algoritmo (tope de filas, corte por
bytes medidos, corte recursivo, orden y supervision en el primer archivo), no un escritor real.
"""

from dataclasses import dataclass

import pytest

from app.core.entities.division_archivos import ArchivoDemasiadoGrande
from app.core.services.division_archivos import dividir, previstos_por_filas, tramos_por_filas


@dataclass(frozen=True)
class Fila:
    texto: str
    supervision: bool = False


def _escribir(filas) -> bytes:
    """Un archivo es sus textos separados por coma: su tamano es predecible."""
    return ",".join(f.texto for f in filas).encode()


def _filas(cantidad: int, supervision: int = 0) -> list[Fila]:
    return [Fila(f"f{i:03d}", supervision=i < supervision) for i in range(cantidad)]


def test_tramos_por_filas() -> None:
    assert tramos_por_filas(0, 3) == []
    assert tramos_por_filas(7, 3) == [(0, 3), (3, 6), (6, 7)]
    assert tramos_por_filas(6, 3) == [(0, 3), (3, 6)]
    with pytest.raises(ValueError):
        tramos_por_filas(5, 0)


def test_el_tope_de_filas_parte_la_carga_y_la_supervision_cuenta_en_el_primero() -> None:
    tramos = dividir(_filas(7, supervision=2), _escribir, 3, 10_000)

    assert [(len(t.filas), t.supervision) for t in tramos] == [(3, 2), (3, 0), (1, 0)]


def test_un_tramo_dentro_del_maximo_queda_entero() -> None:
    (tramo,) = dividir(_filas(5), _escribir, 50, 10_000)

    assert tramo.contenido == _escribir(tramo.filas)
    assert len(tramo.filas) == 5


def test_un_tramo_que_pasa_de_los_bytes_se_parte_y_conserva_el_orden() -> None:
    filas = _filas(10)

    tramos = dividir(filas, _escribir, 50, 30)

    assert len(tramos) > 1
    assert all(len(t.contenido) <= 30 for t in tramos)
    assert [f for t in tramos for f in t.filas] == filas


def test_un_pedazo_que_sigue_pasando_se_vuelve_a_partir() -> None:
    # Tres filas largas al inicio: partir por proporcion no alcanza y hay que cortar otra vez.
    filas = [Fila("x" * 20)] * 3 + [Fila("y")] * 9

    tramos = dividir(filas, _escribir, 50, 45)

    assert all(len(t.contenido) <= 45 for t in tramos)
    assert [f for t in tramos for f in t.filas] == filas
    assert len(tramos) >= 4


def test_cada_archivo_se_mide_con_lo_que_escribe_el_escritor() -> None:
    escritos: list[int] = []

    def escribir(filas) -> bytes:
        escritos.append(len(filas))
        return _escribir(filas)

    dividir(_filas(10), escribir, 50, 30)

    assert escritos[0] == 10  # primero se escribe el tramo entero y se mide


def test_una_fila_mas_grande_que_el_maximo_no_se_puede_dividir() -> None:
    with pytest.raises(ArchivoDemasiadoGrande, match="Una sola fila ocupa"):
        dividir(_filas(2), _escribir, 50, 3)


def test_sin_filas_no_hay_archivos() -> None:
    assert dividir([], _escribir, 50, 30) == []
    assert previstos_por_filas([], 50) == []


def test_previstos_por_filas() -> None:
    previstos = previstos_por_filas(_filas(7, supervision=2), 3)

    assert [(p.numero, p.filas, p.supervision) for p in previstos] == [
        (1, 3, 2),
        (2, 3, 0),
        (3, 1, 0),
    ]

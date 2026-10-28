"""Memoria acotada de la lista de valores de un filtro (T-FV-B3, RF-67).

Por que es seguro guardar en memoria: las filas de una carga NO cambian despues de procesarla (una
carga nueva es otra fila de `carga` con otro id, que no se reutiliza) y la decision y la lista de un
campo salen solo de esas filas. Por eso la clave lleva el id de la carga VIGENTE: si la fecha pasa a
otra version vigente, la clave cambia y se vuelve a calcular, sin invalidar nada a mano. (Si algun
dia una carga se reprocesara en su sitio, habria que sumar su version a la clave.)

Por que se guarda la decision y tambien la lista:

- la decision del umbral (`DISTINCT ... LIMIT umbral + 1`) recorre toda la fecha cuando el campo
  tiene pocos valores, y la lista es otra pasada completa: dos recorridos de la tabla por pedido;
- con la decision en memoria un pedido hace, como mucho, el de la lista; y la lista sin filtros (la
  que se abre al elegir el campo) y las que ya se pidieron en la cascada no se repiten.

Acotada (LRU) para no crecer sin limite, y con candado: la API atiende en hilos. Solo se guardan
listas de campos que ofrecen lista (a lo sumo `umbral` valores), nunca las de un campo que lo
supera.
"""

from collections import OrderedDict
from collections.abc import Hashable
from threading import Lock
from typing import Any

ENTRADAS_POR_DEFECTO = 256
_AUSENTE = object()


class _Lru:
    def __init__(self, maximo: int) -> None:
        self._maximo = maximo
        self._entradas: OrderedDict[Hashable, Any] = OrderedDict()
        self._candado = Lock()

    def obtener(self, clave: Hashable) -> Any:
        with self._candado:
            valor = self._entradas.get(clave, _AUSENTE)
            if valor is _AUSENTE:
                return None
            self._entradas.move_to_end(clave)
            return valor

    def guardar(self, clave: Hashable, valor: Any) -> None:
        with self._candado:
            self._entradas[clave] = valor
            self._entradas.move_to_end(clave)
            while len(self._entradas) > self._maximo:
                self._entradas.popitem(last=False)

    def __len__(self) -> int:
        with self._candado:
            return len(self._entradas)

    def vaciar(self) -> None:
        with self._candado:
            self._entradas.clear()


class CacheValoresFiltro:
    """La decision del umbral y las listas de valores, cada una en su memoria acotada.

    - decision: `(id de la carga vigente, campo, umbral)` -> si el campo ofrece lista (bool);
    - lista: `(id de la carga vigente, campo, filtros de arriba, umbral)` -> los valores ya
      ordenados.
    """

    def __init__(self, entradas: int = ENTRADAS_POR_DEFECTO) -> None:
        self._decisiones = _Lru(entradas)
        self._listas = _Lru(entradas)

    def decision(self, clave: Hashable) -> bool | None:
        """None si esa decision no esta en memoria."""
        return self._decisiones.obtener(clave)

    def guardar_decision(self, clave: Hashable, ofrece_lista: bool) -> None:
        self._decisiones.guardar(clave, ofrece_lista)

    def lista(self, clave: Hashable) -> tuple | None:
        """None si esa lista no esta en memoria."""
        return self._listas.obtener(clave)

    def guardar_lista(self, clave: Hashable, valores: tuple) -> None:
        self._listas.guardar(clave, valores)

    @property
    def tamanos(self) -> tuple[int, int]:
        """(decisiones, listas) guardadas: para las pruebas."""
        return len(self._decisiones), len(self._listas)

    def vaciar(self) -> None:
        self._decisiones.vaciar()
        self._listas.vaciar()

/**
 * The order of the filters of a selection (T-FV-F3, RF-68, docs/filtro-valores-interfaz.md §3): moving one in a list,
 * the edges, which button keeps the focus, and where a drag would drop it.
 */
import { describe, expect, it } from 'vitest';

import { botonConFoco, destinoDeArrastre, moverFiltro, posicion, puedeMover } from '../../src/lib/orden-filtros';

describe('mover un filtro en la lista', () => {
  const lista = ['a', 'b', 'c', 'd'];

  it('sube y baja una posición, y los demás conservan su orden', () => {
    expect(moverFiltro(lista, 2, 1)).toEqual(['a', 'c', 'b', 'd']);
    expect(moverFiltro(lista, 1, 2)).toEqual(['a', 'c', 'b', 'd']);
  });

  it('puede saltar varios lugares, como al soltar un arrastre', () => {
    expect(moverFiltro(lista, 3, 0)).toEqual(['d', 'a', 'b', 'c']);
    expect(moverFiltro(lista, 0, 3)).toEqual(['b', 'c', 'd', 'a']);
  });

  it('en el mismo lugar, o fuera de la lista, no cambia nada', () => {
    expect(moverFiltro(lista, 1, 1)).toEqual(lista);
    expect(moverFiltro(lista, -1, 2)).toEqual(lista);
    expect(moverFiltro(lista, 4, 0)).toEqual(lista);
  });

  it('un destino fuera de los bordes se queda en el borde', () => {
    expect(moverFiltro(lista, 1, -5)).toEqual(['b', 'a', 'c', 'd']);
    expect(moverFiltro(lista, 1, 99)).toEqual(['a', 'c', 'd', 'b']);
    // A negative index must not count from the end, as `splice` would.
    expect(moverFiltro(lista, 3, -1)).toEqual(['d', 'a', 'b', 'c']);
  });

  it('no toca la lista que recibe y no pierde ni repite ningún filtro', () => {
    const original = [...lista];
    const movida = moverFiltro(lista, 0, 2);

    expect(lista).toEqual(original);
    expect(movida).not.toBe(lista);
    expect([...movida].sort()).toEqual([...lista].sort());
  });

  it('con objetos, mueve el mismo objeto: lo marcado y el estado de cada filtro viajan con él', () => {
    const a = { campo: 'a' };
    const b = { campo: 'b' };

    const [primero, segundo] = moverFiltro([a, b], 1, 0);

    expect(primero).toBe(b);
    expect(segundo).toBe(a);
  });
});

describe('los bordes: el primero no sube y el último no baja', () => {
  it('con tres filtros', () => {
    expect(puedeMover('subir', 0, 3)).toBe(false);
    expect(puedeMover('subir', 1, 3)).toBe(true);
    expect(puedeMover('subir', 2, 3)).toBe(true);
    expect(puedeMover('bajar', 0, 3)).toBe(true);
    expect(puedeMover('bajar', 1, 3)).toBe(true);
    expect(puedeMover('bajar', 2, 3)).toBe(false);
  });

  it('con dos, cada uno puede ir solo hacia el otro', () => {
    expect(puedeMover('subir', 0, 2)).toBe(false);
    expect(puedeMover('bajar', 0, 2)).toBe(true);
    expect(puedeMover('subir', 1, 2)).toBe(true);
    expect(puedeMover('bajar', 1, 2)).toBe(false);
  });
});

describe('a qué botón va el foco tras mover', () => {
  it('al mismo botón de su fila nueva', () => {
    expect(botonConFoco('subir', 1, 4)).toBe('subir');
    expect(botonConFoco('bajar', 2, 4)).toBe('bajar');
  });

  it('si llegó al borde y ese botón quedó inactivo, al otro', () => {
    expect(botonConFoco('subir', 0, 4)).toBe('bajar');
    expect(botonConFoco('bajar', 3, 4)).toBe('subir');
  });

  it('con dos filtros, siempre queda el botón que sí funciona', () => {
    expect(botonConFoco('subir', 0, 2)).toBe('bajar');
    expect(botonConFoco('bajar', 1, 2)).toBe('subir');
  });
});

describe('dónde cae un arrastre', () => {
  // Four rows whose centres are at 10, 30, 50 and 70.
  const centros = [10, 30, 50, 70];

  it('antes de la primera fila cuyo centro queda debajo del puntero', () => {
    expect(destinoDeArrastre(centros, 25, 3)).toEqual({ antes: 1, destino: 1 });
    expect(destinoDeArrastre(centros, 5, 3)).toEqual({ antes: 0, destino: 0 });
  });

  it('pasado el último centro, al final', () => {
    expect(destinoDeArrastre(centros, 99, 0)).toEqual({ antes: 4, destino: 3 });
  });

  it('hacia abajo, el destino cuenta que la fila que se arrastra ya no está donde estaba', () => {
    expect(destinoDeArrastre(centros, 45, 0)).toEqual({ antes: 2, destino: 1 });
  });

  it('soltarla donde estaba, o justo debajo de sí misma, no mueve nada', () => {
    expect(destinoDeArrastre(centros, 12, 1).destino).toBe(1);
    expect(destinoDeArrastre(centros, 45, 2).destino).toBe(2);
  });

  it('el destino nunca sale de la lista', () => {
    for (const y of [-100, 0, 20, 40, 60, 80, 1000]) {
      for (let origen = 0; origen < centros.length; origen += 1) {
        const { destino } = destinoDeArrastre(centros, y, origen);
        expect(destino).toBeGreaterThanOrEqual(0);
        expect(destino).toBeLessThanOrEqual(centros.length - 1);
      }
    }
  });
});

describe('la posición que se dice', () => {
  it('cuenta desde 1', () => {
    expect(posicion(0)).toBe(1);
    expect(posicion(3)).toBe(4);
  });
});

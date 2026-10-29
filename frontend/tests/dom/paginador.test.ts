/**
 * The pager every paged table shares: the range it says, the buttons off at their edge, and that it only
 * exists when the rows do not fit one page.
 */
import { beforeEach, describe, expect, it } from 'vitest';

import { setLanguage } from '../../src/lib/i18n';
import { pintarPaginador } from '../../src/lib/paginacion';

function paginador(): HTMLElement {
  const raiz = document.createElement('div');
  raiz.className = 'pager';
  raiz.hidden = true;
  raiz.innerHTML =
    '<button type="button" data-page-prev>Anteriores</button>' +
    '<p data-page-range></p>' +
    '<button type="button" data-page-next>Siguientes</button>';
  document.body.append(raiz);
  return raiz;
}

const rango = (raiz: HTMLElement) => raiz.querySelector('[data-page-range]')!.textContent;
const anterior = (raiz: HTMLElement) => raiz.querySelector<HTMLButtonElement>('[data-page-prev]')!;
const siguiente = (raiz: HTMLElement) => raiz.querySelector<HTMLButtonElement>('[data-page-next]')!;

beforeEach(() => {
  document.body.replaceChildren();
  setLanguage('es');
});

describe('pintarPaginador: el rango', () => {
  it('dice desde–hasta de total, con el formato de los números del sitio', () => {
    const raiz = paginador();

    pintarPaginador(raiz, { desde: 51, hasta: 100, total: 3200 });

    expect(rango(raiz)).toBe('51–100 de 3,200');
    expect(raiz.hidden).toBe(false);
  });

  it('sigue el idioma activo', () => {
    const raiz = paginador();
    setLanguage('en');

    pintarPaginador(raiz, { desde: 1, hasta: 10, total: 25 });

    expect(rango(raiz)).toBe('1–10 of 25');
  });

  it('una página incompleta, la última, dice su hasta real', () => {
    const raiz = paginador();

    pintarPaginador(raiz, { desde: 21, hasta: 25, total: 25 });

    expect(rango(raiz)).toBe('21–25 de 25');
  });
});

describe('pintarPaginador: los bordes', () => {
  it('en la primera página, «Anteriores» está apagado y «Siguientes» no', () => {
    const raiz = paginador();

    pintarPaginador(raiz, { desde: 1, hasta: 10, total: 25 });

    expect(anterior(raiz).disabled).toBe(true);
    expect(siguiente(raiz).disabled).toBe(false);
  });

  it('en una página del medio, los dos botones están encendidos', () => {
    const raiz = paginador();

    pintarPaginador(raiz, { desde: 11, hasta: 20, total: 25 });

    expect(anterior(raiz).disabled).toBe(false);
    expect(siguiente(raiz).disabled).toBe(false);
  });

  it('en la última, «Siguientes» está apagado y «Anteriores» no', () => {
    const raiz = paginador();

    pintarPaginador(raiz, { desde: 21, hasta: 25, total: 25 });

    expect(anterior(raiz).disabled).toBe(false);
    expect(siguiente(raiz).disabled).toBe(true);
  });

  it('un botón apagado se vuelve a encender al volver a pintar', () => {
    const raiz = paginador();
    pintarPaginador(raiz, { desde: 1, hasta: 10, total: 25 });
    expect(anterior(raiz).disabled).toBe(true);

    pintarPaginador(raiz, { desde: 11, hasta: 20, total: 25 });

    expect(anterior(raiz).disabled).toBe(false);
  });
});

describe('pintarPaginador: una sola página', () => {
  it('con todas las filas en la primera página, se oculta', () => {
    const raiz = paginador();
    raiz.hidden = false;

    pintarPaginador(raiz, { desde: 1, hasta: 7, total: 7 });

    expect(raiz.hidden).toBe(true);
  });

  it('justo una página llena también se oculta', () => {
    const raiz = paginador();
    raiz.hidden = false;

    pintarPaginador(raiz, { desde: 1, hasta: 10, total: 10 });

    expect(raiz.hidden).toBe(true);
  });

  it('sin filas, se oculta', () => {
    const raiz = paginador();
    raiz.hidden = false;

    pintarPaginador(raiz, { desde: 0, hasta: 0, total: 0 });

    expect(raiz.hidden).toBe(true);
  });

  it('sin rango (una página vacía), se oculta', () => {
    const raiz = paginador();
    raiz.hidden = false;

    pintarPaginador(raiz, null);

    expect(raiz.hidden).toBe(true);
  });

  it('si se oculta y luego hay más filas, vuelve a aparecer', () => {
    const raiz = paginador();
    pintarPaginador(raiz, { desde: 1, hasta: 7, total: 7 });
    expect(raiz.hidden).toBe(true);

    pintarPaginador(raiz, { desde: 1, hasta: 10, total: 17 });

    expect(raiz.hidden).toBe(false);
    expect(rango(raiz)).toBe('1–10 de 17');
  });
});

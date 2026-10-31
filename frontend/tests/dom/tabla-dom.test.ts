/**
 * The pieces of a table that the page scripts build by hand: every variant the screens used before they
 * shared them (the campaign's cells that name their column, the follow-up's muted figure, a row header).
 */
import { describe, expect, it } from 'vitest';

import { celda, celdaDeFila, cifra, tabla, vacio } from '../../src/lib/tabla-dom';

describe('celda', () => {
  it('una celda de datos: su texto, sin clase ni etiqueta de columna si no se piden', () => {
    const nodo = celda('td', '900000001');

    expect(nodo.tagName).toBe('TD');
    expect(nodo.textContent).toBe('900000001');
    expect(nodo.hasAttribute('class')).toBe(false);
    expect(nodo.hasAttribute('data-etiqueta')).toBe(false);
  });

  it('con clase', () => {
    expect(celda('td', '12', 'num').className).toBe('num');
  });

  it('con la etiqueta de la columna, para cuando la tabla se apila', () => {
    const nodo = celda('td', '12', 'num', 'Productos');

    expect(nodo.dataset.etiqueta).toBe('Productos');
    expect(nodo.className).toBe('num');
  });

  it('un th suelto es un encabezado de columna: no lleva scope', () => {
    const nodo = celda('th', 'Pagaré', 'segmentos__grupo');

    expect(nodo.tagName).toBe('TH');
    expect(nodo.hasAttribute('scope')).toBe(false);
  });

  it('un texto vacío deja la celda sin hijos (el que la llama le pone el contenido)', () => {
    expect(celda('td', '', 'mono', 'Origen').childNodes).toHaveLength(0);
  });
});

describe('celdaDeFila', () => {
  it('es un th que encabeza su fila', () => {
    const nodo = celdaDeFila('Productos', 'num', 'Grupo');

    expect(nodo.tagName).toBe('TH');
    expect(nodo.scope).toBe('row');
    expect(nodo.textContent).toBe('Productos');
    expect(nodo.className).toBe('num');
    expect(nodo.dataset.etiqueta).toBe('Grupo');
  });
});

describe('vacio', () => {
  it('es el párrafo .empty con su texto', () => {
    const nodo = vacio('Sin filas');

    expect(nodo.tagName).toBe('P');
    expect(nodo.className).toBe('empty');
    expect(nodo.textContent).toBe('Sin filas');
  });
});

describe('cifra', () => {
  it('con icono, la etiqueta lo lleva antes de su texto y el texto sigue siendo el mismo', () => {
    const icono = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    icono.setAttribute('aria-hidden', 'true');
    const etiqueta = cifra('Excluidos', '20', undefined, false, icono).querySelector('dt')!;

    expect(etiqueta.firstElementChild).toBe(icono);
    expect(etiqueta.textContent).toBe('Excluidos');
    expect(etiqueta.querySelectorAll('svg')).toHaveLength(1);
  });

  it('sin icono, la etiqueta es solo su texto, como antes', () => {
    const etiqueta = cifra('Excluidos', '20').querySelector('dt')!;

    expect(etiqueta.children).toHaveLength(0);
    expect(etiqueta.textContent).toBe('Excluidos');
  });

  it('etiqueta y valor, el valor con el estilo de las cifras', () => {
    const nodo = cifra('Cargados', '982');

    expect(nodo.className).toBe('stat');
    expect(nodo.querySelector('dt')!.className).toBe('stat__label');
    expect(nodo.querySelector('dt')!.textContent).toBe('Cargados');
    expect(nodo.querySelector('dd')!.className).toBe('stat__value');
    expect(nodo.querySelector('dd')!.textContent).toBe('982');
    expect(nodo.querySelectorAll('dd')).toHaveLength(1);
  });

  it('con pista, la pista va en un segundo dd', () => {
    const nodo = cifra('Costo', 'S/ 19.04', '952 × S/ 0.02');
    const dds = nodo.querySelectorAll('dd');

    expect(dds).toHaveLength(2);
    expect(dds[1].className).toBe('field__hint');
    expect(dds[1].textContent).toBe('952 × S/ 0.02');
  });

  it('apagada: el valor se lee en gris, como texto y no como monto', () => {
    const nodo = cifra('Costo real', 'Pendiente del reporte', undefined, true);

    expect(nodo.querySelector('dd')!.className).toBe('stat__value muted');
  });

  it('una pista vacía no agrega nada', () => {
    expect(cifra('A', '1', '').querySelectorAll('dd')).toHaveLength(1);
  });
});

describe('tabla', () => {
  const columnas: Array<[string, boolean]> = [
    ['Id', true],
    ['Descripción', false],
  ];

  it('un contenedor con scroll, una tabla densa y su cuerpo vacío', () => {
    const { envoltorio, cuerpo } = tabla('mm-campanas__tabla', columnas);

    expect(envoltorio.className).toBe('table-scroll');
    const nodo = envoltorio.querySelector('table')!;
    expect(nodo.className).toBe('table mm-campanas__tabla');
    expect(cuerpo.tagName).toBe('TBODY');
    expect(cuerpo.children).toHaveLength(0);
    expect(nodo.contains(cuerpo)).toBe(true);
  });

  it('apilable: la clase va entre `table` y la de la tabla, como antes en la campaña', () => {
    const { envoltorio } = tabla('mm-muestra__tabla', columnas, { apilable: true });

    expect(envoltorio.querySelector('table')!.className).toBe('table table--apilable mm-muestra__tabla');
  });

  it('sin apilable no se apila', () => {
    expect(tabla('x', columnas, { apilable: false }).envoltorio.querySelector('table')!.className).toBe('table x');
  });

  it('las cabeceras son th de columna, con el texto recibido y .num en las numéricas', () => {
    const { envoltorio } = tabla('x', columnas);
    const cabeceras = [...envoltorio.querySelectorAll<HTMLTableCellElement>('thead th')];

    expect(cabeceras.map((th) => th.textContent)).toEqual(['Id', 'Descripción']);
    expect(cabeceras.map((th) => th.scope)).toEqual(['col', 'col']);
    expect(cabeceras.map((th) => th.className)).toEqual(['num', '']);
  });
});

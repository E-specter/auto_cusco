/**
 * The DOM helpers the pages share: the busy button and the wrappable identifier.
 */
import { afterEach, describe, expect, it } from 'vitest';

import { $, appendBreakable, ocupado } from '../../src/lib/dom';

afterEach(() => {
  document.body.innerHTML = '';
});

describe('$', () => {
  it('devuelve el elemento que coincide con el selector', () => {
    document.body.innerHTML = '<p data-x>hola</p>';
    expect($<HTMLElement>('[data-x]').textContent).toBe('hola');
  });
});

describe('ocupado', () => {
  it('marca el botón como cargando y lo desactiva, y lo devuelve a su estado', () => {
    const boton = document.createElement('button');

    ocupado(boton, true);
    expect(boton.dataset.loading).toBe('true');
    expect(boton.disabled).toBe(true);

    ocupado(boton, false);
    expect(boton.dataset.loading).toBe('false');
    expect(boton.disabled).toBe(false);
  });
});

describe('appendBreakable', () => {
  it('deja un <wbr> tras cada guion bajo, menos al final', () => {
    const celda = document.createElement('td');

    appendBreakable(celda, 'columna_faltante_x');

    expect(celda.innerHTML).toBe('columna_<wbr>faltante_<wbr>x');
    expect(celda.textContent).toBe('columna_faltante_x');
  });

  it('un identificador sin guion bajo queda tal cual, sin <wbr>', () => {
    const celda = document.createElement('td');

    appendBreakable(celda, 'dni');

    expect(celda.innerHTML).toBe('dni');
  });

  it('un guion bajo final conserva el guion bajo y no deja un <wbr> sobrante', () => {
    const celda = document.createElement('td');

    appendBreakable(celda, 'ad_');

    expect(celda.innerHTML).toBe('ad_<wbr>');
  });
});

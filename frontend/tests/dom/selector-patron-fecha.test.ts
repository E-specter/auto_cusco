/**
 * The selector of a parameter with known values: a date pattern, or a file
 * option of «Generar carga» whose suggested values come from the backend.
 * A value that does not read on its own (a tab) shows its label instead.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';

import { crearSelectorPatronFecha, textoOpcion } from '../../src/scripts/selector-patron-fecha';

afterEach(() => {
  document.body.innerHTML = '';
});

describe('texto de cada opción', () => {
  it('muestra el valor y su ejemplo, como el patrón de fecha', () => {
    expect(textoOpcion({ valor: 'dd/mm/aaaa', ejemplo: '05/10/2026' })).toBe('dd/mm/aaaa — 05/10/2026');
    expect(textoOpcion({ valor: 'utf-8', ejemplo: null })).toBe('utf-8');
  });

  it('con etiqueta, la nombra y deja el carácter al lado cuando se ve', () => {
    expect(textoOpcion({ valor: ';', ejemplo: null, etiqueta: 'punto y coma' })).toBe('punto y coma (;)');
  });

  it('un carácter en blanco nunca se muestra: solo su etiqueta', () => {
    expect(textoOpcion({ valor: '\t', ejemplo: null, etiqueta: 'tabulación' })).toBe('tabulación');
  });
});

describe('selector con valores sugeridos', () => {
  const delimitadores = [
    { valor: ',', ejemplo: null, etiqueta: 'coma' },
    { valor: '\t', ejemplo: null, etiqueta: 'tabulación' },
  ];

  it('elige el valor dado y permite otro con «Personalizado»', () => {
    const onCambio = vi.fn();
    const raiz = crearSelectorPatronFecha({
      id: 'delimitador',
      etiqueta: 'Delimitador',
      opciones: delimitadores,
      cerradas: false,
      marcas: [],
      valor: '\t',
      onCambio,
    });
    document.body.append(raiz);
    const select = raiz.querySelector('select')!;

    expect([...select.options].map((o) => o.textContent)).toEqual(['coma (,)', 'tabulación', 'Personalizado']);
    expect(select.value).toBe('\t');
    expect(raiz.querySelector<HTMLElement>('.selector-patron__propio')!.hidden).toBe(true);

    select.value = '__propio__';
    select.dispatchEvent(new Event('change'));
    const propio = raiz.querySelector<HTMLInputElement>('#delimitador-propio')!;
    expect(raiz.querySelector<HTMLElement>('.selector-patron__propio')!.hidden).toBe(false);
    propio.value = '~';
    propio.dispatchEvent(new Event('input'));
    expect(onCambio).toHaveBeenLastCalledWith('~');
  });

  it('un valor fuera de los sugeridos abre «Personalizado» con ese valor', () => {
    const raiz = crearSelectorPatronFecha({
      id: 'delimitador',
      etiqueta: 'Delimitador',
      opciones: delimitadores,
      cerradas: false,
      marcas: [],
      valor: '~',
      onCambio: () => undefined,
    });
    expect(raiz.querySelector('select')!.value).toBe('__propio__');
    expect(raiz.querySelector<HTMLInputElement>('#delimitador-propio')!.value).toBe('~');
  });
});

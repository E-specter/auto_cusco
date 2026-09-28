/**
 * Scrolling table containers must be reachable by keyboard while they
 * overflow (WCAG 2.1.1), and only then: a tab stop on a table that fits is a
 * detour. jsdom has no layout, so overflow is stubbed on the element.
 */
import { afterEach, describe, expect, it } from 'vitest';

import { actualizarDesplazable, observarDesplazables } from '../../src/lib/desplazables';

function medidas(el: HTMLElement, scroll: number, cliente: number): void {
  Object.defineProperty(el, 'scrollWidth', { configurable: true, value: scroll });
  Object.defineProperty(el, 'clientWidth', { configurable: true, value: cliente });
  Object.defineProperty(el, 'scrollHeight', { configurable: true, value: 0 });
  Object.defineProperty(el, 'clientHeight', { configurable: true, value: 0 });
}

function contenedor(html = '<table><tr><td>x</td></tr></table>'): HTMLElement {
  const div = document.createElement('div');
  div.className = 'table-scroll';
  div.innerHTML = html;
  return div;
}

afterEach(() => {
  document.body.innerHTML = '';
});

describe('contenedor que desborda', () => {
  it('se vuelve una región enfocable', () => {
    const el = contenedor();
    document.body.append(el);
    medidas(el, 900, 360);

    actualizarDesplazable(el);

    expect(el.tabIndex).toBe(0);
    expect(el.getAttribute('role')).toBe('region');
    expect(el.getAttribute('aria-label')).toBeTruthy();
  });

  it('toma el nombre del título de su panel, el mismo que se ve', () => {
    document.body.innerHTML = `
      <section aria-labelledby="titulo"><h2 id="titulo">Incidencias</h2></section>`;
    const el = contenedor();
    document.querySelector('section')!.append(el);
    medidas(el, 900, 360);

    actualizarDesplazable(el);

    expect(el.getAttribute('aria-labelledby')).toBe('titulo');
    expect(el.hasAttribute('aria-label')).toBe(false);
  });

  it('prefiere la leyenda de la propia tabla', () => {
    const el = contenedor('<table><caption id="ley">Supervisores</caption><tr><td>x</td></tr></table>');
    document.body.append(el);
    medidas(el, 900, 360);

    actualizarDesplazable(el);

    expect(el.getAttribute('aria-labelledby')).toBe('ley');
  });
});

describe('contenedor que cabe', () => {
  it('no agrega una parada de tabulación inútil', () => {
    const el = contenedor();
    document.body.append(el);
    medidas(el, 360, 360);

    actualizarDesplazable(el);

    expect(el.hasAttribute('tabindex')).toBe(false);
  });

  it('deja de ser enfocable cuando vuelve a caber', () => {
    const el = contenedor();
    document.body.append(el);
    medidas(el, 900, 360);
    actualizarDesplazable(el);

    medidas(el, 360, 1200);
    actualizarDesplazable(el);

    expect(el.hasAttribute('tabindex')).toBe(false);
  });

  it('respeta el tabindex que puso la página', () => {
    const el = contenedor();
    el.tabIndex = 0;
    document.body.append(el);
    medidas(el, 360, 360);

    actualizarDesplazable(el);

    expect(el.tabIndex).toBe(0);
  });
});

describe('tablas que construye el script después', () => {
  it('también se atienden', async () => {
    const detener = observarDesplazables(document);
    const el = contenedor();
    medidas(el, 900, 360);

    document.body.append(el);
    await new Promise((listo) => setTimeout(listo, 0));

    expect(el.tabIndex).toBe(0);
    detener();
  });
});

/**
 * The description of the MOWA MES campaign (T-MM-F9; RF-MM-04), end to end against an intercepted API:
 * the 100-character limit with its counter, and the «Copiar» button that copies what will be
 * registered, with the classic fallback when the browser has no async clipboard.
 *
 * What costs when it is wrong: a counter that disagrees with what the field accepts (an emoji), a copy
 * that keeps the spaces at the ends or ignores the suggestion, an error nobody reads, or a failed copy
 * that leaves nothing selected to copy by hand. Plain http outside localhost has no `navigator.clipboard`,
 * so the fallback is the real path there. Every text is synthetic.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page, type Route } from '@playwright/test';

import type { Campos, SeleccionGuardada, Version } from '../src/lib/api';
import type { PeticionCampanaEntrada } from '../src/lib/api-mowa-mes';
import { camposSinteticos, seleccionGuardada, version } from './api-falsa';
import {
  acortarDescripcion,
  apiMowaMes,
  montarApiMowaMes,
  previsualizacionCampanaSintetica,
  type ApiFalsaMowaMes,
} from './api-falsa-mowa-mes';

const RUTA = '/mowa-mes/campana';
const SUGERIDA = 'CajaCusco 9 <= dias atraso <= 30';
const COPIADA = 'Descripción copiada.';
const FALLO = 'No se pudo copiar. El texto quedó seleccionado: cópialo con Ctrl+C.';
const FALLO_VACIO = 'No se pudo copiar la descripción sugerida. Escríbela en el campo para poder seleccionarla.';
const PEGADO_CORTADO = 'Se pegó solo lo que cabe: los primeros 100 caracteres.';

test.use({ timezoneId: 'America/Lima', reducedMotion: 'reduce' });

const json = (route: Route, estado: number, cuerpo: unknown) =>
  route.fulfill({ status: estado, contentType: 'application/json', body: JSON.stringify(cuerpo) });

/** The compact selector's own calls, layered over the module's mock (as in mowa-mes-campana.spec.ts). */
async function montarSeleccion(page: Page): Promise<void> {
  const versiones: Version[] = [version({ fecha_corte: '2026-09-13', vigente: true })];
  const campos: Campos = camposSinteticos();
  const selecciones: SeleccionGuardada[] = [seleccionGuardada({ id: 1, nombre: 'Preventiva top 1000', cantidad: 1000 })];
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const ruta = url.pathname.replace(/^\/api/, '');
    const metodo = route.request().method();
    if (ruta === '/cargas' && metodo === 'GET') return json(route, 200, versiones);
    if (ruta === '/cartera/campos') return json(route, 200, campos);
    if (ruta === '/selecciones' && metodo === 'GET') return json(route, 200, selecciones);
    return route.fallback();
  });
}

function entradaMinima(): PeticionCampanaEntrada {
  return {
    fecha_corte: '2026-09-13',
    filtros: [],
    cantidad: 1000,
    seleccion_id: 1,
    tipo_carga: 'masiva',
    salida: 'numero_largo',
    herramientas: { keyword: false, respuesta_automatica: false, blacklist_indecopi: false, speech_optimizado: false },
    programacion: 'hora_determinada',
    envios: ['2026-09-14T09:00:00-05:00'],
  };
}

interface Espias {
  /** `navigator.clipboard`: untouched, missing (plain http) or one whose `writeText` rejects. */
  clipboard?: 'normal' | 'ausente' | 'rechaza';
  /** `document.execCommand('copy')`: answers true, false or throws; every call records what was selected. */
  exec?: 'verdadero' | 'falso' | 'lanza';
}

/** Spies installed before the page loads, so the script of the page sees them from its first line. */
async function instalarEspias(page: Page, espias: Espias): Promise<void> {
  await page.addInitScript((cfg) => {
    const w = window as unknown as { __exec: string[] };
    w.__exec = [];
    if (cfg.exec) {
      const original = document.execCommand.bind(document);
      document.execCommand = (orden: string, ...resto: [boolean?, string?]) => {
        if (orden !== 'copy') return original(orden, ...resto);
        // What is selected at this moment, in whichever textarea holds a selection (the field or the temporary one).
        const texto = [...document.querySelectorAll('textarea')]
          .map((t) => t.value.slice(t.selectionStart, t.selectionEnd))
          .find(Boolean);
        w.__exec.push(texto ?? '');
        if (cfg.exec === 'lanza') throw new Error('execCommand no disponible');
        return cfg.exec === 'verdadero';
      };
    }
    if (cfg.clipboard === 'ausente') {
      Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true });
    } else if (cfg.clipboard === 'rechaza') {
      Object.defineProperty(navigator, 'clipboard', {
        value: { writeText: () => Promise.reject(new DOMException('negado', 'NotAllowedError')) },
        configurable: true,
      });
    }
  }, espias);
}

async function abrir(page: Page, api: ApiFalsaMowaMes = apiMowaMes(), idioma: 'es' | 'en' = 'es', tema = 'light') {
  await page.addInitScript(
    ([lenguaje, elegido]) => {
      try {
        localStorage.setItem('app:appearance', JSON.stringify({ language: lenguaje, theme: elegido }));
      } catch {
        /* storage blocked: the page keeps its default */
      }
    },
    [idioma, tema],
  );
  await montarApiMowaMes(page, api);
  await montarSeleccion(page);
  await page.goto(RUTA);
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  return api;
}

const campo = (page: Page) => page.locator('#mm-descripcion');
const contador = (page: Page) => page.locator('[data-descripcion-contador]');
const estado = (page: Page) => page.locator('[data-descripcion-estado]');
const copiar = (page: Page, nombre = 'Copiar descripción') => page.getByRole('button', { name: nombre });
const copiado = (page: Page) => page.evaluate(() => (window as unknown as { __exec: string[] }).__exec);

/** Load the saved selection and wait for the preview to fill the field with the suggestion. */
async function conSugerida(page: Page, etiqueta = 'Selección guardada'): Promise<void> {
  await page.getByLabel(etiqueta).selectOption({ label: 'Preventiva top 1000' });
  await expect(campo(page)).not.toHaveValue('');
}

async function permisosDePortapapeles(page: Page): Promise<void> {
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write']);
}

const leerPortapapeles = (page: Page) => page.evaluate(() => navigator.clipboard.readText());

test.describe('el tope de 100 y el contador', () => {
  test('el campo no deja escribir más de 100, y el contador lo dice con tono de advertencia solo al llegar', async ({ page }) => {
    await abrir(page);
    await conSugerida(page);
    await expect(campo(page)).toHaveAttribute('maxlength', '100');

    await campo(page).fill('');
    await campo(page).pressSequentially('a'.repeat(105));

    await expect(campo(page)).toHaveValue('a'.repeat(100));
    await expect(contador(page)).toHaveText('100/100');
    await expect(contador(page)).toHaveAttribute('data-tope', 'true');
    await campo(page).press('Backspace');
    await expect(contador(page)).toHaveText('99/100');
    await expect(contador(page)).toHaveAttribute('data-tope', 'false');
  });

  test('cuenta como el navegador: un emoji ocupa 2, y el campo se llena cuando el contador dice 100', async ({ page }) => {
    await abrir(page);
    await conSugerida(page);
    await campo(page).fill('');

    await campo(page).pressSequentially(`${'a'.repeat(98)}😀`);
    await expect(contador(page)).toHaveText('100/100');
    await campo(page).pressSequentially('b');

    // Ni el contador marcó 99 ni el campo aceptó la «b»: miden igual.
    await expect(contador(page)).toHaveText('100/100');
    expect(await campo(page).evaluate((e: HTMLTextAreaElement) => e.value.length)).toBe(100);
    await expect(campo(page)).not.toHaveValue(/b$/);
  });

  test('la sugerida llena el campo sin que se escriba nada, y el contador la sigue', async ({ page }) => {
    await abrir(page);
    await expect(contador(page)).toHaveText('0/100');

    await conSugerida(page);

    await expect(campo(page)).toHaveValue(SUGERIDA);
    await expect(contador(page)).toHaveText(`${SUGERIDA.length}/100`);
  });

  test('una sugerida larga, ya acortada como el backend, cabe y el contador la cuenta', async ({ page }) => {
    const api = apiMowaMes();
    const filtros = Array.from({ length: 9 }, (_, i) => `filtro numero ${i + 1} de prueba`);
    const larga = acortarDescripcion('CajaCusco', filtros);
    api.respuestas.previsualizarCampana = [
      { estado: 200, cuerpo: previsualizacionCampanaSintetica(entradaMinima(), { descripcion_sugerida: larga, descripcion: larga }) },
    ];
    await abrir(page, api);

    await conSugerida(page);

    await expect(campo(page)).toHaveValue(larga);
    expect(larga.length).toBeLessThanOrEqual(100);
    expect(larga.endsWith('...')).toBe(true);
    await expect(contador(page)).toHaveText(`${larga.length}/100`);
  });

  test('un pegado largo lo corta el navegador y se avisa una sola vez, con la cifra', async ({ page }) => {
    await permisosDePortapapeles(page);
    await abrir(page);
    await conSugerida(page);
    await campo(page).fill('');
    await page.evaluate(() => navigator.clipboard.writeText('x'.repeat(150)));

    await campo(page).focus();
    await page.keyboard.press('ControlOrMeta+V');

    await expect(campo(page)).toHaveValue('x'.repeat(100));
    await expect(contador(page)).toHaveText('100/100');
    await expect(estado(page)).toHaveText(PEGADO_CORTADO);
  });

  test('un pegado que cabe no dice nada', async ({ page }) => {
    await permisosDePortapapeles(page);
    await abrir(page);
    await conSugerida(page);
    await campo(page).fill('');
    await page.evaluate(() => navigator.clipboard.writeText('abc'));

    await campo(page).focus();
    await page.keyboard.press('ControlOrMeta+V');

    await expect(campo(page)).toHaveValue('abc');
    await expect(estado(page)).toHaveText('');
  });
});

test.describe('«Copiar» con el portapapeles del navegador', () => {
  test('copia lo que se registrará: el texto sin los espacios de los extremos, y avisa', async ({ page }) => {
    await permisosDePortapapeles(page);
    await instalarEspias(page, { clipboard: 'normal', exec: 'verdadero' });
    await abrir(page);
    await conSugerida(page);
    await campo(page).fill('   CajaCusco 9 a 30   ');

    await copiar(page).click();

    expect(await leerPortapapeles(page)).toBe('CajaCusco 9 a 30');
    await expect(estado(page)).toHaveText(COPIADA);
    await expect(copiar(page)).toBeFocused();
    // El portapapeles funcionó: no se pasó al respaldo.
    expect(await copiado(page)).toEqual([]);
    // El aviso se lee con lector de pantalla: está en una región de estado, no en un párrafo suelto.
    await expect(estado(page)).toHaveAttribute('role', 'status');
  });

  test('la región de estado está siempre en el árbol de accesibilidad, también vacía', async ({ page }) => {
    await permisosDePortapapeles(page);
    await abrir(page);
    await conSugerida(page);
    await expect(estado(page)).toHaveText('');
    const region = page.getByRole('status').and(estado(page));

    // Vacía: ni display:none ni fuera del árbol, que es donde la leen NVDA y JAWS cuando cambia.
    expect(await estado(page).evaluate((e) => getComputedStyle(e).display)).not.toBe('none');
    await expect(region).toHaveCount(1);

    await copiar(page).click();
    await expect(estado(page)).toHaveText(COPIADA);
    await expect(region).toHaveCount(1);

    // De nuevo vacía, tras editar el texto.
    await campo(page).pressSequentially('!');
    await expect(estado(page)).toHaveText('');
    expect(await estado(page).evaluate((e) => getComputedStyle(e).display)).not.toBe('none');
    await expect(region).toHaveCount(1);
  });

  test('al copiar dos veces el aviso se repite: la región se vacía antes de escribir el mismo texto', async ({ page }) => {
    await permisosDePortapapeles(page);
    await abrir(page);
    await conSugerida(page);
    // Every state the region goes through, to see the emptying between the two identical messages.
    await page.evaluate(() => {
      const w = window as unknown as { __estados: string[] };
      w.__estados = [];
      const region = document.querySelector('[data-descripcion-estado]')!;
      new MutationObserver(() => w.__estados.push(region.textContent ?? '')).observe(region, {
        childList: true,
        characterData: true,
        subtree: true,
      });
    });

    await copiar(page).click();
    await expect(estado(page)).toHaveText(COPIADA);
    await copiar(page).click();
    await expect.poll(() => page.evaluate(() => (window as unknown as { __estados: string[] }).__estados.length)).toBeGreaterThanOrEqual(3);

    const estados = await page.evaluate(() => (window as unknown as { __estados: string[] }).__estados);
    expect(estados.filter((e) => e !== '')).toEqual([COPIADA, COPIADA]);
    // Entre los dos avisos iguales hubo un momento vacío: eso es lo que un lector de pantalla vuelve a leer.
    const entre = estados.slice(estados.indexOf(COPIADA) + 1, estados.lastIndexOf(COPIADA));
    expect(entre).toContain('');
    await expect(estado(page)).toHaveText(COPIADA);
  });

  test('con el campo vacío copia la sugerida de la última previsualización', async ({ page }) => {
    await permisosDePortapapeles(page);
    await abrir(page);
    await conSugerida(page);
    await campo(page).fill('');
    await expect(contador(page)).toHaveText('0/100');

    await copiar(page).click();

    expect(await leerPortapapeles(page)).toBe(SUGERIDA);
    await expect(estado(page)).toHaveText(COPIADA);
  });

  test('un campo con solo espacios cuenta como vacío', async ({ page }) => {
    await permisosDePortapapeles(page);
    await abrir(page);
    await conSugerida(page);
    await campo(page).fill('     ');

    await copiar(page).click();

    expect(await leerPortapapeles(page)).toBe(SUGERIDA);
  });

  test('sin nada que copiar queda inactivo, sigue en el orden de tabulación y no hace nada', async ({ page }) => {
    // The preview answers with no suggestion and the field is empty: there is nothing to copy.
    const api = apiMowaMes();
    api.respuestas.previsualizarCampana = [
      { estado: 200, cuerpo: previsualizacionCampanaSintetica(entradaMinima(), { descripcion_sugerida: '', descripcion: '' }) },
    ];
    await abrir(page, api);
    await page.getByLabel('Selección guardada').selectOption({ label: 'Preventiva top 1000' });
    await expect.poll(() => api.pedidos.some((p) => p.ruta === '/mowa-mes/campanas/previsualizacion')).toBe(true);
    await expect(campo(page)).toHaveValue('');
    await expect(copiar(page)).toHaveAttribute('aria-disabled', 'true');
    // aria-disabled, no disabled: se llega con Tab y se descubre.
    await expect(copiar(page)).not.toHaveAttribute('disabled', /.*/);
    await campo(page).focus();
    await page.keyboard.press('Tab');
    await expect(copiar(page)).toBeFocused();

    await page.keyboard.press('Enter');

    await expect(estado(page)).toHaveText('');
  });

  test('el botón sigue al campo: se activa al escribir y vuelve a quedar inactivo al vaciarlo', async ({ page }) => {
    const api = apiMowaMes();
    api.respuestas.previsualizarCampana = [
      { estado: 200, cuerpo: previsualizacionCampanaSintetica(entradaMinima(), { descripcion_sugerida: '', descripcion: '' }) },
    ];
    await abrir(page, api);
    await page.getByLabel('Selección guardada').selectOption({ label: 'Preventiva top 1000' });
    await expect(copiar(page)).toHaveAttribute('aria-disabled', 'true');

    await campo(page).fill('CajaCusco');
    await expect(copiar(page)).toHaveAttribute('aria-disabled', 'false');

    await campo(page).fill('   ');
    await expect(copiar(page)).toHaveAttribute('aria-disabled', 'true');
  });

  test('al cargar la sugerida el botón se activa, sin tocar el campo', async ({ page }) => {
    await abrir(page);

    await conSugerida(page);

    await expect(copiar(page)).toHaveAttribute('aria-disabled', 'false');
  });
});

test.describe('«Copiar» cuando el navegador no deja (respaldo clásico)', () => {
  const SIN_PORTAPAPELES: Array<[string, Espias]> = [
    ['sin navigator.clipboard (página en http fuera de localhost)', { clipboard: 'ausente', exec: 'verdadero' }],
    ['con writeText que rechaza', { clipboard: 'rechaza', exec: 'verdadero' }],
  ];

  for (const [titulo, espias] of SIN_PORTAPAPELES) {
    test(`${titulo}: copia con execCommand el texto correcto y avisa`, async ({ page }) => {
      await instalarEspias(page, espias);
      await abrir(page);
      await conSugerida(page);
      await campo(page).fill('  CajaCusco 9 a 30  ');

      await copiar(page).click();

      await expect(estado(page)).toHaveText(COPIADA);
      // Lo que estaba seleccionado cuando se llamó a execCommand: la parte sin espacios, no el campo entero.
      expect(await copiado(page)).toEqual(['CajaCusco 9 a 30']);
      await expect(copiar(page)).toBeFocused();
    });
  }

  test('con el campo vacío copia la sugerida desde un textarea temporal, que no queda en la página', async ({ page }) => {
    await instalarEspias(page, { clipboard: 'ausente', exec: 'verdadero' });
    await abrir(page);
    await conSugerida(page);
    await campo(page).fill('');

    await copiar(page).click();

    await expect(estado(page)).toHaveText(COPIADA);
    expect(await copiado(page)).toEqual([SUGERIDA]);
    await expect(page.locator('textarea[aria-hidden="true"]')).toHaveCount(0);
    await expect(copiar(page)).toBeFocused();
  });

  test('si execCommand dice que no, sale el aviso de error y la parte sin espacios queda seleccionada', async ({ page }) => {
    await instalarEspias(page, { clipboard: 'ausente', exec: 'falso' });
    await abrir(page);
    await conSugerida(page);
    await campo(page).fill('  CajaCusco 9 a 30  ');

    await copiar(page).click();

    await expect(estado(page)).toHaveText(FALLO);
    await expect(campo(page)).toBeFocused();
    const seleccion = await campo(page).evaluate((e: HTMLTextAreaElement) => [e.selectionStart, e.selectionEnd]);
    expect(seleccion).toEqual([2, 2 + 'CajaCusco 9 a 30'.length]);
  });

  test('si execCommand lanza, es el mismo aviso y el mismo texto seleccionado', async ({ page }) => {
    await instalarEspias(page, { clipboard: 'rechaza', exec: 'lanza' });
    await abrir(page);
    await conSugerida(page);
    await campo(page).fill('CajaCusco 9 a 30');

    await copiar(page).click();

    await expect(estado(page)).toHaveText(FALLO);
    const seleccion = await campo(page).evaluate((e: HTMLTextAreaElement) => [e.selectionStart, e.selectionEnd]);
    expect(seleccion).toEqual([0, 'CajaCusco 9 a 30'.length]);
  });

  test('con el campo vacío y sin poder copiar, lo dice y el foco vuelve al botón', async ({ page }) => {
    await instalarEspias(page, { clipboard: 'ausente', exec: 'falso' });
    await abrir(page);
    await conSugerida(page);
    await campo(page).fill('');

    await copiar(page).click();

    await expect(estado(page)).toHaveText(FALLO_VACIO);
    await expect(copiar(page)).toBeFocused();
    await expect(page.locator('textarea[aria-hidden="true"]')).toHaveCount(0);
  });

  test('editar el texto borra el aviso viejo', async ({ page }) => {
    await instalarEspias(page, { clipboard: 'ausente', exec: 'falso' });
    await abrir(page);
    await conSugerida(page);
    await campo(page).fill('CajaCusco 9 a 30');
    await copiar(page).click();
    await expect(estado(page)).toHaveText(FALLO);

    await campo(page).pressSequentially('!');

    await expect(estado(page)).toHaveText('');
  });
});

test.describe('teclado, foco y anchos', () => {
  test('Tab lleva del campo al botón, y Enter y Espacio copian', async ({ page }) => {
    await permisosDePortapapeles(page);
    await abrir(page);
    await conSugerida(page);
    await campo(page).fill('CajaCusco 9 a 30');
    await campo(page).focus();

    await page.keyboard.press('Tab');
    await expect(copiar(page)).toBeFocused();

    await page.keyboard.press('Enter');
    await expect(estado(page)).toHaveText(COPIADA);
    expect(await leerPortapapeles(page)).toBe('CajaCusco 9 a 30');

    await campo(page).fill('Otro texto');
    await copiar(page).focus();
    await page.keyboard.press('Space');
    await expect.poll(() => leerPortapapeles(page)).toBe('Otro texto');
    await expect(copiar(page)).toBeFocused();
  });

  test('en inglés, el botón, el aviso y el error están traducidos', async ({ page }) => {
    await instalarEspias(page, { clipboard: 'ausente', exec: 'verdadero' });
    await abrir(page, apiMowaMes(), 'en');
    await conSugerida(page, 'Saved selection');
    await campo(page).fill('CajaCusco 9 a 30');

    await copiar(page, 'Copy description').click();
    await expect(estado(page)).toHaveText('Description copied.');
    await expect(copiar(page, 'Copy description')).toContainText('Copy');
    await expect(page.locator('body')).not.toContainText('mowaMes.');
  });

  test('en inglés, el error de copia y el pegado cortado también', async ({ page }) => {
    await permisosDePortapapeles(page);
    await instalarEspias(page, { clipboard: 'normal', exec: 'falso' });
    await abrir(page, apiMowaMes(), 'en');
    await conSugerida(page, 'Saved selection');
    await campo(page).fill('');
    await page.evaluate(() => navigator.clipboard.writeText('x'.repeat(150)));
    await campo(page).focus();
    await page.keyboard.press('ControlOrMeta+V');
    await expect(estado(page)).toHaveText('Only what fits was pasted: the first 100 characters.');
  });

  test('en inglés, si no se puede copiar, el error dice qué hacer', async ({ page }) => {
    await instalarEspias(page, { clipboard: 'ausente', exec: 'falso' });
    await abrir(page, apiMowaMes(), 'en');
    await conSugerida(page, 'Saved selection');
    await campo(page).fill('CajaCusco 9 a 30');

    await copiar(page, 'Copy description').click();

    await expect(estado(page)).toHaveText('Could not copy. The text is selected: copy it with Ctrl+C.');
  });

  test('a 360 px el botón y el campo caben sin desbordar la página', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    await abrir(page);
    await conSugerida(page);

    const desborde = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(desborde).toBeLessThanOrEqual(0);
    const caja = await copiar(page).boundingBox();
    const cajaCampo = await campo(page).boundingBox();
    expect(caja!.x).toBeGreaterThanOrEqual(0);
    expect(caja!.x + caja!.width).toBeLessThanOrEqual(361);
    expect(cajaCampo!.width).toBeGreaterThan(150);
    // Side by side, aligned at the top.
    expect(Math.abs(caja!.y - cajaCampo!.y)).toBeLessThan(8);
  });
});

const REGLAS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

for (const tema of ['light', 'dark'] as const) {
  test(`axe, tema ${tema === 'light' ? 'claro' : 'oscuro'}: el contador en el tope y el aviso de error a la vista`, async ({ page }) => {
    await instalarEspias(page, { clipboard: 'ausente', exec: 'falso' });
    await abrir(page, apiMowaMes(), 'es', tema);
    await conSugerida(page);
    await campo(page).fill('');
    await campo(page).pressSequentially('a'.repeat(100));
    await copiar(page).click();
    await expect(estado(page)).toHaveText(FALLO);
    await expect(contador(page)).toHaveAttribute('data-tope', 'true');

    const previa = page.locator('[data-previa]');
    if ((await previa.count()) > 0) await expect(previa).toHaveAttribute('data-calculando', 'false');
    const resultado = await new AxeBuilder({ page }).withTags(REGLAS).analyze();
    const resumen = resultado.violations.map((v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`);
    expect(resumen).toEqual([]);
  });
}

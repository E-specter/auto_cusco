/**
 * Automated accessibility (WCAG 2.1 A and AA rules of axe-core) on every
 * screen and on the states where problems hide: open dialogs, a selection
 * marked as not applicable, the dark theme.
 *
 * axe catches roughly a third of accessibility problems. It does not replace
 * a keyboard pass; it replaces the part that gets forgotten between releases.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import { apiVacia, montarApi, seleccionGuardada, version } from './api-falsa';

const REGLAS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

// Contrast measured mid-entrance reads a half-faded paragraph as a failure.
// With reduced motion every screen lands in its final state at once, which is
// also a real mode the product supports.
test.use({ reducedMotion: 'reduce' });

async function sinViolaciones(page: Page): Promise<void> {
  const resultado = await new AxeBuilder({ page }).withTags(REGLAS).analyze();
  const resumen = resultado.violations.map(
    (v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`,
  );
  expect(resumen).toEqual([]);
}

function apiConDatos() {
  const api = apiVacia();
  api.versiones = [version()];
  api.incidencias = [
    { fila: 8, columna: 'pagare', codigo: 'pagare_repetido', severidad: 'error', detalle: 'x', valor_original: null },
  ];
  api.selecciones = [seleccionGuardada()];
  return api;
}

for (const tema of ['light', 'dark'] as const) {
  test.describe(`tema ${tema === 'light' ? 'claro' : 'oscuro'}`, () => {
    test.beforeEach(async ({ page }) => {
      await page.addInitScript((elegido) => {
        localStorage.setItem('app:appearance', JSON.stringify({ theme: elegido, language: 'es' }));
      }, tema);
    });

    test('bienvenida', async ({ page }) => {
      await montarApi(page, apiConDatos());
      await page.goto('/');
      await expect(page.getByRole('link', { name: 'Abrir la consola de cargas' })).toBeVisible();
      await sinViolaciones(page);
    });

    test('consola de cargas', async ({ page }) => {
      await montarApi(page, apiConDatos());
      await page.goto('/cargas');
      await expect(page.getByRole('cell', { name: 'pagare_repetido' })).toBeVisible();
      await sinViolaciones(page);
    });

    test('selección de cartera con métricas, segmentos y productos', async ({ page }) => {
      await montarApi(page, apiConDatos());
      await page.goto('/cartera');
      await page.getByLabel('Selección guardada').selectOption({ label: 'Preventiva mayor saldo' });
      await page.getByRole('button', { name: 'Agregar indicador' }).click();
      await expect(page.locator('[data-solicitados]')).toHaveText('500');
      await expect(page.locator('.productos__tabla')).toBeVisible();
      await sinViolaciones(page);
    });
  });
}

test('cartera: diálogo de guardar con error de nombre', async ({ page }) => {
  const api = apiConDatos();
  api.respuestasCrearSeleccion = [{ estado: 409, cuerpo: { detail: 'repetido' } }];
  await montarApi(page, api);
  await page.goto('/cartera');
  await page.getByRole('button', { name: 'Guardar como nueva' }).click();
  const dialogo = page.getByRole('dialog', { name: 'Guardar la selección' });
  await dialogo.getByLabel('Nombre').fill('Repetido');
  await dialogo.getByRole('button', { name: 'Guardar', exact: true }).click();
  await expect(dialogo.getByText('Ya existe una selección con ese nombre. Elige otro.')).toBeVisible();
  await sinViolaciones(page);
});

test('cartera: selección que no aplica, con partes marcadas', async ({ page }) => {
  const api = apiConDatos();
  api.selecciones = [
    seleccionGuardada({
      filtros: ['campo_retirado:igual:x'],
      aplicable: false,
      problemas: [{ parte: 'filtro', expresion: 'campo_retirado:igual:x', detalle: 'El campo no existe' }],
    }),
  ];
  await montarApi(page, api);
  await page.goto('/cartera');
  await page.getByLabel('Selección guardada').selectOption({ index: 1 });
  await expect(page.getByRole('heading', { name: 'La selección tiene partes que no aplican.' })).toBeVisible();
  await sinViolaciones(page);
});

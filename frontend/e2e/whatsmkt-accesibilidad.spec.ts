/**
 * Automated accessibility (WCAG 2.1 A and AA rules of axe-core) on the WhatsMKT screens of T-WM-F1a, in the
 * light and dark themes, at 1280 and 360 px (RF-WM-44), including the states where problems hide: the
 * dropdown open and the errors under a row, a time slot, the name template and a limit.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import { apiWhatsmkt, montarApiWhatsmkt } from './api-falsa-whatsmkt';

const REGLAS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

// Contrast measured mid-entrance reads a half-faded paragraph as a failure: with reduced motion every screen
// lands in its final state at once, which is also a real mode the product supports.
test.use({ reducedMotion: 'reduce' });

async function sinViolaciones(page: Page): Promise<void> {
  const resultado = await new AxeBuilder({ page }).withTags(REGLAS).analyze();
  const resumen = resultado.violations.map(
    (v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`,
  );
  expect(resumen).toEqual([]);
}

const anchos = [
  ['1280 px', { width: 1280, height: 900 }],
  ['360 px', { width: 360, height: 900 }],
] as const;

for (const tema of ['light', 'dark'] as const) {
  for (const [nombreAncho, tamano] of anchos) {
    test.describe(`WhatsMKT, tema ${tema === 'light' ? 'claro' : 'oscuro'}, ${nombreAncho}`, () => {
      test.beforeEach(async ({ page }) => {
        await page.setViewportSize(tamano);
        await page.addInitScript((elegido) => {
          localStorage.setItem('app:appearance', JSON.stringify({ theme: elegido, language: 'es' }));
        }, tema);
        await montarApiWhatsmkt(page, apiWhatsmkt());
      });

      test('campaña, con su aviso de construcción', async ({ page }) => {
        await page.goto('/whatsmkt/campana');
        await expect(page.getByRole('heading', { name: 'Campaña de WhatsMKT', level: 1 })).toBeVisible();
        await sinViolaciones(page);
      });

      test('seguimiento, con su aviso de construcción', async ({ page }) => {
        await page.goto('/whatsmkt/seguimiento');
        await expect(page.getByRole('heading', { name: 'Seguimiento de WhatsMKT', level: 1 })).toBeVisible();
        await sinViolaciones(page);
      });

      test('configuración, con todos sus paneles', async ({ page }) => {
        await page.goto('/whatsmkt/configuracion');
        await expect(page.getByLabel('Nombre del segmento Preventivo')).toBeVisible();
        await sinViolaciones(page);
      });

      test('configuración, con el error de una fila, el de una franja, el del nombre y el de un tope', async ({ page }) => {
        await page.goto('/whatsmkt/configuracion');
        await expect(page.getByLabel('Nombre del segmento Preventivo')).toBeVisible();

        await page.getByLabel('Desde, segmento Tramo 2').fill('0');
        await page.getByRole('button', { name: 'Guardar segmentos' }).click();
        await expect(page.locator('[data-error-fila="tramo_2"]')).toBeVisible();

        await page.locator('#wm-h1-fin').fill('08:00');
        await page.locator('#wm-h1-fin').blur();
        await expect(page.locator('[data-franja="horario_1"] [data-franja-error]')).not.toBeEmpty();

        await page.locator('#wm-plantilla').fill(`${'a'.repeat(64)}{segmento}`);
        await expect(page.locator('[data-plantilla-error]')).not.toBeEmpty();

        // A limit says its error on leaving the field.
        await page.locator('#wm-tope-mensaje').fill('0');
        await page.locator('#wm-tope-mensaje').blur();
        await expect(page.locator('[data-tope-error="tope_mensaje"]')).not.toBeEmpty();

        await sinViolaciones(page);
      });
    });
  }

  test(`el desplegable de WhatsMKT abierto, tema ${tema === 'light' ? 'claro' : 'oscuro'}`, async ({ page }) => {
    await page.addInitScript((elegido) => {
      localStorage.setItem('app:appearance', JSON.stringify({ theme: elegido, language: 'es' }));
    }, tema);
    await montarApiWhatsmkt(page, apiWhatsmkt());
    await page.goto('/whatsmkt/campana');

    await page.getByRole('button', { name: 'WhatsMKT' }).click();
    await expect(page.getByRole('link', { name: 'WhatsMKT: campaña' })).toBeVisible();

    await sinViolaciones(page);
  });
}

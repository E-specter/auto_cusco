/**
 * Pending reports (RF-MM-33, T-MM-C11 M-F4): a campaign whose sent report has not been imported yet says so in
 * its row (the tag), above the list (how many) and in its detail (the next step and the way to it); and the
 * follow-up opens the campaign a link points at (`?campana=<id>`). What is pending is `pendiente_reporte`,
 * which the API computes: the screen never works it out. Every value is synthetic.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import { apiMowaMes, campanaSintetica, montarApiMowaMes, type ApiFalsaMowaMes } from './api-falsa-mowa-mes';

test.use({ timezoneId: 'America/Lima', reducedMotion: 'reduce' });

const REGLAS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];
const REPORTE = {
  name: 'REPORTE_SINTETICO.xlsx',
  mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  buffer: Buffer.from('reporte sintetico de prueba'),
};

/** Campaigns 3, 2 and 1 (most recent first); `pendientes` says which of them still wait for their report. */
function conCampanas(pendientes: number[], total = 3): ApiFalsaMowaMes {
  const api = apiMowaMes();
  api.campanas = Array.from({ length: total }, (_, i) => {
    const id = total - i;
    return campanaSintetica({ id, descripcion: `Campaña sintética ${id}`, pendiente_reporte: pendientes.includes(id) });
  });
  return api;
}

async function abrir(page: Page, api: ApiFalsaMowaMes, busqueda = ''): Promise<void> {
  await montarApiMowaMes(page, api);
  await page.goto(`/mowa-mes/seguimiento${busqueda}`);
  await expect(page.getByRole('heading', { name: 'Seguimiento de MOWA MES', level: 1 })).toBeVisible();
  await expect(page.locator('.mm-campanas__tabla tbody tr').first()).toBeVisible();
}

const filas = (page: Page) => page.locator('.mm-campanas__tabla tbody tr');
const fila = (page: Page, id: number) => filas(page).filter({ hasText: `Campaña sintética ${id}` });
const linea = (page: Page) => page.locator('[data-pendientes]');
const aviso = (page: Page) => page.locator('[data-pendiente-aviso]');
const detalle = (page: Page) => page.getByRole('heading', { name: /^Campaña \d+$/, level: 2 });

test.describe('la fila y la línea de arriba', () => {
  test('solo las pendientes llevan el tag, con su icono, como advertencia', async ({ page }) => {
    await abrir(page, conCampanas([3, 1]));

    await expect(fila(page, 3).locator('.tag')).toHaveText('Pendiente del reporte');
    await expect(fila(page, 3).locator('.tag')).toHaveClass(/tag--advertencia/);
    await expect(fila(page, 3).locator('.tag svg')).toHaveCount(1);
    await expect(fila(page, 1).locator('.tag')).toHaveCount(1);
    await expect(fila(page, 2).locator('.tag')).toHaveCount(0);
  });

  test('la línea de arriba cuenta las pendientes, en plural', async ({ page }) => {
    await abrir(page, conCampanas([3, 1]));

    await expect(linea(page)).toBeVisible();
    await expect(linea(page)).toHaveText('2 campañas pendientes del reporte');
    await expect(linea(page).locator('.notice')).toHaveClass(/notice--warning/);
  });

  test('con una sola, en singular', async ({ page }) => {
    await abrir(page, conCampanas([2]));

    await expect(linea(page)).toHaveText('1 campaña pendiente del reporte');
  });

  test('la línea cuenta toda la lista, no solo la página que se ve', async ({ page }) => {
    // 25 campaigns, 20 per page: the pending ones (1, 2 and 3) are all on the second page.
    await abrir(page, conCampanas([1, 2, 3], 25));

    await expect(page.locator('.mm-campanas__tabla .tag')).toHaveCount(0);
    await expect(linea(page)).toHaveText('3 campañas pendientes del reporte');
  });

  test('sin ninguna, ni la línea ni el tag', async ({ page }) => {
    await abrir(page, conCampanas([]));

    await expect(linea(page)).toBeHidden();
    await expect(page.locator('.mm-campanas__tabla .tag')).toHaveCount(0);
  });

  test('el estado se lee por el texto: el tag no depende solo del color', async ({ page }) => {
    await abrir(page, conCampanas([3]));

    const tag = fila(page, 3).locator('.tag');
    await expect(tag).toHaveText('Pendiente del reporte');
    expect(await tag.evaluate((el) => getComputedStyle(el).opacity)).toBe('1');
  });
});

test.describe('el detalle', () => {
  test('una pendiente muestra el paso siguiente y «Importar el reporte»', async ({ page }) => {
    await abrir(page, conCampanas([3, 2, 1]));

    await expect(aviso(page)).toBeVisible();
    await expect(aviso(page)).toHaveClass(/notice--warning/);
    await expect(aviso(page)).toContainText(
      'Falta importar el reporte de enviados de MES. Cuando la campaña se haya enviado, descárgalo de MES e impórtalo aquí.',
    );
    await expect(aviso(page).getByRole('button', { name: 'Importar el reporte' })).toBeVisible();
  });

  test('una con reporte no muestra el aviso', async ({ page }) => {
    await abrir(page, conCampanas([2, 1]));

    await expect(detalle(page)).toHaveText('Campaña 3');
    await expect(aviso(page)).toBeHidden();
  });

  test('el aviso sigue a la campaña elegida', async ({ page }) => {
    await abrir(page, conCampanas([2]));
    await expect(aviso(page)).toBeHidden();

    await page.getByRole('button', { name: 'Ver la campaña 2' }).click();
    await expect(detalle(page)).toHaveText('Campaña 2');
    await expect(aviso(page)).toBeVisible();

    await page.getByRole('button', { name: 'Ver la campaña 1' }).click();
    await expect(aviso(page)).toBeHidden();
  });

  test('«Importar el reporte» lleva al campo de importación', async ({ page }) => {
    await abrir(page, conCampanas([3]));

    await aviso(page).getByRole('button', { name: 'Importar el reporte' }).click();

    await expect(page.getByLabel('Archivo del reporte')).toBeFocused();
    await expect(page.getByLabel('Archivo del reporte')).toBeInViewport();
  });

  test('al importar el reporte, el tag, la línea y el aviso se van', async ({ page }) => {
    await abrir(page, conCampanas([3, 1]));
    await expect(linea(page)).toHaveText('2 campañas pendientes del reporte');

    await page.getByLabel('Archivo del reporte').setInputFiles(REPORTE);
    await page.getByRole('button', { name: 'Importar reporte' }).click();

    await expect(page.getByText('Reporte importado.')).toBeVisible();
    await expect(fila(page, 3).locator('.tag')).toHaveCount(0);
    await expect(aviso(page)).toBeHidden();
    await expect(linea(page)).toHaveText('1 campaña pendiente del reporte');
    // The other one still waits.
    await expect(fila(page, 1).locator('.tag')).toHaveCount(1);
  });
});

test.describe('?campana=<id>', () => {
  test('abre esa campaña, no la más reciente', async ({ page }) => {
    await abrir(page, conCampanas([3, 2, 1]), '?campana=2');

    await expect(detalle(page)).toHaveText('Campaña 2');
    await expect(page.getByRole('button', { name: 'Ver la campaña 2' })).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByRole('button', { name: 'Ver la campaña 3' })).toHaveAttribute('aria-pressed', 'false');
  });

  test('una campaña de otra página de la lista también se abre', async ({ page }) => {
    // 25 campaigns, 20 per page: the 3rd is on the second page.
    await abrir(page, conCampanas([], 25), '?campana=3');

    await expect(detalle(page)).toHaveText('Campaña 3');
    await expect(page.locator('.mm-campanas__tabla tbody tr')).toHaveCount(20);
  });

  test('una campaña que no existe deja la más reciente', async ({ page }) => {
    await abrir(page, conCampanas([]), '?campana=999');

    await expect(detalle(page)).toHaveText('Campaña 3');
  });

  test('un valor que no es un número deja la más reciente', async ({ page }) => {
    await abrir(page, conCampanas([]), '?campana=abc');

    await expect(detalle(page)).toHaveText('Campaña 3');
  });

  test('sin el parámetro, la más reciente, como siempre', async ({ page }) => {
    await abrir(page, conCampanas([]));

    await expect(detalle(page)).toHaveText('Campaña 3');
  });
});

test.describe('idioma y anchos', () => {
  test('en inglés traduce el tag, la línea y el aviso', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    await montarApiMowaMes(page, conCampanas([3, 1]));
    await page.goto('/mowa-mes/seguimiento');
    await expect(page.locator('.mm-campanas__tabla tbody tr').first()).toBeVisible();

    await expect(page.locator('.mm-campanas__tabla tbody tr').first().locator('.tag')).toHaveText('Report pending');
    await expect(linea(page)).toHaveText('2 campaigns with the report pending');
    await expect(aviso(page)).toContainText('The MES sent report has not been imported yet.');
    await expect(aviso(page).getByRole('button', { name: 'Import the report' })).toBeVisible();
  });

  test('a 360 px el aviso no desborda y su botón queda a la vista', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    await abrir(page, conCampanas([3]));

    const boton = aviso(page).getByRole('button', { name: 'Importar el reporte' });
    await boton.scrollIntoViewIfNeeded();
    const caja = (await boton.boundingBox())!;
    expect(caja.x).toBeGreaterThanOrEqual(0);
    expect(caja.x + caja.width).toBeLessThanOrEqual(361);
    const desborde = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(desborde).toBeLessThanOrEqual(0);
  });

  for (const tema of ['light', 'dark'] as const) {
    for (const ancho of [1280, 360]) {
      test(`sin violaciones WCAG a ${ancho} px, tema ${tema === 'light' ? 'claro' : 'oscuro'}`, async ({ page }) => {
        await page.addInitScript((elegido) => {
          localStorage.setItem('app:appearance', JSON.stringify({ theme: elegido, language: 'es' }));
        }, tema);
        await page.setViewportSize({ width: ancho, height: 900 });
        await abrir(page, conCampanas([3, 1]));
        await expect(aviso(page)).toBeVisible();

        const resultado = await new AxeBuilder({ page }).withTags(REGLAS).analyze();
        expect(resultado.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
      });
    }
  }
});

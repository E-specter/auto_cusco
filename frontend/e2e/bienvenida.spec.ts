/**
 * The welcome screen.
 *
 * Its hard rule is that it never scrolls (brand guide: the hero is one
 * viewport at 100dvh). That rule breaks silently — a longer sentence, one
 * more stat, a heading that wraps — and nothing else in the build notices.
 * These are the sizes the guide names for verification.
 */
import { expect, test } from '@playwright/test';

import { apiVacia, montarApi, version } from './api-falsa';

const TAMANOS = [
  { nombre: 'móvil pequeño', width: 360, height: 640 },
  { nombre: 'tablet vertical', width: 768, height: 1024 },
  { nombre: 'portátil', width: 1440, height: 900 },
  { nombre: 'escritorio', width: 1920, height: 1080 },
];

for (const tamano of TAMANOS) {
  test(`no se desplaza en ${tamano.nombre} (${tamano.width}x${tamano.height})`, async ({ page }) => {
    const api = apiVacia();
    api.versiones = [
      version({ id: 7, fecha_corte: '2026-09-10' }),
      version({ id: 6, fecha_corte: '2026-09-09', version: 1 }),
    ];
    await montarApi(page, api);
    await page.setViewportSize({ width: tamano.width, height: tamano.height });

    await page.goto('/');
    // La entrada escalonada termina antes de esto; medir durante la animación
    // daría una altura que nadie ve.
    await page.waitForTimeout(1600);

    const medidas = await page.evaluate(() => ({
      alto: document.documentElement.scrollHeight,
      altoVisible: document.documentElement.clientHeight,
      ancho: document.documentElement.scrollWidth,
      anchoVisible: document.documentElement.clientWidth,
    }));

    expect(medidas.alto).toBeLessThanOrEqual(medidas.altoVisible + 1);
    expect(medidas.ancho).toBeLessThanOrEqual(medidas.anchoVisible + 1);
  });
}

test('las cifras son el estado real del sistema, no un ejemplo', async ({ page }) => {
  const api = apiVacia();
  api.versiones = [
    version({ id: 7, fecha_corte: '2026-09-10', vigente: true }),
    version({ id: 6, fecha_corte: '2026-09-09', vigente: true }),
    version({ id: 5, fecha_corte: '2026-09-09', version: 2, vigente: false }),
  ];
  await montarApi(page, api);

  await page.goto('/');

  await expect(page.locator('[data-stat="fechas"]')).toHaveText('2');
  await expect(page.locator('[data-stat="versiones"]')).toHaveText('3');
  await expect(page.locator('[data-stat="ultima"]')).toHaveText('10.09.2026');
});

test('con la base vacía lo dice en vez de inventar cifras', async ({ page }) => {
  await montarApi(page, apiVacia());

  await page.goto('/');

  await expect(page.locator('[data-stat="fechas"]')).toHaveText('0');
  await expect(page.locator('[data-stat="ultima"]')).toHaveText('—');
  await expect(page.locator('[data-latest]')).toContainText('Todavía no hay ninguna sábana cargada');
});

test('el aviso señala las fechas sin vigente, que es lo accionable', async ({ page }) => {
  const api = apiVacia();
  api.versiones = [
    version({ id: 7, fecha_corte: '2026-09-10', vigente: true }),
    // Esta fecha quedó sin vigente: ese día no cuenta para nada.
    version({ id: 6, fecha_corte: '2026-09-09', vigente: false }),
  ];
  await montarApi(page, api);

  await page.goto('/');

  await expect(page.locator('[data-latest]')).toContainText('1 fecha sin versión vigente');
  await expect(page.locator('[data-latest]')).toHaveAttribute('data-state', 'attention');
});

test('el diagrama se nombra como diagrama, para que no se lea como estado', async ({ page }) => {
  // Con la base vacía las cifras dicen 0 mientras el diagrama muestra una v2
  // vigente. El rótulo es lo que evita que una cosa contradiga a la otra.
  await montarApi(page, apiVacia());
  await page.setViewportSize({ width: 1440, height: 900 });

  await page.goto('/');

  await expect(page.locator('.hero__figcaption')).toBeVisible();
  await expect(page.locator('.hero__figcaption')).toHaveText('Recorrido de una sábana');
});

test('la llamada a la acción lleva a la consola', async ({ page }) => {
  await montarApi(page, apiVacia());

  await page.goto('/');
  await page.getByRole('link', { name: 'Abrir la consola de cargas' }).click();

  await expect(page).toHaveURL(/\/cargas/);
  await expect(page.getByRole('heading', { name: 'Fechas de corte' })).toBeVisible();
});

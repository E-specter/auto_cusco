/**
 * The top navigation: pinned while the page scrolls, grouped by section, and
 * each module's routes in a dropdown that works by mouse, touch and keyboard.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import { apiVacia, montarApi, productosSinteticos, version } from './api-falsa';

async function abrirCartera(page: Page): Promise<void> {
  const api = apiVacia();
  api.versiones = [version()];
  api.productos = productosSinteticos(120);
  await montarApi(page, api);
  await page.goto('/cartera');
  await expect(page.locator('.productos__tabla')).toBeVisible();
}

const cabecera = (page: Page) => page.locator('header.chrome');
const disparador = (page: Page) => page.getByRole('button', { name: 'MOWA MES' });

test.describe('cabecera adhesiva', () => {
  test('sigue a la vista al bajar hasta el final, sin cambiar de alto', async ({ page }) => {
    await abrirCartera(page);
    const antes = await cabecera(page).boundingBox();

    await page.mouse.wheel(0, 4000);
    await page.waitForFunction(() => window.scrollY > 500);
    const despues = await cabecera(page).boundingBox();

    expect(despues?.y).toBe(0);
    expect(despues?.height).toBe(antes?.height);
    await expect(disparador(page)).toBeInViewport();
  });

  test('queda por encima de un desplegable de la página que pasa por debajo', async ({ page }) => {
    // A short window leaves room to scroll the list all the way up.
    await page.setViewportSize({ width: 1280, height: 420 });
    await abrirCartera(page);
    // The column chooser is the highest layer a page draws (z-index 3).
    await page.locator('[data-columnas] > summary').click();
    const lista = page.locator('[data-columnas-lista]');
    const alto = (await cabecera(page).boundingBox())!.height;
    const antes = (await lista.boundingBox())!;

    // Scroll until the open list runs under the pinned header.
    await page.evaluate((dy) => window.scrollBy(0, dy), antes.y - alto / 2);
    const despues = (await lista.boundingBox())!;
    const punto = { x: despues.x + 12, y: alto - 4 };

    const encima = await page.evaluate(
      ({ x, y }) => Boolean(document.elementFromPoint(x, y)?.closest('header.chrome')),
      punto,
    );

    expect(despues.y).toBeLessThan(punto.y);
    expect(encima).toBe(true);
  });
});

test.describe('secciones', () => {
  test('separa las secciones con un divisor y los ítems con un punto medio', async ({ page }) => {
    await abrirCartera(page);
    const nav = page.getByRole('navigation', { name: 'Secciones' });

    await expect(nav.getByRole('list', { name: 'Flujo diario' })).toBeVisible();
    await expect(nav.getByRole('list', { name: 'Canales' })).toBeVisible();
    await expect(nav.locator('.nav__divisor')).toHaveText('|');
    await expect(nav.locator('.nav__punto').first()).toHaveText('·');
    await expect(nav.getByRole('link', { name: 'Cartera' })).toHaveAttribute('aria-current', 'page');
  });
});

test.describe('submenú de un módulo', () => {
  test('se abre con clic, lleva a la ruta y marca el módulo activo', async ({ page }) => {
    await abrirCartera(page);

    await disparador(page).click();
    await expect(disparador(page)).toHaveAttribute('aria-expanded', 'true');
    await page.getByRole('link', { name: 'MOWA MES: seguimiento' }).click();

    await expect(page).toHaveURL(/\/mowa-mes\/seguimiento$/);
    await expect(page.locator('.nav__modulo[data-modulo="mowa-mes"]')).toHaveAttribute('data-activo', 'true');
    // The module page may open its own dialog here (this fake API does not
    // serve MOWA MES), so the mark is read without reopening the menu.
    await expect(page.locator('#nav-mowa-mes a[href="/mowa-mes/seguimiento"]')).toHaveAttribute('aria-current', 'page');
  });

  test('se maneja con teclado: flechas, Escape devuelve el foco', async ({ page }) => {
    await abrirCartera(page);

    await disparador(page).focus();
    await page.keyboard.press('ArrowDown');
    await expect(page.getByRole('link', { name: 'MOWA MES: campaña' })).toBeFocused();
    await page.keyboard.press('ArrowDown');
    await expect(page.getByRole('link', { name: 'MOWA MES: seguimiento' })).toBeFocused();
    await page.keyboard.press('Escape');

    await expect(disparador(page)).toBeFocused();
    await expect(disparador(page)).toHaveAttribute('aria-expanded', 'false');
  });

  test('se cierra al tocar fuera o al salir el foco', async ({ page }) => {
    await abrirCartera(page);

    await disparador(page).click();
    await page.locator('.cartera__title').click();
    await expect(disparador(page)).toHaveAttribute('aria-expanded', 'false');

    await disparador(page).click();
    await page.keyboard.press('Shift+Tab');
    await expect(disparador(page)).toHaveAttribute('aria-expanded', 'false');
  });

  test('con el ratón se abre al pasar y se cierra al salir', async ({ page }) => {
    await abrirCartera(page);

    await disparador(page).hover();
    await expect(page.getByRole('link', { name: 'MOWA MES: campaña' })).toBeVisible();
    await page.mouse.move(5, 600);

    await expect(page.getByRole('link', { name: 'MOWA MES: campaña' })).toBeHidden();
  });

  test('un clic sobre el menú abierto al pasar lo fija en vez de cerrarlo', async ({ page }) => {
    await abrirCartera(page);

    await disparador(page).hover();
    await expect(disparador(page)).toHaveAttribute('aria-expanded', 'true');
    await disparador(page).click();
    await page.mouse.move(5, 600);
    await page.waitForTimeout(400);

    await expect(disparador(page)).toHaveAttribute('aria-expanded', 'true');
  });

  test('en móvil el submenú cabe en la pantalla y funciona con toque', async ({ browser }) => {
    const contexto = await browser.newContext({ viewport: { width: 360, height: 640 }, hasTouch: true });
    const page = await contexto.newPage();
    await abrirCartera(page);

    await disparador(page).tap();
    const panel = page.locator('#nav-mowa-mes');
    await expect(panel).toBeVisible();
    const caja = await panel.boundingBox();

    expect((caja?.x ?? -1) >= 0).toBe(true);
    expect((caja?.x ?? 0) + (caja?.width ?? 0)).toBeLessThanOrEqual(360);
    await contexto.close();
  });
});

test.describe('accesibilidad de la navegación', () => {
  test.use({ reducedMotion: 'reduce' });

  for (const tema of ['light', 'dark'] as const) {
    test(`sin violaciones WCAG con el submenú abierto, tema ${tema}`, async ({ page }) => {
      await page.addInitScript((elegido) => {
        localStorage.setItem('app:appearance', JSON.stringify({ theme: elegido, language: 'es' }));
      }, tema);
      await abrirCartera(page);
      await disparador(page).click();

      const resultado = await new AxeBuilder({ page })
        .include('header.chrome')
        .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
        .analyze();

      expect(resultado.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
    });
  }
});

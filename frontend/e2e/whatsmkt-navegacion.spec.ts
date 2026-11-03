/**
 * WhatsMKT in the menu and its two screens that wait for their cut (T-WM-F2, T-WM-F3): the dropdown is
 * the same as MOWA MES's, and each screen says what it will do instead of standing empty.
 */
import { expect, test, type Page } from '@playwright/test';

import { apiWhatsmkt, montarApiWhatsmkt } from './api-falsa-whatsmkt';
import { mensajesFalsos, montarMensajesWhatsmkt } from './api-falsa-whatsmkt-mensajes';
import { campanaFalsa, montarCampanaWhatsmkt } from './api-falsa-whatsmkt-campana';
import { montarSeleccion } from './apoyo-seleccion';

const nav = (page: Page) => page.getByRole('navigation', { name: /Secciones|Sections/ });
const disparador = (page: Page) => page.getByRole('button', { name: 'WhatsMKT' });

async function abrir(page: Page, ruta: string): Promise<void> {
  await montarApiWhatsmkt(page, apiWhatsmkt());
  // The settings read the saved messages and the default definition; what a spec registers after this one answers first.
  await montarMensajesWhatsmkt(page, mensajesFalsos());
  // The campaign screen also reads the selection, the saved texts and a definition: registered after, they fall back to the rest.
  await montarCampanaWhatsmkt(page, campanaFalsa());
  await montarSeleccion(page);
  await page.goto(ruta);
}

test.describe('menú de WhatsMKT', () => {
  test('va en Canales después de MOWA MES', async ({ page }) => {
    await abrir(page, '/whatsmkt/campana');

    await expect(nav(page).getByRole('list', { name: 'Canales' }).getByRole('button')).toHaveText(['MOWA MES', 'WhatsMKT']);
  });

  test('abre Campaña, Seguimiento y Configuración, con el nombre del módulo en cada enlace', async ({ page }) => {
    await abrir(page, '/whatsmkt/campana');

    await disparador(page).click();

    await expect(disparador(page)).toHaveAttribute('aria-expanded', 'true');
    const enlaces = page.locator('#nav-whatsmkt a');
    await expect(enlaces).toHaveText(['Campaña', 'Seguimiento', 'Configuración']);
    await expect(page.getByRole('link', { name: 'WhatsMKT: campaña' })).toHaveAttribute('href', '/whatsmkt/campana');
    await expect(page.getByRole('link', { name: 'WhatsMKT: seguimiento' })).toHaveAttribute('href', '/whatsmkt/seguimiento');
    await expect(page.getByRole('link', { name: 'WhatsMKT: configuración' })).toHaveAttribute('href', '/whatsmkt/configuracion');
  });

  test('lleva a la pantalla, marca WhatsMKT como módulo activo y no MOWA MES', async ({ page }) => {
    await abrir(page, '/whatsmkt/campana');

    await disparador(page).click();
    await page.getByRole('link', { name: 'WhatsMKT: configuración' }).click();

    await expect(page).toHaveURL(/\/whatsmkt\/configuracion$/);
    await expect(page.locator('.nav__modulo[data-modulo="whatsmkt"]')).toHaveAttribute('data-activo', 'true');
    await expect(page.locator('.nav__modulo[data-modulo="mowa-mes"]')).not.toHaveAttribute('data-activo', 'true');
    await expect(page.locator('#nav-whatsmkt a[href="/whatsmkt/configuracion"]')).toHaveAttribute('aria-current', 'page');
  });

  test('se maneja con teclado: flechas, y Escape devuelve el foco', async ({ page }) => {
    await abrir(page, '/whatsmkt/campana');

    await disparador(page).focus();
    await page.keyboard.press('ArrowDown');
    await expect(page.getByRole('link', { name: 'WhatsMKT: campaña' })).toBeFocused();
    await page.keyboard.press('ArrowDown');
    await expect(page.getByRole('link', { name: 'WhatsMKT: seguimiento' })).toBeFocused();
    await page.keyboard.press('Escape');

    await expect(disparador(page)).toBeFocused();
    await expect(disparador(page)).toHaveAttribute('aria-expanded', 'false');
  });

  test('en inglés se traduce', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    await abrir(page, '/whatsmkt/campana');

    await disparador(page).click();

    await expect(page.locator('#nav-whatsmkt a')).toHaveText(['Campaign', 'Tracking', 'Settings']);
    await expect(page.getByRole('link', { name: 'WhatsMKT: tracking' })).toBeVisible();
  });

  test('a 360 px el submenú cabe en la pantalla y la página no desborda', async ({ browser }) => {
    const contexto = await browser.newContext({ viewport: { width: 360, height: 640 }, hasTouch: true });
    const page = await contexto.newPage();
    await abrir(page, '/whatsmkt/campana');

    await disparador(page).tap();
    const caja = await page.locator('#nav-whatsmkt').boundingBox();

    expect((caja?.x ?? -1) >= 0).toBe(true);
    expect((caja?.x ?? 0) + (caja?.width ?? 0)).toBeLessThanOrEqual(360);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
    await contexto.close();
  });
});

test.describe('pantallas que esperan su corte', () => {
  test('Campaña tiene su título y empieza por elegir la selección', async ({ page }) => {
    await abrir(page, '/whatsmkt/campana');

    // `.page__head`, not the whole page: the header's «API en línea» is an `.eyebrow` too.
    await expect(page.locator('.page__head .eyebrow')).toHaveText('Canales · WhatsMKT');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Campaña de WhatsMKT');
    await expect(page.locator('[data-guardia]')).toContainText('Elige una selección guardada para armar la campaña.');
  });

  test('Seguimiento tiene su título y dice lo que traerá', async ({ page }) => {
    await abrir(page, '/whatsmkt/seguimiento');

    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Seguimiento de WhatsMKT');
    const aviso = page.locator('.notice--info');
    await expect(aviso).toContainText('en construcción');
    await expect(aviso).toContainText('importarás el informe de WhatsMKT');
  });
});

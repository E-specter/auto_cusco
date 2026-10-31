/**
 * The icons of the configuration (RF-MM-36, T-MM-C11 M-F7c; docs/mowa-mes-interfaz.md §3): the tags and actions of the
 * disabled versions of the speech, which M-F2 put there, as the catalogue says. «Deshabilitada» is a neutral tag with
 * `power-off`; «Original» is an info tag with `lock`, the padlock of the read-only notice. The catalogue asks nothing
 * else of this screen: no gauge, no figures, and «Guardar» stays without an icon. Every value is synthetic.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Locator, type Page } from '@playwright/test';

import {
  DESHABILITADA_EN,
  apiMowaMes,
  montarApiMowaMes,
  speechOriginal,
  versionAdministrable,
  type ApiFalsaMowaMes,
} from './api-falsa-mowa-mes';

test.use({ timezoneId: 'America/Lima', reducedMotion: 'reduce' });

const REGLAS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];
const RUTA = '/mowa-mes/configuracion';

/** 1 is the Speech original, disabled; 2 is enabled; 3 and 4 are disabled (3 unused, so it can be deleted). */
function conVersiones(): ApiFalsaMowaMes {
  const api = apiMowaMes();
  api.versiones = [
    versionAdministrable({ ...speechOriginal(), deshabilitada_en: DESHABILITADA_EN }),
    versionAdministrable({ id: 2, nombre: 'Activa' }),
    versionAdministrable({ id: 3, nombre: 'Borrable', deshabilitada_en: DESHABILITADA_EN }),
    versionAdministrable({ id: 4, nombre: 'Usada deshabilitada', usada: true, deshabilitada_en: DESHABILITADA_EN }),
  ];
  return api;
}

async function abrir(page: Page, api = conVersiones()): Promise<void> {
  await montarApiMowaMes(page, api);
  await page.goto(RUTA);
  await expect(page.getByRole('heading', { name: 'Configuración de MOWA MES' })).toBeVisible();
  await expect(page.locator('[data-deshabilitadas]')).toBeVisible();
  await page.locator('[data-deshabilitadas] summary').click();
  await expect(fila(page, 3)).toBeVisible();
}

const fila = (page: Page, id: number) => page.locator(`[data-deshab-lista] [data-version="${id}"]`);
/** The drawing of an icon: two icons are the same one if they draw the same. */
const dibujo = (nodo: Locator) => nodo.evaluate((el) => el.innerHTML);

test.describe('los tags de las versiones deshabilitadas', () => {
  test('«Deshabilitada» es un tag neutro con su icono, y «Original» un tag de información con el suyo', async ({ page }) => {
    await abrir(page);

    const deshabilitada = fila(page, 3).locator('.tag', { hasText: 'Deshabilitada' });
    await expect(deshabilitada).toHaveClass(/tag--neutral/);
    await expect(deshabilitada.locator('svg')).toHaveCount(1);
    await expect(deshabilitada.locator('svg')).toHaveAttribute('aria-hidden', 'true');
    const original = fila(page, 1).locator('.tag', { hasText: 'Original' });
    await expect(original).toHaveClass(/tag--info/);
    await expect(original).not.toHaveClass(/tag--neutral/);
    await expect(original.locator('svg')).toHaveCount(1);
    await expect(original.locator('svg')).toHaveAttribute('aria-hidden', 'true');
  });

  test('una versión que no es la original no lleva el tag «Original»', async ({ page }) => {
    await abrir(page);

    await expect(fila(page, 3).locator('.tag')).toHaveText(['Deshabilitada']);
    await expect(fila(page, 1).locator('.tag')).toHaveText(['Deshabilitada', 'Original']);
  });

  test('un concepto, un icono: «Original» lleva el candado del aviso de solo lectura', async ({ page }) => {
    await abrir(page);
    const delTag = await dibujo(fila(page, 1).locator('.tag', { hasText: 'Original' }).locator('svg'));

    await fila(page, 1).getByRole('button', { name: 'Ver' }).click();

    await expect(page.locator('[data-speech-inmutable]')).toBeVisible();
    expect(await dibujo(page.locator('[data-speech-inmutable] svg').first())).toBe(delTag);
  });

  test('un concepto, un icono: «Deshabilitada» lleva el de la acción «Deshabilitar»', async ({ page }) => {
    await abrir(page);
    const delTag = await dibujo(fila(page, 3).locator('.tag', { hasText: 'Deshabilitada' }).locator('svg'));

    await page.locator('#mm-version').selectOption('2');

    expect(await dibujo(page.getByRole('button', { name: 'Deshabilitar' }).locator('svg'))).toBe(delTag);
    // And «Habilitar» is its opposite, not the same drawing.
    expect(await dibujo(fila(page, 3).getByRole('button', { name: 'Habilitar' }).locator('svg'))).not.toBe(delTag);
  });

  test('el icono de un tag mide 1,2 veces su texto', async ({ page }) => {
    await abrir(page);

    for (const tag of [fila(page, 3).locator('.tag').first(), fila(page, 1).locator('.tag', { hasText: 'Original' })]) {
      const medidas = await tag.evaluate((el) => {
        const icono = el.querySelector('svg')!.getBoundingClientRect();
        return { ancho: icono.width, alto: icono.height, texto: parseFloat(getComputedStyle(el).fontSize) };
      });
      expect(Math.abs(medidas.ancho - medidas.texto * 1.2)).toBeLessThan(0.6);
      expect(Math.abs(medidas.alto - medidas.texto * 1.2)).toBeLessThan(0.6);
    }
  });

  test('los tags no usan opacidad: su texto conserva el contraste', async ({ page }) => {
    await abrir(page);

    expect(await fila(page, 3).evaluate((el) => getComputedStyle(el).opacity)).toBe('1');
    expect(await fila(page, 1).locator('.tag', { hasText: 'Original' }).evaluate((el) => getComputedStyle(el).opacity)).toBe('1');
  });
});

test.describe('las acciones y lo que el catálogo no pide', () => {
  test('cada acción de la fila lleva su icono: Ver eye, Habilitar power, Eliminar trash-2, los tres distintos', async ({ page }) => {
    await abrir(page);

    const ver = await dibujo(fila(page, 3).getByRole('button', { name: 'Ver' }).locator('svg'));
    const habilitar = await dibujo(fila(page, 3).getByRole('button', { name: 'Habilitar' }).locator('svg'));
    const eliminar = await dibujo(fila(page, 3).getByRole('button', { name: 'Eliminar definitivamente' }).locator('svg'));
    expect(new Set([ver, habilitar, eliminar]).size).toBe(3);
    // «Eliminar» is the same trash can in the row and in the dialog that confirms it.
    await fila(page, 3).getByRole('button', { name: 'Eliminar definitivamente' }).click();
    const dialogo = page.getByRole('dialog', { name: 'Eliminar definitivamente la versión «Borrable»' });
    expect(await dibujo(dialogo.getByRole('button', { name: 'Eliminar definitivamente' }).locator('svg'))).toBe(eliminar);
  });

  test('«Renombrar» lleva pencil y «Deshabilitar» power-off, con su texto', async ({ page }) => {
    await abrir(page);
    await page.locator('#mm-version').selectOption('2');

    for (const nombre of ['Renombrar', 'Deshabilitar']) {
      const boton = page.getByRole('button', { name: nombre });
      await expect(boton.locator('svg')).toHaveCount(1);
      await expect(boton).toContainText(nombre);
    }
  });

  test('«Guardar» no gana icono, ni los títulos de panel, ni las cifras', async ({ page }) => {
    await abrir(page);

    await expect(page.locator('[data-plataforma-guardar] svg')).toHaveCount(0);
    await expect(page.locator('[data-speech-guardar] svg')).toHaveCount(0);
    await expect(page.locator('.panel__title svg')).toHaveCount(0);
    await expect(page.locator('.stat__label svg')).toHaveCount(0);
  });

  test('todos los iconos de la pantalla son decorativos y ningún botón queda sin nombre', async ({ page }) => {
    await abrir(page);

    const resultado = await page.evaluate(() => ({
      visibles: [...document.querySelectorAll<SVGElement>('main svg, .page svg')]
        .filter((s) => s.getBoundingClientRect().width > 0)
        .filter((s) => s.getAttribute('aria-hidden') !== 'true')
        .map((s) => s.outerHTML.slice(0, 60)),
      sinNombre: [...document.querySelectorAll<HTMLElement>('button, a.btn')]
        .filter((b) => b.offsetParent !== null)
        .filter((b) => (b.getAttribute('aria-label') || b.getAttribute('title') || (b.textContent ?? '').trim()) === '')
        .map((b) => b.outerHTML.slice(0, 80)),
    }));
    expect(resultado.visibles).toEqual([]);
    expect(resultado.sinNombre).toEqual([]);
  });
});

test.describe('idioma y anchos', () => {
  test('en inglés los tags llevan su icono y su clase', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    await montarApiMowaMes(page, conVersiones());
    await page.goto(RUTA);
    await page.locator('[data-deshabilitadas] summary').click();

    await expect(fila(page, 1).locator('.tag', { hasText: 'Original' })).toHaveClass(/tag--info/);
    await expect(fila(page, 3).locator('.tag', { hasText: 'Disabled' })).toHaveClass(/tag--neutral/);
    await expect(fila(page, 3).locator('.tag svg')).toHaveCount(1);
  });

  test('a 360 px los tags y los botones de la fila no desbordan', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    await abrir(page);

    const desborde = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(desborde).toBeLessThanOrEqual(0);
    for (const tag of await fila(page, 1).locator('.tag').all()) {
      const caja = (await tag.boundingBox())!;
      expect(caja.x).toBeGreaterThanOrEqual(0);
      expect(caja.x + caja.width).toBeLessThanOrEqual(361);
    }
  });

  for (const tema of ['light', 'dark'] as const) {
    for (const ancho of [1280, 360]) {
      test(`sin violaciones WCAG a ${ancho} px, tema ${tema === 'light' ? 'claro' : 'oscuro'}, con los dos tags`, async ({ page }) => {
        await page.addInitScript((elegido) => {
          localStorage.setItem('app:appearance', JSON.stringify({ theme: elegido, language: 'es' }));
        }, tema);
        await page.setViewportSize({ width: ancho, height: 900 });
        await abrir(page);

        const resultado = await new AxeBuilder({ page }).withTags(REGLAS).analyze();
        expect(resultado.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
      });
    }
  }
});

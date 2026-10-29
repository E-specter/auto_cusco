/**
 * The frame every screen shares (`.page`, T-MM-C10 L-F11): a column in the shell's width, centred, with the
 * shell's gutter, and a head (`.page__head`, title and intro) whose children start at the left.
 *
 * Nine screens had their own copy of these rules (and one of them, Columnas, a different one: 80rem). Now
 * they are one, so the same geometry has to hold in all of them, on a wide screen and on a phone.
 */
import { expect, test, type Page } from '@playwright/test';

import { apiSupervisionCalendario, apiVacia, montarApi, montarApiSupervisionCalendario } from './api-falsa';
import { apiMowaMes, montarApiMowaMes } from './api-falsa-mowa-mes';

test.use({ reducedMotion: 'reduce', timezoneId: 'America/Lima' });

interface Pantalla {
  nombre: string;
  ruta: string;
  /** The h1 sits in a `.page__head`; the console's is the ruler's title, on purpose. */
  conCabecera: boolean;
  montar: (page: Page) => Promise<void>;
}

const sinDatos = (page: Page) => montarApi(page, apiVacia());
const conMowaMes = (page: Page) => montarApiMowaMes(page, apiMowaMes());
const conSupervision = (page: Page) => montarApiSupervisionCalendario(page, apiSupervisionCalendario());

const PANTALLAS: Pantalla[] = [
  { nombre: 'Cargas', ruta: '/cargas', conCabecera: false, montar: sinDatos },
  { nombre: 'Cartera', ruta: '/cartera', conCabecera: true, montar: sinDatos },
  { nombre: 'Generar carga', ruta: '/generar-carga', conCabecera: true, montar: sinDatos },
  { nombre: 'Columnas', ruta: '/columnas', conCabecera: true, montar: sinDatos },
  { nombre: 'Campaña de MOWA MES', ruta: '/mowa-mes/campana', conCabecera: true, montar: conMowaMes },
  { nombre: 'Seguimiento de MOWA MES', ruta: '/mowa-mes/seguimiento', conCabecera: true, montar: conMowaMes },
  { nombre: 'Configuración de MOWA MES', ruta: '/mowa-mes/configuracion', conCabecera: true, montar: conMowaMes },
  { nombre: 'Supervisores', ruta: '/supervisores', conCabecera: true, montar: conSupervision },
  { nombre: 'Calendario', ruta: '/calendario', conCabecera: true, montar: conSupervision },
];

/** The shell's own measures, in px: a probe takes them from the tokens, so the test never copies a number. */
async function medidas(page: Page): Promise<{ maximo: number; gutter: number; espacio: number }> {
  return page.evaluate(() => {
    const medir = (token: string) => {
      const sonda = document.createElement('div');
      sonda.style.cssText = `position:absolute;visibility:hidden;inline-size:var(${token})`;
      document.body.append(sonda);
      const ancho = sonda.getBoundingClientRect().width;
      sonda.remove();
      return ancho;
    };
    return { maximo: medir('--shell-max'), gutter: medir('--shell-gutter'), espacio: medir('--space-4') };
  });
}

for (const pantalla of PANTALLAS) {
  test.describe(pantalla.nombre, () => {
    test('en pantalla ancha (1920 px) el marco mide el ancho del shell y queda centrado', async ({ page }) => {
      await page.setViewportSize({ width: 1920, height: 900 });
      await pantalla.montar(page);
      await page.goto(pantalla.ruta);
      const marco = page.locator('.page');
      await expect(marco).toHaveCount(1);

      const { maximo } = await medidas(page);
      const caja = (await marco.boundingBox())!;
      // Centred in the shell's `<main>` (a classic scrollbar takes a few px off the window's width).
      const principal = (await page.locator('main').boundingBox())!;
      expect(Math.abs(caja.width - maximo)).toBeLessThanOrEqual(1);
      expect(Math.abs(caja.x - (principal.x + (principal.width - maximo) / 2))).toBeLessThanOrEqual(1);
    });

    test('a 360 px llena el ancho, con el gutter del shell a cada lado y sin desbordar', async ({ page }) => {
      await page.setViewportSize({ width: 360, height: 900 });
      await pantalla.montar(page);
      await page.goto(pantalla.ruta);
      const marco = page.locator('.page');
      await expect(marco).toHaveCount(1);

      const { gutter } = await medidas(page);
      const caja = (await marco.boundingBox())!;
      const principal = (await page.locator('main').boundingBox())!;
      expect(Math.abs(caja.width - principal.width)).toBeLessThanOrEqual(1);
      const relleno = await marco.evaluate((el) => {
        const estilo = getComputedStyle(el);
        return { inicio: parseFloat(estilo.paddingInlineStart), fin: parseFloat(estilo.paddingInlineEnd) };
      });
      expect(relleno.inicio).toBeCloseTo(gutter, 0);
      expect(relleno.fin).toBeCloseTo(gutter, 0);
      const desborde = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(desborde).toBeLessThanOrEqual(0);
    });

    test('es una columna con el espacio del shell entre sus bloques', async ({ page }) => {
      await pantalla.montar(page);
      await page.goto(pantalla.ruta);
      const marco = page.locator('.page');
      await expect(marco).toHaveCount(1);

      const { espacio } = await medidas(page);
      const estilo = await marco.evaluate((el) => {
        const e = getComputedStyle(el);
        return { display: e.display, direccion: e.flexDirection, hueco: parseFloat(e.rowGap) };
      });
      expect(estilo.display).toBe('flex');
      expect(estilo.direccion).toBe('column');
      expect(estilo.hueco).toBeCloseTo(espacio, 0);
    });

    if (pantalla.conCabecera) {
      test('la cabecera: título e introducción nacen a la izquierda y el título es el h1', async ({ page }) => {
        await pantalla.montar(page);
        await page.goto(pantalla.ruta);
        const cabecera = page.locator('.page > .page__head');
        await expect(cabecera).toHaveCount(1);

        expect(await cabecera.evaluate((el) => getComputedStyle(el).alignItems)).toBe('flex-start');
        await expect(cabecera.locator('h1.page__title')).toHaveCount(1);
        const titulo = (await cabecera.locator('.page__title').boundingBox())!;
        const marco = (await page.locator('.page').boundingBox())!;
        const { gutter } = await medidas(page);
        expect(Math.abs(titulo.x - (marco.x + gutter))).toBeLessThanOrEqual(1);
        // The intro keeps its reading measure: it never spans the whole page.
        const intro = cabecera.locator('.page__intro');
        if ((await intro.count()) > 0) {
          const caja = (await intro.boundingBox())!;
          expect(caja.width).toBeLessThanOrEqual(marco.width);
        }
      });
    }
  });
}

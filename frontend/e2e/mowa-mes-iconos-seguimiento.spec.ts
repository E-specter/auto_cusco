/**
 * The icons of the follow-up (RF-MM-36, T-MM-C11 M-F7a; docs/mowa-mes-interfaz.md §3 and §4.1): the gauge and the
 * usage bar of the monthly limit, and the catalogue's icons on the figures, actions and tags of the detail. Nothing
 * here adds a word: an icon goes before its text, is decorative (`aria-hidden`), takes its colour from the text, and the
 * same concept carries the same icon wherever it appears. Every value is synthetic.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Locator, type Page } from '@playwright/test';

import {
  DESCARTADA_EN,
  apiMowaMes,
  campanaSintetica,
  consumoSintetico,
  montarApiMowaMes,
  type ApiFalsaMowaMes,
} from './api-falsa-mowa-mes';

test.use({ timezoneId: 'America/Lima', reducedMotion: 'reduce' });

const REGLAS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];
const LIMITE = 2_500_000;

function conUso(cargados: number): ApiFalsaMowaMes {
  const api = apiMowaMes();
  api.consumo = (mes) =>
    consumoSintetico(mes, {
      limite: LIMITE,
      cargados_mes: cargados,
      total: cargados,
      disponible: LIMITE - cargados,
      excedido: cargados > LIMITE,
    });
  return api;
}

async function abrir(page: Page, api: ApiFalsaMowaMes, busqueda = ''): Promise<void> {
  await montarApiMowaMes(page, api);
  await page.goto(`/mowa-mes/seguimiento${busqueda}`);
  await expect(page.getByRole('heading', { name: 'Seguimiento de MOWA MES', level: 1 })).toBeVisible();
  await expect(page.locator('[data-limite-cifras] .stat').first()).toBeVisible();
}

const barra = (page: Page) => page.locator('[data-limite-barra]');
const etiqueta = (page: Page, texto: string) => page.locator('[data-detalle-cifras] .stat__label', { hasText: texto });
const titulo = (page: Page) => page.locator('#mm-limite-title');

/** The colour a token paints, as the browser resolves it (so the test follows the theme and the tokens). */
async function colorDe(page: Page, token: string): Promise<string> {
  return page.evaluate((valor) => {
    const sonda = document.createElement('div');
    sonda.style.backgroundColor = `var(${valor})`;
    document.body.append(sonda);
    const color = getComputedStyle(sonda).backgroundColor;
    sonda.remove();
    return color;
  }, token);
}

const fondo = (nodo: Locator) => nodo.evaluate((el) => getComputedStyle(el).backgroundColor);
/** The drawing of an icon: two icons are the same one if they draw the same. */
const dibujo = (nodo: Locator) => nodo.evaluate((el) => el.innerHTML);

test.describe('el límite mensual', () => {
  test('el título lleva el medidor (gauge), a 20 px, antes del texto', async ({ page }) => {
    await abrir(page, conUso(625_000));

    await expect(titulo(page)).toHaveText('Límite mensual');
    await expect(titulo(page).locator('svg')).toHaveCount(1);
    await expect(titulo(page).locator('svg')).toHaveAttribute('aria-hidden', 'true');
    const caja = (await titulo(page).locator('svg').boundingBox())!;
    expect(Math.round(caja.width)).toBe(20);
    expect(Math.round(caja.height)).toBe(20);
    // The icon comes first.
    const iconoAntes = await titulo(page).evaluate((el) => el.firstElementChild?.tagName.toLowerCase());
    expect(iconoAntes).toBe('svg');
  });

  test('es el único título de panel con icono', async ({ page }) => {
    await abrir(page, conUso(625_000));

    await expect(page.locator('#mm-campanas-title svg')).toHaveCount(0);
    await expect(page.locator('#mm-detalle-title svg')).toHaveCount(0);
  });

  test('las cifras del medidor no llevan icono: las explica el medidor', async ({ page }) => {
    await abrir(page, conUso(625_000));

    await expect(page.locator('[data-limite-cifras] .stat')).toHaveCount(4);
    await expect(page.locator('[data-limite-cifras] svg')).toHaveCount(0);
  });

  test('la barra es decorativa: aria-hidden, sin nada que se enfoque ni se lea', async ({ page }) => {
    await abrir(page, conUso(625_000));

    const contenedor = page.locator('.mm-uso');
    await expect(contenedor).toHaveAttribute('aria-hidden', 'true');
    await expect(contenedor.locator('button, a, input, [tabindex]')).toHaveCount(0);
    expect((await contenedor.textContent())?.trim()).toBe('');
    // What is read is the figure.
    await expect(page.locator('[data-limite-cifras] .stat', { hasText: 'Uso del límite' }).locator('.stat__value')).toHaveText('25%');
  });

  test('con un uso bajo (25%) el relleno es el 25% de la barra, en el color de acento', async ({ page }) => {
    await abrir(page, conUso(625_000));

    await expect(barra(page)).toHaveAttribute('data-tono', 'normal');
    const ancho = await barra(page).evaluate((el) => (el.getBoundingClientRect().width / el.parentElement!.getBoundingClientRect().width) * 100);
    expect(ancho).toBeGreaterThan(24.5);
    expect(ancho).toBeLessThan(25.5);
    expect(await fondo(barra(page))).toBe(await colorDe(page, '--color-accent'));
  });

  test('con el 95% se acerca: el relleno es el color de señal', async ({ page }) => {
    await abrir(page, conUso(2_375_000));

    await expect(barra(page)).toHaveAttribute('data-tono', 'cerca');
    expect(await fondo(barra(page))).toBe(await colorDe(page, '--color-signal'));
    await expect(page.locator('[data-limite-excedido]')).toBeHidden();
  });

  test('por encima del 100% el relleno es el de peligro, no se sale de la barra, y sale el aviso de exceso', async ({ page }) => {
    await abrir(page, conUso(2_600_000));

    await expect(barra(page)).toHaveAttribute('data-tono', 'excedido');
    expect(await fondo(barra(page))).toBe(await colorDe(page, '--color-danger'));
    const anchos = await barra(page).evaluate((el) => ({
      relleno: Math.round(el.getBoundingClientRect().width),
      barra: Math.round(el.parentElement!.getBoundingClientRect().width),
    }));
    expect(anchos.relleno).toBe(anchos.barra);
    await expect(page.locator('[data-limite-excedido]')).toBeVisible();
  });

  test('el 100% justo es «se acerca», todavía no un exceso', async ({ page }) => {
    await abrir(page, conUso(LIMITE));

    await expect(barra(page)).toHaveAttribute('data-tono', 'cerca');
  });

  test('el borde del 90% ya se acerca, y justo debajo no', async ({ page }) => {
    await abrir(page, conUso(2_250_000));
    await expect(barra(page)).toHaveAttribute('data-tono', 'cerca');

    const debajo = await page.context().newPage();
    await montarApiMowaMes(debajo, conUso(2_249_999));
    await debajo.goto('/mowa-mes/seguimiento');
    await expect(debajo.locator('[data-limite-cifras] .stat').first()).toBeVisible();
    await expect(debajo.locator('[data-limite-barra]')).toHaveAttribute('data-tono', 'normal');
    await debajo.close();
  });

  test('cambiar de mes repinta la barra con el consumo de ese mes', async ({ page }) => {
    const api = apiMowaMes();
    api.consumo = (mes) => {
      const hoy = new Date();
      const actual = `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, '0')}`;
      const cargados = mes === actual ? 625_000 : 2_600_000;
      return consumoSintetico(mes, { limite: LIMITE, cargados_mes: cargados, total: cargados, disponible: LIMITE - cargados, excedido: cargados > LIMITE });
    };
    await abrir(page, api);
    await expect(barra(page)).toHaveAttribute('data-tono', 'normal');

    await page.getByRole('button', { name: 'Mes anterior' }).click();

    await expect(barra(page)).toHaveAttribute('data-tono', 'excedido');
  });

  test('«Costo del mes» lleva su moneda (coins) y el texto sigue igual', async ({ page }) => {
    await abrir(page, conUso(625_000));

    await expect(page.locator('[data-costo-mes] svg')).toHaveCount(1);
    await expect(page.locator('[data-costo-mes] svg')).toHaveAttribute('aria-hidden', 'true');
    await expect(page.locator('[data-costo-mes]')).toHaveText(/^Costo del mes: S\/ /);
  });
});

test.describe('los iconos del detalle', () => {
  test('las cifras del catálogo llevan su icono antes del texto; Productos, que no está, no', async ({ page }) => {
    await abrir(page, apiMowaMes());
    await expect(page.locator('[data-detalle-cifras] .stat')).not.toHaveCount(0);

    for (const texto of ['Supervisión', 'Total cargados', 'Excluidos', 'Con advertencia', 'Costo estimado', 'Costo real']) {
      const nodo = etiqueta(page, texto);
      await expect(nodo.locator('svg'), texto).toHaveCount(1);
      await expect(nodo.locator('svg'), texto).toHaveAttribute('aria-hidden', 'true');
      expect(await nodo.evaluate((el) => el.firstElementChild?.tagName.toLowerCase()), texto).toBe('svg');
    }
    await expect(etiqueta(page, 'Productos').locator('svg')).toHaveCount(0);
  });

  test('el icono no cambia las palabras de la etiqueta', async ({ page }) => {
    await abrir(page, apiMowaMes());

    await expect(etiqueta(page, 'Excluidos')).toHaveText('Excluidos');
    await expect(etiqueta(page, 'Total cargados')).toHaveText('Total cargados');
    await expect(etiqueta(page, 'Costo real')).toHaveText('Costo real');
  });

  test('un concepto, un icono: el costo es el mismo en la cifra, en la otra cifra y en el del mes', async ({ page }) => {
    await abrir(page, apiMowaMes());

    const estimado = await dibujo(etiqueta(page, 'Costo estimado').locator('svg'));
    expect(await dibujo(etiqueta(page, 'Costo real').locator('svg'))).toBe(estimado);
    expect(await dibujo(page.locator('[data-costo-mes] svg'))).toBe(estimado);
    // And it is not the one of another concept.
    expect(await dibujo(etiqueta(page, 'Excluidos').locator('svg'))).not.toBe(estimado);
    expect(await dibujo(etiqueta(page, 'Supervisión').locator('svg'))).not.toBe(await dibujo(etiqueta(page, 'Total cargados').locator('svg')));
  });

  test('un concepto, un icono: excluidos es el mismo en la cifra y en la sección; «Con advertencia», el de los avisos', async ({ page }) => {
    await abrir(page, apiMowaMes());

    const seccion = page.getByRole('heading', { name: 'Exclusiones', level: 3 });
    await expect(seccion.locator('svg')).toHaveCount(1);
    expect(await dibujo(seccion.locator('svg'))).toBe(await dibujo(etiqueta(page, 'Excluidos').locator('svg')));
    // The warning icon of a notice (the pending one of the detail) is the one of the «Con advertencia» figure.
    expect(await dibujo(page.locator('[data-pendiente-aviso] svg').first())).toBe(await dibujo(etiqueta(page, 'Con advertencia').locator('svg')));
  });

  test('«Archivos de carga» lleva files; cada «Descargar», download', async ({ page }) => {
    await abrir(page, apiMowaMes());

    const archivos = page.getByRole('heading', { name: 'Archivos de carga', level: 3 });
    await expect(archivos.locator('svg')).toHaveCount(1);
    await expect(archivos.locator('svg')).toHaveAttribute('aria-hidden', 'true');
    const descargar = page.getByRole('button', { name: 'Descargar el archivo 1' });
    await expect(descargar.locator('svg')).toHaveCount(1);
    await expect(descargar).toContainText('Descargar');
  });

  test('«Ver» lleva eye, y «Importar reporte», upload (el mismo que el aviso de pendiente)', async ({ page }) => {
    await abrir(page, apiMowaMes());

    const ver = page.getByRole('button', { name: 'Ver la campaña 1' });
    await expect(ver.locator('svg')).toHaveCount(1);
    await expect(ver).toContainText('Ver');
    const importar = page.getByRole('button', { name: 'Importar reporte' });
    await expect(importar.locator('svg')).toHaveCount(1);
    expect(await dibujo(importar.locator('svg'))).toBe(await dibujo(page.locator('[data-pendiente-importar] svg')));
  });

  test('los iconos que ya estaban siguen: Pendiente, Descartar, y en la vista de descartadas Restaurar y Eliminar', async ({ page }) => {
    const api = apiMowaMes();
    api.campanas = [
      campanaSintetica({ id: 2, descripcion: 'Campaña sintética 2', pendiente_reporte: true }),
      campanaSintetica({ id: 1, descripcion: 'Campaña sintética 1', descartada_en: DESCARTADA_EN, mes_imputacion: '2026-09' }),
    ];
    await abrir(page, api);

    await expect(page.locator('.mm-campanas__tabla .tag svg')).toHaveCount(1);
    await expect(page.getByRole('button', { name: 'Descartar la campaña 2' }).locator('svg')).toHaveCount(1);

    await page.getByRole('button', { name: /^Descartadas \(/ }).click();
    await expect(page.getByRole('button', { name: 'Restaurar la campaña 1' }).locator('svg')).toHaveCount(1);
    await expect(page.getByRole('button', { name: 'Eliminar definitivamente la campaña 1' }).locator('svg')).toHaveCount(1);
    await expect(page.locator('.mm-campanas__tabla .tag svg')).toHaveCount(1);
    await expect(page.getByLabel('Mes de gestión').locator('xpath=ancestor::div[contains(@class,"field")]').locator('label svg')).toHaveCount(1);
  });

  test('el icono de un tag mide 1,2 veces su texto, no 16 px', async ({ page }) => {
    await abrir(page, apiMowaMes());

    const tag = page.locator('.mm-campanas__tabla .tag').first();
    const medidas = await tag.evaluate((el) => {
      const icono = el.querySelector('svg')!.getBoundingClientRect();
      return { icono: icono.width, alto: icono.height, texto: parseFloat(getComputedStyle(el).fontSize) };
    });
    expect(Math.abs(medidas.icono - medidas.texto * 1.2)).toBeLessThan(0.6);
    expect(Math.abs(medidas.alto - medidas.texto * 1.2)).toBeLessThan(0.6);
  });

  test('ningún botón queda solo con icono y sin nombre', async ({ page }) => {
    const api = apiMowaMes();
    api.campanas = [campanaSintetica({ id: 2, pendiente_reporte: true }), campanaSintetica({ id: 1, descartada_en: DESCARTADA_EN })];
    await abrir(page, api);

    const sinNombre = await page.evaluate(() =>
      [...document.querySelectorAll<HTMLElement>('button, a.btn')]
        .filter((b) => b.offsetParent !== null)
        .filter((b) => {
          const nombre = b.getAttribute('aria-label') || b.getAttribute('title') || (b.textContent ?? '').trim();
          return nombre === '';
        })
        .map((b) => b.outerHTML.slice(0, 80)),
    );
    expect(sinNombre).toEqual([]);
  });

  test('todos los iconos del seguimiento son decorativos (aria-hidden)', async ({ page }) => {
    await abrir(page, apiMowaMes());

    const visibles = await page.evaluate(() =>
      [...document.querySelectorAll<SVGElement>('main svg, .page svg')]
        .filter((s) => s.getBoundingClientRect().width > 0)
        .filter((s) => s.getAttribute('aria-hidden') !== 'true')
        .map((s) => s.outerHTML.slice(0, 60)),
    );
    expect(visibles).toEqual([]);
  });
});

test.describe('idioma y anchos', () => {
  test('en inglés los iconos siguen y las palabras son las de siempre', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    await montarApiMowaMes(page, conUso(2_600_000));
    await page.goto('/mowa-mes/seguimiento');
    await expect(page.locator('[data-limite-cifras] .stat').first()).toBeVisible();

    await expect(page.locator('#mm-limite-title')).toHaveText('Monthly limit');
    await expect(page.locator('#mm-limite-title svg')).toHaveCount(1);
    await expect(page.locator('[data-limite-barra]')).toHaveAttribute('data-tono', 'excedido');
    await expect(page.locator('[data-detalle-cifras] .stat__label svg')).not.toHaveCount(0);
  });

  test('a 360 px la barra ocupa el ancho del panel y nada desborda', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    await abrir(page, conUso(2_375_000));

    const medidas = await page.evaluate(() => {
      const contenedor = document.querySelector('.mm-uso')!.getBoundingClientRect();
      const cuerpo = document.querySelector('.mm-uso')!.closest('.panel__body')!.getBoundingClientRect();
      return { barra: contenedor.width, cuerpo: cuerpo.width };
    });
    expect(medidas.barra).toBeGreaterThan(medidas.cuerpo - 40);
    expect(medidas.barra).toBeLessThanOrEqual(medidas.cuerpo);
    const desborde = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(desborde).toBeLessThanOrEqual(0);
  });

  test('a 360 px una etiqueta larga con icono se parte sin que el icono se aplaste ni se desborde', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    await abrir(page, apiMowaMes());

    const etiquetaLarga = etiqueta(page, 'Costo estimado');
    const caja = (await etiquetaLarga.locator('svg').boundingBox())!;
    expect(Math.round(caja.width)).toBe(16);
    expect(Math.round(caja.height)).toBe(16);
    const desborde = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(desborde).toBeLessThanOrEqual(0);
  });

  for (const tema of ['light', 'dark'] as const) {
    for (const ancho of [1280, 360]) {
      test(`sin violaciones WCAG a ${ancho} px, tema ${tema === 'light' ? 'claro' : 'oscuro'}, con la barra en sus tres tonos`, async ({ page }) => {
        await page.addInitScript((elegido) => {
          localStorage.setItem('app:appearance', JSON.stringify({ theme: elegido, language: 'es' }));
        }, tema);
        await page.setViewportSize({ width: ancho, height: 900 });

        for (const cargados of [625_000, 2_375_000, 2_600_000]) {
          const api = conUso(cargados);
          await montarApiMowaMes(page, api);
          await page.goto('/mowa-mes/seguimiento');
          await expect(page.locator('[data-limite-cifras] .stat').first()).toBeVisible();
          await expect(page.locator('[data-detalle-cifras] .stat').first()).toBeVisible();
          const resultado = await new AxeBuilder({ page }).withTags(REGLAS).analyze();
          expect(
            resultado.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`),
            `cargados ${cargados}`,
          ).toEqual([]);
          await page.unrouteAll({ behavior: 'ignoreErrors' });
        }
      });
    }
  }
});

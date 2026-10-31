/**
 * The icons of the campaign (RF-MM-36, T-MM-C11 M-F7b; docs/mowa-mes-interfaz.md §3): the catalogue's icons on the
 * preview's figures and sections. Nothing here adds a word: an icon goes before its text, is decorative
 * (`aria-hidden`), and the same concept carries the same icon as in the follow-up. The icons the other cuts put
 * (copy, download, editing in Cartera, upload) stay as they were. Every value is synthetic.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Locator, type Page } from '@playwright/test';

import { seleccionGuardada } from './api-falsa';
import { apiMowaMes, montarApiMowaMes } from './api-falsa-mowa-mes';
import { montarSeleccion, seleccionFalsa } from './apoyo-seleccion';

test.use({ timezoneId: 'America/Lima', reducedMotion: 'reduce' });

const REGLAS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];
const RUTA = '/mowa-mes/campana';

async function abrirConPrevia(page: Page): Promise<void> {
  await montarApiMowaMes(page, apiMowaMes());
  await montarSeleccion(page, seleccionFalsa({ selecciones: [seleccionGuardada({ id: 1, nombre: 'Preventiva top 1000', cantidad: 1000 })] }));
  await page.goto(RUTA);
  await expect(page.getByRole('heading', { name: 'Campaña de MOWA MES', level: 1 })).toBeVisible();
  await page.getByLabel('Selección guardada').selectOption({ label: 'Preventiva top 1000' });
  await expect(page.locator('[data-cifras] .stat').first()).toBeVisible();
}

const etiqueta = (page: Page, texto: string) => page.locator('[data-cifras] .stat__label', { hasText: texto });
/** The drawing of an icon: two icons are the same one if they draw the same. */
const dibujo = (nodo: Locator) => nodo.evaluate((el) => el.innerHTML);

test.describe('las cifras de la previsualización', () => {
  test('las del catálogo llevan su icono antes del texto, decorativo', async ({ page }) => {
    await abrirConPrevia(page);

    for (const texto of ['Supervisión', 'Total cargados', 'Excluidos', 'Costo estimado']) {
      const nodo = etiqueta(page, texto);
      await expect(nodo.locator('svg'), texto).toHaveCount(1);
      await expect(nodo.locator('svg'), texto).toHaveAttribute('aria-hidden', 'true');
      expect(await nodo.evaluate((el) => el.firstElementChild?.tagName.toLowerCase()), texto).toBe('svg');
    }
  });

  test('las que el catálogo no nombra no llevan: disponibles, solicitados, evaluados y productos', async ({ page }) => {
    await abrirConPrevia(page);

    for (const texto of ['Disponibles', 'Solicitados', 'Evaluados', 'Productos']) {
      await expect(etiqueta(page, texto).locator('svg'), texto).toHaveCount(0);
    }
  });

  test('el icono no cambia las palabras de la etiqueta', async ({ page }) => {
    await abrirConPrevia(page);

    await expect(etiqueta(page, 'Total cargados')).toHaveText('Total cargados');
    await expect(etiqueta(page, 'Excluidos')).toHaveText('Excluidos');
    await expect(etiqueta(page, 'Costo estimado')).toHaveText('Costo estimado');
  });

  test('las cifras del consumo del mes no llevan icono: las explica el medidor', async ({ page }) => {
    await abrirConPrevia(page);

    await expect(page.locator('[data-limite-cifras] .stat')).toHaveCount(3);
    await expect(page.locator('[data-limite-cifras] svg')).toHaveCount(0);
  });

  test('un concepto, un icono: el de la campaña es el del seguimiento', async ({ page }) => {
    await abrirConPrevia(page);
    const enCampana = {
      supervision: await dibujo(etiqueta(page, 'Supervisión').locator('svg')),
      total: await dibujo(etiqueta(page, 'Total cargados').locator('svg')),
      excluidos: await dibujo(etiqueta(page, 'Excluidos').locator('svg')),
      costo: await dibujo(etiqueta(page, 'Costo estimado').locator('svg')),
    };

    await page.goto('/mowa-mes/seguimiento');
    await expect(page.locator('[data-detalle-cifras] .stat').first()).toBeVisible();
    const delDetalle = (texto: string) => page.locator('[data-detalle-cifras] .stat__label', { hasText: texto }).locator('svg');
    expect(await dibujo(delDetalle('Supervisión'))).toBe(enCampana.supervision);
    expect(await dibujo(delDetalle('Total cargados'))).toBe(enCampana.total);
    expect(await dibujo(delDetalle('Excluidos'))).toBe(enCampana.excluidos);
    expect(await dibujo(delDetalle('Costo estimado'))).toBe(enCampana.costo);
    // And they are four different drawings.
    expect(new Set(Object.values(enCampana)).size).toBe(4);
  });
});

test.describe('las secciones de la previsualización', () => {
  test('«Exclusiones» lleva ban, el mismo de la cifra «Excluidos», y su nombre sigue siendo el de siempre', async ({ page }) => {
    await abrirConPrevia(page);

    const seccion = page.locator('[data-exclusiones-titulo]');
    await expect(seccion.locator('svg')).toHaveCount(1);
    await expect(seccion.locator('svg')).toHaveAttribute('aria-hidden', 'true');
    expect(await dibujo(seccion.locator('svg'))).toBe(await dibujo(etiqueta(page, 'Excluidos').locator('svg')));
    await expect(page.getByRole('heading', { name: /^Exclusiones \d/, level: 3 })).toBeVisible();
  });

  test('«Archivos previstos» lleva files, decorativo, y su texto no cambia', async ({ page }) => {
    await abrirConPrevia(page);

    const seccion = page.getByRole('heading', { name: 'Archivos previstos', level: 3 });
    await expect(seccion).toBeVisible();
    await expect(seccion.locator('svg')).toHaveCount(1);
    await expect(seccion.locator('svg')).toHaveAttribute('aria-hidden', 'true');
  });

  test('los títulos de panel de la campaña no llevan icono: un título ya es un título', async ({ page }) => {
    await abrirConPrevia(page);

    await expect(page.locator('.panel__title svg')).toHaveCount(0);
  });
});

test.describe('lo que ya tenía icono se queda', () => {
  test('copiar la descripción lleva copy, y «Editar en Cartera», square-pen', async ({ page }) => {
    await abrirConPrevia(page);

    await expect(page.locator('[data-descripcion-copiar] svg')).toHaveCount(1);
    await expect(page.getByRole('button', { name: 'Editar en Cartera' }).locator('svg')).toHaveCount(1);
  });
});

test.describe('accesibilidad de los iconos', () => {
  test('todos los iconos de la campaña son decorativos (aria-hidden)', async ({ page }) => {
    await abrirConPrevia(page);

    const visibles = await page.evaluate(() =>
      [...document.querySelectorAll<SVGElement>('main svg, .page svg')]
        .filter((s) => s.getBoundingClientRect().width > 0)
        .filter((s) => s.getAttribute('aria-hidden') !== 'true')
        .map((s) => s.outerHTML.slice(0, 60)),
    );
    expect(visibles).toEqual([]);
  });

  test('ningún botón queda solo con icono y sin nombre', async ({ page }) => {
    await abrirConPrevia(page);

    const sinNombre = await page.evaluate(() =>
      [...document.querySelectorAll<HTMLElement>('button, a.btn')]
        .filter((b) => b.offsetParent !== null)
        .filter((b) => (b.getAttribute('aria-label') || b.getAttribute('title') || (b.textContent ?? '').trim()) === '')
        .map((b) => b.outerHTML.slice(0, 80)),
    );
    expect(sinNombre).toEqual([]);
  });
});

test.describe('idioma y anchos', () => {
  test('en inglés los iconos siguen y las palabras son las de siempre', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    await montarApiMowaMes(page, apiMowaMes());
    await montarSeleccion(page, seleccionFalsa({ selecciones: [seleccionGuardada({ id: 1, nombre: 'Preventiva top 1000', cantidad: 1000 })] }));
    await page.goto(RUTA);
    await page.getByLabel('Saved selection').selectOption({ label: 'Preventiva top 1000' });
    await expect(page.locator('[data-cifras] .stat').first()).toBeVisible();

    await expect(page.locator('[data-cifras] .stat__label svg')).toHaveCount(4);
    await expect(page.locator('[data-cifras] .stat__label', { hasText: 'Total loaded' })).toHaveText('Total loaded');
    await expect(page.getByRole('heading', { name: 'Expected files', level: 3 }).locator('svg')).toHaveCount(1);
  });

  test('a 360 px los iconos de las etiquetas miden 16 px, no desbordan y la sección no se parte mal', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    await abrirConPrevia(page);

    const caja = (await etiqueta(page, 'Costo estimado').locator('svg').boundingBox())!;
    expect(Math.round(caja.width)).toBe(16);
    expect(Math.round(caja.height)).toBe(16);
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
        await abrirConPrevia(page);

        const resultado = await new AxeBuilder({ page }).withTags(REGLAS).analyze();
        expect(resultado.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
      });
    }
  }
});

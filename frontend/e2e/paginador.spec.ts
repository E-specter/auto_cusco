/**
 * The pager every paged table shares (`.pager`, T-MM-C10 L-F9), in the four screens that page: the portfolio,
 * the load console's issues, the campaign's sample and the follow-up's campaigns.
 *
 * A wide screen keeps «Anteriores», the range and «Siguientes» on one line. A narrow one (360 px) puts the range
 * on top, centred, and the two buttons under it, one at each end: «Siguientes» never drops alone to a second
 * line next to the range. The range is announced when the page changes (`aria-live`).
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import { apiVacia, montarApi, productosSinteticos, version } from './api-falsa';
import { apiMowaMes, campanaSintetica, montarApiMowaMes, previsualizacionCampanaSintetica } from './api-falsa-mowa-mes';
import { montarSeleccion } from './apoyo-seleccion';

test.use({ reducedMotion: 'reduce', timezoneId: 'America/Lima' });

const REGLAS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

interface Pantalla {
  nombre: string;
  pager: string;
  abrir: (page: Page) => Promise<void>;
}

const PANTALLAS: Pantalla[] = [
  {
    nombre: 'Cartera',
    pager: '[data-pager]',
    abrir: async (page) => {
      const api = apiVacia();
      api.versiones = [version()];
      api.productos = productosSinteticos(120);
      await montarApi(page, api);
      await page.goto('/cartera');
      await expect(page.locator('.productos__tabla')).toBeVisible();
    },
  },
  {
    nombre: 'Cargas (la consola de incidencias)',
    pager: '[data-pager]',
    abrir: async (page) => {
      const api = apiVacia();
      api.versiones = [version()];
      api.incidencias = Array.from({ length: 120 }, (_, i) => ({
        fila: i + 2,
        columna: 'pagare',
        codigo: 'pagare_repetido',
        severidad: 'error' as const,
        detalle: 'x',
        valor_original: null,
      }));
      await montarApi(page, api);
      await page.goto('/cargas');
      await expect(page.getByRole('cell', { name: 'pagare_repetido' }).first()).toBeVisible();
    },
  },
  {
    nombre: 'Campaña (la muestra)',
    pager: '[data-muestra-pager]',
    abrir: async (page) => {
      const api = apiMowaMes();
      api.respuestas.previsualizarCampana = [
        {
          estado: 200,
          cuerpo: previsualizacionCampanaSintetica(
            {
              fecha_corte: '2026-09-13',
              filtros: [],
              cantidad: 1000,
              tipo_carga: 'masiva',
              salida: 'numero_largo',
              herramientas: { keyword: false, respuesta_automatica: false, blacklist_indecopi: false, speech_optimizado: false },
              programacion: 'hora_determinada',
              envios: ['2026-09-14T09:00:00-05:00'],
            },
            {
              muestra: Array.from({ length: 20 }, (_, i) => ({
                numero: `900000${String(i + 1).padStart(3, '0')}`,
                mensaje: `Mensaje sintetico ${i + 1}`,
                dni: `00${String(100000 + i)}`,
                supervision: false,
                pagare: `${'0'.repeat(14)}${String(1000 + i)}`,
                segmento: '9_a_30' as const,
                largo: 60,
                advertencias: [],
              })),
            },
          ),
        },
      ];
      await montarApiMowaMes(page, api);
      await montarSeleccion(page);
      await page.goto('/mowa-mes/campana');
      await page.getByLabel('Selección guardada').selectOption({ label: 'Preventiva top 1000' });
      await expect(page.locator('[data-muestra-pager]')).toBeVisible();
    },
  },
  {
    nombre: 'Seguimiento (las campañas)',
    pager: '[data-campanas-pager]',
    abrir: async (page) => {
      const api = apiMowaMes();
      api.campanas = Array.from({ length: 25 }, (_, i) => campanaSintetica({ id: 25 - i, descripcion: `Campaña sintética ${25 - i}` }));
      await montarApiMowaMes(page, api);
      await page.goto('/mowa-mes/seguimiento');
      await expect(page.locator('[data-campanas-pager]')).toBeVisible();
    },
  },
];

const caja = async (page: Page, selector: string) => (await page.locator(selector).boundingBox())!;

for (const pantalla of PANTALLAS) {
  test.describe(pantalla.nombre, () => {
    test('a 1280 px: «Anteriores», el rango y «Siguientes» en una sola línea, en ese orden', async ({ page }) => {
      await page.setViewportSize({ width: 1280, height: 900 });
      await pantalla.abrir(page);
      const pager = pantalla.pager;

      const [anterior, rango, siguiente] = await Promise.all([
        caja(page, `${pager} [data-page-prev]`),
        caja(page, `${pager} [data-page-range]`),
        caja(page, `${pager} [data-page-next]`),
      ]);
      const centro = (c: { y: number; height: number }) => c.y + c.height / 2;
      expect(Math.abs(centro(anterior) - centro(rango))).toBeLessThanOrEqual(2);
      expect(Math.abs(centro(siguiente) - centro(rango))).toBeLessThanOrEqual(2);
      expect(anterior.x + anterior.width).toBeLessThanOrEqual(rango.x + 1);
      expect(rango.x + rango.width).toBeLessThanOrEqual(siguiente.x + 1);
    });

    test('a 360 px: el rango arriba y centrado, y los dos botones en la misma fila, uno en cada extremo', async ({ page }) => {
      await page.setViewportSize({ width: 360, height: 900 });
      await pantalla.abrir(page);
      const pager = pantalla.pager;
      await page.locator(pager).scrollIntoViewIfNeeded();

      const [caja_, anterior, rango, siguiente] = await Promise.all([
        caja(page, pager),
        caja(page, `${pager} [data-page-prev]`),
        caja(page, `${pager} [data-page-range]`),
        caja(page, `${pager} [data-page-next]`),
      ]);
      // The range is above both buttons, which share a row.
      expect(rango.y + rango.height).toBeLessThanOrEqual(Math.min(anterior.y, siguiente.y) + 1);
      expect(Math.abs(anterior.y - siguiente.y)).toBeLessThanOrEqual(1);
      // One at each end, and the range fills the width, so its text is centred on the pager.
      expect(anterior.x).toBeLessThan(siguiente.x);
      expect(Math.abs(anterior.x - caja_.x)).toBeLessThanOrEqual(caja_.width * 0.1);
      expect(Math.abs(caja_.x + caja_.width - (siguiente.x + siguiente.width))).toBeLessThanOrEqual(caja_.width * 0.1);
      expect(Math.abs(rango.x + rango.width / 2 - (caja_.x + caja_.width / 2))).toBeLessThanOrEqual(2);
      // And the page does not scroll sideways.
      const desborde = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(desborde).toBeLessThanOrEqual(0);
    });

    test('el rango se anuncia al cambiar de página (aria-live) y los dos botones son botones', async ({ page }) => {
      await pantalla.abrir(page);

      const rango = page.locator(`${pantalla.pager} [data-page-range]`);
      await expect(rango).toHaveAttribute('aria-live', 'polite');
      await expect(page.locator(`${pantalla.pager} [data-page-prev]`)).toBeDisabled();
      await expect(page.getByRole('button', { name: 'Siguientes' }).first()).toBeEnabled();
    });

    for (const tema of ['light', 'dark'] as const) {
      test(`a 360 px, sin violaciones WCAG, tema ${tema === 'light' ? 'claro' : 'oscuro'}`, async ({ page }) => {
        await page.addInitScript((elegido) => {
          localStorage.setItem('app:appearance', JSON.stringify({ theme: elegido, language: 'es' }));
        }, tema);
        await page.setViewportSize({ width: 360, height: 900 });
        await pantalla.abrir(page);

        const resultado = await new AxeBuilder({ page }).withTags(REGLAS).analyze();
        expect(resultado.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
      });
    }
  });
}

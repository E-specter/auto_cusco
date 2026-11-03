/**
 * The working-day calendar (`/calendario`), end to end against an intercepted API. The screen used to
 * live inside the MOWA MES configuration; the cases are the same, moved with it (T-MM-C10, L-F7).
 * A law holiday is withdrawn with an exception, never deleted.
 */
import { expect, test, type Page } from '@playwright/test';

import {
  apiSupervisionCalendario,
  montarApiSupervisionCalendario,
  type ApiFalsaSupervisionCalendario,
} from './api-falsa';

const RUTA = '/calendario';
/**
 * The clock the page runs on. Node's own year is not used: on a runner in UTC it is already the next year on 31 Dec
 * from 19:00 in Lima, where the browser still is. `setFixedTime` keeps the timers running.
 */
const AHORA = '2026-10-15T12:00:00-05:00';
const ANIO = Number(AHORA.slice(0, 4));

test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(new Date(AHORA));
});

/** Requests to exactly `ruta` (query ignored); a trailing `/` matches any id under it. */
const pedidosA = (api: ApiFalsaSupervisionCalendario, metodo: string, ruta: string) =>
  api.pedidos.filter((p) => {
    const camino = p.ruta.split('?')[0];
    return p.metodo === metodo && (ruta.endsWith('/') ? camino.startsWith(ruta) : camino === ruta);
  });

async function abrir(page: Page, api: ApiFalsaSupervisionCalendario): Promise<void> {
  await montarApiSupervisionCalendario(page, api);
  await page.goto(RUTA);
  await expect(page.getByRole('heading', { name: 'Calendario laboral', level: 1 })).toBeVisible();
  await expect(page.getByRole('rowheader', { name: new RegExp(`01 ene\\.? ${ANIO}`) })).toBeVisible();
}

test.describe('carga inicial', () => {
  test('muestra el título, la introducción, el año, los días y el siguiente día gestionable', async ({ page }) => {
    const api = apiSupervisionCalendario();
    await abrir(page, api);

    await expect(page.getByText(/Los feriados de ley se calculan solos/)).toBeVisible();
    // The panel's title says what is inside, not the h1 again.
    await expect(page.getByRole('heading', { name: 'Feriados y días no laborables', level: 2 })).toBeVisible();
    await expect(page.locator('[data-anio]')).toHaveText(String(ANIO));
    await expect(page.getByText('Retirado este año')).toBeVisible();
    await expect(page.getByText(/Siguiente día gestionable desde hoy/)).toBeVisible();
  });

  test('sin conexión con la API muestra el aviso en vez de un panel vacío', async ({ page }) => {
    const api = apiSupervisionCalendario();
    api.sinRed = true;
    await montarApiSupervisionCalendario(page, api);
    await page.goto(RUTA);

    await expect(page.getByRole('heading', { name: 'Sin conexión con la API' })).toBeVisible();
    await expect(page.locator('[data-contenido]')).toBeHidden();
  });

  test('en inglés traduce el título y los días', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    await montarApiSupervisionCalendario(page, apiSupervisionCalendario());
    await page.goto(RUTA);

    await expect(page.getByRole('heading', { name: 'Working calendar', level: 1 })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Holidays and non-working days', level: 2 })).toBeVisible();
    await expect(page.getByText('Withdrawn this year')).toBeVisible();
  });
});

test.describe('a 360 px', () => {
  test('la tabla se apila y nada se sale de su panel ni de la página', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 780 });
    await abrir(page, apiSupervisionCalendario());

    const geometria = await page.evaluate(() => {
      const panel = document.querySelector('.table-scroll')!.getBoundingClientRect();
      const fuera = [...document.querySelectorAll('.calendario__tabla th, .calendario__tabla td, .calendario__tabla button')]
        .filter((n) => {
          const r = n.getBoundingClientRect();
          return r.width > 0 && (r.left < panel.left - 0.5 || r.right > panel.right + 0.5);
        })
        .length;
      return {
        pagina: document.documentElement.scrollWidth,
        vista: window.innerWidth,
        fuera,
        celdas: document.querySelectorAll('.calendario__tabla td[data-etiqueta]').length,
        sinEtiqueta: document.querySelectorAll('.calendario__tabla td:not([data-etiqueta])').length,
        // The text itself on one line (the cell's own height also holds the stacked label).
        fechaEnUnaLinea: [...document.querySelectorAll('.calendario__tabla tbody th')].every((n) => {
          const rango = document.createRange();
          rango.selectNodeContents(n);
          return new Set([...rango.getClientRects()].map((r) => Math.round(r.top))).size === 1;
        }),
      };
    });

    expect(geometria.pagina).toBeLessThanOrEqual(geometria.vista);
    expect(geometria.fuera).toBe(0);
    expect(geometria.celdas).toBeGreaterThan(0);
    expect(geometria.sinEtiqueta).toBe(0);
    expect(geometria.fechaEnUnaLinea).toBe(true);
  });
});

test.describe('días no laborables', () => {
  test('un feriado de ley se retira con una excepción, nunca se borra', async ({ page }) => {
    const api = apiSupervisionCalendario();
    await abrir(page, api);

    const fila = page.getByRole('row', { name: /Día del Trabajo/ });
    await fila.getByRole('button', { name: /Retirar el feriado/ }).click();

    const dialogo = page.getByRole('dialog', { name: 'Retirar «Día del Trabajo» este año' });
    // The date is the holiday clicked: read-only, and it looks it (sunken, unlike the editable motive).
    const fecha = dialogo.locator('input[type="date"]');
    await expect(fecha).not.toBeEditable();
    const fondo = (campo: typeof fecha) => campo.evaluate((e) => getComputedStyle(e).backgroundColor);
    expect(await fondo(fecha)).not.toBe(await fondo(dialogo.getByLabel('Motivo')));
    await dialogo.getByLabel('Motivo').fill('Decreto sintético');
    await dialogo.getByRole('button', { name: 'Retirar feriado' }).click();

    await expect(dialogo).toBeHidden();
    await expect(fila.getByText('Retirado este año')).toBeVisible();
    expect(pedidosA(api, 'POST', '/calendario/excepciones')[0].cuerpo).toEqual({
      fecha: `${ANIO}-05-01`,
      tipo: 'retirado',
      descripcion: 'Decreto sintético',
    });
    expect(pedidosA(api, 'DELETE', '/calendario/excepciones')).toEqual([]);
  });

  test('un día agregado se quita borrando su excepción', async ({ page }) => {
    const api = apiSupervisionCalendario();
    await abrir(page, api);

    await page.getByRole('button', { name: /Quitar el día no laborable/ }).click();

    await expect(page.getByRole('row', { name: /Día no laborable sintético/ })).toHaveCount(0);
    expect(pedidosA(api, 'DELETE', '/calendario/excepciones/').map((p) => p.ruta)).toEqual([
      `/calendario/excepciones/${ANIO}-12-24`,
    ]);
  });

  test('una fecha que ya tiene excepción responde 409 y se explica en el diálogo', async ({ page }) => {
    const api = apiSupervisionCalendario();
    api.respuestas.crearExcepcion = [{ estado: 409, cuerpo: { detail: 'repetida' } }];
    await abrir(page, api);

    await page.getByRole('button', { name: 'Agregar día no laborable' }).click();
    const dialogo = page.getByRole('dialog', { name: 'Agregar un día no laborable' });
    await dialogo.getByLabel('Fecha').fill(`${ANIO}-11-02`);
    await dialogo.getByLabel('Descripción').fill('Día sintético');
    await dialogo.getByRole('button', { name: 'Agregar día' }).click();

    await expect(dialogo.getByText('Esa fecha ya tiene una excepción registrada.')).toBeVisible();
  });

  test('cambia de año', async ({ page }) => {
    const api = apiSupervisionCalendario();
    await abrir(page, api);

    await page.getByRole('button', { name: 'Año siguiente' }).click();

    await expect(page.locator('[data-anio]')).toHaveText(String(ANIO + 1));
    await expect(page.getByRole('rowheader', { name: new RegExp(`01 ene\\.? ${ANIO + 1}`) })).toBeVisible();
  });
});


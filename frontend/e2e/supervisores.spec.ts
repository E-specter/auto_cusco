/**
 * The default supervisors (`/supervisores`), end to end against an intercepted API. The screen used to
 * live inside the MOWA MES configuration; the cases are the same, moved with it (T-MM-C10, L-F7).
 * Every number is synthetic (900000xxx).
 */
import { expect, test, type Page } from '@playwright/test';

import {
  apiSupervisionCalendario,
  montarApiSupervisionCalendario,
  type ApiFalsaSupervisionCalendario,
} from './api-falsa';

const RUTA = '/supervisores';

/** Requests to exactly `ruta` (query ignored); a trailing `/` matches any id under it. */
const pedidosA = (api: ApiFalsaSupervisionCalendario, metodo: string, ruta: string) =>
  api.pedidos.filter((p) => {
    const camino = p.ruta.split('?')[0];
    return p.metodo === metodo && (ruta.endsWith('/') ? camino.startsWith(ruta) : camino === ruta);
  });

async function abrir(page: Page, api: ApiFalsaSupervisionCalendario): Promise<void> {
  await montarApiSupervisionCalendario(page, api);
  await page.goto(RUTA);
  await expect(page.getByRole('heading', { name: 'Supervisores', level: 1 })).toBeVisible();
  await expect(page.locator('[data-contenido]')).toBeVisible();
}

test.describe('carga inicial', () => {
  test('muestra el título, la introducción, las procedencias y los supervisores con su documento', async ({ page }) => {
    const api = apiSupervisionCalendario();
    await abrir(page, api);

    await expect(page.getByText('Los supervisores que se asignan por defecto a cada campaña, en todos los canales.')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Supervisores por defecto' })).toBeVisible();
    await expect(page.getByLabel('Número del supervisor 1')).toHaveValue('900000101');
    await expect(page.getByRole('cell', { name: '00000002' })).toBeVisible();
  });

  test('sin conexión con la API muestra el aviso en vez de un panel vacío', async ({ page }) => {
    const api = apiSupervisionCalendario();
    api.sinRed = true;
    await montarApiSupervisionCalendario(page, api);
    await page.goto(RUTA);

    await expect(page.getByRole('heading', { name: 'Sin conexión con la API' })).toBeVisible();
    await expect(page.locator('[data-contenido]')).toBeHidden();
  });

  test('en inglés traduce el título y la introducción', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    await montarApiSupervisionCalendario(page, apiSupervisionCalendario());
    await page.goto(RUTA);

    await expect(page.getByRole('heading', { name: 'Supervisors', level: 1 })).toBeVisible();
    await expect(page.getByText('The supervisors assigned by default to each campaign, in every channel.')).toBeVisible();
  });
});

test.describe('lista y guardado', () => {
  test('agrega un supervisor y guarda la lista completa, con los documentos que asigna la API', async ({ page }) => {
    const api = apiSupervisionCalendario();
    await abrir(page, api);

    await page.getByRole('button', { name: 'Agregar supervisor' }).click();
    await expect(page.getByText('Hay cambios sin guardar: los documentos se reasignan al guardar.')).toBeVisible();
    await page.getByLabel('Número del supervisor 3').fill('900000103');
    await page.getByLabel('Procedencia del supervisor 3').selectOption('Procedencia A');
    await page.getByRole('button', { name: 'Guardar supervisores' }).click();

    await expect(page.getByText('Guardado.')).toBeVisible();
    expect(pedidosA(api, 'PUT', '/supervisores')[0].cuerpo).toEqual({
      procedencias: ['Procedencia A', 'Procedencia B'],
      supervisores: [
        { numero: '900000101', procedencia: 'Procedencia A' },
        { numero: '900000102', procedencia: 'Procedencia B' },
        { numero: '900000103', procedencia: 'Procedencia A' },
      ],
    });
    // La numeración es de la API: primero Procedencia A, luego Procedencia B.
    await expect(page.locator('.supervisores__tabla tbody tr').nth(2).getByRole('cell', { name: '00000002' })).toBeVisible();
  });

  test('renombrar una procedencia arrastra a sus supervisores', async ({ page }) => {
    const api = apiSupervisionCalendario();
    await abrir(page, api);

    await page.getByLabel('Procedencia 1', { exact: true }).fill('Procedencia C');
    await expect(page.getByLabel('Procedencia del supervisor 1')).toHaveValue('Procedencia C');
  });

  test('un supervisor sin número se señala antes de llamar a la API', async ({ page }) => {
    const api = apiSupervisionCalendario();
    await abrir(page, api);

    await page.getByRole('button', { name: 'Agregar supervisor' }).click();
    await page.getByRole('button', { name: 'Guardar supervisores' }).click();

    await expect(page.getByText('El supervisor 3 no tiene número.')).toBeVisible();
    await expect(page.getByLabel('Número del supervisor 3')).toHaveAttribute('aria-invalid', 'true');
    expect(pedidosA(api, 'PUT', '/supervisores')).toEqual([]);
  });

  test('una procedencia de más de 60 caracteres dice el máximo, en español y en inglés', async ({ page }) => {
    const api = apiSupervisionCalendario();
    await abrir(page, api);

    await page.getByRole('textbox', { name: 'Procedencia 1', exact: true }).fill('x'.repeat(61));
    await page.getByRole('button', { name: 'Guardar supervisores' }).click();

    await expect(page.getByText('La procedencia 1 pasa de 60 caracteres.')).toBeVisible();
    expect(pedidosA(api, 'PUT', '/supervisores')).toEqual([]);

    const en = apiSupervisionCalendario();
    const paginaEn = await page.context().newPage();
    await paginaEn.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    await montarApiSupervisionCalendario(paginaEn, en);
    await paginaEn.goto(RUTA);
    await expect(paginaEn.getByRole('heading', { name: 'Supervisors', level: 1 })).toBeVisible();
    await paginaEn.getByRole('textbox', { name: 'Origin 1', exact: true }).fill('x'.repeat(61));
    await paginaEn.getByRole('button', { name: 'Save supervisors' }).click();
    await expect(paginaEn.getByText('Origin 1 is longer than 60 characters.')).toBeVisible();
    await paginaEn.close();
  });

  test('sin supervisores guardados avisa que no se podrá crear ninguna campaña', async ({ page }) => {
    const api = apiSupervisionCalendario();
    api.supervision = { procedencias: ['Procedencia A'], supervisores: [] };
    await abrir(page, api);

    await expect(page.getByText('Sin supervisores no se puede crear ninguna campaña.', { exact: false })).toBeVisible();
  });
});


test.describe('anchos (T-MM-F5, hallazgo 2)', () => {
  test('a 360 px, la tabla de supervisores se apila sin desbordar la página', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    const api = apiSupervisionCalendario();
    await abrir(page, api);

    const desborda = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
    expect(desborda).toBe(false);

    const sinDesbordeHorizontal = async (locator: ReturnType<Page['locator']>) => {
      await locator.scrollIntoViewIfNeeded();
      const caja = await locator.boundingBox();
      expect(caja).not.toBeNull();
      expect(caja!.x).toBeGreaterThanOrEqual(0);
      expect(caja!.x + caja!.width).toBeLessThanOrEqual(361);
    };

    // The supervisors table stacks below 48rem (`.table--apilable`):
    // Procedencia and Documento, cut off before F5, are now full rows.
    const filaSupervisor = page.locator('.supervisores__tabla tbody tr').first();
    const procedenciaEtiqueta = await filaSupervisor
      .locator('select')
      .evaluateHandle((el) => el.closest('td'))
      .then((handle) => handle.evaluate((td) => getComputedStyle(td as Element, '::before').content));
    expect(procedenciaEtiqueta).toContain('Procedencia');
    await sinDesbordeHorizontal(filaSupervisor.locator('select'));
    const celdaDocumento = filaSupervisor.locator('td').filter({ hasText: '00000001' });
    await sinDesbordeHorizontal(celdaDocumento);
  });
});

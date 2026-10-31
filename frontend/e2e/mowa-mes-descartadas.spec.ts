/**
 * Discarded campaigns on the follow-up (RF-MM-31, RF-MM-32, T-MM-C11 M-F3): «Activas (N) · Descartadas (M)»
 * kept in the URL, the month filter of the discarded view, and the three confirmed actions (discard, restore,
 * delete for good) with the announcement and the focus each leaves behind. The screen never decides what is
 * pending or discarded: it reads `pendiente_reporte` and `descartada_en`. Every value is synthetic.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import {
  DESCARTADA_EN,
  apiMowaMes,
  campanaSintetica,
  montarApiMowaMes,
  type ApiFalsaMowaMes,
} from './api-falsa-mowa-mes';

test.use({ timezoneId: 'America/Lima', reducedMotion: 'reduce' });

const REGLAS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

/**
 * 5 and 4 are active (5 waits for its report, 4 has it); 3, 2 and 1 are discarded: 3 in October, 2 and 1 in
 * September (1 would be pending if it were active, 2 has its report).
 */
function conDescartadas(): ApiFalsaMowaMes {
  const api = apiMowaMes();
  const una = (id: number, mes: string, pendiente: boolean, descartada: boolean) =>
    campanaSintetica({
      id,
      descripcion: `Campaña sintética ${id}`,
      fecha_envio: `${mes}-15`,
      mes_imputacion: mes,
      pendiente_reporte: pendiente,
      descartada_en: descartada ? DESCARTADA_EN : null,
    });
  api.campanas = [
    una(5, '2026-10', true, false),
    una(4, '2026-10', false, false),
    una(3, '2026-10', true, true),
    una(2, '2026-09', false, true),
    una(1, '2026-09', true, true),
  ];
  return api;
}

async function abrir(page: Page, api: ApiFalsaMowaMes, busqueda = ''): Promise<void> {
  await montarApiMowaMes(page, api);
  await page.goto(`/mowa-mes/seguimiento${busqueda}`);
  await expect(page.getByRole('heading', { name: 'Seguimiento de MOWA MES', level: 1 })).toBeVisible();
  await expect(page.getByRole('group', { name: 'Mostrar' })).toBeVisible();
}

const filas = (page: Page) => page.locator('.mm-campanas__tabla tbody tr');
const fila = (page: Page, id: number) => filas(page).filter({ hasText: `Campaña sintética ${id}` });
const vista = (page: Page, cual: 'Activas' | 'Descartadas') => page.getByRole('button', { name: new RegExp(`^${cual} \\(`) });
const estado = (page: Page) => page.locator('[data-campanas-aviso]');
const detalle = (page: Page) => page.getByRole('heading', { name: /^Campaña \d+$/, level: 2 });
const mes = (page: Page) => page.getByLabel('Mes de gestión');
const pendientes = (page: Page) => page.locator('[data-pendientes]');

async function pedir(page: Page, accion: 'Descartar' | 'Restaurar' | 'Eliminar definitivamente', id: number) {
  await page.getByRole('button', { name: `${accion} la campaña ${id}` }).click();
  return page.getByRole('dialog', { name: `${accion} la campaña ${id}` });
}

test.describe('las dos vistas', () => {
  test('arriba de la lista, «Activas (N)» y «Descartadas (M)», con las activas a la vista', async ({ page }) => {
    await abrir(page, conDescartadas());

    await expect(vista(page, 'Activas')).toHaveText('Activas (2)');
    await expect(vista(page, 'Descartadas')).toHaveText('Descartadas (3)');
    await expect(vista(page, 'Activas')).toHaveAttribute('aria-pressed', 'true');
    await expect(vista(page, 'Descartadas')).toHaveAttribute('aria-pressed', 'false');
    await expect(filas(page)).toHaveCount(2);
    await expect(fila(page, 5)).toBeVisible();
    await expect(fila(page, 4)).toBeVisible();
    await expect(fila(page, 3)).toHaveCount(0);
  });

  test('una descartada no entra en la línea de pendientes', async ({ page }) => {
    // 5 is pending and active; 3 and 1 would be pending but are discarded.
    await abrir(page, conDescartadas());

    await expect(pendientes(page)).toHaveText('1 campaña pendiente del reporte');
  });

  test('la vista queda en la URL, y atrás y adelante la restauran', async ({ page }) => {
    await abrir(page, conDescartadas());

    await vista(page, 'Descartadas').click();
    await expect(page).toHaveURL(/\/mowa-mes\/seguimiento\?vista=descartadas$/);
    await expect(vista(page, 'Descartadas')).toHaveAttribute('aria-pressed', 'true');
    await expect(fila(page, 3)).toBeVisible();

    await page.goBack();
    await expect(page).toHaveURL(/\/mowa-mes\/seguimiento$/);
    await expect(vista(page, 'Activas')).toHaveAttribute('aria-pressed', 'true');
    await expect(fila(page, 5)).toBeVisible();

    await page.goForward();
    await expect(page).toHaveURL(/\?vista=descartadas$/);
    await expect(fila(page, 3)).toBeVisible();
  });

  test('un enlace con ?vista=descartadas abre directamente las descartadas', async ({ page }) => {
    await abrir(page, conDescartadas(), '?vista=descartadas');

    await expect(vista(page, 'Descartadas')).toHaveAttribute('aria-pressed', 'true');
    await expect(fila(page, 3)).toBeVisible();
    await expect(fila(page, 5)).toHaveCount(0);
    // And it opens on the newest month, not on the first campaign of all.
    await expect(mes(page)).toHaveValue('2026-10');
  });

  test('sin descartadas, «Descartadas (0)» se muestra y su vista lo dice', async ({ page }) => {
    const api = conDescartadas();
    api.campanas = api.campanas.filter((c) => c.descartada_en === null);
    await abrir(page, api);

    await expect(vista(page, 'Descartadas')).toHaveText('Descartadas (0)');
    await vista(page, 'Descartadas').click();
    await expect(page.getByText('No hay campañas descartadas.')).toBeVisible();
    await expect(filas(page)).toHaveCount(0);
    await expect(mes(page)).toBeHidden();
  });
});

test.describe('la vista de las descartadas', () => {
  test('el filtro «Mes de gestión» ofrece solo los meses con descartadas, del más reciente al más antiguo', async ({ page }) => {
    await abrir(page, conDescartadas(), '?vista=descartadas');

    await expect(mes(page).locator('option')).toHaveText(['Octubre de 2026', 'Septiembre de 2026']);
    await expect(mes(page)).toHaveValue('2026-10');
    await expect(filas(page)).toHaveCount(1);
    await expect(fila(page, 3)).toBeVisible();
  });

  test('elegir otro mes lista las de ese mes', async ({ page }) => {
    await abrir(page, conDescartadas(), '?vista=descartadas');

    await mes(page).selectOption('2026-09');

    await expect(filas(page)).toHaveCount(2);
    await expect(fila(page, 2)).toBeVisible();
    await expect(fila(page, 1)).toBeVisible();
    await expect(fila(page, 3)).toHaveCount(0);
  });

  test('dice una vez que no cuentan en el límite, el costo ni las cifras del mes', async ({ page }) => {
    await abrir(page, conDescartadas(), '?vista=descartadas');

    await expect(page.getByText('Las campañas descartadas no cuentan en el límite, el costo ni las cifras del mes.')).toBeVisible();
    await expect(mes(page).locator('xpath=ancestor::div[contains(@class,"field")]').locator('label svg')).toHaveCount(1);
  });

  test('la fila lleva el tag «Descartada», el día y sus tres acciones, sin opacidad', async ({ page }) => {
    await abrir(page, conDescartadas(), '?vista=descartadas');

    const tres = fila(page, 3);
    await expect(tres.locator('.tag')).toHaveCount(1);
    await expect(tres.locator('.tag')).toHaveText('Descartada');
    await expect(tres.locator('.tag svg')).toHaveCount(1);
    await expect(tres).toContainText(/Descartada el 30 .* 2026/);
    await expect(tres.getByRole('button', { name: 'Ver la campaña 3' })).toBeVisible();
    await expect(tres.getByRole('button', { name: 'Restaurar la campaña 3' })).toBeVisible();
    await expect(tres.getByRole('button', { name: 'Eliminar definitivamente la campaña 3' })).toBeVisible();
    await expect(tres.getByRole('button', { name: /Descartar la campaña/ })).toHaveCount(0);
    expect(await tres.evaluate((el) => getComputedStyle(el).opacity)).toBe('1');
    expect(await tres.locator('td').nth(2).evaluate((el) => getComputedStyle(el).opacity)).toBe('1');
  });

  test('una descartada no lleva el tag «Pendiente del reporte», aunque pendiente_reporte sea verdadero', async ({ page }) => {
    await abrir(page, conDescartadas(), '?vista=descartadas');

    // Campaign 3 has `pendiente_reporte: true`.
    await expect(page.locator('.mm-campanas__tabla .tag', { hasText: 'Pendiente del reporte' })).toHaveCount(0);
    await expect(pendientes(page)).toBeHidden();
  });

  test('«Ver» abre su detalle como siempre, sin aviso de pendiente ni importación', async ({ page }) => {
    await abrir(page, conDescartadas(), '?vista=descartadas');

    await fila(page, 3).getByRole('button', { name: 'Ver la campaña 3' }).click();

    await expect(detalle(page)).toHaveText('Campaña 3');
    await expect(page.locator('[data-pendiente-aviso]')).toBeHidden();
    await expect(page.getByLabel('Archivo del reporte')).toBeHidden();
    await expect(page.getByRole('button', { name: 'Importar reporte' })).toBeHidden();
    // Where the form was, the hint says why and what to do.
    await expect(page.locator('[data-reporte-descartada]')).toHaveText(
      'Esta campaña está descartada: restáurala para importar su reporte.',
    );
    await expect(page.locator('[data-reporte-descartada]')).toHaveClass(/field__hint/);
    // Its files and its reconciliation are read as for any other.
    await expect(page.getByRole('heading', { name: 'Archivos de carga' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Conciliación' })).toBeVisible();
  });

  test('importar a una campaña que se descartó mientras tanto muestra su error, sin el diálogo de reemplazo', async ({ page }) => {
    const api = conDescartadas();
    await abrir(page, api);
    await expect(detalle(page)).toHaveText('Campaña 5');

    // Another tab discarded it.
    api.campanas = api.campanas.map((c) => (c.id === 5 ? { ...c, descartada_en: DESCARTADA_EN } : c));
    await page.getByLabel('Archivo del reporte').setInputFiles({
      name: 'REPORTE_SINTETICO.xlsx',
      mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      buffer: Buffer.from('reporte sintetico de prueba'),
    });
    await page.getByRole('button', { name: 'Importar reporte' }).click();

    await expect(page.locator('#mm-reporte-error')).toHaveText('La campaña está descartada. Restáurala primero.');
    await expect(page.getByRole('dialog')).toHaveCount(0);
  });
});

test('una campaña activa no lleva el hint de «está descartada»', async ({ page }) => {
  await abrir(page, conDescartadas());

  await expect(detalle(page)).toHaveText('Campaña 5');
  await expect(page.locator('[data-reporte-descartada]')).toBeHidden();
  await expect(page.getByLabel('Archivo del reporte')).toBeVisible();
});

test('el mes del límite y el del filtro se escriben igual, con mayúscula', async ({ page }) => {
  const api = conDescartadas();
  await abrir(page, api, '?vista=descartadas');

  const delLimite = (await page.locator('[data-mes]').textContent())!;
  expect(delLimite).toMatch(/^[A-ZÁÉÍÓÚ][a-z]+ de \d{4}$/);
  // The filter's options are the same label for each month.
  const opciones = await mes(page).locator('option').allTextContents();
  for (const opcion of opciones) expect(opcion).toMatch(/^[A-ZÁÉÍÓÚ][a-z]+ de \d{4}$/);
  // And the limit's month, taken to the filter's month, reads the same way.
  await page.getByRole('button', { name: 'Mes anterior' }).click();
  await expect(page.locator('[data-mes]')).not.toHaveText(delLimite);
  await expect(page.locator('[data-mes]')).toHaveText(/^[A-ZÁÉÍÓÚ][a-z]+ de \d{4}$/);
});

test('el «cuenta en» del detalle lleva el mes en minúscula, a mitad de frase', async ({ page }) => {
  await abrir(page, conDescartadas());

  await expect(page.locator('[data-detalle-meta]')).toContainText('cuenta en octubre de 2026');
});

test.describe('descartar', () => {
  test('pide confirmación, con el foco en «Cancelar»; sin reporte importado no advierte', async ({ page }) => {
    await abrir(page, conDescartadas());

    const dialogo = await pedir(page, 'Descartar', 5);

    await expect(dialogo).toBeVisible();
    await expect(dialogo.getByText('Deja de mostrarse entre las activas y sale del límite, el costo y las cifras del mes.')).toBeVisible();
    await expect(dialogo.getByRole('button', { name: 'Cancelar' })).toBeFocused();
    // Campaign 5 is still pending: no report to warn about.
    await expect(dialogo.locator('.notice--warning')).toBeHidden();
    await expect(dialogo.getByRole('button', { name: 'Descartar' })).toHaveClass(/btn--primary/);
  });

  test('con el reporte ya importado, advierte que su consumo deja de contar', async ({ page }) => {
    await abrir(page, conDescartadas());

    const dialogo = await pedir(page, 'Descartar', 4);

    await expect(dialogo.locator('.notice--warning')).toBeVisible();
    await expect(dialogo.locator('.notice--warning')).toContainText(
      'Esta campaña ya tiene reporte de enviados. Si se envió, su consumo deja de contar en el límite del mes.',
    );
  });

  test('Escape y «Cancelar» no cambian nada', async ({ page }) => {
    const api = conDescartadas();
    await abrir(page, api);

    const dialogo = await pedir(page, 'Descartar', 5);
    await page.keyboard.press('Escape');
    await expect(dialogo).toBeHidden();

    await pedir(page, 'Descartar', 5);
    await page.getByRole('button', { name: 'Cancelar' }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);

    await expect(vista(page, 'Activas')).toHaveText('Activas (2)');
    expect(api.pedidos.filter((p) => p.metodo === 'POST' && p.ruta.endsWith('/descartar'))).toHaveLength(0);
  });

  test('al confirmar: la fila sale, los contadores y la línea de pendientes cambian, se anuncia y el foco pasa a la fila siguiente', async ({ page }) => {
    const api = conDescartadas();
    await abrir(page, api);

    const dialogo = await pedir(page, 'Descartar', 5);
    await dialogo.getByRole('button', { name: 'Descartar' }).click();

    await expect(dialogo).toBeHidden();
    await expect(fila(page, 5)).toHaveCount(0);
    await expect(vista(page, 'Activas')).toHaveText('Activas (1)');
    await expect(vista(page, 'Descartadas')).toHaveText('Descartadas (4)');
    await expect(pendientes(page)).toBeHidden();
    await expect(estado(page)).toHaveText('Se descartó la campaña 5.');
    await expect(page.getByRole('button', { name: 'Ver la campaña 4' })).toBeFocused();
    expect(api.pedidos.filter((p) => p.metodo === 'POST' && p.ruta === '/mowa-mes/campanas/5/descartar')).toHaveLength(1);

    // It is now in the other view, under its month.
    await vista(page, 'Descartadas').click();
    await expect(fila(page, 5)).toBeVisible();
  });

  test('descartar la última fila deja el foco en el control de las vistas', async ({ page }) => {
    await abrir(page, conDescartadas());

    const dialogo = await pedir(page, 'Descartar', 4);
    await dialogo.getByRole('button', { name: 'Descartar' }).click();

    await expect(fila(page, 4)).toHaveCount(0);
    await expect(estado(page)).toHaveText('Se descartó la campaña 4.');
    await expect(vista(page, 'Activas')).toBeFocused();
  });

  test('descartar la campaña que está en el detalle cierra su detalle', async ({ page }) => {
    await abrir(page, conDescartadas());
    await expect(detalle(page)).toHaveText('Campaña 5');

    const dialogo = await pedir(page, 'Descartar', 5);
    await dialogo.getByRole('button', { name: 'Descartar' }).click();

    await expect(fila(page, 5)).toHaveCount(0);
    await expect(page.getByText('Elige una campaña para ver su detalle.')).toBeVisible();
  });

  test('el consumo del mes se lee de nuevo: una descartada sale del límite', async ({ page }) => {
    const api = conDescartadas();
    await abrir(page, api);
    const antes = api.pedidos.filter((p) => p.ruta.startsWith('/mowa-mes/limite-mensual')).length;

    const dialogo = await pedir(page, 'Descartar', 5);
    await dialogo.getByRole('button', { name: 'Descartar' }).click();
    await expect(estado(page)).toHaveText('Se descartó la campaña 5.');

    expect(api.pedidos.filter((p) => p.ruta.startsWith('/mowa-mes/limite-mensual')).length).toBeGreaterThan(antes);
  });
});

test.describe('restaurar', () => {
  test('pide confirmación y devuelve la campaña a las activas', async ({ page }) => {
    await abrir(page, conDescartadas(), '?vista=descartadas');

    const dialogo = await pedir(page, 'Restaurar', 3);
    await expect(dialogo.getByText('Vuelve a las activas y a todos los cálculos del mes.')).toBeVisible();
    await expect(dialogo.getByRole('button', { name: 'Cancelar' })).toBeFocused();
    await expect(dialogo.getByRole('button', { name: 'Restaurar' })).toHaveClass(/btn--primary/);
    await dialogo.getByRole('button', { name: 'Restaurar' }).click();

    await expect(dialogo).toBeHidden();
    await expect(fila(page, 3)).toHaveCount(0);
    await expect(vista(page, 'Activas')).toHaveText('Activas (3)');
    await expect(vista(page, 'Descartadas')).toHaveText('Descartadas (2)');
    await expect(estado(page)).toHaveText('Se restauró la campaña 3.');
    // It was the only one of October: the filter falls to the newest month left.
    await expect(mes(page).locator('option')).toHaveText(['Septiembre de 2026']);
    await expect(mes(page)).toHaveValue('2026-09');
    await expect(filas(page)).toHaveCount(2);
    // Nothing follows it in its list: the focus goes to the views control.
    await expect(vista(page, 'Descartadas')).toBeFocused();

    await vista(page, 'Activas').click();
    await expect(fila(page, 3)).toBeVisible();
    // Restored, and still waiting for its report: it counts again in the line above.
    await expect(pendientes(page)).toHaveText('2 campañas pendientes del reporte');
  });
});

test.describe('eliminar definitivamente', () => {
  test('exige la casilla: el botón queda inactivo hasta marcarla', async ({ page }) => {
    await abrir(page, conDescartadas(), '?vista=descartadas');

    const dialogo = await pedir(page, 'Eliminar definitivamente', 3);

    await expect(dialogo.locator('.notice--danger')).toContainText(
      'Se borran la campaña, sus archivos, filas, exclusiones y reportes. No se puede deshacer.',
    );
    await expect(dialogo.getByRole('button', { name: 'Cancelar' })).toBeFocused();
    const eliminar = dialogo.getByRole('button', { name: 'Eliminar definitivamente' });
    await expect(eliminar).toHaveClass(/btn--danger/);
    await expect(eliminar).toBeDisabled();

    await dialogo.getByLabel('Entiendo que no se puede deshacer').check();
    await expect(eliminar).toBeEnabled();
    await dialogo.getByLabel('Entiendo que no se puede deshacer').uncheck();
    await expect(eliminar).toBeDisabled();
  });

  test('sin marcar la casilla no se manda ninguna petición', async ({ page }) => {
    const api = conDescartadas();
    await abrir(page, api, '?vista=descartadas');

    const dialogo = await pedir(page, 'Eliminar definitivamente', 3);
    await dialogo.getByRole('button', { name: 'Eliminar definitivamente' }).click({ force: true });

    await expect(dialogo).toBeVisible();
    expect(api.pedidos.filter((p) => p.metodo === 'DELETE')).toHaveLength(0);
  });

  test('con la casilla, borra la campaña: sale de la lista, de los contadores y del servidor', async ({ page }) => {
    const api = conDescartadas();
    await abrir(page, api, '?vista=descartadas');
    await mes(page).selectOption('2026-09');

    const dialogo = await pedir(page, 'Eliminar definitivamente', 2);
    await dialogo.getByLabel('Entiendo que no se puede deshacer').check();
    await dialogo.getByRole('button', { name: 'Eliminar definitivamente' }).click();

    await expect(dialogo).toBeHidden();
    await expect(fila(page, 2)).toHaveCount(0);
    await expect(vista(page, 'Descartadas')).toHaveText('Descartadas (2)');
    await expect(vista(page, 'Activas')).toHaveText('Activas (2)');
    await expect(estado(page)).toHaveText('Se eliminó la campaña 2.');
    await expect(page.getByRole('button', { name: 'Ver la campaña 1' })).toBeFocused();
    expect(api.pedidos.filter((p) => p.metodo === 'DELETE' && p.ruta === '/mowa-mes/campanas/2')).toHaveLength(1);
    expect(api.campanas.map((c) => c.id)).not.toContain(2);
  });

  test('un 409 campana_no_descartada se dice en el diálogo, que sigue abierto', async ({ page }) => {
    const api = conDescartadas();
    await abrir(page, api, '?vista=descartadas');

    // Someone restored it in the meantime.
    api.campanas = api.campanas.map((c) => (c.id === 3 ? { ...c, descartada_en: null } : c));
    const dialogo = await pedir(page, 'Eliminar definitivamente', 3);
    await dialogo.getByLabel('Entiendo que no se puede deshacer').check();
    await dialogo.getByRole('button', { name: 'Eliminar definitivamente' }).click();

    await expect(dialogo.getByRole('alert')).toHaveText('Solo se puede eliminar una campaña descartada. Descártala primero.');
    await expect(dialogo).toBeVisible();
    await expect(dialogo.getByRole('button', { name: 'Eliminar definitivamente' })).toBeEnabled();
  });
});

test.describe('idioma y anchos', () => {
  test('en inglés traduce las vistas, el tag, la fecha, el diálogo y el aviso', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    await montarApiMowaMes(page, conDescartadas());
    await page.goto('/mowa-mes/seguimiento?vista=descartadas');
    await expect(page.getByRole('group', { name: 'Show' })).toBeVisible();
    await expect(page.getByRole('button', { name: /^Active \(/ })).toHaveText('Active (2)');
    await expect(page.getByRole('button', { name: /^Discarded \(/ })).toHaveText('Discarded (3)');
    await expect(page.getByLabel('Management month')).toHaveValue('2026-10');
    await expect(page.getByLabel('Management month').locator('option').first()).toHaveText('October 2026');
    await expect(fila(page, 3).locator('.tag')).toHaveText('Discarded');
    await expect(fila(page, 3)).toContainText(/Discarded on /);

    await page.getByRole('button', { name: 'Restore campaign 3' }).click();
    const dialogo = page.getByRole('dialog', { name: 'Restore campaign 3' });
    await dialogo.getByRole('button', { name: 'Restore' }).click();
    await expect(page.locator('[data-campanas-aviso]')).toHaveText('Campaign 3 was restored.');
  });

  test('a 360 px no desborda y las acciones y el diálogo quedan a la vista', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    await abrir(page, conDescartadas(), '?vista=descartadas');

    const desborde = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(desborde).toBeLessThanOrEqual(0);

    await vista(page, 'Descartadas').scrollIntoViewIfNeeded();
    const caja = (await vista(page, 'Descartadas').boundingBox())!;
    expect(caja.x).toBeGreaterThanOrEqual(0);
    expect(caja.x + caja.width).toBeLessThanOrEqual(361);

    const dialogo = await pedir(page, 'Eliminar definitivamente', 3);
    for (const nombre of ['Cancelar', 'Eliminar definitivamente']) {
      const boton = (await dialogo.getByRole('button', { name: nombre }).boundingBox())!;
      expect(boton.x).toBeGreaterThanOrEqual(0);
      expect(boton.x + boton.width).toBeLessThanOrEqual(361);
    }
  });

  for (const tema of ['light', 'dark'] as const) {
    for (const ancho of [1280, 360]) {
      test(`sin violaciones WCAG a ${ancho} px, tema ${tema === 'light' ? 'claro' : 'oscuro'}`, async ({ page }) => {
        await page.addInitScript((elegido) => {
          localStorage.setItem('app:appearance', JSON.stringify({ theme: elegido, language: 'es' }));
        }, tema);
        await page.setViewportSize({ width: ancho, height: 900 });
        await abrir(page, conDescartadas(), '?vista=descartadas');
        await expect(fila(page, 3)).toBeVisible();

        const lista = await new AxeBuilder({ page }).withTags(REGLAS).analyze();
        expect(lista.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);

        // And with the confirmation open: the danger notice, the checkbox and the disabled button.
        const dialogo = await pedir(page, 'Eliminar definitivamente', 3);
        await expect(dialogo).toBeVisible();
        const confirmando = await new AxeBuilder({ page }).withTags(REGLAS).analyze();
        expect(confirmando.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
      });
    }
  }
});

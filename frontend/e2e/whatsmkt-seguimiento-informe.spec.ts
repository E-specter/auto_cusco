/**
 * The report of WhatsMKT and its reconciliation on the tracking screen (T-WM-F3b, RF-WM-37 to RF-WM-41, docs/whatsmkt-interfaz.md §4.2), against the
 * same intercepted API as `whatsmkt-seguimiento.spec.ts`: importing it, replacing one that was already there, every refusal by its code, and what
 * the reconciliation says (the figures, the products and the supervision apart, the numbers with no match, and a total that differs). Every
 * number is synthetic.
 */
import { expect, test, type Page } from '@playwright/test';

import { apiWhatsmkt, errorWhatsmkt, montarApiWhatsmkt } from './api-falsa-whatsmkt';
import { informeFalso, montarSeguimientoWhatsmkt, seguimientoFalso, type SeguimientoFalso } from './api-falsa-whatsmkt-seguimiento';

const RUTA = '/whatsmkt/seguimiento';

async function abrir(page: Page, estado: SeguimientoFalso = seguimientoFalso(), busqueda = ''): Promise<SeguimientoFalso> {
  await montarApiWhatsmkt(page, apiWhatsmkt());
  await montarSeguimientoWhatsmkt(page, estado);
  await page.goto(`${RUTA}${busqueda}`);
  await expect(page.locator('[data-vista="activas"]')).toContainText('Activas (');
  return estado;
}

const guardada = (estado: SeguimientoFalso, id: number) => estado.campanas.find((c) => c.resumen.id === id)!;
const detalle = (page: Page) => page.locator('[data-detalle]');
const conciliacion = (page: Page) => page.locator('[data-conciliacion]');
const errorInforme = (page: Page) => page.locator('[data-informe-error]');
const importar = (page: Page) => page.getByRole('button', { name: 'Importar informe', exact: true });
const dialogo = (page: Page) => page.locator('[data-dialog="confirmar"]');

async function elegirInforme(page: Page, nombre = 'informe-whatsmkt.xlsx'): Promise<void> {
  await page.locator('#wm-informe').setInputFiles({
    name: nombre,
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: Buffer.from('contenido sintetico del informe'),
  });
}

test.describe('el aviso de pendiente', () => {
  test('lleva un «Importar el informe» que va al selector del informe', async ({ page }) => {
    await abrir(page, seguimientoFalso(), '?campana=37');
    await expect(page.locator('[data-detalle-pendiente]')).toBeVisible();

    await page.locator('[data-detalle-pendiente]').getByRole('button', { name: 'Importar el informe' }).click();

    await expect(page.locator('#wm-informe')).toBeFocused();
  });
});

test.describe('importar el informe', () => {
  test('manda el archivo; la campaña deja de estar pendiente y aparecen las cifras y la conciliación', async ({ page }) => {
    const estado = await abrir(page, seguimientoFalso(), '?campana=37');
    await expect(conciliacion(page)).toBeHidden();
    await elegirInforme(page);
    await expect(page.locator('[data-informe-nombre]')).toHaveText('informe-whatsmkt.xlsx');

    await importar(page).click();

    await expect(page.locator('[data-informe-estado]')).toHaveText('Informe importado.');
    expect(estado.importaciones).toEqual([{ id: 37, archivo: 'informe-whatsmkt.xlsx', reemplazar: false }]);
    await expect(page.locator('[data-detalle-pendiente]')).toBeHidden();
    await expect(conciliacion(page)).toBeVisible();
    await expect(page.locator('[data-conciliacion-linea]')).toHaveText(/^Informe del 30 oct\.? 2026 · total informado 101 · 101 filas$/);
    // The figures gain the sent and the not sent; the list is read again: one campaign less is pending.
    await expect(page.locator('[data-detalle-cifras] .stat').filter({ has: page.getByText('Enviados', { exact: true }) })).toContainText('99');
    await expect(page.locator('[data-detalle-cifras] .stat').filter({ has: page.getByText('No enviados', { exact: true }) })).toContainText('2');
    await expect(page.locator('[data-pendientes]')).toContainText('1 campaña pendiente del informe');
    await expect(page.locator('tr[data-campana="37"] .tag')).toHaveCount(0);
  });

  test('sin archivo lo dice bajo el campo y no manda nada', async ({ page }) => {
    const estado = await abrir(page, seguimientoFalso(), '?campana=37');

    await importar(page).click();

    await expect(errorInforme(page)).toHaveText('Elige el archivo del informe.');
    await expect(page.locator('#wm-informe')).toHaveAttribute('aria-invalid', 'true');
    await expect(page.locator('#wm-informe')).toBeFocused();
    expect(estado.importaciones).toEqual([]);
  });

  test('en una descartada el formulario se oculta y dice que se restaure', async ({ page }) => {
    await abrir(page, seguimientoFalso(), '?campana=30');

    await expect(page.locator('[data-form-informe]')).toBeHidden();
    await expect(page.locator('[data-informe-descartada]')).toHaveText('Esta campaña está descartada: restáurala para importar su informe.');
  });
});

test.describe('reemplazar un informe que ya estaba', () => {
  test('el 409 pide confirmar, y al aceptar lo manda otra vez con reemplazar', async ({ page }) => {
    const estado = await abrir(page, seguimientoFalso(), '?campana=36');
    await elegirInforme(page, 'informe-nuevo.xlsx');

    await importar(page).click();

    await expect(dialogo(page)).toBeVisible();
    await expect(dialogo(page).locator('[data-confirmar-titulo]')).toHaveText('Esta campaña ya tiene un informe');
    await expect(dialogo(page).locator('[data-confirmar-cuerpo]')).toHaveText('Si lo reemplazas, la conciliación se recalcula con el archivo nuevo.');
    await expect(dialogo(page).getByRole('button', { name: 'No reemplazar' })).toBeVisible();
    expect(estado.importaciones).toHaveLength(1);

    await dialogo(page).getByRole('button', { name: 'Reemplazar', exact: true }).click();

    await expect(dialogo(page)).toBeHidden();
    expect(estado.importaciones).toEqual([
      { id: 36, archivo: 'informe-nuevo.xlsx', reemplazar: false },
      { id: 36, archivo: 'informe-nuevo.xlsx', reemplazar: true },
    ]);
    await expect(page.locator('[data-informe-estado]')).toHaveText('Informe importado.');
    await expect(page.locator('[data-conciliacion-nombre]')).toBeVisible();
  });

  test('cancelar deja el informe como estaba y no manda nada más', async ({ page }) => {
    const estado = await abrir(page, seguimientoFalso(), '?campana=36');
    await elegirInforme(page);
    await importar(page).click();

    await dialogo(page).getByRole('button', { name: 'No reemplazar' }).click();

    await expect(dialogo(page)).toBeHidden();
    expect(estado.importaciones).toHaveLength(1);
  });

  test('si el reemplazo falla, el motivo queda en el diálogo por su código', async ({ page }) => {
    const estado = seguimientoFalso();
    estado.respuestas.informe = [null, { estado: 422, cuerpo: errorWhatsmkt('informe_sin_filas') }];
    await abrir(page, estado, '?campana=36');
    await elegirInforme(page);
    await importar(page).click();

    await dialogo(page).getByRole('button', { name: 'Reemplazar', exact: true }).click();

    await expect(dialogo(page).locator('[data-confirmar-error]')).toHaveText('El informe no trae números enviados.');
    await expect(dialogo(page)).toBeVisible();
  });
});

test.describe('lo que rechaza la API, por su código', () => {
  for (const [nombre, respuesta, texto] of [
    [
      'sin los encabezados (422)',
      { estado: 422, cuerpo: errorWhatsmkt('informe_sin_encabezados') },
      'El informe no tiene los encabezados CAMPAÑA, TIPO DE ENVIO y NUMERO en la fila 4. ¿Es el informe de WhatsMKT?',
    ],
    ['sin números enviados (422)', { estado: 422, cuerpo: errorWhatsmkt('informe_sin_filas') }, 'El informe no trae números enviados.'],
    [
      'una campaña descartada entretanto (409)',
      { estado: 409, cuerpo: { detail: 'La campaña está descartada', codigo: 'campana_descartada' } },
      'La campaña está descartada. Restáurala primero.',
    ],
    ['un archivo demasiado grande (413), con la frase del servidor', { estado: 413, cuerpo: { detail: 'El archivo supera los 32 MB' } }, 'El archivo supera los 32 MB'],
  ] as const) {
    test(`${nombre} se dice bajo el campo`, async ({ page }) => {
      const estado = seguimientoFalso();
      estado.respuestas.informe = [respuesta];
      await abrir(page, estado, '?campana=37');
      await elegirInforme(page);

      await importar(page).click();

      await expect(errorInforme(page)).toHaveText(texto);
      await expect(page.locator('#wm-informe')).toHaveAttribute('aria-invalid', 'true');
      await expect(page.locator('[data-detalle-pendiente]')).toBeVisible();
    });
  }

  test('elegir otro archivo limpia el error', async ({ page }) => {
    const estado = seguimientoFalso();
    estado.respuestas.informe = [{ estado: 422, cuerpo: errorWhatsmkt('informe_sin_filas') }];
    await abrir(page, estado, '?campana=37');
    await elegirInforme(page);
    await importar(page).click();
    await expect(errorInforme(page)).not.toHaveText('');

    await elegirInforme(page, 'otro.xlsx');

    await expect(errorInforme(page)).toHaveText('');
    await expect(page.locator('#wm-informe')).not.toHaveAttribute('aria-invalid', 'true');
  });
});

test.describe('la conciliación', () => {
  test('con informe: su línea, las cifras de enviados y los productos y la supervisión cada uno en su tabla', async ({ page }) => {
    await abrir(page, seguimientoFalso(), '?campana=36');

    await expect(page.locator('[data-conciliacion-linea]')).toHaveText(/^Informe del 30 oct\.? 2026 · total informado 101 · 101 filas$/);
    await expect(page.locator('[data-detalle-pendiente]')).toBeHidden();
    await expect(page.locator('[data-conciliacion-tablas] table')).toHaveCount(2);
    await expect(page.locator('table[aria-label="Productos"] thead th')).toHaveText(['Cargados', 'Enviados', 'No enviados']);
    await expect(page.locator('table[aria-label="Productos"] tbody td')).toHaveText(['99', '97', '2']);
    // The supervision is its own table, never added to the products (RF-41).
    await expect(page.locator('table[aria-label="Supervisión"] tbody td')).toHaveText(['2', '2', '0']);
    await expect(page.locator('[data-detalle-cifras] .stat').filter({ has: page.getByText('Enviados', { exact: true }) })).toContainText('99');
    await expect(page.locator('[data-detalle-cifras] .stat').filter({ has: page.getByText('No enviados', { exact: true }) })).toContainText('2');
    await expect(conciliacion(page)).toContainText('Un producto cuenta como enviado si su número aparece en el informe.');
  });

  test('sin informe no hay conciliación ni cifras de enviados', async ({ page }) => {
    await abrir(page, seguimientoFalso(), '?campana=37');

    await expect(conciliacion(page)).toBeHidden();
    await expect(page.locator('[data-detalle-cifras] .stat').filter({ has: page.getByText('No enviados', { exact: true }) })).toHaveCount(0);
  });

  test('los números del informe que no están en la carga, con su lista; con cero no se muestra', async ({ page }) => {
    const estado = seguimientoFalso();
    guardada(estado, 35).informe = informeFalso(35);
    guardada(estado, 35).informe!.conciliacion!.sin_correspondencia = [];
    guardada(estado, 35).informe!.conciliacion!.total_sin_correspondencia = 0;
    await abrir(page, estado, '?campana=36');
    await expect(page.locator('[data-conciliacion-sin-texto]')).toHaveText('Números del informe que no están en la carga: 2');
    await expect(page.locator('[data-conciliacion-sin-lista] span')).toHaveText(['900000901', '900000902']);

    await page.locator('tr[data-campana="35"]').getByRole('button', { name: /^Ver CUZCO/ }).click();

    await expect(page.locator('[data-detalle-titulo]')).toContainText('Campaña 35');
    await expect(page.locator('[data-conciliacion-sin]')).toBeHidden();
  });

  test('el nombre que trae el informe se lee, sin compararlo', async ({ page }) => {
    await abrir(page, seguimientoFalso(), '?campana=36');

    await expect(page.locator('[data-conciliacion-nombre]')).toHaveText('Nombre en el informe: CUZCO_Vencida (Preventivo) whatsapp 36');
  });

  test('si el total que dice el informe no coincide con sus filas, dice los dos y no rechaza (DU-WM-7)', async ({ page }) => {
    const estado = seguimientoFalso();
    guardada(estado, 36).informe = informeFalso(36, { total_informado: 101, filas: 99, coincide_total: false });
    await abrir(page, estado, '?campana=36');

    await expect(page.locator('[data-conciliacion-total]')).toBeVisible();
    await expect(page.locator('[data-conciliacion-total]')).toHaveClass(/notice--warning/);
    await expect(page.locator('[data-conciliacion-total-texto]')).toHaveText('El informe dice 101 enviados y trae 99 filas. La conciliación usa las filas.');
    await expect(conciliacion(page)).toBeVisible();
  });

  test('si coincide, o el informe no dijo su total, no hay aviso', async ({ page }) => {
    const estado = seguimientoFalso();
    guardada(estado, 35).informe = informeFalso(35, { total_informado: null, coincide_total: null, fecha_informada: null });
    await abrir(page, estado, '?campana=36');
    await expect(page.locator('[data-conciliacion-total]')).toBeHidden();

    await page.locator('tr[data-campana="35"]').getByRole('button', { name: /^Ver CUZCO/ }).click();

    await expect(page.locator('[data-detalle-titulo]')).toContainText('Campaña 35');
    await expect(page.locator('[data-conciliacion-total]')).toBeHidden();
    // What the report did not say stands as a dash; the date falls back on the day it was imported.
    await expect(page.locator('[data-conciliacion-linea]')).toHaveText(/^Informe del 30 oct\.? 2026 · total informado — · 101 filas$/);
  });

  test('si no se puede leer, lo dice en su lugar y el resto del detalle queda', async ({ page }) => {
    const estado = seguimientoFalso();
    estado.fallos.conciliacion = [{ estado: 500, cuerpo: { detail: 'No se pudo leer el informe' } }];
    await abrir(page, estado, '?campana=36');

    await expect(page.locator('[data-conciliacion-error]')).toHaveText('No se pudo leer el informe');
    await expect(conciliacion(page)).toBeHidden();
    await expect(detalle(page).locator('[data-detalle-cifras]')).toBeVisible();
  });

  test('a 360 px las tablas se apilan y la página no desborda', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    await abrir(page, seguimientoFalso(), '?campana=36');

    await expect(conciliacion(page)).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360);
    await expect(page.locator('[data-conciliacion-tablas] table').first()).toHaveClass(/table--apilable/);
    await expect(page.locator('table[aria-label="Productos"] tbody td').first()).toHaveAttribute('data-etiqueta', 'Cargados');
  });

  test('en inglés se dice en inglés', async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' })));
    await montarApiWhatsmkt(page, apiWhatsmkt());
    await montarSeguimientoWhatsmkt(page, seguimientoFalso());
    await page.goto(RUTA + '?campana=36');
    await expect(conciliacion(page)).toBeVisible();

    await expect(page.locator('[data-conciliacion-linea]')).toHaveText(/^Report of 30 Oct\.? 2026 · reported total 101 · 101 rows$/);
    await expect(page.locator('[data-conciliacion-sin-texto]')).toHaveText('Report numbers that are not in the load: 2');
    await expect(page.locator('table[aria-label="Products"] thead th')).toHaveText(['Loaded', 'Sent', 'Not sent']);
    await expect(page.getByRole('button', { name: 'Import report', exact: true })).toBeVisible();
  });
});

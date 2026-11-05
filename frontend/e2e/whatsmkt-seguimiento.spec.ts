/**
 * The WhatsMKT tracking screen (T-WM-F3a), end to end against an intercepted API: the list of campaigns with its views, filters, pending line and
 * pages, the `?campana=` of the card of a lot created, the detail with its card and its exclusions (and the products left out of the lot, seen from
 * any campaign of it), and discarding, restoring and deleting with their confirmation. The clock is fixed from the first spec, in
 * `montarApiWhatsmkt`. Every text and number is invented.
 */
import { expect, test, type Page } from '@playwright/test';

import { apiWhatsmkt, montarApiWhatsmkt } from './api-falsa-whatsmkt';
import { conMuchasCampanas, montarSeguimientoWhatsmkt, seguimientoFalso, type SeguimientoFalso } from './api-falsa-whatsmkt-seguimiento';

const RUTA = '/whatsmkt/seguimiento';

async function abrir(page: Page, estado: SeguimientoFalso = seguimientoFalso(), busqueda = ''): Promise<SeguimientoFalso> {
  await montarApiWhatsmkt(page, apiWhatsmkt());
  await montarSeguimientoWhatsmkt(page, estado);
  await page.goto(`${RUTA}${busqueda}`);
  await expect(page.getByRole('heading', { name: 'Seguimiento de WhatsMKT', level: 1 })).toBeVisible();
  await expect(page.locator('[data-vista="activas"]')).toContainText('Activas (');
  return estado;
}

const filas = (page: Page) => page.locator('[data-tabla] tbody tr');
const fila = (page: Page, id: number) => page.locator(`tr[data-campana="${id}"]`);
const detalle = (page: Page) => page.locator('[data-detalle]');
const estadoLista = (page: Page) => page.locator('[data-lista-estado]');
const ids = async (page: Page) => (await filas(page).evaluateAll((trs) => trs.map((tr) => Number((tr as HTMLElement).dataset.campana))));

test.describe('la lista', () => {
  test('muestra las activas con su total, el de las descartadas y las pendientes del informe', async ({ page }) => {
    await abrir(page);

    await expect(page.locator('[data-vista="activas"]')).toHaveText('Activas (4)');
    await expect(page.locator('[data-vista="descartadas"]')).toHaveText('Descartadas (1)');
    await expect(page.locator('[data-vista="activas"]')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('[data-pendientes]')).toContainText('2 campañas pendientes del informe');
    // The latest first, a lot together.
    expect(await ids(page)).toEqual([38, 37, 36, 35]);
    await expect(page.locator('[data-tabla] th').filter({ hasText: /^(#|Creada|Nombre|Lote|Segmento|Envío|Filas|Estado|Acciones)$/ })).toHaveCount(9);
  });

  test('pide la lista una sola vez por vista, con lo más que da la API', async ({ page }) => {
    const estado = await abrir(page);

    expect(estado.pedidosDeLista).toEqual([expect.objectContaining({ estado: 'activas', limite: '500', desplazamiento: '0' })]);
  });

  test('cada fila dice su estado: pendiente del informe, o nada si ya está conciliada', async ({ page }) => {
    await abrir(page);

    await expect(fila(page, 37).locator('.tag')).toHaveText('Pendiente del informe');
    await expect(fila(page, 37).locator('.tag')).toHaveClass(/tag--advertencia/);
    await expect(fila(page, 36).locator('.tag')).toHaveCount(0);
    await expect(fila(page, 36).locator('td').nth(3)).toContainText('Global');
    await expect(fila(page, 37).locator('td').nth(4)).toContainText('Horario 1');
  });

  test('los filtros de mes de envío, lote y segmento, solos y juntos', async ({ page }) => {
    await abrir(page);

    await page.locator('#wm-seg-mes').selectOption('2026-10');
    expect(await ids(page)).toEqual([38, 37]);

    await page.locator('#wm-seg-segmento').selectOption('tramo_2');
    expect(await ids(page)).toEqual([38]);

    await page.locator('#wm-seg-mes').selectOption('');
    await page.locator('#wm-seg-segmento').selectOption('');
    await page.locator('#wm-seg-lote').selectOption('11');
    expect(await ids(page)).toEqual([36]);

    await page.locator('#wm-seg-lote').selectOption('');
    await page.locator('#wm-seg-segmento').selectOption('global');
    expect(await ids(page)).toEqual([36]);
  });

  test('sin campañas con esos filtros lo dice', async ({ page }) => {
    await abrir(page);
    await page.locator('#wm-seg-mes').selectOption('2026-11');
    await page.locator('#wm-seg-lote').selectOption('12');

    await expect(page.locator('[data-tabla] .empty')).toHaveText('No hay campañas con estos filtros.');
  });

  test('tocar el lote de una fila filtra por él', async ({ page }) => {
    await abrir(page);

    await fila(page, 37).getByRole('button', { name: 'Ver solo el lote 12' }).click();

    expect(await ids(page)).toEqual([38, 37]);
    await expect(page.locator('#wm-seg-lote')).toHaveValue('12');
  });

  test('Descartadas: la vista queda en la URL, sin línea de pendientes y con sus acciones', async ({ page }) => {
    await abrir(page);

    await page.locator('[data-vista="descartadas"]').click();

    await expect(page).toHaveURL(/\/whatsmkt\/seguimiento\?vista=descartadas$/);
    await expect.poll(() => ids(page)).toEqual([30]);
    await expect(page.locator('[data-pendientes]')).toBeHidden();
    await expect(fila(page, 30).locator('.tag')).toHaveText('Descartada');
    await expect(fila(page, 30).getByRole('button')).toHaveText(['9', 'Ver', 'Restaurar', 'Eliminar definitivamente']);

    await page.locator('[data-vista="activas"]').click();
    await expect(page).toHaveURL(/\/whatsmkt\/seguimiento$/);
    await expect.poll(() => ids(page)).toEqual([38, 37, 36, 35]);
  });

  test('las activas tienen Ver, Descargar y Descartar', async ({ page }) => {
    await abrir(page);

    // The first button is the lot's (it filters by it); the actions follow.
    await expect(fila(page, 37).getByRole('button')).toHaveText(['12', 'Ver', 'Descargar', 'Descartar']);
  });

  test('con más de 20 campañas se pagina, y cambiar de página no pide nada', async ({ page }) => {
    const estado = await abrir(page, conMuchasCampanas(seguimientoFalso(), 25));

    expect(await ids(page)).toHaveLength(20);
    await expect(page.locator('[data-pager] [data-page-range]')).toContainText('1');
    await page.locator('[data-pager] [data-page-next]').click();

    expect(await ids(page)).toHaveLength(9);
    await expect(page.locator('[data-pager] [data-page-next]')).toBeDisabled();
    expect(estado.pedidosDeLista).toHaveLength(1);
  });

  test('«Descargar» baja el archivo de la campaña', async ({ page }) => {
    const estado = await abrir(page);
    const descarga = page.waitForEvent('download');

    await fila(page, 37).getByRole('button', { name: /^Descargar/ }).click();

    expect((await descarga).suggestedFilename()).toBe('campana-37.xlsx');
    expect(estado.descargas).toEqual([37]);
  });
});

test.describe('abrir una campaña por su enlace', () => {
  test('?campana=<id> abre esa campaña, y la URL la conserva', async ({ page }) => {
    await abrir(page, seguimientoFalso(), '?campana=37');

    await expect(detalle(page)).toBeVisible();
    await expect(page.locator('[data-detalle-titulo]')).toHaveText('Campaña 37 · Preventivo · lote 12');
    await expect(page).toHaveURL(/campana=37/);
  });

  test('una campaña descartada está en la otra vista: la lista la sigue', async ({ page }) => {
    await abrir(page, seguimientoFalso(), '?campana=30');

    await expect(detalle(page)).toBeVisible();
    await expect(page.locator('[data-vista="descartadas"]')).toHaveAttribute('aria-pressed', 'true');
    expect(await ids(page)).toEqual([30]);
  });

  test('una campaña que no existe lo dice y no abre nada', async ({ page }) => {
    await abrir(page, seguimientoFalso(), '?campana=999');

    await expect(estadoLista(page)).toHaveText('No existe la campaña');
    await expect(detalle(page)).toBeHidden();
  });
});

test.describe('el detalle', () => {
  test('el encabezado, las fechas, el aviso de pendiente y las cifras', async ({ page }) => {
    await abrir(page);

    await fila(page, 37).getByRole('button', { name: /^Ver CUZCO/ }).click();

    await expect(detalle(page)).toBeVisible();
    await expect(page.locator('[data-detalle-titulo]')).toHaveText('Campaña 37 · Preventivo · lote 12');
    await expect(page.locator('[data-detalle-fechas]')).toContainText('Horario 1');
    await expect(page.locator('[data-detalle-pendiente]')).toContainText('Falta importar el informe de WhatsMKT');
    await expect(page.locator('[data-detalle-cifras] .stat__label')).toHaveText(['Productos cargados', 'Supervisión', 'Total cargados', 'Excluidos']);
    await expect(page.locator('[data-detalle-cifras] .stat__value')).toHaveText(['518', '2', '520', '12']);
  });

  test('con informe no hay aviso de pendiente', async ({ page }) => {
    await abrir(page);

    await fila(page, 36).getByRole('button', { name: /^Ver CUZCO/ }).click();

    await expect(page.locator('[data-detalle-titulo]')).toHaveText('Campaña 36 · lote 11');
    await expect(page.locator('[data-detalle-pendiente]')).toBeHidden();
  });

  test('una descartada dice el día en que se descartó y no ofrece importar', async ({ page }) => {
    await abrir(page, seguimientoFalso(), '?campana=30');

    await expect(page.locator('[data-detalle-descartada-texto]')).toContainText('Descartada el');
    await expect(page.locator('[data-detalle-pendiente]')).toBeHidden();
  });

  test('los archivos dicen qué son, y se descargan', async ({ page }) => {
    const estado = await abrir(page, seguimientoFalso(), '?campana=37');
    await expect(detalle(page)).toBeVisible();

    await expect(detalle(page).locator('.wm-ficha__rotulo')).toHaveText(['Lista de contactos', 'Foto de perfil', 'Adjunto']);
    const delArchivo = page.waitForEvent('download');
    await detalle(page).locator('.wm-ficha__archivo button').first().click();
    expect((await delArchivo).suggestedFilename()).toBe('campana-37.xlsx');
    expect(estado.descargas).toEqual([37]);
    const delAdjunto = page.waitForEvent('download');
    await detalle(page).locator('.wm-ficha__archivo button').nth(2).click();
    expect((await delAdjunto).suggestedFilename()).toBe('afiche-octubre.jpg');
  });

  test('la ficha trae el mensaje congelado, cada dato con su «Copiar»', async ({ page }) => {
    await page.context().grantPermissions(['clipboard-read', 'clipboard-write']);
    await abrir(page, seguimientoFalso(), '?campana=37');
    await expect(detalle(page)).toBeVisible();

    const datos = detalle(page).locator('.wm-ficha__dato');
    await expect(datos.locator('dt')).toHaveText([
      'Nombre de campaña',
      'Fecha y horarios',
      'Lo antes posible',
      'País',
      '¿Cuántos teléfonos tiene en su Lista de contactos?',
      'Tipo de envío',
      'Texto del mensaje',
    ]);
    await expect(datos.nth(6).locator('.wm-ficha__valor')).toContainText('INFO por https://wa.me/+51900000123 (campaña 37)');
    await expect(datos.nth(5).locator('.wm-ficha__valor')).toHaveText('Texto + imagen');

    await detalle(page).getByRole('button', { name: 'Copiar Texto del mensaje' }).click();
    await expect(page.locator('[data-detalle-copia-estado]')).toHaveText('Copiado: Texto del mensaje');
    expect(await page.evaluate(() => navigator.clipboard.readText())).toContain('(campaña 37)');
  });

  test('las exclusiones de la campaña se paginan de a 10, con su motivo y su detalle', async ({ page }) => {
    await abrir(page, seguimientoFalso(), '?campana=37');
    const filasDeExclusiones = page.locator('[data-detalle-exclusiones] tbody tr');

    await expect(filasDeExclusiones).toHaveCount(10);
    await expect(filasDeExclusiones.first().locator('.tag')).toHaveText('Sin teléfono');
    await expect(filasDeExclusiones.first()).toContainText('No tiene un teléfono registrado.');
    await page.locator('[data-pager-exclusiones] [data-page-next]').click();

    await expect(filasDeExclusiones).toHaveCount(2);
    await expect(page.locator('[data-pager-exclusiones] [data-page-next]')).toBeDisabled();
  });

  test('una macro vacía nombra la macro y la etiqueta de su columna, y sin etiqueta no inventa una', async ({ page }) => {
    await abrir(page, seguimientoFalso(), '?campana=37');
    const filasDeExclusiones = page.locator('[data-detalle-exclusiones] tbody tr');

    await expect(filasDeExclusiones.nth(4).locator('.tag')).toHaveText('Macro vacía');
    await expect(filasDeExclusiones.nth(4)).toContainText('La macro 2 (Nombres del titular) queda vacía y su columna no tiene valor por defecto.');
    await expect(filasDeExclusiones.nth(5)).toContainText('La macro 3 queda vacía y su columna no tiene valor por defecto.');
    await expect(filasDeExclusiones.nth(5)).not.toContainText('(');
  });
});

test.describe('los productos fuera de las campañas del lote', () => {
  test('van en un details cerrado, igual desde dos campañas del mismo lote', async ({ page }) => {
    await abrir(page);

    for (const id of [37, 38]) {
      await fila(page, id).getByRole('button', { name: /^Ver CUZCO/ }).click();
      const fuera = page.locator('[data-detalle-fuera]');
      await expect(fuera).toBeVisible();
      await expect(fuera).not.toHaveAttribute('open', '');
      await expect(page.locator('[data-detalle-fuera-titulo]')).toHaveText('Productos fuera de las campañas del lote 12 (15)');
    }
  });

  test('al abrirlo trae el hint y la misma tabla, paginada', async ({ page }) => {
    await abrir(page, seguimientoFalso(), '?campana=37');
    await page.locator('[data-detalle-fuera-titulo]').click();

    await expect(page.locator('[data-detalle-fuera]')).toHaveAttribute('open', '');
    await expect(page.locator('[data-detalle-fuera] .field__hint').first()).toContainText('No entran en ninguna campaña del lote');
    await expect(page.locator('[data-detalle-fuera-tabla] tbody tr')).toHaveCount(10);
    await page.locator('[data-pager-fuera] [data-page-next]').click();
    await expect(page.locator('[data-detalle-fuera-tabla] tbody tr')).toHaveCount(5);
  });

  test('el motivo y el detalle de cada producto salen con su clave, no con la frase cruda del servidor', async ({ page }) => {
    await abrir(page, seguimientoFalso(), '?campana=37');
    await page.locator('[data-detalle-fuera-titulo]').click();

    const primera = page.locator('[data-detalle-fuera-tabla] tbody tr').first();
    await expect(primera.locator('.tag')).toHaveText('Sin días de atraso');
    await expect(primera).toContainText('No tiene días de atraso, así que no cae en ningún segmento. En el modo «Global» sí entraría.');
  });

  test('no aparece con cero, ni en una campaña global', async ({ page }) => {
    await abrir(page);

    await fila(page, 36).getByRole('button', { name: /^Ver CUZCO/ }).click();
    await expect(detalle(page)).toBeVisible();
    await expect(page.locator('[data-detalle-fuera]')).toBeHidden();

    await page.locator('[data-vista="descartadas"]').click();
    await fila(page, 30).getByRole('button', { name: /^Ver CUZCO/ }).click();
    await expect(page.locator('[data-detalle-titulo]')).toContainText('Campaña 30');
    await expect(page.locator('[data-detalle-fuera]')).toBeHidden();
  });

  test('cerrado se queda cerrado al cambiar de campaña', async ({ page }) => {
    await abrir(page, seguimientoFalso(), '?campana=37');
    await page.locator('[data-detalle-fuera-titulo]').click();
    await expect(page.locator('[data-detalle-fuera]')).toHaveAttribute('open', '');

    await fila(page, 38).getByRole('button', { name: /^Ver CUZCO/ }).click();

    await expect(page.locator('[data-detalle-titulo]')).toContainText('Campaña 38');
    await expect(page.locator('[data-detalle-fuera]')).not.toHaveAttribute('open', '');
  });
});

test.describe('descartar, restaurar y eliminar', () => {
  const dialogo = (page: Page) => page.locator('[data-dialog="confirmar"]');

  test('descartar pide confirmar, y al aceptar la campaña pasa a las descartadas con su aviso', async ({ page }) => {
    const estado = await abrir(page);

    await fila(page, 37).getByRole('button', { name: /^Descartar/ }).click();

    await expect(dialogo(page)).toBeVisible();
    await expect(dialogo(page).locator('[data-confirmar-titulo]')).toHaveText('Descartar la campaña 37');
    await expect(dialogo(page).locator('[data-confirmar-cuerpo]')).toContainText('No se borra nada: se puede restaurar.');
    expect(estado.acciones).toEqual([]);

    await dialogo(page).getByRole('button', { name: 'Descartar', exact: true }).click();

    await expect(dialogo(page)).toBeHidden();
    expect(estado.acciones).toEqual(['DESCARTAR 37']);
    await expect(estadoLista(page)).toHaveText('Se descartó la campaña 37.');
    await expect(page.locator('[data-vista="activas"]')).toHaveText('Activas (3)');
    await expect(page.locator('[data-vista="descartadas"]')).toHaveText('Descartadas (2)');
    expect(await ids(page)).toEqual([38, 36, 35]);
    await expect(page.locator('[data-pendientes]')).toContainText('1 campaña pendiente del informe');
  });

  test('cancelar no cambia nada', async ({ page }) => {
    const estado = await abrir(page);
    await fila(page, 37).getByRole('button', { name: /^Descartar/ }).click();

    await dialogo(page).getByRole('button', { name: 'Cancelar' }).click();

    await expect(dialogo(page)).toBeHidden();
    expect(estado.acciones).toEqual([]);
    expect(await ids(page)).toEqual([38, 37, 36, 35]);
  });

  test('descartar con el detalle abierto lo deja abierto, ahora con el aviso de descartada', async ({ page }) => {
    await abrir(page, seguimientoFalso(), '?campana=37');
    await expect(detalle(page)).toBeVisible();
    await expect(page.locator('[data-detalle-descartada]')).toBeHidden();

    await page.locator('tr[data-campana="37"]').getByRole('button', { name: /^Descartar/ }).click();
    await dialogo(page).getByRole('button', { name: 'Descartar', exact: true }).click();

    await expect(page.locator('[data-detalle-descartada]')).toBeVisible();
    await expect(page.locator('[data-detalle-pendiente]')).toBeHidden();
  });

  test('restaurar vuelve la campaña a las activas', async ({ page }) => {
    const estado = await abrir(page, seguimientoFalso(), '?vista=descartadas');

    await fila(page, 30).getByRole('button', { name: /^Restaurar/ }).click();
    await expect(dialogo(page).locator('[data-confirmar-titulo]')).toHaveText('Restaurar la campaña 30');
    await dialogo(page).getByRole('button', { name: 'Restaurar', exact: true }).click();

    await expect(estadoLista(page)).toHaveText('Se restauró la campaña 30.');
    expect(estado.acciones).toEqual(['RESTAURAR 30']);
    await expect(page.locator('[data-vista="activas"]')).toHaveText('Activas (5)');
    await expect(page.locator('[data-vista="descartadas"]')).toHaveText('Descartadas (0)');
  });

  test('eliminar es solo de una descartada, dice que no se puede deshacer y pide marcarlo', async ({ page }) => {
    const estado = await abrir(page, seguimientoFalso(), '?vista=descartadas');

    await fila(page, 30).getByRole('button', { name: /^Eliminar definitivamente/ }).click();

    await expect(dialogo(page).locator('[data-confirmar-titulo]')).toHaveText('Eliminar definitivamente la campaña 30');
    await expect(dialogo(page).locator('[data-confirmar-cuerpo]')).toContainText('La biblioteca de adjuntos y los mensajes no cambian. No se puede deshacer.');
    const aceptar = dialogo(page).getByRole('button', { name: 'Eliminar definitivamente' });
    await expect(aceptar).toBeDisabled();
    await dialogo(page).getByLabel('Entiendo que no se puede deshacer').check();
    await expect(aceptar).toBeEnabled();

    await aceptar.click();

    await expect(estadoLista(page)).toHaveText('Se eliminó la campaña 30.');
    expect(estado.acciones).toEqual(['ELIMINAR 30']);
    await expect(page.locator('[data-vista="descartadas"]')).toHaveText('Descartadas (0)');
    await expect(page.locator('[data-tabla] .empty')).toHaveText('No hay campañas descartadas.');
  });

  test('si la campaña seguía activa, el 409 se dice en el diálogo y nada se borra', async ({ page }) => {
    const estado = seguimientoFalso();
    estado.respuestas.eliminar.push({
      estado: 409,
      cuerpo: { detail: 'La campaña está activa: solo se elimina una descartada', codigo: 'campana_no_descartada' },
    });
    await abrir(page, estado, '?vista=descartadas');
    await fila(page, 30).getByRole('button', { name: /^Eliminar definitivamente/ }).click();
    await dialogo(page).getByLabel('Entiendo que no se puede deshacer').check();

    await dialogo(page).getByRole('button', { name: 'Eliminar definitivamente' }).click();

    await expect(dialogo(page).locator('[data-confirmar-error]')).toHaveText('Solo se puede eliminar una campaña descartada. Descártala primero.');
    await expect(dialogo(page)).toBeVisible();
    expect(await ids(page)).toEqual([30]);
  });

  test('eliminar la campaña que está abierta cierra su detalle', async ({ page }) => {
    await abrir(page, seguimientoFalso(), '?campana=30');
    await expect(detalle(page)).toBeVisible();

    await page.locator('tr[data-campana="30"]').getByRole('button', { name: /^Eliminar definitivamente/ }).click();
    await dialogo(page).getByLabel('Entiendo que no se puede deshacer').check();
    await dialogo(page).getByRole('button', { name: 'Eliminar definitivamente' }).click();

    await expect(detalle(page)).toBeHidden();
    await expect(page).not.toHaveURL(/campana=/);
  });
});

test.describe('a 360 px y en inglés', () => {
  test('la página no desborda y la tabla se apila', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    await abrir(page, seguimientoFalso(), '?campana=37');
    await expect(detalle(page)).toBeVisible();

    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360);
    await expect(page.locator('[data-tabla] table')).toHaveClass(/table--apilable/);
    await expect(page.locator('[data-detalle-exclusiones] table')).toHaveClass(/table--apilable/);
  });

  test('se traduce lo que dibuja el script', async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' })));
    await montarApiWhatsmkt(page, apiWhatsmkt());
    await montarSeguimientoWhatsmkt(page, seguimientoFalso());
    await page.goto(`${RUTA}?campana=37`);

    await expect(page.getByRole('heading', { name: 'WhatsMKT tracking', level: 1 })).toBeVisible();
    await expect(page.locator('[data-detalle-titulo]')).toHaveText('Campaign 37 · Preventivo · batch 12');
    await expect(page.locator('[data-pendientes]')).toContainText('2 campaigns with the report pending');
    await expect(page.locator('[data-detalle-fuera-titulo]')).toHaveText('Products outside the campaigns of batch 12 (15)');
  });

  test('en inglés, el motivo y el detalle de «sin días de atraso» salen en inglés', async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' })));
    await montarApiWhatsmkt(page, apiWhatsmkt());
    await montarSeguimientoWhatsmkt(page, seguimientoFalso());
    await page.goto(`${RUTA}?campana=37`);
    await expect(detalle(page)).toBeVisible();
    await page.locator('[data-detalle-fuera-titulo]').click();

    const primera = page.locator('[data-detalle-fuera-tabla] tbody tr').first();
    await expect(primera.locator('.tag')).toHaveText('No days overdue');
    await expect(primera).toContainText('It has no days overdue, so it falls in no segment. In “Global” mode it would be included.');
    await expect(page.locator('[data-tabla] th').filter({ hasText: 'Send date' })).toHaveCount(1);
  });
});

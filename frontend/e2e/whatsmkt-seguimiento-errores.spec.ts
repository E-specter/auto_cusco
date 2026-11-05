/**
 * The WhatsMKT tracking screen when something fails (T-WM-F3a): the API down, a view or a detail that does not load, a discard, a restore or a
 * delete that is refused or never answered, a delete of what somebody else already deleted, a download that fails, and where the focus goes when a
 * confirmation closes (axe does not see that). Same fake as `whatsmkt-seguimiento.spec.ts`, with its failures scripted. Every text is invented.
 */
import { expect, test, type Page } from '@playwright/test';

import { apiWhatsmkt, montarApiWhatsmkt } from './api-falsa-whatsmkt';
import { montarSeguimientoWhatsmkt, seguimientoFalso, type SeguimientoFalso } from './api-falsa-whatsmkt-seguimiento';

const RUTA = '/whatsmkt/seguimiento';
const SIN_API = 'No se pudo contactar con la API. Comprueba que el backend esté en marcha.';

async function montar(page: Page, estado: SeguimientoFalso, busqueda = ''): Promise<void> {
  await montarApiWhatsmkt(page, apiWhatsmkt());
  await montarSeguimientoWhatsmkt(page, estado);
  await page.goto(`${RUTA}${busqueda}`);
}

async function abrir(page: Page, estado: SeguimientoFalso, busqueda = ''): Promise<SeguimientoFalso> {
  await montar(page, estado, busqueda);
  await expect(page.locator('[data-vista="activas"]')).toContainText('Activas (');
  return estado;
}

const fila = (page: Page, id: number) => page.locator(`tr[data-campana="${id}"]`);
const detalle = (page: Page) => page.locator('[data-detalle]');
const estadoLista = (page: Page) => page.locator('[data-lista-estado]');
const dialogo = (page: Page) => page.locator('[data-dialog="confirmar"]');
const dialogoError = (page: Page) => page.locator('[data-dialog="error"]');
const ids = (page: Page) => page.locator('[data-tabla] tbody tr').evaluateAll((trs) => trs.map((tr) => Number((tr as HTMLElement).dataset.campana)));
const accion = (page: Page, id: number, nombre: RegExp) => fila(page, id).getByRole('button', { name: nombre });
const borrada = (estado: SeguimientoFalso, id: number): void => {
  estado.campanas = estado.campanas.filter((c) => c.resumen.id !== id);
};

test.describe('la API caída al abrir', () => {
  test('sin conexión lo dice, y Reintentar vuelve a pedir la lista hasta que la API contesta', async ({ page }) => {
    const estado = seguimientoFalso();
    estado.fallos.lista = ['red', 'red', null];
    await montar(page, estado);

    await expect(page.getByRole('heading', { name: 'Sin conexión con la API', level: 2 })).toBeVisible();
    await expect(page.locator('[data-contenido]')).toBeHidden();

    await page.getByRole('button', { name: 'Reintentar' }).click();
    await expect(page.locator('[data-offline]')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Reintentar' })).toBeEnabled();

    await page.getByRole('button', { name: 'Reintentar' }).click();
    await expect(page.locator('[data-offline]')).toBeHidden();
    await expect(page.locator('[data-vista="activas"]')).toHaveText('Activas (4)');
    expect(await ids(page)).toEqual([38, 37, 36, 35]);
  });
});

test.describe('cambiar de vista con la lista caída', () => {
  test('un error del servidor se dice y la pantalla se queda con la vista que tenía, también en la URL', async ({ page }) => {
    const estado = seguimientoFalso();
    estado.fallos.lista = [null, { estado: 500, cuerpo: { detail: 'La base de datos no responde' } }, null];
    await abrir(page, estado);

    await page.locator('[data-vista="descartadas"]').click();

    await expect(dialogoError(page)).toBeVisible();
    await expect(dialogoError(page).locator('[data-error-body]')).toHaveText('La base de datos no responde');
    await dialogoError(page).getByRole('button', { name: 'Cerrar' }).click();
    await expect(page).toHaveURL(/\/whatsmkt\/seguimiento$/);
    await expect(page.locator('[data-vista="activas"]')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('[data-vista="descartadas"]')).toHaveAttribute('aria-pressed', 'false');
    expect(await ids(page)).toEqual([38, 37, 36, 35]);

    // Once the API answers, the same click works: nothing was left half done.
    await page.locator('[data-vista="descartadas"]').click();
    await expect(page).toHaveURL(/\/whatsmkt\/seguimiento\?vista=descartadas$/);
    await expect.poll(() => ids(page)).toEqual([30]);
  });

  test('un corte de red lo dice, y Reintentar vuelve a la vista que se veía', async ({ page }) => {
    const estado = seguimientoFalso();
    estado.fallos.lista = [null, 'red', null];
    await abrir(page, estado);

    await page.locator('[data-vista="descartadas"]').click();

    await expect(page.locator('[data-offline]')).toBeVisible();
    await page.getByRole('button', { name: 'Reintentar' }).click();
    await expect(page.locator('[data-offline]')).toBeHidden();
    await expect(page).toHaveURL(/\/whatsmkt\/seguimiento$/);
    await expect(page.locator('[data-vista="activas"]')).toHaveAttribute('aria-pressed', 'true');
    expect(await ids(page)).toEqual([38, 37, 36, 35]);
  });
});

test.describe('un detalle que no carga', () => {
  test('con un error del servidor lo dice en la línea de estado, no abre nada y se puede volver a intentar', async ({ page }) => {
    const estado = seguimientoFalso();
    estado.fallos.detalle = [{ estado: 500, cuerpo: { detail: 'No se pudo leer la campaña' } }, null];
    await abrir(page, estado);

    await accion(page, 37, /^Ver CUZCO/).click();

    await expect(estadoLista(page)).toHaveText('No se pudo leer la campaña');
    await expect(detalle(page)).toBeHidden();
    await expect(page).not.toHaveURL(/campana=/);

    await accion(page, 37, /^Ver CUZCO/).click();
    await expect(detalle(page)).toBeVisible();
    await expect(estadoLista(page)).toHaveText('');
  });

  test('con un corte de red dice que no se pudo contactar con la API', async ({ page }) => {
    const estado = seguimientoFalso();
    estado.fallos.detalle = ['red', null];
    await abrir(page, estado);

    await accion(page, 37, /^Ver CUZCO/).click();

    await expect(estadoLista(page)).toHaveText(SIN_API);
    await expect(detalle(page)).toBeHidden();
  });
});

test.describe('descartar, restaurar y eliminar con error', () => {
  test('un error del servidor se queda en el diálogo, nada cambia, y se puede aceptar de nuevo', async ({ page }) => {
    const estado = seguimientoFalso();
    estado.respuestas.descartar = [{ estado: 500, cuerpo: { detail: 'Error interno del servidor' } }, null];
    await abrir(page, estado);
    await accion(page, 37, /^Descartar/).click();
    const aceptar = dialogo(page).getByRole('button', { name: 'Descartar', exact: true });

    await aceptar.click();

    await expect(dialogo(page).locator('[data-confirmar-error]')).toHaveText('Error interno del servidor');
    await expect(dialogo(page)).toBeVisible();
    expect(await ids(page)).toEqual([38, 37, 36, 35]);
    await expect(estadoLista(page)).toHaveText('');
    // The focus stays in the dialog, on the button that was pressed, so the keyboard can try again.
    await expect(aceptar).toBeFocused();

    await aceptar.click();
    await expect(dialogo(page)).toBeHidden();
    await expect(estadoLista(page)).toHaveText('Se descartó la campaña 37.');
    expect(estado.acciones).toEqual(['DESCARTAR 37', 'DESCARTAR 37']);
  });

  test('un corte de red dice que no se pudo contactar con la API y no cambia nada', async ({ page }) => {
    const estado = seguimientoFalso();
    estado.respuestas.descartar = ['red'];
    await abrir(page, estado);
    await accion(page, 37, /^Descartar/).click();

    await dialogo(page).getByRole('button', { name: 'Descartar', exact: true }).click();

    await expect(dialogo(page).locator('[data-confirmar-error]')).toHaveText(SIN_API);
    expect(await ids(page)).toEqual([38, 37, 36, 35]);
  });

  test('un código de la API se dice con la frase de ese código', async ({ page }) => {
    const estado = seguimientoFalso();
    estado.respuestas.descartar = [{ estado: 409, cuerpo: { detail: 'La campaña ya está descartada', codigo: 'campana_descartada' } }];
    await abrir(page, estado);
    await accion(page, 37, /^Descartar/).click();

    await dialogo(page).getByRole('button', { name: 'Descartar', exact: true }).click();

    await expect(dialogo(page).locator('[data-confirmar-error]')).toHaveText('La campaña está descartada. Restáurala primero.');
  });

  test('restaurar con un error lo dice en el diálogo y la campaña sigue descartada', async ({ page }) => {
    const estado = seguimientoFalso();
    estado.respuestas.restaurar = [{ estado: 404, cuerpo: { detail: 'No existe la campaña' } }];
    await abrir(page, estado, '?vista=descartadas');
    await accion(page, 30, /^Restaurar/).click();

    await dialogo(page).getByRole('button', { name: 'Restaurar', exact: true }).click();

    await expect(dialogo(page).locator('[data-confirmar-error]')).toHaveText('No existe la campaña');
    await expect(dialogo(page)).toBeVisible();
    expect(await ids(page)).toEqual([30]);
  });

  test('eliminar lo que otro ya borró (404) se da por hecho: la lista lo quita y el detalle abierto se cierra', async ({ page }) => {
    const estado = await abrir(page, seguimientoFalso(), '?campana=30');
    await expect(detalle(page)).toBeVisible();
    // The campaign is discarded, so the screen moves to that view: its row is there once the list came.
    await expect(accion(page, 30, /^Eliminar definitivamente/)).toBeVisible();
    borrada(estado, 30);

    await accion(page, 30, /^Eliminar definitivamente/).click();
    await dialogo(page).getByLabel('Entiendo que no se puede deshacer').check();
    await dialogo(page).getByRole('button', { name: 'Eliminar definitivamente' }).click();

    await expect(dialogo(page)).toBeHidden();
    await expect(estadoLista(page)).toHaveText('Se eliminó la campaña 30.');
    await expect(page.locator('[data-tabla] .empty')).toHaveText('No hay campañas descartadas.');
    await expect(detalle(page)).toBeHidden();
    await expect(page).not.toHaveURL(/campana=/);
  });
});

test.describe('una descarga que falla', () => {
  test('desde la lista abre el diálogo de error, el foco vuelve al botón y se puede volver a intentar', async ({ page }) => {
    const estado = seguimientoFalso();
    estado.fallos.archivo = [{ estado: 500, cuerpo: { detail: 'El archivo no está disponible' } }, null];
    await abrir(page, estado);

    await accion(page, 37, /^Descargar/).click();

    await expect(dialogoError(page)).toBeVisible();
    await expect(dialogoError(page).locator('[data-error-body]')).toHaveText('El archivo no está disponible');
    expect(estado.descargas).toEqual([]);
    await dialogoError(page).getByRole('button', { name: 'Cerrar' }).click();
    await expect(accion(page, 37, /^Descargar/)).toBeFocused();

    const descarga = page.waitForEvent('download');
    await accion(page, 37, /^Descargar/).click();
    expect((await descarga).suggestedFilename()).toBe('campana-37.xlsx');
  });

  test('desde el detalle lo dice junto a los archivos, y con un corte de red dice que no hay API', async ({ page }) => {
    const estado = seguimientoFalso();
    estado.fallos.archivo = [{ estado: 500, cuerpo: { detail: 'El archivo no está disponible' } }, 'red', null];
    await abrir(page, estado, '?campana=37');
    await expect(detalle(page)).toBeVisible();
    const descargar = detalle(page).locator('.wm-ficha__archivo button').first();
    const error = page.locator('[data-detalle-descarga-error]');

    await descargar.click();
    await expect(error).toHaveText('El archivo no está disponible');

    await descargar.click();
    await expect(error).toHaveText(SIN_API);
    expect(estado.descargas).toEqual([]);

    const descarga = page.waitForEvent('download');
    await descargar.click();
    expect((await descarga).suggestedFilename()).toBe('campana-37.xlsx');
  });
});

test.describe('el foco al cerrar una confirmación', () => {
  test('cancelar lo devuelve al botón que abrió el diálogo', async ({ page }) => {
    await abrir(page, seguimientoFalso());
    await accion(page, 37, /^Descartar/).click();

    await dialogo(page).getByRole('button', { name: 'Cancelar' }).click();

    await expect(dialogo(page)).toBeHidden();
    await expect(accion(page, 37, /^Descartar/)).toBeFocused();
  });

  test('Escape también', async ({ page }) => {
    await abrir(page, seguimientoFalso());
    await accion(page, 37, /^Descartar/).click();
    await expect(dialogo(page)).toBeVisible();

    await page.keyboard.press('Escape');

    await expect(dialogo(page)).toBeHidden();
    await expect(accion(page, 37, /^Descartar/)).toBeFocused();
  });

  test('tras descartar, el foco queda en la lista (la fila ya no está)', async ({ page }) => {
    await abrir(page, seguimientoFalso());
    await accion(page, 37, /^Descartar/).click();

    await dialogo(page).getByRole('button', { name: 'Descartar', exact: true }).click();

    await expect(estadoLista(page)).toHaveText('Se descartó la campaña 37.');
    await expect(page.locator('[data-tabla]')).toBeFocused();
  });

  test('tras eliminar con el detalle abierto, el foco queda en la lista', async ({ page }) => {
    await abrir(page, seguimientoFalso(), '?campana=30');
    await expect(detalle(page)).toBeVisible();
    await accion(page, 30, /^Eliminar definitivamente/).click();
    await dialogo(page).getByLabel('Entiendo que no se puede deshacer').check();

    await dialogo(page).getByRole('button', { name: 'Eliminar definitivamente' }).click();

    await expect(estadoLista(page)).toHaveText('Se eliminó la campaña 30.');
    await expect(detalle(page)).toBeHidden();
    await expect(page.locator('[data-tabla]')).toBeFocused();
  });
});

/**
 * The upload console, end to end against an intercepted API.
 *
 * These cover the paths where being wrong costs the analyst something real:
 * uploading and reading the result, and the two confirmations that stand
 * between a click and a change nobody asked for (V-4 and V-8).
 */
import { expect, test } from '@playwright/test';

import { ARCHIVO_SINTETICO, apiVacia, montarApi, version } from './api-falsa';

test.describe('camino feliz: subir una sábana y leer el resumen', () => {
  test('sugiere la fecha, sigue el procesamiento y muestra las cifras', async ({ page }) => {
    const api = apiVacia();
    api.respuestasSubida = [
      {
        estado: 202,
        cuerpo: {
          id: 7,
          fecha_corte: '2026-09-10',
          version: 1,
          estado: 'en_cola',
          versiones_identicas: [],
          aviso: null,
        },
      },
    ];
    // El sondeo ve primero una versión en curso y luego la terminada.
    const enCurso = version({ id: 7, estado: 'procesando', vigente: false, filas_total: null, filas_ingestadas: null });
    const terminada = version({ id: 7, filas_total: 1500, filas_ingestadas: 1498 });
    api.seguimiento = [enCurso, terminada];
    api.incidencias = [
      { fila: 8, columna: 'pagare', codigo: 'pagare_repetido', severidad: 'error', detalle: 'Pagare ya presente', valor_original: '000000000000000006' },
      { fila: null, columna: 'bpo', codigo: 'columna_faltante', severidad: 'advertencia', detalle: 'Columna esperada ausente', valor_original: null },
    ];
    await montarApi(page, api);

    await page.goto('/cargas');

    // Primera ejecución: un solo bloque, no tres paneles repitiendo la ausencia.
    await expect(page.getByRole('heading', { name: 'Todavía no hay ninguna sábana cargada.' })).toBeVisible();

    await page.getByRole('button', { name: 'Subir sábana' }).click();
    await page.locator('#upload-file').setInputFiles(ARCHIVO_SINTETICO);

    await expect(page.locator('#upload-date')).toHaveValue('2026-09-10');
    await expect(page.getByText('Sugerida desde el nombre del archivo.')).toBeVisible();

    api.versiones = [terminada];
    await page.getByRole('button', { name: 'Registrar versión' }).click();

    await expect(page.locator('[data-progress]')).toBeVisible();

    await expect(page.getByText('1,500')).toBeVisible();
    await expect(page.getByText('1,498')).toBeVisible();
    await expect(page.getByText('2 filas no se guardaron.')).toBeVisible();
    await expect(page.locator('[data-progress]')).toBeHidden();
  });

  test('filtra las incidencias por severidad', async ({ page }) => {
    const api = apiVacia();
    api.versiones = [version({ id: 7 })];
    api.incidencias = [
      { fila: 8, columna: 'pagare', codigo: 'pagare_repetido', severidad: 'error', detalle: 'x', valor_original: null },
      { fila: null, columna: 'bpo', codigo: 'columna_faltante', severidad: 'advertencia', detalle: 'y', valor_original: null },
    ];
    await montarApi(page, api);

    await page.goto('/cargas');
    await page.getByRole('button', { name: 'Error', exact: true }).click();

    await expect(page.getByText('1 incidencia', { exact: true })).toBeVisible();
    await expect(page.getByRole('cell', { name: 'pagare_repetido' })).toBeVisible();
    await expect(page.getByRole('cell', { name: 'columna_faltante' })).toHaveCount(0);
  });

  test('traduce el detalle de la incidencia al idioma de la interfaz', async ({ page }) => {
    const api = apiVacia();
    api.versiones = [version({ id: 7 })];
    api.incidencias = [
      {
        fila: null,
        columna: 'bpo',
        codigo: 'columna_faltante',
        severidad: 'advertencia',
        // El backend siempre responde en español; la consola traduce por código.
        detalle: 'Columna esperada ausente',
        valor_original: null,
      },
    ];
    await montarApi(page, api);

    await page.goto('/cargas');
    await expect(page.getByText('Columna esperada ausente del archivo')).toBeVisible();

    await page.getByRole('button', { name: 'EN', exact: true }).click();

    await expect(page.getByText('Expected column missing from the file')).toBeVisible();
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  });
});

test.describe('V-8: eliminar la versión vigente', () => {
  test('se niega a eliminar la vigente mientras no se confirme', async ({ page }) => {
    const api = apiVacia();
    api.versiones = [version({ id: 7, vigente: true })];
    await montarApi(page, api);

    await page.goto('/cargas');
    await page.getByRole('button', { name: 'Eliminar' }).click();

    const dialogo = page.locator('dialog[data-dialog="delete"]');
    await expect(dialogo).toBeVisible();
    await expect(dialogo.getByText('Esta es la versión vigente del 10 set. 2026.')).toBeVisible();
    await expect(dialogo.locator('[data-delete-confirm]')).not.toBeChecked();

    await dialogo.getByRole('button', { name: 'Eliminar definitivamente' }).click();

    // Sigue abierto, dice por qué, y no llegó ninguna petición de borrado.
    await expect(dialogo).toBeVisible();
    await expect(
      dialogo.getByText('Marca la casilla para confirmar que la fecha queda sin versión vigente.'),
    ).toBeVisible();
    expect(api.pedidos.filter((p) => p.metodo === 'DELETE')).toHaveLength(0);
  });

  test('elimina la vigente solo cuando se confirma que la fecha queda sin vigente', async ({ page }) => {
    const api = apiVacia();
    api.versiones = [version({ id: 7, vigente: true })];
    api.respuestasEliminar = [{ estado: 204 }];
    await montarApi(page, api);

    await page.goto('/cargas');
    await page.getByRole('button', { name: 'Eliminar' }).click();

    const dialogo = page.locator('dialog[data-dialog="delete"]');
    await dialogo.locator('[data-delete-confirm]').check();
    api.versiones = [];
    await dialogo.getByRole('button', { name: 'Eliminar definitivamente' }).click();

    await expect(dialogo).toBeHidden();

    const borrado = api.pedidos.find((p) => p.metodo === 'DELETE');
    expect(borrado?.url).toContain('dejar_fecha_sin_vigente=true');
  });

  test('no pide confirmación para una versión que no es la vigente', async ({ page }) => {
    const api = apiVacia();
    api.versiones = [
      version({ id: 8, version: 2, vigente: false }),
      version({ id: 7, version: 1, vigente: true }),
    ];
    api.respuestasEliminar = [{ estado: 204 }];
    await montarApi(page, api);

    await page.goto('/cargas');
    await page.getByRole('button', { name: 'Eliminar' }).first().click();

    const dialogo = page.locator('dialog[data-dialog="delete"]');
    await expect(dialogo).toBeVisible();
    await expect(dialogo.locator('[data-delete-vigente]')).toBeHidden();
  });
});

test.describe('V-4: qué versión se considera', () => {
  test('pregunta al terminar y deja preseleccionado mantener la vigente', async ({ page }) => {
    const api = apiVacia();
    const vigenteActual = version({ id: 7, version: 1, vigente: true });
    const nueva = version({ id: 8, version: 2, vigente: false, filas_ingestadas: 1520 });
    api.versiones = [vigenteActual];
    api.respuestasSubida = [
      {
        estado: 202,
        cuerpo: {
          id: 8,
          fecha_corte: '2026-09-10',
          version: 2,
          estado: 'en_cola',
          versiones_identicas: [],
          aviso: null,
        },
      },
    ];
    api.seguimiento = [nueva];
    await montarApi(page, api);

    await page.goto('/cargas');
    await page.getByRole('button', { name: 'Subir sábana' }).click();
    await page.locator('#upload-file').setInputFiles(ARCHIVO_SINTETICO);
    api.versiones = [nueva, vigenteActual];
    await page.getByRole('button', { name: 'Registrar versión' }).click();

    const dialogo = page.locator('dialog[data-dialog="vigente"]');
    await expect(dialogo).toBeVisible();
    // Decisión C-1: nada cambia sin confirmación explícita.
    await expect(dialogo.locator('input[value="keep"]')).toBeChecked();
    await expect(dialogo.locator('input[value="replace"]')).not.toBeChecked();

    await dialogo.getByRole('button', { name: 'Decidir más tarde' }).click();

    // Cerrar sin decidir no cambia la vigente.
    expect(api.pedidos.filter((p) => p.url.includes('/vigente'))).toHaveLength(0);
  });

  test('espera su turno detrás del aviso de archivo idéntico en vez de taparlo', async ({ page }) => {
    const api = apiVacia();
    const vigenteActual = version({ id: 7, version: 1, vigente: true });
    const nueva = version({ id: 8, version: 2, vigente: false });
    api.versiones = [vigenteActual];
    api.respuestasSubida = [
      {
        estado: 202,
        cuerpo: {
          id: 8,
          fecha_corte: '2026-09-10',
          version: 2,
          estado: 'en_cola',
          // V-6: el archivo es idéntico al de la versión 1.
          versiones_identicas: [1],
          aviso: 'Este archivo es identico al de las versiones [1] de la misma fecha',
        },
      },
    ];
    api.seguimiento = [nueva];
    await montarApi(page, api);

    await page.goto('/cargas');
    await page.getByRole('button', { name: 'Subir sábana' }).click();
    await page.locator('#upload-file').setInputFiles(ARCHIVO_SINTETICO);
    api.versiones = [nueva, vigenteActual];
    await page.getByRole('button', { name: 'Registrar versión' }).click();

    const duplicado = page.locator('dialog[data-dialog="duplicate"]');
    const vigente = page.locator('dialog[data-dialog="vigente"]');

    await expect(duplicado).toBeVisible();
    await expect(vigente).toBeHidden();

    await duplicado.getByRole('button', { name: 'Entendido' }).click();

    // La pregunta no se perdió: aparece cuando el aviso deja de estorbar.
    await expect(vigente).toBeVisible();
    await expect(vigente.locator('input[value="keep"]')).toBeChecked();
  });
});

test.describe('API inalcanzable', () => {
  test('lo dice una sola vez, desactiva subir y ofrece reintentar', async ({ page }) => {
    await page.route('**/api/**', (route) => route.abort('failed'));

    await page.goto('/cargas');

    await expect(page.getByRole('heading', { name: 'Sin conexión con la API' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Sin conexión con la API' })).toHaveCount(1);
    await expect(page.getByRole('button', { name: 'Reintentar' })).toBeVisible();
    await expect(page.locator('.ruler__action')).toBeHidden();
  });

  test('vuelve a la normalidad al reintentar, y la cabecera deja de contradecir la página', async ({ page }) => {
    const api = apiVacia();
    api.versiones = [version({ id: 7 })];

    await page.route('**/api/**', (route) => route.abort('failed'));
    await page.goto('/cargas');
    await expect(page.getByRole('button', { name: 'Reintentar' })).toBeVisible();

    await page.unroute('**/api/**');
    await montarApi(page, api);
    await page.getByRole('button', { name: 'Reintentar' }).click();

    await expect(page.locator('[data-date-node]')).toHaveCount(1);
    await expect(page.locator('[data-health]')).toHaveAttribute('data-state', 'ok');
  });
});

/**
 * MOWA MES follow-up, end to end against an intercepted API (scenarios S1 to
 * S7 agreed with dev_backend in T-MM-B7).
 *
 * What a wrong screen costs here is a campaign read as sent when it was not:
 * so "sent" is checked apart from the rows that merely match the campaign, and
 * a MES id imported twice never overwrites without asking. Every value is
 * synthetic: 900000xxx phones, 99xxxxxxx MES ids.
 */
import { expect, test, type Page } from '@playwright/test';

import {
  apiMowaMes,
  campanaSintetica,
  conciliacionSintetica,
  consumoSintetico,
  exclusionesSinteticas,
  montarApiMowaMes,
  type ApiFalsaMowaMes,
} from './api-falsa-mowa-mes';

const RUTA = '/mowa-mes/seguimiento';

// The API sends timestamps in UTC; the screen shows them in the analyst's time,
// which is Lima's. Pinning the zone makes that conversion part of the scenario.
test.use({ timezoneId: 'America/Lima' });

const REPORTE = {
  name: 'REPORTE_SINTETICO.xlsx',
  mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  buffer: Buffer.from('reporte sintetico de prueba'),
};

const dos = (n: number) => String(n).padStart(2, '0');
function mesRelativo(delta: number): string {
  const hoy = new Date();
  const fecha = new Date(hoy.getFullYear(), hoy.getMonth() + delta, 1);
  return `${fecha.getFullYear()}-${dos(fecha.getMonth() + 1)}`;
}

/** Requests to exactly `ruta` (query ignored). */
const pedidosA = (api: ApiFalsaMowaMes, metodo: string, ruta: string) =>
  api.pedidos.filter((p) => p.metodo === metodo && p.ruta.split('?')[0] === ruta);

const parametro = (ruta: string, nombre: string) => new URL(ruta, 'http://x').searchParams.get(nombre);

const cifra = (page: Page, host: string, etiqueta: string) =>
  page.locator(host).locator('.stat', { hasText: etiqueta }).locator('.stat__value');

async function abrir(page: Page, api: ApiFalsaMowaMes): Promise<void> {
  await montarApiMowaMes(page, api);
  await page.goto(RUTA);
  await expect(page.getByRole('heading', { name: 'Seguimiento de MOWA MES', level: 1 })).toBeVisible();
}

async function importarReporte(page: Page): Promise<void> {
  await page.getByLabel('Archivo del reporte').setInputFiles(REPORTE);
  await page.getByRole('button', { name: 'Importar reporte' }).click();
}

test.describe('S1: listado de campañas', () => {
  test('lista las más recientes primero, pagina de a 20 y separa productos, supervisión y total', async ({ page }) => {
    const api = apiMowaMes();
    api.campanas = Array.from({ length: 25 }, (_, i) =>
      campanaSintetica({ id: 25 - i, descripcion: `Campaña sintética ${25 - i}` }),
    );
    await abrir(page, api);

    const filas = page.locator('.mm-campanas__tabla tbody tr');
    await expect(filas).toHaveCount(20);
    await expect(filas.first()).toContainText('Campaña sintética 25');
    // creado_en 02:00 UTC on the 15th crosses midnight: in Lima it is still the 14th.
    await expect(filas.first().getByRole('cell', { name: '14.09 · 21:00' })).toBeVisible();
    await expect(page.locator('[data-campanas-cuenta]')).toHaveText('25 campañas');
    const paginador = page.locator('[data-campanas-pager]');
    await expect(paginador.locator('[data-rango]')).toHaveText('1–20 de 25');

    // RF-41: the detail never folds supervision into the products.
    await expect(page.getByRole('heading', { name: 'Campaña 25' })).toBeVisible();
    await expect(cifra(page, '[data-detalle-cifras]', 'Productos cargados')).toHaveText('980');
    await expect(cifra(page, '[data-detalle-cifras]', 'Supervisión')).toHaveText('2');
    await expect(cifra(page, '[data-detalle-cifras]', 'Total cargados')).toHaveText('982');

    await paginador.getByRole('button', { name: 'Siguientes' }).click();

    await expect(filas).toHaveCount(5);
    await expect(paginador.locator('[data-rango]')).toHaveText('21–25 de 25');
    expect(pedidosA(api, 'GET', '/mowa-mes/campanas').map((p) => parametro(p.ruta, 'desplazamiento'))).toEqual([
      '0',
      '20',
    ]);
  });

  test('sin campañas lo dice en vez de mostrar una tabla vacía', async ({ page }) => {
    const api = apiMowaMes();
    api.campanas = [];
    await abrir(page, api);

    await expect(page.getByText('Todavía no hay campañas generadas.')).toBeVisible();
    await expect(page.getByText('Elige una campaña para ver su detalle.')).toBeVisible();
  });
});

test.describe('S2: consumo del límite mensual', () => {
  test('cambia de mes, pide ese mes y marca el exceso', async ({ page }) => {
    const anterior = mesRelativo(-1);
    const api = apiMowaMes();
    api.consumo = (mes) =>
      mes === anterior
        ? consumoSintetico(mes, { cargados_mes: 2_600_000, total: 2_600_000, disponible: -100_000, excedido: true })
        : consumoSintetico(mes);
    await abrir(page, api);

    const cargados = cifra(page, '[data-limite-cifras]', 'Cargados en el mes');
    await expect(cargados).toHaveText('982');
    await expect(page.locator('[data-limite-excedido]')).toBeHidden();

    await page.getByRole('button', { name: 'Mes anterior' }).click();

    await expect(cargados).toHaveText('2,600,000');
    await expect(cifra(page, '[data-limite-cifras]', 'Disponible')).toHaveText('-100,000');
    await expect(page.getByText('El mes superó el límite: 2,600,000 cargados de 2,500,000.')).toBeVisible();
    expect(pedidosA(api, 'GET', '/mowa-mes/limite-mensual').map((p) => parametro(p.ruta, 'mes'))).toEqual([
      mesRelativo(0),
      anterior,
    ]);
  });
});

test.describe('archivos de carga', () => {
  test('descarga con el nombre y el resumen que manda el servidor', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);

    const descarga = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Descargar el archivo 1' }).click();

    expect((await descarga).suggestedFilename()).toBe('mowa_mes_campana_1_1_de_1.xlsx');
    await expect(page.getByText('Archivo 1 de 1 descargado: 982 filas, 2 de supervisión.')).toBeVisible();
  });
});

test.describe('S3: importar y conciliar', () => {
  test('enviados cuenta solo el estado «enviado» y lo que coincide por id no se rotula como enviado', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);
    await expect(
      page.getByText('Todavía no se importó ningún reporte de enviados para esta campaña.'),
    ).toBeVisible();

    await importarReporte(page);

    await expect(page.getByText('Reporte importado.')).toBeVisible();
    const total = page.locator('.mm-conciliacion__tabla tr[data-grupo="total"]');
    await expect(total.getByRole('cell').nth(0)).toHaveText('982');
    await expect(total.getByRole('cell').nth(1)).toHaveText('952');
    await expect(total.getByRole('cell').nth(2)).toHaveText('30');
    await expect(page.locator('.mm-conciliacion__tabla tr[data-grupo="supervision"]').getByRole('cell').nth(1)).toHaveText('2');

    const ids = page.locator('.mm-ids__tabla');
    await expect(ids.getByRole('columnheader', { name: 'Coinciden con la campaña (cualquier estado)' })).toBeVisible();
    await expect(ids.getByRole('columnheader', { name: /enviad/i })).toHaveCount(0);
    await expect(ids.getByRole('cell', { name: '977' })).toBeVisible();
    await expect(page.getByText('Filas del reporte sin correspondencia en la campaña: 8')).toBeVisible();
    // importado_en 02:30 UTC on the 16th crosses midnight: in Lima it is the 15th.
    await expect(
      page.getByText('Id 990000001 · REPORTE_SINTETICO.xlsx · 985 filas · 15.09 · 21:30'),
    ).toBeVisible();

    const [envio] = pedidosA(api, 'POST', '/mowa-mes/campanas/1/reportes');
    expect(envio.cuerpo).toContain('name="archivo"');
    expect(envio.cuerpo).toMatch(/name="reemplazar"\r\n\r\nfalse/);
  });

  test('sin archivo elegido no llama a la API', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);

    await page.getByRole('button', { name: 'Importar reporte' }).click();

    await expect(page.locator('[data-reporte-error]')).toHaveText('Elige el archivo del reporte.');
    expect(pedidosA(api, 'POST', '/mowa-mes/campanas/1/reportes')).toEqual([]);
  });
});

test.describe('S4: reimportar un id ya importado', () => {
  test('pide confirmación con «No reemplazar» preseleccionado y reenvía con reemplazar=true', async ({ page }) => {
    const api = apiMowaMes();
    api.respuestas.importarReporte = [
      { estado: 409, cuerpo: { detail: 'El id de MES 990000001 ya estaba importado' } },
      { estado: 201, cuerpo: conciliacionSintetica(1) },
    ];
    await abrir(page, api);

    await importarReporte(page);

    const dialogo = page.getByRole('dialog', { name: 'Este reporte ya estaba importado' });
    await expect(dialogo).toBeVisible();
    await expect(dialogo.getByText('El id de MES 990000001 ya estaba importado')).toBeVisible();
    await expect(dialogo.getByRole('button', { name: 'No reemplazar' })).toBeFocused();

    await dialogo.getByRole('button', { name: 'Reemplazar', exact: true }).click();

    await expect(page.getByText('Reporte importado.')).toBeVisible();
    const envios = pedidosA(api, 'POST', '/mowa-mes/campanas/1/reportes');
    expect(envios).toHaveLength(2);
    expect(envios[1].cuerpo).toMatch(/name="reemplazar"\r\n\r\ntrue/);
  });

  test('«No reemplazar» cierra sin volver a enviar', async ({ page }) => {
    const api = apiMowaMes();
    api.respuestas.importarReporte = [{ estado: 409, cuerpo: { detail: 'El id de MES 990000001 ya estaba importado' } }];
    await abrir(page, api);

    await importarReporte(page);
    const dialogo = page.getByRole('dialog', { name: 'Este reporte ya estaba importado' });
    await dialogo.getByRole('button', { name: 'No reemplazar' }).click();

    await expect(dialogo).toBeHidden();
    expect(pedidosA(api, 'POST', '/mowa-mes/campanas/1/reportes')).toHaveLength(1);
  });
});

test.describe('S5: id sin correspondencia', () => {
  test('advierte con el id de MES que no es de esta campaña', async ({ page }) => {
    const api = apiMowaMes();
    api.respuestas.importarReporte = [
      {
        estado: 201,
        cuerpo: conciliacionSintetica(1, {
          por_id: [
            { mes_id: 990000001, filas: 985, con_correspondencia: 977 },
            { mes_id: 990000777, filas: 12, con_correspondencia: 0 },
          ],
          advertencias: [
            { codigo: 'id_sin_correspondencia', tipo: 'advertencia', mes_id: 990000777, detalle: 'detalle del servidor' },
          ],
        }),
      },
    ];
    await abrir(page, api);

    await importarReporte(page);

    await expect(
      page.getByText(
        'Un id de MES del reporte no coincide con ninguna fila cargada de esta campaña: probablemente es de otra. Id de MES: 990000777.',
      ),
    ).toBeVisible();
  });
});

test.describe('S6: reportes rechazados', () => {
  test('un 400 muestra el motivo del servidor junto al archivo', async ({ page }) => {
    const api = apiMowaMes();
    api.respuestas.importarReporte = [{ estado: 400, cuerpo: { detail: 'Faltan columnas en el reporte: estado' } }];
    await abrir(page, api);

    await importarReporte(page);

    await expect(page.locator('[data-reporte-error]')).toHaveText('Faltan columnas en el reporte: estado');
    await expect(page.getByLabel('Archivo del reporte')).toHaveAttribute('aria-invalid', 'true');
  });

  test('un 413 muestra un mensaje propio y traducido, no el detalle crudo', async ({ page }) => {
    const api = apiMowaMes();
    api.respuestas.importarReporte = [{ estado: 413, cuerpo: { detail: 'Request Entity Too Large' } }];
    await abrir(page, api);

    await importarReporte(page);

    await expect(page.locator('[data-reporte-error]')).toHaveText('El archivo supera el máximo de 32 MB.');
  });
});

test.describe('S7: exclusiones', () => {
  test('se filtran por motivo y se paginan de a 50', async ({ page }) => {
    const api = apiMowaMes();
    api.exclusiones.set(1, exclusionesSinteticas(120));
    await abrir(page, api);

    const filas = page.locator('.mm-exclusiones__tabla tbody tr');
    await expect(page.locator('[data-exclusiones-cuenta]')).toHaveText('120 exclusiones');
    await expect(filas).toHaveCount(50);

    const paginador = page.locator('[data-exclusiones-pager]');
    await paginador.getByRole('button', { name: 'Siguientes' }).click();
    await expect(paginador.locator('[data-rango]')).toHaveText('51–100 de 120');

    await page.getByLabel('Motivo', { exact: true }).selectOption('telefono_invalido');

    await expect(page.locator('[data-exclusiones-cuenta]')).toHaveText('20 exclusiones');
    await expect(filas).toHaveCount(20);
    await expect(filas.first()).toContainText('Teléfono inválido');
    const ultimo = pedidosA(api, 'GET', '/mowa-mes/campanas/1/exclusiones').at(-1)!;
    expect(parametro(ultimo.ruta, 'codigo')).toBe('telefono_invalido');
    // Changing the filter starts again from the first page.
    expect(parametro(ultimo.ruta, 'desplazamiento')).toBe('0');
  });
});

test.describe('idioma y conexión', () => {
  test('en inglés rotula enviados aparte de lo que coincide por id', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    const api = apiMowaMes();
    api.conciliaciones.set(1, conciliacionSintetica(1));
    await montarApiMowaMes(page, api);
    await page.goto(RUTA);

    await expect(page.getByRole('heading', { name: 'MOWA MES follow-up', level: 1 })).toBeVisible();
    await expect(page.locator('.mm-conciliacion__tabla').getByRole('columnheader', { name: 'Sent', exact: true })).toBeVisible();
    await expect(
      page.locator('.mm-ids__tabla').getByRole('columnheader', { name: 'Match the campaign (any status)' }),
    ).toBeVisible();
  });

  test('sin conexión con la API muestra el aviso en vez de paneles vacíos', async ({ page }) => {
    const api = apiMowaMes();
    api.sinRed = true;
    await montarApiMowaMes(page, api);
    await page.goto(RUTA);

    await expect(page.getByRole('heading', { name: 'Sin conexión con la API' })).toBeVisible();
    await expect(page.locator('[data-contenido]')).toBeHidden();
  });
});

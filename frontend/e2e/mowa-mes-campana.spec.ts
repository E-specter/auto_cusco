/**
 * MOWA MES campaign, end to end against an intercepted API (scenarios P1 to
 * P9 agreed with dev_backend in T-MM-B7).
 *
 * This is the first MOWA MES screen that also mounts the shared selection
 * picker, so it needs the general `/cartera`, `/cargas` and `/selecciones`
 * routes alongside the module's own. Playwright resolves overlapping
 * `page.route` handlers most-recently-registered first, so `montarSeleccion`
 * below is registered AFTER `montarApiMowaMes` and answers only the handful
 * of routes the compact selector calls, falling back to the module's mock
 * for everything else — neither fake file is modified.
 *
 * Every value is synthetic: phones in 900000xxx, promissory notes numeric,
 * MES ids in 99xxxxxxx.
 */
import { expect, test, type Page, type Route } from '@playwright/test';

import type { Campos, SeleccionGuardada, Version } from '../src/lib/api';
import type { CreacionCampanaEntrada, PeticionCampanaEntrada } from '../src/lib/api-mowa-mes';
import { camposSinteticos, seleccionGuardada, version } from './api-falsa';
import {
  apiMowaMes,
  campanaDesdeEntrada,
  montarApiMowaMes,
  previsualizacionCampanaSintetica,
  type ApiFalsaMowaMes,
} from './api-falsa-mowa-mes';

const RUTA = '/mowa-mes/campana';

test.use({ timezoneId: 'America/Lima' });

interface SeleccionFalsa {
  versiones: Version[];
  campos: Campos;
  selecciones: SeleccionGuardada[];
}

function seleccionFalsa(parcial: Partial<SeleccionFalsa> = {}): SeleccionFalsa {
  return {
    versiones: [version({ fecha_corte: '2026-09-13', vigente: true })],
    campos: camposSinteticos(),
    selecciones: [seleccionGuardada({ id: 1, nombre: 'Preventiva top 1000', cantidad: 1000 })],
    ...parcial,
  };
}

const json = (route: Route, estado: number, cuerpo: unknown) =>
  route.fulfill({ status: estado, contentType: 'application/json', body: JSON.stringify(cuerpo) });

/** A minimal, fully-typed request body, for building a preview or campaign fixture. */
function entradaMinima(cantidad = 1000): PeticionCampanaEntrada {
  return {
    fecha_corte: '2026-09-13',
    filtros: [],
    cantidad,
    seleccion_id: 1,
    tipo_carga: 'masiva',
    salida: 'numero_largo',
    herramientas: { keyword: false, respuesta_automatica: false, blacklist_indecopi: false, speech_optimizado: false },
    programacion: 'hora_determinada',
    envios: ['2026-09-14T09:00:00-05:00'],
  };
}

const cifra = (page: Page, host: string, etiqueta: string) =>
  page.locator(host).locator('.stat', { hasText: etiqueta }).locator('.stat__value');

/** The compact selector's own calls, layered over the module's mock. */
async function montarSeleccion(page: Page, sel: SeleccionFalsa): Promise<void> {
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const ruta = url.pathname.replace(/^\/api/, '');
    const metodo = route.request().method();

    if (ruta === '/cargas' && metodo === 'GET') return json(route, 200, sel.versiones);
    if (ruta === '/cartera/campos') return json(route, 200, sel.campos);
    if (ruta === '/selecciones' && metodo === 'GET') return json(route, 200, sel.selecciones);

    return route.fallback();
  });
}

async function abrir(page: Page, api: ApiFalsaMowaMes, sel: SeleccionFalsa = seleccionFalsa()): Promise<void> {
  await montarApiMowaMes(page, api);
  await montarSeleccion(page, sel);
  await page.goto(RUTA);
  await expect(page.getByRole('heading', { name: 'Campaña de MOWA MES', level: 1 })).toBeVisible();
}

/** Load the one saved selection the fixture seeds, so the form appears. */
async function elegirSeleccionGuardada(page: Page): Promise<void> {
  await page.getByLabel('Selección guardada').selectOption({ label: 'Preventiva top 1000' });
}

test.describe('P9: base de la selección', () => {
  test('sin selección guardada con cantidad, no deja previsualizar', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api, seleccionFalsa({ selecciones: [] }));

    await expect(
      page.getByText('Elige una selección guardada con una cantidad definida.', { exact: false }),
    ).toBeVisible();
    await expect(page.locator('[data-formulario]')).toBeHidden();
    expect(api.pedidos.filter((p) => p.ruta.startsWith('/mowa-mes/campanas/previsualizacion'))).toEqual([]);
  });

  test('una selección que no aplica no deja previsualizar', async ({ page }) => {
    const noAplica = seleccionGuardada({
      id: 2,
      nombre: 'Selección rota',
      cantidad: 500,
      filtros: ['campo_retirado:igual:x'],
      aplicable: false,
      problemas: [{ parte: 'filtro', expresion: 'campo_retirado:igual:x', detalle: 'El campo no existe' }],
    });
    const api = apiMowaMes();
    await abrir(page, api, seleccionFalsa({ selecciones: [noAplica] }));

    // A saved selection that stopped applying loads its "no aplica" suffix too.
    await page.getByLabel('Selección guardada').selectOption({ label: 'Selección rota · no aplica' });

    await expect(
      page.getByText('La selección elegida tiene partes que ya no aplican.', { exact: false }),
    ).toBeVisible();
    await expect(page.locator('[data-formulario]')).toBeHidden();
    expect(api.pedidos.filter((p) => p.ruta.startsWith('/mowa-mes/campanas/previsualizacion'))).toEqual([]);
  });

  test('elegir una selección válida arma la base y dispara la previsualización', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);

    await elegirSeleccionGuardada(page);

    await expect(page.locator('[data-formulario]')).toBeVisible();
    await expect(page.locator('[data-panel-previsualizacion]')).toBeVisible();
    const [pedido] = await esperarPrevisualizacion(api);
    expect(pedido.cuerpo).toMatchObject({
      fecha_corte: '2026-09-13',
      cantidad: 1000,
      seleccion_id: 1,
    });
  });
});

async function esperarPrevisualizacion(api: ApiFalsaMowaMes): Promise<Array<{ cuerpo: unknown }>> {
  await expect.poll(() => api.pedidos.some((p) => p.ruta === '/mowa-mes/campanas/previsualizacion')).toBe(true);
  return api.pedidos.filter((p) => p.ruta === '/mowa-mes/campanas/previsualizacion');
}

test.describe('P1: previsualización válida', () => {
  test('muestra cifras, la muestra con la supervisión primero, exclusiones traducidas y advertencias por código', async ({
    page,
  }) => {
    const api = apiMowaMes();
    api.respuestas.previsualizarCampana = [
      {
        estado: 200,
        cuerpo: previsualizacionCampanaSintetica(
          entradaMinima(),
          {
            productos_cargados: 980,
            supervision_cargados: 2,
            total_cargados: 982,
            muestra: [
              { numero: '900000101', mensaje: 'Mensaje sintetico de supervision', dni: '00000001', supervision: true, pagare: null, segmento: null, largo: 40, advertencias: [] },
              { numero: '900000201', mensaje: 'Mensaje sintetico de producto', dni: '46830218', supervision: false, pagare: '000000000000000900', segmento: '9_a_30', largo: 140, advertencias: ['documento_no_estandar'] },
            ],
            exclusiones: {
              total: 7,
              limite: 100,
              desplazamiento: 0,
              exclusiones: [{ pagare: '000000000000000901', codigo: 'telefono_invalido' }],
            },
            archivos_previstos_por_filas: [{ numero: 1, filas: 982, supervision: 2 }],
          },
        ),
      },
    ];
    await abrir(page, api);
    await elegirSeleccionGuardada(page);

    await expect(cifra(page, '[data-cifras]', 'Total cargados')).toHaveText('982');
    const filas = page.locator('.mm-muestra__tabla tbody tr');
    await expect(filas.first()).toContainText('Supervisión');
    // The code is data, shown in mono with the full sentence as a hover title —
    // same convention as the ingestion issues table, not a translated pill.
    await expect(filas.nth(1)).toContainText('documento_no_estandar');
    await expect(filas.nth(1).locator('[title]')).toHaveAttribute(
      'title',
      'El documento no es un DNI ni un RUC: se carga igual, pero conviene revisarlo.',
    );

    await expect(page.getByRole('cell', { name: '000000000000000901' })).toBeVisible();
    await expect(page.getByText('Mostrando las primeras 1 de 7.')).toBeVisible();
    await expect(page.locator('.mm-exclusiones__tabla .tag')).toHaveText('Teléfono inválido');

    await expect(page.getByText('Estimación solo por filas', { exact: false })).toBeVisible();
    await expect(page.locator('.mm-archivos-previstos li')).toContainText('estimado');
  });
});

test.describe('P2: previsualización con errores', () => {
  test('sin_supervisores, falta_whatsapp y sin_productos_cargables se muestran traducidos y Crear queda deshabilitado', async ({
    page,
  }) => {
    const api = apiMowaMes();
    api.respuestas.previsualizarCampana = [
      {
        estado: 200,
        cuerpo: previsualizacionCampanaSintetica(entradaMinima(), {
          puede_crear: false,
          errores: [
            { codigo: 'sin_supervisores', tipo: 'error', detalle: 'La campana no tiene supervisores' },
            { codigo: 'falta_whatsapp', tipo: 'error', detalle: 'Faltan numeros de WhatsApp' },
            { codigo: 'sin_productos_cargables', tipo: 'error', detalle: 'Ningun producto quedo cargable' },
          ],
        }),
      },
    ];
    await abrir(page, api);
    await elegirSeleccionGuardada(page);

    const resumen = page.locator('[data-resumen]');
    await expect(resumen).toContainText('supervisor');
    await expect(resumen).toContainText('WhatsApp');
    await expect(resumen).toContainText('Ningún producto quedó dentro de la carga');
    await expect(page.getByRole('button', { name: 'Crear campaña' })).toBeDisabled();
  });
});

test.describe('P3: límite mensual excedido', () => {
  test('advierte, pide confirmación con "No crear" preseleccionado, un 409 sin confirmar y 201 confirmando', async ({
    page,
  }) => {
    const api = apiMowaMes();
    const previaExcedida = previsualizacionCampanaSintetica(entradaMinima(), {
      limite: { mes: '2026-09', limite: 2_500_000, cargados_mes: 2_490_000, esta_campana: 982, total: 2_490_982, disponible: 9018, excedido: true },
    });
    api.respuestas.previsualizarCampana = [{ estado: 200, cuerpo: previaExcedida }];
    api.respuestas.crearCampana = [
      { estado: 409, cuerpo: { detail: 'La campana supera el limite mensual; confirma para continuar' } },
    ];
    await abrir(page, api);
    await elegirSeleccionGuardada(page);

    await expect(page.getByText('La campaña superaría el límite mensual', { exact: false }).first()).toBeVisible();

    await page.getByRole('button', { name: 'Crear campaña' }).click();

    const dialogo = page.getByRole('dialog', { name: 'La campaña superaría el límite mensual' });
    await expect(dialogo).toBeVisible();
    await expect(dialogo.getByText('La campana supera el limite mensual; confirma para continuar')).toBeVisible();
    await expect(dialogo.getByRole('button', { name: 'No crear' })).toBeFocused();

    api.respuestas.crearCampana = [{ estado: 201, cuerpo: campanaDesdeEntrada({ ...bodyFrom(previaExcedida), speech_huella: previaExcedida.speech.huella, confirmar_limite: true }, 5) }];
    await dialogo.getByRole('button', { name: 'Crear de todas formas' }).click();

    await expect(page.getByRole('heading', { name: 'Campaña 5 creada' })).toBeVisible();
    const envios = api.pedidos.filter((p) => p.ruta === '/mowa-mes/campanas' && p.metodo === 'POST');
    expect(envios).toHaveLength(2);
    expect((envios[0].cuerpo as Record<string, unknown>).confirmar_limite).toBe(false);
    expect((envios[1].cuerpo as Record<string, unknown>).confirmar_limite).toBe(true);
  });
});

/** A minimal PeticionCampanaEntrada-shaped stand-in, for building a matching Campana. */
function bodyFrom(previa: ReturnType<typeof previsualizacionCampanaSintetica>): CreacionCampanaEntrada {
  return {
    fecha_corte: '2026-09-13',
    filtros: [],
    orden: null,
    cantidad: previa.solicitados,
    seleccion_id: 1,
    tipo_carga: 'masiva',
    descripcion: previa.descripcion,
    salida: 'numero_largo',
    herramientas: { keyword: false, respuesta_automatica: false, blacklist_indecopi: false, speech_optimizado: false },
    programacion: 'hora_determinada',
    envios: ['2026-09-14T09:00:00-05:00'],
    speech_id: null,
    whatsapp: null,
    supervisores: null,
    speech_huella: previa.speech.huella,
    confirmar_limite: false,
  };
}

test.describe('P4: speech cambiado', () => {
  test('envía speech.huella como speech_huella; un 409 tras confirmar el límite bloquea Crear hasta previsualizar de nuevo', async ({
    page,
  }) => {
    const api = apiMowaMes();
    const previa = previsualizacionCampanaSintetica(entradaMinima(), {
      speech: { id: 1, nombre: 'Speech original', huella: 'b'.repeat(64) },
      limite: { mes: '2026-09', limite: 2_500_000, cargados_mes: 2_490_000, esta_campana: 982, total: 2_490_982, disponible: 9018, excedido: true },
    });
    api.respuestas.previsualizarCampana = [{ estado: 200, cuerpo: previa }];
    api.respuestas.crearCampana = [{ estado: 409, cuerpo: { detail: 'La version del speech cambio' } }];
    await abrir(page, api);
    await elegirSeleccionGuardada(page);

    await page.getByRole('button', { name: 'Crear campaña' }).click();
    const dialogo = page.getByRole('dialog', { name: 'La campaña superaría el límite mensual' });
    await dialogo.getByRole('button', { name: 'Crear de todas formas' }).click();

    const [pedido] = api.pedidos.filter((p) => p.ruta === '/mowa-mes/campanas' && p.metodo === 'POST');
    expect((pedido.cuerpo as Record<string, unknown>).speech_huella).toBe('b'.repeat(64));

    await expect(page.getByText('Vuelve a previsualizar antes de crearla', { exact: false })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Crear campaña' })).toBeDisabled();
    await expect(page.getByRole('heading', { name: /creada$/ })).toHaveCount(0);

    // A fresh preview clears the block (P4's "hasta volver a previsualizar").
    api.respuestas.previsualizarCampana = [{ estado: 200, cuerpo: previa }];
    await page.getByLabel('WhatsApp de la campaña').fill('900000555');
    await expect(page.getByRole('button', { name: 'Crear campaña' })).toBeEnabled();
  });

  test('con el límite sin exceder, un 409 en el primer intento es huella directamente, sin el diálogo del límite (B7)', async ({
    page,
  }) => {
    const api = apiMowaMes();
    const previa = previsualizacionCampanaSintetica(entradaMinima(), {
      speech: { id: 1, nombre: 'Speech original', huella: 'c'.repeat(64) },
      // The huella check runs before the limit check server-side, so a 409 on
      // the very first (unconfirmed) attempt can happen with the limit intact.
      limite: { mes: '2026-09', limite: 2_500_000, cargados_mes: 100, esta_campana: 982, total: 1082, disponible: 2_498_918, excedido: false },
    });
    api.respuestas.previsualizarCampana = [{ estado: 200, cuerpo: previa }];
    api.respuestas.crearCampana = [{ estado: 409, cuerpo: { detail: 'La version del speech cambio' } }];
    await abrir(page, api);
    await elegirSeleccionGuardada(page);

    await page.getByRole('button', { name: 'Crear campaña' }).click();

    await expect(page.getByRole('dialog', { name: 'La campaña superaría el límite mensual' })).toBeHidden();
    await expect(page.getByText('Vuelve a previsualizar antes de crearla', { exact: false })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Crear campaña' })).toBeDisabled();
    expect(
      api.pedidos.filter((p) => p.ruta === '/mowa-mes/campanas' && p.metodo === 'POST'),
    ).toHaveLength(1);
  });
});

test.describe('P5: opciones deshabilitadas', () => {
  test('no se pueden elegir, y la petición siempre va con masiva y numero_largo', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);
    await elegirSeleccionGuardada(page);

    await expect(page.getByLabel('Personalizada (todavía no disponible)')).toBeDisabled();
    await expect(page.getByLabel('Número corto (todavía no disponible)')).toBeDisabled();
    await expect(page.getByLabel('Número corto flash (todavía no disponible)')).toBeDisabled();
    await expect(page.getByLabel('Respuesta automática (todavía no disponible)')).toBeDisabled();

    const [pedido] = await esperarPrevisualizacion(api);
    expect(pedido.cuerpo).toMatchObject({ tipo_carga: 'masiva', salida: 'numero_largo' });
    expect((pedido.cuerpo as Record<string, unknown>).herramientas).toMatchObject({ respuesta_automatica: false });
  });
});

test.describe('P6: programación', () => {
  test('la fecha sugerida sale del siguiente día gestionable', async ({ page }) => {
    const api = apiMowaMes();
    api.siguienteDia = '2026-09-21';
    await abrir(page, api);
    await elegirSeleccionGuardada(page);

    await expect(page.locator('#mm-fecha-unica')).toHaveValue('2026-09-21T09:00');
  });

  test('enviar ahora no manda fechas de envío', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);
    await elegirSeleccionGuardada(page);
    await esperarPrevisualizacion(api);

    await page.getByLabel('Enviar ahora').check();

    await expect(page.locator('#mm-fecha-unica')).toBeHidden();
    await expect
      .poll(() => api.pedidos.filter((p) => p.ruta === '/mowa-mes/campanas/previsualizacion').length)
      .toBeGreaterThan(1);
    const ultimo = api.pedidos.filter((p) => p.ruta === '/mowa-mes/campanas/previsualizacion').at(-1)!;
    expect(ultimo.cuerpo).toMatchObject({ programacion: 'enviar_ahora', envios: [] });
  });
});

test.describe('P7: creación y descarga', () => {
  test('crea (201) y descarga cada archivo con el nombre y el resumen del servidor', async ({ page }) => {
    const api = apiMowaMes();
    const previa = previsualizacionCampanaSintetica(entradaMinima(), {
      archivos_previstos_por_filas: [{ numero: 1, filas: 982, supervision: 2 }],
    });
    api.respuestas.previsualizarCampana = [{ estado: 200, cuerpo: previa }];
    const creada = campanaDesdeEntrada(bodyFrom(previa), 9, { archivos: [{ numero: 1, filas: 982, supervision: 2, bytes: 41_500 }] });
    // A scripted response for POST /mowa-mes/campanas answers the create call
    // directly and skips the fake's own bookkeeping, so the download route
    // (which looks the campaign up by id) needs it added here too.
    api.respuestas.crearCampana = [{ estado: 201, cuerpo: creada }];
    api.campanas = [creada, ...api.campanas];
    await abrir(page, api);
    await elegirSeleccionGuardada(page);

    await page.getByRole('button', { name: 'Crear campaña' }).click();
    await expect(page.getByRole('heading', { name: 'Campaña 9 creada' })).toBeVisible();

    const descarga = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Descargar el archivo 1' }).click();
    expect((await descarga).suggestedFilename()).toBe('mowa_mes_campana_9_1_de_1.xlsx');
    await expect(page.getByText('Archivo 1 de 1 descargado: 982 filas, 2 de supervisión.')).toBeVisible();
  });
});

test.describe('P8: sin versión vigente', () => {
  test('un 404 en la previsualización se muestra en el panel', async ({ page }) => {
    const api = apiMowaMes();
    api.respuestas.previsualizarCampana = [
      { estado: 404, cuerpo: { detail: 'La fecha 2026-09-13 no tiene una version vigente de sabana' } },
    ];
    await abrir(page, api);
    await elegirSeleccionGuardada(page);

    await expect(page.getByText('No se pudo previsualizar')).toBeVisible();
    await expect(page.getByText('La fecha 2026-09-13 no tiene una version vigente de sabana')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Crear campaña' })).toBeDisabled();
  });
});

test.describe('idioma y conexión', () => {
  test('en inglés traduce lo que arma el script', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    const api = apiMowaMes();
    await montarApiMowaMes(page, api);
    await montarSeleccion(page, seleccionFalsa());
    await page.goto(RUTA);

    await expect(page.getByRole('heading', { name: 'MOWA MES campaign', level: 1 })).toBeVisible();
    await page.getByLabel('Saved selection').selectOption({ label: 'Preventiva top 1000' });
    await expect(page.getByText('Available in the selection')).toBeVisible();
  });

  test('sin conexión con la API muestra el aviso en vez de paneles vacíos', async ({ page }) => {
    const api = apiMowaMes();
    api.sinRed = true;
    await montarApiMowaMes(page, api);
    await montarSeleccion(page, seleccionFalsa());
    await page.goto(RUTA);

    await expect(page.getByRole('heading', { name: 'Sin conexión con la API' })).toBeVisible();
    await expect(page.locator('[data-contenido]')).toBeHidden();
  });
});

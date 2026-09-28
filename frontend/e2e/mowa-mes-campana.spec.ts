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
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page, type Route } from '@playwright/test';

import type { Campos, SeleccionGuardada, Version } from '../src/lib/api';
import type { CodigoMowaMes, CreacionCampanaEntrada, PeticionCampanaEntrada } from '../src/lib/api-mowa-mes';
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
    await expect(page.getByText('Se muestran las primeras 1 de 7.', { exact: false })).toBeVisible();
    await expect(page.locator('[data-exclusiones-total]')).toHaveText('7 en total');
    // One row per table: nothing to page.
    await expect(page.locator('[data-muestra-pager]')).toBeHidden();
    await expect(page.locator('[data-exclusiones-pager]')).toBeHidden();
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
      {
        estado: 409,
        cuerpo: { detail: 'La campana supera el limite mensual; confirma para continuar', codigo: 'limite_excedido' },
      },
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
  test('envía speech.huella como speech_huella; un 409 de huella bloquea Crear hasta previsualizar de nuevo, aunque el límite esté excedido', async ({
    page,
  }) => {
    const api = apiMowaMes();
    const previa = previsualizacionCampanaSintetica(entradaMinima(), {
      speech: { id: 1, nombre: 'Speech original', huella: 'b'.repeat(64) },
      // Excedido a propósito: el diálogo del límite ya no depende de esta
      // previsualización, solo del `codigo` que devuelva el 409.
      limite: { mes: '2026-09', limite: 2_500_000, cargados_mes: 2_490_000, esta_campana: 982, total: 2_490_982, disponible: 9018, excedido: true },
    });
    api.respuestas.previsualizarCampana = [{ estado: 200, cuerpo: previa }];
    api.respuestas.crearCampana = [
      { estado: 409, cuerpo: { detail: 'La version del speech cambio', codigo: 'huella_cambiada' } },
    ];
    await abrir(page, api);
    await elegirSeleccionGuardada(page);

    await page.getByRole('button', { name: 'Crear campaña' }).click();

    const [pedido] = api.pedidos.filter((p) => p.ruta === '/mowa-mes/campanas' && p.metodo === 'POST');
    expect((pedido.cuerpo as Record<string, unknown>).speech_huella).toBe('b'.repeat(64));

    await expect(page.getByRole('dialog', { name: 'La campaña superaría el límite mensual' })).toBeHidden();
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
      // The client no longer needs to know that order: `codigo` alone decides.
      limite: { mes: '2026-09', limite: 2_500_000, cargados_mes: 100, esta_campana: 982, total: 1082, disponible: 2_498_918, excedido: false },
    });
    api.respuestas.previsualizarCampana = [{ estado: 200, cuerpo: previa }];
    api.respuestas.crearCampana = [
      { estado: 409, cuerpo: { detail: 'La version del speech cambio', codigo: 'huella_cambiada' } },
    ];
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

  test('un 409 sin código conocido se trata como huella: bloquea Crear y pide previsualizar', async ({ page }) => {
    const api = apiMowaMes();
    const previa = previsualizacionCampanaSintetica(entradaMinima(), {
      speech: { id: 1, nombre: 'Speech original', huella: 'd'.repeat(64) },
      limite: { mes: '2026-09', limite: 2_500_000, cargados_mes: 2_490_000, esta_campana: 982, total: 2_490_982, disponible: 9018, excedido: true },
    });
    api.respuestas.previsualizarCampana = [{ estado: 200, cuerpo: previa }];
    // A code this client does not recognize (future backend addition, typo,
    // whatever): the safe default is the huella block, never the limit dialog.
    api.respuestas.crearCampana = [
      { estado: 409, cuerpo: { detail: 'Motivo nuevo que el cliente no conoce', codigo: 'motivo_desconocido' } },
    ];
    await abrir(page, api);
    await elegirSeleccionGuardada(page);

    await page.getByRole('button', { name: 'Crear campaña' }).click();

    await expect(page.getByRole('dialog', { name: 'La campaña superaría el límite mensual' })).toBeHidden();
    await expect(page.getByText('Vuelve a previsualizar antes de crearla', { exact: false })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Crear campaña' })).toBeDisabled();
    await expect(page.getByRole('heading', { name: /creada$/ })).toHaveCount(0);
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
    const creada = campanaDesdeEntrada(bodyFrom(previa), 9, { archivos: [{ numero: 1, filas: 982, supervision: 2, bytes: 41_500, nombre: 'mowa_mes_campana_9_1_de_1.xlsx' }] });
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

/** Synthetic rows: phones in 900000xxx, numeric promissory notes and documents. */
function filasDeMuestra(cantidad: number) {
  return Array.from({ length: cantidad }, (_, i) => ({
    numero: `900000${String(i + 1).padStart(3, '0')}`,
    mensaje: `Mensaje sintetico ${i + 1}`,
    dni: `00${String(100000 + i)}`,
    supervision: false,
    pagare: `${'0'.repeat(14)}${String(1000 + i)}`,
    segmento: '9_a_30' as const,
    largo: 60,
    advertencias: [] as CodigoMowaMes[],
  }));
}

function exclusionesSinteticas(total: number, enLista = Math.min(total, 100)) {
  return {
    total,
    limite: 100,
    desplazamiento: 0,
    exclusiones: Array.from({ length: enLista }, (_, i) => ({
      pagare: `${'0'.repeat(14)}${String(2000 + i)}`,
      codigo: 'telefono_invalido' as const,
    })),
  };
}

function previaPaginada(muestra: number, exclusionesTotal: number) {
  return previsualizacionCampanaSintetica(entradaMinima(), {
    muestra: filasDeMuestra(muestra),
    exclusiones: exclusionesSinteticas(exclusionesTotal),
  });
}

const pedidosDePrevisualizacion = (api: ApiFalsaMowaMes) =>
  api.pedidos.filter((p) => p.ruta === '/mowa-mes/campanas/previsualizacion' && p.metodo === 'POST');

test.describe('F6-A: paginación de la previsualización (RF-MM-26)', () => {
  test('la muestra de 20 se pagina de a 10 sin volver a pedir la previsualización', async ({ page }) => {
    const api = apiMowaMes();
    api.respuestas.previsualizarCampana = [{ estado: 200, cuerpo: previaPaginada(20, 0) }];
    await abrir(page, api);
    await elegirSeleccionGuardada(page);

    const numeros = page.locator('.mm-muestra__tabla tbody tr td:first-child');
    const paginador = page.getByRole('group', { name: 'Paginación de la muestra' });
    const rango = paginador.locator('[data-rango]');

    await expect(numeros).toHaveCount(10);
    await expect(numeros.first()).toHaveText('900000001');
    await expect(numeros.last()).toHaveText('900000010');
    await expect(rango).toHaveText('1–10 de 20');
    await expect(paginador.getByRole('button', { name: 'Anteriores' })).toBeDisabled();

    await paginador.getByRole('button', { name: 'Siguientes' }).click();

    await expect(numeros.first()).toHaveText('900000011');
    await expect(numeros.last()).toHaveText('900000020');
    await expect(rango).toHaveText('11–20 de 20');
    await expect(paginador.getByRole('button', { name: 'Siguientes' })).toBeDisabled();
    // The button that held the focus just went away: the focus follows to the other one.
    await expect(paginador.getByRole('button', { name: 'Anteriores' })).toBeFocused();

    await paginador.getByRole('button', { name: 'Anteriores' }).click();
    await expect(numeros.first()).toHaveText('900000001');
    expect(pedidosDePrevisualizacion(api)).toHaveLength(1);
  });

  test('las 100 exclusiones se pagan de a 10 y el aviso dice que hay más, con el total real', async ({ page }) => {
    const api = apiMowaMes();
    api.respuestas.previsualizarCampana = [{ estado: 200, cuerpo: previaPaginada(0, 250) }];
    await abrir(page, api);
    await elegirSeleccionGuardada(page);

    await expect(page.locator('[data-exclusiones-total]')).toHaveText('250 en total');
    await expect(page.locator('[data-exclusiones-truncadas]')).toHaveText(
      'Se muestran las primeras 100 de 250. La lista completa estará en el seguimiento de la campaña después de crearla.',
    );

    const paginador = page.getByRole('group', { name: 'Paginación de las exclusiones' });
    const siguiente = paginador.getByRole('button', { name: 'Siguientes' });
    await expect(paginador.locator('[data-rango]')).toHaveText('1–10 de 100');
    await siguiente.click();
    // Still enabled: the focus stays where the analyst left it.
    await expect(siguiente).toBeFocused();
    for (let i = 0; i < 8; i++) await siguiente.click();

    await expect(paginador.locator('[data-rango]')).toHaveText('91–100 de 100');
    await expect(siguiente).toBeDisabled();
    await expect(page.locator('.mm-exclusiones__tabla tbody tr')).toHaveCount(10);
    await expect(page.getByRole('cell', { name: `${'0'.repeat(14)}2099` })).toBeVisible();
  });

  test('con 100 o menos exclusiones el encabezado da el total y no hay aviso', async ({ page }) => {
    const api = apiMowaMes();
    api.respuestas.previsualizarCampana = [{ estado: 200, cuerpo: previaPaginada(0, 100) }];
    await abrir(page, api);
    await elegirSeleccionGuardada(page);

    await expect(page.locator('[data-exclusiones-total]')).toHaveText('100 en total');
    await expect(page.locator('[data-exclusiones-truncadas]')).toBeHidden();
    await expect(page.locator('[data-exclusiones-pager]')).toBeVisible();
  });

  test('sin exclusiones el encabezado dice 0 y no hay paginador', async ({ page }) => {
    const api = apiMowaMes();
    api.respuestas.previsualizarCampana = [{ estado: 200, cuerpo: previaPaginada(0, 0) }];
    await abrir(page, api);
    await elegirSeleccionGuardada(page);

    await expect(page.locator('[data-exclusiones-total]')).toHaveText('0 en total');
    await expect(page.getByText('Ningún producto quedó excluido.')).toBeVisible();
    await expect(page.locator('[data-exclusiones-pager]')).toBeHidden();
  });

  test('el paginador solo aparece con más de 10 filas', async ({ page }) => {
    const api = apiMowaMes();
    api.respuestas.previsualizarCampana = [{ estado: 200, cuerpo: previaPaginada(10, 10) }];
    await abrir(page, api);
    await elegirSeleccionGuardada(page);

    await expect(page.locator('.mm-muestra__tabla tbody tr')).toHaveCount(10);
    await expect(page.locator('[data-muestra-pager]')).toBeHidden();
    await expect(page.locator('[data-exclusiones-pager]')).toBeHidden();

    api.respuestas.previsualizarCampana = [{ estado: 200, cuerpo: previaPaginada(11, 11) }];
    await page.getByLabel('WhatsApp de la campaña').fill('900000555');

    await expect(page.locator('[data-muestra-pager] [data-rango]')).toHaveText('1–10 de 11');
    await expect(page.locator('[data-exclusiones-pager] [data-rango]')).toHaveText('1–10 de 11');
  });

  test('al recalcular, las dos tablas vuelven a la página 1 y el foco no se mueve del campo', async ({ page }) => {
    const api = apiMowaMes();
    api.respuestas.previsualizarCampana = [{ estado: 200, cuerpo: previaPaginada(20, 30) }];
    await abrir(page, api);
    await elegirSeleccionGuardada(page);

    const muestra = page.getByRole('group', { name: 'Paginación de la muestra' });
    const exclusiones = page.getByRole('group', { name: 'Paginación de las exclusiones' });
    await muestra.getByRole('button', { name: 'Siguientes' }).click();
    await exclusiones.getByRole('button', { name: 'Siguientes' }).click();
    await expect(muestra.locator('[data-rango]')).toHaveText('11–20 de 20');
    await expect(exclusiones.locator('[data-rango]')).toHaveText('11–20 de 30');

    api.respuestas.previsualizarCampana = [{ estado: 200, cuerpo: previaPaginada(20, 30) }];
    const whatsapp = page.getByLabel('WhatsApp de la campaña');
    await whatsapp.fill('900000555');

    await expect(muestra.locator('[data-rango]')).toHaveText('1–10 de 20');
    await expect(exclusiones.locator('[data-rango]')).toHaveText('1–10 de 30');
    await expect(page.locator('.mm-muestra__tabla tbody tr td:first-child').first()).toHaveText('900000001');
    await expect(whatsapp).toBeFocused();
    expect(pedidosDePrevisualizacion(api).length).toBeGreaterThanOrEqual(2);
  });

  test('en inglés traduce el total, el aviso y el paginador', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    const api = apiMowaMes();
    api.respuestas.previsualizarCampana = [{ estado: 200, cuerpo: previaPaginada(20, 250) }];
    await montarApiMowaMes(page, api);
    await montarSeleccion(page, seleccionFalsa());
    await page.goto(RUTA);
    await page.getByLabel('Saved selection').selectOption({ label: 'Preventiva top 1000' });

    await expect(page.locator('[data-exclusiones-total]')).toHaveText('250 in total');
    await expect(page.locator('[data-exclusiones-truncadas]')).toContainText('Showing the first 100 of 250.');
    await expect(page.getByRole('group', { name: 'Exclusions pagination' })).toBeVisible();
    await expect(page.locator('[data-muestra-pager] [data-rango]')).toHaveText('1–10 of 20');
    await expect(
      page.getByRole('group', { name: 'Sample pagination' }).getByRole('button', { name: 'Next' }),
    ).toBeEnabled();
  });
});

test.describe('F6-B: nombre de los archivos y costo estimado (RF-MM-24, RF-MM-25)', () => {
  const plantilla = (page: Page) => page.getByLabel('Nombre de los archivos');
  const nombre = (page: Page) => page.locator('[data-nombre-primer-archivo]');
  const errorPlantilla = (page: Page) => page.locator('[data-plantilla-error]');

  test('la plantilla llega precargada desde la configuración, con las variables que manda la API', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);
    // The form only shows once a saved selection is loaded.
    await elegirSeleccionGuardada(page);

    await expect(plantilla(page)).toHaveValue('mowa_mes_campana_{campana}_{archivo}_de_{total}');
    // A labelled group that follows the field in the DOM, right after it.
    await expect(page.locator('#mm-plantilla + [data-plantilla-variables]')).toHaveCount(1);
    await expect(
      page.getByRole('group', { name: 'Variables de la plantilla' }).getByRole('button'),
    ).toHaveText(['{campana}', '{descripcion}', '{fecha_envio}', '{fecha_corte}', '{archivo}', '{total}', '{cantidad}']);
  });

  test('sin tocarla no viaja (usa la de la configuración); editada, viaja tal cual', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);
    await elegirSeleccionGuardada(page);
    await expect(page.locator('[data-resultado]')).toBeVisible();
    const previas = () => pedidosDePrevisualizacion(api);
    expect((previas().at(-1)?.cuerpo as Record<string, unknown>).plantilla_nombre_archivo).toBeNull();

    await plantilla(page).fill('carga_{fecha_corte}');
    await expect(nombre(page)).toHaveText('carga_2026-09-13.xlsx');
    expect((previas().at(-1)?.cuerpo as Record<string, unknown>).plantilla_nombre_archivo).toBe('carga_{fecha_corte}');

    // Back to exactly the configured one: it stops travelling.
    await plantilla(page).fill('mowa_mes_campana_{campana}_{archivo}_de_{total}');
    await expect(nombre(page)).toHaveText('mowa_mes_campana_[campana]_1_de_1.xlsx');
    expect((previas().at(-1)?.cuerpo as Record<string, unknown>).plantilla_nombre_archivo).toBeNull();
  });

  test('el nombre del primer archivo es el de la API, con [campana] como marcador, y avisa cuando es estimado', async ({
    page,
  }) => {
    const api = apiMowaMes();
    await abrir(page, api);
    await elegirSeleccionGuardada(page);

    await expect(nombre(page)).toHaveText('mowa_mes_campana_[campana]_1_de_1.xlsx');
    await expect(page.getByText('Nombre del primer archivo:')).toBeVisible();
    // The default uses {archivo} and {total}: it depends on how the load is split.
    await expect(page.locator('[data-nombre-estimado]')).toBeVisible();
    await expect(page.locator('[data-nombre-estimado]')).toContainText('Estimado');

    // A template that does not depend on the split is not an estimate.
    await plantilla(page).fill('carga_{descripcion}');
    await expect(nombre(page)).toHaveText('carga_CajaCusco 9 _= dias atraso _= 30.xlsx');
    await expect(page.locator('[data-nombre-estimado]')).toBeHidden();
  });

  test('sin archivos previstos no hay nombre que mostrar', async ({ page }) => {
    const api = apiMowaMes();
    api.respuestas.previsualizarCampana = [
      {
        estado: 200,
        cuerpo: previsualizacionCampanaSintetica(entradaMinima(), {
          archivos_previstos_por_filas: [],
          nombre_primer_archivo: null,
          nombre_estimado: false,
          puede_crear: false,
        }),
      },
    ];
    await abrir(page, api);
    await elegirSeleccionGuardada(page);

    await expect(page.locator('[data-resultado]')).toBeVisible();
    await expect(page.locator('[data-nombre-archivo]')).toBeHidden();
    await expect(page.locator('[data-nombre-estimado]')).toBeHidden();
  });

  test('el costo estimado va en las cifras, ya calculado, con su hint de SMS por tarifa', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);
    await elegirSeleccionGuardada(page);

    const costo = page.locator('[data-cifras] .stat', { hasText: 'Costo estimado' });
    await expect(costo.locator('.stat__value')).toHaveText('S/ 19.64');
    await expect(costo).toContainText('982 SMS × S/ 0.02');
  });

  test('el monto llega como texto y se formatea sin pasar por un número', async ({ page }) => {
    const api = apiMowaMes();
    api.respuestas.previsualizarCampana = [
      {
        estado: 200,
        cuerpo: previsualizacionCampanaSintetica(entradaMinima(), {
          // More digits than a float keeps: it must come out exactly.
          costo_estimado: '12345678901234567.8900',
          tarifa_sms: '0.0215',
        }),
      },
    ];
    await abrir(page, api);
    await elegirSeleccionGuardada(page);

    const costo = page.locator('[data-cifras] .stat', { hasText: 'Costo estimado' });
    await expect(costo.locator('.stat__value')).toHaveText('S/ 12,345,678,901,234,567.89');
    await expect(costo).toContainText('S/ 0.0215');
  });

  test('una variable desconocida se marca con la lista de la API y no pide otra previsualización', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);
    await elegirSeleccionGuardada(page);
    await expect(page.locator('[data-resultado]')).toBeVisible();
    const antes = pedidosDePrevisualizacion(api).length;

    await plantilla(page).fill('carga_{banco}');

    await expect(errorPlantilla(page)).toHaveText('No es una variable de la plantilla: {banco}. Usa las de los botones.');
    await expect(plantilla(page)).toHaveAttribute('aria-invalid', 'true');
    await expect(page.locator('[data-resultado]')).toBeHidden();
    await page.waitForTimeout(700);
    expect(pedidosDePrevisualizacion(api)).toHaveLength(antes);
    await expect(page.getByRole('button', { name: 'Crear campaña' })).toBeDisabled();

    await plantilla(page).fill('carga_{campana}');
    await expect(errorPlantilla(page)).toHaveText('');
    await expect(page.locator('[data-resultado]')).toBeVisible();
  });

  test('un 400 de la API sobre la plantilla se muestra junto al campo, no en un diálogo', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);
    await elegirSeleccionGuardada(page);
    await expect(page.locator('[data-resultado]')).toBeVisible();
    api.respuestas.previsualizarCampana = [
      { estado: 400, cuerpo: { detail: 'La plantilla tiene una llave { sin cerrar', campo: 'plantilla_nombre_archivo' } },
    ];

    await plantilla(page).fill('carga_{campana');

    await expect(errorPlantilla(page)).toHaveText('La plantilla tiene una llave { sin cerrar');
    await expect(plantilla(page)).toHaveAttribute('aria-invalid', 'true');
    await expect(page.getByRole('dialog')).toBeHidden();
  });

  test('un 400 de la previsualización sin campo (null) va al aviso general, aunque el texto hable de la plantilla', async ({
    page,
  }) => {
    const api = apiMowaMes();
    await abrir(page, api);
    await elegirSeleccionGuardada(page);
    await expect(page.locator('[data-resultado]')).toBeVisible();
    api.respuestas.previsualizarCampana = [
      { estado: 400, cuerpo: { detail: 'Un motivo nuevo que nombra la plantilla sin serlo', campo: null } },
    ];

    await page.getByLabel('WhatsApp de la campaña').fill('900000555');

    // The general notice (the error dialog), not the field: the words do not place the error.
    const dialogo = page.getByRole('dialog');
    await expect(dialogo).toBeVisible();
    await expect(dialogo).toContainText('Un motivo nuevo que nombra la plantilla sin serlo');
    await expect(errorPlantilla(page)).toHaveText('');
    await expect(plantilla(page)).not.toHaveAttribute('aria-invalid', 'true');
  });

  test('un 400 de la previsualización sin el campo en el cuerpo tampoco se ubica en la plantilla', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);
    await elegirSeleccionGuardada(page);
    await expect(page.locator('[data-resultado]')).toBeVisible();
    api.respuestas.previsualizarCampana = [{ estado: 400, cuerpo: { detail: 'La plantilla tiene una llave { sin cerrar' } }];

    await page.getByLabel('WhatsApp de la campaña').fill('900000555');

    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(errorPlantilla(page)).toHaveText('');
  });

  test('la previsualización rechaza una plantilla de más de 300 caracteres y lo dice junto al campo', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);
    await elegirSeleccionGuardada(page);
    await expect(page.locator('[data-resultado]')).toBeVisible();

    await plantilla(page).fill(`{campana}${'x'.repeat(300)}`);

    await expect(errorPlantilla(page)).toHaveText('La plantilla no puede pasar de 300 caracteres');
    await expect(page.getByRole('dialog')).toBeHidden();
  });

  test('un 400 al crear con el campo de la plantilla se muestra en el campo y lo enfoca', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);
    await elegirSeleccionGuardada(page);
    await expect(page.getByRole('button', { name: 'Crear campaña' })).toBeEnabled();
    api.respuestas.crearCampana = [
      { estado: 400, cuerpo: { detail: 'La plantilla no puede pasar de 300 caracteres', campo: 'plantilla_nombre_archivo' } },
    ];

    await page.getByRole('button', { name: 'Crear campaña' }).click();

    await expect(errorPlantilla(page)).toHaveText('La plantilla no puede pasar de 300 caracteres');
    await expect(plantilla(page)).toBeFocused();
    await expect(page.locator('[data-crear-error]')).toHaveText('');
  });

  test('un 400 al crear sin campo se muestra junto al botón, no en la plantilla', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);
    await elegirSeleccionGuardada(page);
    await expect(page.getByRole('button', { name: 'Crear campaña' })).toBeEnabled();
    api.respuestas.crearCampana = [{ estado: 400, cuerpo: { detail: 'La campaña no tiene supervisores', campo: null } }];

    await page.getByRole('button', { name: 'Crear campaña' }).click();

    await expect(page.locator('[data-crear-error]')).toHaveText('La campaña no tiene supervisores');
    await expect(errorPlantilla(page)).toHaveText('');
  });

  test('un botón inserta la variable en el cursor y la previsualización se vuelve a pedir', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);
    await elegirSeleccionGuardada(page);
    await expect(page.locator('[data-resultado]')).toBeVisible();

    await plantilla(page).fill('carga_.final');
    await plantilla(page).evaluate((el: HTMLInputElement) => el.setSelectionRange(6, 6));
    await page.getByRole('group', { name: 'Variables de la plantilla' }).getByRole('button', { name: '{fecha_envio}' }).click();

    await expect(plantilla(page)).toHaveValue('carga_{fecha_envio}.final');
    await expect(plantilla(page)).toBeFocused();
    await expect(nombre(page)).toHaveText('carga_2026-09-17.final.xlsx');
  });

  test('crear manda la plantilla editada y la campaña creada trae los nombres reales', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);
    await elegirSeleccionGuardada(page);
    await plantilla(page).fill('carga_{campana}');
    await expect(nombre(page)).toHaveText('carga_[campana].xlsx');

    await page.getByRole('button', { name: 'Crear campaña' }).click();

    await expect(page.getByRole('heading', { name: /creada$/ })).toBeVisible();
    const [envio] = api.pedidos.filter((p) => p.ruta === '/mowa-mes/campanas' && p.metodo === 'POST');
    expect((envio.cuerpo as Record<string, unknown>).plantilla_nombre_archivo).toBe('carga_{campana}');
    // The fake stores the real names the API would: {campana} became the id.
    expect(api.campanas[0].archivos[0].nombre).toBe('carga_2.xlsx');
  });

  test('en inglés traduce el rótulo, el hint y el aviso de estimado', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    const api = apiMowaMes();
    await montarApiMowaMes(page, api);
    await montarSeleccion(page, seleccionFalsa());
    await page.goto(RUTA);
    await page.getByLabel('Saved selection').selectOption({ label: 'Preventiva top 1000' });

    await expect(page.getByLabel('File names')).toHaveValue('mowa_mes_campana_{campana}_{archivo}_de_{total}');
    await expect(page.getByText('Name of the first file:')).toBeVisible();
    await expect(page.locator('[data-nombre-estimado]')).toContainText('Estimated');
    const costo = page.locator('[data-cifras] .stat', { hasText: 'Estimated cost' });
    await expect(costo).toContainText('982 SMS × S/ 0.02');
  });
});

test.describe('F6-B: las tablas de la previsualización se apilan en pantallas angostas (hallazgo de C3)', () => {
  /** A sample of 20 with long messages, the case that used to split letter by letter. */
  function previaConMensajesLargos() {
    return previsualizacionCampanaSintetica(entradaMinima(), {
      muestra: Array.from({ length: 20 }, (_, i) => ({
        numero: `900000${String(i + 1).padStart(3, '0')}`,
        mensaje: 'Mensaje sintetico de prueba con un largo parecido al real para ver como se parte en pantallas angostas',
        dni: `00${String(100000 + i)}`,
        supervision: i === 0,
        pagare: `${'0'.repeat(14)}${String(1000 + i)}`,
        segmento: '9_a_30' as const,
        largo: 118,
        advertencias: i % 3 === 0 ? (['documento_no_estandar'] as CodigoMowaMes[]) : ([] as CodigoMowaMes[]),
      })),
      exclusiones: exclusionesSinteticas30(),
    });
  }

  function exclusionesSinteticas30() {
    return {
      total: 30,
      limite: 100,
      desplazamiento: 0,
      exclusiones: Array.from({ length: 30 }, (_, i) => ({
        pagare: `${'0'.repeat(14)}${String(2000 + i)}`,
        codigo: 'telefono_invalido' as const,
      })),
    };
  }

  /** Rows of a sensible height: 194–219 px once stacked at 360 px, ~350 px when they were not. */
  const ALTO_MAXIMO_DE_FILA = 240;

  async function abrirAngosto(page: Page, ancho: number): Promise<ApiFalsaMowaMes> {
    await page.setViewportSize({ width: ancho, height: 900 });
    const api = apiMowaMes();
    api.respuestas.previsualizarCampana = [{ estado: 200, cuerpo: previaConMensajesLargos() }];
    await abrir(page, api);
    await elegirSeleccionGuardada(page);
    await expect(page.locator('.mm-muestra__tabla tbody tr').first()).toBeVisible();
    return api;
  }

  for (const ancho of [360, 640]) {
    test(`a ${ancho} px la muestra y las exclusiones no desbordan y sus filas no se estiran`, async ({ page }) => {
      await abrirAngosto(page, ancho);

      for (const tabla of ['.mm-muestra__tabla', '.mm-exclusiones__tabla']) {
        const medida = await page.locator(tabla).evaluate((el) => {
          const contenedor = el.closest('.table-scroll') as HTMLElement;
          return { scroll: contenedor.scrollWidth, cliente: contenedor.clientWidth };
        });
        // No sideways scroll inside the table's own container...
        expect(medida.scroll, `${tabla} desborda a ${ancho}px`).toBeLessThanOrEqual(medida.cliente + 1);
      }
      // ...nor of the page.
      const pagina = await page.evaluate(() => ({
        scroll: document.documentElement.scrollWidth,
        cliente: document.documentElement.clientWidth,
      }));
      expect(pagina.scroll).toBeLessThanOrEqual(pagina.cliente);

      // Rows read as blocks: each cell names itself, and the message is not split letter by letter.
      const primera = page.locator('.mm-muestra__tabla tbody tr').nth(1);
      await expect(primera.locator('td').nth(4)).toHaveCSS('display', 'block');
      const alto = (await primera.boundingBox())!.height;
      expect(alto, `fila de la muestra a ${ancho}px: ${Math.round(alto)}px`).toBeLessThan(ALTO_MAXIMO_DE_FILA);
      // The message takes the block's width; the wide layout's 32ch cap must not follow it here.
      const mensaje = await primera.locator('td').nth(4).boundingBox();
      expect(mensaje!.width).toBeGreaterThan(ancho === 360 ? 150 : 350);
      const exclusion = (await page.locator('.mm-exclusiones__tabla tbody tr').first().boundingBox())!;
      expect(exclusion.height).toBeLessThan(ALTO_MAXIMO_DE_FILA);
    });
  }

  test('a 360 px cada celda se nombra sola y las que no tienen contenido no ocupan un bloque', async ({ page }) => {
    await abrirAngosto(page, 360);

    const fila = page.locator('.mm-muestra__tabla tbody tr').nth(1);
    const etiquetas = await fila.locator('td').evaluateAll((celdas) =>
      celdas.map((c) => (c as HTMLElement).dataset.etiqueta ?? ''),
    );
    expect(etiquetas).toEqual(['Número', 'DNI', 'Segmento', 'Largo', 'Mensaje', 'Advertencias']);
    // The second row has no warnings: its warnings cell takes no room.
    await expect(fila.locator('td').nth(5)).toHaveCSS('display', 'none');
    // The first row does have one.
    await expect(page.locator('.mm-muestra__tabla tbody tr').first().locator('td').nth(5)).not.toHaveCSS('display', 'none');
  });

  test('a 360 px axe no encuentra violaciones en la previsualización', async ({ page }) => {
    await abrirAngosto(page, 360);

    const resultado = await new AxeBuilder({ page })
      .include('[data-resultado]')
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();
    expect(resultado.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
  });

  test('en pantalla ancha la tabla sigue siendo una tabla, con la columna del mensaje acotada', async ({ page }) => {
    await abrirAngosto(page, 1280);

    const fila = page.locator('.mm-muestra__tabla tbody tr').nth(1);
    await expect(fila).toHaveCSS('display', 'table-row');
    const celdaMensaje = fila.locator('td').nth(4);
    expect((await celdaMensaje.boundingBox())!.width).toBeLessThan(400);
    expect((await fila.boundingBox())!.height).toBeLessThan(90);
  });
});

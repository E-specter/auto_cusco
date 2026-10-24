/**
 * MOWA MES configuration, end to end against an intercepted API.
 *
 * The paths covered are the ones where a wrong screen costs a campaign: the
 * original speech edited in place, a speech that cannot be generated because
 * the WhatsApp is missing, supervisors saved with the wrong shape, and a law
 * holiday deleted instead of withdrawn. Every number is synthetic (900000xxx).
 */
import { expect, test, type Page } from '@playwright/test';

import {
  apiMowaMes,
  montarApiMowaMes,
  previsualizacionSintetica,
  versionSpeech,
  type ApiFalsaMowaMes,
} from './api-falsa-mowa-mes';

const RUTA = '/mowa-mes/configuracion';
const ANIO = new Date().getFullYear();

/** Requests to exactly `ruta` (query ignored); a trailing `/` matches any id under it. */
const pedidosA = (api: ApiFalsaMowaMes, metodo: string, ruta: string) =>
  api.pedidos.filter((p) => {
    const camino = p.ruta.split('?')[0];
    return p.metodo === metodo && (ruta.endsWith('/') ? camino.startsWith(ruta) : camino === ruta);
  });

async function abrir(page: Page, api: ApiFalsaMowaMes): Promise<void> {
  await montarApiMowaMes(page, api);
  await page.goto(RUTA);
  await expect(page.getByRole('heading', { name: 'Configuración de MOWA MES' })).toBeVisible();
  await expect(page.locator('[data-speech-filas] tr[data-segmento="9_a_30"] [data-largo]')).not.toHaveText('—');
}

test.describe('carga inicial', () => {
  test('muestra plataforma, supervisores, speech y calendario', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);

    await expect(page.getByLabel('Límite mensual de SMS')).toHaveValue('2500000');
    await expect(page.getByLabel('WhatsApp de contacto')).toHaveValue('900000999');
    await expect(page.getByLabel('Número del supervisor 1')).toHaveValue('900000101');
    await expect(page.getByRole('cell', { name: '00000002' })).toBeVisible();

    // RF-MM-19 corregido: con el Speech original, 9 a 30 mide 156 y se advierte.
    const fila = page.locator('[data-speech-filas] tr[data-segmento="9_a_30"]');
    await expect(fila.locator('[data-largo]')).toHaveText('156');
    await expect(fila.getByText('Más de 150')).toBeVisible();
    // El nombre de fila no repite el segmento.
    await expect(fila.getByRole('rowheader')).toHaveText('9 a 30(9–30 días)');
    // El ejemplo del peor caso describe las partes de su segmento, ya normalizado a GSM-7 (RF-MM-27): sin tildes.
    await expect(fila.locator('[data-ejemplo]')).toHaveText(
      /^Ejemplo en el peor caso: XXXXXXXX Caja Cusco te informa que tu cuota vencio el dd\/mm\/yyyy/,
    );
    await expect(page.locator('[data-speech-resumen]')).toHaveAttribute('role', 'status');
    await expect(page.locator('[data-speech-resumen]')).toHaveText('1 segmento pasa de 150 caracteres.');

    await expect(page.getByRole('rowheader', { name: new RegExp(`01 ene\\.? ${ANIO}`) })).toBeVisible();
    await expect(page.getByText('Retirado este año')).toBeVisible();
    await expect(page.getByText(/Siguiente día gestionable desde hoy/)).toBeVisible();
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

test.describe('speech (RF-MM-17)', () => {
  const NOTICE_V1 = 'Versión de dos partes (v1): se usa en campañas tal como está y ya no se edita.';

  /** Nothing of a v1 is a field: no textarea, no name, no save, no discard. */
  async function esSoloLectura(page: Page) {
    await expect(page.getByText(NOTICE_V1)).toBeVisible();
    await expect(page.locator('[data-speech-filas] textarea')).toHaveCount(0);
    await expect(page.locator('[data-speech-filas] input')).toHaveCount(0);
    await expect(page.locator('[data-speech-pie]')).toBeHidden();
    await expect(page.getByRole('button', { name: /^Guardar (cambios|como versión nueva)$/ })).toBeHidden();
    await expect(page.locator('[data-form-speech]').getByRole('button', { name: 'Descartar cambios' })).toBeHidden();
    await expect(page.getByLabel('Nombre de la versión')).toBeHidden();
  }

  test('el Speech original es solo lectura: sus partes son texto y «Convertir a v2» es lo único que se puede hacer', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);

    await esSoloLectura(page);
    await expect(page.locator('[data-speech-filas] tr[data-segmento="9_a_30"]')).toContainText('Caja Cusco');
    await expect(page.getByRole('button', { name: 'Convertir a v2' })).toBeEnabled();
    await expect(page.getByText('Para personalizarla, conviértela a v2:', { exact: false })).toBeVisible();
    expect(pedidosA(api, 'PUT', '/mowa-mes/speech/')).toEqual([]);
    expect(pedidosA(api, 'POST', '/mowa-mes/speech')).toEqual([]);
  });

  test('una v1 sin uso tampoco se edita: ya no hay editor de dos partes', async ({ page }) => {
    const api = apiMowaMes();
    api.versiones = [api.versiones[0], versionSpeech()];
    await abrir(page, api);

    await page.getByLabel('Versión', { exact: true }).selectOption('2');

    await esSoloLectura(page);
    await expect(page.getByRole('button', { name: 'Convertir a v2' })).toBeEnabled();
  });

  test('las partes se leen tal como se escribieron, con sus espacios', async ({ page }) => {
    const api = apiMowaMes();
    api.versiones = [api.versiones[0], versionSpeech()];
    api.versiones[1].partes[0] = { ...api.versiones[1].partes[0], parte_1: '  dos espacios al inicio ' };
    await abrir(page, api);
    await page.getByLabel('Versión', { exact: true }).selectOption('2');

    const celda = page.locator('[data-speech-filas] tr[data-segmento="preventiva"] [data-campo="parte_1"]');
    // `toHaveText` normalizes spaces: the DOM text is what has to be exact.
    expect(await celda.evaluate((e) => e.textContent)).toBe('  dos espacios al inicio ');
    expect(await celda.evaluate((e) => getComputedStyle(e).whiteSpace)).toBe('pre-wrap');
  });

  test('el hint de estructura de una v1 explica lo que se ve y dónde va el WhatsApp', async ({ page }) => {
    await abrir(page, apiMowaMes());

    await expect(page.locator('p[data-speech-v1][class*="field__hint"]').first()).toHaveText(
      'Mensaje = titular (8 caracteres) + parte 1 + fecha de vencimiento (dd/mm/aaaa) + parte 2. Donde dice [whatsapp] va el enlace al WhatsApp de contacto.',
    );
  });

  test('el backend rechaza crear o editar con partes, y la pantalla nunca las manda', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);
    // What the real backend answers since M3 (B15): the page has no path that sends `partes`.
    const respuestas = await page.evaluate(async () => {
      const crear = await fetch('/api/mowa-mes/speech', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ nombre: 'x', partes: [] }) });
      const editar = await fetch('/api/mowa-mes/speech/1', { method: 'PUT', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ nombre: 'x', partes: [] }) });
      return [crear.status, (await crear.json()).codigo, editar.status, (await editar.json()).codigo];
    });
    expect(respuestas).toEqual([400, 'version_v1_retirada', 400, 'version_v1_retirada']);
  });

  test('sin WhatsApp los segmentos que lo usan no se generan, y al configurarlo se recalcula', async ({ page }) => {
    const api = apiMowaMes();
    api.configuracion = { ...api.configuracion, whatsapp_contacto: null };
    await abrir(page, api);

    await expect(page.getByText(/Falta el WhatsApp de contacto y hay segmentos que usan/)).toBeVisible();
    const resumen = page.getByRole('status').filter({ hasText: /segmento/ });
    await expect(resumen).toHaveText(
      '3 segmentos no se pueden generar sin WhatsApp. 1 segmento pasa de 150 caracteres.',
    );
    const fila = page.locator('[data-speech-filas] tr[data-segmento="31_a_60"]');
    await expect(fila.locator('[data-ejemplo]')).toHaveText('Sin ejemplo: falta el WhatsApp de contacto.');
    await expect(fila.getByText('Falta WhatsApp')).toBeVisible();
    await expect(fila.locator('[data-largo]')).toHaveText('—');

    await page.getByLabel('WhatsApp de contacto').fill('900000555');
    await page.getByRole('button', { name: 'Guardar plataforma' }).click();

    await expect(fila.getByText('Falta WhatsApp')).toHaveCount(0);
    await expect(resumen).not.toContainText('sin WhatsApp');
    await expect(page.getByText(/Falta el WhatsApp de contacto y hay segmentos que usan/)).toBeHidden();
    expect(pedidosA(api, 'PUT', '/mowa-mes/configuracion')[0].cuerpo).toEqual({
      limite_mensual: 2500000,
      registros_por_archivo: 50000,
      bytes_por_archivo: 2000000,
      whatsapp_contacto: '900000555',
      // The form always sends what it shows: the rate, and the template as it is saved.
      tarifa_sms: '0.02',
      plantilla_nombre_archivo: 'mowa_mes_campana_{campana}_{archivo}_de_{total}',
    });
  });
});

test.describe('plataforma', () => {
  test('un WhatsApp que la API rechaza se señala en su campo con el motivo', async ({ page }) => {
    const api = apiMowaMes();
    api.respuestas.guardarConfiguracion = [
      { estado: 400, cuerpo: { detail: 'El numero no cumple RF-02', campo: 'whatsapp_contacto' } },
    ];
    await abrir(page, api);

    const whatsapp = page.getByLabel('WhatsApp de contacto');
    await whatsapp.fill('123');
    await page.getByRole('button', { name: 'Guardar plataforma' }).click();

    await expect(page.getByText('El numero no cumple RF-02')).toBeVisible();
    await expect(whatsapp).toHaveAttribute('aria-invalid', 'true');
  });

  test('vaciar el WhatsApp manda null explícito, porque omitirlo conservaría el número', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);

    await page.getByLabel('WhatsApp de contacto').fill('');
    await page.getByRole('button', { name: 'Guardar plataforma' }).click();

    await expect(page.getByText('Guardado.')).toBeVisible();
    const [guardado] = pedidosA(api, 'PUT', '/mowa-mes/configuracion');
    expect(guardado.cuerpo).toHaveProperty('whatsapp_contacto', null);
    expect(api.configuracion.whatsapp_contacto).toBeNull();
    await expect(page.getByText('Sin WhatsApp de contacto, los segmentos del speech que lo usan no se pueden generar.')).toBeVisible();
  });

  test('un límite que no es un entero positivo no viaja', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);

    await page.getByLabel('Límite mensual de SMS').fill('0');
    await page.getByRole('button', { name: 'Guardar plataforma' }).click();

    await expect(page.locator('[data-plataforma-error]')).toHaveText('Escribe un número entero entre 1 y 1,000,000,000.');
    expect(pedidosA(api, 'PUT', '/mowa-mes/configuracion')).toEqual([]);
  });

  test('el aviso de rango del límite, mientras se escribe, también sale con el número formateado', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);

    await page.getByLabel('Límite mensual de SMS').fill('0');

    await expect(page.locator('[data-limite-hint]')).toHaveText('Escribe un número entero entre 1 y 1,000,000,000.');
  });

  test('en inglés, los tres errores de rango dicen los mismos límites, formateados', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    const api = apiMowaMes();
    await montarApiMowaMes(page, api);
    await page.goto(RUTA);
    await expect(page.getByRole('heading', { name: 'MOWA MES settings' })).toBeVisible();

    await page.getByLabel('Monthly SMS limit').fill('0');
    await page.getByLabel('Rows per file').fill('50001');
    await page.getByLabel('Maximum size per file (bytes)').fill('2000001');
    await page.getByRole('button', { name: 'Save platform' }).click();

    await expect(page.locator('[data-plataforma-error]')).toHaveText(
      'Enter a whole number between 1 and 1,000,000,000. Rows per file range from 1 to 50,000. Size per file ranges from 100,000 to 2,000,000 bytes.',
    );
    expect(pedidosA(api, 'PUT', '/mowa-mes/configuracion')).toEqual([]);
  });
});

test.describe('límites por archivo (C1b, RF-MM-11)', () => {
  test('se muestran y guardan bajando los límites de la plataforma', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);

    await expect(page.getByLabel('Filas por archivo')).toHaveValue('50000');
    await expect(page.getByLabel('Tamaño máximo por archivo (bytes)')).toHaveValue('2000000');

    await page.getByLabel('Filas por archivo').fill('40000');
    await page.getByLabel('Tamaño máximo por archivo (bytes)').fill('1500000');
    await page.getByRole('button', { name: 'Guardar plataforma' }).click();

    await expect(page.getByText('Guardado.')).toBeVisible();
    expect(pedidosA(api, 'PUT', '/mowa-mes/configuracion')[0].cuerpo).toMatchObject({
      registros_por_archivo: 40000,
      bytes_por_archivo: 1500000,
    });
  });

  test('por encima del máximo de la plataforma no viaja y se señala cada campo', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);

    await page.getByLabel('Filas por archivo').fill('50001');
    await page.getByLabel('Tamaño máximo por archivo (bytes)').fill('2000001');
    await page.getByRole('button', { name: 'Guardar plataforma' }).click();

    await expect(page.locator('[data-plataforma-error]')).toHaveText(
      'Las filas por archivo van de 1 a 50,000. El tamaño por archivo va de 100,000 a 2,000,000 bytes.',
    );
    await expect(page.getByLabel('Filas por archivo')).toHaveAttribute('aria-invalid', 'true');
    await expect(page.getByLabel('Tamaño máximo por archivo (bytes)')).toHaveAttribute('aria-invalid', 'true');
    await expect(page.getByLabel('Filas por archivo')).toBeFocused();
    expect(pedidosA(api, 'PUT', '/mowa-mes/configuracion')).toEqual([]);
  });
});

test.describe('supervisores', () => {
  test('agrega un supervisor y guarda la lista completa, con los documentos que asigna la API', async ({ page }) => {
    const api = apiMowaMes();
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
    await expect(page.locator('.mm-supervisores__tabla tbody tr').nth(2).getByRole('cell', { name: '00000002' })).toBeVisible();
  });

  test('renombrar una procedencia arrastra a sus supervisores', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);

    await page.getByLabel('Procedencia 1', { exact: true }).fill('Procedencia C');
    await expect(page.getByLabel('Procedencia del supervisor 1')).toHaveValue('Procedencia C');
  });

  test('un supervisor sin número se señala antes de llamar a la API', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);

    await page.getByRole('button', { name: 'Agregar supervisor' }).click();
    await page.getByRole('button', { name: 'Guardar supervisores' }).click();

    await expect(page.getByText('El supervisor 3 no tiene número.')).toBeVisible();
    await expect(page.getByLabel('Número del supervisor 3')).toHaveAttribute('aria-invalid', 'true');
    expect(pedidosA(api, 'PUT', '/supervisores')).toEqual([]);
  });

  test('una procedencia de más de 60 caracteres dice el máximo, en español y en inglés', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);

    await page.getByRole('textbox', { name: 'Procedencia 1', exact: true }).fill('x'.repeat(61));
    await page.getByRole('button', { name: 'Guardar supervisores' }).click();

    await expect(page.getByText('La procedencia 1 pasa de 60 caracteres.')).toBeVisible();
    expect(pedidosA(api, 'PUT', '/supervisores')).toEqual([]);

    const en = apiMowaMes();
    const paginaEn = await page.context().newPage();
    await paginaEn.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    await montarApiMowaMes(paginaEn, en);
    await paginaEn.goto(RUTA);
    await expect(paginaEn.getByRole('heading', { name: 'MOWA MES settings' })).toBeVisible();
    await paginaEn.getByRole('textbox', { name: 'Origin 1', exact: true }).fill('x'.repeat(61));
    await paginaEn.getByRole('button', { name: 'Save supervisors' }).click();
    await expect(paginaEn.getByText('Origin 1 is longer than 60 characters.')).toBeVisible();
    await paginaEn.close();
  });

  test('sin supervisores guardados avisa que no se podrá crear ninguna campaña', async ({ page }) => {
    const api = apiMowaMes();
    api.supervision = { procedencias: ['Procedencia A'], supervisores: [] };
    await abrir(page, api);

    await expect(page.getByText('Sin supervisores no se puede crear ninguna campaña.', { exact: false })).toBeVisible();
  });
});

test.describe('calendario', () => {
  test('un feriado de ley se retira con una excepción, nunca se borra', async ({ page }) => {
    const api = apiMowaMes();
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
    const api = apiMowaMes();
    await abrir(page, api);

    await page.getByRole('button', { name: /Quitar el día no laborable/ }).click();

    await expect(page.getByRole('row', { name: /Día no laborable sintético/ })).toHaveCount(0);
    expect(pedidosA(api, 'DELETE', '/calendario/excepciones/').map((p) => p.ruta)).toEqual([
      `/calendario/excepciones/${ANIO}-12-24`,
    ]);
  });

  test('una fecha que ya tiene excepción responde 409 y se explica en el diálogo', async ({ page }) => {
    const api = apiMowaMes();
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
    const api = apiMowaMes();
    await abrir(page, api);

    await page.getByRole('button', { name: 'Año siguiente' }).click();

    await expect(page.locator('[data-anio]')).toHaveText(String(ANIO + 1));
    await expect(page.getByRole('rowheader', { name: new RegExp(`01 ene\\.? ${ANIO + 1}`) })).toBeVisible();
  });
});

test.describe('anchos (T-MM-F5, hallazgos 1 y 2)', () => {
  test('a 360 px, las tablas de speech y supervisores se apilan sin desbordar la página', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    const api = apiMowaMes();
    await abrir(page, api);

    const desborda = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
    expect(desborda).toBe(false);

    // The speech table stacks below 64rem (`.table--apilable-ancha`): its
    // head is visually hidden and Largo/Estado read as labelled blocks,
    // visible in the viewport without scrolling sideways.
    // No horizontal overflow means a cell either sits at x=0 (full width,
    // like a stacked block) or does not exist off to the right at all — a
    // scrolling page is fine, a scrolling table (the pre-F5 behaviour) is not.
    const sinDesbordeHorizontal = async (locator: ReturnType<Page['locator']>) => {
      await locator.scrollIntoViewIfNeeded();
      const caja = await locator.boundingBox();
      expect(caja).not.toBeNull();
      expect(caja!.x).toBeGreaterThanOrEqual(0);
      expect(caja!.x + caja!.width).toBeLessThanOrEqual(361);
    };

    const filaSpeech = page.locator('[data-speech-filas] tr[data-segmento="preventiva"]');
    const largoEtiqueta = await filaSpeech.locator('[data-largo]').evaluate(
      (el) => getComputedStyle(el, '::before').content,
    );
    expect(largoEtiqueta).toContain('Largo máximo');
    await sinDesbordeHorizontal(filaSpeech.locator('[data-largo]'));

    // The supervisors table stacks below 48rem (`.table--apilable`):
    // Procedencia and Documento, cut off before F5, are now full rows.
    const filaSupervisor = page.locator('.mm-supervisores__tabla tbody tr').first();
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

test.describe('un segmento sin largo máximo (speech v2, B6)', () => {
  test('la fila muestra «—», no afirma un nivel y la pantalla no se rompe', async ({ page }) => {
    const errores: string[] = [];
    page.on('pageerror', (error) => errores.push(error.message));
    const api = apiMowaMes();
    await montarApiMowaMes(page, api);
    // The fake answers a v1 preview, where the maximum always exists: this one answers, for 9 a 30, as a
    // preview with no maximum would (registered after the module's mock, so it runs first).
    await page.route('**/api/mowa-mes/speech/previsualizacion', async (route) => {
      const real = previsualizacionSintetica(
        JSON.parse(route.request().postData() ?? '{}'),
        api.configuracion.whatsapp_contacto,
      );
      const segmentos = real.segmentos.map((s) =>
        s.segmento === '9_a_30'
          ? {
              ...s,
              largo_maximo: null,
              codigo: null,
              sin_maximo: {
                codigo: 'sin_cota_variable',
                detalle: "El largo de la variable 'monto' depende del dato de cada producto",
                ubicacion: { nodo: 1, funcion: null, parametro: null },
              },
            }
          : s,
      );
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...real, segmentos }) });
    });
    await page.goto(RUTA);
    await expect(page.getByRole('heading', { name: 'Configuración de MOWA MES' })).toBeVisible();
    // The other rows still read as before: the page painted past the segment without a maximum.
    await expect(page.locator('[data-speech-filas] tr[data-segmento="preventiva"] [data-largo]')).not.toHaveText('—');

    const fila = page.locator('[data-speech-filas] tr[data-segmento="9_a_30"]');
    await expect(fila.locator('[data-largo]')).toHaveText('—');
    // No level is claimed for it: neither "Cabe" nor the 150 or 160 warnings.
    await expect(fila.locator('[data-nivel-tags]').getByText(/^(Cabe|Más de 150|Más de 160)$/)).toHaveCount(0);
    // Nor any other level tag: the only tag left is the one that says it uses the WhatsApp.
    await expect(fila.locator('[data-nivel-tags] .tag').filter({ hasNotText: 'Usa WhatsApp' })).toHaveCount(0);
    await expect(fila).toHaveAttribute('data-nivel-largo', '');
    expect(errores).toEqual([]);
  });
});

test.describe('idioma', () => {
  test('en inglés traduce lo que dibuja el script, incluidos los códigos', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    const api = apiMowaMes();
    await montarApiMowaMes(page, api);
    await page.goto(RUTA);

    await expect(page.getByRole('heading', { name: 'MOWA MES settings' })).toBeVisible();
    const fila = page.locator('[data-speech-filas] tr[data-segmento="9_a_30"]');
    await expect(fila.getByText('Over 150')).toBeVisible();
    await expect(fila.getByText(/longer than 150 characters/)).toBeVisible();
  });
});

// Accessibility (axe) for this screen lives in e2e/accesibilidad.spec.ts,
// alongside the other MOWA MES screens (T-MM-F5).

test.describe('F6-B: tarifa y nombre de los archivos (RF-MM-23, RF-MM-25)', () => {
  const plantilla = (page: Page) => page.getByLabel('Nombre de los archivos');
  const tarifa = (page: Page) => page.getByLabel('Tarifa por SMS (S/)');
  const ejemplo = (page: Page) => page.locator('[data-plantilla-ejemplo]');
  const errorPlantilla = (page: Page) => page.locator('[data-plantilla-error]');
  const variables = (page: Page) => page.getByRole('group', { name: 'Variables de la plantilla' });
  const putsDeConfiguracion = (api: ApiFalsaMowaMes) => pedidosA(api, 'PUT', '/mowa-mes/configuracion');
  const revisionesDePlantilla = (api: ApiFalsaMowaMes) =>
    pedidosA(api, 'POST', '/mowa-mes/plantilla-nombre-archivo/previsualizacion');

  test('muestra la tarifa sin ceros de más, la plantilla, las 7 variables de la API y el nombre que ella devuelve', async ({
    page,
  }) => {
    const api = apiMowaMes();
    await abrir(page, api);

    await expect(tarifa(page)).toHaveValue('0.02');
    await expect(tarifa(page)).toHaveAttribute('inputmode', 'decimal');
    await expect(tarifa(page)).not.toHaveAttribute('type', 'number');
    await expect(plantilla(page)).toHaveValue('mowa_mes_campana_{campana}_{archivo}_de_{total}');
    // The list is the API's, in its order: nothing is spelled out in the screen.
    await expect(variables(page).getByRole('button')).toHaveText([
      '{campana}',
      '{descripcion}',
      '{fecha_envio}',
      '{fecha_corte}',
      '{archivo}',
      '{total}',
      '{cantidad}',
    ]);
    // The buttons are a labelled group that follows the field in the DOM, right after it.
    await expect(page.locator('#mm-plantilla + [data-plantilla-variables]')).toHaveCount(1);
    await expect(variables(page)).toHaveAttribute('role', 'group');
    await expect(variables(page).getByRole('button', { name: '{total}' })).toHaveAttribute(
      'title',
      'Cantidad de archivos de la campana',
    );
    // The name is worked out by the API with sample data; the screen only shows it.
    await expect(ejemplo(page)).toContainText('Nombre del primer archivo: mowa_mes_campana_1234_1_de_2.xlsx');
    await expect(ejemplo(page)).toContainText('Nombre del archivo 2: mowa_mes_campana_1234_2_de_2.xlsx');
  });

  test('un botón inserta la variable donde está el cursor, reemplaza la selección y deja el foco en el campo', async ({
    page,
  }) => {
    const api = apiMowaMes();
    await abrir(page, api);
    const campo = plantilla(page);

    await campo.fill('carga_.final');
    await campo.evaluate((el: HTMLInputElement) => el.setSelectionRange(6, 6));
    await variables(page).getByRole('button', { name: '{campana}' }).click();
    await expect(campo).toHaveValue('carga_{campana}.final');
    await expect(campo).toBeFocused();
    expect(await campo.evaluate((el: HTMLInputElement) => el.selectionStart)).toBe(15);

    // A selection is replaced.
    await campo.evaluate((el: HTMLInputElement) => el.setSelectionRange(6, 15));
    await variables(page).getByRole('button', { name: '{fecha_corte}' }).click();
    await expect(campo).toHaveValue('carga_{fecha_corte}.final');
    // Inserting is typing: the API is asked for the new name.
    await expect(ejemplo(page)).toContainText('carga_2026-09-30.final_1de2.xlsx');
  });

  test('una variable desconocida se marca en vivo con la lista de la API y no se pide el nombre', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);
    const antes = revisionesDePlantilla(api).length;

    await plantilla(page).fill('carga_{banco}_{campana}');

    await expect(errorPlantilla(page)).toHaveText('No es una variable de la plantilla: {banco}. Usa las de los botones.');
    await expect(plantilla(page)).toHaveAttribute('aria-invalid', 'true');
    await expect(plantilla(page)).toHaveAccessibleDescription(/No es una variable de la plantilla: \{banco\}/);
    await expect(ejemplo(page)).toBeEmpty();
    // Waits past the typing delay: no request goes out for a template already known to be wrong.
    await page.waitForTimeout(700);
    expect(revisionesDePlantilla(api)).toHaveLength(antes);

    // And it cannot be saved.
    await page.getByRole('button', { name: 'Guardar plataforma' }).click();
    expect(putsDeConfiguracion(api)).toEqual([]);
    await expect(plantilla(page)).toBeFocused();

    // Fixing it clears the mark and brings the name back.
    await plantilla(page).fill('carga_{campana}');
    await expect(errorPlantilla(page)).toHaveText('');
    await expect(plantilla(page)).toHaveAttribute('aria-invalid', 'false');
    await expect(ejemplo(page)).toContainText('carga_1234_1de2.xlsx');
  });

  test('una llave sin cerrar la dice el 400 de la API, junto al campo', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);

    await plantilla(page).fill('carga_{campana');

    await expect(errorPlantilla(page)).toHaveText('La plantilla tiene una llave { sin cerrar');
    await expect(plantilla(page)).toHaveAttribute('aria-invalid', 'true');
    await expect(ejemplo(page)).toBeEmpty();
  });

  test('guardar manda la tarifa y la plantilla, acepta la coma y muestra lo que la API guardó', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);

    await tarifa(page).fill('0,025');
    await plantilla(page).fill('carga_{fecha_envio}_{archivo}');
    await page.getByRole('button', { name: 'Guardar plataforma' }).click();

    await expect(page.getByText('Guardado.')).toBeVisible();
    expect(putsDeConfiguracion(api)[0].cuerpo).toMatchObject({
      tarifa_sms: '0.025',
      plantilla_nombre_archivo: 'carga_{fecha_envio}_{archivo}',
    });
    // The API keeps four decimals; the field reads them without the extra zero.
    await expect(tarifa(page)).toHaveValue('0.025');
    expect(api.configuracion.tarifa_sms).toBe('0.0250');
  });

  test.describe('una tarifa inválida no viaja', () => {
    for (const escrita of ['abc', '', '-0.02', '0.02345', '0.0.2', 'S/ 0.02']) {
      test(`la tarifa ${JSON.stringify(escrita)} se señala junto al campo, anclada con aria-describedby`, async ({
        page,
      }) => {
        const api = apiMowaMes();
        await abrir(page, api);

        await tarifa(page).fill(escrita);
        await page.getByRole('button', { name: 'Guardar plataforma' }).click();

        const mensaje = page.locator('[data-tarifa-error]');
        await expect(mensaje).toHaveText(
          'La tarifa debe ser un decimal de 0 en adelante, con hasta 4 decimales (por ejemplo 0.02).',
        );
        await expect(tarifa(page)).toHaveAttribute('aria-invalid', 'true');
        await expect(tarifa(page)).toHaveAttribute('aria-describedby', 'mm-tarifa-hint mm-tarifa-error');
        await expect(tarifa(page)).toHaveAccessibleDescription(/con hasta 4 decimales \(por ejemplo 0\.02\)/);
        await expect(tarifa(page)).toBeFocused();
        expect(putsDeConfiguracion(api)).toEqual([]);

        // Typing clears the mark.
        await tarifa(page).fill('0.03');
        await expect(mensaje).toHaveText('');
        await expect(tarifa(page)).not.toHaveAttribute('aria-invalid', 'true');
      });
    }
  });

  test('un 400 de la API sobre la tarifa se muestra bajo la tarifa, no bajo el WhatsApp', async ({ page }) => {
    const api = apiMowaMes();
    api.respuestas.guardarConfiguracion = [
      {
        estado: 400,
        cuerpo: {
          detail: 'La tarifa debe ser un numero decimal mayor o igual a 0, con hasta 4 decimales (por ejemplo 0.02)',
          campo: 'tarifa_sms',
        },
      },
    ];
    await abrir(page, api);

    await page.getByRole('button', { name: 'Guardar plataforma' }).click();

    await expect(page.locator('[data-tarifa-error]')).toHaveText(
      'La tarifa debe ser un numero decimal mayor o igual a 0, con hasta 4 decimales (por ejemplo 0.02)',
    );
    await expect(tarifa(page)).toBeFocused();
    await expect(page.getByLabel('WhatsApp de contacto')).not.toHaveAttribute('aria-invalid', 'true');
    await expect(page.locator('[data-plataforma-error]')).toHaveText('');
  });

  test('un 400 de la API sobre la plantilla nombra la variable, bajo el campo de la plantilla', async ({ page }) => {
    const api = apiMowaMes();
    api.respuestas.guardarConfiguracion = [
      {
        estado: 400,
        cuerpo: {
          detail: '{banco} no es una variable de la plantilla. Variables validas: {campana}',
          campo: 'plantilla_nombre_archivo',
        },
      },
    ];
    await abrir(page, api);

    await page.getByRole('button', { name: 'Guardar plataforma' }).click();

    await expect(errorPlantilla(page)).toHaveText(/^\{banco\} no es una variable de la plantilla/);
    await expect(plantilla(page)).toBeFocused();
    await expect(plantilla(page)).toHaveAttribute('aria-invalid', 'true');
  });

  test.describe('el campo del 400 decide dónde va el error, no las palabras del texto', () => {
    const general = (page: Page) => page.locator('[data-plataforma-error]');
    const sinMarcas = async (page: Page) => {
      for (const campo of [tarifa(page), plantilla(page), page.getByLabel('WhatsApp de contacto')]) {
        await expect(campo).not.toHaveAttribute('aria-invalid', 'true');
      }
      await expect(page.locator('[data-tarifa-error]')).toHaveText('');
      await expect(errorPlantilla(page)).toHaveText('');
    };

    test('sin campo el texto va al aviso general y no se marca ni se enfoca ningún campo', async ({ page }) => {
      const api = apiMowaMes();
      // The sentence talks about the rate, but names no field: it must not be placed by its words.
      api.respuestas.guardarConfiguracion = [{ estado: 400, cuerpo: { detail: 'La tarifa no es válida por una razón nueva' } }];
      await abrir(page, api);

      await page.getByRole('button', { name: 'Guardar plataforma' }).click();

      await expect(general(page)).toHaveText('La tarifa no es válida por una razón nueva');
      await sinMarcas(page);
      await expect(tarifa(page)).not.toBeFocused();
    });

    test('un campo que el cliente no conoce se trata como si no hubiera campo', async ({ page }) => {
      const api = apiMowaMes();
      api.respuestas.guardarConfiguracion = [
        { estado: 400, cuerpo: { detail: 'Algo de un ajuste nuevo', campo: 'ajuste_nuevo' } },
      ];
      await abrir(page, api);

      await page.getByRole('button', { name: 'Guardar plataforma' }).click();

      await expect(general(page)).toHaveText('Algo de un ajuste nuevo');
      await sinMarcas(page);
    });

    test('el campo manda aunque el texto hable de otra cosa', async ({ page }) => {
      const api = apiMowaMes();
      api.respuestas.guardarConfiguracion = [
        { estado: 400, cuerpo: { detail: 'La tarifa y la plantilla no tienen nada que ver', campo: 'whatsapp_contacto' } },
      ];
      await abrir(page, api);

      await page.getByRole('button', { name: 'Guardar plataforma' }).click();

      await expect(general(page)).toHaveText('La tarifa y la plantilla no tienen nada que ver');
      await expect(page.getByLabel('WhatsApp de contacto')).toHaveAttribute('aria-invalid', 'true');
      await expect(page.getByLabel('WhatsApp de contacto')).toBeFocused();
      await expect(tarifa(page)).not.toHaveAttribute('aria-invalid', 'true');
      await expect(plantilla(page)).not.toHaveAttribute('aria-invalid', 'true');
    });

    for (const [campo, etiqueta] of [
      ['registros_por_archivo', 'Filas por archivo'],
      ['bytes_por_archivo', 'Tamaño máximo por archivo (bytes)'],
      ['limite_mensual', 'Límite mensual de SMS'],
    ] as const) {
      test(`${campo}: el texto va al aviso general y se marca y enfoca ese campo`, async ({ page }) => {
        const api = apiMowaMes();
        api.respuestas.guardarConfiguracion = [{ estado: 400, cuerpo: { detail: `Motivo de ${campo}`, campo } }];
        await abrir(page, api);

        await page.getByRole('button', { name: 'Guardar plataforma' }).click();

        await expect(general(page)).toHaveText(`Motivo de ${campo}`);
        await expect(page.getByLabel(etiqueta)).toHaveAttribute('aria-invalid', 'true');
        await expect(page.getByLabel(etiqueta)).toBeFocused();
      });
    }

    test('el 400 real de una tarifa o una plantilla que no aceptó la API trae su campo', async ({ page }) => {
      const api = apiMowaMes();
      await abrir(page, api);
      // Past the local checks (a template that is well formed here) but over the API's own limit of 300 characters.
      await plantilla(page).fill(`{campana}${'x'.repeat(300)}`);
      await page.getByRole('button', { name: 'Guardar plataforma' }).click();

      await expect(errorPlantilla(page)).toHaveText('La plantilla no puede pasar de 300 caracteres');
      await expect(plantilla(page)).toBeFocused();
      await expect(plantilla(page)).toHaveAttribute('aria-invalid', 'true');
    });
  });

  test('una plantilla vacía queda como la de por defecto, la que devuelve la API', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);

    await plantilla(page).fill('');
    await expect(ejemplo(page)).toContainText('mowa_mes_campana_1234_1_de_2.xlsx');
    await page.getByRole('button', { name: 'Guardar plataforma' }).click();

    await expect(page.getByText('Guardado.')).toBeVisible();
    await expect(plantilla(page)).toHaveValue('mowa_mes_campana_{campana}_{archivo}_de_{total}');
  });

  test('en inglés traduce los rótulos y la nota de variables', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    const api = apiMowaMes();
    await montarApiMowaMes(page, api);
    await page.goto(RUTA);

    await expect(page.getByLabel('Rate per SMS (S/)')).toHaveValue('0.02');
    await expect(page.getByLabel('File names')).toHaveValue('mowa_mes_campana_{campana}_{archivo}_de_{total}');
    await expect(page.locator('[data-plantilla-ejemplo]')).toContainText('Name of the first file:');
    await expect(page.getByRole('group', { name: 'Template variables' })).toBeVisible();

    await page.getByLabel('File names').fill('{banco}');
    await expect(page.locator('[data-plantilla-error]')).toHaveText(
      'Not a template variable: {banco}. Use the ones on the buttons.',
    );
  });
});

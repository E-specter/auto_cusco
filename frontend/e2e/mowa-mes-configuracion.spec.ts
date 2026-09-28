/**
 * MOWA MES configuration, end to end against an intercepted API.
 *
 * The paths covered are the ones where a wrong screen costs a campaign: the
 * original speech edited in place, a speech that cannot be generated because
 * the WhatsApp is missing, supervisors saved with the wrong shape, and a law
 * holiday deleted instead of withdrawn. Every number is synthetic (900000xxx).
 */
import { expect, test, type Page } from '@playwright/test';

import { apiMowaMes, montarApiMowaMes, versionSpeech, type ApiFalsaMowaMes } from './api-falsa-mowa-mes';

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
    // El ejemplo del peor caso describe las partes de su segmento.
    await expect(page.getByLabel('Parte 2 del segmento 9 a 30')).toHaveAccessibleDescription(
      /^Ejemplo en el peor caso: XXXXXXXX Caja Cusco te informa que tu cuota venció el dd\/mm\/yyyy/,
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
  test('el Speech original nunca se edita: el cambio crea una versión nueva basada en él', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);

    await expect(page.getByText('El Speech original no se modifica nunca.', { exact: false })).toBeVisible();
    const guardar = page.getByRole('button', { name: 'Guardar como versión nueva' });
    await expect(guardar).toBeDisabled();

    const parte = page.getByLabel('Parte 2 del segmento 9 a 30');
    await parte.fill(', acércate a pagar a nuestras agencias.');
    await expect(page.locator('[data-speech-filas] tr[data-segmento="9_a_30"]').getByText('Cabe')).toBeVisible();

    await guardar.click();

    await expect(page.getByText('Versión nueva creada.')).toBeVisible();
    expect(pedidosA(api, 'PUT', '/mowa-mes/speech/')).toEqual([]);
    const [creacion] = pedidosA(api, 'POST', '/mowa-mes/speech');
    expect(creacion.cuerpo).toMatchObject({ nombre: null, basada_en_id: 1 });
    expect((creacion.cuerpo as { partes: Array<{ segmento: string; parte_2: string }> }).partes).toContainEqual(
      expect.objectContaining({ segmento: '9_a_30', parte_2: ', acércate a pagar a nuestras agencias.' }),
    );
    await expect(page.getByLabel('Versión', { exact: true })).toHaveValue('2');
  });

  test('una versión sin uso se edita en su lugar, conservando los espacios de los extremos', async ({ page }) => {
    const api = apiMowaMes();
    api.versiones = [api.versiones[0], versionSpeech()];
    await abrir(page, api);

    await page.getByLabel('Versión', { exact: true }).selectOption('2');
    await page.getByLabel('Parte 1 del segmento Preventiva').fill(' te recordamos que tu cuota vence el ');
    await page.getByRole('button', { name: 'Guardar cambios' }).click();

    await expect(page.getByText('Versión guardada.')).toBeVisible();
    const [edicion] = pedidosA(api, 'PUT', '/mowa-mes/speech/2');
    expect((edicion.cuerpo as { partes: Array<{ segmento: string; parte_1: string }> }).partes).toContainEqual(
      expect.objectContaining({ segmento: 'preventiva', parte_1: ' te recordamos que tu cuota vence el ' }),
    );
  });

  test('si una campaña la usó mientras tanto, lo dice y la vuelve de solo lectura', async ({ page }) => {
    const api = apiMowaMes();
    api.versiones = [api.versiones[0], versionSpeech()];
    api.respuestas.editarSpeech = [{ estado: 409, cuerpo: { detail: 'La version ya se uso y no se modifica' } }];
    await abrir(page, api);

    await page.getByLabel('Versión', { exact: true }).selectOption('2');
    api.versiones = [api.versiones[0], versionSpeech({ usada: true, editable: false })];
    await page.getByLabel('Parte 1 del segmento 1 a 8').fill(' texto sintético ');
    await page.getByRole('button', { name: 'Guardar cambios' }).click();

    await expect(page.getByText('La version ya se uso y no se modifica')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Guardar como versión nueva' })).toBeEnabled();
    // Lo escrito no se pierde.
    await expect(page.getByLabel('Parte 1 del segmento 1 a 8')).toHaveValue(' texto sintético ');
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
    await expect(page.getByLabel('Parte 1 del segmento 31 a 60')).toHaveAccessibleDescription(
      'Sin ejemplo: falta el WhatsApp de contacto.',
    );
    const fila = page.locator('[data-speech-filas] tr[data-segmento="31_a_60"]');
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

    await expect(page.locator('[data-plataforma-error]')).toHaveText('Escribe un número entero entre 1 y 1 000 000 000.');
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
      'Las filas por archivo van de 1 a 50 000. El tamaño por archivo va de 100 000 a 2 000 000 bytes.',
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

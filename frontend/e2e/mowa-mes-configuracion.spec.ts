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
      /^Ejemplo en el peor caso: TITULAR8 Caja Cusco te informa/,
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
      whatsapp_contacto: '900000555',
    });
  });
});

test.describe('plataforma', () => {
  test('un WhatsApp que la API rechaza se señala en su campo con el motivo', async ({ page }) => {
    const api = apiMowaMes();
    api.respuestas.guardarConfiguracion = [{ estado: 400, cuerpo: { detail: 'El numero no cumple RF-02' } }];
    await abrir(page, api);

    const whatsapp = page.getByLabel('WhatsApp de contacto');
    await whatsapp.fill('123');
    await page.getByRole('button', { name: 'Guardar plataforma' }).click();

    await expect(page.getByText('El numero no cumple RF-02')).toBeVisible();
    await expect(whatsapp).toHaveAttribute('aria-invalid', 'true');
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

// Accessibility (axe) for this screen joins e2e/accesibilidad.spec.ts once
// that file and its @axe-core/playwright dependency are committed, so this
// spec does not depend on uncommitted work.

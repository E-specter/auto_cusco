/**
 * WhatsMKT configuration (T-WM-F1a), end to end against an intercepted API.
 *
 * The paths covered are the ones where a wrong screen costs a campaign: a segment table that leaves days
 * without a segment, a time slot that ends before it starts, a name template over the 75 characters
 * WhatsMKT accepts, and a limit saved in the wrong unit (the attachments travel in bytes, the field shows
 * megabytes). The clock is fixed from the first spec, in `montarApiWhatsmkt`.
 */
import { expect, test, type Page } from '@playwright/test';

import { apiWhatsmkt, errorWhatsmkt, montarApiWhatsmkt, type ApiFalsaWhatsmkt } from './api-falsa-whatsmkt';
import { mensajesFalsos, montarMensajesWhatsmkt } from './api-falsa-whatsmkt-mensajes';

const RUTA = '/whatsmkt/configuracion';

/** Requests to exactly `ruta` (query ignored). */
const pedidosA = (api: ApiFalsaWhatsmkt, metodo: string, ruta: string) =>
  api.pedidos.filter((p) => p.metodo === metodo && p.ruta.split('?')[0] === ruta);

async function abrir(page: Page, api: ApiFalsaWhatsmkt): Promise<void> {
  await montarApiWhatsmkt(page, api);
  // The settings read the saved messages and the default definition; what a spec registers after this one answers first.
  await montarMensajesWhatsmkt(page, mensajesFalsos());
  await page.goto(RUTA);
  await expect(page.getByRole('heading', { name: 'Configuración de WhatsMKT', level: 1 })).toBeVisible();
  await expect(page.getByLabel('Nombre del segmento Preventivo')).toBeVisible();
}

const fila = (page: Page, clave: string) => page.locator(`[data-segmentos-tabla] tr[data-clave="${clave}"]`);
const errorDeFila = (page: Page, clave: string) => page.locator(`[data-error-fila="${clave}"]`);
const horaDe = (page: Page, franja: 1 | 2, campo: 'inicio' | 'fin') => page.locator(`#wm-h${franja}-${campo}`);
const topeDe = (page: Page, campo: 'mensaje' | 'video' | 'audio' | 'pdf') => page.locator(`#wm-tope-${campo}`);
const plantilla = (page: Page) => page.locator('#wm-plantilla');
const guardar = (page: Page, nombre: string) => page.getByRole('button', { name: nombre });

test.describe('carga inicial', () => {
  test('muestra lo guardado en cada panel, con los mensajes en los dos primeros', async ({ page }) => {
    await abrir(page, apiWhatsmkt());

    await expect(horaDe(page, 1, 'inicio')).toHaveValue('08:00');
    await expect(horaDe(page, 1, 'fin')).toHaveValue('14:00');
    await expect(horaDe(page, 2, 'inicio')).toHaveValue('14:00');
    await expect(horaDe(page, 2, 'fin')).toHaveValue('20:00');
    await expect(plantilla(page)).toHaveValue('CUZCO_Vencida ({segmento}) whatsapp {fecha_corte}');
    // The attachments are bytes in the API and megabytes (decimal) on the screen.
    await expect(topeDe(page, 'mensaje')).toHaveValue('4096');
    for (const campo of ['video', 'audio', 'pdf'] as const) await expect(topeDe(page, campo)).toHaveValue('16');

    // The eight panels, in the order of the interface rules (§5). The messages of the segments are the component's own panel inside the
    // first one (its heading is hidden: the block carries its own), and the global ones are the second.
    await expect(page.locator('h2.panel__title')).toHaveText([
      'Segmentos y mensajes',
      'Mensajes por segmento',
      'Mensajes globales',
      'WhatsApp de contacto',
      'Horarios de envío',
      'Nombre de la campaña',
      'Definición por defecto',
      'Topes',
      'Biblioteca de adjuntos',
    ]);
    await expect(page.getByRole('region', { name: 'Mensajes globales' })).toBeVisible();
    await expect(page.getByRole('region', { name: 'Segmentos y mensajes' })).toContainText('Mensaje de cada segmento');
    for (const titulo of ['Segmentos y mensajes', 'Mensajes globales', 'WhatsApp de contacto', 'Definición por defecto', 'Biblioteca de adjuntos']) {
      await expect(page.getByRole('region', { name: titulo })).not.toContainText('Disponible pronto.');
    }
  });

  test('avisa que Columnas, Supervisores y Calendario tienen su propia pantalla, con sus enlaces', async ({ page }) => {
    await abrir(page, apiWhatsmkt());

    const aviso = page.locator('[data-herramientas]');
    await expect(aviso).toHaveClass(/notice--info/);
    await expect(aviso).toHaveText(
      'Columnas de carga, Supervisores y Calendario laboral tienen su propia pantalla: Columnas de carga · Supervisores · Calendario laboral.',
    );
    await expect(aviso.getByRole('link', { name: 'Columnas de carga' })).toHaveAttribute('href', '/columnas');
    await expect(aviso.getByRole('link', { name: 'Supervisores' })).toHaveAttribute('href', '/supervisores');
    await expect(aviso.getByRole('link', { name: 'Calendario laboral' })).toHaveAttribute('href', '/calendario');
  });

  test('sin conexión con la API muestra el aviso en vez de paneles vacíos, y Reintentar recupera la pantalla', async ({ page }) => {
    const api = apiWhatsmkt();
    api.sinRed = true;
    await montarApiWhatsmkt(page, api);
    // The settings read the saved messages and the default definition; what a spec registers after this one answers first.
    await montarMensajesWhatsmkt(page, mensajesFalsos());
    await page.goto(RUTA);

    await expect(page.getByRole('heading', { name: 'Sin conexión con la API' })).toBeVisible();
    await expect(page.getByRole('region', { name: 'Topes' })).toBeHidden();

    api.sinRed = false;
    await page.getByRole('button', { name: 'Reintentar' }).click();

    await expect(page.getByRole('region', { name: 'Topes' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Sin conexión con la API' })).toBeHidden();
  });
});

test.describe('segmentos', () => {
  test('el primero no tiene mínimo y el último no tiene máximo: se leen, no se escriben', async ({ page }) => {
    await abrir(page, apiWhatsmkt());

    await expect(fila(page, 'preventivo')).toContainText('sin mínimo');
    await expect(fila(page, 'mayores_2')).toContainText('sin máximo');
    await expect(page.getByLabel('Desde, segmento Preventivo')).toHaveCount(0);
    await expect(page.getByLabel('Hasta, segmento Tramos mayores al 2')).toHaveCount(0);
    await expect(page.getByLabel('Hasta, segmento Preventivo')).toHaveValue('0');
    await expect(page.getByLabel('Desde, segmento Tramo 2')).toHaveValue('1');
  });

  test('el límite fijo ocupa el alto de los campos de su fila y su texto va centrado', async ({ page }) => {
    await abrir(page, apiWhatsmkt());

    const fijo = (await fila(page, 'preventivo').locator('.wm-segmentos__fijo').boundingBox())!;
    const campo = (await page.getByLabel('Hasta, segmento Preventivo').boundingBox())!;

    expect(Math.abs(fijo.height - campo.height)).toBeLessThanOrEqual(1);
    expect(Math.abs(fijo.y - campo.y)).toBeLessThanOrEqual(1);
    await expect(fila(page, 'preventivo').locator('.wm-segmentos__fijo')).toHaveCSS('align-items', 'center');
    // It has the box of a field but must not look like one: no border and no fill, or it would read as editable.
    await expect(fila(page, 'preventivo').locator('.wm-segmentos__fijo')).toHaveCSS('border-top-color', 'rgba(0, 0, 0, 0)');
    await expect(fila(page, 'preventivo').locator('.wm-segmentos__fijo')).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)');
  });

  test('salir de un campo inválido hacia otro campo dice el problema de su fila, sin guardar', async ({ page }) => {
    const api = apiWhatsmkt();
    await abrir(page, api);

    await page.getByLabel('Desde, segmento Tramo 2').fill('1.5');
    await page.keyboard.press('Tab');

    await expect(errorDeFila(page, 'tramo_2')).toHaveText('Escribe un número entero de días.');
    await expect(page.getByLabel('Desde, segmento Tramo 2')).toHaveAttribute('aria-invalid', 'true');
    expect(pedidosA(api, 'PUT', '/whatsmkt/segmentos')).toHaveLength(0);
  });

  test('guarda la etiqueta y los límites, y manda los tres segmentos con los límites fijos en null', async ({ page }) => {
    const api = apiWhatsmkt();
    await abrir(page, api);

    await page.getByLabel('Nombre del segmento Tramo 2').fill('Tramo medio');
    await page.getByLabel('Hasta, segmento Tramo 2').fill('10');
    await page.getByLabel('Desde, segmento Tramos mayores al 2').fill('11');
    await guardar(page, 'Guardar segmentos').click();

    await expect(page.locator('[data-segmentos-estado]')).toHaveText('Guardado.');
    expect(pedidosA(api, 'PUT', '/whatsmkt/segmentos').at(-1)?.cuerpo).toEqual([
      { clave: 'preventivo', etiqueta: 'Preventivo', desde: null, hasta: 0 },
      { clave: 'tramo_2', etiqueta: 'Tramo medio', desde: 1, hasta: 10 },
      { clave: 'mayores_2', etiqueta: 'Tramos mayores al 2', desde: 11, hasta: null },
    ]);
    // The table is drawn again from the answer, and the name examples carry the new label.
    await expect(page.getByLabel('Nombre del segmento Tramo medio')).toHaveValue('Tramo medio');
    await expect(page.locator('[data-ejemplos]')).toContainText('CUZCO_Vencida (Tramo medio) whatsapp');
  });

  test('segmentos que se superponen: el error va bajo la fila y nombra con quién se pisa', async ({ page }) => {
    const api = apiWhatsmkt();
    await abrir(page, api);

    await page.getByLabel('Desde, segmento Tramo 2').fill('0');
    await guardar(page, 'Guardar segmentos').click();

    await expect(errorDeFila(page, 'tramo_2')).toBeVisible();
    await expect(errorDeFila(page, 'tramo_2')).toHaveText('Los rangos de días se superponen con Preventivo.');
    await expect(page.getByLabel('Desde, segmento Tramo 2')).toHaveAttribute('aria-invalid', 'true');
    await expect(page.getByLabel('Desde, segmento Tramo 2')).toBeFocused();
    await expect(errorDeFila(page, 'preventivo')).toBeHidden();
    // Nothing was saved: the saved table is the same.
    expect(api.segmentos.map((s) => s.desde)).toEqual([null, 1, 9]);
    await expect(page.locator('[data-segmentos-estado]')).toHaveText('');
  });

  test('segmentos con hueco: el error va bajo la tabla, con los días que quedan sin segmento', async ({ page }) => {
    await abrir(page, apiWhatsmkt());

    await page.getByLabel('Desde, segmento Tramo 2').fill('3');
    await guardar(page, 'Guardar segmentos').click();

    await expect(page.locator('[data-segmentos-error]')).toHaveText('Quedan días de atraso sin segmento: 1 a 2.');
    await expect(page.locator('[data-error-fila]:not([hidden])')).toHaveCount(0);
  });

  test('el error se va al volver a escribir', async ({ page }) => {
    await abrir(page, apiWhatsmkt());
    await page.getByLabel('Desde, segmento Tramo 2').fill('3');
    await guardar(page, 'Guardar segmentos').click();
    await expect(page.locator('[data-segmentos-error]')).not.toBeEmpty();

    await page.getByLabel('Desde, segmento Tramo 2').fill('1');

    await expect(page.locator('[data-segmentos-error]')).toBeEmpty();
  });

  test('un nombre vacío o un límite que no es un entero se dice en su fila, sin llamar a la API', async ({ page }) => {
    const api = apiWhatsmkt();
    await abrir(page, api);

    await page.getByLabel('Nombre del segmento Tramo 2').fill('   ');
    await guardar(page, 'Guardar segmentos').click();
    await expect(errorDeFila(page, 'tramo_2')).toHaveText('Escribe el nombre del segmento.');
    await expect(page.getByLabel('Nombre del segmento Tramo 2')).toBeFocused();

    await page.getByLabel('Nombre del segmento Tramo 2').fill('Tramo 2');
    await page.getByLabel('Desde, segmento Tramo 2').fill('1.5');
    await guardar(page, 'Guardar segmentos').click();
    await expect(errorDeFila(page, 'tramo_2')).toHaveText('Escribe un número entero de días.');

    await page.getByLabel('Desde, segmento Tramo 2').fill('9');
    await page.getByLabel('Hasta, segmento Tramo 2').fill('8');
    await guardar(page, 'Guardar segmentos').click();
    await expect(errorDeFila(page, 'tramo_2')).toHaveText('«Desde» no puede ser mayor que «Hasta».');

    expect(pedidosA(api, 'PUT', '/whatsmkt/segmentos')).toHaveLength(0);
  });

  test('en inglés el error de la superposición se traduce', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    await montarApiWhatsmkt(page, apiWhatsmkt());
    // The settings read the saved messages and the default definition; what a spec registers after this one answers first.
    await montarMensajesWhatsmkt(page, mensajesFalsos());
    await page.goto(RUTA);
    await expect(page.getByRole('heading', { name: 'WhatsMKT settings', level: 1 })).toBeVisible();

    await page.getByLabel('From, segment Tramo 2').fill('0');
    await page.getByRole('button', { name: 'Save segments' }).click();

    await expect(errorDeFila(page, 'tramo_2')).toHaveText('The day ranges overlap with Preventivo.');
    await expect(page.getByRole('columnheader', { name: 'Segment' })).toBeVisible();
  });
});

test.describe('horarios de envío', () => {
  test('guarda las dos franjas y manda solo los horarios', async ({ page }) => {
    const api = apiWhatsmkt();
    await abrir(page, api);

    await horaDe(page, 1, 'inicio').fill('09:00');
    await horaDe(page, 2, 'fin').fill('21:30');
    await guardar(page, 'Guardar horarios').click();

    await expect(page.locator('[data-horarios-estado]')).toHaveText('Guardado.');
    expect(pedidosA(api, 'PUT', '/whatsmkt/configuracion').at(-1)?.cuerpo).toEqual({
      horario_1: { inicio: '09:00', fin: '14:00' },
      horario_2: { inicio: '14:00', fin: '21:30' },
    });
  });

  test('una franja que termina antes de empezar se dice al salir del campo, bajo esa franja, y no se guarda', async ({ page }) => {
    const api = apiWhatsmkt();
    await abrir(page, api);

    await horaDe(page, 2, 'inicio').fill('20:00');
    await horaDe(page, 2, 'fin').fill('14:00');
    // The error is said on leaving the field.
    await horaDe(page, 2, 'fin').blur();

    const franja2 = page.locator('[data-franja="horario_2"]');
    await expect(franja2.locator('[data-franja-error]')).toHaveText(
      'Horario 2 termina antes de empezar: la hora de inicio tiene que ser anterior a la de fin.',
    );
    await expect(horaDe(page, 2, 'fin')).toHaveAttribute('aria-invalid', 'true');
    await expect(page.locator('[data-franja="horario_1"] [data-franja-error]')).toBeEmpty();

    await guardar(page, 'Guardar horarios').click();
    await expect(horaDe(page, 2, 'inicio')).toBeFocused();
    expect(pedidosA(api, 'PUT', '/whatsmkt/configuracion')).toHaveLength(0);

    // Writing it right takes the error away.
    await horaDe(page, 2, 'inicio').fill('15:00');
    await horaDe(page, 2, 'fin').fill('19:00');
    await expect(franja2.locator('[data-franja-error]')).toBeEmpty();
  });

  test('la misma hora de inicio y de fin tampoco vale', async ({ page }) => {
    await abrir(page, apiWhatsmkt());

    await horaDe(page, 1, 'fin').fill('08:00');
    await horaDe(page, 1, 'fin').blur();

    await expect(page.locator('[data-franja="horario_1"] [data-franja-error]')).toContainText('Horario 1 termina antes de empezar');
  });

  test('si la API rechaza una franja (horario_invalido), el error va bajo la franja que nombra', async ({ page }) => {
    const api = apiWhatsmkt();
    api.respuestas.guardarConfiguracion = [{ estado: 422, cuerpo: errorWhatsmkt('horario_invalido', { horarios: ['horario_2'] }) }];
    await abrir(page, api);

    await guardar(page, 'Guardar horarios').click();

    await expect(page.locator('[data-franja="horario_2"] [data-franja-error]')).toContainText('Horario 2 termina antes de empezar');
    await expect(page.locator('[data-franja="horario_1"] [data-franja-error]')).toBeEmpty();
    await expect(horaDe(page, 2, 'inicio')).toBeFocused();
  });
});

test.describe('nombre de la campaña', () => {
  test('muestra un ejemplo por segmento y el contador del nombre más largo', async ({ page }) => {
    await abrir(page, apiWhatsmkt());

    // One block with its own title; each segment is a term and its name the description (no label cut in the middle at 360 px).
    await expect(page.locator('[data-bloque-ejemplos] .wm-nombre__rotulo')).toHaveText('Nombres resultantes');
    const ejemplos = page.locator('[data-ejemplos] > div');
    await expect(ejemplos).toHaveCount(3);
    await expect(ejemplos.nth(0).locator('dt')).toHaveText('Preventivo');
    await expect(ejemplos.nth(0).locator('dd')).toHaveText('CUZCO_Vencida (Preventivo) whatsapp 2026.10.29');
    await expect(ejemplos.nth(2).locator('dt')).toHaveText('Tramos mayores al 2');
    await expect(ejemplos.nth(2).locator('dd')).toHaveText('CUZCO_Vencida (Tramos mayores al 2) whatsapp 2026.10.29');
    await expect(ejemplos.nth(0).locator('dd')).toHaveCSS('overflow-wrap', 'anywhere');
    // «CUZCO_Vencida (Tramos mayores al 2) whatsapp 2026.10.29» has 55 characters.
    await expect(page.locator('[data-contador]')).toHaveText('55 / 75');
  });

  test('las fichas de variables no llevan title: su pista está a la vista y enlazada al grupo', async ({ page }) => {
    await abrir(page, apiWhatsmkt());

    const grupo = page.getByRole('group', { name: 'Variables de la plantilla' });
    await expect(grupo.getByRole('button')).toHaveText(['{fecha_corte}', '{segmento}']);
    await expect(grupo.getByRole('button').first()).not.toHaveAttribute('title', /.*/);
    await expect(grupo.getByRole('button').nth(1)).not.toHaveAttribute('title', /.*/);
    // The braces are the variables' own, not parameters of the dictionary text.
    await expect(page.locator('#wm-variables-hint')).toHaveText(
      '{fecha_corte}: la fecha de corte, como AAAA.MM.DD. {segmento}: el nombre del segmento; queda vacío en una campaña global.',
    );
    await expect(grupo).toHaveAttribute('aria-describedby', 'wm-variables-hint');
  });

  test('las variables se insertan donde está el cursor', async ({ page }) => {
    await abrir(page, apiWhatsmkt());

    await plantilla(page).fill('Campaña ');
    await page.getByRole('button', { name: '{segmento}', exact: true }).click();
    await page.getByRole('button', { name: '{fecha_corte}', exact: true }).click();

    await expect(plantilla(page)).toHaveValue('Campaña {segmento}{fecha_corte}');
    await expect(plantilla(page)).toBeFocused();
    await expect(page.locator('[data-ejemplos] dd').first()).toContainText('Campaña Preventivo2026.10.29');
  });

  test('una variable que no existe se dice enseguida y no se guarda', async ({ page }) => {
    const api = apiWhatsmkt();
    await abrir(page, api);

    await plantilla(page).fill('Campaña {fecha}');

    await expect(page.locator('[data-plantilla-error]')).toHaveText('La variable {fecha} no existe. Usa las de la lista.');
    await expect(plantilla(page)).toHaveAttribute('aria-invalid', 'true');
    await guardar(page, 'Guardar nombre').click();
    await expect(plantilla(page)).toBeFocused();
    expect(pedidosA(api, 'PUT', '/whatsmkt/configuracion')).toHaveLength(0);
  });

  test('un nombre de más de 75 caracteres pone el contador en rojo y no se guarda', async ({ page }) => {
    const api = apiWhatsmkt();
    await abrir(page, api);

    // 64 fixed characters + «Tramos mayores al 2» (19) = 83.
    await plantilla(page).fill(`${'a'.repeat(64)}{segmento}`);

    await expect(page.locator('[data-contador]')).toHaveText('83 / 75');
    await expect(page.locator('[data-contador]')).toHaveAttribute('data-excede', 'true');
    await expect(page.locator('[data-plantilla-error]')).toHaveText('El nombre tiene 83 caracteres: el máximo es 75.');
    await guardar(page, 'Guardar nombre').click();
    expect(pedidosA(api, 'PUT', '/whatsmkt/configuracion')).toHaveLength(0);
  });

  test('guarda la plantilla y manda solo ella', async ({ page }) => {
    const api = apiWhatsmkt();
    await abrir(page, api);

    await plantilla(page).fill('Prueba {segmento}');
    await guardar(page, 'Guardar nombre').click();

    await expect(page.locator('[data-nombre-estado]')).toHaveText('Guardado.');
    expect(pedidosA(api, 'PUT', '/whatsmkt/configuracion').at(-1)?.cuerpo).toEqual({ plantilla_nombre: 'Prueba {segmento}' });
  });

  test('si la API rechaza una variable (variable_inexistente), el error va bajo la plantilla con la variable', async ({ page }) => {
    const api = apiWhatsmkt();
    api.respuestas.guardarConfiguracion = [{ estado: 422, cuerpo: errorWhatsmkt('variable_inexistente', { variable: '{x' }) }];
    await abrir(page, api);

    await guardar(page, 'Guardar nombre').click();

    await expect(page.locator('[data-plantilla-error]')).toHaveText('La variable {x no existe. Usa las de la lista.');
    await expect(plantilla(page)).toBeFocused();
  });
});

test.describe('topes', () => {
  test('cada campo exige al menos 1', async ({ page }) => {
    await abrir(page, apiWhatsmkt());

    for (const campo of ['mensaje', 'video', 'audio', 'pdf'] as const) await expect(topeDe(page, campo)).toHaveAttribute('min', '1');
  });

  test('guarda los megabytes en bytes (1 MB = 1 000 000) y los vuelve a mostrar en megabytes', async ({ page }) => {
    const api = apiWhatsmkt();
    await abrir(page, api);

    await topeDe(page, 'mensaje').fill('2000');
    await topeDe(page, 'video').fill('20');
    await topeDe(page, 'audio').fill('1.5');
    await topeDe(page, 'pdf').fill('2');
    await guardar(page, 'Guardar topes').click();

    await expect(page.locator('[data-topes-estado]')).toHaveText('Guardado.');
    expect(pedidosA(api, 'PUT', '/whatsmkt/configuracion').at(-1)?.cuerpo).toEqual({
      tope_mensaje: 2000,
      tope_video: 20_000_000,
      tope_audio: 1_500_000,
      tope_pdf: 2_000_000,
    });
    await expect(topeDe(page, 'video')).toHaveValue('20');
    await expect(topeDe(page, 'audio')).toHaveValue('1.5');
  });

  test('un tope de cero, de menos de 1 MB o vacío se dice en su campo y no llega a la API', async ({ page }) => {
    const api = apiWhatsmkt();
    await abrir(page, api);

    // The field says so on leaving it (`change`), which a typed value fires on blur.
    await topeDe(page, 'mensaje').fill('0');
    await topeDe(page, 'mensaje').blur();
    // The message's limit does not show the API's technical ceiling.
    await expect(page.locator('[data-tope-error="tope_mensaje"]')).toHaveText('Escribe un número entero de 1 en adelante.');
    await expect(topeDe(page, 'mensaje')).toHaveAttribute('aria-invalid', 'true');

    await topeDe(page, 'video').fill('0.5');
    await topeDe(page, 'video').blur();
    await expect(page.locator('[data-tope-error="tope_video"]')).toContainText('Escribe un número entre 1 y');

    await topeDe(page, 'pdf').fill('');
    await guardar(page, 'Guardar topes').click();

    await expect(topeDe(page, 'mensaje')).toBeFocused();
    await expect(page.locator('[data-tope-error="tope_pdf"]')).toContainText('Escribe un número entre 1 y');
    expect(pedidosA(api, 'PUT', '/whatsmkt/configuracion')).toHaveLength(0);

    await topeDe(page, 'mensaje').fill('4096');
    await topeDe(page, 'mensaje').blur();
    await expect(page.locator('[data-tope-error="tope_mensaje"]')).toBeEmpty();
  });
});

test.describe('salir de un campo inválido directo a Guardar', () => {
  // Validating on leaving a field must not move the button as it is pressed: one click has to be enough, and the
  // click itself validates the whole block and puts the focus on the first error.
  test('topes: un solo clic basta, dice el error y enfoca el campo', async ({ page }) => {
    const api = apiWhatsmkt();
    await abrir(page, api);

    await topeDe(page, 'pdf').fill('');
    await guardar(page, 'Guardar topes').click();

    await expect(page.locator('[data-tope-error="tope_pdf"]')).toContainText('Escribe un número entre 1 y');
    await expect(topeDe(page, 'pdf')).toBeFocused();
    expect(pedidosA(api, 'PUT', '/whatsmkt/configuracion')).toHaveLength(0);
  });

  test('horarios: un solo clic basta, dice el error bajo la franja y enfoca su inicio', async ({ page }) => {
    const api = apiWhatsmkt();
    await abrir(page, api);

    await horaDe(page, 1, 'fin').fill('08:00');
    await guardar(page, 'Guardar horarios').click();

    await expect(page.locator('[data-franja="horario_1"] [data-franja-error]')).toContainText('Horario 1 termina antes de empezar');
    await expect(horaDe(page, 1, 'inicio')).toBeFocused();
    expect(pedidosA(api, 'PUT', '/whatsmkt/configuracion')).toHaveLength(0);
  });

  test('segmentos: un solo clic basta, dice el error en la fila y enfoca el campo', async ({ page }) => {
    const api = apiWhatsmkt();
    await abrir(page, api);

    await page.getByLabel('Desde, segmento Tramo 2').fill('1.5');
    await guardar(page, 'Guardar segmentos').click();

    await expect(errorDeFila(page, 'tramo_2')).toHaveText('Escribe un número entero de días.');
    await expect(page.getByLabel('Desde, segmento Tramo 2')).toBeFocused();
    expect(pedidosA(api, 'PUT', '/whatsmkt/segmentos')).toHaveLength(0);
  });

  test('la fecha de actualización del panel de horarios sale pequeña, no en tamaño de título', async ({ page }) => {
    await abrir(page, apiWhatsmkt());

    const tamano = await page.locator('[data-horarios-meta]').evaluate((nodo) => parseFloat(getComputedStyle(nodo).fontSize));

    expect(tamano).toBeLessThan(12);
  });
});

test.describe('cada panel se guarda por separado', () => {
  test('un guardado que falla no toca lo escrito en otro panel', async ({ page }) => {
    const api = apiWhatsmkt();
    api.respuestas.guardarConfiguracion = [{ estado: 500, cuerpo: { detail: 'La base no respondió' } }];
    await abrir(page, api);

    await topeDe(page, 'video').fill('30');
    await page.getByLabel('Nombre del segmento Tramo 2').fill('Tramo medio');
    await guardar(page, 'Guardar horarios').click();

    await expect(page.locator('[data-horarios-error]')).toHaveText('La base no respondió');
    await expect(topeDe(page, 'video')).toHaveValue('30');
    await expect(page.getByLabel('Nombre del segmento Tramo 2').first()).toHaveValue('Tramo medio');
    // And the failed panel kept its own fields, ready to try again.
    await expect(horaDe(page, 1, 'inicio')).toHaveValue('08:00');
  });
});

test.describe('a 360 px', () => {
  test('la página no desborda y la tabla de segmentos se apila', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    await abrir(page, apiWhatsmkt());

    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
    // Stacked: each row's cells sit one under the other, so «Desde» is below the name, not beside it.
    const nombre = (await page.getByLabel('Nombre del segmento Tramo 2').boundingBox())!;
    const desde = (await page.getByLabel('Desde, segmento Tramo 2').boundingBox())!;
    expect(desde.y).toBeGreaterThan(nombre.y + nombre.height - 1);
    // Every field stays inside the viewport.
    for (const caja of [nombre, desde]) expect(caja.x + caja.width).toBeLessThanOrEqual(360);
  });
});

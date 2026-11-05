/**
 * The messages of the WhatsMKT settings (T-WM-F1b2), end to end against an intercepted API: the two panels of saved texts over the
 * context `whatsmkt.mensaje`, the segment that owns a message, and the editor of §5.1 (macros, counter, emoji and macro errors, preview).
 * The clock is fixed from the first spec, in `montarApiWhatsmkt`. Every text and number is invented.
 */
import { expect, test, type Page } from '@playwright/test';

import { apiWhatsmkt, montarApiWhatsmkt, type ApiFalsaWhatsmkt } from './api-falsa-whatsmkt';
import { mensajesFalsos, montarMensajesWhatsmkt, respuestaDeRegla, type MensajesFalsos } from './api-falsa-whatsmkt-mensajes';

const RUTA = '/whatsmkt/configuracion';

/** The default definition is chosen and the first two segments own their message, as the seed leaves them. */
function apiConfigurada(): ApiFalsaWhatsmkt {
  const api = apiWhatsmkt();
  api.configuracion.definicion_defecto_id = 11;
  api.segmentos[0].texto_guardado_id = 101;
  api.segmentos[1].texto_guardado_id = 102;
  return api;
}

async function abrir(
  page: Page,
  api: ApiFalsaWhatsmkt = apiConfigurada(),
  mensajes: MensajesFalsos = mensajesFalsos(),
): Promise<{ api: ApiFalsaWhatsmkt; mensajes: MensajesFalsos }> {
  await montarApiWhatsmkt(page, api);
  await montarMensajesWhatsmkt(page, mensajes);
  await page.goto(RUTA);
  await expect(page.getByLabel('Nombre del segmento Preventivo')).toBeVisible();
  await expect(segmentos(page)).toHaveAttribute('data-montado', 'true');
  await expect(globales(page)).toHaveAttribute('data-montado', 'true');
  // The panel opens the first text and then the segment's own: what is typed before that would be overwritten.
  await expect(area(page)).toHaveValue(/tu cuota vence el/);
  return { api, mensajes };
}

const segmentos = (page: Page) => page.locator('#wm-mensajes-segmento');
const globales = (page: Page) => page.locator('#wm-globales');
const botonesDeSegmento = (page: Page) => page.locator('[data-segmentos-mensaje] button');
const vinculo = (page: Page) => page.locator('[data-vinculo-texto]');
const selectDe = (raiz: ReturnType<typeof segmentos>) => raiz.locator('[data-textos-select]');
const area = (page: Page) => page.locator('#wm-msg-segmento-texto');
const contador = (page: Page) => page.locator('#wm-msg-segmento-contador');
const etiquetaTope = (page: Page) => page.locator('#wm-msg-segmento-contador + .tag');
const errorDelEditor = (page: Page) => page.locator('#wm-msg-segmento-error');
const lineasDeError = (page: Page) => errorDelEditor(page).locator('p');
const vista = (page: Page) => segmentos(page).locator('.wm-vista__texto');
const pedidosA = (api: ApiFalsaWhatsmkt, metodo: string, ruta: string) =>
  api.pedidos.filter((p) => p.metodo === metodo && p.ruta.split('?')[0] === ruta);
const macroEn = (page: Page, nombre: string | RegExp) => segmentos(page).locator('.wm-editor__barra').getByRole('button', { name: nombre });

/** The options of a select, in order, as text. */
const opciones = (select: ReturnType<typeof selectDe>) => select.locator('option').allTextContents();

test.describe('los dos paneles', () => {
  test('el panel 1 trae un botón por segmento, y el del segmento elegido abre su mensaje', async ({ page }) => {
    await abrir(page);

    await expect(botonesDeSegmento(page)).toHaveText(['Preventivo', 'Tramo 2', 'Tramos mayores al 2']);
    await expect(botonesDeSegmento(page).nth(0)).toHaveAttribute('aria-pressed', 'true');
    await expect(selectDe(segmentos(page))).toHaveValue('101');
    await expect(area(page)).toHaveValue(/^Hola \[\$MACRO1\$\], tu cuota vence el \[\$MACRO2\$\]\./);
    await expect(vinculo(page)).toHaveText('Mensaje de Preventivo: «Preventivo inicial»');

    await botonesDeSegmento(page).nth(1).click();

    await expect(botonesDeSegmento(page).nth(1)).toHaveAttribute('aria-pressed', 'true');
    await expect(botonesDeSegmento(page).nth(0)).toHaveAttribute('aria-pressed', 'false');
    await expect(selectDe(segmentos(page))).toHaveValue('102');
    // The text of the segment is its latest version.
    await expect(area(page)).toHaveValue('Hola [$MACRO1$], ponte al día. INFO por [whatsapp]');
    await expect(vinculo(page)).toHaveText('Mensaje de Tramo 2: «Tramo 2 inicial»');
  });

  test('un segmento sin mensaje lo dice y deja lo que había en pantalla', async ({ page }) => {
    await abrir(page);

    await botonesDeSegmento(page).nth(2).click();

    await expect(vinculo(page)).toHaveText('Tramos mayores al 2 no tiene un mensaje elegido.');
    await expect(selectDe(segmentos(page))).toHaveValue('101');
  });

  test('el panel 1 ofrece todos los mensajes, con el segmento de los que son de uno; el panel 2 solo los globales', async ({ page }) => {
    await abrir(page);

    expect((await opciones(selectDe(segmentos(page)))).sort()).toEqual(
      ['Aviso de pago', 'Oferta de octubre', 'Preventivo inicial · Preventivo', 'Tramo 2 inicial · Tramo 2'].sort(),
    );
    expect((await opciones(selectDe(globales(page)))).sort()).toEqual(['Aviso de pago', 'Oferta de octubre']);
    await expect(globales(page).getByRole('heading', { name: 'Mensajes globales', level: 2 })).toBeVisible();
    await expect(globales(page)).toContainText('Para las campañas especiales, con un solo mensaje para toda la selección.');
  });

  test('«Usar como mensaje de …» vincula el texto elegido al segmento, solo cambia ese vínculo y el texto deja de ser global', async ({ page }) => {
    const { api } = await abrir(page);
    await botonesDeSegmento(page).nth(2).click();
    const usar = page.getByRole('button', { name: 'Usar como mensaje de Tramos mayores al 2' });
    // The text on screen is the one of Preventivo: it is not this segment's, but it already belongs to another and can be moved.
    await selectDe(segmentos(page)).selectOption({ label: 'Oferta de octubre' });
    await expect(usar).toBeEnabled();

    await usar.click();

    await expect(vinculo(page)).toHaveText('«Oferta de octubre» es ahora el mensaje de Tramos mayores al 2.');
    expect(pedidosA(api, 'PUT', '/whatsmkt/segmentos').at(-1)?.cuerpo).toEqual([
      { clave: 'preventivo', etiqueta: 'Preventivo', desde: null, hasta: 0 },
      { clave: 'tramo_2', etiqueta: 'Tramo 2', desde: 1, hasta: 8 },
      { clave: 'mayores_2', etiqueta: 'Tramos mayores al 2', desde: 9, hasta: null, texto_guardado_id: 103 },
    ]);
    // Without asking the lists again, the label of the option and the list of the global ones follow.
    expect(await opciones(selectDe(segmentos(page)))).toContain('Oferta de octubre · Tramos mayores al 2');
    expect(await opciones(selectDe(globales(page)))).toEqual(['Aviso de pago']);
    await expect(usar).toBeHidden();
  });

  test('con el texto que ya es el mensaje del segmento, «Usar como mensaje de …» no aparece', async ({ page }) => {
    await abrir(page);

    await expect(page.getByRole('button', { name: 'Usar como mensaje de Preventivo' })).toBeHidden();
    await selectDe(segmentos(page)).selectOption({ label: 'Aviso de pago' });
    await expect(page.getByRole('button', { name: 'Usar como mensaje de Preventivo' })).toBeVisible();
  });

  test('un mensaje que se crea en un panel aparece en el otro, sin recargar la página', async ({ page }) => {
    await abrir(page);
    await page.getByRole('button', { name: 'Nuevo' }).nth(1).click();
    await page.locator('#wm-globales').getByLabel('Nombre', { exact: true }).fill('Promoción de fin de mes');
    await page.locator('#wm-msg-global-texto').fill('Hola [$MACRO1$], aprovecha la promoción.');

    await globales(page).locator('[data-textos-guardar]').click();

    await expect(globales(page).locator('[data-textos-anuncio]')).toContainText('Promoción de fin de mes');
    await expect.poll(async () => await opciones(selectDe(segmentos(page)))).toContain('Promoción de fin de mes');
  });
});

test.describe('el editor del mensaje', () => {
  test('la barra trae una macro por columna de la definición por defecto, con su etiqueta, y el enlace de WhatsApp', async ({ page }) => {
    await abrir(page);

    await expect(macroEn(page, 'MACRO1 · Nombres del titular')).toBeVisible();
    // A column with no label is only its number.
    await expect(macroEn(page, 'MACRO2')).toBeVisible();
    await expect(macroEn(page, 'Enlace de WhatsApp')).toBeVisible();
    await expect(segmentos(page).getByRole('group', { name: 'Insertar macro' })).toBeVisible();
  });

  test('un botón inserta su marcador donde está el cursor y devuelve el foco al campo', async ({ page }) => {
    await abrir(page);
    await macroEn(page, 'MACRO1 · Nombres del titular').waitFor();
    await area(page).fill('Hola , bienvenido');
    await area(page).evaluate((campo: HTMLTextAreaElement) => campo.setSelectionRange(5, 5));

    await macroEn(page, 'MACRO1 · Nombres del titular').click();

    await expect(area(page)).toHaveValue('Hola [$MACRO1$], bienvenido');
    await expect(area(page)).toBeFocused();

    await macroEn(page, 'Enlace de WhatsApp').click();
    await expect(area(page)).toHaveValue(/\[whatsapp\]/);
    await expect(area(page)).toBeFocused();
  });

  test('el contador cuenta [whatsapp] como el enlace de 26 caracteres, con las macros como están escritas', async ({ page }) => {
    await abrir(page);

    await area(page).fill('INFO por [whatsapp]');
    await expect(contador(page)).toHaveText('35 / 4096 caracteres');
    await expect(contador(page)).toHaveAttribute('data-excede', 'false');

    await area(page).fill('[$MACRO1$]');
    await expect(contador(page)).toHaveText('10 / 4096 caracteres');
  });

  test('al pasar el tope el contador se marca y se anuncia una sola vez, no en cada tecla', async ({ page }) => {
    const api = apiConfigurada();
    api.configuracion.tope_mensaje = 30;
    await abrir(page, api);
    const anuncio = segmentos(page).locator('.wm-editor .visually-hidden[role="status"]');

    // The seeded text already opens over the limit (82): that is no crossing, and nothing is announced.
    await expect(contador(page)).toHaveAttribute('data-excede', 'true');
    await expect(anuncio).toBeEmpty();
    await area(page).fill('corto');
    await expect(contador(page)).toHaveAttribute('data-excede', 'false');

    await area(page).fill('INFO por [whatsapp]');

    await expect(contador(page)).toHaveText('35 / 30 caracteres');
    await expect(contador(page)).toHaveAttribute('data-excede', 'true');
    // Over the limit the counter's tag says so, as in the common editor; and there is no «Cerca del tope» here.
    await expect(etiquetaTope(page)).toBeVisible();
    await expect(etiquetaTope(page)).toHaveText('Pasa el tope');
    await expect(etiquetaTope(page)).toHaveClass(/tag--error/);
    await expect(anuncio).toHaveText('El mensaje pasó el tope: 35 / 30 caracteres.');
    await area(page).pressSequentially(' x');
    await expect(contador(page)).toHaveText('37 / 30 caracteres');
    // Still over: nothing new is said.
    await expect(anuncio).toHaveText('El mensaje pasó el tope: 35 / 30 caracteres.');

    await area(page).fill('corto');
    await expect(anuncio).toBeEmpty();
    await expect(contador(page)).toHaveAttribute('data-excede', 'false');
    await expect(etiquetaTope(page)).toBeHidden();
  });

  test('el contador de WhatsMKT no tiene «Cerca del tope»: ni cerca del tope ni a mitad hay otro tag que «Pasa el tope»', async ({ page }) => {
    const api = apiConfigurada();
    api.configuracion.tope_mensaje = 100;
    await abrir(page, api);
    // 99 / 100: lo más cerca que se puede estar sin pasarlo.
    await area(page).fill('x'.repeat(99));
    await expect(contador(page)).toHaveText('99 / 100 caracteres');
    await expect(segmentos(page).locator('.wm-contador-fila .tag:visible')).toHaveCount(0);
    await expect(segmentos(page).locator('.tag--advertencia')).toHaveCount(0);
  });

  test('un tope guardado en el panel de Topes lo toma el contador sin recargar', async ({ page }) => {
    await abrir(page);
    await area(page).fill('Hola');
    await expect(contador(page)).toHaveText('4 / 4096 caracteres');

    await page.locator('#wm-tope-mensaje').fill('2000');
    await page.locator('#wm-tope-mensaje').blur();
    await page.getByRole('button', { name: 'Guardar topes' }).click();

    await expect(contador(page)).toHaveText('4 / 2000 caracteres');
  });

  test('al salir del campo, el emoji se dice con su posición, y al enfocar el error el cursor queda sobre él', async ({ page }) => {
    await abrir(page);

    // «Hola » are 5 characters: the emoji is the 6th, and takes two UTF-16 units.
    await area(page).fill('Hola 😀 y más');
    await expect(errorDelEditor(page)).toBeEmpty();
    await page.locator('#wm-whatsapp').focus();

    await expect(lineasDeError(page)).toHaveText(['No se admiten emojis: el primero es «😀», en la posición 6.']);
    await expect(area(page)).toHaveAttribute('aria-invalid', 'true');

    await errorDelEditor(page).locator('[data-emoji]').focus();

    await expect(area(page)).toBeFocused();
    const seleccion = await area(page).evaluate((campo: HTMLTextAreaElement) => [campo.selectionStart, campo.selectionEnd]);
    expect(seleccion).toEqual([5, 7]);

    await area(page).fill('Hola y más');
    await expect(errorDelEditor(page)).toBeEmpty();
  });

  test('una macro que la definición no tiene se dice al salir del campo, con cuántas tiene', async ({ page }) => {
    await abrir(page);
    await macroEn(page, 'MACRO2').waitFor();

    await area(page).fill('Hola [$MACRO1$] y [$MACRO4$]');
    await page.locator('#wm-whatsapp').focus();

    await expect(lineasDeError(page)).toHaveText(['[$MACRO4$] no existe en la definición elegida: tiene 2 macros.']);
  });

  test('todos los problemas van bajo el campo y en orden: la macro, el emoji y el largo; el contador rojo no reemplaza al largo', async ({ page }) => {
    const api = apiConfigurada();
    api.configuracion.tope_mensaje = 40;
    await abrir(page, api);
    await macroEn(page, 'MACRO2').waitFor();

    await area(page).fill('Hola 😀 [$MACRO4$], INFO por [whatsapp] y algo más');
    await page.locator('#wm-whatsapp').focus();

    await expect(lineasDeError(page)).toHaveText([
      '[$MACRO4$] no existe en la definición elegida: tiene 2 macros.',
      'No se admiten emojis: el primero es «😀», en la posición 6.',
      'El mensaje tiene 65 caracteres: el máximo es 40.',
    ]);
    await expect(contador(page)).toHaveAttribute('data-excede', 'true');
    await expect(area(page)).toHaveAttribute('aria-invalid', 'true');

    await area(page).fill('Hola');
    await expect(errorDelEditor(page)).toBeEmpty();
  });

  test('yendo a «Guardar» no aparece el error que movería el botón: lo dice la respuesta del guardado, con lo escrito intacto', async ({ page }) => {
    const mensajes = mensajesFalsos();
    mensajes.textos.respuestas.versionar.push(
      respuestaDeRegla('mensaje_con_emoji', { caracter: '😀', posicion: 6 }, 'No se admiten emojis: el primero es «😀», en la posición 6'),
    );
    await abrir(page, apiConfigurada(), mensajes);
    await area(page).fill('Hola 😀 y más');

    await segmentos(page).locator('[data-textos-guardar]').click();

    await expect(errorDelEditor(page)).toBeEmpty();
    await expect(segmentos(page).locator('[data-textos-problemas]')).toContainText('No se admiten emojis: el primero es «😀», en la posición 6.');
    await expect(area(page)).toHaveValue('Hola 😀 y más');
  });

  test('sin definición por defecto no hay macros: lo dice y deja el enlace de WhatsApp', async ({ page }) => {
    const api = apiConfigurada();
    api.configuracion.definicion_defecto_id = null;
    await abrir(page, api);

    await expect(segmentos(page).locator('.wm-editor__aviso')).toHaveText(
      'No hay una definición por defecto. Elige una más abajo, en Definición por defecto, para insertar macros.',
    );
    await expect(segmentos(page).locator('.wm-editor__barra').getByRole('button', { name: /MACRO/ })).toHaveCount(0);
    await expect(macroEn(page, 'Enlace de WhatsApp')).toBeVisible();
  });
});

test.describe('a 360 px', () => {
  test('los segmentos se desplazan de lado dentro de su caja, sin partir sus nombres, y el abierto queda a la vista', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    await abrir(page);
    const caja = page.locator('[data-segmentos-mensaje]');
    const ultimo = botonesDeSegmento(page).nth(2);

    await expect(caja).toHaveCSS('overflow-x', 'auto');
    await expect(ultimo).toHaveCSS('white-space', 'nowrap');
    // A name that fits on one line is not split: every button is as tall as the first.
    const alturas = await botonesDeSegmento(page).evaluateAll((botones) => botones.map((boton) => boton.getBoundingClientRect().height));
    expect(new Set(alturas.map(Math.round)).size).toBe(1);

    await ultimo.click();

    const cajaYBoton = await page.evaluate(() => {
      const c = document.querySelector('[data-segmentos-mensaje]')!.getBoundingClientRect();
      const b = document.querySelectorAll('[data-segmentos-mensaje] button')[2].getBoundingClientRect();
      return { desdeCaja: c.left, hastaCaja: c.right, desdeBoton: b.left, hastaBoton: b.right };
    });
    expect(cajaYBoton.desdeBoton).toBeGreaterThanOrEqual(cajaYBoton.desdeCaja - 1);
    expect(cajaYBoton.hastaBoton).toBeLessThanOrEqual(cajaYBoton.hastaCaja + 1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360);
  });
});

test.describe('la vista previa', () => {
  test('reemplaza las macros con la fila de ejemplo y, sin WhatsApp configurado, pone su aviso apagado', async ({ page }) => {
    await abrir(page);
    await expect(segmentos(page).locator('.wm-vista h3')).toHaveText('Así lo verá el cliente');

    await expect(vista(page)).toHaveText('Hola Maria Perez, tu cuota vence el 05/10/2026. INFO por (sin WhatsApp configurado)');
    await expect(vista(page).locator('.muted')).toHaveText('(sin WhatsApp configurado)');
  });

  test('con el WhatsApp configurado, [whatsapp] sale como el enlace', async ({ page }) => {
    const api = apiConfigurada();
    api.configuracion.whatsapp_contacto = '900000123';
    await abrir(page, api);

    await expect(vista(page)).toHaveText('Hola Maria Perez, tu cuota vence el 05/10/2026. INFO por https://wa.me/+51900000123');
    await expect(vista(page).locator('.muted')).toHaveCount(0);
  });

  test('«Fila de ejemplo» elige entre tres filas', async ({ page }) => {
    const { mensajes } = await abrir(page);
    const fila = segmentos(page).getByLabel('Fila de ejemplo');
    await expect(fila.locator('option')).toHaveText(['1', '2', '3']);

    // By label: a bare «1» would match the value of the second option before the label of the first.
    await fila.selectOption({ label: '2' });

    await expect(vista(page)).toContainText('Hola Jose Rojas, tu cuota vence el 12/10/2026.');
    // It asked the preview of the definition once, with the columns of the definition and the example rows of the engine.
    expect(mensajes.previas).toHaveLength(1);
    expect(mensajes.previas[0]).toMatchObject({ contexto: 'cartera', muestra: { tipo: 'ejemplos_por_segmento' } });
  });

  test('si la muestra no se puede armar, la vista previa lo dice y el editor sigue funcionando', async ({ page }) => {
    const mensajes = mensajesFalsos();
    mensajes.filas = null;
    await abrir(page, apiConfigurada(), mensajes);

    await expect(segmentos(page).locator('.wm-vista .field__hint')).toHaveText('No hay filas de ejemplo para la vista previa.');
    await expect(segmentos(page).getByLabel('Fila de ejemplo')).toBeHidden();
    await area(page).fill('Hola [$MACRO1$]');
    await expect(vista(page)).toHaveText('Hola [$MACRO1$]');
    await expect(macroEn(page, 'MACRO1 · Nombres del titular')).toBeVisible();
  });
});

test.describe('en inglés', () => {
  test('el editor y los paneles se traducen', async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' })));
    await montarApiWhatsmkt(page, apiConfigurada());
    await montarMensajesWhatsmkt(page, mensajesFalsos());
    await page.goto(RUTA);
    await expect(segmentos(page)).toHaveAttribute('data-montado', 'true');

    await expect(macroEn(page, 'MACRO1 · Nombres del titular')).toBeVisible();
    await expect(macroEn(page, 'WhatsApp link')).toBeVisible();
    await expect(area(page)).toHaveValue(/tu cuota vence el/);
    await area(page).fill('INFO por [whatsapp]');
    await expect(contador(page)).toHaveText('35 / 4096 characters');
    await expect(segmentos(page).locator('.wm-vista h3')).toHaveText('This is how the customer will see it');
    await expect(vista(page)).toContainText('(no WhatsApp set up)');
    await expect(vinculo(page)).toHaveText('Message for Preventivo: “Preventivo inicial”');
  });
});

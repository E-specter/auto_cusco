/**
 * The messages of the WhatsMKT settings (T-WM-F1b2), end to end against an intercepted API: the two panels of saved texts over the
 * context `whatsmkt.mensaje`, the segment that owns a message, and the editor of §5.1 (macros, counter, emoji and macro errors, preview).
 * The clock is fixed from the first spec, in `montarApiWhatsmkt`. Every text and number is invented.
 */
import { expect, test, type Page } from '@playwright/test';

import { apiWhatsmkt, montarApiWhatsmkt, type ApiFalsaWhatsmkt } from './api-falsa-whatsmkt';
import { mensajeFalso, mensajesFalsos, montarMensajesWhatsmkt, respuestaDeRegla, type MensajesFalsos } from './api-falsa-whatsmkt-mensajes';

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
  await montarMensajesWhatsmkt(page, mensajes, api);
  await page.goto(RUTA);
  await expect(page.getByLabel('Nombre del segmento Preventivo')).toBeVisible();
  await expect(segmentos(page)).toHaveAttribute('data-montado', 'true');
  await expect(globales(page)).toHaveAttribute('data-montado', 'true');
  // The panel opens the first text and then the segment's own: what is typed before that would be overwritten.
  await expect(tramo(page, 2)).toHaveValue(/tu cuota vence el/);
  return { api, mensajes };
}

const segmentos = (page: Page) => page.locator('#wm-mensajes-segmento');
const globales = (page: Page) => page.locator('#wm-globales');
const botonesDeSegmento = (page: Page) => page.locator('[data-segmentos-mensaje] button');
const vinculo = (page: Page) => page.locator('[data-vinculo-texto]');
const selectDe = (raiz: ReturnType<typeof segmentos>) => raiz.locator('[data-textos-select]');
// The common editor of the first panel: its text runs (textareas, by the position of their piece), its pills, its counter and its search.
const editor = (page: Page) => page.locator('#wm-msg-segmento-editor');
const tramo = (page: Page, indice = 0) => editor(page).locator(`[data-tramo="${indice}"]`);
const pildora = (page: Page, nombre: RegExp) => editor(page).locator('[data-linea]').getByRole('button', { name: nombre });
const buscador = (page: Page) => editor(page).getByRole('listbox', { name: 'Elegir una variable' });
const contador = (page: Page) => editor(page).locator('[data-largo-texto]');
const etiquetaTope = (page: Page) => editor(page).locator('[data-largo-nivel]');
// What this page puts around the editor: the summary of every problem above it and, under it, the rules the editor does not know.
const resumenDelMensaje = (page: Page) => segmentos(page).locator('[data-textos-editor] > .editor-texto__resumen');
const errorDelEmoji = (page: Page) => editor(page).locator('[data-error-tramo] + .field__error');
const vista = (page: Page) => segmentos(page).locator('.wm-vista__texto');
const pedidosA = (api: ApiFalsaWhatsmkt, metodo: string, ruta: string) =>
  api.pedidos.filter((p) => p.metodo === metodo && p.ruta.split('?')[0] === ruta);

/** The options of a select, in order, as text. */
const opciones = (select: ReturnType<typeof selectDe>) => select.locator('option').allTextContents();

test.describe('los dos paneles', () => {
  test('el panel 1 trae un botón por segmento, y el del segmento elegido abre su mensaje', async ({ page }) => {
    await abrir(page);

    await expect(botonesDeSegmento(page)).toHaveText(['Preventivo', 'Tramo 2', 'Tramos mayores al 2']);
    await expect(botonesDeSegmento(page).nth(0)).toHaveAttribute('aria-pressed', 'true');
    await expect(selectDe(segmentos(page))).toHaveValue('101');
    await expect(tramo(page, 0)).toHaveValue('Hola ');
    await expect(tramo(page, 2)).toHaveValue(', tu cuota vence el ');
    await expect(vinculo(page)).toHaveText('Mensaje de Preventivo: «Preventivo inicial»');

    await botonesDeSegmento(page).nth(1).click();

    await expect(botonesDeSegmento(page).nth(1)).toHaveAttribute('aria-pressed', 'true');
    await expect(botonesDeSegmento(page).nth(0)).toHaveAttribute('aria-pressed', 'false');
    await expect(selectDe(segmentos(page))).toHaveValue('102');
    // The text of the segment is its latest version.
    await expect(tramo(page, 0)).toHaveValue('Hola ');
    await expect(tramo(page, 2)).toHaveValue(', ponte al día. INFO por ');
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
    await page.locator('#wm-msg-global-editor [data-tramo="0"]').fill('Hola , aprovecha la promoción.');

    await globales(page).locator('[data-textos-guardar]').click();

    await expect(globales(page).locator('[data-textos-anuncio]')).toContainText('Promoción de fin de mes');
    await expect.poll(async () => await opciones(selectDe(segmentos(page)))).toContain('Promoción de fin de mes');
  });
});

test.describe('el editor del mensaje (el editor común, T-WM-F4)', () => {
  test('es el editor común en el contexto del mensaje: las macros y el enlace son píldoras, y un texto guardado se abre igual', async ({ page }) => {
    const { mensajes } = await abrir(page);

    await expect(pildora(page, /MACRO1 · Nombres del titular/)).toBeVisible();
    await expect(pildora(page, /MACRO2/).first()).toBeVisible();
    await expect(pildora(page, /Enlace de WhatsApp/)).toBeVisible();
    // The text saved before the editor was this one opens as it was: text, pill, text, pill, text, pill.
    await expect(tramo(page, 0)).toHaveValue('Hola ');
    await expect(tramo(page, 2)).toHaveValue(', tu cuota vence el ');
    await expect(tramo(page, 4)).toHaveValue('. INFO por ');
    // It asked the engine for the context of the message, and nothing opening the text is an unsaved change.
    expect(mensajes.editor.map((p) => p.ruta)).toContain('/texto-enriquecido/catalogo?contexto=whatsmkt.mensaje');
    await expect(segmentos(page).locator('[data-textos-guardar]')).toBeDisabled();
  });

  test('sin funciones: el panel de una píldora dice dónde se arman y lleva a Columnas de carga, que vuelve a la configuración', async ({ page }) => {
    await abrir(page);

    await pildora(page, /MACRO1 · Nombres del titular/).click();

    const panel = editor(page).locator('[data-sin-funciones]');
    await expect(panel).toContainText('En WhatsMKT las funciones van en la columna, en Columnas de carga.');
    await expect(panel.getByRole('link', { name: 'Editar en Columnas de carga' })).toHaveAttribute('href', '/columnas?definicion=11&volver=%2Fwhatsmkt%2Fconfiguracion');
    await expect(editor(page).getByRole('button', { name: 'Agregar función', exact: true })).toHaveCount(0);
  });

  test('el buscador ofrece solo las macros de la definición por defecto, con su etiqueta, y el enlace de WhatsApp', async ({ page }) => {
    await abrir(page);
    await tramo(page, 6).click();

    await page.keyboard.type('[@');

    await expect(buscador(page).getByRole('option')).toHaveCount(3);
    // The macros are the columns of the file: they go under «Columnas del archivo», first, and the link of WhatsApp after them.
    await expect(buscador(page).locator('.selector-variable__tema')).toHaveText(['Columnas del archivo', 'Persona y contacto']);
    const nombres = await buscador(page).getByRole('option').allTextContents();
    expect(nombres[0]).toContain('MACRO1 · Nombres del titular');
    expect(nombres[1]).toContain('MACRO2');
    expect(nombres[1]).not.toContain('·');
    expect(nombres[2]).toContain('Enlace de WhatsApp');
  });

  test('una macro insertada se guarda como [$MACROn$] y [whatsapp] como el marcador literal, y el resto del texto no cambia', async ({ page }) => {
    const { mensajes } = await abrir(page);
    await tramo(page, 6).click();

    await page.keyboard.type(' Más [@MACRO1');
    await page.keyboard.press('Enter');
    await expect(segmentos(page).locator('[data-textos-guardar]')).toBeEnabled();
    await segmentos(page).locator('[data-textos-guardar]').click();

    await expect(segmentos(page).locator('[data-textos-anuncio]')).toContainText('Se guardó la versión 2');
    const guardado = mensajes.textos.pedidos.filter((p) => p.metodo === 'POST' && JSON.stringify(p.cuerpo).includes('Más')).at(-1);
    expect(guardado?.cuerpo).toMatchObject({ contenido: { texto: 'Hola [$MACRO1$], tu cuota vence el [$MACRO2$]. INFO por [whatsapp] Más [$MACRO1$]' } });
  });

  test('un speech sembrado, con sus espacios dobles y el espacio antes de la coma, se guarda con solo lo que se escribió de más', async ({ page }) => {
    // As the seeded ones are written: a double space and a space before a comma. Shorter than they are, because the fake of the saved texts refuses over 200.
    const sembrado = 'Hola [$MACRO1$] Caja Cusco te informa que tu cuota vence  el [$MACRO2$] , pague en agencias,  KASNET o Wayki app. INFO por [whatsapp]';
    const mensajes = mensajesFalsos();
    mensajes.textos.textos.push(mensajeFalso(105, 'Speech sembrado', [sembrado]));
    await abrir(page, apiConfigurada(), mensajes);
    await segmentos(page).locator('[data-textos-select]').selectOption({ label: 'Speech sembrado' });
    await expect(tramo(page, 0)).toHaveValue('Hola ');
    await expect(tramo(page, 2)).toHaveValue(' Caja Cusco te informa que tu cuota vence  el ');
    const ultimo = editor(page).locator('[data-tramo]').last();

    await ultimo.click();
    await page.keyboard.press('End');
    await page.keyboard.type('.');
    await segmentos(page).locator('[data-textos-guardar]').click();

    await expect(segmentos(page).locator('[data-textos-anuncio]')).toContainText('Se guardó la versión 2');
    const guardado = mensajes.textos.pedidos.filter((p) => p.metodo === 'POST' && JSON.stringify(p.cuerpo).includes('Caja Cusco')).at(-1);
    expect((guardado?.cuerpo as { contenido: { texto: string } }).contenido.texto).toBe(`${sembrado}.`);
  });

  test('el contador es el del editor común y cuenta [whatsapp] como el enlace de 26 caracteres', async ({ page }) => {
    await abrir(page);

    await expect(contador(page)).toContainText('82 / 4096 caracteres');
    await expect(etiquetaTope(page)).toBeHidden();
  });

  test('al pasar el tope: el contador en color de error, el tag «Pasa el tope», y sin «Cerca del tope»', async ({ page }) => {
    const api = apiConfigurada();
    api.configuracion.tope_mensaje = 30;
    await abrir(page, api);

    await expect(contador(page)).toContainText('82 / 30 caracteres');
    await expect(etiquetaTope(page)).toBeVisible();
    await expect(etiquetaTope(page)).toHaveText('Pasa el tope');
    await expect(etiquetaTope(page)).toHaveClass(/tag--error/);
    await expect(editor(page).locator('.tag--advertencia:visible')).toHaveCount(0);
  });

  test('sin umbral no hay «Cerca del tope»: a punto de pasarlo solo está el contador', async ({ page }) => {
    const api = apiConfigurada();
    api.configuracion.tope_mensaje = 85;
    await abrir(page, api);

    await expect(contador(page)).toContainText('82 / 85 caracteres');
    await expect(etiquetaTope(page)).toBeHidden();
    await expect(editor(page).locator('.tag--advertencia:visible')).toHaveCount(0);
  });

  test('un tope guardado en el panel de Topes lo toma el editor sin recargar: el contexto se pide otra vez', async ({ page }) => {
    const { mensajes } = await abrir(page);
    await expect(contador(page)).toContainText('82 / 4096 caracteres');
    const antes = mensajes.editor.filter((p) => p.ruta.startsWith('/texto-enriquecido/catalogo')).length;

    await page.locator('#wm-tope-mensaje').fill('2000');
    await page.locator('#wm-tope-mensaje').blur();
    await page.getByRole('button', { name: 'Guardar topes' }).click();

    await expect(contador(page)).toContainText('82 / 2000 caracteres');
    expect(mensajes.editor.filter((p) => p.ruta.startsWith('/texto-enriquecido/catalogo')).length).toBeGreaterThan(antes);
    // The text on screen is the one that was: mounting the editor again does not lose it.
    await expect(tramo(page, 2)).toHaveValue(', tu cuota vence el ');
  });

  test('un emoji entra al resumen con su posición apenas se escribe, sin esperar al guardado, y «Ir al problema» deja el cursor sobre él', async ({ page }) => {
    await abrir(page);
    await expect(resumenDelMensaje(page)).toBeHidden();

    // «Hola » are 5 characters: the emoji is the 6th, and takes two UTF-16 units.
    await tramo(page, 0).fill('Hola 😀');

    await expect(resumenDelMensaje(page)).toBeVisible();
    await expect(resumenDelMensaje(page).locator('.editor-texto__resumenTitulo')).toHaveText('Hay 1 problema en el texto.');
    await expect(resumenDelMensaje(page).locator('li')).toContainText('No se admiten emojis: el primero es «😀», en la posición 6.');
    // Once, in its place: the marked run with its error under the line. No box repeats it under the counter.
    await expect(errorDelEmoji(page)).toHaveText('No se admiten emojis: el primero es «😀», en la posición 6.');
    await expect(segmentos(page).locator('[data-textos-editor] > .wm-editor__errores')).toHaveCount(0);
    await expect(tramo(page, 0)).toHaveAttribute('aria-invalid', 'true');

    await resumenDelMensaje(page).getByRole('button', { name: 'Ir al problema' }).click();

    await expect(tramo(page, 0)).toBeFocused();
    const seleccion = await tramo(page, 0).evaluate((campo: HTMLTextAreaElement) => [campo.selectionStart, campo.selectionEnd]);
    expect(seleccion).toEqual([5, 7]);

    await tramo(page, 0).fill('Hola');
    await expect(resumenDelMensaje(page)).toBeHidden();
    await expect(errorDelEmoji(page)).toHaveText('');
    await expect(tramo(page, 0)).not.toHaveAttribute('aria-invalid', 'true');
  });

  test('una macro que la definición no tiene se ve como píldora, se marca y entra al resumen con cuántas tiene', async ({ page }) => {
    const mensajes = mensajesFalsos();
    mensajes.textos.textos.push(mensajeFalso(106, 'Con una macro de más', ['Tu saldo es [$MACRO7$] hoy']));
    await abrir(page, apiConfigurada(), mensajes);

    await segmentos(page).locator('[data-textos-select]').selectOption({ label: 'Con una macro de más' });

    // It does not turn into mute text or disappear: it is a pill, in capitals as the marker is, and it is marked (its name says so).
    await expect(pildora(page, /MACRO7, no existe en este contexto/)).toBeVisible();
    await expect(editor(page).locator('[data-linea]').getByRole('button', { name: /MACRO7/ })).toHaveText(/MACRO7/);
    await expect(resumenDelMensaje(page).locator('li')).toContainText('[$MACRO7$] no existe en la definición elegida: tiene 2 macros.');
    await expect(resumenDelMensaje(page).locator('.editor-texto__resumenTitulo')).toHaveText('Hay 1 problema en el texto.');
    await resumenDelMensaje(page).getByRole('button', { name: 'Ir al problema' }).click();
    await expect(pildora(page, /MACRO7/)).toBeFocused();
  });

  test('todos los problemas van en un solo resumen, arriba del editor: lo que halla el editor, el emoji y el largo', async ({ page }) => {
    const api = apiConfigurada();
    api.configuracion.tope_mensaje = 40;
    const mensajes = mensajesFalsos();
    mensajes.textos.textos.push(mensajeFalso(107, 'Con todo mal', ['Hola 😀 [$MACRO4$], INFO por [whatsapp] y algo más']));
    await abrir(page, api, mensajes);

    await segmentos(page).locator('[data-textos-select]').selectOption({ label: 'Con todo mal' });

    await expect(resumenDelMensaje(page).locator('.editor-texto__resumenTitulo')).toHaveText('Hay 3 problemas en el texto.');
    await expect(resumenDelMensaje(page).locator('li > span')).toHaveText([
      '[$MACRO4$] no existe en la definición elegida: tiene 2 macros.',
      'No se admiten emojis: el primero es «😀», en la posición 6.',
      'El mensaje tiene 65 caracteres: el máximo es 40.',
    ]);
    await expect(resumenDelMensaje(page).getByRole('button', { name: 'Ir al problema' })).toHaveCount(3);
    await expect(contador(page)).toContainText('/ 40 caracteres');
    await expect(etiquetaTope(page)).toHaveText('Pasa el tope');
    // The limit is the counter and its tag, with no box of its own: its sentence is only in the summary.
    await expect(editor(page).locator('.field__error', { hasText: 'El mensaje tiene' })).toHaveCount(0);
    await expect(page.locator('#wm-mensajes-segmento .field__error', { hasText: 'El mensaje tiene' })).toHaveCount(0);
  });

  test('al guardar con un emoji, el backend lo rechaza: el foco va al resumen, que dice el emoji una sola vez, y la lista del componente no lo repite', async ({ page }) => {
    const mensajes = mensajesFalsos();
    mensajes.textos.respuestas.versionar.push(
      respuestaDeRegla('mensaje_con_emoji', { caracter: '😀', posicion: 6 }, 'No se admiten emojis: el primero es «😀», en la posición 6'),
    );
    await abrir(page, apiConfigurada(), mensajes);
    await tramo(page, 0).fill('Hola 😀');

    await segmentos(page).locator('[data-textos-guardar]').click();

    // Only the focus: with `role="alert"` on top a screen reader would say it twice. Its title is its accessible name.
    await expect(resumenDelMensaje(page)).toBeFocused();
    await expect(resumenDelMensaje(page)).not.toHaveAttribute('role', 'alert');
    await expect(resumenDelMensaje(page)).toHaveAccessibleName('Hay 1 problema en el texto.');
    // The summary says it once (the backend's sentence is the one the page already had), and the component's list does not repeat it.
    await expect(resumenDelMensaje(page).locator('li')).toHaveCount(1);
    await expect(resumenDelMensaje(page).locator('li')).toContainText('No se admiten emojis: el primero es «😀», en la posición 6.');
    await expect(segmentos(page).locator('[data-textos-problemas]')).toBeHidden();
    // What was typed stays as it was.
    await expect(tramo(page, 0)).toHaveValue('Hola 😀');
  });

  test('si el backend rechaza algo que la página no conocía, el resumen lo suma con la frase del servidor y el foco va a él', async ({ page }) => {
    const mensajes = mensajesFalsos();
    mensajes.textos.respuestas.versionar.push({
      estado: 400,
      cuerpo: {
        detail: 'El texto no se puede guardar. Otra regla',
        codigo: 'texto_guardado_invalido',
        problemas: [{ codigo: 'regla_del_contexto', detalle: 'Otra regla del módulo', ubicacion: null, nombre: null, columna: null, segmento: null, campo: 'contenido', codigo_contexto: 'otra_regla', parametros: {} }],
      },
    });
    await abrir(page, apiConfigurada(), mensajes);
    await tramo(page, 0).fill('Hola nuevo');

    await segmentos(page).locator('[data-textos-guardar]').click();

    await expect(resumenDelMensaje(page)).toBeFocused();
    await expect(resumenDelMensaje(page).locator('li')).toHaveCount(1);
    await expect(resumenDelMensaje(page).locator('li')).toContainText('Otra regla del módulo');
    await expect(segmentos(page).locator('[data-textos-problemas]')).toBeHidden();
    // The next edit takes what was refused away: the summary only says what the text has.
    await tramo(page, 0).fill('Hola otra vez');
    await expect(resumenDelMensaje(page)).toBeHidden();
  });

  test('sin definición por defecto no hay macros: lo dice y el buscador deja solo el enlace de WhatsApp', async ({ page }) => {
    const api = apiConfigurada();
    api.configuracion.definicion_defecto_id = null;
    await abrir(page, api);

    await expect(segmentos(page).locator('.wm-editor__aviso')).toHaveText(
      'No hay una definición por defecto. Elige una más abajo, en Definición por defecto, para insertar macros.',
    );
    await tramo(page, 6).click();
    await page.keyboard.type('[@');
    await expect(buscador(page).getByRole('option')).toHaveCount(1);
    await expect(buscador(page).getByRole('option')).toContainText('Enlace de WhatsApp');
    // And the panel of a pill says where the column is made: with no definition, a new one.
    await page.keyboard.press('Escape');
    await pildora(page, /Enlace de WhatsApp/).click();
    await expect(editor(page).locator('[data-sin-funciones]').getByRole('link', { name: 'Crear en Columnas de carga' })).toHaveAttribute(
      'href',
      '/columnas?plataforma=whatsmkt&volver=%2Fwhatsmkt%2Fconfiguracion',
    );
  });

  test('un texto con el modo de solo lectura (deshabilitado o una versión vieja) no se puede editar', async ({ page }) => {
    const mensajes = mensajesFalsos();
    await abrir(page, apiConfigurada(), mensajes);
    await segmentos(page).locator('[data-textos-select]').selectOption('102');
    await expect(tramo(page, 0)).toHaveValue('Hola ');

    await segmentos(page).locator('[data-textos-versiones]').selectOption({ index: 1 });

    await expect(tramo(page, 0)).toHaveAttribute('readonly', '');
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
    // The editor goes on: what is typed shows in the preview, and the macros are still there to insert.
    await tramo(page, 0).fill('Adiós ');
    await expect(vista(page)).toContainText('Adiós [$MACRO1$], tu cuota vence el [$MACRO2$].');
    await expect(pildora(page, /MACRO1 · Nombres del titular/)).toBeVisible();
  });
});

test.describe('en inglés', () => {
  test('el editor y los paneles se traducen', async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' })));
    const api = apiConfigurada();
    await montarApiWhatsmkt(page, api);
    await montarMensajesWhatsmkt(page, mensajesFalsos(), api);
    await page.goto(RUTA);
    await expect(segmentos(page)).toHaveAttribute('data-montado', 'true');

    await expect(pildora(page, /MACRO1 · Nombres del titular/)).toBeVisible();
    await expect(pildora(page, /WhatsApp link/)).toBeVisible();
    await expect(tramo(page, 2)).toHaveValue(/tu cuota vence el/);
    await expect(contador(page)).toContainText('82 / 4096 characters');
    await tramo(page, 0).click();
    await page.keyboard.type('[@');
    await expect(page.locator('#wm-msg-segmento-editor [data-disparador-anuncio]')).toHaveText('Variable search. Type to filter, Enter inserts and Escape cancels.');
    await page.keyboard.press('Escape');
    await expect(segmentos(page).locator('.wm-vista h3')).toHaveText('This is how the customer will see it');
    await expect(vista(page)).toContainText('(no WhatsApp set up)');
    await expect(vinculo(page)).toHaveText('Message for Preventivo: “Preventivo inicial”');
  });
});

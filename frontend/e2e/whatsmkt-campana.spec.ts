/**
 * WhatsMKT campaign (T-WM-F2a1), end to end against an intercepted API: the form that builds the request and the preview of the
 * lot. «Crear» is on screen but off (T-WM-F2a2). The clock is fixed from the first spec, in `montarApiWhatsmkt`. Every phone is
 * synthetic (900000xxx).
 */
import { expect, test, type Page } from '@playwright/test';

import { apiWhatsmkt, montarApiWhatsmkt, type ApiFalsaWhatsmkt } from './api-falsa-whatsmkt';
import { campanaFalsa, montarCampanaWhatsmkt, texto, type CampanaFalsa } from './api-falsa-whatsmkt-campana';
import { montarSeleccion } from './apoyo-seleccion';

const RUTA = '/whatsmkt/campana';

/** The configuration of a screen that is already set up: a default definition and a message for two of the segments. */
function apiConfigurada(): ApiFalsaWhatsmkt {
  const api = apiWhatsmkt();
  api.configuracion.definicion_defecto_id = 11;
  api.segmentos[0].texto_guardado_id = 101;
  api.segmentos[1].texto_guardado_id = 102;
  return api;
}

async function abrir(page: Page, api = apiConfigurada(), campana = campanaFalsa()): Promise<{ api: ApiFalsaWhatsmkt; campana: CampanaFalsa }> {
  await montarApiWhatsmkt(page, api);
  await montarCampanaWhatsmkt(page, campana);
  await montarSeleccion(page);
  await page.goto(RUTA);
  await expect(page.locator('h1')).toBeVisible();
  return { api, campana };
}

/** Choose the one saved selection the fixture seeds, so the form appears and the first preview is asked for. */
async function conSeleccion(page: Page, api = apiConfigurada(), campana = campanaFalsa()): Promise<{ api: ApiFalsaWhatsmkt; campana: CampanaFalsa }> {
  const montado = await abrir(page, api, campana);
  await page.getByLabel('Selección guardada').selectOption({ label: 'Preventiva top 1000' });
  await expect(page.locator('[data-campana]')).toBeVisible();
  return montado;
}

const ultimaPrevia = (campana: CampanaFalsa) => campana.previas.at(-1)!;
const resumen = (page: Page) => page.locator('[data-resumen]');
const crear = (page: Page) => page.locator('[data-crear]');
const problemas = (page: Page) => page.locator('[data-problemas-lista] li');
const mensajeDe = (page: Page, clave: string) => page.locator(`#wm-mensaje-${clave}`);

test.describe('la base', () => {
  test('sin selección elegida solo está la selección, y dice qué hacer', async ({ page }) => {
    await abrir(page);

    await expect(page.locator('[data-guardia]')).toContainText('Elige una selección guardada para armar la campaña.');
    await expect(page.locator('[data-formulario]')).toBeHidden();
    await expect(page.getByRole('button', { name: 'Editar en Cartera' })).toBeDisabled();
  });

  test('al elegir una, aparecen las secciones en el orden del §3.1 y se pide la previsualización', async ({ page }) => {
    const { campana } = await conSeleccion(page);

    await expect(page.locator('[data-guardia]')).toBeHidden();
    await expect(page.locator('h2.panel__title')).toHaveText([
      'Selección',
      'Archivo de carga',
      'Mensaje',
      'Programación',
      'Envío',
      'Nombre de la campaña',
      'Previsualización',
      // The card of the lot, hidden until one is created.
      'Para subir a WhatsMKT',
    ]);
    await expect.poll(() => campana.previas.length).toBeGreaterThan(0);
    expect(ultimaPrevia(campana)).toMatchObject({ fecha_corte: '2026-09-13', cantidad: 1000, seleccion_id: 1, modo: 'por_segmento', definicion: { id: 11 } });
  });

  test('«Editar en Cartera» se enciende con una selección guardada y va a Cartera con la selección y la vuelta', async ({ page }) => {
    await conSeleccion(page);
    const boton = page.getByRole('button', { name: 'Editar en Cartera' });

    await expect(boton).toBeEnabled();
    await boton.click();

    await expect(page).toHaveURL(/\/cartera\?seleccion=1&volver=%2Fwhatsmkt%2Fcampana$/);
  });

  test('al volver de Cartera con ?seleccion=<id>, esa selección queda elegida y la dirección se limpia', async ({ page }) => {
    const { campana } = await abrir(page, apiConfigurada(), campanaFalsa());
    await page.goto('/whatsmkt/campana?seleccion=1');

    await expect(page.locator('[data-campana]')).toBeVisible();
    await expect.poll(() => campana.previas.at(-1)?.seleccion_id).toBe(1);
    await expect(page.locator('[data-seleccion-borrada]')).toBeHidden();
    await expect(page).toHaveURL(/\/whatsmkt\/campana$/);
  });

  test('si la selección de la vuelta ya no existe, no se elige ninguna y un aviso lo dice', async ({ page }) => {
    await abrir(page);
    await page.goto('/whatsmkt/campana?seleccion=999');

    await expect(page.locator('[data-seleccion-borrada]')).toBeVisible();
    await expect(page.locator('[data-formulario]')).toBeHidden();
    await expect(page).toHaveURL(/\/whatsmkt\/campana$/);
  });
});

test.describe('archivo de carga', () => {
  test('ofrece solo las definiciones de WhatsMKT, con la de la configuración elegida, su versión y sus columnas', async ({ page }) => {
    await conSeleccion(page);
    const select = page.locator('#wm-definicion');

    await expect(select.locator('option')).toHaveText(['Elige una definición', 'Contactos WhatsMKT', 'Contactos WhatsMKT con apellido']);
    await expect(select).toHaveValue('11');
    await expect(page.locator('[data-version-linea]')).toHaveText('Versión 3 · WhatsMKT');
    const filas = page.locator('[data-columnas-tabla] tbody tr');
    await expect(filas).toHaveCount(3);
    // The first column is the number, with no macro; the others are macro 1, 2 by position.
    await expect(filas.nth(0)).toContainText('—');
    await expect(filas.nth(1)).toContainText('[$MACRO1$]');
    await expect(filas.nth(1)).toContainText('Nombres del titular');
    // The content reads with the catalogue's label of each variable, never the technical name.
    await expect(filas.nth(0)).toContainText('Texto: 51[Teléfono]');
    await expect(filas.nth(1)).toContainText('Variable: Titular');
    await expect(filas.nth(2)).toContainText('Variable: Saldo de capital pendiente');
    // A column with no label says «—», as the constructor does.
    await expect(filas.nth(2).locator('td').nth(2)).toHaveText('—');
    await expect(page.getByRole('link', { name: 'Editar en Columnas de carga' })).toHaveAttribute('href', /^\/columnas\?definicion=11&volver=%2Fwhatsmkt%2Fcampana(%3Fseleccion%3D\d+)?$/);
  });

  test('cambiar de definición pide otra previsualización con la elegida', async ({ page }) => {
    const { campana } = await conSeleccion(page);

    await page.locator('#wm-definicion').selectOption({ label: 'Contactos WhatsMKT con apellido' });

    await expect.poll(() => ultimaPrevia(campana).definicion.id).toBe(12);
    await expect(page.locator('[data-version-linea]')).toHaveText('Versión 3 · WhatsMKT');
  });

  test('sin definiciones de WhatsMKT, el campo queda apagado, dice por qué y el enlace es para crear una', async ({ page }) => {
    const api = apiConfigurada();
    api.configuracion.definicion_defecto_id = null;
    api.definiciones = api.definiciones.filter((d) => d.plataforma !== 'whatsmkt');
    await abrir(page, api);
    await page.getByLabel('Selección guardada').selectOption({ label: 'Preventiva top 1000' });
    await expect(page.locator('[data-formulario]')).toBeVisible();

    await expect(page.locator('#wm-definicion')).toBeDisabled();
    await expect(page.locator('[data-sin-definiciones]')).toContainText('Crea una definición de WhatsMKT en Columnas de carga');
    await expect(page.getByRole('link', { name: 'Crear en Columnas de carga' })).toHaveAttribute('href', /^\/columnas\?plataforma=whatsmkt&volver=%2Fwhatsmkt%2Fcampana(%3Fseleccion%3D\d+)?$/);
  });

  test('más de 5 macros avisan sin bloquear (DU-WM-1)', async ({ page }) => {
    // The fake's definition has 2 macros: no warning.
    await conSeleccion(page);

    await expect(page.locator('[data-cinco-macros]')).toBeHidden();
  });
});

test.describe('mensaje', () => {
  test('por segmento: una fila por segmento con sus días y el mensaje propio ya elegido', async ({ page }) => {
    await conSeleccion(page);

    const filas = page.locator('[data-mensaje-segmentos] tbody tr');
    await expect(filas).toHaveCount(3);
    await expect(filas.nth(0)).toContainText('hasta 0');
    await expect(filas.nth(1)).toContainText('1 a 8');
    await expect(filas.nth(2)).toContainText('9 o más');
    await expect(mensajeDe(page, 'preventivo')).toHaveValue('101');
    await expect(mensajeDe(page, 'tramo_2')).toHaveValue('102');
    await expect(mensajeDe(page, 'mayores_2')).toHaveValue('');
    await expect(page.locator('[data-modo-hint]')).toContainText('Un mensaje por segmento');
  });

  test('un segmento sin productos en la selección lo dice bajo su select: no genera campaña', async ({ page }) => {
    await conSeleccion(page);

    await expect(page.locator('[data-sin-productos="mayores_2"]')).toHaveText('Sin productos en esta selección: no genera campaña.');
    await expect(page.locator('[data-sin-productos="mayores_2"]')).toBeVisible();
    await expect(page.locator('[data-sin-productos="preventivo"]')).toBeHidden();
    await expect(page.locator('[data-sin-productos="tramo_2"]')).toBeHidden();
  });

  test('bajo cada select va el texto del mensaje elegido, de solo lectura, con su largo contra el tope y sus macros marcadas', async ({ page }) => {
    await conSeleccion(page);
    const bloque = page.locator('[data-texto-mensaje="preventivo"]');

    await expect(bloque.locator('.wm-mensaje-texto__cuerpo')).toHaveText('Hola [$MACRO1$], Preventivo: tu saldo es [$MACRO2$]. INFO por [whatsapp]');
    // «[whatsapp]» counts as the link it becomes (26): 72 characters of text plus the 16 the link adds.
    await expect(bloque.locator('.wm-contador')).toHaveText('88 / 4096 caracteres');
    // The macros are marked, and the one whose column has a label says it in its title. The link of WhatsApp is marked too, with the name the editor gives it.
    await expect(bloque.locator('mark.wm-macro')).toHaveText(['[$MACRO1$]', '[$MACRO2$]', '[whatsapp]']);
    await expect(bloque.locator('mark.wm-macro').first()).toHaveAttribute('title', 'MACRO1 · Nombres del titular');
    await expect(bloque.locator('mark.wm-macro').last()).toHaveAttribute('title', 'Enlace de WhatsApp');
    // The segment with no message has no block.
    await expect(page.locator('[data-texto-mensaje="mayores_2"]')).toBeHidden();

    await mensajeDe(page, 'tramo_2').selectOption({ label: 'Oferta de octubre' });
    await expect(page.locator('[data-texto-mensaje="tramo_2"] .wm-mensaje-texto__cuerpo')).toContainText('Oferta de octubre');
    await mensajeDe(page, 'tramo_2').selectOption({ label: 'Elige un mensaje' });
    await expect(page.locator('[data-texto-mensaje="tramo_2"]')).toBeHidden();
  });

  test('elegir otro mensaje de un segmento lo manda en la previsualización', async ({ page }) => {
    const { campana } = await conSeleccion(page);

    await mensajeDe(page, 'tramo_2').selectOption({ label: 'Oferta de octubre' });

    await expect.poll(() => ultimaPrevia(campana).mensajes?.tramo_2?.texto_guardado_id).toBe(103);
    expect(ultimaPrevia(campana).mensajes?.preventivo?.texto_guardado_id).toBe(101);
    // The version is the API's to pick (the latest): the request does not ask for one.
    expect(ultimaPrevia(campana).mensajes?.tramo_2).toEqual({ texto_guardado_id: 103 });
  });

  test('global: un solo select con los mensajes globales y los de los segmentos en dos grupos, y un solo mensaje en el pedido', async ({ page }) => {
    const { campana } = await conSeleccion(page);

    await page.getByRole('button', { name: 'Global' }).click();

    await expect(page.locator('[data-modo-hint]')).toContainText('Un solo mensaje para toda la selección');
    const select = page.locator('#wm-mensaje-global');
    await expect(select.locator('optgroup')).toHaveCount(2);
    await expect(select.locator('optgroup').nth(0)).toHaveAttribute('label', 'Mensajes globales');
    await expect(select.locator('optgroup').nth(0).locator('option')).toHaveText(['Oferta de octubre']);
    await expect(select.locator('optgroup').nth(1)).toHaveAttribute('label', 'Mensajes por segmento');
    await expect(select.locator('optgroup').nth(1).locator('option')).toHaveText(['Preventivo', 'Tramo 2']);
    // Without a message the lot has a problem, with the sentence of a global campaign.
    await expect(page.locator('[data-problemas-mensaje="global"]')).toHaveText('Elige el mensaje de la campaña.');

    await select.selectOption({ label: 'Oferta de octubre' });

    await expect.poll(() => ultimaPrevia(campana).mensaje?.texto_guardado_id).toBe(103);
    expect(ultimaPrevia(campana).modo).toBe('global');
    expect(ultimaPrevia(campana).mensajes).toBeUndefined();
    await expect(page.locator('[data-problemas-mensaje="global"]')).toBeEmpty();
    // A global lot is one campaign: no selector of campaigns.
    await expect(page.locator('[data-campanas]')).toBeHidden();
  });

  test('los problemas del mensaje van bajo el select de su segmento, en el orden en que llegan', async ({ page }) => {
    const campana = campanaFalsa({
      problemasExtra: [
        { codigo: 'mensaje_con_emoji', detalle: 'emoji', segmento: 'tramo_2', parametros: { caracter: '😀', posicion: 42 } },
        { codigo: 'macro_inexistente', detalle: 'macro', segmento: 'tramo_2', parametros: { macro: '[$MACRO4$]', n: 3 } },
      ],
    });
    await conSeleccion(page, apiConfigurada(), campana);

    const bajo = page.locator('[data-problemas-mensaje="tramo_2"] p');
    await expect(bajo).toHaveText([
      'No se admiten emojis: el primero es «😀», en la posición 42.',
      '[$MACRO4$] no existe en la definición elegida: tiene 3 macros.',
    ]);
    await expect(mensajeDe(page, 'tramo_2')).toHaveAttribute('aria-invalid', 'true');
    await expect(mensajeDe(page, 'preventivo')).not.toHaveAttribute('aria-invalid', 'true');
    // The summary lists them too, with the segment in front.
    await expect(problemas(page).filter({ hasText: 'Tramo 2 · No se admiten emojis' })).toHaveCount(1);
  });

  test('un mensaje deshabilitado no se ofrece: el select queda sin elegir y el problema lo dice', async ({ page }) => {
    const campana = campanaFalsa({
      textos: [texto(101, 'Preventivo'), texto(102, 'Tramo 2', { deshabilitado_en: '2026-10-12T10:00:00-05:00' })],
    });
    await conSeleccion(page, apiConfigurada(), campana);

    await expect(mensajeDe(page, 'tramo_2').locator('option')).toHaveText(['Elige un mensaje', 'Preventivo']);
    await expect(mensajeDe(page, 'tramo_2')).toHaveValue('');
  });

  test('si los textos guardados no se pueden leer, lo dice en la sección y el resto sigue', async ({ page }) => {
    await montarApiWhatsmkt(page, apiConfigurada());
    await montarCampanaWhatsmkt(page, campanaFalsa());
    await montarSeleccion(page);
    await page.route('**/api/textos-guardados**', (ruta) => ruta.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'La lista no respondió' }) }));
    await page.goto(RUTA);
    await page.getByLabel('Selección guardada').selectOption({ label: 'Preventiva top 1000' });

    await expect(page.locator('[data-mensajes-error]')).toHaveText('La lista no respondió');
    await expect(page.locator('#wm-definicion')).toBeEnabled();
  });
});

test.describe('programación', () => {
  test('los horarios salen de la configuración', async ({ page }) => {
    await conSeleccion(page);
    await expect(page.locator('[data-horarios] label').nth(0)).toContainText('Horario 1 · 08:00 – 14:00');
    await expect(page.locator('[data-horarios] label').nth(1)).toContainText('Horario 2 · 14:00 – 20:00');
  });

  test('la fecha viene con el siguiente día gestionable, con min en la mínima, y lo que se elige se manda', async ({ page }) => {
    const { campana } = await conSeleccion(page);
    const fecha = page.locator('#wm-fecha');

    await expect(fecha).toHaveValue('2026-10-16');
    await expect(fecha).toHaveAttribute('min', '2026-10-16');
    await expect(page.locator('#wm-fecha-hint')).toHaveText('Se sugiere el siguiente día gestionable: de lunes a sábado, sin feriados.');
    expect(ultimaPrevia(campana).fecha_envio).toBe('2026-10-16');
    await expect(page.locator('[data-fecha-error]')).toBeEmpty();
    await expect(page.locator('[data-fecha-usar]')).toBeHidden();

    await fecha.fill('2026-10-19');
    await expect.poll(() => ultimaPrevia(campana).fecha_envio).toBe('2026-10-19');

    // Left empty, the API takes its own suggestion: nothing is sent.
    await fecha.fill('');
    await expect.poll(() => ultimaPrevia(campana).fecha_envio).toBeUndefined();
  });

  test('un día no gestionable se dice bajo la fecha con «Usar el …», y un clic toma el sugerido', async ({ page }) => {
    const { campana } = await conSeleccion(page);
    const fecha = page.locator('#wm-fecha');

    await fecha.fill('2026-10-18');

    await expect(page.locator('[data-fecha-error]')).toContainText(/no es un día gestionable\. El siguiente es el 19/);
    await expect(fecha).toHaveAttribute('aria-invalid', 'true');
    await expect(problemas(page).filter({ hasText: 'no es un día gestionable' })).toHaveCount(1);
    const usar = page.getByRole('button', { name: /Usar el 19/ });
    await expect(usar).toBeVisible();

    await usar.click();

    // Sunday 18 Oct: the next working day is Monday the 19th, not the one the form started with.
    await expect(fecha).toHaveValue('2026-10-19');
    await expect.poll(() => ultimaPrevia(campana).fecha_envio).toBe('2026-10-19');
    await expect(page.locator('[data-fecha-error]')).toBeEmpty();
    await expect(fecha).not.toHaveAttribute('aria-invalid', 'true');
    await expect(usar).toBeHidden();
  });

  test('si la programación no se puede leer, la fecha queda vacía y lo dice bajo el campo', async ({ page }) => {
    await montarApiWhatsmkt(page, apiConfigurada());
    await montarCampanaWhatsmkt(page, campanaFalsa());
    await montarSeleccion(page);
    // The last route registered answers first: this one is over the fake's.
    await page.route('**/api/whatsmkt/programacion', (route) => route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'Fallo sintético' }) }));
    await page.goto(RUTA);
    await page.getByLabel('Selección guardada').selectOption({ label: 'Preventiva top 1000' });
    await expect(page.locator('[data-campana]')).toBeVisible();

    await expect(page.locator('#wm-fecha')).toHaveValue('');
    await expect(page.locator('[data-fecha-error]')).not.toBeEmpty();
  });

  test('sin horario marcado es un problema, que se dice bajo el campo al salir de la sección, y marcar uno lo quita', async ({ page }) => {
    await conSeleccion(page);
    await expect(problemas(page).filter({ hasText: 'Marca al menos un horario.' })).toHaveCount(1);

    // Leaving the section tells its problems under its fields.
    await page.locator('#wm-fecha').focus();
    await page.locator('#wm-vcard').evaluate((nodo) => nodo.blur());
    await page.getByLabel('Foto de perfil').focus();
    await expect(page.locator('[data-horarios-error]')).toHaveText('Marca al menos un horario.');

    await page.locator('[data-franja="horario_1"]').check();

    await expect(page.locator('[data-horarios-error]')).toBeEmpty();
    await expect(problemas(page).filter({ hasText: 'Marca al menos un horario.' })).toHaveCount(0);
  });

  test('«Ir al campo» lleva el foco a la sección del problema', async ({ page }) => {
    await conSeleccion(page);

    await problemas(page).filter({ hasText: 'Marca al menos un horario.' }).getByRole('button', { name: 'Ir al campo' }).click();

    await expect(page.locator('[data-franja="horario_1"]')).toBeFocused();
  });
});

test.describe('envío', () => {
  test('cada tipo muestra solo sus campos y conserva lo escrito en los otros al cambiar', async ({ page }) => {
    await conSeleccion(page);
    await expect(page.locator('[data-condicional="archivo"]')).toBeHidden();
    await expect(page.locator('[data-condicional="vcard"]')).toBeHidden();

    await page.getByLabel('Texto + archivo').check();
    await expect(page.locator('[data-condicional="archivo"]')).toBeVisible();
    await page.locator('#wm-adjunto').selectOption({ label: 'afiche-octubre.jpg · Imagen JPEG · 240 KB' });

    await page.getByLabel('Texto + vCard').check();
    await expect(page.locator('[data-condicional="archivo"]')).toBeHidden();
    await page.locator('#wm-vcard').fill('Caja Cusco');

    await page.getByLabel('Texto + archivo').check();
    await expect(page.locator('#wm-adjunto')).toHaveValue('1');
    await page.getByLabel('Texto + vCard').check();
    await expect(page.locator('#wm-vcard')).toHaveValue('Caja Cusco');
  });

  test('«Texto + archivo» sin archivo y «Texto + vCard» sin etiqueta son problemas, y solo cuenta lo del tipo elegido', async ({ page }) => {
    await conSeleccion(page);
    await page.locator('[data-franja="horario_1"]').check();
    await expect(problemas(page)).toHaveCount(0);

    await page.getByLabel('Texto + archivo').check();
    await expect(problemas(page).filter({ hasText: 'Elige el archivo que se envía.' })).toHaveCount(1);
    // The error is under the field too, with the field marked.
    await expect(page.locator('[data-envio-error]')).toHaveText('Elige el archivo que se envía.');
    await expect(page.locator('#wm-adjunto')).toHaveAttribute('aria-invalid', 'true');

    await page.getByLabel('Texto + vCard').check();
    await expect(problemas(page).filter({ hasText: 'Elige el archivo que se envía.' })).toHaveCount(0);
    await expect(problemas(page).filter({ hasText: 'Escribe la etiqueta del contacto.' })).toHaveCount(1);
    await expect(page.locator('[data-envio-error]')).toHaveText('Escribe la etiqueta del contacto.');
    await expect(page.locator('#wm-vcard')).toHaveAttribute('aria-invalid', 'true');

    await page.locator('#wm-vcard').fill('Caja Cusco');
    await expect(page.locator('[data-envio-error]')).toBeEmpty();
    await expect(page.locator('#wm-vcard')).not.toHaveAttribute('aria-invalid', 'true');
    await page.locator('#wm-vcard').fill('');

    await page.getByLabel('Solo texto').check();
    await expect(problemas(page)).toHaveCount(0);
  });

  test('con la biblioteca vacía el select de archivos queda inactivo y «Subir un archivo» sigue al lado', async ({ page }) => {
    const api = apiConfigurada();
    api.adjuntos = [];
    await conSeleccion(page, api);
    await page.getByLabel('Texto + archivo').check();

    await expect(page.locator('#wm-adjunto')).toBeDisabled();
    await expect(page.getByRole('button', { name: 'Subir un archivo' })).toBeVisible();
  });

  test('el archivo se elige de la biblioteca (sin los archivados) y la foto solo entre las JPEG, con «Sin foto»', async ({ page }) => {
    await conSeleccion(page);
    await page.getByLabel('Texto + archivo').check();

    await expect(page.locator('#wm-adjunto option')).toHaveText([
      'Elige un archivo',
      'afiche-octubre.jpg · Imagen JPEG · 240 KB',
      /tarifario\.pdf · PDF · 1[.,]5 MB/,
    ]);
    await expect(page.locator('#wm-foto option')).toHaveText(['Sin foto', 'afiche-octubre.jpg · Imagen JPEG · 240 KB']);
    await expect(page.getByRole('button', { name: 'Subir una foto' })).toBeVisible();
  });
});

test.describe('nombre de la campaña', () => {
  test('parte de la plantilla de la configuración, con el contador del nombre más largo', async ({ page }) => {
    await conSeleccion(page);

    await expect(page.locator('#wm-plantilla')).toHaveValue('CUZCO_Vencida ({segmento}) whatsapp {fecha_corte}');
    // The longest of the lot: «CUZCO_Vencida (Preventivo) whatsapp 2026.09.13», 46 characters.
    await expect(page.locator('[data-contador]')).toHaveText('46 / 75');
  });

  test('las fichas insertan la variable donde está el cursor y el hint de las variables está a la vista', async ({ page }) => {
    await conSeleccion(page);

    await page.locator('#wm-plantilla').fill('Campaña ');
    await page.getByRole('button', { name: '{fecha_corte}', exact: true }).click();

    await expect(page.locator('#wm-plantilla')).toHaveValue('Campaña {fecha_corte}');
    await expect(page.locator('#wm-variables-hint')).toContainText('{fecha_corte}: la fecha de corte, como AAAA.MM.DD.');
  });

  test('una plantilla sin {segmento} en un lote lo dice (DU-WM-6) y el nombre resultante lleva el segmento al final', async ({ page }) => {
    await conSeleccion(page);

    await page.locator('#wm-plantilla').fill('Campaña {fecha_corte}');

    await expect(page.locator('[data-segmento-al-final]')).toBeVisible();
    await expect(page.locator('[data-nombre-resultante]')).toHaveText('Campaña 2026.09.13 Preventivo');
  });

  test('un nombre de más de 75 caracteres, o una variable que no existe, son problemas', async ({ page }) => {
    // A long label makes a long name: the template is under its 75, the name it gives is not (35 + 41 = 76).
    const etiquetas = { preventivo: 'Preventivo de la campaña de octubre', tramo_2: 'Tramo 2', mayores_2: 'Tramos mayores al 2' };
    await conSeleccion(page, apiConfigurada(), campanaFalsa({ etiquetas }));
    await page.locator('[data-franja="horario_1"]').check();

    await page.locator('#wm-plantilla').fill(`${'a'.repeat(41)}{segmento}`);
    await expect(page.locator('[data-contador]')).toHaveText('76 / 75');
    await expect(page.locator('[data-contador]')).toHaveAttribute('data-excede', 'true');
    await expect(problemas(page).filter({ hasText: 'El nombre tiene 76 caracteres: el máximo es 75.' })).toHaveCount(1);

    await page.locator('#wm-plantilla').fill('Campaña {fecha}');
    await expect(problemas(page).filter({ hasText: 'La variable {fecha} no existe.' })).toHaveCount(1);
  });
});

test.describe('previsualización', () => {
  test('resume el lote, y un .segmented elige la campaña con sus cifras, su nombre y su mensaje de ejemplo', async ({ page }) => {
    await conSeleccion(page);

    await expect(resumen(page)).toContainText('Se crearán 2 campañas');
    await expect(resumen(page)).toContainText(/1[.,]000 filas en total/);
    await expect(resumen(page).getByRole('link', { name: '3 productos fuera de las campañas' })).toHaveAttribute('href', '#wm-fuera-titulo');
    // The segment with no products is not in the selector.
    const botones = page.locator('[data-campanas] button');
    await expect(botones).toHaveText(['Preventivo (520)', 'Tramo 2 (480)']);
    await expect(botones.first()).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('[data-cifras]')).toContainText('Filas del archivo');
    await expect(page.locator('[data-cifras]')).toContainText('520');
    await expect(page.locator('[data-nombre-rotulo]')).toHaveText('Nombre de la campaña Preventivo:');
    await expect(page.locator('[data-nombre-resultante]')).toHaveText('CUZCO_Vencida (Preventivo) whatsapp 2026.09.13');
    await expect(page.locator('[data-ejemplo-bloque] h3')).toHaveText('Así lo verá el cliente');
    // The text is kept as written: line breaks and double spaces.
    await expect(page.locator('[data-ejemplo]')).toHaveCSS('white-space', 'pre-wrap');

    await botones.nth(1).click();

    await expect(botones.nth(1)).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('[data-cifras]')).toContainText('480');
    await expect(page.locator('[data-nombre-resultante]')).toHaveText('CUZCO_Vencida (Tramo 2) whatsapp 2026.09.13');
  });

  test('la muestra lleva el nombre de cada columna con su etiqueta debajo, y las filas de supervisión su marca', async ({ page }) => {
    await conSeleccion(page);

    const cabeceras = page.locator('[data-muestra] thead th');
    await expect(cabeceras.nth(0)).toContainText('número');
    await expect(cabeceras.nth(0)).toContainText('Número con prefijo');
    await expect(cabeceras.nth(1)).toContainText('[$MACRO1$]');
    await expect(cabeceras.nth(1)).toContainText('Nombres del titular');
    // Every column of the definition is there, the one with no label too.
    await expect(cabeceras).toHaveCount(3);
    await expect(cabeceras.nth(2)).toContainText('[$MACRO2$]');
    const filas = page.locator('[data-muestra] tbody tr');
    await expect(filas).toHaveCount(4);
    await expect(filas.nth(0).locator('.tag')).toHaveText('Supervisión');
    await expect(filas.nth(2).locator('.tag')).toHaveCount(0);
  });

  test('las exclusiones se paginan de a 10, con el motivo en una marca y el detalle', async ({ page }) => {
    await conSeleccion(page);

    const filas = page.locator('[data-exclusiones] tbody tr');
    await expect(filas).toHaveCount(10);
    await expect(filas.first().locator('.tag')).toHaveText('Sin teléfono');
    // The sentence is the one of its code, not the server's own (that one is the fallback for a code with no key).
    await expect(filas.first()).toContainText('No tiene un teléfono registrado.');
    await expect(page.locator('[data-exclusiones-pager] [data-page-range]')).toContainText('1');
    // The detail of a product out of every campaign reads whole, with its two sentences.
    await expect(page.locator('[data-fuera-tabla] tbody tr').first()).toContainText('No tiene días de atraso, así que no cae en ningún segmento. En el modo «Global» sí entraría.');

    await page.locator('[data-exclusiones-pager] [data-page-next]').click();

    await expect(filas).toHaveCount(2);
    await expect(page.locator('[data-exclusiones-pager] [data-page-next]')).toBeDisabled();
  });

  test('los productos fuera de las campañas van aparte, no cambian con la campaña y no salen en el modo global', async ({ page }) => {
    await conSeleccion(page, apiConfigurada(), campanaFalsa({ fuera: { total: 120, listadas: 100 } }));

    await expect(page.locator('[data-fuera-titulo]')).toHaveText('Productos fuera de las campañas (120)');
    await expect(page.locator('[data-fuera-truncadas]')).toContainText('Se muestran las primeras 100 de 120.');
    await expect(page.locator('[data-fuera-tabla] tbody tr')).toHaveCount(10);
    await page.locator('[data-campanas] button').nth(1).click();
    await expect(page.locator('[data-fuera-titulo]')).toHaveText('Productos fuera de las campañas (120)');

    await page.getByRole('button', { name: 'Global' }).click();

    await expect(page.locator('[data-fuera]')).toBeHidden();
  });

  test('una exclusión sin ninguna dice que ninguno queda fuera', async ({ page }) => {
    await conSeleccion(page, apiConfigurada(), campanaFalsa({ exclusiones: 0, fuera: { total: 0, listadas: 0 } }));

    await expect(page.locator('[data-exclusiones]')).toContainText('Ninguno de esta campaña queda fuera.');
    await expect(page.locator('[data-fuera]')).toBeHidden();
  });

  test('si ningún segmento tiene productos, en vez de la previsualización va un aviso y no se puede crear', async ({ page }) => {
    const campana = campanaFalsa({
      respuestasPrevia: [
        {
          estado: 200,
          cuerpo: {
            campanas: [],
            problemas: [{ codigo: 'sin_productos', detalle: 'sin productos', segmento: null, parametros: {} }],
            disponibles: 0,
            solicitados: 1000,
            total_exclusiones: 0,
            total_exclusiones_sin_campana: 0,
            exclusiones_sin_campana: [],
          },
        },
      ],
    });
    await abrir(page, apiConfigurada(), campana);
    await page.getByLabel('Selección guardada').selectOption({ label: 'Preventiva top 1000' });

    await expect(page.locator('[data-sin-campanas]')).toContainText('Ningún segmento tiene productos después de las exclusiones');
    await expect(page.locator('[data-campana]')).toBeHidden();
    await expect(crear(page)).toBeDisabled();
  });

  test('si la previsualización falla, lo dice en el panel y nada más se rompe', async ({ page }) => {
    const campana = campanaFalsa({ respuestasPrevia: [{ estado: 500, cuerpo: { detail: 'No se pudo calcular el lote' } }] });
    await abrir(page, apiConfigurada(), campana);
    await page.getByLabel('Selección guardada').selectOption({ label: 'Preventiva top 1000' });

    await expect(page.locator('[data-previa-error]')).toHaveText('No se pudo calcular el lote');
    await expect(page.locator('#wm-definicion')).toBeEnabled();
  });
});

test.describe('los problemas y «Crear»', () => {
  test('con problemas, «Crear» está apagado con el motivo; cada problema tiene su enlace; ninguno llama a crear', async ({ page }) => {
    const campana = campanaFalsa({
      problemasExtra: [
        { codigo: 'sin_supervisores', detalle: 'Sin supervisores', segmento: null, parametros: {} },
        { codigo: 'sin_whatsapp', detalle: 'Sin WhatsApp', segmento: 'tramo_2', parametros: {} },
      ],
    });
    const { api } = await conSeleccion(page, apiConfigurada(), campana);

    await expect(crear(page)).toBeDisabled();
    await expect(crear(page)).toContainText('Crear 2 campañas');
    // The horario is also missing: three problems in all.
    await expect(page.locator('[data-crear-motivo]')).toHaveText('Corrige 3 problemas para crear.');
    // It reads as a hint (small, muted, sans), like «Disponible pronto.», not as data.
    await expect(page.locator('[data-crear-motivo]')).toHaveClass(/field__hint/);
    await expect(page.locator('[data-crear-motivo]')).not.toHaveClass(/mono/);
    await expect(page.getByRole('link', { name: 'Configurar supervisores' })).toHaveAttribute('href', /^\/supervisores\?volver=%2Fwhatsmkt%2Fcampana%3Fseleccion%3D\d+$/);
    await expect(page.getByRole('link', { name: 'Configurar el WhatsApp de contacto' })).toHaveAttribute('href', '/whatsmkt/configuracion#wm-whatsapp');
    expect(api.pedidos.filter((p) => p.metodo === 'POST' && p.ruta === '/whatsmkt/campanas')).toHaveLength(0);
  });

  test('sin problemas «Crear» está activo y, sin pedirlo, no crea nada', async ({ page }) => {
    const { api } = await conSeleccion(page);
    await page.locator('[data-franja="horario_1"]').check();

    await expect(problemas(page)).toHaveCount(0);
    await expect(crear(page)).toBeEnabled();
    await expect(page.locator('[data-crear-motivo]')).toBeEmpty();
    expect(api.pedidos.filter((p) => p.metodo === 'POST' && p.ruta === '/whatsmkt/campanas')).toHaveLength(0);
  });

  test('en una campaña global «Crear» dice «Crear campaña»', async ({ page }) => {
    await conSeleccion(page);

    await page.getByRole('button', { name: 'Global' }).click();
    await page.locator('#wm-mensaje-global').selectOption({ label: 'Oferta de octubre' });

    await expect(crear(page)).toContainText('Crear campaña');
    await expect(resumen(page)).toContainText('Se creará 1 campaña');
  });
});

test.describe('pantalla angosta e inglés', () => {
  test('a 360 px la página no desborda y las tablas se apilan', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    await conSeleccion(page);

    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
    const encabezado = (await page.locator('[data-columnas-tabla] tbody tr').first().locator('td').nth(0).boundingBox())!;
    const siguiente = (await page.locator('[data-columnas-tabla] tbody tr').first().locator('td').nth(1).boundingBox())!;
    // Stacked: each cell under the other.
    expect(siguiente.y).toBeGreaterThan(encabezado.y + encabezado.height - 1);
  });

  test('en inglés se traduce lo dibujado por el script', async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' })));
    await abrir(page);
    await page.getByLabel('Saved selection').selectOption({ label: 'Preventiva top 1000' });
    await expect(page.locator('[data-campana]')).toBeVisible();

    await expect(page.locator('h2.panel__title')).toContainText(['Selection', 'Load file', 'Message', 'Scheduling', 'Sending', 'Campaign name', 'Preview']);
    await expect(resumen(page)).toContainText('2 campaigns will be created');
    await expect(page.locator('[data-ejemplo-bloque] h3')).toHaveText('This is how the customer will see it');
  });
});

/**
 * Creating the lot of a WhatsMKT campaign, the card to upload it and the uploads from the campaign (T-WM-F2a2), end to end against an
 * intercepted API: the exact version of each message in the request, the 409 of a date that went stale, the failures at the top, «Copiar»,
 * the downloads, and an upload that is new, repeated, archived or refused. The clock is fixed from the first spec, in `montarApiWhatsmkt`.
 * Every text and number is invented.
 */
import { expect, test, type Page } from '@playwright/test';

import { apiWhatsmkt, montarApiWhatsmkt, type ApiFalsaWhatsmkt } from './api-falsa-whatsmkt';
import { campanaFalsa, montarCampanaWhatsmkt, texto, type CampanaFalsa } from './api-falsa-whatsmkt-campana';
import { montarSeleccion } from './apoyo-seleccion';

const RUTA = '/whatsmkt/campana';

/** The default definition is chosen and the first two segments own their message, as the seed leaves them. */
function apiConfigurada(): ApiFalsaWhatsmkt {
  const api = apiWhatsmkt();
  api.configuracion.definicion_defecto_id = 11;
  api.segmentos[0].texto_guardado_id = 101;
  api.segmentos[1].texto_guardado_id = 102;
  return api;
}

/** The messages have versions of their own, so a request that said «the latest» instead of the exact one would not match. */
const conVersiones = (parcial: Partial<CampanaFalsa> = {}) =>
  campanaFalsa({
    textos: [texto(101, 'Preventivo', { version_vigente: 3 }), texto(102, 'Tramo 2'), texto(103, 'Oferta de octubre', { version_vigente: 2 })],
    ...parcial,
  });

async function conSeleccion(
  page: Page,
  api = apiConfigurada(),
  campana = conVersiones(),
): Promise<{ api: ApiFalsaWhatsmkt; campana: CampanaFalsa }> {
  await montarApiWhatsmkt(page, api);
  await montarCampanaWhatsmkt(page, campana);
  await montarSeleccion(page);
  await page.goto(RUTA);
  await page.getByLabel('Selección guardada').selectOption({ label: 'Preventiva top 1000' });
  await expect(page.locator('[data-campana]')).toBeVisible();
  return { api, campana };
}

const crear = (page: Page) => page.locator('[data-crear]');
const ficha = (page: Page) => page.locator('#wm-sec-ficha');
const alerta = (page: Page) => page.locator('[data-crear-error]');
const campos = (page: Page) => ficha(page).locator('.wm-ficha__dato');
const pedidosA = (api: ApiFalsaWhatsmkt, metodo: string, ruta: string) =>
  api.pedidos.filter((p) => p.metodo === metodo && p.ruta.split('?')[0] === ruta);

/** Marks the first time slot, so nothing stops creating, and creates. */
async function crearLote(page: Page): Promise<void> {
  await page.locator('[data-franja="horario_1"]').check();
  await expect(crear(page)).toBeEnabled();
  await crear(page).click();
}

test.describe('crear el lote', () => {
  test('por segmento: cada mensaje va con su versión EXACTA, y aparece la ficha de las dos campañas', async ({ page }) => {
    const { campana } = await conSeleccion(page);

    await crearLote(page);

    await expect(ficha(page)).toBeVisible();
    expect(campana.creaciones).toHaveLength(1);
    expect(campana.creaciones[0].mensajes).toEqual({
      preventivo: { texto_guardado_id: 101, version: 3 },
      tramo_2: { texto_guardado_id: 102, version: 1 },
    });
    expect(campana.creaciones[0]).toMatchObject({ modo: 'por_segmento', horarios: ['horario_1'], lo_antes_posible: false, tipo_envio: 'solo_texto' });
    expect(Object.keys(campana.creaciones[0].nombres ?? {})).toEqual(['preventivo', 'tramo_2']);
    await expect(ficha(page).locator('.notice--success')).toContainText('Se crearon 2 campañas (lote 12). Ahora súbelas a WhatsMKT con estos datos.');
    await expect(ficha(page).locator('[data-ficha-campanas] button')).toHaveText(['Preventivo', 'Tramo 2']);
  });

  test('la ficha trae cada dato del formulario en su orden, y el segmented cambia de campaña', async ({ page }) => {
    await conSeleccion(page);
    await crearLote(page);

    await expect(campos(page).locator('dt')).toHaveText([
      'Nombre de campaña',
      'Fecha y horarios',
      'Lo antes posible',
      'País',
      '¿Cuántos teléfonos tiene en su Lista de contactos?',
      'Tipo de envío',
      'Texto del mensaje',
    ]);
    await expect(campos(page).nth(1).locator('.wm-ficha__valor')).toHaveText('16/10/2026 · Horario 1 (08:00 – 14:00)');
    await expect(campos(page).nth(2).locator('.wm-ficha__valor')).toHaveText('No');
    await expect(campos(page).nth(3).locator('.wm-ficha__valor')).toHaveText('Perú');
    await expect(campos(page).nth(4).locator('.wm-ficha__valor')).toHaveText('520');
    await expect(campos(page).nth(5).locator('.wm-ficha__valor')).toHaveText('Solo texto');
    await expect(ficha(page).locator('[data-ficha-seguimiento]')).toHaveAttribute('href', '/whatsmkt/seguimiento?campana=37');

    await ficha(page).locator('[data-ficha-campanas] button').nth(1).click();

    await expect(campos(page).nth(4).locator('.wm-ficha__valor')).toHaveText('480');
    await expect(ficha(page).locator('[data-ficha-seguimiento]')).toHaveAttribute('href', '/whatsmkt/seguimiento?campana=38');
    await expect(ficha(page).locator('[data-ficha-campanas] button').nth(1)).toBeFocused();
  });

  test('global: un solo mensaje con su versión, una sola campaña y sin segmented', async ({ page }) => {
    const { campana } = await conSeleccion(page);
    await page.locator('button[data-modo="global"]').click();
    await page.locator('#wm-mensaje-global').selectOption({ label: 'Oferta de octubre' });

    await crearLote(page);

    await expect(ficha(page)).toBeVisible();
    expect(campana.creaciones[0].mensaje).toEqual({ texto_guardado_id: 103, version: 2 });
    expect(campana.creaciones[0].mensajes).toBeUndefined();
    expect(typeof campana.creaciones[0].nombre).toBe('string');
    await expect(ficha(page).locator('.notice--success')).toContainText('Se creó la campaña 37.');
    await expect(ficha(page).locator('[data-ficha-campanas]')).toBeHidden();
  });

  test('después de crear, la ficha reemplaza la previsualización, «Crear» ya no está, el formulario queda inactivo y «Armar otra campaña» recarga', async ({ page }) => {
    const { campana } = await conSeleccion(page);
    await crearLote(page);
    await expect(ficha(page)).toBeVisible();

    await expect(page.locator('[data-previa]')).toBeHidden();
    await expect(crear(page)).toBeHidden();
    await expect(page.locator('#wm-sec-programacion')).toHaveAttribute('inert', '');
    await expect(page.locator('[data-selector]')).toHaveAttribute('inert', '');
    // Inactive but readable: what was created is still read, so the text keeps its normal contrast (no opacity).
    await expect(page.locator('#wm-sec-programacion')).toHaveCSS('opacity', '1');
    await expect(page.locator('[data-selector]')).toHaveCSS('opacity', '1');
    expect(campana.creaciones).toHaveLength(1);

    await page.getByRole('button', { name: 'Armar otra campaña' }).click();

    // It reloads: a clean page, with no selection chosen and no card.
    await expect(page.locator('[data-guardia]')).toBeVisible();
    await expect(ficha(page)).toBeHidden();
  });

  test('el POST lleva el texto y la versión que se previsualizaron, y la ficha muestra el texto de esa versión', async ({ page }) => {
    const { campana } = await conSeleccion(page);
    // «Así lo verá el cliente» already shows the version 3 of the message of Preventivo.
    await expect(page.locator('[data-ejemplo]')).toHaveText('Hola Maria, Preventivo: tu saldo es 1500.50. INFO por https://wa.me/+51900000123 (v3)');

    await crearLote(page);

    expect(campana.creaciones[0].mensajes?.preventivo).toEqual({ texto_guardado_id: 101, version: 3 });
    expect(campana.creaciones[0].mensajes?.tramo_2).toEqual({ texto_guardado_id: 102, version: 1 });
    const mensaje = campos(page).nth(6).locator('.wm-ficha__valor');
    await expect(mensaje).toHaveText('Hola [$MACRO1$], Preventivo: tu saldo es [$MACRO2$]. INFO por https://wa.me/+51900000123 (v3)');
    await ficha(page).locator('[data-ficha-campanas] button').nth(1).click();
    await expect(mensaje).toHaveText('Hola [$MACRO1$], Tramo 2: tu saldo es [$MACRO2$]. INFO por https://wa.me/+51900000123');
  });

  test('con «Texto + archivo» y una foto, el pedido lleva el archivo y la foto, y la ficha los ofrece para descargar', async ({ page }) => {
    const { api, campana } = await conSeleccion(page);
    await page.getByLabel('Texto + archivo').check();
    await page.locator('#wm-adjunto').selectOption({ label: 'afiche-octubre.jpg · Imagen JPEG · 240 KB' });
    await page.locator('#wm-foto').selectOption({ label: 'afiche-octubre.jpg · Imagen JPEG · 240 KB' });

    await crearLote(page);

    await expect(ficha(page)).toBeVisible();
    expect(campana.creaciones[0]).toMatchObject({ tipo_envio: 'archivo', adjunto_id: 1, foto_id: 1 });
    expect(campana.creaciones[0].etiqueta_vcard).toBeUndefined();
    await expect(campos(page).nth(5).locator('.wm-ficha__valor')).toHaveText('Texto + imagen');
    await expect(ficha(page).locator('.wm-ficha__archivo')).toHaveCount(3);
    // The photo and the attachment are the same file here: each row says what it is.
    await expect(ficha(page).locator('.wm-ficha__rotulo')).toHaveText(['Lista de contactos', 'Foto de perfil', 'Adjunto']);

    // The contact list is the campaign's own file; the photo and the attachment come from the library.
    const delArchivo = page.waitForEvent('download');
    await ficha(page).locator('.wm-ficha__archivo button').first().click();
    expect((await delArchivo).suggestedFilename()).toBe('campana-37.xlsx');
    expect(campana.descargas).toEqual([37]);
    const delAdjunto = page.waitForEvent('download');
    await ficha(page).locator('.wm-ficha__archivo button').nth(2).click();
    expect((await delAdjunto).suggestedFilename()).toBe('afiche-octubre.jpg');
    expect(pedidosA(api, 'GET', '/whatsmkt/adjuntos/1/contenido').length).toBeGreaterThan(0);
  });

  test('a 360 px «Copiar» va en la fila del dato y el valor ocupa todo el ancho debajo', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    await conSeleccion(page);
    await crearLote(page);
    await expect(ficha(page)).toBeVisible();

    const cajas = await campos(page).nth(6).evaluate((dato) => {
      const caja = (selector: string) => dato.querySelector(selector)!.getBoundingClientRect();
      const dt = caja('dt');
      const boton = caja('button');
      const valor = caja('.wm-ficha__valor');
      return { dt: { arriba: dt.top, abajo: dt.bottom }, boton: { arriba: boton.top, abajo: boton.bottom, derecha: boton.right }, valor: { arriba: valor.top, ancho: valor.width }, dato: dato.getBoundingClientRect().width };
    });
    // The button is on the row of the name, to its right; the value starts under both and is as wide as the datum, not squeezed beside the button.
    expect(cajas.boton.arriba).toBeLessThan(cajas.dt.abajo);
    expect(cajas.boton.abajo).toBeGreaterThan(cajas.dt.arriba);
    expect(cajas.valor.arriba).toBeGreaterThanOrEqual(Math.max(cajas.dt.abajo, cajas.boton.abajo) - 1);
    expect(cajas.valor.ancho).toBeGreaterThan(cajas.dato * 0.8);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360);
  });

  test('un mensaje con [whatsapp] y sin número configurado lo avisa en la ficha', async ({ page }) => {
    await conSeleccion(page, apiConfigurada(), conVersiones({ avisosFicha: ['sin_whatsapp'] }));
    await crearLote(page);

    await expect(ficha(page).locator('[data-ficha-avisos]')).toHaveText('El mensaje usa [whatsapp] y no hay WhatsApp de contacto configurado.');
  });

  test('«Copiar» deja el dato en el portapapeles y lo anuncia', async ({ page }) => {
    await page.context().grantPermissions(['clipboard-read', 'clipboard-write']);
    await conSeleccion(page);
    await crearLote(page);

    await ficha(page).getByRole('button', { name: 'Copiar Texto del mensaje' }).click();

    await expect(ficha(page).locator('[data-ficha-copia-estado]')).toHaveText('Copiado: Texto del mensaje');
    const copiado = await page.evaluate(() => navigator.clipboard.readText());
    expect(copiado).toContain('https://wa.me/+51900000123');
    expect(copiado).toContain('[$MACRO1$]');
  });

  test('con el portapapeles bloqueado, «Copiar» deja el texto seleccionado y lo dice', async ({ page }) => {
    // What a browser does with a page it does not trust: the async clipboard rejects and the classic copy refuses.
    await page.addInitScript(() => {
      Object.defineProperty(navigator, 'clipboard', {
        value: { writeText: () => Promise.reject(new DOMException('bloqueado', 'NotAllowedError')) },
        configurable: true,
      });
      document.execCommand = () => false;
    });
    await conSeleccion(page);
    await crearLote(page);

    await ficha(page).getByRole('button', { name: 'Copiar Texto del mensaje' }).click();

    await expect(ficha(page).locator('[data-ficha-copia-estado]')).toHaveText('No se pudo copiar Texto del mensaje. Quedó seleccionado: cópialo con Ctrl+C.');
    const seleccionado = await page.evaluate(() => window.getSelection()?.toString() ?? '');
    expect(seleccionado).toContain('https://wa.me/+51900000123');
    expect(seleccionado).toContain('[$MACRO1$]');
  });
});

test.describe('cuando no se puede crear', () => {
  test('una fecha que dejó de ser gestionable (409) ofrece la siguiente, y lo escrito se conserva', async ({ page }) => {
    const campana = conVersiones({
      respuestasCrear: [{ estado: 409, cuerpo: { detail: 'La fecha ya no es gestionable', codigo: 'fecha_no_gestionable', fecha: '2026-10-16', sugerida: '2026-10-17' } }],
    });
    await conSeleccion(page, apiConfigurada(), campana);
    await page.locator('#wm-mensaje-tramo_2').selectOption({ label: 'Oferta de octubre' });

    await crearLote(page);

    await expect(ficha(page)).toBeHidden();
    const aviso = page.locator('[data-fecha-vencida]');
    await expect(aviso).toBeVisible();
    await expect(aviso).toContainText(/ya no es un día gestionable\. El siguiente es el 17/);
    await aviso.getByRole('button', { name: /Usar el 17/ }).click();

    await expect(page.locator('#wm-fecha')).toHaveValue('2026-10-17');
    await expect(aviso).toBeHidden();
    await expect(page.locator('#wm-mensaje-tramo_2')).toHaveValue('103');
    await expect(crear(page)).toBeEnabled();
  });

  test('lo que impide crear (422) va arriba, en un alert, con cada problema, y no se crea nada', async ({ page }) => {
    const campana = conVersiones({
      respuestasCrear: [
        {
          estado: 422,
          cuerpo: {
            detail: 'Algo impide crear',
            codigo: 'sin_supervisores',
            problemas: [{ codigo: 'sin_supervisores', detalle: 'Sin supervisores', segmento: null, parametros: {} }],
          },
        },
      ],
    });
    await conSeleccion(page, apiConfigurada(), campana);

    await crearLote(page);

    await expect(alerta(page)).toBeVisible();
    await expect(alerta(page)).toHaveAttribute('role', 'alert');
    await expect(alerta(page)).toContainText('No hay supervisores configurados: sin ellos no se crea la campaña.');
    await expect(alerta(page)).toBeFocused();
    await expect(ficha(page)).toBeHidden();
    await expect(crear(page)).toBeEnabled();
  });

  test('otro rechazo (400) dice su motivo arriba, y un intento que sale bien lo quita', async ({ page }) => {
    const campana = conVersiones({
      respuestasCrear: [{ estado: 400, cuerpo: { detail: 'La fecha de envío es anterior a la de corte', codigo: 'fecha_envio_anterior' } }, { estado: 201, cuerpo: [] }],
    });
    await conSeleccion(page, apiConfigurada(), campana);

    await crearLote(page);
    await expect(alerta(page)).toContainText('La fecha de envío es anterior a la de corte');

    await crear(page).click();
    await expect(alerta(page)).toBeHidden();
  });
});

test.describe('subir desde la campaña', () => {
  const subirArchivo = (page: Page, nombre: string, propósito: 'adjunto' | 'foto' = 'adjunto') =>
    page.locator(`[data-subir-entrada="${propósito}"]`).setInputFiles({ name: nombre, mimeType: 'application/octet-stream', buffer: Buffer.from('sintetico') });
  const estado = (page: Page, propósito: 'adjunto' | 'foto' = 'adjunto') => page.locator(`[data-subir-estado="${propósito}"]`);

  test('un archivo nuevo queda en la biblioteca y elegido; una imagen suma que se guardó sin metadatos', async ({ page }) => {
    await conSeleccion(page);
    await page.getByLabel('Texto + archivo').check();

    await subirArchivo(page, 'nuevo.pdf');

    await expect(estado(page)).toHaveText('Subido y elegido: nuevo.pdf.');
    await expect(page.locator('#wm-adjunto')).toHaveValue('4');
    await expect(page.locator('#wm-adjunto option:checked')).toContainText('nuevo.pdf');

    await subirArchivo(page, 'nueva.jpg');
    await expect(estado(page)).toHaveText('Subido y elegido: nueva.jpg. Se guardó sin metadatos (EXIF, ubicación).');
  });

  test('uno que ya estaba se elige sin duplicarlo y lo dice', async ({ page }) => {
    const { api } = await conSeleccion(page);
    await page.getByLabel('Texto + archivo').check();

    await subirArchivo(page, 'tarifario.pdf');

    await expect(estado(page)).toHaveText('Ya estaba en la biblioteca: se usa el mismo archivo.');
    await expect(page.locator('#wm-adjunto')).toHaveValue('2');
    expect(api.adjuntos).toHaveLength(3);
  });

  test('uno que ya estaba ARCHIVADO no se restaura solo: se ofrece «Restaurar y usar», que lo restaura y lo elige', async ({ page }) => {
    const { api } = await conSeleccion(page);
    await page.getByLabel('Texto + archivo').check();

    await subirArchivo(page, 'spot-anterior.mp4');

    await expect(estado(page)).toHaveText('Ya estaba en la biblioteca, archivado: spot-anterior.mp4.');
    await expect(page.locator('#wm-adjunto')).toHaveValue('');
    const restaurar = page.getByRole('button', { name: 'Restaurar y usar' }).first();
    await expect(restaurar).toBeVisible();

    await restaurar.click();

    expect(pedidosA(api, 'POST', '/whatsmkt/adjuntos/3/desarchivar')).toHaveLength(1);
    await expect(page.locator('#wm-adjunto')).toHaveValue('3');
    await expect(restaurar).toBeHidden();
    await expect(estado(page)).toHaveText('Subido y elegido: spot-anterior.mp4.');
  });

  test('un archivo que WhatsMKT no admite dice su motivo por código, bajo su select', async ({ page }) => {
    await conSeleccion(page);
    await page.getByLabel('Texto + archivo').check();

    await subirArchivo(page, 'datos.txt');

    await expect(page.locator('[data-subir-error="adjunto"]')).toHaveText('WhatsMKT no admite este tipo de archivo. Sube una imagen, un video, un audio o un PDF.');
    await expect(page.locator('#wm-adjunto')).toHaveAttribute('aria-invalid', 'true');
    await expect(page.locator('#wm-adjunto')).toHaveValue('');
  });

  test('«Subir una foto» deja la foto elegida en su select', async ({ page }) => {
    await conSeleccion(page);

    await subirArchivo(page, 'foto-perfil.jpg', 'foto');

    await expect(estado(page, 'foto')).toContainText('Subido y elegido: foto-perfil.jpg.');
    await expect(page.locator('#wm-foto option:checked')).toContainText('foto-perfil.jpg');
  });

  test('con la biblioteca vacía el select espera y, al subir, se enciende con el archivo elegido', async ({ page }) => {
    const api = apiConfigurada();
    api.adjuntos = [];
    await conSeleccion(page, api);
    await page.getByLabel('Texto + archivo').check();
    await expect(page.locator('#wm-adjunto')).toBeDisabled();

    await subirArchivo(page, 'primero.pdf');

    await expect(page.locator('#wm-adjunto')).toBeEnabled();
    await expect(page.locator('#wm-adjunto option:checked')).toContainText('primero.pdf');
  });
});

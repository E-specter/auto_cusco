/**
 * WhatsMKT configuration, T-WM-F1b1: the contact WhatsApp and the default definition, end to end against an
 * intercepted API. The clock is fixed from the first spec, in `montarApiWhatsmkt`. Every number is synthetic (900000xxx).
 */
import { expect, test, type Page } from '@playwright/test';

import { json } from './apoyo';
import { apiWhatsmkt, definicionSintetica, errorWhatsmkt, montarApiWhatsmkt, type ApiFalsaWhatsmkt } from './api-falsa-whatsmkt';
import { mensajesFalsos, montarMensajesWhatsmkt } from './api-falsa-whatsmkt-mensajes';

const RUTA = '/whatsmkt/configuracion';

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

const whatsapp = (page: Page) => page.locator('#wm-whatsapp');
const errorWhatsapp = (page: Page) => page.locator('[data-whatsapp-error]');
const definicion = (page: Page) => page.locator('#wm-definicion');
const errorDefinicion = (page: Page) => page.locator('[data-definicion-error]');
const guardar = (page: Page, nombre: string) => page.getByRole('button', { name: nombre });

test.describe('WhatsApp de contacto', () => {
  test('el campo es de 9 dígitos y, vacío, el panel avisa que [whatsapp] no se puede enviar', async ({ page }) => {
    await abrir(page, apiWhatsmkt());

    await expect(whatsapp(page)).toHaveAttribute('inputmode', 'numeric');
    await expect(whatsapp(page)).toHaveAttribute('maxlength', '9');
    await expect(whatsapp(page)).toHaveAttribute('autocomplete', 'off');
    await expect(whatsapp(page)).toHaveValue('');
    const aviso = page.locator('[data-sin-whatsapp]');
    await expect(aviso).toHaveClass(/notice--warning/);
    await expect(aviso).toHaveText('Sin WhatsApp de contacto, los mensajes que usan [whatsapp] no se pueden enviar.');
    // The hint says what the number is for, and it is tied to the field.
    await expect(page.locator('#wm-whatsapp-hint')).toContainText('https://wa.me/+51');
    await expect(whatsapp(page)).toHaveAttribute('aria-describedby', 'wm-whatsapp-hint wm-whatsapp-error');
    // The panel's title already says «WhatsApp de contacto»: the field's label is only «Número», not the title twice.
    await expect(page.locator('label[for="wm-whatsapp"]')).toHaveText('Número');
    await expect(page.getByRole('heading', { name: 'WhatsApp de contacto' })).toBeVisible();
  });

  test('guarda el número y manda solo ese campo; el aviso se va', async ({ page }) => {
    const api = apiWhatsmkt();
    await abrir(page, api);

    await whatsapp(page).fill('900000123');
    await guardar(page, 'Guardar WhatsApp').click();

    await expect(page.locator('[data-whatsapp-estado]')).toHaveText('Guardado.');
    expect(pedidosA(api, 'PUT', '/whatsmkt/configuracion').at(-1)?.cuerpo).toEqual({ whatsapp_contacto: '900000123' });
    await expect(page.locator('[data-sin-whatsapp]')).toBeHidden();
    expect(api.configuracion.whatsapp_contacto).toBe('900000123');
  });

  test('vaciar el campo borra el número (null) y el aviso vuelve', async ({ page }) => {
    const api = apiWhatsmkt();
    api.configuracion.whatsapp_contacto = '900000123';
    await abrir(page, api);
    await expect(whatsapp(page)).toHaveValue('900000123');
    await expect(page.locator('[data-sin-whatsapp]')).toBeHidden();

    await whatsapp(page).fill('');
    await guardar(page, 'Guardar WhatsApp').click();

    expect(pedidosA(api, 'PUT', '/whatsmkt/configuracion').at(-1)?.cuerpo).toEqual({ whatsapp_contacto: null });
    await expect(page.locator('[data-sin-whatsapp]')).toBeVisible();
  });

  test('un número mal escrito se dice al salir del campo, bajo el campo, y no se guarda', async ({ page }) => {
    const api = apiWhatsmkt();
    await abrir(page, api);

    // 9 digits, but it does not start with 9.
    await whatsapp(page).fill('812345678');
    await whatsapp(page).blur();

    await expect(errorWhatsapp(page)).toHaveText('El WhatsApp debe tener 9 dígitos y empezar con 9.');
    await expect(whatsapp(page)).toHaveAttribute('aria-invalid', 'true');
    await guardar(page, 'Guardar WhatsApp').click();
    await expect(whatsapp(page)).toBeFocused();
    expect(pedidosA(api, 'PUT', '/whatsmkt/configuracion')).toHaveLength(0);

    // Writing it right takes the error away without leaving the field.
    await whatsapp(page).fill('900000123');
    await expect(errorWhatsapp(page)).toBeEmpty();
  });

  test('salir de un campo inválido directo a Guardar: un solo clic basta y el foco va al error', async ({ page }) => {
    const api = apiWhatsmkt();
    await abrir(page, api);

    await whatsapp(page).fill('12');
    await guardar(page, 'Guardar WhatsApp').click();

    await expect(errorWhatsapp(page)).toHaveText('El WhatsApp debe tener 9 dígitos y empezar con 9.');
    await expect(whatsapp(page)).toBeFocused();
    expect(pedidosA(api, 'PUT', '/whatsmkt/configuracion')).toHaveLength(0);
  });

  test('si la API lo rechaza (whatsapp_invalido), el error va bajo el campo', async ({ page }) => {
    const api = apiWhatsmkt();
    api.respuestas.guardarConfiguracion = [{ estado: 422, cuerpo: errorWhatsmkt('whatsapp_invalido') }];
    await abrir(page, api);

    await whatsapp(page).fill('900000123');
    await guardar(page, 'Guardar WhatsApp').click();

    await expect(errorWhatsapp(page)).toHaveText('El WhatsApp debe tener 9 dígitos y empezar con 9.');
    await expect(whatsapp(page)).toBeFocused();
  });

  test('un fallo que no es del campo va al panel, y lo escrito se conserva', async ({ page }) => {
    const api = apiWhatsmkt();
    api.respuestas.guardarConfiguracion = [{ estado: 500, cuerpo: { detail: 'La base no respondió' } }];
    await abrir(page, api);

    await whatsapp(page).fill('900000123');
    await guardar(page, 'Guardar WhatsApp').click();

    await expect(page.locator('[data-whatsapp-general]')).toHaveText('La base no respondió');
    await expect(whatsapp(page)).toHaveValue('900000123');
  });
});

test.describe('definición por defecto', () => {
  test('ofrece «sin definición» y solo las de plataforma WhatsMKT', async ({ page }) => {
    await abrir(page, apiWhatsmkt());

    await expect(definicion(page).locator('option')).toHaveText([
      'Sin definición por defecto',
      'Contactos WhatsMKT',
      'Contactos WhatsMKT con apellido',
    ]);
    await expect(definicion(page)).toHaveValue('');
    // The one of another platform is not offered.
    await expect(definicion(page).locator('option', { hasText: 'Carga SMS de MES' })).toHaveCount(0);
    await expect(page.locator('[data-sin-definiciones]')).toBeHidden();
    await expect(page.locator('#wm-definicion-hint')).toHaveText(
      'La definición de columnas con la que parte cada campaña de WhatsMKT. En la campaña se puede elegir otra.',
    );
  });

  test('guarda la elegida y manda solo ese campo', async ({ page }) => {
    const api = apiWhatsmkt();
    await abrir(page, api);

    await definicion(page).selectOption({ label: 'Contactos WhatsMKT con apellido' });
    await guardar(page, 'Guardar definición').click();

    await expect(page.locator('[data-definicion-estado]')).toHaveText('Guardado.');
    expect(pedidosA(api, 'PUT', '/whatsmkt/configuracion').at(-1)?.cuerpo).toEqual({ definicion_defecto_id: 12 });
    await expect(definicion(page)).toHaveValue('12');
  });

  test('«sin definición» quita la elegida (null)', async ({ page }) => {
    const api = apiWhatsmkt();
    api.configuracion.definicion_defecto_id = 11;
    await abrir(page, api);
    await expect(definicion(page)).toHaveValue('11');

    await definicion(page).selectOption({ label: 'Sin definición por defecto' });
    await guardar(page, 'Guardar definición').click();

    expect(pedidosA(api, 'PUT', '/whatsmkt/configuracion').at(-1)?.cuerpo).toEqual({ definicion_defecto_id: null });
    await expect(definicion(page)).toHaveValue('');
  });

  test('si la API dice que no es de WhatsMKT (definicion_no_whatsmkt), el error va bajo la definición', async ({ page }) => {
    const api = apiWhatsmkt();
    api.respuestas.guardarConfiguracion = [{ estado: 422, cuerpo: errorWhatsmkt('definicion_no_whatsmkt') }];
    await abrir(page, api);

    await definicion(page).selectOption({ label: 'Contactos WhatsMKT' });
    await guardar(page, 'Guardar definición').click();

    await expect(errorDefinicion(page)).toHaveText('La definición elegida no es de WhatsMKT.');
    await expect(definicion(page)).toHaveAttribute('aria-invalid', 'true');
    await expect(definicion(page)).toBeFocused();
  });

  test('si la definición ya no existe (404), el motivo de la API va bajo la definición', async ({ page }) => {
    const api = apiWhatsmkt();
    await abrir(page, api);
    // It disappears after the screen read the list.
    api.definiciones = api.definiciones.filter((d) => d.id !== 11);

    await definicion(page).selectOption({ label: 'Contactos WhatsMKT' });
    await guardar(page, 'Guardar definición').click();

    await expect(errorDefinicion(page)).toHaveText('No existe la definicion de columnas');
  });

  test('sin definiciones de WhatsMKT: el campo queda apagado, dice por qué y el enlace es para crear', async ({ page }) => {
    const api = apiWhatsmkt();
    api.definiciones = [definicionSintetica(13, 'Carga SMS de MES', 'mowa_mes')];
    await abrir(page, api);

    await expect(definicion(page)).toBeDisabled();
    await expect(definicion(page).locator('option')).toHaveText(['No hay definiciones de WhatsMKT']);
    await expect(page.locator('[data-sin-definiciones]')).toHaveClass(/notice--warning/);
    await expect(page.locator('[data-sin-definiciones]')).toHaveText(
      'Crea una definición de WhatsMKT en Columnas de carga para armar el archivo.',
    );
    await expect(guardar(page, 'Guardar definición')).toBeDisabled();
    const enlace = page.getByRole('link', { name: 'Crear en Columnas de carga' });
    await expect(enlace).toHaveAttribute('href', '/columnas?plataforma=whatsmkt&volver=%2Fwhatsmkt%2Fconfiguracion');
  });

  test('con definiciones y ninguna elegida, el enlace es «Editar en Columnas de carga» y lleva solo el camino de vuelta', async ({ page }) => {
    await abrir(page, apiWhatsmkt());

    await expect(page.getByRole('link', { name: 'Editar en Columnas de carga' })).toHaveAttribute('href', '/columnas?volver=%2Fwhatsmkt%2Fconfiguracion');
  });

  test('una definición guardada que ya no es de WhatsMKT sigue a la vista por su número, no se disfraza', async ({ page }) => {
    const api = apiWhatsmkt();
    api.configuracion.definicion_defecto_id = 13;
    await abrir(page, api);

    await expect(definicion(page)).toHaveValue('13');
    await expect(definicion(page).locator('option:checked')).toHaveText('#13');
  });

  test('si la lista de definiciones no se puede leer, lo dice en el panel y el resto de la pantalla funciona', async ({ page }) => {
    const api = apiWhatsmkt();
    await montarApiWhatsmkt(page, api);
    // The settings read the saved messages and the default definition; what a spec registers after this one answers first.
    await montarMensajesWhatsmkt(page, mensajesFalsos());
    // Registered last, it answers first: only this call fails.
    await page.route('**/api/definiciones-columnas', (ruta) => json(ruta, 500, { detail: 'La lista no respondió' }));
    await page.goto(RUTA);
    await expect(page.getByLabel('Nombre del segmento Preventivo')).toBeVisible();

    await expect(errorDefinicion(page)).toHaveText('La lista no respondió');
    await expect(definicion(page)).toBeDisabled();
    // Nothing else went down with it.
    await expect(whatsapp(page)).toBeVisible();
    await expect(page.locator('#wm-tope-mensaje')).toHaveValue('4096');
  });
});

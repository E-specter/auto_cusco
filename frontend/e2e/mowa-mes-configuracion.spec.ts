/**
 * MOWA MES configuration, end to end against an intercepted API.
 *
 * The paths covered are the ones where a wrong screen costs a campaign: the
 * original speech saved over itself, a speech that cannot be generated because
 * the WhatsApp is missing, supervisors saved with the wrong shape, and a law
 * holiday deleted instead of withdrawn. Every number is synthetic (900000xxx).
 */
import { expect, test, type Page } from '@playwright/test';

import { apiMowaMes, montarApiMowaMes, type ApiFalsaMowaMes } from './api-falsa-mowa-mes';
import { montarConfiguracion } from './api-falsa-speech-v2';

const RUTA = '/mowa-mes/configuracion';

/** Requests to exactly `ruta` (query ignored); a trailing `/` matches any id under it. */
const pedidosA = (api: ApiFalsaMowaMes, metodo: string, ruta: string) =>
  api.pedidos.filter((p) => {
    const camino = p.ruta.split('?')[0];
    return p.metodo === metodo && (ruta.endsWith('/') ? camino.startsWith(ruta) : camino === ruta);
  });

/** The screen with its whole API (the speech is always the v2 editor since M-B3) and the editor ready. */
async function abrir(page: Page, api: ApiFalsaMowaMes): Promise<void> {
  await montarConfiguracion(page, api);
  await page.goto(RUTA);
  await expect(page.getByRole('heading', { name: 'Configuración de MOWA MES' })).toBeVisible();
  await expect(segmentos(page)).toHaveCount(6);
}

const segmentos = (page: Page) => page.locator('#mm-speech-v2 [data-segmento-botones] button');

test.describe('carga inicial', () => {
  test('muestra plataforma y speech, y avisa dónde están ahora los supervisores y el calendario', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);

    await expect(page.getByLabel('Límite mensual de SMS')).toHaveValue('2500000');
    await expect(page.getByLabel('WhatsApp de contacto')).toHaveValue('900000999');

    // The supervisors and the calendar moved out (T-MM-C10, L-F7): a notice links to their screens.
    const aviso = page.locator('[data-pantallas-nuevas]');
    await expect(aviso).toHaveClass(/notice--info/);
    // The whole text, with the space between the colon and the first link (Astro drops the whitespace
    // between a span and a link unless the markup says it).
    await expect(aviso).toHaveText(
      'Los supervisores y el calendario laboral ahora tienen su propia pantalla: Supervisores · Calendario laboral.',
    );
    await expect(aviso.getByRole('link', { name: 'Supervisores' })).toHaveAttribute('href', '/supervisores');
    await expect(aviso.getByRole('link', { name: 'Calendario laboral' })).toHaveAttribute('href', '/calendario');
    await expect(page.getByLabel('Número del supervisor 1')).toHaveCount(0);
    await expect(page.locator('[data-calendario]')).toHaveCount(0);

    // RF-MM-19 corregido: con el Speech original, 9 a 30 mide 156 y se advierte (el nivel junto al segmento, que sale del backend).
    await expect(segmentos(page).nth(2)).toContainText('Más de 150 · 156');
    await expect(segmentos(page).nth(0)).toContainText('Cabe');
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
  test('el Speech original se abre en el editor y solo se guarda como una versión nueva: abrirlo no guarda nada', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);

    await expect(page.locator('#mm-speech-v2')).toBeVisible();
    await expect(page.locator('[data-speech-inmutable]')).toBeVisible();
    await expect(page.locator('[data-speech-inmutable]')).toContainText('Este es el Speech original: no se modifica.');
    // Nothing to save until something is written: the original is read.
    await expect(page.locator('[data-speech-guardar]')).toBeDisabled();
    expect(pedidosA(api, 'PUT', '/mowa-mes/speech/')).toEqual([]);
    expect(pedidosA(api, 'POST', '/mowa-mes/speech')).toEqual([]);
  });

  test('sin WhatsApp los segmentos que lo usan no se generan, y al configurarlo se recalcula', async ({ page }) => {
    const api = apiMowaMes();
    api.configuracion = { ...api.configuracion, whatsapp_contacto: null };
    await abrir(page, api);

    await expect(page.getByText(/Falta el WhatsApp de contacto y hay segmentos que usan/)).toBeVisible();
    // The segments that use it say so beside their name (31 a 60, 61 a 90 and 91 a 120 do).
    const fila = segmentos(page).nth(3);
    await expect(fila).toContainText('Falta WhatsApp');

    await page.getByLabel('WhatsApp de contacto').fill('900000555');
    await page.getByRole('button', { name: 'Guardar plataforma' }).click();

    await expect(fila).not.toContainText('Falta WhatsApp');
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
    await montarConfiguracion(page, api);
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

test.describe('plataforma: la tarjeta ocupa todo el ancho y sus campos van en una rejilla', () => {
  const caja = async (locator: ReturnType<Page['locator']>) => (await locator.boundingBox())!;

  test('a 1280 px: tres columnas, el nombre de los archivos y el guardado en su propia fila', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await abrir(page, apiMowaMes());

    const panel = await caja(page.locator('section[aria-labelledby="mm-plataforma-title"]'));
    const contenido = await caja(page.locator('[data-contenido]'));
    expect(Math.abs(panel.width - contenido.width)).toBeLessThanOrEqual(1);

    const [limite, registros, bytes, whatsapp, tarifa] = await Promise.all(
      ['#mm-limite', '#mm-registros', '#mm-bytes', '#mm-whatsapp', '#mm-tarifa'].map((id) => caja(page.locator(id))),
    );
    // Three columns: the first three share a row, the next two start the second one.
    expect(Math.abs(limite.y - registros.y)).toBeLessThanOrEqual(1);
    expect(Math.abs(limite.y - bytes.y)).toBeLessThanOrEqual(1);
    expect(registros.x).toBeGreaterThan(limite.x + limite.width - 1);
    expect(bytes.x).toBeGreaterThan(registros.x + registros.width - 1);
    expect(whatsapp.y).toBeGreaterThan(limite.y + limite.height);
    expect(Math.abs(whatsapp.y - tarifa.y)).toBeLessThanOrEqual(1);

    // The template takes the whole row, under the others; the save button goes under everything.
    const campoPlantilla = await caja(page.locator('.mm-plataforma__plantilla'));
    expect(campoPlantilla.y).toBeGreaterThan(whatsapp.y + whatsapp.height - 1);
    expect(campoPlantilla.width).toBeGreaterThan(limite.width * 2.5);
    const guardar = await caja(page.getByRole('button', { name: 'Guardar plataforma' }));
    expect(guardar.y).toBeGreaterThan(campoPlantilla.y + campoPlantilla.height - 1);
  });

  test('a 360 px: una columna y sin desbordar la página', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    await abrir(page, apiMowaMes());

    const limite = await caja(page.locator('#mm-limite'));
    const registros = await caja(page.locator('#mm-registros'));
    expect(registros.y).toBeGreaterThan(limite.y + limite.height);
    expect(Math.abs(registros.x - limite.x)).toBeLessThanOrEqual(1);
    const desborde = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(desborde).toBeLessThanOrEqual(0);
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

test.describe('anchos (T-MM-F5, hallazgos 1 y 2)', () => {
  test('a 360 px, la página no desborda', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    const api = apiMowaMes();
    await abrir(page, api);

    const desborda = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
    expect(desborda).toBe(false);

  });
});

test.describe('idioma', () => {
  test('en inglés traduce lo que dibuja el script, incluidos los códigos', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    await montarConfiguracion(page, apiMowaMes());
    await page.goto(RUTA);

    await expect(page.getByRole('heading', { name: 'MOWA MES settings' })).toBeVisible();
    await expect(segmentos(page)).toHaveCount(6);
    await expect(segmentos(page).nth(2)).toContainText('Over 150');
  });

  test('en inglés el aviso de las pantallas nuevas dice el texto completo, con el espacio antes del primer enlace', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    await montarConfiguracion(page, apiMowaMes());
    await page.goto(RUTA);

    await expect(page.locator('[data-pantallas-nuevas]')).toHaveText(
      'Supervisors and the working calendar now have their own screens: Supervisors · Working calendar.',
    );
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
    await montarConfiguracion(page, api);
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

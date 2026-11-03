/**
 * WhatsMKT configuration, T-WM-F1b1: the attachment library, end to end against an intercepted API. The clock is
 * fixed from the first spec, in `montarApiWhatsmkt`. Files are synthetic bytes with invented names.
 */
import { expect, test, type Page } from '@playwright/test';

import { adjuntoSintetico, apiWhatsmkt, errorWhatsmkt, montarApiWhatsmkt, type ApiFalsaWhatsmkt } from './api-falsa-whatsmkt';
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

const panel = (page: Page) => page.getByRole('region', { name: 'Biblioteca de adjuntos' });
const activos = (page: Page) => page.getByRole('table', { name: 'Adjuntos activos' });
const archivados = (page: Page) => page.getByRole('table', { name: 'Adjuntos archivados' });
const filaActiva = (page: Page, nombre: string) => activos(page).getByRole('row').filter({ hasText: nombre });
const detalle = (page: Page) => page.locator('[data-biblioteca-archivados]');
const estado = (page: Page) => page.locator('[data-biblioteca-estado]');
const errorCampo = (page: Page) => page.locator('[data-adjunto-error]');
const campo = (page: Page) => page.locator('#wm-adjunto');
const subir = (page: Page) => page.getByRole('button', { name: 'Subir un archivo' });

const archivo = (name: string, mimeType: string) => ({ name, mimeType, buffer: Buffer.from(`bytes sinteticos de ${name}`) });

test.describe('la biblioteca', () => {
  test('lista los adjuntos activos con su tipo, tamaño y fecha, y los archivados aparte', async ({ page }) => {
    await abrir(page, apiWhatsmkt());

    await expect(activos(page).getByRole('columnheader')).toHaveText(['Nombre', 'Tipo', 'Tamaño', 'Subido', 'Acciones']);
    const afiche = filaActiva(page, 'afiche-octubre.jpg');
    await expect(afiche).toContainText('Imagen JPEG');
    await expect(afiche).toContainText('240 KB');
    // The cells are Tipo, Tamaño, Subido and Acción (the name is the row's header): the third is the date.
    await expect(afiche.getByRole('cell').nth(2)).not.toBeEmpty();
    await expect(filaActiva(page, 'tarifario.pdf')).toContainText('PDF');
    await expect(filaActiva(page, 'tarifario.pdf')).toContainText(/1[.,]5 MB/);
    // The archived one is not in the active table: it is in a closed fold that counts them.
    await expect(filaActiva(page, 'spot-anterior.mp4')).toHaveCount(0);
    await expect(detalle(page)).toBeVisible();
    await expect(detalle(page).locator('summary')).toHaveText('Archivados (1)');
    await expect(detalle(page)).not.toHaveAttribute('open', '');
    await detalle(page).locator('summary').click();
    await expect(archivados(page)).toContainText('spot-anterior.mp4');
    await expect(archivados(page)).toContainText('Video');
  });

  test('la tabla de activos y la de archivados comparten sus columnas: se leen como una sola lista', async ({ page }) => {
    await abrir(page, apiWhatsmkt());
    await detalle(page).locator('summary').click();
    await expect(archivados(page)).toBeVisible();

    const columnas = async (tabla: ReturnType<typeof activos>) =>
      Promise.all((await tabla.getByRole('columnheader').all()).map(async (celda) => (await celda.boundingBox())!));
    const deActivos = await columnas(activos(page));
    const deArchivados = await columnas(archivados(page));

    expect(deArchivados).toHaveLength(deActivos.length);
    deActivos.forEach((caja, i) => {
      expect(Math.abs(caja.x - deArchivados[i].x), `x de la columna ${i}`).toBeLessThanOrEqual(1);
      expect(Math.abs(caja.width - deArchivados[i].width), `ancho de la columna ${i}`).toBeLessThanOrEqual(1);
    });
    await expect(activos(page).locator('col')).toHaveCount(5);
    await expect(archivados(page).locator('col')).toHaveCount(5);
  });

  test('sin adjuntos lo dice, y sin archivados no muestra el pliegue', async ({ page }) => {
    const api = apiWhatsmkt();
    api.adjuntos = [];
    await abrir(page, api);

    await expect(panel(page)).toContainText('La biblioteca no tiene adjuntos.');
    await expect(activos(page)).toHaveCount(0);
    await expect(detalle(page)).toBeHidden();
  });

  test('descarga un adjunto con el nombre que da la API', async ({ page }) => {
    const api = apiWhatsmkt();
    await abrir(page, api);

    const descarga = page.waitForEvent('download');
    await filaActiva(page, 'afiche-octubre.jpg').getByRole('button', { name: /Descargar/ }).click();

    expect((await descarga).suggestedFilename()).toBe('afiche-octubre.jpg');
    expect(pedidosA(api, 'GET', '/whatsmkt/adjuntos/1/contenido')).toHaveLength(1);
  });

  test('cada botón de una fila dice de qué archivo es', async ({ page }) => {
    await abrir(page, apiWhatsmkt());

    await expect(page.getByRole('button', { name: 'Descargar afiche-octubre.jpg' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Archivar tarifario.pdf' })).toBeVisible();
  });

  test('archivar mueve el adjunto a los archivados, lo anuncia y deja el foco cerca', async ({ page }) => {
    const api = apiWhatsmkt();
    await abrir(page, api);

    await page.getByRole('button', { name: 'Archivar afiche-octubre.jpg' }).click();

    expect(pedidosA(api, 'POST', '/whatsmkt/adjuntos/1/archivar')).toHaveLength(1);
    await expect(estado(page)).toHaveText('Archivado: afiche-octubre.jpg.');
    await expect(filaActiva(page, 'afiche-octubre.jpg')).toHaveCount(0);
    await expect(detalle(page).locator('summary')).toHaveText('Archivados (2)');
    // The focus stays in the table, on the row that took its place.
    await expect(page.getByRole('button', { name: 'Descargar tarifario.pdf' })).toBeFocused();
  });

  test('archivar el último activo deja la biblioteca vacía y el foco en el selector de archivo', async ({ page }) => {
    const api = apiWhatsmkt();
    api.adjuntos = [adjuntoSintetico(1, 'pdf', 'unico.pdf', 100_000)];
    await abrir(page, api);

    await page.getByRole('button', { name: 'Archivar unico.pdf' }).click();

    await expect(panel(page)).toContainText('La biblioteca no tiene adjuntos.');
    await expect(campo(page)).toBeFocused();
  });

  test('restaurar vuelve el adjunto a los activos y, sin más archivados, el pliegue se va', async ({ page }) => {
    const api = apiWhatsmkt();
    await abrir(page, api);

    await detalle(page).locator('summary').click();
    await archivados(page).getByRole('button', { name: 'Restaurar spot-anterior.mp4' }).click();

    expect(pedidosA(api, 'POST', '/whatsmkt/adjuntos/3/desarchivar')).toHaveLength(1);
    await expect(estado(page)).toHaveText('Restaurado: spot-anterior.mp4.');
    await expect(filaActiva(page, 'spot-anterior.mp4')).toHaveCount(1);
    await expect(detalle(page)).toBeHidden();
  });

  test('un archivado también se descarga', async ({ page }) => {
    await abrir(page, apiWhatsmkt());
    await detalle(page).locator('summary').click();

    const descarga = page.waitForEvent('download');
    await archivados(page).getByRole('button', { name: 'Descargar spot-anterior.mp4' }).click();

    expect((await descarga).suggestedFilename()).toBe('spot-anterior.mp4');
  });

  test('si el adjunto ya no existe (404), el motivo va en el panel', async ({ page }) => {
    const api = apiWhatsmkt();
    await abrir(page, api);
    api.adjuntos = api.adjuntos.filter((a) => a.id !== 2);

    await page.getByRole('button', { name: 'Archivar tarifario.pdf' }).click();

    await expect(page.locator('[data-biblioteca-error]')).toHaveText('No existe el adjunto');
  });
});

test.describe('subir un archivo', () => {
  test('una imagen nueva se agrega y el estado dice que se guardó sin metadatos', async ({ page }) => {
    const api = apiWhatsmkt();
    await abrir(page, api);
    await expect(page.locator('[data-adjunto-nombre]')).toHaveText('Ningún archivo elegido');

    await campo(page).setInputFiles(archivo('nuevo.png', 'image/png'));
    await expect(page.locator('[data-adjunto-nombre]')).toHaveText('nuevo.png');
    await subir(page).click();

    await expect(estado(page)).toHaveText('Subido: nuevo.png. Se guardó sin metadatos (EXIF, ubicación).');
    await expect(filaActiva(page, 'nuevo.png')).toContainText('Imagen PNG');
    // The picker is ready for the next one.
    await expect(page.locator('[data-adjunto-nombre]')).toHaveText('Ningún archivo elegido');
    const envio = pedidosA(api, 'POST', '/whatsmkt/adjuntos')[0];
    expect(String(envio.cuerpo)).toContain('name="proposito"');
    expect(String(envio.cuerpo)).toContain('adjunto');
  });

  test('un archivo que no es imagen no lleva la frase de los metadatos', async ({ page }) => {
    await abrir(page, apiWhatsmkt());

    await campo(page).setInputFiles(archivo('contrato.pdf', 'application/pdf'));
    await subir(page).click();

    await expect(estado(page)).toHaveText('Subido: contrato.pdf.');
    await expect(filaActiva(page, 'contrato.pdf')).toContainText('PDF');
  });

  test('un archivo que la biblioteca ya tenía no se duplica y se dice', async ({ page }) => {
    await abrir(page, apiWhatsmkt());

    await campo(page).setInputFiles(archivo('afiche-octubre.jpg', 'image/jpeg'));
    await subir(page).click();

    await expect(estado(page)).toHaveText('Ya estaba en la biblioteca: afiche-octubre.jpg.');
    await expect(filaActiva(page, 'afiche-octubre.jpg')).toHaveCount(1);
  });

  test('si estaba archivado, sigue archivado y el estado ofrece restaurarlo', async ({ page }) => {
    const api = apiWhatsmkt();
    await abrir(page, api);

    await campo(page).setInputFiles(archivo('spot-anterior.mp4', 'video/mp4'));
    await subir(page).click();

    await expect(estado(page)).toHaveText('Ya estaba en la biblioteca, archivado: spot-anterior.mp4.');
    await expect(filaActiva(page, 'spot-anterior.mp4')).toHaveCount(0);
    const restaurar = page.locator('[data-restaurar-subido]');
    await expect(restaurar).toBeVisible();

    await restaurar.click();

    expect(pedidosA(api, 'POST', '/whatsmkt/adjuntos/3/desarchivar')).toHaveLength(1);
    await expect(filaActiva(page, 'spot-anterior.mp4')).toHaveCount(1);
    await expect(restaurar).toBeHidden();
    await expect(estado(page)).toHaveText('Restaurado: spot-anterior.mp4.');
  });

  test('sin elegir archivo lo dice, enfoca el selector y no llama a la API', async ({ page }) => {
    const api = apiWhatsmkt();
    await abrir(page, api);

    await subir(page).click();

    await expect(errorCampo(page)).toHaveText('Elige un archivo para subir.');
    await expect(campo(page)).toBeFocused();
    expect(pedidosA(api, 'POST', '/whatsmkt/adjuntos')).toHaveLength(0);
  });

  test('un tipo que WhatsMKT no admite (adjunto_tipo) se dice bajo el campo', async ({ page }) => {
    await abrir(page, apiWhatsmkt());

    await campo(page).setInputFiles(archivo('datos.txt', 'text/plain'));
    await subir(page).click();

    await expect(errorCampo(page)).toHaveText(
      'WhatsMKT no admite este tipo de archivo. Sube una imagen, un video, un audio o un PDF.',
    );
    await expect(campo(page)).toHaveAttribute('aria-invalid', 'true');
    // The file stays chosen, so it can be seen what was refused.
    await expect(page.locator('[data-adjunto-nombre]')).toHaveText('datos.txt');
  });

  test('un archivo que pesa de más (adjunto_peso) dice cuánto pesa y cuánto admite ese tipo', async ({ page }) => {
    const api = apiWhatsmkt();
    api.respuestas.subirAdjunto = [
      { estado: 422, cuerpo: errorWhatsmkt('adjunto_peso', { peso: 20_000_000, maximo: 16_000_000, tipo: 'video' }) },
    ];
    await abrir(page, api);

    await campo(page).setInputFiles(archivo('largo.mp4', 'video/mp4'));
    await subir(page).click();

    await expect(errorCampo(page)).toHaveText('El archivo pesa 20 MB: el máximo para video es 16 MB.');
  });

  test('un archivo dañado (adjunto_danado) se dice bajo el campo', async ({ page }) => {
    const api = apiWhatsmkt();
    api.respuestas.subirAdjunto = [{ estado: 422, cuerpo: errorWhatsmkt('adjunto_danado') }];
    await abrir(page, api);

    await campo(page).setInputFiles(archivo('roto.png', 'image/png'));
    await subir(page).click();

    await expect(errorCampo(page)).toHaveText(
      'El archivo está incompleto o dañado. Vuelve a descargarlo y súbelo de nuevo.',
    );
  });

  test('elegir otro archivo quita el error anterior', async ({ page }) => {
    await abrir(page, apiWhatsmkt());
    await campo(page).setInputFiles(archivo('datos.txt', 'text/plain'));
    await subir(page).click();
    await expect(errorCampo(page)).not.toBeEmpty();

    await campo(page).setInputFiles(archivo('bueno.pdf', 'application/pdf'));

    await expect(errorCampo(page)).toBeEmpty();
    await expect(campo(page)).not.toHaveAttribute('aria-invalid', 'true');
  });
});

test.describe('idioma y pantalla angosta', () => {
  test('en inglés, la tabla, el estado y el error se traducen', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    await montarApiWhatsmkt(page, apiWhatsmkt());
    // The settings read the saved messages and the default definition; what a spec registers after this one answers first.
    await montarMensajesWhatsmkt(page, mensajesFalsos());
    await page.goto(RUTA);
    await expect(page.getByRole('heading', { name: 'WhatsMKT settings', level: 1 })).toBeVisible();

    const tabla = page.getByRole('table', { name: 'Active attachments' });
    await expect(tabla.getByRole('columnheader')).toHaveText(['Name', 'Type', 'Size', 'Uploaded', 'Actions']);
    await expect(page.locator('#wm-adjunto-hint')).toHaveText(
      'JPEG or PNG image, video, audio or PDF. WhatsMKT does not accept other types.',
    );
    await expect(tabla).toContainText('JPEG image');
    await expect(page.locator('[data-biblioteca-archivados] summary')).toHaveText('Archived (1)');

    await campo(page).setInputFiles(archivo('nuevo.png', 'image/png'));
    await page.getByRole('button', { name: 'Upload a file' }).click();
    await expect(estado(page)).toHaveText('Uploaded: nuevo.png. It was saved without metadata (EXIF, location).');

    await campo(page).setInputFiles(archivo('datos.txt', 'text/plain'));
    await page.getByRole('button', { name: 'Upload a file' }).click();
    await expect(errorCampo(page)).toHaveText(
      'WhatsMKT does not accept this type of file. Upload an image, a video, an audio or a PDF.',
    );
  });

  test('a 360 px la tabla se apila, la página no desborda y los botones no se cortan', async ({ page }) => {
    const api = apiWhatsmkt();
    api.adjuntos.push(adjuntoSintetico(4, 'pdf', `${'condiciones-comerciales-'.repeat(4)}2026.pdf`, 90_000));
    await page.setViewportSize({ width: 360, height: 900 });
    await abrir(page, api);

    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
    const fila = filaActiva(page, 'condiciones-comerciales');
    // Stacked: the cells sit one under the other, so «Tipo» is below the name.
    const nombre = (await fila.getByRole('rowheader').boundingBox())!;
    const tipo = (await fila.getByRole('cell').first().boundingBox())!;
    expect(tipo.y).toBeGreaterThan(nombre.y + nombre.height - 1);
    for (const boton of await fila.getByRole('button').all()) {
      const caja = (await boton.boundingBox())!;
      expect(caja.x + caja.width).toBeLessThanOrEqual(360);
    }
  });
});

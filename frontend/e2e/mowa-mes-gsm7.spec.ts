/**
 * The message in GSM-7 (T-MM-F7; RF-MM-27 and RF-MM-19, docs/motor-texto-enriquecido-interfaz.md §10.2),
 * end to end against an intercepted API.
 *
 * What costs when it is wrong: a deleted emoji nobody was told about, a line that names what is only
 * replaced (accents, quotes), a line on a segment with nothing deleted, or a screen that promises the
 * normalisation without saying so. The fake API deletes what the backend deletes (api-falsa-gsm7.ts);
 * what matters here is what the screen does with the list it receives. Every text is synthetic.
 */
import { expect, test, type Page } from '@playwright/test';

import { apiMowaMes, montarApiMowaMes, type ApiFalsaMowaMes } from './api-falsa-mowa-mes';
import { v1ConBorrados, v1ConExtendidos, v2ConBorrados } from './fixtures-gsm7';
import { apiSpeechV2, montarApiSpeechV2, type ApiFalsaSpeechV2 } from './api-falsa-speech-v2';
import { apiTextoEnriquecidoVacia } from './api-falsa-texto-enriquecido';

const RUTA = '/mowa-mes/configuracion';

const HINT_ES =
  'Al generar, se quitan las tildes, los signos que el SMS no admite se cambian por uno simple y los que no tienen equivalente se borran. La versión se guarda como la escribes.';
const HINT_EN =
  'When generating, accents are removed, signs the SMS does not accept are replaced by a simple one, and those with no equivalent are deleted. The version is saved as you write it.';
const UNIDAD_ES =
  'Se cuenta como lo cuenta el SMS: los signos que se cambian se cuentan ya cambiados («…» ocupa 3, como «...», y «€» también, como «EUR»).';
const UNIDAD_EN =
  'Counted the way the SMS counts it: replaced signs are counted already replaced (“…” takes 3, as “...”, and so does “€”, as “EUR”).';

async function abrir(
  page: Page,
  ajustar?: (api: ApiFalsaMowaMes, v2: ApiFalsaSpeechV2) => void,
  idioma: 'es' | 'en' = 'es',
): Promise<{ api: ApiFalsaMowaMes; v2: ApiFalsaSpeechV2 }> {
  await page.addInitScript((elegido) => {
    try {
      localStorage.setItem('app:appearance', JSON.stringify({ language: elegido, theme: 'light' }));
    } catch {
      /* storage blocked: the page keeps its default */
    }
  }, idioma);
  const api = apiMowaMes();
  const v2 = apiSpeechV2();
  ajustar?.(api, v2);
  await montarApiMowaMes(page, api);
  await montarApiSpeechV2(page, api, v2, apiTextoEnriquecidoVacia());
  await page.goto(RUTA);
  await expect(page.locator('#mm-speech-title')).toBeVisible();
  return { api, v2 };
}

const version = (page: Page) => page.locator('#mm-version');
const editor = (page: Page) => page.locator('#mm-speech-v2');
const segmentos = (page: Page) => editor(page).locator('[data-segmento-botones] button');
const lineaV2 = (page: Page) => page.locator('[data-borrados-v2]');
const filaV1 = (page: Page, segmento: string) => page.locator(`[data-speech-filas] tr[data-segmento="${segmento}"]`);

async function abrirV2(
  page: Page,
  idioma: 'es' | 'en' = 'es',
  ajustar?: (api: ApiFalsaMowaMes) => void,
) {
  const contexto = await abrir(
    page,
    (api) => {
      v2ConBorrados(api);
      ajustar?.(api);
    },
    idioma,
  );
  await version(page).selectOption({ label: 'Speech v2' });
  await expect(editor(page)).toBeVisible();
  await expect(segmentos(page)).toHaveCount(6);
  return contexto;
}

test.describe('hint fijo de GSM-7 (RF-MM-27)', () => {
  test('está en una v1, incluido el Speech original que tiene tildes', async ({ page }) => {
    await abrir(page);

    await expect(page.locator('[data-speech-filas]')).toBeVisible();
    await expect(page.locator('[data-speech-gsm7]')).toHaveText(HINT_ES);
    await expect(page.locator('[data-speech-gsm7]')).toBeVisible();
  });

  test('está en una v2', async ({ page }) => {
    await abrirV2(page);

    await expect(editor(page)).toBeVisible();
    await expect(page.locator('[data-speech-gsm7]')).toHaveText(HINT_ES);
    await expect(page.locator('[data-speech-gsm7]')).toBeVisible();
  });

  test('en inglés, el hint y la frase de la unidad están traducidos', async ({ page }) => {
    await abrir(page, undefined, 'en');

    await expect(page.locator('[data-speech-gsm7]')).toHaveText(HINT_EN);
    await expect(page.locator('[data-speech-calculo]')).toContainText(UNIDAD_EN);
    await expect(page.locator('body')).not.toContainText('mowaMes.');
  });
});

test.describe('la unidad del largo', () => {
  test('la nota de cálculo bajo la tabla suma la frase de cómo cuenta el SMS, y la columna sigue en «caracteres»', async ({ page }) => {
    await abrir(page);

    const nota = page.locator('[data-speech-calculo]');
    await expect(nota).toContainText('Largo calculado con un titular de 8 caracteres');
    await expect(nota).toContainText(UNIDAD_ES);
    await expect(page.getByRole('columnheader', { name: 'Largo máximo' })).toBeVisible();
  });
});

test.describe('«Al enviar se borran: …» en una v1', () => {
  test('va en la celda Estado del segmento, con lo que se borra y en su orden', async ({ page }) => {
    await abrir(page, (api) => v1ConBorrados(api));
    await page.getByLabel('Versión', { exact: true }).selectOption('2');

    const linea = filaV1(page, 'preventiva').locator('[data-borrados]');
    await expect(linea).toBeVisible();
    await expect(linea).toHaveText('Al enviar se borran: 👍🏽 · ✓ · ^ · espacio de ancho cero U+200B');
    // Visible elements in mono, the invisible one by its name and its code point in mono.
    await expect(linea.locator('[data-borrado-visible]')).toHaveText(['👍🏽', '✓', '^']);
    await expect(linea.locator('[data-borrado-nombre]')).toHaveText(['espacio de ancho cero']);
    await expect(linea.locator('[data-borrado-codigo]')).toHaveText(['U+200B']);
    const familia = (selector: string) => linea.locator(selector).first().evaluate((e) => getComputedStyle(e).fontFamily);
    expect(await familia('[data-borrado-visible]')).toMatch(/mono/i);
    expect(await familia('[data-borrado-codigo]')).toMatch(/mono/i);
    expect(await familia('[data-borrado-nombre]')).not.toMatch(/mono/i);
    // The icon says it is a warning without relying on colour alone.
    await expect(linea.locator('svg')).toHaveCount(1);
  });

  test('un grafema compuesto sale una vez, entero, y lo que solo se cambia no se nombra', async ({ page }) => {
    await abrir(page, (api) => v1ConBorrados(api));
    await page.getByLabel('Versión', { exact: true }).selectOption('2');

    const linea = filaV1(page, 'preventiva').locator('[data-borrados]');
    await expect(linea.locator('[data-borrado-visible]').filter({ hasText: '👍🏽' })).toHaveCount(1);
    // «👍🏽» is one element, not an emoji and a skin tone; «✓» is there twice in the text and once in the line.
    await expect(linea.locator('[data-borrado-visible]')).toHaveCount(3);
    const texto = (await linea.textContent()) ?? '';
    for (const cambiado of ['á', 'ñ', '“', '”', '«', '»', '—', '…', '°', 'ú']) expect(texto).not.toContain(cambiado);
    // The extended table is transliterated too (RF-MM-27, 2026-10-26): only `^` has no equivalent.
    for (const cambiado of ['€', '[', ']', '{', '}', '\\', '~', '|']) expect(texto).not.toContain(cambiado);
  });

  test('un segmento sin nada que borrar no tiene línea', async ({ page }) => {
    await abrir(page, (api) => v1ConBorrados(api));
    await page.getByLabel('Versión', { exact: true }).selectOption('2');
    await expect(filaV1(page, 'preventiva').locator('[data-borrados]')).toBeVisible();

    // The five others have accents or nothing at all, and not one deletion.
    await expect(page.locator('[data-speech-filas] [data-borrados]:visible')).toHaveCount(1);
    await expect(filaV1(page, '9_a_30').locator('[data-borrados]')).toBeHidden();
    await expect(filaV1(page, '9_a_30').locator('[data-borrados]')).toBeEmpty();
  });

  test('el Speech original, con tildes y sin nada que se borre, no muestra ninguna línea', async ({ page }) => {
    await abrir(page);

    await expect(page.locator('[data-speech-filas] tr[data-segmento]')).toHaveCount(6);
    await expect(page.locator('[data-speech-filas] [data-borrados]:visible')).toHaveCount(0);
  });

  test('en inglés, el prefijo y el nombre del invisible están traducidos', async ({ page }) => {
    await abrir(page, (api) => v1ConBorrados(api), 'en');
    await page.getByLabel('Version', { exact: true }).selectOption('2');

    await expect(filaV1(page, 'preventiva').locator('[data-borrados]')).toHaveText(
      'Deleted when sent: 👍🏽 · ✓ · ^ · zero-width space U+200B',
    );
  });
});

test.describe('los extendidos de GSM-7 se transliteran (RF-MM-27, 2026-10-26)', () => {
  test('el ejemplo sale transliterado, el largo se cuenta ya transliterado y no hay línea de borrados', async ({ page }) => {
    await abrir(page, (api) => v1ConExtendidos(api));
    await page.getByLabel('Versión', { exact: true }).selectOption('2');
    const fila = filaV1(page, 'preventiva');

    // «[€5]{x}» is «(EUR5)(x)» and the form feed is a space: no extended character is left in the example.
    await expect(fila.locator('[data-ejemplo]')).toContainText('XXXXXXXX (EUR5)(x)dd/mm/yyyy a/b/c - .');
    const ejemplo = (await fila.locator('[data-ejemplo]').textContent()) ?? '';
    for (const c of ['€', '[', ']', '{', '}', '\\', '~', '|', '\f']) expect(ejemplo).not.toContain(c);
    // 8 (holder) + 10 («(EUR5)(x)» with its space) + 10 (the date) + 11 («a/b/c - » and the point): the
    // same length as the transliterated text, not 2 per extended character.
    await expect(fila.locator('[data-largo]')).toHaveText('39');
    // Everything here was replaced and nothing deleted, so there is nothing to warn about.
    await expect(fila.locator('[data-borrados]')).toBeHidden();
  });
});

test.describe('«Al enviar se borran: …» en una v2', () => {
  test('es un aviso de una línea bajo el editor, para el segmento en pantalla', async ({ page }) => {
    await abrirV2(page);
    await segmentos(page).nth(0).click();

    await expect(lineaV2(page)).toBeVisible();
    await expect(lineaV2(page)).toHaveText('Al enviar se borran: 👍🏽 · espacio de ancho cero U+200B · ^');
    await expect(lineaV2(page)).toHaveClass(/notice--warning/);
    await expect(lineaV2(page).locator('svg')).toHaveCount(1);
    // The visible character and the code point are mono; the sentence and the name are not.
    const familia = (selector: string) => lineaV2(page).locator(selector).first().evaluate((e) => getComputedStyle(e).fontFamily);
    expect(await familia('[data-borrado-visible]')).toMatch(/mono/i);
    expect(await familia('[data-borrado-codigo]')).toMatch(/mono/i);
    expect(await familia('[data-borrado-nombre]')).not.toMatch(/mono/i);
    // Under the editor, not above it.
    const cajaEditor = await editor(page).getByRole('textbox').last().boundingBox();
    const cajaLinea = await lineaV2(page).boundingBox();
    expect(cajaLinea!.y).toBeGreaterThan(cajaEditor!.y);
  });

  test('al elegir otro segmento la línea cambia en el acto; sin borrados desaparece', async ({ page }) => {
    await abrirV2(page);

    await segmentos(page).nth(0).click();
    await expect(lineaV2(page)).toContainText('👍🏽');

    await segmentos(page).nth(2).click();
    await expect(lineaV2(page)).toHaveText('Al enviar se borran: 🙂');

    await segmentos(page).nth(1).click();
    await expect(lineaV2(page)).toBeHidden();
    await expect(lineaV2(page)).toBeEmpty();
  });

  test('lo que se borra sigue lo que se escribe, y no impide guardar', async ({ page }) => {
    const { v2 } = await abrirV2(page);
    await segmentos(page).nth(1).click();
    await expect(lineaV2(page)).toBeHidden();

    await editor(page).getByRole('textbox').last().fill(', pague ya 😀 y evite el cobro.');

    await expect(lineaV2(page)).toHaveText('Al enviar se borran: 😀');
    await page.locator('#mm-speech-nombre').fill('Speech con emoji');
    const guardar = page.locator('[data-speech-guardar]');
    await expect(async () => {
      await guardar.click();
      await expect(page.getByText('Versión guardada.').first()).toBeVisible({ timeout: 1500 });
    }).toPass();
    // The version goes as it was written: the emoji is in what was sent, not stripped by the screen.
    const [edicion] = v2.pedidos.filter((p) => p.metodo === 'PUT' && p.ruta === '/mowa-mes/speech/20');
    expect(JSON.stringify(edicion.cuerpo)).toContain('😀');
  });

  test('si el segmento en pantalla cambia sin un clic, la línea cambia con él: guardar salta al segmento vacío', async ({ page }) => {
    // «preventiva» pierde un emoji y «1 a 8» no tiene mensaje: guardar no manda nada y lleva al segmento vacío.
    const { v2 } = await abrirV2(page, 'es', (api) => {
      api.versiones.at(-1)!.expresiones.find((x) => x.segmento === '1_a_8')!.expresion = { nodos: [] };
    });
    await segmentos(page).nth(0).click();
    await expect(lineaV2(page)).toContainText('👍🏽');
    await page.locator('#mm-speech-nombre').fill('Otro nombre');

    await page.locator('[data-speech-guardar]').click();

    await expect(page.locator('#mm-speech-error')).toContainText('Estos segmentos no tienen mensaje: 1 a 8');
    await expect(segmentos(page).nth(1)).toHaveAttribute('aria-pressed', 'true');
    await expect(segmentos(page).nth(0)).toHaveAttribute('aria-pressed', 'false');
    // The editor now shows «1 a 8», which loses nothing: the line of «preventiva» is gone.
    await expect(lineaV2(page)).toBeHidden();
    expect(v2.pedidos.filter((p) => p.metodo === 'PUT')).toHaveLength(0);
  });

  test('en inglés, el aviso y el nombre del invisible están traducidos', async ({ page }) => {
    await abrirV2(page, 'en');
    await segmentos(page).nth(0).click();

    await expect(lineaV2(page)).toHaveText('Deleted when sent: 👍🏽 · zero-width space U+200B · ^');
  });
});

test.describe('la tarjeta apilada de una v1, por debajo de 64rem', () => {
  test('lee segmento, largo y estado primero, y después las partes con el ejemplo', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    await abrir(page, (api) => v1ConBorrados(api));
    await page.getByLabel('Versión', { exact: true }).selectOption('2');
    const fila = filaV1(page, 'preventiva');
    await expect(fila.locator('[data-borrados]')).toBeVisible();

    const y = async (selector: string) => (await fila.locator(selector).first().boundingBox())!.y;
    const segmento = await y('th');
    const largo = await y('[data-largo]');
    const estado = await y('td:has([data-nivel-tags])');
    const parte1 = await y('td:has([data-campo="parte_1"])');
    const parte2 = await y('td:has([data-campo="parte_2"])');
    expect(segmento).toBeLessThan(largo);
    expect(largo).toBeLessThan(estado);
    expect(estado).toBeLessThan(parte1);
    expect(parte1).toBeLessThan(parte2);
    // The line travels with the status, not with the parts.
    const linea = (await fila.locator('[data-borrados]').boundingBox())!.y;
    expect(linea).toBeLessThan(parte1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
  });
});

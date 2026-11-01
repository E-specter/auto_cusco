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

import { apiMowaMes, type ApiFalsaMowaMes } from './api-falsa-mowa-mes';
import { v2ConBorrados } from './fixtures-gsm7';
import { montarConfiguracion, type ApiFalsaSpeechV2 } from './api-falsa-speech-v2';

const RUTA = '/mowa-mes/configuracion';

const HINT_ES =
  'Al generar, se quitan las tildes, los signos que el SMS no admite se cambian por uno simple y los que no tienen equivalente se borran. La versión se guarda como la escribes.';
const HINT_EN =
  'When generating, accents are removed, signs the SMS does not accept are replaced by a simple one, and those with no equivalent are deleted. The version is saved as you write it.';

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
  // The fakes read the state when they answer, so the scenario can change it after mounting.
  const { v2 } = await montarConfiguracion(page, api);
  ajustar?.(api, v2);
  await page.goto(RUTA);
  await expect(page.locator('#mm-speech-title')).toBeVisible();
  return { api, v2 };
}

const version = (page: Page) => page.locator('#mm-version');
const editor = (page: Page) => page.locator('#mm-speech-v2');
const segmentos = (page: Page) => editor(page).locator('[data-segmento-botones] button');
const lineaV2 = (page: Page) => page.locator('[data-borrados-v2]');

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
  test('está en el Speech original, que tiene tildes', async ({ page }) => {
    await abrir(page);

    await expect(editor(page)).toBeVisible();
    await expect(page.locator('[data-speech-gsm7]')).toHaveText(HINT_ES);
    await expect(page.locator('[data-speech-gsm7]')).toBeVisible();
  });

  test('está en una versión propia', async ({ page }) => {
    await abrirV2(page);

    await expect(editor(page)).toBeVisible();
    await expect(page.locator('[data-speech-gsm7]')).toHaveText(HINT_ES);
    await expect(page.locator('[data-speech-gsm7]')).toBeVisible();
  });

  test('en inglés, el hint está traducido', async ({ page }) => {
    await abrir(page, undefined, 'en');

    await expect(page.locator('[data-speech-gsm7]')).toHaveText(HINT_EN);
    await expect(page.locator('body')).not.toContainText('mowaMes.');
  });
});

test.describe('«Al enviar se borran: …» en el Speech original', () => {
  test('con tildes y sin nada que se borre, no muestra ninguna línea en ningún segmento', async ({ page }) => {
    await abrir(page);

    for (let i = 0; i < 6; i += 1) {
      await segmentos(page).nth(i).click();
      await expect(lineaV2(page)).toBeHidden();
    }
  });
});

test.describe('«Al enviar se borran: …» bajo el editor', () => {
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

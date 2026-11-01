/**
 * The speech of /mowa-mes/configuracion (T-MTE-F4), end to end against intercepted APIs: the module's own fake, the
 * engine's fake and `api-falsa-speech-v2.ts` over them. Every version is a v2 since M-B3 (M-F1 took the screen of
 * two parts out): one editor, one segment at a time.
 *
 * What costs a campaign when it is wrong: the original is never changed by looking at it, a segment with nothing is
 * never sent, a level is never claimed without a maximum length, and a problem reads from the catalogue it came from.
 */
import { expect, test, type Page } from '@playwright/test';

import { apiMowaMes, type ApiFalsaMowaMes } from './api-falsa-mowa-mes';
import { montarConfiguracion, versionV2Sintetica, type ApiFalsaSpeechV2 } from './api-falsa-speech-v2';
import type { ApiFalsaTextoEnriquecido } from './api-falsa-texto-enriquecido';

const RUTA = '/mowa-mes/configuracion';

interface Contexto {
  api: ApiFalsaMowaMes;
  v2: ApiFalsaSpeechV2;
  motor: ApiFalsaTextoEnriquecido;
}

async function abrir(
  page: Page,
  ajustar?: (api: ApiFalsaMowaMes, v2: ApiFalsaSpeechV2, motor: ApiFalsaTextoEnriquecido) => void,
): Promise<Contexto> {
  const api = apiMowaMes();
  // The module's fake first, so the scenario can change what the layers read; the layers read it when they answer.
  const { v2, motor } = await montarConfiguracion(page, api);
  ajustar?.(api, v2, motor);
  await page.goto(RUTA);
  await expect(page.getByRole('heading', { name: 'Configuración de MOWA MES' })).toBeVisible();
  await expect(segmentos(page)).toHaveCount(6);
  return { api, v2, motor };
}

const version = (page: Page) => page.locator('#mm-version');
const editor = (page: Page) => page.locator('#mm-speech-v2');
const segmentos = (page: Page) => editor(page).locator('[data-segmento-botones] button');
const guardar = (page: Page) => page.locator('[data-speech-guardar]');
const pedidosV2 = (v2: ApiFalsaSpeechV2, metodo: string, ruta: string) =>
  v2.pedidos.filter((p) => p.metodo === metodo && p.ruta === ruta);

/** Guardar waits for the editor to finish validating, so press until it takes. */
async function guardarYEsperar(page: Page, mensaje: string | RegExp) {
  await expect(async () => {
    await guardar(page).click();
    await expect(page.getByText(mensaje).first()).toBeVisible({ timeout: 1500 });
  }).toPass();
}

/** Something typed in the 9 a 30 segment: the original is never changed, so what is saved from it is a new version. */
async function escribirEnSegmento(page: Page) {
  await segmentos(page).nth(2).click();
  await editor(page).getByRole('textbox').last().fill(', pague ya y evite el cobro.');
}

test.describe('el Speech original', () => {
  test('se abre en el editor, con sus seis segmentos y su aviso: no hay tabla de dos partes ni «Convertir a v2»', async ({ page }) => {
    await abrir(page);

    await expect(editor(page)).toBeVisible();
    await expect(segmentos(page)).toHaveCount(6);
    await expect(page.locator('[data-speech-inmutable]')).toBeVisible();
    await expect(page.locator('[data-speech-inmutable]')).toContainText('Este es el Speech original: no se modifica.');
    await expect(page.getByRole('button', { name: 'Convertir a v2' })).toHaveCount(0);
    await expect(page.locator('table.mm-speech__tabla')).toHaveCount(0);
  });

  test('guardar desde él crea una versión nueva basada en él, y él no cambia', async ({ page }) => {
    const { api, v2 } = await abrir(page);
    await escribirEnSegmento(page);
    await page.locator('#mm-speech-nombre').fill('Speech por piezas');

    await guardarYEsperar(page, 'Versión nueva creada.');

    const [creacion] = pedidosV2(v2, 'POST', '/mowa-mes/speech');
    const cuerpo = creacion.cuerpo as {
      nombre: string;
      basada_en_id: number;
      expresiones: Array<{ segmento: string; expresion: { nodos: unknown[] } }>;
    };
    expect(cuerpo).toMatchObject({ nombre: 'Speech por piezas', basada_en_id: 1 });
    expect(cuerpo.expresiones.map((e) => e.segmento)).toEqual(['preventiva', '1_a_8', '9_a_30', '31_a_60', '61_a_90', '91_a_120']);
    expect(api.versiones.at(-1)).toMatchObject({ nombre: 'Speech por piezas' });
    expect(api.versiones[0]).toMatchObject({ original: true });
    expect(pedidosV2(v2, 'PUT', '/mowa-mes/speech/1')).toHaveLength(0);

    // The original keeps its notice and its messages.
    await version(page).selectOption({ label: 'Speech original (original)' });
    await expect(page.locator('[data-speech-inmutable]')).toBeVisible();
    await expect(page.locator('[data-speech-inmutable]')).toContainText('Este es el Speech original');
  });

  test('un nombre repetido se dice y lo escrito se conserva', async ({ page }) => {
    const { v2 } = await abrir(page, (_api, speech) => {
      speech.respuestasCrear = [{ estado: 409, cuerpo: { detail: 'Ya existe', codigo: null } }];
    });
    await escribirEnSegmento(page);

    await guardarYEsperar(page, 'Ya existe una versión con ese nombre.');

    await expect(editor(page)).toBeVisible();
    await expect(editor(page).getByRole('textbox').last()).toHaveValue(/pague ya y evite el cobro\.$/);
    expect(pedidosV2(v2, 'POST', '/mowa-mes/speech').length).toBeGreaterThan(0);
  });
});

test.describe('una versión v2 guardada', () => {
  async function conV2(page: Page, ajustar?: (v: ReturnType<typeof versionV2Sintetica>) => void) {
    const contexto = await abrir(page, (api) => {
      const v = versionV2Sintetica(api.versiones[0]);
      ajustar?.(v);
      api.versiones.push(v);
    });
    await version(page).selectOption({ label: 'Speech v2' });
    await expect(editor(page)).toBeVisible();
    await expect(segmentos(page)).toHaveCount(6);
    return contexto;
  }

  test('cada versión abre su editor, con su aviso: el original dice que no se modifica, una propia no dice nada', async ({ page }) => {
    await conV2(page);
    await expect(page.locator('[data-speech-inmutable]')).toBeHidden();

    await version(page).selectOption({ label: 'Speech original (original)' });

    await expect(editor(page)).toBeVisible();
    await expect(page.locator('[data-speech-inmutable]')).toBeVisible();
    await expect(page.locator('[data-speech-inmutable]')).toContainText('Este es el Speech original');
  });

  test('armar un segmento no pide teclear sintaxis y viaja como expresión', async ({ page }) => {
    const { v2 } = await conV2(page);
    await segmentos(page).nth(2).click();

    await editor(page).getByRole('textbox').last().fill(', pague ya y evite el cobro.');
    await page.locator('#mm-speech-nombre').fill('Speech 2 corregido');

    await guardarYEsperar(page, 'Versión guardada.');
    const [edicion] = pedidosV2(v2, 'PUT', '/mowa-mes/speech/20');
    const cuerpo = edicion.cuerpo as { nombre: string; expresiones: Array<{ segmento: string; expresion: { nodos: Array<{ tipo: string; valor?: string }> } }> };
    expect(cuerpo.nombre).toBe('Speech 2 corregido');
    const segmento = cuerpo.expresiones.find((e) => e.segmento === '9_a_30');
    expect(segmento?.expresion.nodos.at(-1)).toMatchObject({ tipo: 'texto', valor: ', pague ya y evite el cobro.' });
  });

  test('cada segmento lleva su nivel con el largo, que sale del backend', async ({ page }) => {
    await conV2(page);

    // The original's 9 a 30 measures 156: over the warning, under the limit.
    await expect(segmentos(page).nth(2)).toContainText('Más de 150 · 156');
    await expect(segmentos(page).nth(0)).toContainText('Cabe');
  });

  test('un segmento sin máximo explica el motivo y nunca dice «Cabe»', async ({ page }) => {
    await conV2(page, (v) => {
      const e = v.expresiones.find((x) => x.segmento === '1_a_8')!;
      e.expresion = { nodos: [{ tipo: 'variable', nombre: 'titular', funciones: [], obligatoria: true }] };
    });

    const fila = segmentos(page).nth(1);
    await expect(fila).toContainText('No se puede calcular el largo máximo');
    await expect(fila).not.toContainText('Cabe');
  });

  test('sin WhatsApp de contacto, el segmento que lo usa dice «Falta WhatsApp» y se avisa', async ({ page }) => {
    await abrir(page, (api) => {
      api.configuracion.whatsapp_contacto = null;
      api.versiones.push(versionV2Sintetica(api.versiones[0]));
    });
    await version(page).selectOption({ label: 'Speech v2' });

    await expect(segmentos(page).nth(3)).toContainText('Falta WhatsApp');
    await expect(page.locator('[data-speech-falta-whatsapp]')).toBeVisible();
  });

  test('un segmento sin mensaje no se manda: se dice cuál y no hay pedido', async ({ page }) => {
    const { v2 } = await conV2(page, (v) => {
      v.expresiones.find((x) => x.segmento === '61_a_90')!.expresion = { nodos: [] };
    });
    await page.locator('#mm-speech-nombre').fill('Otro nombre');

    await guardar(page).click();

    await expect(page.locator('#mm-speech-error')).toContainText('Estos segmentos no tienen mensaje: 61 a 90');
    expect(pedidosV2(v2, 'PUT', '/mowa-mes/speech/20')).toHaveLength(0);
  });

  test('los problemas del backend se muestran por segmento y se traducen por su catálogo', async ({ page }) => {
    const { v2 } = await conV2(page);
    v2.respuestasCrear = [
      {
        estado: 400,
        cuerpo: {
          detail: 'No se guarda',
          problemas: [
            { segmento: '9_a_30', campo: 'expresion', detalle: 'crudo uno', codigo: 'telefono_invalido', catalogo: 'mowa_mes', ubicacion: null },
            { segmento: '1_a_8', campo: 'expresion', detalle: 'crudo dos', codigo: 'telefono_invalido', catalogo: 'texto', ubicacion: null },
          ],
        },
      },
    ];
    // An immutable base is saved as a new version: the scripted answer is the create call's.
    await version(page).selectOption({ label: 'Speech original (original)' });
    await escribirEnSegmento(page);

    await guardarYEsperar(page, /Sin teléfono válido/);

    const lista = page.locator('[data-speech-problemas-lista]');
    await expect(lista).toContainText('9 a 30: Sin teléfono válido: falta o no tiene 9 dígitos');
    await expect(lista).toContainText('1 a 8: El teléfono no es válido: debe tener 9 dígitos');
    await expect(lista).not.toContainText('crudo');
  });

  test('el aviso del segmento con un producto real está a la vista', async ({ page }) => {
    await conV2(page);

    await expect(
      page.getByText(
        'el segmento sale de sus días de atraso ajustados a hoy, como si el mensaje se enviara hoy; en la campaña se ajustan a su fecha de envío',
      ),
    ).toBeVisible();
  });
});

test.describe('en inglés', () => {
  test('el editor no deja claves sin traducir', async ({ page }) => {
    await page.addInitScript(() => {
      try {
        localStorage.setItem('app:appearance', JSON.stringify({ language: 'en', theme: 'light' }));
      } catch {
        /* storage blocked: the page keeps its default */
      }
    });
    await montarConfiguracion(page, apiMowaMes());
    await page.goto(RUTA);

    await expect(editor(page)).toBeVisible();
    await expect(segmentos(page)).toHaveCount(6);
    await expect(page.locator('body')).not.toContainText('mowaMes.');
    await expect(page.locator('[data-speech-inmutable]')).toBeVisible();
    await expect(page.locator('[data-speech-inmutable]')).toContainText('This is the original speech');
  });
});

test.describe('teclado y anchos', () => {
  for (const ancho of [360, 768, 1440]) {
    test(`a ${ancho} px el editor v2 no desborda la página y sus segmentos se alcanzan`, async ({ page }) => {
      await page.setViewportSize({ width: ancho, height: 900 });
      await abrir(page);

      const desborde = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(desborde).toBeLessThanOrEqual(0);
      // Wide: the segments are a list of buttons; narrow: a select. One of them must be usable.
      const lista = segmentos(page).first();
      const selector = editor(page).locator('[data-segmento-select]');
      await expect
        .poll(async () => (await lista.isVisible()) || (await selector.isVisible()))
        .toBe(true);
      await expect(editor(page).getByRole('textbox').last()).toBeVisible();
    });
  }
});

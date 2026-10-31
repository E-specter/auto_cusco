/**
 * «Para subir a MES» (RF-MM-35, T-MM-C11 M-F5): once the campaign exists the screen says what to do with it,
 * in three steps: download the files, fill in MES's form copying each datum, and import the report from the
 * follow-up. Every value is synthetic.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import {
  apiMowaMes,
  campanaDesdeEntrada,
  montarApiMowaMes,
  previsualizacionCampanaSintetica,
} from './api-falsa-mowa-mes';
import { montarSeleccion } from './apoyo-seleccion';

test.use({ timezoneId: 'America/Lima', reducedMotion: 'reduce' });

const REGLAS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];
const ARCHIVOS = [
  { numero: 2, filas: 482, supervision: 0, bytes: 29_000, nombre: 'mowa_mes_campana_9_2_de_2.xlsx' },
  { numero: 1, filas: 500, supervision: 2, bytes: 30_000, nombre: 'mowa_mes_campana_9_1_de_2.xlsx' },
];

function entradaMinima() {
  return {
    fecha_corte: '2026-09-13',
    filtros: [],
    cantidad: 1000,
    seleccion_id: 1,
    tipo_carga: 'masiva' as const,
    salida: 'numero_largo' as const,
    herramientas: { keyword: false, respuesta_automatica: false, blacklist_indecopi: false, speech_optimizado: false },
    programacion: 'hora_determinada' as const,
    envios: ['2026-09-14T09:00:00-05:00'],
  };
}

/** Opens the campaign screen, previews and creates campaign 9, which `parcial` can change. */
async function crearCampana(page: Page, parcial: Parameters<typeof campanaDesdeEntrada>[2] = {}): Promise<void> {
  const api = apiMowaMes();
  const previa = previsualizacionCampanaSintetica(entradaMinima(), {
    archivos_previstos_por_filas: [{ numero: 1, filas: 982, supervision: 2 }],
  });
  api.respuestas.previsualizarCampana = [{ estado: 200, cuerpo: previa }];
  const creada = campanaDesdeEntrada(
    { ...entradaMinima(), orden: null, descripcion: 'Preventiva 9 a 30 · septiembre', speech_id: null, whatsapp: null, supervisores: null, speech_huella: previa.speech.huella, confirmar_limite: false },
    9,
    { archivos: ARCHIVOS, ...parcial },
  );
  api.respuestas.crearCampana = [{ estado: 201, cuerpo: creada }];
  api.campanas = [creada, ...api.campanas];
  await montarApiMowaMes(page, api);
  await montarSeleccion(page);
  await page.goto('/mowa-mes/campana');
  await page.getByLabel('Selección guardada').selectOption({ label: 'Preventiva top 1000' });
  await page.getByRole('button', { name: 'Crear campaña' }).click();
  await expect(page.getByRole('heading', { name: 'Para subir a MES', level: 2 })).toBeVisible();
}

const panel = (page: Page) => page.locator('[data-panel-creada]');
const estadoCopia = (page: Page) => page.locator('[data-creada-copia-estado]');

test.describe('el aviso y los tres pasos', () => {
  test('un aviso de éxito con el id, y un panel con tres pasos numerados, en orden', async ({ page }) => {
    await crearCampana(page);

    const aviso = page.locator('[data-creada-aviso]');
    await expect(aviso).toHaveClass(/notice--success/);
    await expect(aviso).toHaveText('Se creó la campaña 9. Ahora súbela a MES con estos datos.');
    await expect(aviso.locator('svg')).toHaveCount(1);

    const pasos = panel(page).locator('ol > li');
    await expect(pasos).toHaveCount(3);
    await expect(pasos.nth(0).getByRole('heading', { level: 3 })).toHaveText('Descarga los archivos de carga');
    await expect(pasos.nth(1).getByRole('heading', { level: 3 })).toHaveText('Completa el formulario de MES');
    await expect(pasos.nth(2).getByRole('heading', { level: 3 })).toHaveText('Después del envío, importa el reporte');
    // The form of the campaign is gone: what is left is to upload it.
    await expect(page.locator('[data-formulario]')).toBeHidden();
  });

  test('paso 1: un botón por archivo, con su nombre, en el orden de {archivo}', async ({ page }) => {
    await crearCampana(page);

    const archivos = panel(page).locator('[data-creada-archivos] li');
    await expect(archivos).toHaveCount(2);
    await expect(archivos.nth(0).locator('.mm-subir__nombre')).toHaveText('mowa_mes_campana_9_1_de_2.xlsx');
    await expect(archivos.nth(1).locator('.mm-subir__nombre')).toHaveText('mowa_mes_campana_9_2_de_2.xlsx');
    await expect(archivos.nth(0)).toContainText('500 filas · 2 de supervisión');
    await expect(archivos.nth(0).getByRole('button', { name: 'Descargar el archivo 1' })).toBeVisible();
    await expect(archivos.nth(1).getByRole('button', { name: 'Descargar el archivo 2' })).toBeVisible();
    expect(await archivos.nth(0).locator('.mm-subir__nombre').evaluate((el) => getComputedStyle(el).fontFamily)).toMatch(/mono/i);
  });

  test('paso 1: descargar entrega el archivo con el nombre del servidor', async ({ page }) => {
    await crearCampana(page);

    const descarga = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Descargar el archivo 1' }).click();
    expect((await descarga).suggestedFilename()).toBe('mowa_mes_campana_9_1_de_2.xlsx');
  });

  test('paso 3: el enlace lleva al seguimiento de esa campaña', async ({ page }) => {
    await crearCampana(page);

    const enlace = panel(page).getByRole('link', { name: 'Ir al seguimiento de la campaña' });
    await expect(enlace).toHaveAttribute('href', '/mowa-mes/seguimiento?campana=9');
    await enlace.click();
    await expect(page).toHaveURL(/\/mowa-mes\/seguimiento\?campana=9$/);
  });

  test('«Armar otra campaña» sigue ahí', async ({ page }) => {
    await crearCampana(page);

    await expect(panel(page).getByRole('button', { name: 'Armar otra campaña' })).toBeVisible();
  });
});

test.describe('paso 2: los datos del formulario de MES', () => {
  const ESPERADOS = [
    ['Tipo de carga', 'Masiva'],
    ['Descripción de la campaña', 'Preventiva 9 a 30 · septiembre'],
    ['Salida', 'Número largo'],
    ['Herramientas', 'Keyword, Blacklist Indecopi'],
    ['Programación del envío', 'Enviar en hora determinada: 14/09/2026 09:00'],
  ] as const;
  const CONFIGURADA = { herramientas: { keyword: true, respuesta_automatica: false, blacklist_indecopi: true, speech_optimizado: false } };

  test('una lista de definición con los cinco datos, en el orden del formulario', async ({ page }) => {
    await crearCampana(page, CONFIGURADA);

    const filas = panel(page).locator('dl > div');
    await expect(filas).toHaveCount(5);
    for (const [indice, [dato, valor]] of ESPERADOS.entries()) {
      await expect(filas.nth(indice).locator('dt')).toHaveText(dato);
      await expect(filas.nth(indice).locator('dd .mm-subir__valor')).toHaveText(valor);
    }
  });

  test('cada «Copiar» deja en el portapapeles exactamente lo que se lee, y lo anuncia', async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await crearCampana(page, CONFIGURADA);

    for (const [dato, valor] of ESPERADOS) {
      await page.getByRole('button', { name: `Copiar ${dato}`, exact: true }).click();
      await expect(estadoCopia(page)).toHaveText(`Copiado: ${dato}`);
      expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(valor);
    }
  });

  test('al copiar, el icono pasa a «copiado» y a los 2 s vuelve', async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await crearCampana(page, CONFIGURADA);
    const boton = page.getByRole('button', { name: 'Copiar Salida', exact: true });
    const antes = await boton.innerHTML();

    await boton.click();
    await expect(estadoCopia(page)).toHaveText('Copiado: Salida');
    expect(await boton.innerHTML()).not.toBe(antes);

    await expect.poll(() => boton.innerHTML(), { timeout: 5000 }).toBe(antes);
  });

  test('una segunda copia del mismo dato se vuelve a anunciar', async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await crearCampana(page, CONFIGURADA);
    const boton = page.getByRole('button', { name: 'Copiar Salida', exact: true });

    await boton.click();
    await expect(estadoCopia(page)).toHaveText('Copiado: Salida');
    // The region is emptied and written again, so a screen reader reads it a second time.
    const lecturas = page.evaluate(
      () =>
        new Promise<string[]>((resolver) => {
          const nodo = document.querySelector('[data-creada-copia-estado]')!;
          const vistas: string[] = [];
          new MutationObserver(() => vistas.push(nodo.textContent ?? '')).observe(nodo, { childList: true, characterData: true, subtree: true });
          window.setTimeout(() => resolver(vistas), 600);
        }),
    );
    await boton.click();
    const vistas = await lecturas;
    expect(vistas).toContain('');
    expect(vistas.at(-1)).toBe('Copiado: Salida');
  });

  test('si el navegador no deja copiar, el dato queda seleccionado y se dice cómo copiarlo', async ({ page }) => {
    await page.addInitScript(() => {
      Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: () => Promise.reject(new Error('negado')) } });
      document.execCommand = () => false;
    });
    await crearCampana(page, CONFIGURADA);

    await page.getByRole('button', { name: 'Copiar Descripción de la campaña', exact: true }).click();

    await expect(estadoCopia(page)).toHaveText('No se pudo copiar Descripción de la campaña. Quedó seleccionado: cópialo con Ctrl+C.');
    expect(await page.evaluate(() => window.getSelection()?.toString())).toBe('Preventiva 9 a 30 · septiembre');
  });

  test('sin herramientas dice «Ninguna» y varias fechas de envío van todas', async ({ page }) => {
    await crearCampana(page, {
      programacion: 'diferentes_horas',
      envios: ['2026-09-14T09:00:00-05:00', '2026-09-14T15:30:00-05:00'],
    });

    const filas = panel(page).locator('dl > div');
    await expect(filas.nth(3).locator('.mm-subir__valor')).toHaveText('Ninguna');
    await expect(filas.nth(4).locator('.mm-subir__valor')).toHaveText(
      'Enviar en diferentes horas: 14/09/2026 09:00; 14/09/2026 15:30',
    );
  });

  test('en inglés traduce el panel y los datos; las fechas son las mismas', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    await crearCampanaEnIngles(page);

    await expect(page.locator('[data-creada-aviso]')).toHaveText('Campaign 9 was created. Now upload it to MES with this data.');
    await expect(panel(page).getByRole('heading', { name: 'Fill in the MES form', level: 3 })).toBeVisible();
    await expect(panel(page).locator('dl > div').nth(0).locator('dt')).toHaveText('Load type');
    await expect(panel(page).getByRole('button', { name: 'Copy Load type', exact: true })).toBeVisible();
    await expect(panel(page).locator('dl > div').nth(4).locator('.mm-subir__valor')).toContainText('14/09/2026 09:00');
  });
});

/** The English run reuses `crearCampana`'s steps; the language is already in `localStorage`. */
async function crearCampanaEnIngles(page: Page): Promise<void> {
  const api = apiMowaMes();
  const previa = previsualizacionCampanaSintetica(entradaMinima(), {
    archivos_previstos_por_filas: [{ numero: 1, filas: 982, supervision: 2 }],
  });
  api.respuestas.previsualizarCampana = [{ estado: 200, cuerpo: previa }];
  api.respuestas.crearCampana = [
    {
      estado: 201,
      cuerpo: campanaDesdeEntrada(
        { ...entradaMinima(), orden: null, descripcion: 'Preventive', speech_id: null, whatsapp: null, supervisores: null, speech_huella: previa.speech.huella, confirmar_limite: false },
        9,
        { archivos: ARCHIVOS },
      ),
    },
  ];
  await montarApiMowaMes(page, api);
  await montarSeleccion(page);
  await page.goto('/mowa-mes/campana');
  await page.getByLabel('Saved selection').selectOption({ label: 'Preventiva top 1000' });
  await page.getByRole('button', { name: 'Create campaign' }).click();
  await expect(page.getByRole('heading', { name: 'To upload to MES', level: 2 })).toBeVisible();
}

test.describe('anchos y accesibilidad', () => {
  test('a 360 px cada dato se apila: el nombre encima y el valor con su botón debajo, sin desbordar', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 900 });
    await crearCampana(page);

    const fila = panel(page).locator('dl > div').first();
    const nombre = (await fila.locator('dt').boundingBox())!;
    const valor = (await fila.locator('dd').boundingBox())!;
    expect(nombre.y + nombre.height).toBeLessThanOrEqual(valor.y + 1);
    const boton = (await fila.getByRole('button').boundingBox())!;
    expect(boton.x + boton.width).toBeLessThanOrEqual(361);
    const desborde = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(desborde).toBeLessThanOrEqual(0);
  });

  test('a 1280 px el nombre y el valor van lado a lado', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await crearCampana(page);

    const fila = panel(page).locator('dl > div').first();
    const nombre = (await fila.locator('dt').boundingBox())!;
    const valor = (await fila.locator('dd').boundingBox())!;
    expect(valor.x).toBeGreaterThan(nombre.x + nombre.width - 1);
  });

  for (const tema of ['light', 'dark'] as const) {
    for (const ancho of [1280, 360]) {
      test(`sin violaciones WCAG a ${ancho} px, tema ${tema === 'light' ? 'claro' : 'oscuro'}`, async ({ page }) => {
        await page.addInitScript((elegido) => {
          localStorage.setItem('app:appearance', JSON.stringify({ theme: elegido, language: 'es' }));
        }, tema);
        await page.setViewportSize({ width: ancho, height: 900 });
        await crearCampana(page, { herramientas: { keyword: true, respuesta_automatica: false, blacklist_indecopi: true, speech_optimizado: false } });

        const resultado = await new AxeBuilder({ page }).withTags(REGLAS).analyze();
        expect(resultado.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
      });
    }
  }
});

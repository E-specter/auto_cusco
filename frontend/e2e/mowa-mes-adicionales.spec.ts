/**
 * Additional fields in the MOWA MES screens (T-MM-F11; RF-64 to RF-66, docs/campos-adicionales-interfaz.md):
 * the readable names of the fields that left a product out, in follow-up and in the campaign preview, and the
 * notice of an archived field in the v2 speech editor. End to end against an intercepted API.
 *
 * What costs when it is wrong: a product left out with no way to know which field was empty, the technical
 * name (`ad_monto_mora`) where a person reads «Monto en mora», a reason in the filter that shows as a raw key,
 * or a speech that still uses an archived field with nobody told. Every name and number is synthetic.
 *
 * `CAPTURAS_F11`: if set, the new states are also saved there as screenshots, light and dark, for the review.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Locator, type Page, type Route } from '@playwright/test';

import type { Campos, SeleccionGuardada, Version } from '../src/lib/api';
import type { Exclusion, PeticionCampanaEntrada } from '../src/lib/api-mowa-mes';
import { camposSinteticos, seleccionGuardada, version } from './api-falsa';
import {
  apiMowaMes,
  montarApiMowaMes,
  previsualizacionCampanaSintetica,
  type ApiFalsaMowaMes,
} from './api-falsa-mowa-mes';
import { apiSpeechV2, montarApiSpeechV2, versionV2Sintetica, type ApiFalsaSpeechV2 } from './api-falsa-speech-v2';
import { apiTextoEnriquecidoVacia, variablesAdicionalesSinteticas } from './api-falsa-texto-enriquecido';

const REGLAS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];
const CAPTURAS = process.env.CAPTURAS_F11;

test.use({ timezoneId: 'America/Lima', reducedMotion: 'reduce' });

const MORA = { nombre: 'ad_monto_mora', etiqueta: 'Monto en mora' };
const ZONA = { nombre: 'ad_zona', etiqueta: 'Zona' };

/** Two additional fields missing, one missing, and an exclusion that has nothing to do with fields. */
const EXCLUSIONES: Exclusion[] = [
  { pagare: '000000000000000901', codigo: 'falta_campo_adicional', campos: [MORA, ZONA] },
  { pagare: '000000000000000902', codigo: 'falta_campo_adicional', campos: [ZONA] },
  { pagare: '000000000000000903', codigo: 'telefono_invalido', campos: [] },
];

type Tema = 'light' | 'dark';
const TEMAS: Tema[] = ['light', 'dark'];
const nombreDelTema = (tema: Tema) => (tema === 'light' ? 'claro' : 'oscuro');

async function fijarApariencia(page: Page, idioma: 'es' | 'en', tema: Tema): Promise<void> {
  await page.addInitScript(
    ([lenguaje, elegido]) => {
      try {
        localStorage.setItem('app:appearance', JSON.stringify({ language: lenguaje, theme: elegido }));
      } catch {
        /* storage blocked: the page keeps its default */
      }
    },
    [idioma, tema],
  );
}

async function capturar(zona: Locator, nombre: string, tema: Tema): Promise<void> {
  if (CAPTURAS) await zona.screenshot({ path: `${CAPTURAS}/${nombre}-${tema}.png` });
}

async function sinViolaciones(page: Page): Promise<void> {
  const resultado = await new AxeBuilder({ page }).withTags(REGLAS).analyze();
  const resumen = resultado.violations.map((v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`);
  expect(resumen).toEqual([]);
}

const json = (route: Route, estado: number, cuerpo: unknown) =>
  route.fulfill({ status: estado, contentType: 'application/json', body: JSON.stringify(cuerpo) });

// ---- Follow-up -------------------------------------------------------------------------------

test.describe('seguimiento: el detalle de una exclusión por campo adicional', () => {
  const RUTA = '/mowa-mes/seguimiento';

  async function abrir(page: Page, idioma: 'es' | 'en' = 'es', tema: Tema = 'light'): Promise<ApiFalsaMowaMes> {
    await fijarApariencia(page, idioma, tema);
    const api = apiMowaMes();
    api.exclusiones.set(1, EXCLUSIONES.map((e) => ({ ...e })));
    await montarApiMowaMes(page, api);
    await page.goto(RUTA);
    await expect(page.locator('.mm-exclusiones__tabla tbody tr')).toHaveCount(EXCLUSIONES.length);
    return api;
  }

  const filas = (page: Page) => page.locator('.mm-exclusiones__tabla tbody tr');

  test('con dos campos muestra el tag corto y la frase con los nombres legibles; con uno, en singular', async ({ page }) => {
    await abrir(page);

    const dos = filas(page).nth(0);
    await expect(dos.locator('.tag')).toHaveText('Sin campo adicional');
    await expect(dos.locator('td').nth(2)).toHaveText(
      'Faltan los campos adicionales «Monto en mora», «Zona», que el mensaje necesita.',
    );
    const uno = filas(page).nth(1);
    await expect(uno.locator('.tag')).toHaveText('Sin campo adicional');
    await expect(uno.locator('td').nth(2)).toHaveText('Falta el campo adicional «Zona», que el mensaje necesita.');
    // Lo que se lee es la etiqueta, nunca el nombre técnico.
    await expect(page.locator('.mm-exclusiones__tabla')).not.toContainText('ad_');
  });

  test('otro motivo sigue diciendo lo que decía, sin nombres', async ({ page }) => {
    await abrir(page);

    const otra = filas(page).nth(2);
    await expect(otra.locator('.tag')).toHaveText('Teléfono inválido');
    await expect(otra.locator('td').nth(2)).not.toContainText('«');
    await expect(otra.locator('td').nth(2)).not.toContainText('campo adicional');
  });

  test('el filtro ofrece «Sin campo adicional» y filtra por ese motivo', async ({ page }) => {
    const api = await abrir(page);
    const motivo = page.getByLabel('Motivo', { exact: true });

    await expect(motivo.locator('option', { hasText: 'Sin campo adicional' })).toHaveCount(1);
    // Ninguna opción ni etiqueta es la clave cruda.
    await expect(motivo).not.toContainText('mowaMes.');
    await motivo.selectOption('falta_campo_adicional');

    await expect(filas(page)).toHaveCount(2);
    const ultimo = api.pedidos.filter((p) => p.ruta.split('?')[0] === '/mowa-mes/campanas/1/exclusiones').at(-1)!;
    expect(new URL(ultimo.ruta, 'http://x').searchParams.get('codigo')).toBe('falta_campo_adicional');
  });

  test('en inglés, las comillas son las del inglés y el singular y el plural salen bien', async ({ page }) => {
    await abrir(page, 'en');

    await expect(filas(page).nth(0).locator('.tag')).toHaveText('No additional field');
    await expect(filas(page).nth(0).locator('td').nth(2)).toHaveText(
      'The additional fields “Monto en mora”, “Zona” are missing, and the message needs them.',
    );
    await expect(filas(page).nth(1).locator('td').nth(2)).toHaveText(
      'The additional field “Zona” is missing, and the message needs it.',
    );
  });

  for (const tema of TEMAS) {
    test(`axe, tema ${nombreDelTema(tema)}: la exclusión con campos`, async ({ page }) => {
      await abrir(page, 'es', tema);
      await expect(filas(page).nth(0).locator('td').nth(2)).toContainText('Monto en mora');

      await capturar(page.locator('.mm-exclusiones__tabla'), 'seguimiento-exclusion-con-campos', tema);
      await sinViolaciones(page);
    });
  }
});

// ---- Campaign preview ----------------------------------------------------------------------

function entradaMinima(): PeticionCampanaEntrada {
  return {
    fecha_corte: '2026-09-13',
    filtros: [],
    cantidad: 1000,
    seleccion_id: 1,
    tipo_carga: 'masiva',
    salida: 'numero_largo',
    herramientas: { keyword: false, respuesta_automatica: false, blacklist_indecopi: false, speech_optimizado: false },
    programacion: 'hora_determinada',
    envios: ['2026-09-14T09:00:00-05:00'],
  };
}

/** The compact selector's own calls, layered over the module's mock (as in mowa-mes-campana.spec.ts). */
async function montarSeleccion(page: Page): Promise<void> {
  const versiones: Version[] = [version({ fecha_corte: '2026-09-13', vigente: true })];
  const campos: Campos = camposSinteticos();
  const selecciones: SeleccionGuardada[] = [seleccionGuardada({ id: 1, nombre: 'Preventiva top 1000', cantidad: 1000 })];
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const ruta = url.pathname.replace(/^\/api/, '');
    const metodo = route.request().method();
    if (ruta === '/cargas' && metodo === 'GET') return json(route, 200, versiones);
    if (ruta === '/cartera/campos') return json(route, 200, campos);
    if (ruta === '/selecciones' && metodo === 'GET') return json(route, 200, selecciones);
    return route.fallback();
  });
}

/** The campaign page with the preview scripted: `parcial` overrides what the fake builds (exclusions, archived fields). */
async function abrirCampana(
  page: Page,
  parcial: Parameters<typeof previsualizacionCampanaSintetica>[1],
  idioma: 'es' | 'en' = 'es',
  tema: Tema = 'light',
): Promise<void> {
  await fijarApariencia(page, idioma, tema);
  const api = apiMowaMes();
  api.respuestas.previsualizarCampana = [{ estado: 200, cuerpo: previsualizacionCampanaSintetica(entradaMinima(), parcial) }];
  await montarApiMowaMes(page, api);
  await montarSeleccion(page);
  await page.goto('/mowa-mes/campana');
  await page.getByLabel(idioma === 'es' ? 'Selección guardada' : 'Saved selection').selectOption({ label: 'Preventiva top 1000' });
}

test.describe('campaña: los nombres junto al motivo de la exclusión', () => {
  const RUTA = '/mowa-mes/campana';

  async function abrir(page: Page, idioma: 'es' | 'en' = 'es', tema: Tema = 'light'): Promise<void> {
    await abrirCampana(
      page,
      { exclusiones: { total: EXCLUSIONES.length, limite: 100, desplazamiento: 0, exclusiones: EXCLUSIONES } },
      idioma,
      tema,
    );
    await expect(filas(page)).toHaveCount(EXCLUSIONES.length);
  }

  const filas = (page: Page) => page.locator('.mm-exclusiones__tabla tbody tr');
  const celdaDelMotivo = (page: Page, fila: number) => filas(page).nth(fila).locator('td').nth(1);

  test('los nombres van en la misma celda, después del tag, como texto normal', async ({ page }) => {
    await abrir(page);

    await expect(celdaDelMotivo(page, 0).locator('.tag')).toHaveText('Sin campo adicional');
    await expect(celdaDelMotivo(page, 0)).toHaveText('Sin campo adicional «Monto en mora», «Zona»');
    await expect(celdaDelMotivo(page, 1)).toHaveText('Sin campo adicional «Zona»');
    // Los nombres no son un tag: son texto de la celda.
    await expect(celdaDelMotivo(page, 0).locator('.tag')).toHaveCount(1);
    await expect(celdaDelMotivo(page, 0).locator('.mm-exclusion__campos')).toHaveText('«Monto en mora», «Zona»');
  });

  test('en ancho de escritorio los nombres empiezan bajo el tag, nunca a su lado', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await abrir(page);

    for (const fila of [0, 1]) {
      const cajaTag = await celdaDelMotivo(page, fila).locator('.tag').boundingBox();
      const cajaNombres = await celdaDelMotivo(page, fila).locator('.mm-exclusion__campos').boundingBox();
      // El borde de arriba de los nombres no está por encima del borde de abajo del tag.
      expect(cajaNombres!.y).toBeGreaterThanOrEqual(cajaTag!.y + cajaTag!.height - 0.5);
    }
  });

  test('el motivo que no es de campos queda solo con su tag, y no hay columna de detalle', async ({ page }) => {
    await abrir(page);

    await expect(celdaDelMotivo(page, 2)).toHaveText('Teléfono inválido');
    await expect(celdaDelMotivo(page, 2).locator('.mm-exclusion__campos')).toHaveCount(0);
    await expect(page.locator('.mm-exclusiones__tabla thead th')).toHaveCount(2);
  });

  test('en inglés, con las comillas del inglés', async ({ page }) => {
    await abrir(page, 'en');

    await expect(celdaDelMotivo(page, 0)).toHaveText('No additional field “Monto en mora”, “Zona”');
  });

  for (const tema of TEMAS) {
    test(`a 360 px la celda no desborda y el texto pasa bajo el tag, tema ${nombreDelTema(tema)}`, async ({ page }) => {
      await page.setViewportSize({ width: 360, height: 900 });
      await abrir(page, 'es', tema);

      const desborde = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(desborde).toBeLessThanOrEqual(0);
      const celda = celdaDelMotivo(page, 0);
      await celda.scrollIntoViewIfNeeded();
      const cajaCelda = await celda.boundingBox();
      const cajaTag = await celda.locator('.tag').boundingBox();
      const cajaNombres = await celda.locator('.mm-exclusion__campos').boundingBox();
      expect(cajaCelda!.x + cajaCelda!.width).toBeLessThanOrEqual(361);
      expect(cajaNombres!.x + cajaNombres!.width).toBeLessThanOrEqual(cajaCelda!.x + cajaCelda!.width + 1);
      expect(cajaTag!.width).toBeGreaterThan(0);
      expect(cajaNombres!.y).toBeGreaterThanOrEqual(cajaTag!.y + cajaTag!.height - 0.5);

      await capturar(celda, 'campana-exclusion-con-campos-360px', tema);
      await sinViolaciones(page);
    });
  }
});

// ---- Campaign preview: archived fields ---------------------------------------------------------

test.describe('campaña: el aviso de campos archivados que el speech usa (T-MM-F12)', () => {
  const REGION = { nombre: 'ad_region', etiqueta: 'Región' };
  const ZONA = { nombre: 'ad_zona', etiqueta: 'Zona' };
  const UNO =
    'El speech usa el campo archivado «Región». Las sábanas cargadas después de archivarlo ya no lo traen, y los productos que lo necesitan quedan fuera. Para evitarlo, reactívalo en Cargas › Campos adicionales o quítalo del speech.';
  const VARIOS =
    'El speech usa los campos archivados «Región», «Zona». Las sábanas cargadas después de archivarlos ya no los traen, y los productos que los necesitan quedan fuera. Para evitarlo, reactívalos en Cargas › Campos adicionales o quítalos del speech.';

  const aviso = (page: Page) => page.locator('[data-campos-archivados]');
  const resultado = (page: Page) => page.locator('[data-resultado]');

  async function abrir(page: Page, camposArchivados: Array<{ nombre: string; etiqueta: string }>, idioma: 'es' | 'en' = 'es', tema: Tema = 'light') {
    await abrirCampana(page, { campos_archivados: camposArchivados }, idioma, tema);
    await expect(resultado(page)).toBeVisible();
  }

  test('con un campo archivado, el aviso con su nombre legible, en singular y como advertencia', async ({ page }) => {
    await abrir(page, [REGION]);

    await expect(aviso(page)).toBeVisible();
    await expect(aviso(page)).toHaveText(UNO);
    await expect(aviso(page)).toHaveClass(/notice--warning/);
    await expect(aviso(page).locator('svg')).toHaveCount(1);
    await expect(aviso(page)).not.toContainText('ad_region');
  });

  test('con dos, el plural con los dos nombres, en el orden que llegan', async ({ page }) => {
    await abrir(page, [REGION, ZONA]);

    await expect(aviso(page)).toHaveText(VARIOS);
  });

  test('va bajo el resumen y antes de las cifras', async ({ page }) => {
    await abrir(page, [REGION]);

    const orden = await aviso(page).evaluate((el) => {
      const resumen = document.querySelector('[data-resumen]')!;
      const cifras = document.querySelector('[data-cifras]')!;
      return {
        despuesDelResumen: Boolean(resumen.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING),
        antesDeLasCifras: Boolean(el.compareDocumentPosition(cifras) & Node.DOCUMENT_POSITION_FOLLOWING),
      };
    });
    expect(orden).toEqual({ despuesDelResumen: true, antesDeLasCifras: true });
  });

  test('con la lista vacía no hay aviso', async ({ page }) => {
    await abrir(page, []);

    await expect(aviso(page)).toBeHidden();
    await expect(aviso(page)).toBeEmpty();
  });

  test('en inglés, el aviso está traducido, con las comillas del inglés', async ({ page }) => {
    await abrir(page, [REGION, ZONA], 'en');

    await expect(aviso(page)).toHaveText(
      'The speech uses the archived fields “Región”, “Zona”. Sheets loaded after they were archived no longer bring them, and the products that need them are left out. To avoid this, reactivate them in Uploads › Additional fields or remove them from the speech.',
    );
    await expect(aviso(page)).not.toContainText('mowaMes.');
  });

  for (const tema of TEMAS) {
    test(`a 360 px el aviso cabe y no hay violaciones, tema ${nombreDelTema(tema)}`, async ({ page }) => {
      await page.setViewportSize({ width: 360, height: 900 });
      await abrir(page, [REGION, ZONA], 'es', tema);
      await expect(aviso(page)).toHaveText(VARIOS);

      const desborde = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(desborde).toBeLessThanOrEqual(0);
      const caja = await aviso(page).boundingBox();
      expect(caja!.x + caja!.width).toBeLessThanOrEqual(361);

      await capturar(aviso(page), 'campana-aviso-archivados-360px', tema);
      await sinViolaciones(page);
    });
  }
});

// ---- v2 speech editor ------------------------------------------------------------------------

test.describe('configuración: el editor v2 con campos adicionales', () => {
  const RUTA = '/mowa-mes/configuracion';
  const AVISO =
    'El speech usa el campo archivado «Región». Las sábanas cargadas después de archivarlo ya no lo traen: en la campaña, los productos que lo necesitan quedan fuera. Para evitarlo, reactívalo en Cargas › Campos adicionales o quítalo del speech.';

  type Variable = { tipo: 'texto'; valor: string } | { tipo: 'variable'; nombre: string; funciones: Array<{ nombre: string; args: Array<string | number> }> };

  /** A v2 version whose «preventiva» segment is `nodos` (the rest keep the original's messages). */
  function versionConSegmento(api: ApiFalsaMowaMes, nombre: string, id: number, nodos: Variable[]) {
    const v = versionV2Sintetica(api.versiones[0], { id, nombre });
    const e = v.expresiones.find((x) => x.segmento === 'preventiva')!;
    e.expresion = {
      nodos: nodos.map((n) =>
        n.tipo === 'texto' ? n : { tipo: 'variable' as const, nombre: n.nombre, funciones: n.funciones, obligatoria: false },
      ),
    } as typeof e.expresion;
    api.versiones.push(v);
  }

  async function abrir(
    page: Page,
    ajustar: (api: ApiFalsaMowaMes) => void,
    opciones: { idioma?: 'es' | 'en'; tema?: Tema } = {},
  ): Promise<{ api: ApiFalsaMowaMes; v2: ApiFalsaSpeechV2 }> {
    await fijarApariencia(page, opciones.idioma ?? 'es', opciones.tema ?? 'light');
    const api = apiMowaMes();
    const v2 = apiSpeechV2();
    const motor = apiTextoEnriquecidoVacia();
    motor.catalogos['mowa_mes.speech'].contexto.variables.push(...variablesAdicionalesSinteticas());
    ajustar(api);
    await montarApiMowaMes(page, api);
    await montarApiSpeechV2(page, api, v2, motor);
    await page.goto(RUTA);
    await expect(page.locator('#mm-speech-title')).toBeVisible();
    await expect(page.locator('[data-speech-filas] tr[data-segmento="9_a_30"] [data-largo]')).not.toHaveText('—');
    return { api, v2 };
  }

  const selectorDeVersion = (page: Page) => page.locator('#mm-version');
  const editor = (page: Page) => page.locator('#mm-speech-v2');
  const segmentos = (page: Page) => editor(page).locator('[data-segmento-botones] button');
  const aviso = (page: Page) => page.locator('[data-speech-archivados]');

  async function abrirV2(page: Page, nombre: string): Promise<void> {
    await selectorDeVersion(page).selectOption({ label: nombre });
    await expect(editor(page)).toBeVisible();
    await expect(segmentos(page)).toHaveCount(6);
  }

  const CON_ARCHIVADO: Variable[] = [{ tipo: 'texto', valor: 'Hola ' }, { tipo: 'variable', nombre: 'ad_region', funciones: [] }];
  const SIN_ARCHIVADO: Variable[] = [{ tipo: 'texto', valor: 'Hola ' }, { tipo: 'variable', nombre: 'ad_zona', funciones: [{ nombre: 'primeros', args: [5] }] }];

  test('un speech que usa un campo archivado muestra el aviso con su nombre, después del de WhatsApp', async ({ page }) => {
    await abrir(page, (api) => versionConSegmento(api, 'Speech v2 archivado', 30, CON_ARCHIVADO));
    await abrirV2(page, 'Speech v2 archivado');

    await expect(aviso(page)).toBeVisible();
    await expect(aviso(page)).toHaveText(AVISO);
    await expect(aviso(page)).toHaveClass(/notice--warning/);
    // Su propio texto, no el del motor (el de Cartera y /columnas dice «ahí sale vacío»; este dice qué pasa en la campaña).
    await expect(aviso(page)).not.toContainText('ahí sale vacío');
    // Va después del aviso de falta de WhatsApp, en el mismo lugar que los demás avisos del speech.
    const despues = await aviso(page).evaluate(
      (el) => Boolean(document.querySelector('[data-speech-falta-whatsapp]')!.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING),
    );
    expect(despues).toBe(true);
  });

  test('sin campos archivados no hay aviso', async ({ page }) => {
    await abrir(page, (api) => versionConSegmento(api, 'Speech v2 limpio', 31, SIN_ARCHIVADO));
    await abrirV2(page, 'Speech v2 limpio');

    await expect(aviso(page)).toBeHidden();
    await expect(aviso(page)).toBeEmpty();
  });

  test('al cambiar a una versión sin archivados el aviso desaparece, y al volver, vuelve', async ({ page }) => {
    await abrir(page, (api) => {
      versionConSegmento(api, 'Speech v2 archivado', 30, CON_ARCHIVADO);
      versionConSegmento(api, 'Speech v2 limpio', 31, SIN_ARCHIVADO);
    });
    await abrirV2(page, 'Speech v2 archivado');
    await expect(aviso(page)).toBeVisible();

    await selectorDeVersion(page).selectOption({ label: 'Speech v2 limpio' });
    await expect(aviso(page)).toBeHidden();

    await selectorDeVersion(page).selectOption({ label: 'Speech v2 archivado' });
    await expect(aviso(page)).toHaveText(AVISO);
  });

  test('con el Speech original, que es v1 y de solo lectura, no hay aviso', async ({ page }) => {
    await abrir(page, () => undefined);

    await expect(aviso(page)).toBeHidden();
  });

  test('si la previsualización falla, no se dice nada de archivados', async ({ page }) => {
    await abrir(page, (api) => versionConSegmento(api, 'Speech v2 archivado', 30, CON_ARCHIVADO));
    await page.route('**/api/mowa-mes/speech/previsualizacion', (route) => json(route, 500, { detail: 'Error interno' }));
    await selectorDeVersion(page).selectOption({ label: 'Speech v2 archivado' });
    await expect(editor(page)).toBeVisible();

    await expect(aviso(page)).toBeHidden();
  });

  test('un adicional se ofrece en el selector de variables con su nombre y «Adicional»; el archivado, no', async ({ page }) => {
    await abrir(page, (api) => versionConSegmento(api, 'Speech v2 limpio', 31, SIN_ARCHIVADO));
    await abrirV2(page, 'Speech v2 limpio');

    await editor(page).getByRole('button', { name: 'Variable', exact: true }).click();

    const opcion = editor(page).getByRole('button', { name: /^Zona/ });
    await expect(opcion.locator('.tag')).toContainText(['texto', 'Adicional']);
    await expect(opcion.locator('.selector-variable__tecnico')).toHaveText('ad_zona');
    await expect(editor(page).getByRole('button', { name: /^Monto en mora/ }).locator('.tag')).toContainText(['número', 'Adicional']);
    await expect(editor(page).getByRole('button', { name: /^Región/ })).toHaveCount(0);
  });

  test('un adicional sin «primeros» no tiene largo máximo (sin_cota_variable); con «primeros» sí', async ({ page }) => {
    await abrir(page, (api) => {
      versionConSegmento(api, 'Speech v2 sin cota', 32, [{ tipo: 'texto', valor: 'Hola ' }, { tipo: 'variable', nombre: 'ad_zona', funciones: [] }]);
      versionConSegmento(api, 'Speech v2 con primeros', 33, SIN_ARCHIVADO);
    });

    await abrirV2(page, 'Speech v2 sin cota');
    await expect(segmentos(page).nth(0)).toContainText('No se puede calcular el largo máximo');
    await expect(segmentos(page).nth(0)).not.toContainText('Cabe');

    await selectorDeVersion(page).selectOption({ label: 'Speech v2 con primeros' });
    await expect(segmentos(page).nth(0)).toContainText('Cabe');
    await expect(segmentos(page).nth(0)).not.toContainText('No se puede calcular');
  });

  for (const tema of TEMAS) {
    test(`axe, tema ${nombreDelTema(tema)}: el aviso de archivado a la vista`, async ({ page }) => {
      await abrir(page, (api) => versionConSegmento(api, 'Speech v2 archivado', 30, CON_ARCHIVADO), { tema });
      await abrirV2(page, 'Speech v2 archivado');
      await expect(aviso(page)).toHaveText(AVISO);

      await capturar(aviso(page), 'editor-aviso-archivado', tema);
      await sinViolaciones(page);
    });
  }

  test('en inglés, el aviso de archivado está traducido', async ({ page }) => {
    await abrir(page, (api) => versionConSegmento(api, 'Speech v2 archivado', 30, CON_ARCHIVADO), { idioma: 'en' });
    await selectorDeVersion(page).selectOption({ label: 'Speech v2 archivado' });

    await expect(aviso(page)).toBeVisible();
    await expect(aviso(page)).toHaveText(
      'The speech uses the archived field “Región”. Sheets loaded after it was archived no longer bring it: in the campaign, the products that need it are left out. To avoid this, reactivate it in Uploads › Additional fields or remove it from the speech.',
    );
    await expect(aviso(page)).not.toContainText('mowaMes.');
  });
});

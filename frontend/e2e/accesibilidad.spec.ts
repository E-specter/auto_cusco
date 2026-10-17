/**
 * Automated accessibility (WCAG 2.1 A and AA rules of axe-core) on every
 * screen and on the states where problems hide: open dialogs, a selection
 * marked as not applicable, the dark theme.
 *
 * axe catches roughly a third of accessibility problems. It does not replace
 * a keyboard pass; it replaces the part that gets forgotten between releases.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page, type Route } from '@playwright/test';

import type { Campos, SeleccionGuardada, Version } from '../src/lib/api';
import { apiVacia, camposSinteticos, montarApi, seleccionGuardada, version } from './api-falsa';
import {
  apiMowaMes,
  campanaSintetica,
  consumoSintetico,
  montarApiMowaMes,
  previsualizacionCampanaSintetica,
  SIN_TARIFA_GUARDADA,
} from './api-falsa-mowa-mes';
import { apiArchivosCarga, crearCompuerta, manejadorArchivosCarga } from './api-falsa-archivos-carga';
import { apiDefiniciones, definicionFalsa, manejadorDefiniciones } from './api-falsa-definiciones';
import { apiTextoEnriquecidoVacia, manejarTextoEnriquecido } from './api-falsa-texto-enriquecido';
import { apiSpeechV2, montarApiSpeechV2, versionV2Sintetica } from './api-falsa-speech-v2';

const REGLAS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

// Contrast measured mid-entrance reads a half-faded paragraph as a failure.
// With reduced motion every screen lands in its final state at once, which is
// also a real mode the product supports.
test.use({ reducedMotion: 'reduce' });

async function sinViolaciones(page: Page): Promise<void> {
  const resultado = await new AxeBuilder({ page }).withTags(REGLAS).analyze();
  const resumen = resultado.violations.map(
    (v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`,
  );
  expect(resumen).toEqual([]);
}

/**
 * The compact selector's own calls for `/mowa-mes/campana`, layered over the
 * module's mock (registered after `montarApiMowaMes`, so it runs first and
 * falls back to it for everything else — see mowa-mes-campana.spec.ts).
 */
async function montarSeleccionCampana(page: Page): Promise<void> {
  const json = (route: Route, estado: number, cuerpo: unknown) =>
    route.fulfill({ status: estado, contentType: 'application/json', body: JSON.stringify(cuerpo) });
  const versiones: Version[] = [version({ fecha_corte: '2026-09-13', vigente: true })];
  const campos: Campos = camposSinteticos();
  const selecciones: SeleccionGuardada[] = [
    seleccionGuardada({ id: 1, nombre: 'Preventiva top 1000', cantidad: 1000 }),
  ];
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

/**
 * A preview with the full sample (20 rows) and 250 exclusions of which the
 * API lists the first 100: both tables paged, the "there are more" notice on.
 */
function previaConTablasPaginadas() {
  return previsualizacionCampanaSintetica(
    { fecha_corte: '2026-09-13', filtros: [], cantidad: 1000, tipo_carga: 'masiva', salida: 'numero_largo', herramientas: { keyword: false, respuesta_automatica: false, blacklist_indecopi: false, speech_optimizado: false }, programacion: 'hora_determinada', envios: ['2026-09-14T09:00:00-05:00'] },
    {
      muestra: Array.from({ length: 20 }, (_, i) => ({
        numero: `900000${String(i + 1).padStart(3, '0')}`,
        mensaje: `Mensaje sintetico ${i + 1}`,
        dni: `00${String(100000 + i)}`,
        supervision: false,
        pagare: `${'0'.repeat(14)}${String(1000 + i)}`,
        segmento: '9_a_30' as const,
        largo: 60,
        advertencias: [],
      })),
      exclusiones: {
        total: 250,
        limite: 100,
        desplazamiento: 0,
        exclusiones: Array.from({ length: 100 }, (_, i) => ({
          pagare: `${'0'.repeat(14)}${String(2000 + i)}`,
          codigo: 'telefono_invalido' as const,
        })),
      },
    },
  );
}

function apiConDatos() {
  const api = apiVacia();
  api.versiones = [version()];
  api.incidencias = [
    { fila: 8, columna: 'pagare', codigo: 'pagare_repetido', severidad: 'error', detalle: 'x', valor_original: null },
  ];
  api.selecciones = [seleccionGuardada()];
  return api;
}

for (const tema of ['light', 'dark'] as const) {
  test.describe(`tema ${tema === 'light' ? 'claro' : 'oscuro'}`, () => {
    test.beforeEach(async ({ page }) => {
      await page.addInitScript((elegido) => {
        localStorage.setItem('app:appearance', JSON.stringify({ theme: elegido, language: 'es' }));
      }, tema);
    });

    test('bienvenida', async ({ page }) => {
      await montarApi(page, apiConDatos());
      await page.goto('/');
      await expect(page.getByRole('link', { name: 'Abrir la consola de cargas' })).toBeVisible();
      await sinViolaciones(page);
    });

    test('consola de cargas', async ({ page }) => {
      await montarApi(page, apiConDatos());
      await page.goto('/cargas');
      await expect(page.getByRole('cell', { name: 'pagare_repetido' })).toBeVisible();
      await sinViolaciones(page);
    });

    test('selección de cartera con métricas, segmentos y productos', async ({ page }) => {
      await montarApi(page, apiConDatos());
      await page.goto('/cartera');
      await page.getByLabel('Selección guardada').selectOption({ label: 'Preventiva mayor saldo' });
      await page.getByRole('button', { name: 'Agregar indicador' }).click();
      await expect(page.locator('[data-solicitados]')).toHaveText('500');
      await expect(page.locator('.productos__tabla')).toBeVisible();
      await sinViolaciones(page);
    });

    test('configuración de MOWA MES, con el aviso de WhatsApp faltante', async ({ page }) => {
      const api = apiMowaMes();
      api.configuracion = { ...api.configuracion, whatsapp_contacto: null };
      await montarApiMowaMes(page, api);
      await page.goto('/mowa-mes/configuracion');
      await expect(page.getByText('Falta WhatsApp').first()).toBeVisible();
      await sinViolaciones(page);
    });

    test('seguimiento de MOWA MES, con el aviso del límite excedido', async ({ page }) => {
      const api = apiMowaMes();
      api.consumo = (mes) => ({
        mes,
        limite: 2_500_000,
        cargados_mes: 2_600_000,
        esta_campana: 0,
        total: 2_600_000,
        disponible: -100_000,
        excedido: true,
      });
      await montarApiMowaMes(page, api);
      await page.goto('/mowa-mes/seguimiento');
      await expect(page.getByText('El mes superó el límite', { exact: false })).toBeVisible();
      await sinViolaciones(page);
    });

    test('campaña de MOWA MES, con la previsualización y el aviso del límite excedido', async ({ page }) => {
      const api = apiMowaMes();
      api.respuestas.previsualizarCampana = [
        {
          estado: 200,
          cuerpo: previsualizacionCampanaSintetica(
            { fecha_corte: '2026-09-13', filtros: [], cantidad: 1000, tipo_carga: 'masiva', salida: 'numero_largo', herramientas: { keyword: false, respuesta_automatica: false, blacklist_indecopi: false, speech_optimizado: false }, programacion: 'hora_determinada', envios: ['2026-09-14T09:00:00-05:00'] },
            {
              limite: { mes: '2026-09', limite: 2_500_000, cargados_mes: 2_490_000, esta_campana: 982, total: 2_490_982, disponible: 9018, excedido: true },
            },
          ),
        },
      ];
      await montarApiMowaMes(page, api);
      await montarSeleccionCampana(page);
      await page.goto('/mowa-mes/campana');
      await page.getByLabel('Selección guardada').selectOption({ label: 'Preventiva top 1000' });
      await expect(page.locator('[data-limite-excedido]')).toBeVisible();
      await sinViolaciones(page);
    });

    test('campaña de MOWA MES, con las tablas paginadas y el aviso de más exclusiones', async ({ page }) => {
      const api = apiMowaMes();
      api.respuestas.previsualizarCampana = [{ estado: 200, cuerpo: previaConTablasPaginadas() }];
      await montarApiMowaMes(page, api);
      await montarSeleccionCampana(page);
      await page.goto('/mowa-mes/campana');
      await page.getByLabel('Selección guardada').selectOption({ label: 'Preventiva top 1000' });
      await expect(page.locator('[data-exclusiones-truncadas]')).toBeVisible();
      await expect(page.getByRole('group', { name: 'Paginación de la muestra' })).toBeVisible();
      await sinViolaciones(page);

      // Second page: the previous button on, the next one disabled.
      await page.getByRole('group', { name: 'Paginación de la muestra' }).getByRole('button', { name: 'Siguientes' }).click();
      await expect(page.locator('[data-muestra-pager] [data-rango]')).toHaveText('11–20 de 20');
      await sinViolaciones(page);
    });

    test('configuración de MOWA MES, con el error de la plantilla y el de la tarifa', async ({ page }) => {
      const api = apiMowaMes();
      await montarApiMowaMes(page, api);
      await page.goto('/mowa-mes/configuracion');
      await expect(page.locator('[data-plantilla-ejemplo]')).toContainText('Nombre del primer archivo:');
      await sinViolaciones(page);

      await page.getByLabel('Nombre de los archivos').fill('carga_{banco}');
      await expect(page.locator('[data-plantilla-error]')).toContainText('No es una variable de la plantilla: {banco}');
      await sinViolaciones(page);

      await page.getByLabel('Nombre de los archivos').fill('carga_{campana}');
      await page.getByLabel('Tarifa por SMS (S/)').fill('abc');
      await page.getByRole('button', { name: 'Guardar plataforma' }).click();
      await expect(page.locator('[data-tarifa-error]')).toContainText('La tarifa debe ser un decimal');
      await sinViolaciones(page);
    });

    test('seguimiento de MOWA MES, con los estados del costo y el aviso de campañas sin tarifa', async ({ page }) => {
      const api = apiMowaMes();
      api.campanas = [
        campanaSintetica({ id: 3, descripcion: 'Campaña sintética 3' }),
        campanaSintetica({ id: 2, descripcion: 'Campaña sintética 2', costo_real: '0.0000', costo_real_estado: 'calculado' }),
        campanaSintetica({ id: 1, descripcion: 'Campaña sintética 1', ...SIN_TARIFA_GUARDADA }),
      ];
      api.consumo = (mes) => consumoSintetico(mes, { campanas_sin_tarifa: 2 });
      await montarApiMowaMes(page, api);
      await page.goto('/mowa-mes/seguimiento');
      await expect(page.locator('[data-costo-mes]')).toContainText('no incluye 2 campañas sin tarifa');
      await expect(page.getByText('Pendiente del reporte').first()).toBeVisible();
      await expect(page.getByText('No disponible').first()).toBeVisible();
      await sinViolaciones(page);

      // The campaign without a rate in the detail too: muted words with the reason.
      await page.getByRole('button', { name: 'Ver la campaña 1' }).click();
      await expect(page.getByRole('heading', { name: 'Campaña 1' })).toBeVisible();
      await sinViolaciones(page);
    });

    test('campaña de MOWA MES, con el nombre estimado, el costo y el error de la plantilla', async ({ page }) => {
      const api = apiMowaMes();
      await montarApiMowaMes(page, api);
      await montarSeleccionCampana(page);
      await page.goto('/mowa-mes/campana');
      await page.getByLabel('Selección guardada').selectOption({ label: 'Preventiva top 1000' });
      await expect(page.locator('[data-nombre-primer-archivo]')).toContainText('[campana]');
      await expect(page.locator('[data-nombre-estimado]')).toBeVisible();
      await expect(page.locator('[data-cifras] .stat', { hasText: 'Costo estimado' })).toContainText('S/ 19.64');
      await sinViolaciones(page);

      await page.getByLabel('Nombre de los archivos').fill('carga_{banco}');
      await expect(page.locator('[data-plantilla-error]')).toContainText('{banco}');
      await sinViolaciones(page);
    });
  });
}

test('cartera: diálogo de guardar con error de nombre', async ({ page }) => {
  const api = apiConDatos();
  api.respuestasCrearSeleccion = [{ estado: 409, cuerpo: { detail: 'repetido' } }];
  await montarApi(page, api);
  await page.goto('/cartera');
  await page.getByRole('button', { name: 'Guardar como nueva' }).click();
  const dialogo = page.getByRole('dialog', { name: 'Guardar la selección' });
  await dialogo.getByLabel('Nombre').fill('Repetido');
  await dialogo.getByRole('button', { name: 'Guardar', exact: true }).click();
  await expect(dialogo.getByText('Ya existe una selección con ese nombre. Elige otro.')).toBeVisible();
  await sinViolaciones(page);
});

test('mowa-mes configuración: diálogo de excepción de calendario con error', async ({ page }) => {
  const api = apiMowaMes();
  await montarApiMowaMes(page, api);
  await page.goto('/mowa-mes/configuracion');
  await page.getByRole('row', { name: /Año Nuevo/ }).getByRole('button', { name: /Retirar el feriado/ }).click();
  const dialogo = page.getByRole('dialog');
  await dialogo.getByRole('button', { name: 'Retirar feriado' }).click();
  await expect(dialogo.getByText('Escribe una descripción.')).toBeVisible();
  await sinViolaciones(page);
});

test('mowa-mes seguimiento: diálogo de reporte ya importado (409) con error', async ({ page }) => {
  const api = apiMowaMes();
  api.respuestas.importarReporte = [
    { estado: 409, cuerpo: { detail: 'El id de MES 990000001 ya estaba importado' } },
  ];
  await montarApiMowaMes(page, api);
  await page.goto('/mowa-mes/seguimiento');
  await page.getByLabel('Archivo del reporte').setInputFiles({
    name: 'REPORTE_SINTETICO.xlsx',
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: Buffer.from('reporte sintetico de prueba'),
  });
  await page.getByRole('button', { name: 'Importar reporte' }).click();
  const dialogo = page.getByRole('dialog', { name: 'Este reporte ya estaba importado' });
  await expect(dialogo.getByText('El id de MES 990000001 ya estaba importado')).toBeVisible();
  await sinViolaciones(page);
});

test('mowa-mes campaña: diálogo del límite mensual con error', async ({ page }) => {
  const api = apiMowaMes();
  api.respuestas.previsualizarCampana = [
    {
      estado: 200,
      cuerpo: previsualizacionCampanaSintetica(
        { fecha_corte: '2026-09-13', filtros: [], cantidad: 1000, tipo_carga: 'masiva', salida: 'numero_largo', herramientas: { keyword: false, respuesta_automatica: false, blacklist_indecopi: false, speech_optimizado: false }, programacion: 'hora_determinada', envios: ['2026-09-14T09:00:00-05:00'] },
        {
          limite: { mes: '2026-09', limite: 2_500_000, cargados_mes: 2_490_000, esta_campana: 982, total: 2_490_982, disponible: 9018, excedido: true },
        },
      ),
    },
  ];
  api.respuestas.crearCampana = [
    {
      estado: 409,
      cuerpo: { detail: 'La campana supera el limite mensual; confirma para continuar', codigo: 'limite_excedido' },
    },
  ];
  await montarApiMowaMes(page, api);
  await montarSeleccionCampana(page);
  await page.goto('/mowa-mes/campana');
  await page.getByLabel('Selección guardada').selectOption({ label: 'Preventiva top 1000' });
  await page.getByRole('button', { name: 'Crear campaña' }).click();
  const dialogo = page.getByRole('dialog', { name: 'La campaña superaría el límite mensual' });
  await expect(dialogo.getByText('La campana supera el limite mensual; confirma para continuar')).toBeVisible();
  await sinViolaciones(page);
});

test('cartera: selección que no aplica, con partes marcadas', async ({ page }) => {
  const api = apiConDatos();
  api.selecciones = [
    seleccionGuardada({
      filtros: ['campo_retirado:igual:x'],
      aplicable: false,
      problemas: [{ parte: 'filtro', expresion: 'campo_retirado:igual:x', detalle: 'El campo no existe' }],
    }),
  ];
  await montarApi(page, api);
  await page.goto('/cartera');
  await page.getByLabel('Selección guardada').selectOption({ index: 1 });
  await expect(page.getByRole('heading', { name: 'La selección tiene partes que no aplican.' })).toBeVisible();
  await sinViolaciones(page);
});

// The column builder, in the states where problems hide: an open row with its editor, the
// variants selector, a dialog, the problems summary and an old version opened to look at.
async function abrirColumnas(page: Page, versiones = 1) {
  const definiciones = apiDefiniciones();
  definiciones.definiciones.push(definicionFalsa({ id: 1, nombre: 'SMS preventivo', versiones }));
  const base = apiVacia();
  base.manejadores = [manejarTextoEnriquecido(apiTextoEnriquecidoVacia()), manejadorDefiniciones(definiciones)];
  await montarApi(page, base);
  await page.goto('/columnas');
  await page.getByLabel('Definición guardada').selectOption('1');
  await expect(page.getByLabel('Nombre de la columna 1')).toBeVisible();
  return definiciones;
}

for (const tema of ['light', 'dark'] as const) {
  test.describe(`columnas de carga, tema ${tema === 'light' ? 'claro' : 'oscuro'}`, () => {
    test.beforeEach(async ({ page }) => {
      await page.addInitScript((elegido) => {
        localStorage.setItem('app:appearance', JSON.stringify({ theme: elegido, language: 'es' }));
      }, tema);
    });

    test('la lista de columnas con su vista previa', async ({ page }) => {
      await abrirColumnas(page);
      await expect(page.locator('.cl-previa')).toBeVisible();
      await sinViolaciones(page);
    });

    test('una fila abierta con el editor de texto', async ({ page }) => {
      await abrirColumnas(page);
      await page.getByRole('button', { name: 'Editar mensaje' }).click();
      await expect(page.locator('#columna-editor')).toBeVisible();
      await sinViolaciones(page);
    });

    test('una columna de variable directa y el formato de una fecha', async ({ page }) => {
      await abrirColumnas(page);
      await page.getByLabel('Tipo de telefono').selectOption('fecha');
      await page.getByRole('button', { name: 'Editar telefono' }).click();
      await expect(page.locator('#columna-editor-directa')).toBeVisible();
      await sinViolaciones(page);
    });

    test('la segmentación y las variantes por segmento', async ({ page }) => {
      await abrirColumnas(page);
      await page.getByText('Segmentación', { exact: true }).click();
      await page.getByLabel('Segmentar las columnas').check();
      await page.getByRole('button', { name: 'Editar mensaje' }).click();
      await page.getByLabel('Variar por segmento').check();
      await expect(page.locator('#columna-editor [data-segmento-botones] button').first()).toBeVisible();
      await sinViolaciones(page);
    });

    test('el diálogo de confirmación al quitar una columna con contenido', async ({ page }) => {
      await abrirColumnas(page);
      await page.getByRole('button', { name: 'Quitar telefono' }).click();
      await expect(page.getByRole('dialog', { name: 'Quitar la columna' })).toBeVisible();
      await sinViolaciones(page);
    });

    test('el resumen de problemas tras un guardado rechazado', async ({ page }) => {
      await abrirColumnas(page);
      await page.getByRole('button', { name: 'Agregar columna' }).click();
      await page.getByRole('button', { name: 'Guardar' }).click();
      await expect(page.getByRole('alert').filter({ hasText: 'impide guardar' })).toBeVisible();
      await sinViolaciones(page);
    });

    test('una versión antigua en solo lectura, con el aviso', async ({ page }) => {
      await abrirColumnas(page, 3);
      await page.getByLabel('Versión', { exact: true }).selectOption('2');
      await expect(page.getByText('Estás viendo la versión 2. La vigente es la 3.')).toBeVisible();
      await sinViolaciones(page);
    });
  });
}

test('columnas de carga a 360 px: la fila abierta y las tablas se alcanzan con teclado', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 640 });
  await abrirColumnas(page);
  await page.getByRole('button', { name: 'Editar mensaje' }).click();
  await expect(page.locator('#columna-editor')).toBeVisible();
  await sinViolaciones(page);
});

// The v2 speech of the MOWA MES configuration: the segment editor, the unsaved draft a v1 becomes,
// the backend's problems per segment and a segment with no maximum length.
async function abrirSpeechV2(
  page: Page,
  ajustar?: (api: ReturnType<typeof apiMowaMes>, v2: ReturnType<typeof apiSpeechV2>) => void,
) {
  const api = apiMowaMes();
  const v2 = apiSpeechV2();
  ajustar?.(api, v2);
  await montarApiMowaMes(page, api);
  await montarApiSpeechV2(page, api, v2, apiTextoEnriquecidoVacia());
  await page.goto('/mowa-mes/configuracion');
  await expect(page.locator('[data-speech-filas] tr[data-segmento="9_a_30"] [data-largo]')).not.toHaveText('—');
  return { api, v2 };
}

for (const tema of ['light', 'dark'] as const) {
  test.describe(`speech v2 de MOWA MES, tema ${tema === 'light' ? 'claro' : 'oscuro'}`, () => {
    test.beforeEach(async ({ page }) => {
      await page.addInitScript((elegido) => {
        localStorage.setItem('app:appearance', JSON.stringify({ theme: elegido, language: 'es' }));
      }, tema);
    });

    test('una versión v2 guardada, con el editor por segmento y sus niveles', async ({ page }) => {
      await abrirSpeechV2(page, (api) => api.versiones.push(versionV2Sintetica(api.versiones[0])));
      await page.locator('#mm-version').selectOption({ label: 'Speech v2' });
      await expect(page.locator('#mm-speech-v2 [data-segmento-botones] button').nth(2)).toContainText('156');
      await sinViolaciones(page);
    });

    test('el borrador que sale de convertir una v1, sin guardar', async ({ page }) => {
      await abrirSpeechV2(page);
      await page.getByRole('button', { name: 'Convertir a v2' }).click();
      await expect(page.getByText(/Borrador a partir de/)).toBeVisible();
      await sinViolaciones(page);
    });

    test('un segmento sin máximo calculable, con su motivo', async ({ page }) => {
      await abrirSpeechV2(page, (api) => {
        const v = versionV2Sintetica(api.versiones[0]);
        v.expresiones.find((e) => e.segmento === '1_a_8')!.expresion = {
          nodos: [{ tipo: 'variable', nombre: 'titular', funciones: [], obligatoria: true }],
        };
        api.versiones.push(v);
      });
      await page.locator('#mm-version').selectOption({ label: 'Speech v2' });
      await expect(page.locator('#mm-speech-v2 [data-segmento-botones] button').nth(1)).toContainText('máximo');
      await sinViolaciones(page);
    });

    test('los problemas del backend por segmento tras un guardado rechazado', async ({ page }) => {
      const { v2 } = await abrirSpeechV2(page);
      v2.respuestasCrear = [
        {
          estado: 400,
          cuerpo: {
            detail: 'No se guarda',
            problemas: [
              { segmento: '9_a_30', campo: 'expresion', detalle: 'x', codigo: 'telefono_invalido', catalogo: 'mowa_mes', ubicacion: null },
            ],
          },
        },
      ];
      await page.getByRole('button', { name: 'Convertir a v2' }).click();
      await expect(page.locator('#mm-speech-v2')).toBeVisible();
      await expect(async () => {
        await page.locator('[data-speech-guardar]').click();
        await expect(page.locator('[data-speech-problemas-lista] li').first()).toBeVisible({ timeout: 1500 });
      }).toPass();
      await sinViolaciones(page);
    });
  });
}

test('speech v2 a 360 px: el editor por segmento se alcanza con teclado', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await abrirSpeechV2(page);
  await page.getByRole('button', { name: 'Convertir a v2' }).click();
  await expect(page.locator('#mm-speech-v2')).toBeVisible();
  await sinViolaciones(page);
});

// A table wider than a phone scrolls sideways; its hidden columns must be
// reachable by keyboard (axe: scrollable-region-focusable, WCAG 2.1.1).
for (const ruta of ['/cargas', '/cartera'] as const) {
  test(`${ruta} a 360 px: las tablas que desbordan se alcanzan con teclado`, async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 640 });
    await montarApi(page, apiConDatos());
    await page.goto(ruta);
    if (ruta === '/cartera') {
      await page.getByLabel('Selección guardada').selectOption({ label: 'Preventiva mayor saldo' });
      await expect(page.locator('.productos__tabla')).toBeVisible();
    } else {
      await expect(page.getByRole('cell', { name: 'pagare_repetido' })).toBeVisible();
    }
    await sinViolaciones(page);
  });
}

// Hover and press are states axe never sees on a still page: the primary
// button must keep AA contrast while the pointer is on it and while pressed.
for (const tema of ['light', 'dark'] as const) {
  test(`botón primario con el mouse encima y presionado, tema ${tema === 'light' ? 'claro' : 'oscuro'}`, async ({ page }) => {
    await page.addInitScript((elegido) => {
      localStorage.setItem('app:appearance', JSON.stringify({ theme: elegido, language: 'es' }));
    }, tema);
    await montarApi(page, apiConDatos());
    await page.goto('/cargas');
    const boton = page.locator('.btn--primary').first();
    await expect(boton).toBeVisible();

    await boton.hover();
    // Colour transitions run regardless of reduced motion; let them settle.
    await page.waitForTimeout(250);
    await sinViolaciones(page);

    await page.mouse.down();
    await page.waitForTimeout(250);
    await sinViolaciones(page);
    await page.mouse.up();
  });
}

// "Generar carga" (/generar-carga): the preview with its notices and problems, the options of a format,
// the notices after a download, a cancel and a refusal, and the table that overflows on a phone.
async function abrirGenerarCarga(
  page: Page,
  ajustar?: (cargas: ReturnType<typeof apiArchivosCarga>) => void,
) {
  const base = apiVacia();
  base.versiones = [version({ fecha_corte: '2026-09-10', vigente: true })];
  base.selecciones = [seleccionGuardada({ id: 1, nombre: 'Preventiva top 500', cantidad: 500 })];
  const definiciones = apiDefiniciones();
  definiciones.definiciones.push(definicionFalsa({ id: 7, nombre: 'SMS preventivo', versiones: 2 }));
  const cargas = apiArchivosCarga();
  ajustar?.(cargas);
  base.manejadores = [manejadorDefiniciones(definiciones), manejadorArchivosCarga(cargas)];
  await montarApi(page, base);
  await page.goto('/generar-carga');
  await page.getByLabel('Selección guardada').selectOption({ label: 'Preventiva top 500' });
  await page.getByLabel('Definición guardada').selectOption({ label: 'SMS preventivo' });
  await expect(page.locator('[data-previa-contenido]')).toBeVisible();
  // The figures dim while the preview recalculates; axe measures contrast only once it is up to date.
  await expect(page.locator('[data-previa]')).toHaveAttribute('data-calculando', 'false');
  return cargas;
}

const conProblemas = (cargas: ReturnType<typeof apiArchivosCarga>) => {
  cargas.disponibles = 300;
  cargas.segmentadas = [7];
  cargas.errores = [{ fila: 2, campo: 'mensaje', detalle: 'La variable titular está vacía' }];
  cargas.exclusiones = Array.from({ length: 6 }, (_, i) => ({
    fila: i + 1,
    pagare: `90000${String(i).padStart(2, '0')}`,
    codigo: 'sin_segmento' as const,
    detalle: 'El producto no cae en ningún segmento',
  }));
};

for (const tema of ['light', 'dark'] as const) {
  test.describe(`generar carga, tema ${tema === 'light' ? 'claro' : 'oscuro'}`, () => {
    test.beforeEach(async ({ page }) => {
      await page.addInitScript((elegido) => {
        localStorage.setItem('app:appearance', JSON.stringify({ theme: elegido, language: 'es' }));
      }, tema);
    });

    test('con la vista previa lista', async ({ page }) => {
      await abrirGenerarCarga(page);
      await sinViolaciones(page);
    });

    test('con avisos, problemas y un grupo abierto', async ({ page }) => {
      await abrirGenerarCarga(page, conProblemas);
      await expect(page.locator('[data-aviso-suficiencia]')).toBeVisible();
      await expect(page.locator('[data-aviso-exclusiones]')).toBeVisible();
      await page.getByRole('button', { name: 'Ver los 6' }).click();
      await expect(page.locator('.gc-problemas__lista li').first()).toBeVisible();
      await sinViolaciones(page);
    });

    test('con las opciones de un formato y «Personalizado» abierto', async ({ page }) => {
      await abrirGenerarCarga(page);
      await page.locator('[data-formatos]').getByRole('button', { name: 'CSV', exact: true }).click();
      await page.getByLabel('Delimitador', { exact: true }).selectOption({ label: 'Personalizado' });
      await expect(page.locator('#gc-op-delimitador-propio')).toBeVisible();
      // The figures dim while the preview recalculates (as in Cartera); contrast is read once it settles.
      await expect(page.locator('[data-previa]')).toHaveAttribute('data-calculando', 'false');
      await sinViolaciones(page);
    });

    test('con la cantidad inválida y el motivo junto al botón', async ({ page }) => {
      await abrirGenerarCarga(page);
      await page.getByLabel('Cantidad a generar').fill('0');
      await expect(page.locator('[data-cantidad-error]')).not.toBeEmpty();
      await sinViolaciones(page);
    });

    test('tras generar, tras cancelar y tras un rechazo', async ({ page }) => {
      const cargas = await abrirGenerarCarga(page);
      await Promise.all([page.waitForEvent('download'), page.locator('[data-generar]').click()]);
      await expect(page.locator('[data-resultado-exito]')).toBeVisible();
      await expect(page.locator('[data-previa]')).toHaveAttribute('data-calculando', 'false');
      await sinViolaciones(page);

      const { compuerta, liberar } = crearCompuerta();
      cargas.compuerta = compuerta;
      await page.locator('[data-generar]').click();
      await page.locator('[data-cancelar]').click();
      await expect(page.locator('[data-resultado-cancelado]')).toBeVisible();
      await sinViolaciones(page);
      liberar();

      cargas.compuerta = null;
      cargas.respuestas.generar = [{ estado: 404, cuerpo: { detail: 'No hay cartera', codigo: 'sin_version_vigente' } }];
      await page.locator('[data-generar]').click();
      await expect(page.locator('[data-resultado-error]')).toBeVisible();
      await sinViolaciones(page);
    });
  });
}

test('generar carga a 360 px: la tabla de la muestra y la de problemas se alcanzan con teclado', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await abrirGenerarCarga(page, conProblemas);
  await sinViolaciones(page);
});

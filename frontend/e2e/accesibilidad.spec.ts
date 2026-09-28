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
import { apiMowaMes, montarApiMowaMes, previsualizacionCampanaSintetica } from './api-falsa-mowa-mes';

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

/**
 * The column builder (/columnas), end to end against intercepted APIs: the saved definitions and
 * the rich-text engine's fakes, chained the way `montarApi` documents.
 *
 * What is worth proving here is what costs a load when it is wrong: saving never modifies a
 * version (so the hint is always there and the name is fixed after creation), an old version
 * cannot be saved over the current one by accident, and what the backend refuses is shown where
 * it belongs while what was typed stays. Every name is synthetic.
 */
import { expect, test, type Page } from '@playwright/test';

import { apiVacia, montarApi, version } from './api-falsa';
import { apiDefiniciones, definicionFalsa, manejadorDefiniciones, type ApiFalsaDefiniciones } from './api-falsa-definiciones';
import {
  apiTextoEnriquecidoVacia,
  manejarTextoEnriquecido,
  previsualizacionSintetica,
  type ApiFalsaTextoEnriquecido,
} from './api-falsa-texto-enriquecido';

const RUTA = '/columnas';

/** Requests to exactly `ruta` (query ignored). */
const pedidosA = (api: ApiFalsaDefiniciones, metodo: string, ruta: string) =>
  api.pedidos.filter((p) => p.metodo === metodo && p.ruta.split('?')[0] === ruta);

/**
 * The engine's fake only previews an expression; this one also reads a definition: each column is its
 * nodes with the example record, and by segment there is one row per range of the catalogue.
 */
function motorConDefiniciones(): ApiFalsaTextoEnriquecido {
  const motor = apiTextoEnriquecidoVacia();
  motor.previsualizacion = (cuerpo, catalogo) => {
    // An expression is the editor's own preview, inside an open row: the engine's fake answers it.
    if (cuerpo.expresion) return previsualizacionSintetica(cuerpo, catalogo, motor.productos);
    const columnas = cuerpo.definicion?.columnas ?? [];
    const ejemplo = catalogo.contexto.ejemplo as Record<string, unknown>;
    // Like the backend: a row names its product (`pagare`, `fecha_corte`) only when the sample is a real
    // product or the first of a selection; the example record answers null and null.
    const esProductoReal = cuerpo.muestra.tipo === 'producto_real' || cuerpo.muestra.tipo === 'primeros_de_seleccion';
    const fila = (numero: number, etiqueta: string | null, segmento: string | null) => ({
      numero,
      etiqueta,
      segmento,
      pagare: esProductoReal ? (cuerpo.muestra.pagare ?? String(99 + numero).padStart(18, '0')) : null,
      fecha_corte: esProductoReal ? (cuerpo.muestra.fecha_corte ?? '2026-10-05') : null,
      excluida: null,
      columnas: columnas.map((c) => {
        const propia = segmento ? c.variantes?.find((v) => v.segmento === segmento) : undefined;
        const nodos = (propia?.expresion ?? c.expresion).nodos.map((n, indice) => {
          if (n.tipo === 'texto') return { indice, tipo: 'texto', texto: n.valor ?? '', vacio: false };
          const crudo = ejemplo[n.nombre ?? ''];
          const vacio = crudo === null || crudo === undefined || crudo === '';
          return { indice, tipo: 'variable', texto: vacio ? '' : String(crudo), vacio };
        });
        const texto = nodos.map((n) => n.texto).join('');
        return {
          nombre: c.nombre,
          tipo: 'texto' as const,
          texto,
          valor: texto,
          largo: texto.length,
          cota: null,
          sin_cota: null,
          usa_variante: Boolean(propia),
          nodos,
          problemas: [],
        };
      }),
    });
    const porSegmento =
      cuerpo.muestra.tipo === 'ejemplos_por_segmento' ||
      (cuerpo.muestra.tipo === 'primeros_de_seleccion' && Boolean(cuerpo.definicion?.segmentacion));
    const filas = porSegmento
      ? catalogo.contexto.segmentos.map((r, i) => fila(i + 1, r.etiqueta, r.clave))
      : [fila(1, null, null)];
    const fecha_envio = esProductoReal ? (cuerpo.muestra.fecha_envio ?? '2026-10-19') : null;
    return { problemas: [], filas, limite_largo: null, umbral_advertencia: null, disponibles: null, fecha_envio };
  };
  return motor;
}

async function abrir(
  page: Page,
  definiciones: ApiFalsaDefiniciones = apiDefiniciones(),
  motor: ApiFalsaTextoEnriquecido = motorConDefiniciones(),
) {
  const base = apiVacia();
  base.manejadores = [manejarTextoEnriquecido(motor), manejadorDefiniciones(definiciones)];
  await montarApi(page, base);
  await page.goto(RUTA);
  await expect(page.getByRole('heading', { name: 'Columnas de carga', level: 1 })).toBeVisible();
  return definiciones;
}

const nombreDeColumna = (page: Page, numero: number) => page.getByLabel(`Nombre de la columna ${numero}`);

test.describe('carga inicial', () => {
  test('sin definiciones guardadas lo dice y deja armar la primera', async ({ page }) => {
    await abrir(page);

    await expect(page.getByText('Todavía no hay definiciones guardadas')).toBeVisible();
    await expect(page.getByText('Todavía sin guardar')).toBeVisible();
    await expect(page.getByLabel('Nombre', { exact: true })).toBeEditable();
    await expect(page.getByText('Al guardar se crea la versión 1.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Guardar' })).toBeDisabled();
  });

  test('con definiciones las lista por nombre, y la primera carga empieza como definición nueva', async ({ page }) => {
    const api = apiDefiniciones();
    api.definiciones.push(definicionFalsa({ id: 2, nombre: 'Zeta' }), definicionFalsa({ id: 1, nombre: 'Alfa' }));
    await abrir(page, api);

    await expect(page.getByText('Todavía no hay definiciones guardadas')).toBeHidden();
    const opciones = page.getByLabel('Definición guardada').locator('option');
    await expect(opciones).toHaveText(['Sin guardar: definición nueva', 'Alfa', 'Zeta']);
  });

  test('sin conexión con la API muestra el aviso en vez de paneles vacíos', async ({ page }) => {
    const api = apiDefiniciones();
    api.sinRed = true;
    await montarApi(page, (() => {
      const base = apiVacia();
      base.manejadores = [manejarTextoEnriquecido(apiTextoEnriquecidoVacia()), manejadorDefiniciones(api)];
      return base;
    })());
    await page.goto(RUTA);

    await expect(page.getByRole('heading', { name: 'Sin conexión con la API' })).toBeVisible();
    await expect(page.locator('[data-contenido]')).toBeHidden();
  });
});

test.describe('una definición nueva', () => {
  test('se arma con columnas, se guarda como versión 1 y queda abierta con su nombre fijo', async ({ page }) => {
    const api = await abrir(page);

    await page.getByLabel('Nombre', { exact: true }).fill('SMS preventivo');
    await nombreDeColumna(page, 1).fill('telefono');
    await page.getByRole('button', { name: 'Agregar columna' }).click();
    await nombreDeColumna(page, 2).fill('mensaje');
    await page.getByRole('button', { name: 'Guardar' }).click();

    await expect(page.getByText('Guardada como versión 1.')).toBeVisible();
    const [creacion] = pedidosA(api, 'POST', '/definiciones-columnas');
    expect(creacion.cuerpo).toMatchObject({ nombre: 'SMS preventivo', proteger_formulas: true });
    const columnas = (creacion.cuerpo as { columnas: Array<{ nombre: string; orden: number }> }).columnas;
    expect(columnas.map((c) => [c.orden, c.nombre])).toEqual([
      [0, 'telefono'],
      [1, 'mensaje'],
    ]);

    // After creating: the name is fixed and the hint says so; the next save is version 2.
    await expect(page.getByLabel('Nombre', { exact: true })).toHaveJSProperty('readOnly', true);
    await expect(page.getByText('El nombre se cambia con Renombrar y no crea una versión.')).toBeVisible();
    await expect(page.locator('[data-renombrar]')).toBeVisible();
    await expect(page.getByText('Al guardar se crea la versión 2; la 1 no cambia.')).toBeVisible();
    await expect(page.getByText('Versión 1', { exact: true }).first()).toBeVisible();
  });

  test('la protección de fórmulas viene marcada y viaja como se deja', async ({ page }) => {
    const api = await abrir(page);
    const proteger = page.getByLabel('Proteger fórmulas en CSV');
    await expect(proteger).toBeChecked();

    await proteger.uncheck();
    await page.getByLabel('Nombre', { exact: true }).fill('Sin protección');
    await nombreDeColumna(page, 1).fill('uno');
    await page.getByRole('button', { name: 'Guardar' }).click();

    await expect(page.getByText('Guardada como versión 1.')).toBeVisible();
    expect(pedidosA(api, 'POST', '/definiciones-columnas')[0].cuerpo).toMatchObject({ proteger_formulas: false });
  });
});

test.describe('las columnas', () => {
  async function conDefinicion(page: Page) {
    const api = apiDefiniciones();
    api.definiciones.push(definicionFalsa({ id: 1, nombre: 'SMS preventivo' }));
    await abrir(page, api);
    await page.getByLabel('Definición guardada').selectOption('1');
    await expect(nombreDeColumna(page, 1)).toHaveValue('telefono');
    return api;
  }

  test('el contenido de cada columna se lee en la lista, sin tocar el motor', async ({ page }) => {
    await conDefinicion(page);

    const filas = page.locator('[data-filas] tr');
    await expect(filas.nth(0)).toContainText('Variable: Teléfono');
    // The backend's result for the example record, once the preview answers; never braces.
    await expect(filas.nth(1)).toContainText('Texto: NOMBRE SINTETICO DE PRUEBA te recuerda tu cuota');
    await expect(filas.nth(1)).not.toContainText(/[{}]/);
  });

  test('subir y bajar cambia el orden, el foco sigue en la columna movida y el orden viaja', async ({ page }) => {
    const api = await conDefinicion(page);

    await page.getByRole('button', { name: 'Bajar telefono' }).click();

    await expect(nombreDeColumna(page, 2)).toHaveValue('telefono');
    await expect(page.getByRole('button', { name: 'Subir telefono' })).toBeFocused();
    await page.getByRole('button', { name: 'Guardar' }).click();
    await expect(page.getByText('Guardada como versión 2.')).toBeVisible();
    const columnas = (pedidosA(api, 'POST', '/definiciones-columnas/1/versiones')[0].cuerpo as {
      columnas: Array<{ nombre: string; orden: number }>;
    }).columnas;
    expect(columnas.map((c) => [c.orden, c.nombre])).toEqual([
      [0, 'mensaje'],
      [1, 'telefono'],
    ]);
  });

  test('duplicar deja una copia con nombre único justo después', async ({ page }) => {
    await conDefinicion(page);

    await page.getByRole('button', { name: 'Duplicar telefono' }).click();

    await expect(nombreDeColumna(page, 2)).toHaveValue('telefono (copia)');
    await expect(nombreDeColumna(page, 1)).toHaveValue('telefono');
  });

  test('quitar una columna con contenido pide confirmación y no quita si se cancela', async ({ page }) => {
    await conDefinicion(page);

    await page.getByRole('button', { name: 'Quitar telefono' }).click();
    const dialogo = page.getByRole('dialog', { name: 'Quitar la columna' });
    await expect(dialogo).toBeVisible();
    await dialogo.getByRole('button', { name: 'Cancelar' }).click();
    await expect(nombreDeColumna(page, 1)).toHaveValue('telefono');

    await page.getByRole('button', { name: 'Quitar telefono' }).click();
    await page.getByRole('dialog', { name: 'Quitar la columna' }).getByRole('button', { name: 'Quitar' }).click();
    await expect(nombreDeColumna(page, 1)).toHaveValue('mensaje');
  });

  test('dos columnas con el mismo nombre se marcan sin esperar a guardar', async ({ page }) => {
    await conDefinicion(page);

    await nombreDeColumna(page, 2).fill('Teléfono');
    await nombreDeColumna(page, 2).blur();

    await expect(nombreDeColumna(page, 1)).toHaveAttribute('aria-invalid', 'true');
    await expect(page.getByText('Otra columna lleva este nombre.').first()).toBeVisible();
  });
});

test.describe('las versiones: nunca se modifica una', () => {
  async function conVersiones(page: Page) {
    const api = apiDefiniciones();
    api.definiciones.push(definicionFalsa({ id: 1, nombre: 'SMS preventivo', versiones: 5, usadasHasta: 1 }));
    await abrir(page, api);
    await page.getByLabel('Definición guardada').selectOption('1');
    await expect(page.getByText('Al guardar se crea la versión 6; la 5 no cambia.')).toBeVisible();
    return api;
  }

  test('la vigente se abre editable y el hint dice qué versión crea, se haya usado o no', async ({ page }) => {
    await conVersiones(page);

    await expect(page.getByLabel('Versión', { exact: true })).toHaveValue('5');
    await expect(nombreDeColumna(page, 1)).toBeEditable();
    await expect(page.getByText('Estás viendo la versión')).toBeHidden();
  });

  test('una versión antigua se abre en solo lectura, sin Guardar ni agregar columnas', async ({ page }) => {
    await conVersiones(page);

    await page.getByLabel('Versión', { exact: true }).selectOption('2');

    await expect(page.getByText('Estás viendo la versión 2. La vigente es la 5.')).toBeVisible();
    await expect(nombreDeColumna(page, 1)).toHaveJSProperty('readOnly', true);
    await expect(page.getByRole('button', { name: 'Guardar' })).toBeDisabled();
    await expect(page.getByRole('button', { name: 'Agregar columna' })).toBeDisabled();
    await expect(page.getByRole('button', { name: /^Subir / }).first()).toBeDisabled();
  });

  test('«Ir a la vigente» vuelve a la 5 editable', async ({ page }) => {
    await conVersiones(page);
    await page.getByLabel('Versión', { exact: true }).selectOption('2');

    await page.getByRole('button', { name: 'Ir a la vigente' }).click();

    await expect(page.getByLabel('Versión', { exact: true })).toHaveValue('5');
    await expect(page.getByText('Estás viendo la versión')).toBeHidden();
    await expect(page.getByRole('button', { name: 'Agregar columna' })).toBeEnabled();
  });

  test('«Usar como base» habilita Guardar con el aviso, y guardar crea la 6 con el contenido de la 2', async ({ page }) => {
    const api = await conVersiones(page);
    await page.getByLabel('Versión', { exact: true }).selectOption('2');
    await expect(nombreDeColumna(page, 1)).toHaveValue('telefono_v2');

    await page.getByRole('button', { name: 'Usar como base' }).click();

    await expect(
      page.getByText(
        'Partes de la versión 2. Al guardar se crea la versión 6 con este contenido y pasa a ser la vigente; la 5 no cambia.',
      ),
    ).toBeVisible();
    await expect(page.getByRole('button', { name: 'Guardar' })).toBeEnabled();

    await page.getByRole('button', { name: 'Guardar' }).click();

    await expect(page.getByText('Guardada como versión 6.')).toBeVisible();
    const [version] = pedidosA(api, 'POST', '/definiciones-columnas/1/versiones');
    expect(version.cuerpo).not.toHaveProperty('nombre');
    expect((version.cuerpo as { columnas: Array<{ nombre: string }> }).columnas[0].nombre).toBe('telefono_v2');
    expect(api.definiciones[0].versiones).toHaveLength(6);
    // The earlier ones are as they were.
    expect(api.definiciones[0].versiones[4].contenido.columnas[0].nombre).toBe('telefono_v5');
  });

  test('descartar lo armado desde una antigua la devuelve a solo lectura', async ({ page }) => {
    await conVersiones(page);
    await page.getByLabel('Versión', { exact: true }).selectOption('2');
    await page.getByRole('button', { name: 'Usar como base' }).click();

    await page.getByRole('button', { name: 'Descartar cambios' }).click();

    await expect(page.getByText('Estás viendo la versión 2. La vigente es la 5.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Guardar' })).toBeDisabled();
  });
});

test.describe('lo que el backend rechaza', () => {
  test('un nombre repetido se dice bajo el nombre y se conserva lo escrito', async ({ page }) => {
    const api = apiDefiniciones();
    api.definiciones.push(definicionFalsa({ id: 1, nombre: 'SMS preventivo' }));
    await abrir(page, api);

    await page.getByLabel('Nombre', { exact: true }).fill('sms PREVENTIVO');
    await nombreDeColumna(page, 1).fill('telefono');
    await page.getByRole('button', { name: 'Guardar' }).click();

    await expect(page.locator('[data-nombre-error]')).toHaveText('Ya hay una definición con ese nombre.');
    await expect(page.getByLabel('Nombre', { exact: true })).toHaveValue('sms PREVENTIVO');
    await expect(nombreDeColumna(page, 1)).toHaveValue('telefono');
    await expect(page.getByRole('alert').filter({ hasText: 'Hay un problema que impide guardar' })).toBeVisible();
  });

  test('un 400 con problemas por columna: resumen con alerta, marca en su campo y lleva al problema', async ({ page }) => {
    const api = await abrir(page);

    await page.getByLabel('Nombre', { exact: true }).fill('SMS');
    await nombreDeColumna(page, 1).fill('ok');
    await page.getByRole('button', { name: 'Agregar columna' }).click();
    await page.getByRole('button', { name: 'Guardar' }).click();

    const resumen = page.getByRole('alert').filter({ hasText: 'impide guardar' });
    await expect(resumen).toBeVisible();
    await expect(resumen).toContainText('Columna 2');
    await expect(nombreDeColumna(page, 2)).toHaveAttribute('aria-invalid', 'true');
    expect(api.definiciones).toHaveLength(0);

    await resumen.getByRole('button', { name: 'Ir al problema' }).click();
    await expect(nombreDeColumna(page, 2)).toBeFocused();
  });

  test('un error de red al guardar no pierde lo escrito', async ({ page }) => {
    const api = apiDefiniciones();
    api.respuestas.crear = [{ estado: 500, cuerpo: { detail: 'Fallo interno' } }];
    await abrir(page, api);

    await page.getByLabel('Nombre', { exact: true }).fill('SMS');
    await nombreDeColumna(page, 1).fill('telefono');
    await page.getByRole('button', { name: 'Guardar' }).click();

    await expect(page.getByRole('dialog', { name: 'Algo salió mal' })).toContainText('Fallo interno');
    await page.getByRole('dialog').getByRole('button', { name: 'Cerrar' }).click();
    await expect(page.getByLabel('Nombre', { exact: true })).toHaveValue('SMS');
    await expect(page.getByRole('button', { name: 'Guardar' })).toBeEnabled();
  });
});

test.describe('cambios sin guardar', () => {
  test('cambiar de definición pide confirmar, y volver conserva lo escrito', async ({ page }) => {
    const api = apiDefiniciones();
    api.definiciones.push(definicionFalsa({ id: 1, nombre: 'Alfa' }), definicionFalsa({ id: 2, nombre: 'Beta' }));
    await abrir(page, api);
    await page.getByLabel('Definición guardada').selectOption('1');
    await nombreDeColumna(page, 1).fill('cambiado');

    await page.getByLabel('Definición guardada').selectOption('2');
    const dialogo = page.getByRole('dialog', { name: 'Hay cambios sin guardar' });
    await expect(dialogo).toBeVisible();
    await dialogo.getByRole('button', { name: 'Volver a la definición' }).click();

    await expect(nombreDeColumna(page, 1)).toHaveValue('cambiado');
    await expect(page.getByLabel('Definición guardada')).toHaveValue('1');

    await page.getByLabel('Definición guardada').selectOption('2');
    await page.getByRole('dialog', { name: 'Hay cambios sin guardar' }).getByRole('button', { name: 'Descartar y seguir' }).click();
    await expect(page.getByLabel('Definición guardada')).toHaveValue('2');
    await expect(nombreDeColumna(page, 1)).toHaveValue('telefono');
  });
});

test.describe('en inglés', () => {
  test('la pantalla no deja claves sin traducir', async ({ page }) => {
    const api = apiDefiniciones();
    api.definiciones.push(definicionFalsa({ id: 1, nombre: 'Alpha', versiones: 2 }));
    await page.addInitScript(() => {
      try {
        localStorage.setItem('app:appearance', JSON.stringify({ language: 'en', theme: 'light' }));
      } catch {
        /* storage blocked: the page keeps its default */
      }
    });
    const base = apiVacia();
    base.manejadores = [manejarTextoEnriquecido(apiTextoEnriquecidoVacia()), manejadorDefiniciones(api)];
    await montarApi(page, base);
    await page.goto(RUTA);

    await expect(page.getByRole('heading', { name: 'Load columns', level: 1 })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Add column' })).toBeVisible();
    await page.getByLabel('Saved definition').selectOption('1');
    await expect(page.getByText('Saving creates version 3; version 2 does not change.')).toBeVisible();
    await expect(page.locator('body')).not.toContainText('columnas.');
  });
});

/** The saved definition with its two columns, opened. */
async function conDefinicion(page: Page) {
  const api = apiDefiniciones();
  api.definiciones.push(definicionFalsa({ id: 1, nombre: 'SMS preventivo' }));
  await abrir(page, api);
  await page.getByLabel('Definición guardada').selectOption('1');
  await expect(nombreDeColumna(page, 1)).toHaveValue('telefono');
  return api;
}

const editorAbierto = (page: Page) => page.locator('#columna-editor');

/** Guardar waits for the open editor to finish validating, so press until it takes. */
async function guardarYEsperar(page: Page, mensaje: string | RegExp) {
  await expect(async () => {
    await page.getByRole('button', { name: 'Guardar' }).click();
    await expect(page.getByText(mensaje)).toBeVisible({ timeout: 1500 });
  }).toPass();
}

test.describe('el contenido de una columna', () => {
  test('abrir la fila monta el editor; cerrarla lo desmonta', async ({ page }) => {
    await conDefinicion(page);
    const abrirFila = page.getByRole('button', { name: 'Editar mensaje' });
    await expect(abrirFila).toHaveAttribute('aria-expanded', 'false');

    await abrirFila.click();

    await expect(editorAbierto(page)).toBeVisible();
    await expect(page.getByRole('button', { name: 'Cerrar mensaje' })).toHaveAttribute('aria-expanded', 'true');
    // One row at a time: opening another closes the first.
    await page.getByRole('button', { name: 'Editar telefono' }).click();
    await expect(page.locator('#columna-editor')).toHaveCount(1);
    await expect(page.getByRole('button', { name: 'Editar mensaje' })).toHaveAttribute('aria-expanded', 'false');

    await page.getByRole('button', { name: 'Cerrar telefono' }).click();
    await expect(editorAbierto(page)).toHaveCount(0);
  });

  test('lo que se escribe cambia el resumen de la fila y viaja al guardar', async ({ page }) => {
    const api = await conDefinicion(page);
    await page.getByRole('button', { name: 'Editar mensaje' }).click();

    const texto = editorAbierto(page).getByRole('textbox').last();
    await texto.fill(' te recuerda tu cuota hoy');

    await expect(page.locator('tr[data-columna]').nth(1)).toContainText('hoy');
    await guardarYEsperar(page, 'Guardada como versión 2.');
    const columnas = (pedidosA(api, 'POST', '/definiciones-columnas/1/versiones')[0].cuerpo as {
      columnas: Array<{ nombre: string; expresion: { nodos: Array<{ tipo: string; valor?: string }> } }>;
    }).columnas;
    const mensaje = columnas.find((c) => c.nombre === 'mensaje')!;
    expect(mensaje.expresion.nodos.at(-1)).toMatchObject({ tipo: 'texto', valor: ' te recuerda tu cuota hoy' });
  });

  test('una columna de una sola variable se abre como variable directa, con su selector', async ({ page }) => {
    await conDefinicion(page);

    await page.getByRole('button', { name: 'Editar telefono' }).click();

    await expect(page.getByRole('radio', { name: 'Variable directa' })).toBeChecked();
    await expect(editorAbierto(page).locator('#columna-editor-directa')).toBeVisible();
  });

  test('pasar un texto a variable directa pide confirmar porque se pierde el texto', async ({ page }) => {
    await conDefinicion(page);
    await page.getByRole('button', { name: 'Editar mensaje' }).click();
    await expect(page.getByRole('radio', { name: 'Texto compuesto' })).toBeChecked();

    await page.getByRole('radio', { name: 'Variable directa' }).check();
    const dialogo = page.getByRole('dialog', { name: 'Se pierde el texto' });
    await expect(dialogo).toBeVisible();
    await dialogo.getByRole('button', { name: 'Cancelar' }).click();
    await expect(page.getByRole('radio', { name: 'Texto compuesto' })).toBeChecked();

    await page.getByRole('radio', { name: 'Variable directa' }).check();
    await page.getByRole('dialog', { name: 'Se pierde el texto' }).getByRole('button', { name: 'Usar variable directa' }).click();

    await expect(page.locator('tr[data-columna]').nth(1)).toContainText('Variable: Titular');
    await expect(page.getByRole('radio', { name: 'Variable directa' })).toBeChecked();
  });
});

test.describe('el formato', () => {
  test('una fecha elige su patrón de la lista y viaja con marcas, sin strftime', async ({ page }) => {
    const api = await conDefinicion(page);
    await page.getByLabel('Tipo de telefono').selectOption('fecha');
    await page.getByRole('button', { name: 'Editar telefono' }).click();

    await page.locator('#cl-patron-fecha').selectOption('dd/mm/aaaa');

    await expect(page.locator('tr[data-columna]').first()).toContainText('Fecha dd/mm/aaaa');
    await guardarYEsperar(page, 'Guardada como versión 2.');
    const columnas = (pedidosA(api, 'POST', '/definiciones-columnas/1/versiones')[0].cuerpo as {
      columnas: Array<{ nombre: string; tipo: string; formato_fecha: string | null }>;
    }).columnas;
    expect(columnas.find((c) => c.nombre === 'telefono')).toMatchObject({ tipo: 'fecha', formato_fecha: 'dd/mm/aaaa' });
  });

  test('un importe muestra su ejemplo en vivo y manda el formato', async ({ page }) => {
    const api = await conDefinicion(page);
    await page.getByLabel('Tipo de telefono').selectOption('financiero');
    await page.getByRole('button', { name: 'Editar telefono' }).click();
    await expect(page.getByText('Ejemplo: 1,234.50')).toBeVisible();

    await page.getByLabel('Decimales').fill('0');
    await page.getByLabel('Separador de miles').fill('.');

    await expect(page.getByText('Ejemplo: 1.235')).toBeVisible();
    await guardarYEsperar(page, 'Guardada como versión 2.');
    const columnas = (pedidosA(api, 'POST', '/definiciones-columnas/1/versiones')[0].cuerpo as {
      columnas: Array<{ nombre: string; formato_financiero: { decimales: number; separador_miles: string } }>;
    }).columnas;
    expect(columnas.find((c) => c.nombre === 'telefono')?.formato_financiero).toMatchObject({
      decimales: 0,
      separador_miles: '.',
    });
  });

  test('un tipo sin formato lo dice', async ({ page }) => {
    await conDefinicion(page);

    await page.getByRole('button', { name: 'Editar telefono' }).click();

    await expect(page.getByText('Este tipo no lleva formato.')).toBeVisible();
  });
});

test.describe('segmentación y variantes', () => {
  async function conSegmentacion(page: Page) {
    const api = await conDefinicion(page);
    await page.getByText('Segmentación', { exact: true }).click();
    await page.getByLabel('Segmentar las columnas').check();
    return api;
  }

  test('activarla muestra la tabla de rangos de solo lectura y la política', async ({ page }) => {
    await conSegmentacion(page);

    await expect(page.getByLabel('Criterio')).toHaveValue('calculado');
    await expect(page.locator('[data-rangos] tr').first()).toBeVisible();
    await expect(page.getByLabel('Excluir el producto e informar el motivo')).toBeChecked();
  });

  test('sin segmentación no se puede variar por segmento y el motivo está a la vista', async ({ page }) => {
    await conDefinicion(page);

    await page.getByRole('button', { name: 'Editar mensaje' }).click();

    await expect(page.getByLabel('Variar por segmento')).toBeDisabled();
    await expect(page.getByText('Activa la segmentación de la definición para variar el contenido por segmento.')).toBeVisible();
  });

  test('una variante propia por segmento viaja con la segmentación', async ({ page }) => {
    const api = await conSegmentacion(page);
    await page.getByRole('button', { name: 'Editar mensaje' }).click();

    await page.getByLabel('Variar por segmento').check();
    const segmentos = editorAbierto(page).locator('[data-segmento-botones] button');
    await expect(segmentos.nth(1)).toBeVisible();
    await segmentos.nth(1).click();
    await editorAbierto(page).getByRole('textbox').last().fill('Solo para este segmento');

    await expect(page.locator('tr[data-columna]').nth(1)).toContainText('1 variante');
    await guardarYEsperar(page, 'Guardada como versión 2.');
    const cuerpo = pedidosA(api, 'POST', '/definiciones-columnas/1/versiones')[0].cuerpo as {
      segmentacion: { criterio: { tipo: string }; politica: string } | null;
      columnas: Array<{ nombre: string; variantes: Array<{ segmento: string }> }>;
    };
    expect(cuerpo.segmentacion).toMatchObject({ criterio: { tipo: 'calculado' }, politica: 'excluir' });
    expect(cuerpo.columnas.find((c) => c.nombre === 'mensaje')?.variantes).toHaveLength(1);
  });

  test('desactivar la segmentación con variantes pide confirmar y las quita', async ({ page }) => {
    await conSegmentacion(page);
    await page.getByRole('button', { name: 'Editar mensaje' }).click();
    await page.getByLabel('Variar por segmento').check();
    await editorAbierto(page).locator('[data-segmento-botones] button').nth(1).click();
    await editorAbierto(page).getByRole('textbox').last().fill('Propio');
    await expect(page.locator('tr[data-columna]').nth(1)).toContainText('1 variante');

    await page.getByLabel('Segmentar las columnas').uncheck();
    const dialogo = page.getByRole('dialog', { name: 'Cambiar la segmentación' });
    await expect(dialogo).toBeVisible();
    await dialogo.getByRole('button', { name: 'Quitar variantes y cambiar' }).click();

    await expect(page.locator('tr[data-columna]').nth(1)).not.toContainText('variante');
    await expect(page.getByLabel('Segmentar las columnas')).not.toBeChecked();
  });
});

test.describe('la vista previa de la definición', () => {
  test('muestra una fila con las columnas y su resultado, y la marca de vacío', async ({ page }) => {
    await conDefinicion(page);

    const tabla = page.locator('.cl-previa');
    await expect(tabla.getByRole('columnheader', { name: 'mensaje' })).toBeVisible();
    await expect(tabla).toContainText('900000123');
    await expect(tabla).toContainText('te recuerda tu cuota');
  });

  test('con segmentación hay una fila por segmento, rotulada con su etiqueta', async ({ page }) => {
    await conDefinicion(page);
    await page.getByText('Segmentación', { exact: true }).click();
    await page.getByLabel('Segmentar las columnas').check();

    const rangos = await page.locator('[data-rangos] tr').count();
    expect(rangos).toBeGreaterThan(1);
    await expect(page.locator('.cl-previa tbody tr')).toHaveCount(rangos);
    await expect(page.locator('.cl-previa tbody tr').first().getByRole('rowheader')).toHaveText(/\S+/);
  });

  test('una definición sin contenido lo dice en vez de mostrar una tabla vacía', async ({ page }) => {
    await abrir(page);

    await expect(page.getByText('Agrega una columna con contenido para ver cómo queda.')).toBeVisible();
    await expect(page.locator('.cl-previa')).toBeHidden();
  });
});

test.describe('una versión antigua con una fila abierta', () => {
  test('el editor se abre sin poder editarse hasta «Usar como base»', async ({ page }) => {
    const api = apiDefiniciones();
    api.definiciones.push(definicionFalsa({ id: 1, nombre: 'SMS', versiones: 3 }));
    await abrir(page, api);
    await page.getByLabel('Definición guardada').selectOption('1');
    await page.getByLabel('Versión', { exact: true }).selectOption('2');
    await page.getByRole('button', { name: 'Editar mensaje_v2' }).click();

    await expect(editorAbierto(page).getByRole('textbox').last()).not.toBeEditable();

    await page.getByRole('button', { name: 'Usar como base' }).click();

    await expect(editorAbierto(page).getByRole('textbox').last()).toBeEditable();
  });
});

test.describe('correcciones de la revisión de experiencia', () => {
  test('la tabla y las acciones usan el ancho del panel: Acciones queda a la vista en una línea', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await conDefinicion(page);

    const ancho = await page.locator('.cl-tabla').evaluate((tabla) => tabla.getBoundingClientRect().width);
    expect(ancho).toBeGreaterThan(900);
    const fila = page.locator('tr[data-columna]').first();
    const acciones = fila.locator('.cl-acciones');
    await expect(acciones.getByRole('button')).toHaveCount(5);
    const cajas = await acciones.getByRole('button').evaluateAll((botones) =>
      botones.map((b) => b.getBoundingClientRect().top),
    );
    expect(new Set(cajas.map((y) => Math.round(y))).size).toBe(1);
  });

  test('«Variar por segmento» se habilita al segmentar con la fila ya abierta', async ({ page }) => {
    await conDefinicion(page);
    await page.getByRole('button', { name: 'Editar mensaje' }).click();
    await expect(page.getByLabel('Variar por segmento')).toBeDisabled();

    await page.getByText('Segmentación', { exact: true }).click();
    await page.getByLabel('Segmentar las columnas').check();

    await expect(page.getByLabel('Variar por segmento')).toBeEnabled();
    await expect(page.getByText('Activa la segmentación de la definición para variar el contenido por segmento.')).toBeHidden();
  });

  test('el editor de la fila no muestra su propio control de muestra: la página la fija', async ({ page }) => {
    await conDefinicion(page);
    await page.getByText('Segmentación', { exact: true }).click();
    await page.getByLabel('Segmentar las columnas').check();
    await page.getByRole('button', { name: 'Editar mensaje' }).click();
    await expect(editorAbierto(page)).toBeVisible();
    await expect(editorAbierto(page).locator('[data-control-muestra]')).toBeHidden();

    await page.getByLabel('Variar por segmento').check();

    await expect(editorAbierto(page).locator('[data-segmento-botones] button').first()).toBeVisible();
    await expect(editorAbierto(page).locator('[data-control-muestra]')).toBeHidden();
  });

  test('en solo lectura no hay hint de guardado; con «Usar como base» va el corto', async ({ page }) => {
    const api = apiDefiniciones();
    api.definiciones.push(definicionFalsa({ id: 1, nombre: 'SMS', versiones: 3 }));
    await abrir(page, api);
    await page.getByLabel('Definición guardada').selectOption('1');
    await expect(page.getByText('Al guardar se crea la versión 4; la 3 no cambia.')).toBeVisible();

    await page.getByLabel('Versión', { exact: true }).selectOption('1');
    await expect(page.locator('[data-guardar-hint]')).toBeEmpty();

    await page.getByRole('button', { name: 'Usar como base' }).click();
    await expect(page.locator('[data-guardar-hint]')).toHaveText('Se creará la versión 4 con este contenido.');
  });

  test('los rangos son una tabla de solo lectura con etiqueta, desde y hasta', async ({ page }) => {
    await conDefinicion(page);
    await page.getByText('Segmentación', { exact: true }).click();
    await page.getByLabel('Segmentar las columnas').check();

    const tabla = page.locator('.cl-rangos-tabla');
    await expect(tabla.getByRole('columnheader')).toHaveText(['Segmento', 'Desde (días)', 'Hasta (días)']);
    const primera = tabla.locator('tbody tr').first();
    await expect(primera.getByRole('rowheader')).toHaveText(/\S+/);
    await expect(primera.locator('td')).toHaveCount(2);
  });

  test('la vista previa por segmento rotula su primera columna «Segmento»', async ({ page }) => {
    await conDefinicion(page);
    await expect(page.locator('.cl-previa thead th').first()).toHaveText('Fila');

    await page.getByText('Segmentación', { exact: true }).click();
    await page.getByLabel('Segmentar las columnas').check();

    await expect(page.locator('.cl-previa thead th').first()).toHaveText('Segmento');
  });

  test('Guardar no es un botón de envío', async ({ page }) => {
    await conDefinicion(page);

    await expect(page.getByRole('button', { name: 'Guardar' })).toHaveAttribute('type', 'button');
  });

  test('la muestra de la vista previa es un control segmentado con el estado a la vista', async ({ page }) => {
    await conDefinicion(page);
    const ejemplos = page.getByRole('button', { name: 'Ejemplos por segmento' });
    const real = page.getByRole('button', { name: 'Cartera real' });
    await expect(ejemplos).toHaveAttribute('aria-pressed', 'true');

    await real.click();

    await expect(real).toHaveAttribute('aria-pressed', 'true');
    await expect(ejemplos).toHaveAttribute('aria-pressed', 'false');
  });

  test('el control de muestra no se estira a todo el panel y a 360 px cabe en la pantalla', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await conDefinicion(page);
    const control = page.locator('[aria-labelledby="cl-muestra-etiqueta"]');
    const panel = page.locator('.cl-previa').locator('xpath=ancestor::*[contains(@class,"panel__body")]');
    const anchoControl = await control.evaluate((e) => e.getBoundingClientRect().width);
    const anchoPanel = await panel.evaluate((e) => e.getBoundingClientRect().width);
    expect(anchoControl).toBeLessThan(anchoPanel / 2);

    await page.setViewportSize({ width: 360, height: 800 });
    const borde = await control.evaluate((e) => e.getBoundingClientRect().right);
    expect(borde).toBeLessThanOrEqual(360);
    await expect(page.getByRole('button', { name: 'Cartera real' })).toBeVisible();
  });
});

test('la vista previa dice cuándo está al día: ocupada desde el cambio hasta que llega su respuesta', async ({ page }) => {
  await conDefinicion(page);
  const previa = page.locator('[data-previa]');
  await expect(previa).toHaveAttribute('data-calculando', 'false');
  await expect(previa).toHaveAttribute('aria-busy', 'false');

  await nombreDeColumna(page, 1).fill('telefono_nuevo');

  // Busy from the change (before the request even leaves), so a test can wait for it instead of a fixed time.
  await expect(previa).toHaveAttribute('data-calculando', 'true');
  await expect(previa).toHaveAttribute('aria-busy', 'true');
  await expect(previa).toHaveAttribute('data-calculando', 'false');
  await expect(previa).toHaveAttribute('aria-busy', 'false');
});

test.describe('la muestra del editor es el producto del segmento elegido', () => {
  /** Real portfolio, a segmentation, and the open row varying by segment: the editor's own preview is the call to watch. */
  async function abrirConCarteraReal(page: Page, ajustar?: (motor: ApiFalsaTextoEnriquecido) => void) {
    const definiciones = apiDefiniciones();
    definiciones.definiciones.push(definicionFalsa({ id: 1, nombre: 'SMS preventivo' }));
    const motor = motorConDefiniciones();
    // Every product the editor may ask for by pagaré (rows 1 to 3 of the preview), so none is a 404.
    for (const numero of [1, 2, 3]) motor.productos[String(99 + numero).padStart(18, '0')] = { telefono: '900000001', titular: 'ZZPRUEBA UNO' };
    ajustar?.(motor);
    const base = apiVacia();
    base.versiones = [version({ fecha_corte: '2026-09-10', vigente: true })];
    base.manejadores = [manejarTextoEnriquecido(motor), manejadorDefiniciones(definiciones)];
    await montarApi(page, base);
    await page.goto(RUTA);
    await page.getByLabel('Definición guardada').selectOption('1');
    await expect(nombreDeColumna(page, 1)).toHaveValue('telefono');
    await page.getByText('Segmentación', { exact: true }).click();
    await page.getByLabel('Segmentar las columnas').check();
    await page.getByRole('button', { name: 'Cartera real' }).click();
    await expect(page.locator('.cl-previa tbody tr')).not.toHaveCount(0);
    await page.getByRole('button', { name: 'Editar mensaje' }).click();
    await page.getByLabel('Variar por segmento').check();
    await expect(editorAbierto(page).locator('[data-segmento-botones] button').first()).toBeVisible();
    return motor;
  }

  /** The note the editor shows under its own preview, and the region that says it to a screen reader. */
  const notaDeMuestra = (page: Page) => editorAbierto(page).locator('[data-resultado] + [data-nota-muestra]');
  const anuncioDeNota = (page: Page) => editorAbierto(page).locator('[data-nota-anuncio]');

  /** The samples the open editor asked for, in order. */
  const muestrasDelEditor = (motor: ApiFalsaTextoEnriquecido) =>
    motor.pedidos
      .filter((p) => p.ruta.startsWith('/texto-enriquecido/previsualizacion'))
      .map((p) => p.cuerpo as { expresion?: unknown; muestra: { tipo: string; pagare?: string | null; fecha_corte?: string | null; cantidad?: number } })
      .filter((c) => c.expresion)
      .map((c) => c.muestra);

  const segmento = (page: Page, etiqueta: string) =>
    editorAbierto(page).locator('[data-segmento-botones] button').filter({ hasText: etiqueta }).first();

  test('al elegir un segmento, el editor previsualiza con el pagaré y la fecha de la primera fila de ese segmento', async ({ page }) => {
    const motor = await abrirConCarteraReal(page);

    await segmento(page, '1 a 8').click();

    await expect
      .poll(() => muestrasDelEditor(motor).at(-1))
      .toMatchObject({ tipo: 'producto_real', pagare: '000000000000000101', fecha_corte: '2026-09-10' });
    await expect(notaDeMuestra(page)).toBeHidden();

    await segmento(page, '9 a 30').click();

    await expect
      .poll(() => muestrasDelEditor(motor).at(-1))
      .toMatchObject({ tipo: 'producto_real', pagare: '000000000000000102' });
  });

  test('al variar abre el primer segmento con su producto; con el contenido por defecto no hay segmento y usa el primero de la selección', async ({ page }) => {
    const motor = await abrirConCarteraReal(page);

    await expect
      .poll(() => muestrasDelEditor(motor).at(-1))
      .toMatchObject({ tipo: 'producto_real', pagare: '000000000000000100', fecha_corte: '2026-09-10' });

    await editorAbierto(page).locator('[data-segmento-botones] button[data-segmento=""]').click();

    await expect
      .poll(() => muestrasDelEditor(motor).at(-1))
      .toMatchObject({ tipo: 'primeros_de_seleccion', fecha_corte: '2026-09-10', cantidad: 1 });
    await expect(notaDeMuestra(page)).toBeHidden();
  });

  /** A preview in which no product falls in the segment «9 a 30». */
  const sinProductoEn9a30 = (m: ApiFalsaTextoEnriquecido) => {
    const original = m.previsualizacion;
    m.previsualizacion = (cuerpo, catalogo) => {
      const respuesta = original(cuerpo, catalogo);
      return 'filas' in respuesta && cuerpo.definicion
        ? { ...respuesta, filas: respuesta.filas.filter((f) => f.segmento !== '9_a_30') }
        : respuesta;
    };
  };

  test('si ningún producto de la muestra cae en el segmento, usa el primero y lo dice en una línea', async ({ page }) => {
    const motor = await abrirConCarteraReal(page, sinProductoEn9a30);

    await segmento(page, '9 a 30').click();

    await expect(notaDeMuestra(page)).toBeVisible();
    await expect(notaDeMuestra(page)).toHaveText(
      'Ningún producto de la muestra cae en «9 a 30»: la vista previa usa el primer producto de la selección.',
    );
    // Said once to a screen reader, from the editor's own region.
    await expect(anuncioDeNota(page)).toHaveText(
      'Ningún producto de la muestra cae en «9 a 30»: la vista previa usa el primer producto de la selección.',
    );
    await expect
      .poll(() => muestrasDelEditor(motor).at(-1))
      .toMatchObject({ tipo: 'primeros_de_seleccion', cantidad: 1 });

    await segmento(page, '1 a 8').click();

    await expect(notaDeMuestra(page)).toBeHidden();
    await expect
      .poll(() => muestrasDelEditor(motor).at(-1))
      .toMatchObject({ tipo: 'producto_real', pagare: '000000000000000101' });
  });

  test('la nota se vuelve a decir en el idioma nuevo, y queda donde la vista previa del editor', async ({ page }) => {
    await abrirConCarteraReal(page, sinProductoEn9a30);
    await segmento(page, '9 a 30').click();
    await expect(notaDeMuestra(page)).toBeVisible();

    await page.locator('[data-lang="en"]').click();

    await expect(notaDeMuestra(page)).toHaveText(
      'No product in the sample falls in “9 a 30”: the preview uses the first product of the selection.',
    );
    await expect(anuncioDeNota(page)).toHaveText(
      'No product in the sample falls in “9 a 30”: the preview uses the first product of the selection.',
    );
  });

  test('con ejemplos no hay producto: el editor usa el registro de ejemplo, haya o no segmento', async ({ page }) => {
    const definiciones = apiDefiniciones();
    definiciones.definiciones.push(definicionFalsa({ id: 1, nombre: 'SMS preventivo' }));
    const motor = motorConDefiniciones();
    const base = apiVacia();
    base.manejadores = [manejarTextoEnriquecido(motor), manejadorDefiniciones(definiciones)];
    await montarApi(page, base);
    await page.goto(RUTA);
    await page.getByLabel('Definición guardada').selectOption('1');
    await page.getByText('Segmentación', { exact: true }).click();
    await page.getByLabel('Segmentar las columnas').check();
    await page.getByRole('button', { name: 'Editar mensaje' }).click();
    await page.getByLabel('Variar por segmento').check();

    await segmento(page, '1 a 8').click();

    await expect.poll(() => muestrasDelEditor(motor).at(-1)).toMatchObject({ tipo: 'ejemplo' });
    await expect(notaDeMuestra(page)).toBeHidden();
  });

  test('con cartera real, bajo el título de la vista previa dice a qué día están calculados los segmentos', async ({ page }) => {
    await abrirConCarteraReal(page);

    const aviso = page.locator('[data-previa-envio]');
    await expect(aviso).toBeVisible();
    await expect(aviso).toHaveText(/^Segmentos calculados con los días de atraso a hoy, .+ \d{4}, como si se enviara hoy\.$/);
    // Under the title, before the sample control.
    const ordenCorrecto = await page.evaluate(() => {
      const titulo = document.querySelector('#cl-previa-title')!;
      const hint = document.querySelector('[data-previa-envio]')!;
      const muestra = document.querySelector('#cl-muestra-etiqueta')!;
      return (
        Boolean(titulo.compareDocumentPosition(hint) & Node.DOCUMENT_POSITION_FOLLOWING) &&
        Boolean(hint.compareDocumentPosition(muestra) & Node.DOCUMENT_POSITION_FOLLOWING)
      );
    });
    expect(ordenCorrecto).toBe(true);
  });

  test('con ejemplos no hay producto ni fecha: no hay aviso, y al volver de la cartera real se va', async ({ page }) => {
    await abrirConCarteraReal(page);
    await expect(page.locator('[data-previa-envio]')).toBeVisible();

    await page.getByRole('button', { name: 'Ejemplos por segmento' }).click();

    await expect(page.locator('[data-previa-envio]')).toBeHidden();
  });

  test('sin tocar la muestra (ejemplos) el aviso nunca sale', async ({ page }) => {
    await conDefinicion(page);
    await expect(page.locator('.cl-previa tbody tr').first()).toBeVisible();

    await expect(page.locator('[data-previa-envio]')).toBeHidden();
  });

  test('en inglés el aviso sale en inglés', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    const definiciones = apiDefiniciones();
    definiciones.definiciones.push(definicionFalsa({ id: 1, nombre: 'SMS preventivo' }));
    const base = apiVacia();
    base.versiones = [version({ fecha_corte: '2026-09-10', vigente: true })];
    base.manejadores = [manejarTextoEnriquecido(motorConDefiniciones()), manejadorDefiniciones(definiciones)];
    await montarApi(page, base);
    await page.goto(RUTA);
    await page.locator('[data-definiciones]').selectOption('1');
    await page.locator('[data-muestra="real"]').click();

    await expect(page.locator('[data-previa-envio]')).toHaveText(
      /^Segments worked out with the days past due as of today, .+, as if it were sent today\.$/,
    );
  });
});

test.describe('renombrar una definición guardada (RF-56)', () => {
  const dialogo = (page: Page) => page.getByRole('dialog', { name: /^Renombrar / });
  const campoDelDialogo = (page: Page) => page.getByLabel('Nombre nuevo');
  const botonDelDialogo = (page: Page) => dialogo(page).getByRole('button', { name: 'Renombrar', exact: true });
  const botonDeLaPantalla = (page: Page) => page.locator('[data-renombrar]');

  /** Two saved definitions (so a name can be taken) and the first one open. */
  async function conDosDefiniciones(page: Page, versiones = 1) {
    const api = apiDefiniciones();
    api.definiciones.push(
      definicionFalsa({ id: 1, nombre: 'SMS preventivo', versiones }),
      definicionFalsa({ id: 2, nombre: 'WhatsApp cobranza' }),
    );
    await abrir(page, api);
    await page.getByLabel('Definición guardada').selectOption('1');
    await expect(nombreDeColumna(page, 1)).toHaveValue(versiones > 1 ? 'telefono_v3' : 'telefono');
    return api;
  }

  const patches = (api: ApiFalsaDefiniciones) => pedidosA(api, 'PATCH', '/definiciones-columnas/1');

  test('una definición sin guardar no tiene «Renombrar»: su nombre se escribe en el campo', async ({ page }) => {
    await abrir(page);

    await expect(botonDeLaPantalla(page)).toBeHidden();
    await expect(page.getByLabel('Nombre', { exact: true })).toBeEditable();
  });

  test('una guardada: el campo es de solo lectura, el hint manda a «Renombrar» y el botón está junto al campo', async ({ page }) => {
    await conDosDefiniciones(page);

    await expect(page.getByLabel('Nombre', { exact: true })).not.toBeEditable();
    await expect(page.locator('[data-nombre-hint]')).toHaveText('El nombre se cambia con Renombrar y no crea una versión.');
    await expect(botonDeLaPantalla(page)).toBeVisible();
    await expect(botonDeLaPantalla(page)).toHaveAccessibleDescription(/El nombre se cambia con Renombrar/);
  });

  test('el diálogo trae el nombre actual seleccionado, el hint, el tope del catálogo y «Renombrar» inactivo', async ({ page }) => {
    await conDosDefiniciones(page);

    await botonDeLaPantalla(page).click();

    await expect(dialogo(page)).toBeVisible();
    await expect(dialogo(page).getByRole('heading')).toHaveText('Renombrar “SMS preventivo”');
    await expect(campoDelDialogo(page)).toHaveValue('SMS preventivo');
    await expect(campoDelDialogo(page)).toBeFocused();
    expect(await campoDelDialogo(page).evaluate((e: HTMLInputElement) => [e.selectionStart, e.selectionEnd])).toEqual([0, 14]);
    await expect(campoDelDialogo(page)).toHaveAttribute('maxlength', '120');
    await expect(dialogo(page).getByText('Las versiones y las cargas ya generadas no cambian.')).toBeVisible();
    await expect(botonDelDialogo(page)).toBeDisabled();
  });

  test('renombrar cambia el nombre en el campo y en la lista, sin crear una versión, y dice qué pasó', async ({ page }) => {
    const api = await conDosDefiniciones(page);
    await botonDeLaPantalla(page).click();

    await campoDelDialogo(page).fill('SMS preventivo B');
    await expect(botonDelDialogo(page)).toBeEnabled();
    await botonDelDialogo(page).click();

    await expect(dialogo(page)).toBeHidden();
    await expect(page.getByLabel('Nombre', { exact: true })).toHaveValue('SMS preventivo B');
    await expect(page.getByLabel('Definición guardada').getByRole('option', { name: 'SMS preventivo B' })).toBeAttached();
    await expect(page.getByLabel('Definición guardada').getByRole('option', { name: 'SMS preventivo', exact: true })).toHaveCount(0);
    await expect(page.locator('[data-estado]')).toHaveText('Renombrada a “SMS preventivo B”.');
    await expect(botonDeLaPantalla(page)).toBeFocused();
    expect(patches(api)).toHaveLength(1);
    expect(patches(api)[0].cuerpo).toEqual({ nombre: 'SMS preventivo B' });
    // No version: nothing but the PATCH was written, and the definition keeps its one version.
    expect(api.pedidos.filter((p) => p.metodo !== 'GET' && p.metodo !== 'PATCH')).toEqual([]);
    expect(api.definiciones[0].versiones).toHaveLength(1);
  });

  test('sin cambios «Renombrar» queda inactivo, también con espacios en los extremos; cambiar solo las mayúsculas sí cuenta', async ({ page }) => {
    const api = await conDosDefiniciones(page);
    await botonDeLaPantalla(page).click();

    await campoDelDialogo(page).fill('  SMS preventivo  ');
    await expect(botonDelDialogo(page)).toBeDisabled();

    await campoDelDialogo(page).fill('Sms preventivo');
    await expect(botonDelDialogo(page)).toBeEnabled();
    await botonDelDialogo(page).click();

    await expect(page.getByLabel('Nombre', { exact: true })).toHaveValue('Sms preventivo');
    expect(patches(api)[0].cuerpo).toEqual({ nombre: 'Sms preventivo' });
  });

  test('un nombre repetido (409) se dice bajo el campo, con el diálogo abierto, lo escrito y el foco en el campo', async ({ page }) => {
    const api = await conDosDefiniciones(page);
    await botonDeLaPantalla(page).click();

    await campoDelDialogo(page).fill('whatsapp COBRANZA');
    await botonDelDialogo(page).click();

    await expect(dialogo(page)).toBeVisible();
    await expect(dialogo(page).locator('[data-renombrar-error]')).toContainText('Ya hay una definición con ese nombre');
    await expect(campoDelDialogo(page)).toHaveAttribute('aria-invalid', 'true');
    await expect(campoDelDialogo(page)).toHaveAccessibleDescription(/Ya hay una definición con ese nombre/);
    await expect(campoDelDialogo(page)).toHaveValue('whatsapp COBRANZA');
    await expect(campoDelDialogo(page)).toBeFocused();
    await expect(botonDelDialogo(page)).toBeEnabled();
    expect(api.definiciones[0].nombre).toBe('SMS preventivo');

    // Editing clears the error: the next try is a new one.
    await campoDelDialogo(page).fill('WhatsApp cobranza 2');
    await expect(dialogo(page).locator('[data-renombrar-error]')).toBeEmpty();
    await expect(campoDelDialogo(page)).not.toHaveAttribute('aria-invalid', 'true');
  });

  test('un nombre vacío o demasiado largo lo rechaza el backend, y la pantalla lo dice con su propio texto y el tope del catálogo', async ({ page }) => {
    await conDosDefiniciones(page);
    await botonDeLaPantalla(page).click();

    await campoDelDialogo(page).fill('   ');
    await botonDelDialogo(page).click();

    await expect(dialogo(page).locator('[data-renombrar-error]')).toHaveText('Escribe un nombre de 1 a 120 caracteres.');
    await expect(campoDelDialogo(page)).toHaveAttribute('aria-invalid', 'true');
    // Not the backend's Spanish sentence: it would stay Spanish in English.
    await expect(dialogo(page)).not.toContainText('El nombre debe tener entre');
  });

  test('en inglés el diálogo y el error salen en inglés', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    const definiciones = apiDefiniciones();
    definiciones.definiciones.push(
      definicionFalsa({ id: 1, nombre: 'SMS preventivo' }),
      definicionFalsa({ id: 2, nombre: 'WhatsApp cobranza' }),
    );
    const base = apiVacia();
    base.manejadores = [manejarTextoEnriquecido(motorConDefiniciones()), manejadorDefiniciones(definiciones)];
    await montarApi(page, base);
    await page.goto(RUTA);
    await expect(page.getByRole('heading', { name: 'Load columns', level: 1 })).toBeVisible();
    await page.locator('[data-definiciones]').selectOption('1');
    await expect(page.locator('[data-renombrar]')).toBeVisible();

    await page.locator('[data-renombrar]').click();
    const dialog = page.getByRole('dialog', { name: /^Rename / });
    await expect(dialog.getByRole('heading')).toHaveText('Rename “SMS preventivo”');
    await page.getByLabel('New name').fill('   ');
    await dialog.getByRole('button', { name: 'Rename', exact: true }).click();

    await expect(dialog.locator('[data-renombrar-error]')).toHaveText('Enter a name of 1 to 120 characters.');
    await page.getByLabel('New name').fill('WhatsApp cobranza');
    await dialog.getByRole('button', { name: 'Rename', exact: true }).click();
    await expect(dialog.locator('[data-renombrar-error]')).toContainText('already exists');
  });

  test('desde una versión antigua en solo lectura solo cambia el nombre: lo que se mira se queda', async ({ page }) => {
    const api = await conDosDefiniciones(page, 3);
    await page.getByLabel('Versión', { exact: true }).selectOption('2');
    await expect(page.getByText('Estás viendo la versión 2. La vigente es la 3.')).toBeVisible();
    await expect(nombreDeColumna(page, 1)).toHaveValue('telefono_v2');

    await botonDeLaPantalla(page).click();
    await campoDelDialogo(page).fill('SMS preventivo B');
    await botonDelDialogo(page).click();

    await expect(page.getByLabel('Nombre', { exact: true })).toHaveValue('SMS preventivo B');
    await expect(page.getByText('Estás viendo la versión 2. La vigente es la 3.')).toBeVisible();
    await expect(nombreDeColumna(page, 1)).toHaveValue('telefono_v2');
    await expect(page.getByLabel('Versión', { exact: true })).toHaveValue('2');
    expect(patches(api)).toHaveLength(1);
    expect(api.definiciones[0].versiones).toHaveLength(3);
  });

  test('un borrador sin guardar sigue igual y renombrar no pide confirmar cambios', async ({ page }) => {
    const api = await conDosDefiniciones(page);
    await nombreDeColumna(page, 1).fill('telefono_editado');
    await expect(page.getByRole('button', { name: 'Guardar' })).toBeEnabled();

    await botonDeLaPantalla(page).click();
    await campoDelDialogo(page).fill('SMS preventivo B');
    await botonDelDialogo(page).click();

    await expect(dialogo(page)).toBeHidden();
    await expect(page.getByRole('dialog', { name: /Hay cambios sin guardar/ })).toHaveCount(0);
    await expect(nombreDeColumna(page, 1)).toHaveValue('telefono_editado');
    // Still a pending change, and still only that: the new name does not count as one.
    await expect(page.getByRole('button', { name: 'Guardar' })).toBeEnabled();
    expect(patches(api)).toHaveLength(1);

    await page.getByRole('button', { name: 'Descartar cambios' }).click();
    await expect(page.getByLabel('Nombre', { exact: true })).toHaveValue('SMS preventivo B');
    await expect(nombreDeColumna(page, 1)).toHaveValue('telefono');
  });

  test('renombrar solo no deja cambios sin guardar', async ({ page }) => {
    await conDosDefiniciones(page);
    await botonDeLaPantalla(page).click();
    await campoDelDialogo(page).fill('SMS preventivo B');
    await botonDelDialogo(page).click();
    await expect(dialogo(page)).toBeHidden();

    await expect(page.getByRole('button', { name: 'Guardar' })).toBeDisabled();
    await expect(page.getByRole('button', { name: 'Descartar cambios' })).toBeDisabled();
  });

  test('Cancelar y Escape no mandan nada y devuelven el foco a «Renombrar»', async ({ page }) => {
    const api = await conDosDefiniciones(page);

    await botonDeLaPantalla(page).click();
    await campoDelDialogo(page).fill('Otro nombre');
    await dialogo(page).getByRole('button', { name: 'Cancelar' }).click();
    await expect(dialogo(page)).toBeHidden();
    await expect(botonDeLaPantalla(page)).toBeFocused();

    await botonDeLaPantalla(page).click();
    await expect(campoDelDialogo(page)).toHaveValue('SMS preventivo');
    await page.keyboard.press('Escape');
    await expect(dialogo(page)).toBeHidden();
    await expect(botonDeLaPantalla(page)).toBeFocused();
    expect(patches(api)).toEqual([]);
    await expect(page.getByLabel('Nombre', { exact: true })).toHaveValue('SMS preventivo');
  });

  test('se hace con el teclado: Enter en el campo renombra', async ({ page }) => {
    const api = await conDosDefiniciones(page);
    await botonDeLaPantalla(page).focus();
    await page.keyboard.press('Enter');
    await expect(campoDelDialogo(page)).toBeFocused();

    await page.keyboard.type('Teclado');
    await page.keyboard.press('Enter');

    await expect(dialogo(page)).toBeHidden();
    await expect(page.getByLabel('Nombre', { exact: true })).toHaveValue('Teclado');
    expect(patches(api)).toHaveLength(1);
  });

  test('una definición que ya no existe (404) se dice bajo el campo y no cambia nada', async ({ page }) => {
    const api = await conDosDefiniciones(page);
    api.respuestas.renombrar = [{ estado: 404, cuerpo: { detail: 'No existe', codigo: 'definicion_no_encontrada' } }];
    await botonDeLaPantalla(page).click();

    await campoDelDialogo(page).fill('SMS preventivo B');
    await botonDelDialogo(page).click();

    await expect(dialogo(page)).toBeVisible();
    await expect(dialogo(page).locator('[data-renombrar-error]')).toContainText('Esa definición no existe');
    await expect(page.getByLabel('Nombre', { exact: true })).toHaveValue('SMS preventivo');
  });

  test('sin red lo dice y se puede reintentar', async ({ page }) => {
    const api = await conDosDefiniciones(page);
    await botonDeLaPantalla(page).click();
    await campoDelDialogo(page).fill('SMS preventivo B');
    api.sinRed = true;

    await botonDelDialogo(page).click();

    await expect(dialogo(page).locator('[data-renombrar-error]')).not.toBeEmpty();
    await expect(botonDelDialogo(page)).toBeEnabled();
    api.sinRed = false;
    await botonDelDialogo(page).click();
    await expect(dialogo(page)).toBeHidden();
    await expect(page.getByLabel('Nombre', { exact: true })).toHaveValue('SMS preventivo B');
  });
});

test.describe('una versión que segmenta sin el ajuste a la fecha de envío (D-C3-1)', () => {
  const AVISO = 'Esta versión calcula los segmentos con los días de atraso de la sábana, sin ajustarlos a la fecha de envío. Para usar el ajuste, guarda una versión nueva.';
  const aviso = (page: Page) => page.locator('[data-sin-ajuste]');
  const tabla = [{ clave: 'preventiva', etiqueta: 'Preventiva', desde: null, hasta: 0 }];

  type Segmentacion = NonNullable<ReturnType<typeof definicionFalsa>['versiones'][number]['contenido']['segmentacion']>;
  const calculado = (variable: string): Segmentacion => ({
    criterio: { tipo: 'calculado', variable_dias: variable, tabla },
    politica: 'excluir',
  });
  const porCampo: Segmentacion = { criterio: { tipo: 'campo', campo: 'segmento_financiero' }, politica: 'excluir' };

  async function conSegmentacion(page: Page, versiones: Array<Segmentacion | null>) {
    const definiciones = apiDefiniciones();
    const definicion = definicionFalsa({ id: 1, nombre: 'SMS preventivo', versiones: versiones.length });
    definicion.versiones.forEach((v, i) => {
      v.contenido.segmentacion = versiones[i];
    });
    definiciones.definiciones.push(definicion);
    await abrir(page, definiciones);
    await page.getByLabel('Definición guardada').selectOption('1');
    await expect(page.getByLabel('Nombre', { exact: true })).toHaveValue('SMS preventivo');
  }

  test('con los días de la sábana se avisa, en el panel de la definición, bajo la línea de versión', async ({ page }) => {
    await conSegmentacion(page, [calculado('dias_atraso')]);

    await expect(aviso(page)).toBeVisible();
    await expect(aviso(page)).toHaveText(AVISO);
    await expect(aviso(page)).toHaveClass(/notice--info/);
    const orden = await page.evaluate(() => {
      const linea = document.querySelector('[data-version-linea]')!;
      return Boolean(linea.compareDocumentPosition(document.querySelector('[data-sin-ajuste]')!) & Node.DOCUMENT_POSITION_FOLLOWING);
    });
    expect(orden).toBe(true);
  });

  test('con la variable ajustada que el catálogo da por defecto no hay aviso', async ({ page }) => {
    await conSegmentacion(page, [calculado('dias_atraso_ajustados')]);

    await expect(aviso(page)).toBeHidden();
  });

  test('un criterio por campo no cuenta días: sin aviso', async ({ page }) => {
    await conSegmentacion(page, [porCampo]);

    await expect(aviso(page)).toBeHidden();
  });

  test('sin segmentación, sin aviso; una definición sin guardar tampoco lo tiene', async ({ page }) => {
    await conSegmentacion(page, [null]);
    await expect(aviso(page)).toBeHidden();
  });

  test('no se reinterpreta una versión guardada: cada versión dice lo suyo al elegirla', async ({ page }) => {
    await conSegmentacion(page, [calculado('dias_atraso'), calculado('dias_atraso_ajustados')]);
    // The latest (2) is adjusted; the first one counts the sheet's days.
    await expect(aviso(page)).toBeHidden();

    await page.getByLabel('Versión', { exact: true }).selectOption('1');

    await expect(aviso(page)).toBeVisible();

    await page.getByLabel('Versión', { exact: true }).selectOption('2');

    await expect(aviso(page)).toBeHidden();
  });

  test('no bloquea guardar ni nada más: es un aviso sin acciones', async ({ page }) => {
    await conSegmentacion(page, [calculado('dias_atraso')]);

    await expect(aviso(page).getByRole('button')).toHaveCount(0);
    await nombreDeColumna(page, 1).fill('telefono_editado');
    await expect(page.getByRole('button', { name: 'Guardar' })).toBeEnabled();
  });

  test('en inglés el aviso sale en inglés', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    const definiciones = apiDefiniciones();
    const definicion = definicionFalsa({ id: 1, nombre: 'SMS preventivo' });
    definicion.versiones[0].contenido.segmentacion = calculado('dias_atraso');
    definiciones.definiciones.push(definicion);
    const base = apiVacia();
    base.manejadores = [manejarTextoEnriquecido(motorConDefiniciones()), manejadorDefiniciones(definiciones)];
    await montarApi(page, base);
    await page.goto(RUTA);
    await page.locator('[data-definiciones]').selectOption('1');

    await expect(aviso(page)).toHaveText(
      'This version works out the segments with the days past due from the sheet, without adjusting them to the send date. To use the adjustment, save a new version.',
    );
  });
});

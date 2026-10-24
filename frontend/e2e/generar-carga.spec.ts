/**
 * "Generar carga" (/generar-carga), end to end against intercepted APIs: the base fake (selector,
 * versions), the saved definitions and `/archivos-carga`, chained the way `montarApi` documents.
 *
 * What costs a load when it is wrong: the body of the preview is the body of the download and carries
 * exactly what the user chose (filters and order as the selector wrote them, never indicators; a
 * version only when it is not the current one), the amount follows the selection only until it is
 * edited, a file that may leave out products says so ("hasta N"), "not enough products" and "left
 * out for lack of a segment" are two different notices, Cancel only frees the screen and says what is
 * not known, and a refusal shows its reason while what was typed stays. Every name is synthetic.
 */
import { expect, test, type Page } from '@playwright/test';

import { apiVacia, montarApi, seleccionGuardada, version, type ApiFalsa } from './api-falsa';
import {
  apiArchivosCarga,
  crearCompuerta,
  manejadorArchivosCarga,
  type ApiFalsaArchivosCarga,
} from './api-falsa-archivos-carga';
import { apiDefiniciones, definicionFalsa, manejadorDefiniciones, type ApiFalsaDefiniciones } from './api-falsa-definiciones';

const RUTA = '/generar-carga';
const PREVIA = '/archivos-carga/previsualizacion';

interface Contexto {
  base: ApiFalsa;
  definiciones: ApiFalsaDefiniciones;
  cargas: ApiFalsaArchivosCarga;
}

async function abrir(
  page: Page,
  ajustar?: (contexto: Contexto) => void,
  { esperarContenido = true }: { esperarContenido?: boolean } = {},
): Promise<Contexto> {
  const base = apiVacia();
  base.versiones = [version({ fecha_corte: '2026-09-10', vigente: true })];
  base.selecciones = [
    seleccionGuardada({
      id: 1,
      nombre: 'Preventiva top 500',
      cantidad: 500,
      filtros: ['segmento_financiero:igual:1. Preventiva', 'telefono:no_vacio'],
      orden: '-saldo_capital_pendiente',
      indicadores: ['total:suma:saldo_capital_pendiente'],
    }),
  ];
  const definiciones = apiDefiniciones();
  definiciones.definiciones = [definicionFalsa({ id: 7, nombre: 'SMS preventivo', versiones: 4 })];
  const cargas = apiArchivosCarga();
  const contexto = { base, definiciones, cargas };
  ajustar?.(contexto);
  base.manejadores = [manejadorDefiniciones(definiciones), manejadorArchivosCarga(cargas)];
  await montarApi(page, base);
  await page.goto(RUTA);
  await expect(page.getByRole('heading', { name: 'Generar carga', level: 1 })).toBeVisible();
  if (esperarContenido) await expect(page.locator('[data-contenido]')).toBeVisible();
  return contexto;
}

const generar = (page: Page) => page.locator('[data-generar]');
const cancelar = (page: Page) => page.locator('[data-cancelar]');
const linea = (page: Page) => page.locator('[data-linea]');
const cantidad = (page: Page) => page.getByLabel('Cantidad a generar');
const formato = (page: Page, nombre: string) => page.locator('[data-formatos]').getByRole('button', { name: nombre, exact: true });
const filasDeLaTabla = (page: Page) => page.locator('[data-tabla-cuerpo] tr');

const previas = (cargas: ApiFalsaArchivosCarga) => cargas.pedidos.filter((p) => p.ruta === PREVIA);
const descargas = (cargas: ApiFalsaArchivosCarga) =>
  cargas.pedidos.filter((p) => p.ruta === '/archivos-carga' && p.metodo === 'POST');
/** The body of the latest preview, or undefined while none has been asked. */
const ultimaPrevia = (cargas: ApiFalsaArchivosCarga) => previas(cargas).at(-1)?.cuerpo;

async function elegirDefinicion(page: Page, nombre = 'SMS preventivo') {
  await page.getByLabel('Definición guardada').selectOption({ label: nombre });
  await expect(page.getByLabel('Versión', { exact: true })).toBeVisible();
}

async function elegirSeleccion(page: Page, nombre = 'Preventiva top 500') {
  await page.getByLabel('Selección guardada').selectOption({ label: nombre });
}

async function conPreviaLista(page: Page) {
  await expect(page.locator('[data-previa-contenido]')).toBeVisible();
}

/** Makes the definition 7 segment and leave out products with no segment, as the backend would for exclusions. */
function conExclusiones(contexto: Contexto, exclusiones: ApiFalsaArchivosCarga['exclusiones'], enLaCarga = exclusiones.length) {
  contexto.cargas.exclusiones = exclusiones;
  contexto.cargas.excluidosEnLaCarga = enLaCarga;
  contexto.cargas.segmentadas = [7];
  contexto.definiciones.definiciones[0].versiones.forEach((v) => {
    v.contenido.segmentacion = conSegmentacion('excluir');
  });
}

const conSegmentacion = (politica: 'excluir' | 'usar_por_defecto') => ({
  criterio: { tipo: 'campo' as const, campo: 'segmento_financiero' },
  politica,
});

test.describe('carga inicial', () => {
  test('explica qué es y deja la salida inactiva diciendo por qué', async ({ page }) => {
    const { cargas } = await abrir(page);

    await expect(page.getByText('«Cargas» es lo que entra', { exact: false })).toBeVisible();
    await expect(page.getByLabel('Selección guardada')).toBeVisible();
    // The compact picker has no editor of filters: this screen consumes a selection, it does not build one.
    await expect(page.getByText('Sin filtros: se considera toda la cartera del día.')).toBeHidden();
    await expect(generar(page)).toBeDisabled();
    await expect(linea(page)).toHaveText('Elige una definición de columnas para poder generar.');
    // The reason is written once, next to the button; the preview only says what it is waiting for.
    await expect(page.locator('[data-previa-pendiente]')).toHaveText(
      'La vista previa aparece cuando elijas una definición de columnas.',
    );
    await expect(page.getByText('Elige una definición de columnas para poder generar.')).toHaveCount(1);
    expect(previas(cargas)).toEqual([]);
  });

  test('sin definiciones guardadas lo dice y lleva a armar la primera', async ({ page }) => {
    await abrir(page, ({ definiciones }) => {
      definiciones.definiciones = [];
    });

    await expect(page.getByText('Todavía no hay definiciones guardadas')).toBeVisible();
    await expect(page.getByRole('link', { name: 'Ir a Columnas de carga' })).toHaveAttribute('href', '/columnas');
    await expect(page.getByLabel('Definición guardada')).toBeHidden();
    await expect(generar(page)).toBeDisabled();
  });

  test('sin conexión lo dice y recupera al reintentar', async ({ page }) => {
    const { cargas } = await abrir(page, ({ cargas: c }) => (c.sinRed = true), { esperarContenido: false });

    await expect(page.getByText('Sin conexión con la API')).toBeVisible();
    await expect(page.locator('[data-contenido]')).toBeHidden();

    cargas.sinRed = false;
    await page.getByRole('button', { name: 'Reintentar' }).click();
    await expect(page.locator('[data-contenido]')).toBeVisible();
    await expect(page.getByLabel('Definición guardada')).toBeVisible();
  });
});

test.describe('definición y versión', () => {
  test('elegir una definición muestra su resumen y pide la vista previa con la vigente, sin fijar versión', async ({ page }) => {
    const { cargas } = await abrir(page);
    await elegirDefinicion(page);

    await expect(page.getByLabel('Versión', { exact: true })).toHaveValue('4');
    await expect(page.getByRole('option', { name: 'Versión 4 (la vigente)' })).toBeAttached();
    const resumen = page.locator('[data-definicion-resumen]');
    await expect(resumen).toContainText('2');
    await expect(resumen).toContainText('Sin segmentación');
    await expect(resumen).toContainText('Sí');

    await conPreviaLista(page);
    expect(ultimaPrevia(cargas)?.definicion_guardada).toEqual({ id: 7 });
    await expect(page.getByRole('link', { name: 'Editar en Columnas de carga' })).toHaveAttribute('href', '/columnas');
  });

  test('una versión anterior se envía con su número; volver a la vigente la suelta', async ({ page }) => {
    const { cargas } = await abrir(page);
    await elegirDefinicion(page);
    await conPreviaLista(page);

    await page.getByLabel('Versión', { exact: true }).selectOption('2');
    await expect.poll(() => ultimaPrevia(cargas)?.definicion_guardada).toEqual({ id: 7, version: 2 });
    await expect(linea(page)).toContainText('con la versión 2 de “SMS preventivo”');

    await page.getByLabel('Versión', { exact: true }).selectOption('4');
    await expect.poll(() => ultimaPrevia(cargas)?.definicion_guardada).toEqual({ id: 7 });
    await expect(linea(page)).toContainText('con la versión 4 de “SMS preventivo”');
  });

  test('cambiar de definición suelta la versión elegida en la anterior', async ({ page }) => {
    const { cargas } = await abrir(page, ({ definiciones }) => {
      definiciones.definiciones.push(definicionFalsa({ id: 9, nombre: 'WhatsApp cobranza', versiones: 2 }));
    });
    await elegirDefinicion(page);
    await page.getByLabel('Versión', { exact: true }).selectOption('2');
    await expect.poll(() => ultimaPrevia(cargas)?.definicion_guardada).toEqual({ id: 7, version: 2 });

    await elegirDefinicion(page, 'WhatsApp cobranza');
    await expect(page.getByLabel('Versión', { exact: true })).toHaveValue('2');
    await expect.poll(() => ultimaPrevia(cargas)?.definicion_guardada).toEqual({ id: 9 });
  });

  test('una definición que no se puede leer lo dice sin tumbar la pantalla', async ({ page }) => {
    await abrir(page);
    await page.route('**/api/definiciones-columnas/7**', (route) =>
      route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'No existe', codigo: 'definicion_no_encontrada' }) }),
    );
    await page.getByLabel('Definición guardada').selectOption({ label: 'SMS preventivo' });

    await expect(page.locator('[data-definicion-error]')).toContainText('Esa definición no existe.');
    await expect(page.getByLabel('Definición guardada')).toHaveValue('');
    await expect(page.getByLabel('Versión', { exact: true })).toBeHidden();
    await expect(generar(page)).toBeDisabled();
    await expect(linea(page)).toHaveText('Elige una definición de columnas para poder generar.');
  });
});

test.describe('lo que se pide', () => {
  test('la vista previa lleva los filtros y el orden del selector tal cual, y nunca los indicadores', async ({ page }) => {
    const { cargas } = await abrir(page);
    await elegirSeleccion(page);
    await elegirDefinicion(page);
    await conPreviaLista(page);

    const cuerpo = ultimaPrevia(cargas)!;
    expect(cuerpo.filtros).toEqual(['segmento_financiero:igual:1. Preventiva', 'telefono:no_vacio']);
    expect(cuerpo.orden).toBe('-saldo_capital_pendiente');
    expect(cuerpo.fecha_corte).toBe('2026-09-10');
    expect(cuerpo).not.toHaveProperty('indicadores');
    expect(cuerpo).not.toHaveProperty('definicion');
  });

  test('la cantidad toma la de la selección hasta que se edita; sin ella, 1 000', async ({ page }) => {
    await abrir(page);
    await expect(cantidad(page)).toHaveValue('1000');
    await expect(page.locator('[data-cantidad-hint]')).toContainText('La selección no fija cantidad: se usan');
    await expect(page.locator('[data-cantidad-hint]')).toContainText('Máximo');

    await elegirSeleccion(page);
    await expect(cantidad(page)).toHaveValue('500');
    await expect(page.getByText('Toma la cantidad de la selección hasta que la cambies.')).toBeVisible();

    await cantidad(page).fill('120');
    await expect(page.getByText('Ya no sigue a la selección.')).toBeVisible();
    await page.getByLabel('Selección guardada').selectOption({ index: 0 });
    await expect(cantidad(page)).toHaveValue('120');
  });

  test('la cantidad fuera de 1 a 120 000 o con texto no se puede pedir', async ({ page }) => {
    const { cargas } = await abrir(page);
    await elegirDefinicion(page);
    await conPreviaLista(page);

    for (const texto of ['0', '120001', 'mucho', '']) {
      await cantidad(page).fill(texto);
      await expect(page.locator('[data-cantidad-error]')).toContainText('Escribe un número entero entre 1 y');
      await expect(generar(page)).toBeDisabled();
      await expect(linea(page)).toHaveText('Escribe una cantidad válida para poder generar.');
    }
    const antes = previas(cargas).length;

    await cantidad(page).fill('120000');
    await expect(page.locator('[data-cantidad-error]')).toBeEmpty();
    await expect(generar(page)).toBeEnabled();
    await expect.poll(() => previas(cargas).length).toBeGreaterThan(antes);
    expect(ultimaPrevia(cargas)?.cantidad).toBe(120000);
  });

  test('una selección con partes que no aplican no deja pedir nada', async ({ page }) => {
    const { cargas } = await abrir(page, ({ base }) => {
      base.selecciones = [
        seleccionGuardada({
          id: 2,
          nombre: 'Selección rota',
          cantidad: 500,
          filtros: ['campo_retirado:igual:x'],
          aplicable: false,
          problemas: [{ parte: 'filtro', expresion: 'campo_retirado:igual:x', detalle: 'El campo no existe' }],
        }),
      ];
    });
    await elegirDefinicion(page);
    await conPreviaLista(page);
    const antes = previas(cargas).length;

    await elegirSeleccion(page, 'Selección rota · no aplica');

    await expect(generar(page)).toBeDisabled();
    await expect(linea(page)).toHaveText('La selección tiene partes que no aplican; corrígelas en Cartera.');
    await page.waitForTimeout(900);
    expect(previas(cargas).length).toBe(antes);
  });
});

test.describe('formato y opciones', () => {
  test('cada formato muestra las opciones que la API anuncia y el cuerpo lleva el formato elegido', async ({ page }) => {
    const { cargas } = await abrir(page);
    await elegirDefinicion(page);
    await conPreviaLista(page);

    await expect(formato(page, 'XLSX')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByLabel('Nombre de la hoja')).toHaveValue('Carga');
    await expect(page.getByLabel('Incluir la fila de cabeceras')).toBeChecked();
    await expect(page.getByLabel('Delimitador', { exact: true })).toBeHidden();

    await formato(page, 'CSV').click();
    await expect(formato(page, 'CSV')).toHaveAttribute('aria-pressed', 'true');
    await expect(formato(page, 'XLSX')).toHaveAttribute('aria-pressed', 'false');
    await expect(page.getByLabel('Delimitador', { exact: true })).toHaveValue(',');
    await expect(page.getByLabel('Codificación', { exact: true })).toHaveValue('utf-8');
    await expect(page.getByLabel('Nombre de la hoja')).toBeHidden();
    await expect.poll(() => ultimaPrevia(cargas)?.formato).toBe('csv');

    await formato(page, 'JSON').click();
    await expect(page.getByLabel('Sangría')).toHaveValue('');
    await expect(page.getByText('De 0 a 8 espacios. Vacío: todo en una línea.')).toBeVisible();
    await expect.poll(() => ultimaPrevia(cargas)?.formato).toBe('json');
  });

  test('las opciones sin tocar no viajan; al editar una viaja completa con los defectos de la API', async ({ page }) => {
    const { cargas } = await abrir(page);
    await elegirDefinicion(page);
    await formato(page, 'CSV').click();
    await conPreviaLista(page);
    expect(ultimaPrevia(cargas)).not.toHaveProperty('opciones');

    await page.getByLabel('Delimitador', { exact: true }).selectOption({ label: 'punto y coma (;)' });

    await expect
      .poll(() => ultimaPrevia(cargas)?.opciones)
      .toEqual({ delimitador: ';', codificacion: 'utf-8', con_cabeceras: true, hoja: 'Carga', sangria: null });
  });

  test('el delimitador ofrece nombres legibles, incluida la tabulación, y «Personalizado» abre un campo de un carácter', async ({ page }) => {
    const { cargas } = await abrir(page);
    await elegirDefinicion(page);
    await formato(page, 'CSV').click();
    await conPreviaLista(page);

    const delimitador = page.getByLabel('Delimitador', { exact: true });
    for (const nombre of ['coma (,)', 'punto y coma (;)', 'tabulación', 'barra vertical (|)', 'Personalizado']) {
      await expect(delimitador.getByRole('option', { name: nombre })).toBeAttached();
    }
    await delimitador.selectOption({ label: 'tabulación' });
    await expect.poll(() => ultimaPrevia(cargas)?.opciones?.delimitador).toBe('\t');

    await delimitador.selectOption({ label: 'Personalizado' });
    const propio = page.locator('#gc-op-delimitador-propio');
    await expect(propio).toBeVisible();
    await expect(propio).toHaveAttribute('maxlength', '1');
    await propio.fill('~');
    await expect.poll(() => ultimaPrevia(cargas)?.opciones?.delimitador).toBe('~');
  });

  test('la codificación se muestra tal cual y admite otra', async ({ page }) => {
    const { cargas } = await abrir(page);
    await elegirDefinicion(page);
    await formato(page, 'CSV').click();
    await conPreviaLista(page);

    const codificacion = page.getByLabel('Codificación', { exact: true });
    await expect(codificacion.getByRole('option', { name: 'latin-1' })).toBeAttached();
    await codificacion.selectOption({ label: 'Personalizado' });
    await page.locator('#gc-op-codificacion-propio').fill('utf-16');
    await expect.poll(() => ultimaPrevia(cargas)?.opciones?.codificacion).toBe('utf-16');
  });

  test('la sangría es un número: con letras no se puede pedir; con dígitos viaja como número; vacía, una línea', async ({ page }) => {
    const { cargas } = await abrir(page);
    await elegirDefinicion(page);
    await formato(page, 'JSON').click();
    await conPreviaLista(page);

    const sangria = page.getByLabel('Sangría');
    await expect(sangria).toHaveAttribute('inputmode', 'numeric');
    await sangria.fill('cuatro');
    await expect(generar(page)).toBeDisabled();
    await expect(linea(page)).toHaveText('Corrige la opción «Sangría»: debe ser un número entero.');

    await sangria.fill('4');
    await expect(generar(page)).toBeEnabled();
    await expect.poll(() => ultimaPrevia(cargas)?.opciones?.sangria).toBe(4);

    await sangria.fill('');
    await expect.poll(() => ultimaPrevia(cargas)?.opciones?.sangria).toBeNull();
  });

  test('no valida reglas de plataforma: una hoja larga y con caracteres raros se envía y el backend decide', async ({ page }) => {
    const { cargas } = await abrir(page);
    await elegirDefinicion(page);
    await conPreviaLista(page);
    const hoja = page.getByLabel('Nombre de la hoja');
    await expect(hoja).toHaveAttribute('maxlength', '31');

    await hoja.fill('Hoja:de/carga?');

    await expect(generar(page)).toBeEnabled();
    await expect.poll(() => ultimaPrevia(cargas)?.opciones?.hoja).toBe('Hoja:de/carga?');
  });

  test('la casilla de cabeceras viaja como booleano', async ({ page }) => {
    const { cargas } = await abrir(page);
    await elegirDefinicion(page);
    await conPreviaLista(page);

    await page.getByLabel('Incluir la fila de cabeceras').uncheck();

    await expect.poll(() => ultimaPrevia(cargas)?.opciones?.con_cabeceras).toBe(false);
  });
});

test.describe('vista previa', () => {
  test('muestra la muestra de 20 filas y las cifras, sin avisos cuando todo alcanza', async ({ page }) => {
    const { cargas } = await abrir(page, ({ cargas: c }) => (c.disponibles = 3200));
    await elegirSeleccion(page);
    await elegirDefinicion(page);
    await conPreviaLista(page);

    await expect(filasDeLaTabla(page)).toHaveCount(20);
    await expect(page.locator('[data-tabla-cabeza] th')).toHaveText(['anexo', 'numero', 'mensaje']);
    await expect(page.locator('[data-cifra-solicitados]')).toHaveText('500');
    await expect(page.locator('[data-cifra-muestra]')).toHaveText('20');
    await expect(page.locator('[data-aviso-suficiencia]')).toBeHidden();
    await expect(page.locator('[data-aviso-exclusiones]')).toBeHidden();
    await expect(page.locator('[data-aviso-errores]')).toBeHidden();
    await expect(page.locator('[data-problemas]')).toBeHidden();
    await expect(linea(page)).toHaveText(
      /^Se generarán 500 filas en XLSX con la versión 4 de “SMS preventivo”, para enviar el .+ \d{4}\.$/,
    );
    expect(cargas.pedidos.some((p) => p.ruta === '/archivos-carga' && p.metodo === 'POST')).toBe(false);
  });

  test('si hay menos productos que los pedidos lo dice aparte y el total se acota', async ({ page }) => {
    await abrir(page, ({ cargas }) => (cargas.disponibles = 300));
    await elegirSeleccion(page);
    await elegirDefinicion(page);
    await conPreviaLista(page);

    await expect(page.locator('[data-aviso-suficiencia]')).toBeVisible();
    // Not enough products is not a problem: the file comes out with the ones there are.
    await expect(page.locator('[data-aviso-suficiencia]')).toHaveClass(/notice--info/);
    await expect(page.locator('[data-aviso-suficiencia]')).toContainText(
      'Hay 300 productos y se pidieron 500. El archivo sale con los 300 que hay.',
    );
    await expect(page.locator('[data-aviso-exclusiones]')).toBeHidden();
    await expect(linea(page)).toContainText('Se generarán 300 filas');
  });

  test('los productos sin segmento son otro aviso, no el de «no alcanzan», y salen en la lista de problemas', async ({ page }) => {
    await abrir(page, (contexto) => {
      conExclusiones(
        contexto,
        [4, 9, 13].map((fila) => ({
          fila,
          pagare: `90000${String(fila).padStart(2, '0')}`,
          codigo: 'sin_segmento' as const,
          detalle: 'El producto no cae en ningún segmento',
        })),
      );
      contexto.cargas.disponibles = 3200;
    });
    await elegirSeleccion(page);
    await elegirDefinicion(page);
    await conPreviaLista(page);

    await expect(page.locator('[data-aviso-exclusiones]')).toBeVisible();
    await expect(page.locator('[data-aviso-exclusiones]')).toHaveClass(/notice--warning/);
    await expect(page.locator('[data-aviso-exclusiones]')).toContainText(
      'Productos de la muestra que no salen en el archivo por no caer en ningún segmento: 3 de 20.',
    );
    await expect(page.locator('[data-aviso-suficiencia]')).toBeHidden();
    await expect(filasDeLaTabla(page)).toHaveCount(17);
    const problemas = page.locator('[data-problemas-cuerpo] tr');
    await expect(problemas).toHaveCount(3);
    await expect(problemas.first()).toContainText('Producto 4 de la selección · pagaré 9000004');
    await expect(problemas.first()).toContainText('no cae en ningún segmento');
    await expect(linea(page)).toContainText('Se generarán hasta 500 filas');
  });

  test('más de cinco del mismo motivo son un grupo con su botón; menos, filas sueltas', async ({ page }) => {
    await abrir(page, (contexto) => {
      conExclusiones(
        contexto,
        Array.from({ length: 6 }, (_, i) => ({
          fila: i + 1,
          pagare: `90001${String(i).padStart(2, '0')}`,
          codigo: 'sin_segmento' as const,
          detalle: 'El producto no cae en ningún segmento',
        })),
      );
    });
    await elegirDefinicion(page);
    await conPreviaLista(page);

    // One row: where (how many, and the button), what happened (in plain text, not inside the button).
    const fila = page.locator('[data-problemas-cuerpo] tr').first();
    await expect(fila.locator('td').first()).toContainText('6 productos');
    await expect(fila.locator('td').nth(1)).toContainText('no cae en ningún segmento');
    const grupo = fila.getByRole('button', { name: 'Ver los 6' });
    await expect(grupo).toHaveAttribute('aria-expanded', 'false');
    await expect(grupo).toHaveAttribute('aria-controls', /gc-grupo-\d+/);
    await expect(grupo).not.toContainText('no cae en ningún segmento');
    const items = page.locator('.gc-problemas__lista li');
    await expect(items.first()).toBeHidden();

    await grupo.click();
    await expect(grupo).toHaveAttribute('aria-expanded', 'true');
    await expect(items.first()).toBeVisible();
    await expect(items).toHaveCount(6);
    // The group's row already says why; each product only says which one it is.
    await expect(items.first()).toHaveText('Producto 1 de la selección · pagaré 9000100');
    await expect(items.first()).not.toContainText('no cae en ningún segmento');

    await grupo.click();
    await expect(grupo).toHaveAttribute('aria-expanded', 'false');
    await expect(items.first()).toBeHidden();
  });

  test('una definición sin segmentación nunca trae exclusiones, aunque el servidor falso las tenga', async ({ page }) => {
    await abrir(page, ({ cargas }) => {
      cargas.exclusiones = [{ fila: 1, pagare: '9000001', codigo: 'sin_segmento', detalle: 'x' }];
    });
    await elegirDefinicion(page);
    await conPreviaLista(page);

    await expect(page.locator('[data-aviso-exclusiones]')).toBeHidden();
    await expect(page.locator('[data-problemas]')).toBeHidden();
    await expect(filasDeLaTabla(page)).toHaveCount(20);
  });

  test('los campos que no se pudieron generar se avisan y listan, y no impiden descargar', async ({ page }) => {
    await abrir(page, ({ cargas }) => {
      cargas.errores = [{ fila: 2, campo: 'mensaje', detalle: 'La variable titular está vacía' }];
    });
    await elegirDefinicion(page);
    await conPreviaLista(page);

    await expect(page.locator('[data-aviso-errores]')).toBeVisible();
    await expect(page.locator('[data-aviso-errores]')).toContainText('Campos que no se pudieron generar en la muestra: 1.');
    const problema = page.locator('[data-problemas-cuerpo] tr');
    await expect(problema).toHaveCount(1);
    await expect(problema).toContainText('Columna «mensaje», fila 2 de la tabla');
    await expect(problema).toContainText('La variable titular está vacía');
    await expect(generar(page)).toBeEnabled();
  });

  test('una selección sin productos lo dice en vez de mostrar una tabla vacía', async ({ page }) => {
    await abrir(page, ({ cargas }) => (cargas.disponibles = 0));
    await elegirDefinicion(page);

    await expect(page.locator('[data-previa-pendiente]')).toHaveText('La selección no tiene productos con esta fecha de corte.');
    await expect(page.locator('[data-previa-contenido]')).toBeHidden();
  });

  test('si la API rechaza la vista previa muestra su motivo y reintentar la recupera', async ({ page }) => {
    const { cargas } = await abrir(page, ({ cargas: c }) => {
      c.respuestas.previsualizar = [{ estado: 400, cuerpo: { detail: 'El filtro «x» está mal escrito' } }];
    });
    await elegirDefinicion(page);

    await expect(page.locator('[data-previa-error]')).toContainText('No se pudo calcular la vista previa: El filtro «x» está mal escrito');
    await expect(cantidad(page)).toHaveValue('1000');

    cargas.respuestas.previsualizar = [];
    await page.getByRole('button', { name: 'Reintentar' }).last().click();
    await conPreviaLista(page);
    await expect(page.locator('[data-previa-error]')).toBeHidden();
  });

  test('el último cambio gana: una respuesta vieja que llega tarde no pisa la nueva', async ({ page }) => {
    const { cargas } = await abrir(page);
    const { compuerta, liberar } = crearCompuerta();
    cargas.compuertaPrevia = compuerta;

    await elegirDefinicion(page);
    await expect.poll(() => previas(cargas).length).toBe(1);

    await cantidad(page).fill('100');
    await expect(page.locator('[data-cifra-solicitados]')).toHaveText('100');

    liberar();
    await page.waitForTimeout(400);
    await expect(page.locator('[data-cifra-solicitados]')).toHaveText('100');
    expect(previas(cargas)).toHaveLength(2);
  });

  test('una ráfaga de cambios es una sola petición', async ({ page }) => {
    const { cargas } = await abrir(page);
    await elegirDefinicion(page);
    await conPreviaLista(page);
    const antes = previas(cargas).length;

    for (const texto of ['1', '12', '123', '1234']) await cantidad(page).fill(texto);

    await expect.poll(() => previas(cargas).length).toBe(antes + 1);
    await page.waitForTimeout(900);
    expect(previas(cargas)).toHaveLength(antes + 1);
    expect(ultimaPrevia(cargas)?.cantidad).toBe(1234);
  });
});

test.describe('generar', () => {
  test('descarga el archivo con el nombre del servidor, la misma petición que la vista previa y el resumen de sus cabeceras', async ({ page }) => {
    const { cargas } = await abrir(page, (contexto) => {
      contexto.cargas.disponibles = 3200;
      conExclusiones(contexto, [], 3);
    });
    await elegirSeleccion(page);
    await elegirDefinicion(page);
    await formato(page, 'CSV').click();
    await conPreviaLista(page);

    const [descarga] = await Promise.all([page.waitForEvent('download'), generar(page).click()]);

    expect(descarga.suggestedFilename()).toBe('sms_preventivo.csv');
    const aviso = page.locator('[data-resultado-exito]');
    await expect(aviso).toContainText('Se descargó «sms_preventivo.csv»: 497 filas generadas y 3 excluidas.');
    await expect(aviso).toContainText('La versión 4 de “SMS preventivo” queda marcada como usada.');
    expect(descargas(cargas)).toHaveLength(1);
    expect(descargas(cargas)[0].cuerpo).toEqual(ultimaPrevia(cargas));
    await expect(generar(page)).toBeEnabled();
    await expect(generar(page)).toBeFocused();
  });

  test('con 0 excluidas el aviso de éxito no menciona exclusiones', async ({ page }) => {
    await abrir(page, ({ cargas }) => (cargas.disponibles = 300));
    await elegirDefinicion(page);
    await conPreviaLista(page);

    await Promise.all([page.waitForEvent('download'), generar(page).click()]);

    const aviso = page.locator('[data-resultado-exito]');
    await expect(aviso).toContainText('Se descargó «sms_preventivo.xlsx»: 300 filas generadas.');
    await expect(aviso).not.toContainText('excluidas');
  });

  test('si no alcanzaban los productos el aviso de éxito también lo dice', async ({ page }) => {
    await abrir(page, ({ cargas }) => (cargas.disponibles = 300));
    await elegirSeleccion(page);
    await elegirDefinicion(page);
    await conPreviaLista(page);

    await Promise.all([page.waitForEvent('download'), generar(page).click()]);

    const aviso = page.locator('[data-resultado-exito]');
    await expect(aviso).toContainText('Había 300 productos y se pidieron 500.');
    await expect(aviso).not.toContainText('El archivo sale con');
  });

  test('con una definición que excluye, el total es un tope («hasta»); con la que usa el contenido por defecto, exacto', async ({ page }) => {
    await abrir(page, ({ definiciones }) => {
      const excluye = definicionFalsa({ id: 8, nombre: 'WhatsApp segmentado' });
      excluye.versiones[0].contenido.segmentacion = conSegmentacion('excluir');
      const usaDefecto = definicionFalsa({ id: 9, nombre: 'Correo segmentado' });
      usaDefecto.versiones[0].contenido.segmentacion = conSegmentacion('usar_por_defecto');
      definiciones.definiciones.push(excluye, usaDefecto);
    });

    await elegirDefinicion(page, 'WhatsApp segmentado');
    await expect(page.locator('[data-resumen-segmentacion]')).toHaveText(
      'Con segmentación: los productos sin segmento quedan fuera',
    );
    await expect(linea(page)).toContainText('Se generarán hasta 1000 filas');
    await expect(linea(page)).toContainText('los productos sin segmento quedan fuera');

    await elegirDefinicion(page, 'Correo segmentado');
    await expect(page.locator('[data-resumen-segmentacion]')).toHaveText(
      'Con segmentación: los productos sin segmento usan el contenido por defecto',
    );
    await expect(linea(page)).toContainText('Se generarán 1000 filas');
    await expect(linea(page)).not.toContainText('hasta');
  });

  test('mientras genera cierra el formulario, lleva el foco a Cancelar y no deja lanzar otra descarga', async ({ page }) => {
    const { cargas } = await abrir(page);
    const { compuerta, liberar } = crearCompuerta();
    cargas.compuerta = compuerta;
    await elegirDefinicion(page);
    await conPreviaLista(page);

    await generar(page).click();

    await expect(cancelar(page)).toBeVisible();
    await expect(cancelar(page)).toBeFocused();
    await expect(generar(page)).toBeDisabled();
    await expect(generar(page)).toContainText('Generando…');
    await expect(page.locator('[data-selector]')).toHaveJSProperty('inert', true);
    expect(descargas(cargas)).toHaveLength(1);

    liberar();
    await expect(page.locator('[data-resultado-exito]')).toBeVisible();
    await expect(cancelar(page)).toBeHidden();
    await expect(page.locator('[data-selector]')).toHaveJSProperty('inert', false);
    expect(descargas(cargas)).toHaveLength(1);
  });

  test('Cancelar libera la pantalla, devuelve el foco y avisa sin prometer lo que no sabe', async ({ page }) => {
    const { cargas } = await abrir(page);
    const { compuerta, liberar } = crearCompuerta();
    cargas.compuerta = compuerta;
    await elegirDefinicion(page);
    await conPreviaLista(page);
    await generar(page).click();
    await expect(cancelar(page)).toBeFocused();

    await cancelar(page).click();

    const aviso = page.locator('[data-resultado-cancelado]');
    await expect(aviso).toHaveText('Se canceló la descarga. Si el servidor alcanzó a terminarla, la versión 4 puede figurar como usada.');
    await expect(page.locator('[data-resultado-exito]')).toBeHidden();
    await expect(page.locator('[data-resultado-error]')).toBeHidden();
    await expect(cancelar(page)).toBeHidden();
    await expect(generar(page)).toBeEnabled();
    await expect(generar(page)).toBeFocused();
    await expect(page.locator('[data-selector]')).toHaveJSProperty('inert', false);

    // The server is free to finish; the screen does not wait for it and can ask again.
    liberar();
    cargas.compuerta = null;
    const [descarga] = await Promise.all([page.waitForEvent('download'), generar(page).click()]);
    expect(descarga.suggestedFilename()).toBe('sms_preventivo.xlsx');
    await expect(page.locator('[data-resultado-cancelado]')).toBeHidden();
  });

  test('un rechazo muestra el motivo del catálogo, deja lo escrito y devuelve el foco', async ({ page }) => {
    const { cargas } = await abrir(page, ({ cargas: c }) => {
      c.respuestas.generar = [{ estado: 404, cuerpo: { detail: 'No hay cartera vigente', codigo: 'sin_version_vigente' } }];
    });
    await elegirSeleccion(page);
    await elegirDefinicion(page);
    await cantidad(page).fill('250');
    await conPreviaLista(page);

    await generar(page).click();

    const aviso = page.locator('[data-resultado-error]');
    await expect(aviso).toContainText('No se pudo generar el archivo');
    await expect(aviso).toContainText('No hay cartera vigente para esa fecha de corte. Elige otra fecha.');
    await expect(cantidad(page)).toHaveValue('250');
    await expect(page.getByLabel('Definición guardada')).toHaveValue('7');
    await expect(generar(page)).toBeEnabled();
    await expect(generar(page)).toBeFocused();
    expect(descargas(cargas)).toHaveLength(1);
  });

  test('un rechazo sin código muestra la frase del servidor', async ({ page }) => {
    await abrir(page, ({ cargas }) => {
      cargas.respuestas.generar = [{ estado: 400, cuerpo: { detail: 'La codificación «utf-99» no existe' } }];
    });
    await elegirDefinicion(page);
    await conPreviaLista(page);

    await generar(page).click();

    await expect(page.locator('[data-resultado-error]')).toContainText('La codificación «utf-99» no existe');
  });

  test('sin red al generar lo dice y deja reintentar', async ({ page }) => {
    const { cargas } = await abrir(page);
    await elegirDefinicion(page);
    await conPreviaLista(page);
    cargas.sinRed = true;

    await generar(page).click();

    await expect(page.locator('[data-resultado-error]')).toContainText('No se pudo contactar con el backend');
    await expect(generar(page)).toBeEnabled();
    cargas.sinRed = false;
    const [descarga] = await Promise.all([page.waitForEvent('download'), generar(page).click()]);
    expect(descarga.suggestedFilename()).toBe('sms_preventivo.xlsx');
  });
});

test.describe('fecha de envío (RF-55)', () => {
  const campo = (page: Page) => page.getByLabel('Fecha de envío');
  const errorDeFecha = (page: Page) => page.locator('[data-envio-error]');
  const lineaDeEnvio = (page: Page) => page.locator('[data-previa-envio]');

  // Lima is UTC-5: 02:30 UTC on the 20th is 21:30 in Lima on the 19th.
  const NOCHE_DE_LIMA = '2026-10-20T02:30:00Z';

  test('está en el panel «Selección», junto al selector, y es una fecha', async ({ page }) => {
    await abrir(page);

    await expect(page.locator('[data-selector] [data-envio]')).toHaveCount(1);
    await expect(campo(page)).toHaveAttribute('type', 'date');
    await expect(page.locator('#gc-envio-hint')).toHaveText(
      'Los días de atraso se cuentan hasta esta fecha para calcular el segmento. Por defecto, hoy.',
    );
    await expect(campo(page)).toHaveAccessibleDescription(/Los días de atraso se cuentan hasta esta fecha/);
  });

  test('por defecto es hoy en Lima: de noche, cuando UTC ya es mañana, sigue siendo hoy', async ({ page }) => {
    await page.clock.setFixedTime(new Date(NOCHE_DE_LIMA));
    await abrir(page);

    await expect(campo(page)).toHaveValue('2026-10-19');
  });

  test('con el reloj ya en el día siguiente de Lima, el defecto es ese día', async ({ page }) => {
    await page.clock.setFixedTime(new Date('2026-10-20T05:00:00Z'));
    await abrir(page);

    await expect(campo(page)).toHaveValue('2026-10-20');
  });

  test('el mínimo es la fecha de corte elegida', async ({ page }) => {
    await abrir(page);

    await expect(campo(page)).toHaveAttribute('min', '2026-09-10');
  });

  test('viaja siempre, explícita, y es la misma en la vista previa y en la descarga', async ({ page }) => {
    await page.clock.setFixedTime(new Date(NOCHE_DE_LIMA));
    const { cargas } = await abrir(page);
    await elegirDefinicion(page);
    await conPreviaLista(page);

    expect(ultimaPrevia(cargas)!.fecha_envio).toBe('2026-10-19');
    await Promise.all([page.waitForEvent('download'), generar(page).click()]);
    expect(descargas(cargas)[0].cuerpo).toEqual(ultimaPrevia(cargas));
  });

  test('cambiarla recalcula la vista previa y la línea del botón dice para cuándo es', async ({ page }) => {
    const { cargas } = await abrir(page);
    await elegirDefinicion(page);
    await conPreviaLista(page);
    const antes = previas(cargas).length;

    await campo(page).fill('2026-09-14');

    await expect.poll(() => previas(cargas).length).toBeGreaterThan(antes);
    expect(ultimaPrevia(cargas)!.fecha_envio).toBe('2026-09-14');
    await expect(linea(page)).toContainText('para enviar el');
    await expect(linea(page)).toContainText('2026');
  });

  test('la vista previa dice la fecha de envío y cuántos días pasaron desde el corte: varios, uno o el mismo día', async ({ page }) => {
    await abrir(page);
    await elegirDefinicion(page);
    await conPreviaLista(page);

    await campo(page).fill('2026-09-14');
    await expect(lineaDeEnvio(page)).toContainText('Fecha de envío:');
    await expect(lineaDeEnvio(page)).toContainText('4 días después del corte');
    await campo(page).fill('2026-09-11');
    await expect(lineaDeEnvio(page)).toContainText('1 día después del corte');
    await expect(lineaDeEnvio(page)).not.toContainText('1 días');
    await campo(page).fill('2026-09-10');
    await expect(lineaDeEnvio(page)).toContainText('el mismo día del corte');
  });

  test('en inglés la línea de la vista previa sale en inglés', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    const base = apiVacia();
    base.versiones = [version({ fecha_corte: '2026-09-10', vigente: true })];
    const definiciones = apiDefiniciones();
    definiciones.definiciones = [definicionFalsa({ id: 7, nombre: 'SMS preventivo', versiones: 2 })];
    const cargas = apiArchivosCarga();
    base.manejadores = [manejadorDefiniciones(definiciones), manejadorArchivosCarga(cargas)];
    await montarApi(page, base);
    await page.goto(RUTA);
    await expect(page.locator('[data-contenido]')).toBeVisible();
    await page.getByLabel('Saved definition').selectOption({ label: 'SMS preventivo' });
    await expect(page.locator('[data-previa-contenido]')).toBeVisible();

    await page.getByLabel('Send date').fill('2026-09-12');

    await expect(page.locator('[data-previa-envio]')).toContainText('Send date:');
    await expect(page.locator('[data-previa-envio]')).toContainText('2 days after the cut-off');
  });

  test('una fecha anterior al corte la rechaza el backend: el error va bajo el campo con las dos fechas, sin llaves, y lo escrito se queda', async ({ page }) => {
    await abrir(page);
    await elegirDefinicion(page);
    await conPreviaLista(page);

    await campo(page).fill('2026-09-01');

    await expect(errorDeFecha(page)).toHaveText(
      /^La fecha de envío \(.+\) es anterior a la fecha de corte \(.+\)\. Elige una fecha igual o posterior\.$/,
    );
    await expect(errorDeFecha(page)).not.toContainText('{');
    await expect(errorDeFecha(page)).not.toContainText('}');
    // Both dates are named, written by format.ts (the month's spelling is the browser's, not ours).
    await expect(errorDeFecha(page)).toHaveText(/\(01 .+ 2026\).+\(10 .+ 2026\)/);
    await expect(campo(page)).toHaveAttribute('aria-invalid', 'true');
    await expect(campo(page)).toHaveAccessibleDescription(/es anterior a la fecha de corte/);
    await expect(campo(page)).toHaveValue('2026-09-01');
    // No second summary in the preview panel, and the button says what to do.
    await expect(page.locator('[data-previa-error]')).toBeHidden();
    await expect(generar(page)).toBeDisabled();
    await expect(linea(page)).toHaveText('Corrige la fecha de envío para poder generar.');

    await campo(page).fill('2026-09-10');

    await expect(errorDeFecha(page)).toBeEmpty();
    await expect(campo(page)).not.toHaveAttribute('aria-invalid', 'true');
    await expect(generar(page)).toBeEnabled();
    await conPreviaLista(page);
  });

  test('el rechazo de la descarga también va bajo el campo, no en el aviso general', async ({ page }) => {
    const { cargas } = await abrir(page, ({ cargas: c }) => {
      c.respuestas.generar = [
        {
          estado: 400,
          cuerpo: { detail: 'x', codigo: 'fecha_envio_anterior', fecha_envio: '2026-09-09', fecha_corte: '2026-09-10' },
        },
      ];
    });
    await elegirDefinicion(page);
    await conPreviaLista(page);

    await generar(page).click();

    await expect(errorDeFecha(page)).toContainText('es anterior a la fecha de corte');
    await expect(page.locator('[data-resultado-error]')).toBeHidden();
    expect(descargas(cargas)).toHaveLength(1);
  });

  test('en inglés el error sale en inglés, con las dos fechas', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('app:appearance', JSON.stringify({ language: 'en' }));
    });
    const base = apiVacia();
    base.versiones = [version({ fecha_corte: '2026-09-10', vigente: true })];
    const definiciones = apiDefiniciones();
    definiciones.definiciones = [definicionFalsa({ id: 7, nombre: 'SMS preventivo' })];
    base.manejadores = [manejadorDefiniciones(definiciones), manejadorArchivosCarga(apiArchivosCarga())];
    await montarApi(page, base);
    await page.goto(RUTA);
    await page.getByLabel('Saved definition').selectOption({ label: 'SMS preventivo' });

    await page.getByLabel('Send date').fill('2026-09-01');

    await expect(page.locator('[data-envio-error]')).toHaveText(
      /^The send date \(.+\) is before the cut-off date \(.+\)\. Choose the same date or a later one\.$/,
    );
  });

  test('sin fecha de envío no se puede pedir, y lo dice', async ({ page }) => {
    await abrir(page);
    await elegirDefinicion(page);
    await conPreviaLista(page);

    await campo(page).fill('');

    await expect(generar(page)).toBeDisabled();
    await expect(linea(page)).toHaveText('Elige la fecha de envío para poder generar.');
  });

  test('pasada la medianoche, al volver a la pestaña con la fecha sin tocar, se toma el hoy de Lima otra vez', async ({ page }) => {
    await page.clock.setFixedTime(new Date(NOCHE_DE_LIMA));
    const { cargas } = await abrir(page);
    await elegirDefinicion(page);
    await conPreviaLista(page);
    await expect(campo(page)).toHaveValue('2026-10-19');

    // Lima turns the 20th while the screen stays open.
    await page.clock.setFixedTime(new Date('2026-10-20T06:00:00Z'));
    await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));

    await expect(campo(page)).toHaveValue('2026-10-20');
    await expect.poll(() => ultimaPrevia(cargas)?.fecha_envio).toBe('2026-10-20');
  });

  test('una fecha que el analista tocó se respeta aunque pase la medianoche', async ({ page }) => {
    await page.clock.setFixedTime(new Date(NOCHE_DE_LIMA));
    const { cargas } = await abrir(page);
    await elegirDefinicion(page);
    await conPreviaLista(page);
    await campo(page).fill('2026-09-30');
    await expect.poll(() => ultimaPrevia(cargas)?.fecha_envio).toBe('2026-09-30');

    await page.clock.setFixedTime(new Date('2026-10-20T06:00:00Z'));
    await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
    await page.waitForTimeout(300);

    await expect(campo(page)).toHaveValue('2026-09-30');
    expect(ultimaPrevia(cargas)!.fecha_envio).toBe('2026-09-30');
  });
});

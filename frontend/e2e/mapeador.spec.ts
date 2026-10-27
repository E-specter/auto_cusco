/**
 * MapeadorEncabezados on its own, through the test-only page /pruebas/mapeador
 * (docs/mapeador-encabezados-interfaz.md §8). The case goes in
 * `window.casoMapeador` before the page loads; validation answers through the
 * mapper's fake. Every header, example and field is synthetic.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import { apiVacia, montarApi } from './api-falsa';
import { CAMPOS_SINTETICOS, analisisSintetico, columna, manejarMapeador, type Analisis, type ApiFalsaMapeador } from './api-falsa-mapeador';

test.use({ reducedMotion: 'reduce' });

async function abrir(page: Page, analisis: Analisis): Promise<ApiFalsaMapeador> {
  const mapeador: ApiFalsaMapeador = { analisis, pedidos: [] };
  const api = apiVacia();
  api.manejadores = [manejarMapeador(mapeador)];
  await montarApi(page, api);
  await page.addInitScript((caso) => {
    (window as unknown as { casoMapeador: unknown }).casoMapeador = caso;
  }, { analisis, campos: CAMPOS_SINTETICOS });
  await page.goto('/pruebas/mapeador');
  await expect(page.locator('body')).toHaveAttribute('data-montado', 'true');
  return mapeador;
}

const raiz = (page: Page) => page.locator('#mapeador-prueba');
const fila = (page: Page, indice: number) => raiz(page).locator(`tr[data-fila="${indice}"]`);
const campoDe = (page: Page, indice: number) => fila(page, indice).locator('[role="combobox"]');
/** Opens the row's field list and clicks the field by its technical name ('' is «No cargar esta columna»). */
const opcionDe = (page: Page, indice: number, valor: string) => fila(page, indice).locator(`[role="option"][data-valor="${valor}"]`);
async function elegirCampo(page: Page, indice: number, valor: string): Promise<void> {
  await campoDe(page, indice).click();
  await fila(page, indice).locator(`[role="option"][data-valor="${valor}"]`).click();
}
const estadoListo = (page: Page) => page.locator('[data-estado-prueba]');

const TODO_COINCIDE = analisisSintetico([
  columna(0, 'Pagare', 'coincide', 'pagare'),
  columna(1, 'Titular', 'coincide', 'titular'),
  columna(2, 'Telefono', 'recordado', 'telefono'),
]);

const CON_PARECIDOS = analisisSintetico([
  columna(0, 'Pagare', 'coincide', 'pagare'),
  columna(1, 'Saldo Capital', 'parecido', 'saldo_capital_pendiente', ['1500.50', '82.00']),
  columna(2, 'Nombre cliente', 'parecido', 'titular'),
  columna(3, 'Telefono', 'recordado', 'telefono'),
  columna(4, 'Otra cosa', 'sin_coincidencia', null, []),
]);

test.describe('el caso de todos los días', () => {
  test('todo coincide: aviso de éxito, tabla recogida y se puede confirmar', async ({ page }) => {
    await abrir(page, TODO_COINCIDE);

    await expect(raiz(page).locator('[data-listo]')).toContainText('Las 3 columnas se relacionaron con los campos de carga.');
    await expect(raiz(page).locator('table')).toBeHidden();
    await expect(estadoListo(page)).toHaveText('listo');
    await expect(raiz(page).locator('[data-contexto]')).toHaveText('3 columnas · 3,200 filas · hoja «VENCIDA»');

    const ver = raiz(page).getByRole('button', { name: 'Ver columnas' });
    await ver.click();
    await expect(ver).toHaveAttribute('aria-expanded', 'true');
    await expect(fila(page, 2)).toContainText('Recordado');
    await expect(fila(page, 2)).toContainText('De una carga anterior');
  });
});

test.describe('revisar parecidos', () => {
  test('abre en «Por revisar», con lo que falta, y el parecido dice a qué se parece', async ({ page }) => {
    await abrir(page, CON_PARECIDOS);

    await expect(raiz(page).getByRole('button', { name: 'Por revisar (2)' })).toHaveAttribute('aria-pressed', 'true');
    await expect(fila(page, 0)).toBeHidden();
    await expect(fila(page, 1)).toContainText('Por revisar');
    await expect(fila(page, 1)).toContainText('Parecido a «Saldo de capital pendiente»');
    await expect(estadoListo(page)).toHaveText('no listo');
  });

  test('un parecido se acepta con su botón; elegirlo otra vez en la lista no lo acepta', async ({ page }) => {
    const api = await abrir(page, CON_PARECIDOS);

    await elegirCampo(page, 1, 'dias_atraso');
    await elegirCampo(page, 1, 'saldo_capital_pendiente');
    await expect.poll(() => api.pedidos.at(-1)?.find((a) => a.indice === 1)).toEqual({ indice: 1, campo: 'saldo_capital_pendiente', origen: 'coincide' });
    await expect(fila(page, 1)).toContainText('Por revisar');

    await fila(page, 1).getByRole('button', { name: 'Aceptar Saldo de capital pendiente para la columna B' }).click();
    await expect(fila(page, 1)).toContainText('Aceptado');
    await expect(campoDe(page, 1)).toBeFocused();
    await expect.poll(() => api.pedidos.at(-1)?.find((a) => a.indice === 1)?.origen).toBe('parecido_aceptado');
    // The list does not move under the cursor: the reviewed row stays until the filter changes.
    await expect(fila(page, 1)).toBeVisible();
    await expect(raiz(page).getByRole('button', { name: 'Por revisar (1)' })).toBeVisible();
  });

  test('«Aceptar sugerencias» acepta todos los pendientes y deja confirmar', async ({ page }) => {
    await abrir(page, CON_PARECIDOS);

    await raiz(page).getByRole('button', { name: 'Aceptar sugerencias (2)' }).click();

    await expect(fila(page, 1)).toContainText('Aceptado');
    await expect(fila(page, 2)).toContainText('Aceptado');
    await expect(raiz(page).getByRole('button', { name: /^Aceptar sugerencias/ })).toBeHidden();
    await expect(estadoListo(page)).toHaveText('listo');
  });

  test('otro campo es «Elegido a mano», y volver al original devuelve su estado', async ({ page }) => {
    await abrir(page, CON_PARECIDOS);
    await raiz(page).getByRole('button', { name: /^Todas/ }).click();

    await elegirCampo(page, 3, 'dias_atraso');
    await expect(fila(page, 3)).toContainText('Elegido a mano');
    await elegirCampo(page, 3, 'telefono');
    await expect(fila(page, 3)).toContainText('Recordado');
  });
});

test.describe('un campo en una sola columna', () => {
  test('un campo en uso sale deshabilitado en las demás filas, dice dónde, y su fila lo conserva', async ({ page }) => {
    await abrir(page, CON_PARECIDOS);
    await raiz(page).getByRole('button', { name: /^Todas/ }).click();

    await campoDe(page, 4).click();
    const opcion = opcionDe(page, 4, 'pagare');
    await expect(opcion).toHaveAttribute('aria-disabled', 'true');
    await expect(opcion).toHaveText('Pagaré · en uso en A');
    // Visible and reachable, but Enter and a click do nothing.
    // `force`: Playwright itself will not click an aria-disabled element; the list must ignore it too.
    await opcion.click({ force: true });
    await expect(campoDe(page, 4)).toHaveAttribute('data-valor', '');
    await campoDe(page, 4).press('Escape');

    await campoDe(page, 0).click();
    await expect(opcionDe(page, 0, 'pagare')).not.toHaveAttribute('aria-disabled');
    await expect(campoDe(page, 0)).toHaveAttribute('data-valor', 'pagare');
  });

  test('dos encabezados iguales se distinguen por su columna', async ({ page }) => {
    await abrir(page, analisisSintetico([columna(0, 'Pagare', 'coincide', 'pagare'), columna(1, 'Pagare', 'coincide', 'pagare_duplicado')]));
    await raiz(page).getByRole('button', { name: 'Ver columnas' }).click();

    await expect(campoDe(page, 0)).toHaveAccessibleName('Campo de carga para la columna A, «Pagare»');
    await expect(campoDe(page, 1)).toHaveAccessibleName('Campo de carga para la columna B, «Pagare»');
  });

  test('un repetido que trae el análisis marca las dos filas y se resuelve con «No cargar»', async ({ page }) => {
    await abrir(page, analisisSintetico([
      columna(0, 'Pagare', 'coincide', 'pagare'),
      columna(1, 'Nombre', 'recordado', 'titular'),
      columna(2, 'Titular', 'coincide', 'titular'),
    ]));

    for (const indice of [1, 2]) {
      await expect(fila(page, indice).locator('.field__error')).toHaveText('Titular está asignado a más de una columna: deja una sola.');
      await expect(campoDe(page, indice)).toHaveAttribute('aria-invalid', 'true');
      await campoDe(page, indice).click();
      await expect(opcionDe(page, indice, 'titular')).not.toHaveAttribute('aria-disabled');
      await campoDe(page, indice).press('Escape');
    }

    await elegirCampo(page, 2, '');
    await expect(fila(page, 1).locator('.field__error')).toBeEmpty();
    await expect(estadoListo(page)).toHaveText('listo');
  });
});

test.describe('problemas sin columna', () => {
  test('un obligatorio sin columna va arriba y «Elegir la columna» lleva a una libre', async ({ page }) => {
    await abrir(page, analisisSintetico([columna(0, 'Numero', 'sin_coincidencia', null), columna(1, 'Titular', 'coincide', 'titular')]));

    const resumen = raiz(page).locator('[data-resumen]');
    await expect(resumen).toContainText('Falta asignar una columna al campo obligatorio Pagaré.');
    await resumen.getByRole('button', { name: 'Elegir la columna' }).click();

    await expect(raiz(page).getByRole('button', { name: /^Todas/ })).toHaveAttribute('aria-pressed', 'true');
    await expect(campoDe(page, 0)).toBeFocused();
    await elegirCampo(page, 0, 'pagare');
    await expect(resumen).toBeHidden();
  });
});

test('fijarProblemas (el 422 de confirmar): muestra los problemas en su lugar sin tocar lo elegido', async ({ page }) => {
  await abrir(page, TODO_COINCIDE);
  await expect(estadoListo(page)).toHaveText('listo');

  await page.evaluate(() => {
    const controlador = (window as unknown as { controladorPrueba: { fijarProblemas(p: unknown[]): void } }).controladorPrueba;
    controlador.fijarProblemas([
      { indice: 1, codigo: 'campo_repetido', detalle: 'x', campo: 'titular' },
      { indice: null, codigo: 'obligatorio_sin_columna', detalle: 'x', campo: 'pagare' },
    ]);
  });

  await expect(estadoListo(page)).toHaveText('no listo');
  await expect(raiz(page).locator('table')).toBeVisible();
  await expect(fila(page, 1).locator('.field__error')).toHaveText('Titular está asignado a más de una columna: deja una sola.');
  await expect(raiz(page).locator('[data-resumen]')).toContainText('Falta asignar una columna al campo obligatorio Pagaré.');
  await expect(campoDe(page, 1)).toHaveAttribute('data-valor', 'titular');
  const estado = await page.evaluate(() =>
    (window as unknown as { controladorPrueba: { estado(): { modificado: boolean } } }).controladorPrueba.estado(),
  );
  expect(estado.modificado).toBe(false);
});

test('destruir: deja de validar y de emitir', async ({ page }) => {
  const api = await abrir(page, CON_PARECIDOS);
  await page.evaluate(() => (window as unknown as { controladorPrueba: { destruir(): void } }).controladorPrueba.destruir());
  const antes = api.pedidos.length;

  await elegirCampo(page, 1, 'dias_atraso');
  await page.waitForTimeout(600);

  expect(api.pedidos.length).toBe(antes);
});

test.describe('buscar en la lista de campos (T-MAP-F3, RF-59)', () => {
  const opciones = (page: Page, indice: number) => fila(page, indice).getByRole('option');
  const anuncio = (page: Page) => raiz(page).locator('[data-anuncio-busqueda]');

  test.beforeEach(async ({ page }) => {
    await abrir(page, CON_PARECIDOS);
    await raiz(page).getByRole('button', { name: /^Todas/ }).click();
  });

  test('escribir filtra sin mayúsculas ni tildes, dice cuántos hay y «No cargar» queda siempre', async ({ page }) => {
    await campoDe(page, 4).fill('DIAS');

    await expect(campoDe(page, 4)).toHaveAttribute('aria-expanded', 'true');
    await expect(opciones(page, 4)).toHaveText(['No cargar esta columna', 'Días de atraso']);
    await expect(anuncio(page)).toHaveText('1 campo');

    // Every word, in any order, against the visible and the technical name.
    await campoDe(page, 4).fill('capital saldo');
    await expect(opciones(page, 4)).toHaveText(['No cargar esta columna', 'Saldo de capital pendiente · en uso en B']);

    await campoDe(page, 4).fill('');
    await expect(opciones(page, 4)).toHaveCount(CAMPOS_SINTETICOS.length + 1);
    await expect(anuncio(page)).toHaveText(`${CAMPOS_SINTETICOS.length} campos`);
  });

  test('busca también por los alias del catálogo', async ({ page }) => {
    await campoDe(page, 4).fill('celular');
    await expect(opciones(page, 4)).toHaveText(['No cargar esta columna', 'Teléfono · en uso en D']);

    await campoDe(page, 4).fill('MÓVIL');
    await expect(opciones(page, 4)).toHaveText(['No cargar esta columna', 'Teléfono · en uso en D']);
  });

  test('sin resultados lo dice, y Escape cierra sin cambiar la elección', async ({ page }) => {
    await campoDe(page, 3).fill('zzz');

    await expect(opciones(page, 3)).toHaveText(['No cargar esta columna']);
    await expect(fila(page, 3).locator('.selector-campo__vacio')).toHaveText('No hay campos con «zzz».');
    await expect(anuncio(page)).toHaveText('No hay campos con «zzz».');

    await campoDe(page, 3).press('Escape');

    await expect(campoDe(page, 3)).toHaveAttribute('aria-expanded', 'false');
    await expect(campoDe(page, 3)).toHaveValue('Teléfono');
    await expect(campoDe(page, 3)).toHaveAttribute('data-valor', 'telefono');
    await expect(fila(page, 3)).toContainText('Recordado');
  });

  test('con el teclado: ↓ abre y recorre, la opción activa se señala, y un campo en uso no se elige', async ({ page }) => {
    const campo = campoDe(page, 4);
    await campo.focus();
    await expect(campo).toHaveAttribute('aria-expanded', 'false');

    await campo.press('ArrowDown');
    await expect(campo).toHaveAttribute('aria-expanded', 'true');
    await expect(campo).toHaveAttribute('aria-activedescendant', await opcionDe(page, 4, '').getAttribute('id') ?? '');

    // Pagaré, the only required field, is in use in A: reachable, said, and Enter leaves it alone.
    await campo.press('ArrowDown');
    await expect(campo).toHaveAttribute('aria-activedescendant', await opcionDe(page, 4, 'pagare').getAttribute('id') ?? '');
    await campo.press('Enter');
    await expect(campo).toHaveAttribute('aria-expanded', 'true');
    await expect(campo).toHaveAttribute('data-valor', '');

    await campo.press('ArrowDown');
    await campo.press('Enter');
    await expect(campo).toHaveAttribute('aria-expanded', 'false');
    await expect(campo).toHaveAttribute('data-valor', 'dias_atraso');
    await expect(campo).toBeFocused();
    await expect(fila(page, 4)).toContainText('Elegido a mano');
  });

  test('escribir e Intro elige el primer campo que coincide', async ({ page }) => {
    await campoDe(page, 4).fill('atraso');
    await campoDe(page, 4).press('Enter');

    await expect(campoDe(page, 4)).toHaveAttribute('data-valor', 'dias_atraso');
    await expect(campoDe(page, 4)).toHaveValue('Días de atraso');
  });

  test('Tab cierra la lista sin elegir', async ({ page }) => {
    await campoDe(page, 4).fill('atraso');
    await campoDe(page, 4).press('Tab');

    await expect(fila(page, 4).getByRole('listbox')).toBeHidden();
    await expect(campoDe(page, 4)).toHaveAttribute('data-valor', '');
    await expect(campoDe(page, 4)).toHaveValue('No cargar esta columna');
  });
});

// ---- axe --------------------------------------------------------------------------------

const REGLAS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

async function sinViolaciones(page: Page): Promise<void> {
  const resultado = await new AxeBuilder({ page }).include('[data-ruta-prueba]').withTags(REGLAS).analyze();
  expect(resultado.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
}

for (const tema of ['light', 'dark'] as const) {
  test.describe(`axe, tema ${tema === 'light' ? 'claro' : 'oscuro'}`, () => {
    test.beforeEach(async ({ page }) => {
      await page.addInitScript((elegido) => {
        localStorage.setItem('app:appearance', JSON.stringify({ theme: elegido, language: 'es' }));
      }, tema);
    });

    test('con parecidos por revisar', async ({ page }) => {
      await abrir(page, CON_PARECIDOS);
      await expect(fila(page, 1)).toContainText('Por revisar');
      await sinViolaciones(page);
    });

    test('con un obligatorio sin columna', async ({ page }) => {
      await abrir(page, analisisSintetico([columna(0, 'Numero', 'sin_coincidencia', null), columna(1, 'Titular', 'coincide', 'titular')]));
      await expect(raiz(page).locator('[data-resumen]')).toBeVisible();
      await sinViolaciones(page);
    });

    test('con la tabla recogida', async ({ page }) => {
      await abrir(page, TODO_COINCIDE);
      await expect(raiz(page).locator('[data-listo]')).toBeVisible();
      await sinViolaciones(page);
    });

    for (const ancho of [1440, 930, 360]) {
      test(`con la lista abierta y filtrada, a ${ancho} px`, async ({ page }) => {
        await page.setViewportSize({ width: ancho, height: 900 });
        await abrir(page, CON_PARECIDOS);
        await raiz(page).getByRole('button', { name: /^Todas/ }).click();
        await campoDe(page, 4).fill('a');
        await expect(fila(page, 4).getByRole('listbox')).toBeVisible();
        await sinViolaciones(page);
      });
    }

    test('a 360 px, con parecidos', async ({ page }) => {
      await page.setViewportSize({ width: 360, height: 800 });
      await abrir(page, CON_PARECIDOS);
      await expect(fila(page, 1)).toContainText('Por revisar');
      await sinViolaciones(page);
    });
  });
}

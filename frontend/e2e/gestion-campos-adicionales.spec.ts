/**
 * Managing the additional fields from /cargas (T-CA-F2, docs/campos-adicionales-interfaz.md §4, RF-65): the
 * table, rename, archive and reactivate, and the names the table of incidences shows (RF-66). Against an
 * intercepted API; every name, header and value is synthetic.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import { ARCHIVO_SINTETICO, apiVacia, montarApi, version } from './api-falsa';
import { adicionalFalso, apiAdicionales, manejarAdicionales, type ApiFalsaAdicionales } from './api-falsa-adicionales';
import { conCargaMapeada } from './api-falsa-carga-mapeada';
import { analisisSintetico, columna } from './api-falsa-mapeador';

test.use({ reducedMotion: 'reduce' });

const CAMPOS = [
  adicionalFalso('ad_zona', 'Zona de cobranza'),
  adicionalFalso('ad_monto_en_mora', 'Monto en mora', { tipo: 'numero', encabezado_origen: 'monto_mora' }),
  adicionalFalso('ad_antiguo', 'Campo antiguo', { tipo: 'fecha', archivado: true }),
];

async function abrir(page: Page, adicionales: ApiFalsaAdicionales = apiAdicionales(CAMPOS.map((c) => ({ ...c })))) {
  const api = apiVacia();
  api.versiones = [version({ id: 7 })];
  api.manejadores = [manejarAdicionales(adicionales)];
  await montarApi(page, api);
  await page.goto('/cargas');
  await expect(page.locator('[data-ruler]')).toBeVisible();
  return { api, adicionales };
}

const dialogo = (page: Page) => page.locator('dialog[data-dialog="adicionales"]');
const abrirDialogo = (page: Page) => page.locator('.ruler__rail').getByRole('button', { name: /^Campos adicionales \(/ });
const fila = (page: Page, nombre: string) => dialogo(page).locator(`tr[data-campo="${nombre}"]`);
const estado = (page: Page) => dialogo(page).locator('[data-adicionales-estado]');

async function conDialogo(page: Page, adicionales?: ApiFalsaAdicionales) {
  const contexto = await abrir(page, adicionales);
  await abrirDialogo(page).click();
  await expect(dialogo(page)).toBeVisible();
  return contexto;
}

test.describe('el botón y la tabla', () => {
  test('el botón cuenta todos los campos, archivados incluidos', async ({ page }) => {
    await abrir(page);

    await expect(abrirDialogo(page)).toHaveText('Campos adicionales (3)');
  });

  test('con cero campos el botón sigue y el diálogo dice dónde se crean', async ({ page }) => {
    await abrir(page, apiAdicionales([]));
    await expect(abrirDialogo(page)).toHaveText('Campos adicionales (0)');

    await abrirDialogo(page).click();

    await expect(dialogo(page)).toContainText('Todavía no hay campos adicionales. Se crean al subir una sábana, desde la revisión de columnas.');
    await expect(dialogo(page).locator('table')).toBeHidden();
  });

  test('la tabla trae nombre, tipo, encabezado de origen y estado; los archivados van al final', async ({ page }) => {
    await conDialogo(page);

    await expect(dialogo(page).locator('tbody tr')).toHaveCount(3);
    const nombres = await dialogo(page).locator('tbody tr th').allTextContents();
    expect(nombres.map((n) => n.trim())).toEqual(['Monto en mora', 'Zona de cobranza', 'Campo antiguo']);
    await expect(fila(page, 'ad_monto_en_mora').locator('td').nth(0)).toHaveText('Número');
    await expect(fila(page, 'ad_monto_en_mora').locator('td').nth(1)).toHaveText('monto_mora');
    await expect(fila(page, 'ad_monto_en_mora').locator('td').nth(2)).toHaveText('Activo');
    await expect(fila(page, 'ad_antiguo').locator('.tag')).toHaveText('Archivado');
    await expect(fila(page, 'ad_antiguo').locator('td').nth(0)).toHaveText('Fecha');
  });

  test('sin la lista (API caída) el botón sigue y el diálogo lo dice sin romper la página', async ({ page }) => {
    const adicionales = apiAdicionales(CAMPOS.map((c) => ({ ...c })));
    adicionales.sinLista = true;
    await abrir(page, adicionales);
    await expect(abrirDialogo(page)).toHaveText('Campos adicionales (0)');

    await abrirDialogo(page).click();

    await expect(dialogo(page).locator('[data-adicionales-error]')).toContainText('No se pudieron cargar los campos adicionales.');
  });

  test('al abrir vuelve a leer la lista', async ({ page }) => {
    const { adicionales } = await abrir(page);
    const antes = adicionales.lecturas;

    await abrirDialogo(page).click();

    await expect.poll(() => adicionales.lecturas).toBeGreaterThan(antes);
  });
});

test.describe('la forma del diálogo', () => {
  test('la región de estado vacía no ocupa lugar, pero sigue en la página para anunciar', async ({ page }) => {
    await conDialogo(page);

    await expect(estado(page)).toHaveCount(1);
    await expect(estado(page)).toHaveAttribute('role', 'status');
    const vacia = (await estado(page).boundingBox())!;
    expect(vacia.height).toBeLessThanOrEqual(1);
    // The table starts right under the intro, with no empty strip above it.
    const intro = (await dialogo(page).locator('.dialog__head').boundingBox())!;
    const tabla = (await dialogo(page).locator('[data-adicionales-tabla]').boundingBox())!;
    expect(tabla.y - (intro.y + intro.height)).toBeLessThan(24);

    await fila(page, 'ad_zona').getByRole('button', { name: /^Archivar/ }).click();

    await expect(estado(page)).toContainText('Se archivó');
    expect((await estado(page).boundingBox())!.height).toBeGreaterThan(10);
  });

  test('la nota del nombre en edición queda separada del campo, fuera de su anillo de foco', async ({ page }) => {
    await conDialogo(page);
    await fila(page, 'ad_zona').getByRole('button', { name: /^Renombrar/ }).click();

    const entrada = (await fila(page, 'ad_zona').getByRole('textbox').boundingBox())!;
    const nota = (await fila(page, 'ad_zona').locator('.adicionales__nota').boundingBox())!;

    expect(nota.y - (entrada.y + entrada.height)).toBeGreaterThanOrEqual(6);
  });
});

test.describe('renombrar', () => {
  test('el nombre pasa a un campo con «Guardar» y «Cancelar» en la misma fila, con el foco y la nota', async ({ page }) => {
    await conDialogo(page);

    await fila(page, 'ad_zona').getByRole('button', { name: 'Renombrar «Zona de cobranza»' }).click();

    const entrada = fila(page, 'ad_zona').getByRole('textbox', { name: 'Nuevo nombre de «Zona de cobranza»' });
    await expect(entrada).toHaveValue('Zona de cobranza');
    await expect(entrada).toBeFocused();
    await expect(entrada).toHaveAttribute('maxlength', '80');
    await expect(fila(page, 'ad_zona')).toContainText('Lo que ya lo usa sigue funcionando: se guarda por su nombre interno, que no cambia.');
    await expect(fila(page, 'ad_zona').getByRole('button', { name: 'Guardar' })).toBeDisabled();
    await expect(fila(page, 'ad_zona').getByRole('button', { name: 'Cancelar' })).toBeVisible();
  });

  test('guarda un nombre nuevo, lo anuncia y devuelve el foco a «Renombrar»', async ({ page }) => {
    const { adicionales } = await conDialogo(page);
    await fila(page, 'ad_zona').getByRole('button', { name: /^Renombrar/ }).click();
    const entrada = fila(page, 'ad_zona').getByRole('textbox');

    await entrada.fill('  Zona comercial ');
    await fila(page, 'ad_zona').getByRole('button', { name: 'Guardar' }).click();

    await expect.poll(() => adicionales.cambios).toEqual([{ nombre: 'ad_zona', cuerpo: { nombre_legible: 'Zona comercial' } }]);
    await expect(estado(page)).toHaveText('Se renombró «Zona de cobranza» a «Zona comercial».');
    await expect(fila(page, 'ad_zona').locator('th')).toHaveText('Zona comercial');
    await expect(fila(page, 'ad_zona').getByRole('button', { name: 'Renombrar «Zona comercial»' })).toBeFocused();
  });

  test('Enter guarda y no envía nada más', async ({ page }) => {
    const { adicionales } = await conDialogo(page);
    await fila(page, 'ad_zona').getByRole('button', { name: /^Renombrar/ }).click();

    await fila(page, 'ad_zona').getByRole('textbox').fill('Zona norte');
    await fila(page, 'ad_zona').getByRole('textbox').press('Enter');

    await expect.poll(() => adicionales.cambios.length).toBe(1);
    await expect(dialogo(page)).toBeVisible();
  });

  test('si la lista llega con un cambio mientras se escribe, el campo conserva el foco y lo escrito', async ({ page }) => {
    const { adicionales } = await abrir(page);
    adicionales.campos.push(adicionalFalso('ad_nuevo', 'Campo nuevo'));
    let liberar!: () => void;
    const espera = new Promise<void>((resolver) => (liberar = resolver));
    await page.route('**/api/mapeador/sabana_vencida/campos-adicionales', async (route) => {
      if (route.request().method() === 'GET') await espera;
      await route.fallback();
    });
    await abrirDialogo(page).click();
    await fila(page, 'ad_zona').getByRole('button', { name: /^Renombrar/ }).click();
    const entrada = fila(page, 'ad_zona').getByRole('textbox');
    await entrada.fill('Zona nueva');

    liberar();

    await expect(fila(page, 'ad_nuevo')).toBeVisible();
    await expect(fila(page, 'ad_zona').getByRole('textbox')).toBeFocused();
    await expect(fila(page, 'ad_zona').getByRole('textbox')).toHaveValue('Zona nueva');
  });

  test('«Guardar» espera un nombre distinto y no vacío', async ({ page }) => {
    await conDialogo(page);
    await fila(page, 'ad_zona').getByRole('button', { name: /^Renombrar/ }).click();
    const guardar = fila(page, 'ad_zona').getByRole('button', { name: 'Guardar' });

    await fila(page, 'ad_zona').getByRole('textbox').fill('   ');
    await expect(guardar).toBeDisabled();
    await fila(page, 'ad_zona').getByRole('textbox').fill('Zona de cobranza');
    await expect(guardar).toBeDisabled();
    await fila(page, 'ad_zona').getByRole('textbox').fill('Zona de cobranza norte');
    await expect(guardar).toBeEnabled();
  });

  test('«Cancelar» deja el nombre como estaba y Escape cancela la edición sin cerrar el diálogo', async ({ page }) => {
    const { adicionales } = await conDialogo(page);
    await fila(page, 'ad_zona').getByRole('button', { name: /^Renombrar/ }).click();
    await fila(page, 'ad_zona').getByRole('textbox').fill('Otro nombre');

    await fila(page, 'ad_zona').getByRole('button', { name: 'Cancelar' }).click();

    await expect(fila(page, 'ad_zona').locator('th')).toHaveText('Zona de cobranza');
    await expect(fila(page, 'ad_zona').getByRole('button', { name: /^Renombrar/ })).toBeFocused();

    await fila(page, 'ad_zona').getByRole('button', { name: /^Renombrar/ }).click();
    await fila(page, 'ad_zona').getByRole('textbox').press('Escape');

    await expect(dialogo(page)).toBeVisible();
    await expect(fila(page, 'ad_zona').getByRole('textbox')).toHaveCount(0);
    expect(adicionales.cambios).toEqual([]);
  });

  test('un nombre repetido lo dice bajo el nombre, conserva lo escrito y deja el foco ahí', async ({ page }) => {
    await conDialogo(page);
    await fila(page, 'ad_zona').getByRole('button', { name: /^Renombrar/ }).click();
    const entrada = fila(page, 'ad_zona').getByRole('textbox');

    await entrada.fill('monto EN mora');
    await fila(page, 'ad_zona').getByRole('button', { name: 'Guardar' }).click();

    await expect(fila(page, 'ad_zona').locator('[data-nombre-error]')).toHaveText('Ya existe el campo «Monto en mora». Usa otro nombre.');
    await expect(entrada).toHaveValue('monto EN mora');
    await expect(entrada).toHaveAttribute('aria-invalid', 'true');
    await expect(entrada).toBeFocused();
    expect(await entrada.getAttribute('aria-describedby')).toContain('-error');
  });

  test('un nombre que tiene un campo archivado lo dice, y manda a reactivarlo', async ({ page }) => {
    await conDialogo(page);
    await fila(page, 'ad_zona').getByRole('button', { name: /^Renombrar/ }).click();

    await fila(page, 'ad_zona').getByRole('textbox').fill('Campo antiguo');
    await fila(page, 'ad_zona').getByRole('button', { name: 'Guardar' }).click();

    await expect(fila(page, 'ad_zona').locator('[data-nombre-error]')).toHaveText('Ya existe el campo archivado «Campo antiguo». Reactívalo o usa otro nombre.');
  });

  test('un 422 se reconoce por el estado y escribir de nuevo quita el error', async ({ page }) => {
    const adicionales = apiAdicionales(CAMPOS.map((c) => ({ ...c })));
    adicionales.rechazos = [{ estado: 422, cuerpo: { detail: [{ type: 'string_too_long' }] } }];
    await conDialogo(page, adicionales);
    await fila(page, 'ad_zona').getByRole('button', { name: /^Renombrar/ }).click();
    await fila(page, 'ad_zona').getByRole('textbox').fill('Zona nueva');
    await fila(page, 'ad_zona').getByRole('button', { name: 'Guardar' }).click();

    await expect(fila(page, 'ad_zona').locator('[data-nombre-error]')).toHaveText('Escribe un nombre de hasta 80 caracteres.');

    await fila(page, 'ad_zona').getByRole('textbox').fill('Zona nueva 2');

    await expect(fila(page, 'ad_zona').locator('[data-nombre-error]')).toHaveText('');
  });

  test('un campo que ya no existe lo dice, termina la edición y vuelve a leer la lista', async ({ page }) => {
    const adicionales = apiAdicionales(CAMPOS.map((c) => ({ ...c })));
    adicionales.rechazos = [{ estado: 404, cuerpo: { detail: 'No existe', codigo: 'campo_adicional_no_encontrado' } }];
    await conDialogo(page, adicionales);
    const antes = adicionales.lecturas;
    await fila(page, 'ad_zona').getByRole('button', { name: /^Renombrar/ }).click();
    await fila(page, 'ad_zona').getByRole('textbox').fill('Zona nueva');

    await fila(page, 'ad_zona').getByRole('button', { name: 'Guardar' }).click();

    await expect(dialogo(page).locator('[data-adicionales-error]')).toHaveText('El campo adicional no existe.');
    await expect(fila(page, 'ad_zona').getByRole('textbox')).toHaveCount(0);
    await expect.poll(() => adicionales.lecturas).toBeGreaterThan(antes);
  });
});

test.describe('archivar y reactivar', () => {
  test('archivar no pide confirmar, lo anuncia, lo manda al final con su tag y deja el foco en «Reactivar»', async ({ page }) => {
    const { adicionales } = await conDialogo(page);

    await fila(page, 'ad_monto_en_mora').getByRole('button', { name: 'Archivar «Monto en mora»' }).click();

    await expect.poll(() => adicionales.cambios).toEqual([{ nombre: 'ad_monto_en_mora', cuerpo: { archivado: true } }]);
    await expect(estado(page)).toHaveText('Se archivó «Monto en mora». Deja de ofrecerse, y las sábanas que cargues desde ahora no lo traen.');
    await expect(fila(page, 'ad_monto_en_mora').locator('.tag')).toHaveText('Archivado');
    const nombres = await dialogo(page).locator('tbody tr th').allTextContents();
    expect(nombres.map((n) => n.trim())).toEqual(['Zona de cobranza', 'Campo antiguo', 'Monto en mora']);
    await expect(fila(page, 'ad_monto_en_mora').getByRole('button', { name: 'Reactivar «Monto en mora»' })).toBeFocused();
    await expect(abrirDialogo(page)).toHaveText('Campos adicionales (3)');
  });

  test('reactivar lo anuncia, lo vuelve a poner entre los activos y deja el foco en «Archivar»', async ({ page }) => {
    const { adicionales } = await conDialogo(page);

    await fila(page, 'ad_antiguo').getByRole('button', { name: 'Reactivar «Campo antiguo»' }).click();

    await expect.poll(() => adicionales.cambios).toEqual([{ nombre: 'ad_antiguo', cuerpo: { archivado: false } }]);
    await expect(estado(page)).toHaveText('Se reactivó «Campo antiguo».');
    await expect(fila(page, 'ad_antiguo').locator('.tag')).toHaveCount(0);
    await expect(fila(page, 'ad_antiguo').getByRole('button', { name: 'Archivar «Campo antiguo»' })).toBeFocused();
    const nombres = await dialogo(page).locator('tbody tr th').allTextContents();
    expect(nombres.map((n) => n.trim())).toEqual(['Campo antiguo', 'Monto en mora', 'Zona de cobranza']);
  });

  test('un rechazo al archivar lo dice y deja la fila como estaba', async ({ page }) => {
    const adicionales = apiAdicionales(CAMPOS.map((c) => ({ ...c })));
    adicionales.rechazos = [{ estado: 500, cuerpo: { detail: 'fallo interno' } }];
    await conDialogo(page, adicionales);

    await fila(page, 'ad_zona').getByRole('button', { name: /^Archivar/ }).click();

    await expect(dialogo(page).locator('[data-adicionales-error]')).not.toHaveText('');
    await expect(fila(page, 'ad_zona').locator('.tag')).toHaveCount(0);
  });
});

test.describe('crear un campo desde la carga', () => {
  test('el botón de gestión cuenta el campo nuevo apenas se crea', async ({ page }) => {
    const adicionales = apiAdicionales(CAMPOS.map((c) => ({ ...c })));
    const api = apiVacia();
    api.versiones = [version({ id: 7 })];
    api.manejadores = [manejarAdicionales(adicionales)];
    conCargaMapeada(api, {
      analisis: analisisSintetico([columna(0, 'Pagare', 'coincide', 'pagare'), columna(1, 'Monto en mora', 'sin_coincidencia', null, ['1500.50'])]),
    });
    await montarApi(page, api);
    await page.goto('/cargas');
    await expect(abrirDialogo(page)).toHaveText('Campos adicionales (3)');
    await page.getByRole('button', { name: 'Subir sábana' }).click();
    await page.locator('#upload-file').setInputFiles(ARCHIVO_SINTETICO);
    await page.getByRole('button', { name: 'Continuar' }).click();
    await page.getByRole('button', { name: 'Crear un campo adicional' }).click();
    await page.getByRole('radio', { name: 'Número' }).check();
    // The backend now has it: the page reads the list again after creating.
    adicionales.campos.push(adicionalFalso('ad_monto_en_mora_2', 'Monto en mora 2'));

    await page.getByRole('button', { name: 'Crear campo' }).click();

    await expect(abrirDialogo(page)).toHaveText('Campos adicionales (4)');
  });
});

test.describe('los nombres en la tabla de incidencias (RF-66)', () => {
  const incidencia = (codigo: string, columna: string | null) => ({
    fila: 12,
    columna,
    codigo,
    severidad: 'advertencia' as const,
    detalle: 'detalle',
    valor_original: 'x',
  });

  async function conIncidencias(page: Page, adicionales = apiAdicionales(CAMPOS.map((c) => ({ ...c })))) {
    const api = apiVacia();
    api.versiones = [version({ id: 7 })];
    api.incidencias = [
      incidencia('valor_no_convertible', 'ad_monto_en_mora'),
      incidencia('valor_no_convertible', 'ad_antiguo'),
      incidencia('columnas_opcionales_ausentes', 'telefono, titular, ad_zona'),
      incidencia('columna_faltante', 'bpo'),
    ];
    api.manejadores = [manejarAdicionales(adicionales)];
    await montarApi(page, api);
    await page.goto('/cargas');
    await expect(page.locator('.incidencia__column').first()).toBeVisible();
    return adicionales;
  }

  const columnas = (page: Page) => page.locator('.incidencia__column');

  test('un adicional se muestra por su nombre legible, también uno archivado', async ({ page }) => {
    await conIncidencias(page);

    await expect(columnas(page).nth(0)).toHaveText('Monto en mora');
    await expect(columnas(page).nth(1)).toHaveText('Campo antiguo');
  });

  test('una lista de columnas opcionales se separa por «, » y cada nombre sale traducido', async ({ page }) => {
    await conIncidencias(page);

    await expect(columnas(page).nth(2)).toHaveText('Teléfono, Titular, Zona de cobranza');
  });

  test('otro código conserva el encabezado del archivo tal cual', async ({ page }) => {
    await conIncidencias(page);

    await expect(columnas(page).nth(3)).toHaveText('bpo');
  });

  test('sin la lista de adicionales las incidencias se leen igual, con el nombre del catálogo base', async ({ page }) => {
    const adicionales = apiAdicionales(CAMPOS.map((c) => ({ ...c })));
    adicionales.sinLista = true;
    await conIncidencias(page, adicionales);

    await expect(columnas(page).nth(2)).toContainText('Teléfono, Titular');
  });

  test('renombrar un campo cambia el nombre que muestra la tabla de incidencias', async ({ page }) => {
    await conIncidencias(page);
    await abrirDialogo(page).click();
    await fila(page, 'ad_monto_en_mora').getByRole('button', { name: /^Renombrar/ }).click();
    await fila(page, 'ad_monto_en_mora').getByRole('textbox').fill('Monto vencido');
    await fila(page, 'ad_monto_en_mora').getByRole('button', { name: 'Guardar' }).click();
    await expect(estado(page)).toContainText('Se renombró');

    await expect(columnas(page).nth(0)).toHaveText('Monto vencido');
  });
});

// ---- axe ------------------------------------------------------------------------------------

const REGLAS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

async function sinViolaciones(page: Page): Promise<void> {
  const resultado = await new AxeBuilder({ page }).withTags(REGLAS).analyze();
  expect(resultado.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
}

for (const tema of ['light', 'dark'] as const) {
  test.describe(`axe de la gestión, tema ${tema === 'light' ? 'claro' : 'oscuro'}`, () => {
    test.beforeEach(async ({ page }) => {
      await page.addInitScript((elegido) => {
        localStorage.setItem('app:appearance', JSON.stringify({ theme: elegido, language: 'es' }));
      }, tema);
    });

    test('la tabla con un archivado', async ({ page }) => {
      await conDialogo(page);
      await expect(dialogo(page).locator('tbody tr')).toHaveCount(3);
      await sinViolaciones(page);
    });

    test('con un nombre en edición y su error', async ({ page }) => {
      await conDialogo(page);
      await fila(page, 'ad_zona').getByRole('button', { name: /^Renombrar/ }).click();
      await fila(page, 'ad_zona').getByRole('textbox').fill('Monto en mora');
      await fila(page, 'ad_zona').getByRole('button', { name: 'Guardar' }).click();
      await expect(fila(page, 'ad_zona').locator('[data-nombre-error]')).toContainText('Ya existe');
      await sinViolaciones(page);
    });

    test('sin campos', async ({ page }) => {
      await conDialogo(page, apiAdicionales([]));
      await sinViolaciones(page);
    });
  });
}

test('la gestión a 360 px cabe, y sus acciones se alcanzan', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await conDialogo(page);

  const desborde = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(desborde).toBeLessThanOrEqual(0);
  await fila(page, 'ad_zona').getByRole('button', { name: /^Archivar/ }).scrollIntoViewIfNeeded();
  await expect(fila(page, 'ad_zona').getByRole('button', { name: /^Archivar/ })).toBeInViewport();
  await sinViolaciones(page);
});

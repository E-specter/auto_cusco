/**
 * The upload dialog of /cargas in two steps (T-MAP-F2): pick the file, then review how its columns relate to
 * the load's fields. Against an intercepted API; the header mapper itself is covered in mapeador.spec.ts.
 * Every file, header and field is synthetic.
 */
import { expect, test, type Page } from '@playwright/test';

import { ARCHIVO_SINTETICO, apiVacia, montarApi, version } from './api-falsa';
import {
  ANALISIS_TODO_COINCIDE,
  codigoDeRechazo,
  conCargaMapeada,
  type ApiFalsaCargaMapeada,
} from './api-falsa-carga-mapeada';
import { analisisSintetico, columna, type Analisis } from './api-falsa-mapeador';

test.use({ reducedMotion: 'reduce' });

const CSV_SINTETICO = { name: 'SABANA_10.09.2026.csv', mimeType: 'text/csv', buffer: Buffer.from('pagare;titular\nX1;Y1\n') };

const dialogo = (page: Page) => page.locator('dialog[data-dialog="upload"]');
const pasoActual = (page: Page) => dialogo(page).locator('[data-paso-marca][aria-current="step"]');
const continuar = (page: Page) => dialogo(page).getByRole('button', { name: 'Continuar' });
const confirmar = (page: Page) => dialogo(page).getByRole('button', { name: 'Confirmar y cargar' });
const fila = (page: Page, indice: number) => dialogo(page).locator(`tr[data-fila="${indice}"]`);
const campoDe = (page: Page, indice: number) => fila(page, indice).locator('[role="combobox"]');
/** Opens the row's field list and clicks the field by its technical name ('' is «No cargar esta columna»). */
async function elegirCampo(page: Page, indice: number, valor: string): Promise<void> {
  await campoDe(page, indice).click();
  await fila(page, indice).locator(`[role="option"][data-valor="${valor}"]`).click();
}
const opcion = (page: Page, cual: 'hoja' | 'separador' | 'codificacion') => dialogo(page).locator(`[data-opcion-select="${cual}"]`);
const errorDeOpcion = (page: Page, cual: 'hoja' | 'separador' | 'codificacion') => dialogo(page).locator(`[data-opcion-error="${cual}"]`);
const motivo = (page: Page) => dialogo(page).locator('[data-motivo]');

const VARIAS_HOJAS = analisisSintetico(
  [columna(0, 'Pagare', 'coincide', 'pagare'), columna(1, 'Titular', 'coincide', 'titular')],
  { hojas: ['VENCIDA', 'MORA'], hoja: 'VENCIDA', detectados: ['hoja'] },
);
const CON_PARECIDOS = analisisSintetico([
  columna(0, 'Pagare', 'coincide', 'pagare'),
  columna(1, 'Saldo Capital', 'parecido', 'saldo_capital_pendiente'),
  columna(2, 'Nombre cliente', 'parecido', 'titular'),
]);
const CSV = analisisSintetico(
  [columna(0, 'Pagare', 'coincide', 'pagare'), columna(1, 'Titular', 'coincide', 'titular')],
  { formato: 'csv', hojas: ['datos'], hoja: 'datos', separador: ';', codificacion: 'utf-8', detectados: ['separador', 'codificacion'] },
);

/** Opens the dialog on /cargas (nothing loaded yet) and, unless told otherwise, hands the file to step 1. */
async function abrir(page: Page, analisis: Analisis = ANALISIS_TODO_COINCIDE, parcial: Partial<ApiFalsaCargaMapeada> = {}) {
  const api = apiVacia();
  const carga = conCargaMapeada(api, { analisis, ...parcial });
  await montarApi(page, api);
  await page.goto('/cargas');
  await page.getByRole('button', { name: 'Subir sábana' }).click();
  return { api, carga };
}

async function alPaso2(page: Page, archivo: typeof ARCHIVO_SINTETICO | typeof CSV_SINTETICO = ARCHIVO_SINTETICO) {
  await page.locator('#upload-file').setInputFiles(archivo);
  await continuar(page).click();
  await expect(pasoActual(page)).toHaveAttribute('data-paso-marca', '2');
}

test.describe('los dos pasos', () => {
  test('el paso 1 pide archivo y fecha; el 2 revisa las columnas, y el paso en curso lo dice el marcador', async ({ page }) => {
    await abrir(page);

    await expect(pasoActual(page)).toHaveText('1. Elegir archivo');
    await expect(page.locator('#upload-file')).toHaveAttribute('accept', '.xlsx,.xlsb,.xls,.ods,.csv,.tsv,.txt,.json');
    await expect(dialogo(page).getByText('Excel (.xlsx, .xlsb, .xls, .ods), CSV o JSON, hasta 64 MB.')).toBeVisible();
    await expect(dialogo(page).getByLabel('Hoja')).toBeHidden();
    await expect(confirmar(page)).toBeHidden();

    await alPaso2(page);

    await expect(pasoActual(page)).toHaveText('2. Revisar columnas');
    await expect(dialogo(page).locator('[data-mapeo-resumen]')).toContainText('SABANA_10.09.2026.xlsx');
    await expect(dialogo(page).locator('#mapeador')).toBeVisible();
    await expect(continuar(page)).toBeHidden();
    await expect(confirmar(page)).toBeEnabled();
    await expect(motivo(page)).toHaveText('');
  });

  test('confirmar manda las asignaciones tal como las armó el componente, con la fecha de corte', async ({ page }) => {
    const { api, carga } = await abrir(page);
    api.respuestasSubida = [
      { estado: 202, cuerpo: { id: 7, fecha_corte: '2026-09-10', version: 1, estado: 'en_cola', versiones_identicas: [], aviso: null } },
    ];
    const terminada = version({ id: 7 });
    api.seguimiento = [terminada];
    await alPaso2(page);

    api.versiones = [terminada];
    await confirmar(page).click();

    await expect(dialogo(page)).toBeHidden();
    expect(carga.confirmaciones).toEqual([
      {
        borrador_id: 7,
        fecha_corte: '2026-09-10',
        asignaciones: [
          { indice: 0, campo: 'pagare', origen: 'coincide' },
          { indice: 1, campo: 'titular', origen: 'coincide' },
          { indice: 2, campo: 'telefono', origen: 'recordado' },
        ],
      },
    ]);
    // The draft went into the load: nothing left to delete.
    expect(carga.descartados).toEqual([]);
  });

  test('el archivo se manda al borrador sin hoja, separador ni codificación: lo detecta el lector', async ({ page }) => {
    const { carga } = await abrir(page);
    await alPaso2(page);

    expect(carga.borradoresCreados).toHaveLength(1);
    expect(carga.borradoresCreados[0]).toContain('name="archivo"');
    expect(carga.borradoresCreados[0]).not.toMatch(/name="(hoja|separador|codificacion)"/);
  });
});

test.describe('confirmar solo con el mapeo listo', () => {
  test('con columnas por revisar queda apagado y dice cuántas; al aceptarlas se enciende', async ({ page }) => {
    await abrir(page, CON_PARECIDOS);
    await alPaso2(page);

    await expect(confirmar(page)).toBeDisabled();
    await expect(motivo(page)).toHaveText('Revisa 2 columnas para poder cargar.');
    await expect(confirmar(page)).toHaveAttribute('aria-describedby', 'mapeo-motivo');

    await dialogo(page).getByRole('button', { name: 'Aceptar sugerencias (2)' }).click();

    await expect(confirmar(page)).toBeEnabled();
    await expect(motivo(page)).toHaveText('');
  });

  test('sin el campo obligatorio dice cuál falta, por su nombre visible', async ({ page }) => {
    await abrir(page, analisisSintetico([columna(0, 'Titular', 'coincide', 'titular')]));
    await alPaso2(page);

    await expect(confirmar(page)).toBeDisabled();
    await expect(motivo(page)).toHaveText('Falta asignar el campo obligatorio Pagaré.');
  });
});

test.describe('cómo se lee el archivo', () => {
  test('un CSV deja elegir separador y codificación, y marca lo que detectó el lector', async ({ page }) => {
    const { carga } = await abrir(page, CSV, {
      analisisPara: (opciones) => ({ ...CSV, separador: opciones.separador ?? ';', codificacion: opciones.codificacion ?? 'utf-8', detectados: [] }),
    });
    await alPaso2(page, CSV_SINTETICO);

    await expect(opcion(page, 'hoja')).toBeHidden();
    await expect(opcion(page, 'separador').locator('option')).toHaveText(['Punto y coma (detectado)', 'Tabulación', 'Coma']);
    await expect(opcion(page, 'separador')).toHaveValue(';');
    await expect(opcion(page, 'codificacion').locator('option')).toHaveText(['utf-8 (detectada)', 'latin-1', 'cp1252']);

    await opcion(page, 'separador').selectOption({ value: '\t' });

    await expect.poll(() => carga.reanalisis).toEqual([{ separador: '\t' }]);
    await expect(opcion(page, 'separador')).toHaveValue('\t');
    // Chosen by the analyst now, not detected: the mark goes.
    await expect(opcion(page, 'separador').locator('option:checked')).toHaveText('Tabulación');

    await opcion(page, 'codificacion').selectOption('latin-1');

    // What was chosen stays chosen when the next option re-reads the file.
    await expect.poll(() => carga.reanalisis.at(-1)).toEqual({ separador: '\t', codificacion: 'latin-1' });
  });

  test('un Excel con varias hojas deja elegir la hoja; con una sola no hay lista', async ({ page }) => {
    const { carga } = await abrir(page, VARIAS_HOJAS, {
      analisisPara: (opciones) => ({ ...VARIAS_HOJAS, hoja: opciones.hoja ?? 'VENCIDA', detectados: [] }),
    });
    await alPaso2(page);

    await expect(opcion(page, 'hoja').locator('option')).toHaveText(['VENCIDA (detectado)', 'MORA']);
    await expect(opcion(page, 'separador')).toBeHidden();
    await expect(opcion(page, 'codificacion')).toBeHidden();

    await opcion(page, 'hoja').selectOption('MORA');

    await expect.poll(() => carga.reanalisis).toEqual([{ hoja: 'MORA' }]);
    await expect(opcion(page, 'hoja')).toHaveValue('MORA');
  });

  test('un Excel de una hoja no muestra ninguna opción de lectura', async ({ page }) => {
    await abrir(page);
    await alPaso2(page);

    await expect(dialogo(page).locator('[data-opcion-select]:visible')).toHaveCount(0);
  });

  test('si ya se eligió algo en las columnas, cambiar la lectura pregunta antes; «Mantener» no vuelve a leer', async ({ page }) => {
    const { carga } = await abrir(page, VARIAS_HOJAS, { analisisPara: (opciones) => ({ ...VARIAS_HOJAS, hoja: opciones.hoja ?? 'VENCIDA' }) });
    await alPaso2(page);
    await dialogo(page).getByRole('button', { name: 'Ver columnas' }).click();
    await elegirCampo(page, 1, 'dias_atraso');

    await opcion(page, 'hoja').selectOption('MORA');

    const aviso = dialogo(page).locator('[data-reanalizar]');
    await expect(aviso).toBeVisible();
    await expect(aviso).toContainText('Cambiar la hoja vuelve a leer el archivo y descarta lo que elegiste en las columnas.');
    expect(carga.reanalisis).toEqual([]);

    await aviso.getByRole('button', { name: 'Mantener lo elegido' }).click();

    await expect(aviso).toBeHidden();
    await expect(opcion(page, 'hoja')).toHaveValue('VENCIDA');
    await expect(campoDe(page, 1)).toHaveAttribute('data-valor', 'dias_atraso');
    expect(carga.reanalisis).toEqual([]);
  });

  test('«Volver a leer» lee de nuevo con la hoja elegida y descarta lo hecho en las columnas', async ({ page }) => {
    const { carga } = await abrir(page, VARIAS_HOJAS, { analisisPara: (opciones) => ({ ...VARIAS_HOJAS, hoja: opciones.hoja ?? 'VENCIDA' }) });
    await alPaso2(page);
    await dialogo(page).getByRole('button', { name: 'Ver columnas' }).click();
    await elegirCampo(page, 1, 'dias_atraso');

    await opcion(page, 'hoja').selectOption('MORA');
    await dialogo(page).getByRole('button', { name: 'Volver a leer' }).click();

    await expect.poll(() => carga.reanalisis).toEqual([{ hoja: 'MORA' }]);
    await expect(dialogo(page).locator('[data-reanalizar]')).toBeHidden();
    await expect(opcion(page, 'hoja')).toHaveValue('MORA');
    await expect(campoDe(page, 1)).toHaveAttribute('data-valor', 'titular');
  });
});

test.describe('lo que el lector rechaza, por su código', () => {
  const EN_EL_PASO_1: Array<[string, ReturnType<typeof codigoDeRechazo>, string]> = [
    ['archivo_vacio', codigoDeRechazo(400, 'archivo_vacio'), 'El archivo está vacío.'],
    ['archivo_ilegible', codigoDeRechazo(400, 'archivo_ilegible'), 'No se pudo leer el archivo: está dañado o no es de un formato admitido.'],
    ['extension_no_coincide', codigoDeRechazo(400, 'extension_no_coincide'), 'La extensión del archivo no coincide con su contenido. Revisa que sea el archivo correcto.'],
    ['archivo_sin_datos', codigoDeRechazo(400, 'archivo_sin_datos'), 'El archivo no tiene encabezados ni datos.'],
    ['archivo_demasiado_grande', codigoDeRechazo(413, 'archivo_demasiado_grande', { maximo_mb: 64 }), 'El archivo supera el máximo de 64 MB.'],
    ['catalogo_desconocido', codigoDeRechazo(404, 'catalogo_desconocido'), 'El catálogo de campos no existe.'],
  ];

  for (const [codigo, rechazo, texto] of EN_EL_PASO_1) {
    test(`${codigo}: se queda en el paso 1, bajo el archivo, con el texto de la interfaz`, async ({ page }) => {
      await abrir(page, ANALISIS_TODO_COINCIDE, { erroresBorrador: [rechazo] });

      await page.locator('#upload-file').setInputFiles(ARCHIVO_SINTETICO);
      await continuar(page).click();

      await expect(dialogo(page).locator('[data-error-for="archivo"]')).toHaveText(texto);
      await expect(pasoActual(page)).toHaveAttribute('data-paso-marca', '1');
      await expect(confirmar(page)).toBeHidden();
      await expect(continuar(page)).toBeEnabled();
    });
  }

  test('sin red lo dice una vez y no entra al paso 2', async ({ page }) => {
    const { api } = await abrir(page);
    await page.route('**/api/mapeador/**', (route) => route.abort('failed'));
    void api;

    await page.locator('#upload-file').setInputFiles(ARCHIVO_SINTETICO);
    await continuar(page).click();

    await expect(dialogo(page).locator('[data-upload-error]')).toHaveText('No se pudo contactar con la API. Comprueba que el backend esté en marcha.');
    await expect(pasoActual(page)).toHaveAttribute('data-paso-marca', '1');
  });

  test('una hoja que no existe se dice bajo la lista de hojas, que ofrece las del archivo', async ({ page }) => {
    await abrir(page, VARIAS_HOJAS, {
      erroresAnalisis: [codigoDeRechazo(400, 'hoja_inexistente', { hoja: 'ANTIGUA', hojas: ['VENCIDA', 'MORA', 'ARCHIVO'] })],
    });
    await alPaso2(page);

    await opcion(page, 'hoja').selectOption('MORA');

    await expect(errorDeOpcion(page, 'hoja')).toHaveText('La hoja «ANTIGUA» no está en el archivo. Elige una de la lista.');
    // The sheets the refusal offers are the file's own, whatever the select held.
    await expect(opcion(page, 'hoja').locator('option')).toHaveText(['VENCIDA (detectado)', 'MORA', 'ARCHIVO']);
    await expect(opcion(page, 'hoja')).toHaveValue('VENCIDA');
    await expect(pasoActual(page)).toHaveAttribute('data-paso-marca', '2');
  });

  test('un separador o una codificación rechazados se dicen bajo su lista y se queda en el paso 2', async ({ page }) => {
    await abrir(page, CSV, {
      erroresAnalisis: [codigoDeRechazo(400, 'separador_invalido'), codigoDeRechazo(400, 'codificacion_no_coincide')],
    });
    await alPaso2(page, CSV_SINTETICO);

    await opcion(page, 'separador').selectOption(',');
    await expect(errorDeOpcion(page, 'separador')).toHaveText('El separador debe ser un solo carácter.');
    await expect(opcion(page, 'separador')).toHaveValue(';');

    await opcion(page, 'codificacion').selectOption('cp1252');
    await expect(errorDeOpcion(page, 'codificacion')).toHaveText('El archivo no se puede leer con esa codificación. Prueba con otra.');
    await expect(opcion(page, 'codificacion')).toHaveValue('utf-8');
    await expect(pasoActual(page)).toHaveAttribute('data-paso-marca', '2');
  });
});

test.describe('al confirmar', () => {
  test('un 422 deja en el paso 2 con lo elegido intacto y los problemas sobre sus filas', async ({ page }) => {
    const { carga } = await abrir(page, ANALISIS_TODO_COINCIDE, {
      respuestasConfirmar: [
        {
          estado: 422,
          cuerpo: {
            detail: 'Hay columnas por revisar',
            codigo: 'mapeo_con_problemas',
            problemas: [{ indice: 1, codigo: 'campo_repetido', detalle: 'Campo repetido', campo: 'dias_atraso' }],
          },
        },
      ],
    });
    await alPaso2(page);
    await dialogo(page).getByRole('button', { name: 'Ver columnas' }).click();
    await elegirCampo(page, 1, 'dias_atraso');

    await confirmar(page).click();

    await expect.poll(() => carga.confirmaciones).toHaveLength(1);
    await expect(dialogo(page)).toBeVisible();
    await expect(pasoActual(page)).toHaveAttribute('data-paso-marca', '2');
    await expect(campoDe(page, 1)).toHaveAttribute('data-valor', 'dias_atraso');
    await expect(confirmar(page)).toBeDisabled();
    await expect(motivo(page)).not.toHaveText('');
    expect(carga.descartados).toEqual([]);
  });

  test('un 404 vuelve al paso 1 con el texto de la interfaz', async ({ page }) => {
    await abrir(page, ANALISIS_TODO_COINCIDE, { respuestasConfirmar: [codigoDeRechazo(404, 'borrador_no_encontrado')] });
    await alPaso2(page);

    await confirmar(page).click();

    await expect(pasoActual(page)).toHaveAttribute('data-paso-marca', '1');
    await expect(dialogo(page).locator('[data-upload-error]')).toHaveText('La carga en curso venció, ya se confirmó o no existe. Vuelve a elegir el archivo.');
    await expect(dialogo(page)).toBeVisible();
  });

  test('un borrador que ya no existe al validar también vuelve al paso 1', async ({ page }) => {
    await abrir(page, ANALISIS_TODO_COINCIDE, { borradorPerdido: true });
    await alPaso2(page);

    // The first validation comes with a change: the draft is found missing there.
    await dialogo(page).getByRole('button', { name: 'Ver columnas' }).click();
    await elegirCampo(page, 1, 'dias_atraso');

    await expect(dialogo(page).locator('[data-upload-error]')).toHaveText('La carga en curso venció, ya se confirmó o no existe. Vuelve a elegir el archivo.');
    await expect(pasoActual(page)).toHaveAttribute('data-paso-marca', '1');
  });

  test('otro fallo de la API se dice sin salir del paso 2', async ({ page }) => {
    await abrir(page, ANALISIS_TODO_COINCIDE, { respuestasConfirmar: [{ estado: 500, cuerpo: { detail: 'fallo interno' } }] });
    await alPaso2(page);

    await confirmar(page).click();

    await expect(dialogo(page).locator('[data-confirmar-error]')).not.toHaveText('');
    await expect(pasoActual(page)).toHaveAttribute('data-paso-marca', '2');
    await expect(confirmar(page)).toBeEnabled();
  });
});

test.describe('cancelar', () => {
  test('«Cancelar» en el paso 2 borra el borrador y vuelve al paso 1 sin cerrar el diálogo', async ({ page }) => {
    const { carga } = await abrir(page);
    await alPaso2(page);

    await dialogo(page).getByRole('button', { name: 'Cancelar' }).click();

    await expect.poll(() => carga.descartados).toEqual([7]);
    await expect(dialogo(page)).toBeVisible();
    await expect(pasoActual(page)).toHaveAttribute('data-paso-marca', '1');
    await expect(dialogo(page).locator('#mapeador')).toBeHidden();
  });

  test('cerrar el diálogo con Escape en el paso 2 tampoco deja el borrador', async ({ page }) => {
    const { carga } = await abrir(page);
    await alPaso2(page);

    await page.keyboard.press('Escape');

    await expect(dialogo(page)).toBeHidden();
    await expect.poll(() => carga.descartados).toEqual([7]);
  });

  test('«Cancelar» en el paso 1 solo cierra: no hay borrador', async ({ page }) => {
    const { carga } = await abrir(page);

    await dialogo(page).getByRole('button', { name: 'Cancelar' }).click();

    await expect(dialogo(page)).toBeHidden();
    expect(carga.descartados).toEqual([]);
  });

  test('volver a abrir el diálogo empieza otra vez por el paso 1, con el archivo olvidado', async ({ page }) => {
    await abrir(page);
    await alPaso2(page);
    await page.keyboard.press('Escape');
    await expect(dialogo(page)).toBeHidden();

    await page.getByRole('button', { name: 'Subir sábana' }).click();

    await expect(pasoActual(page)).toHaveAttribute('data-paso-marca', '1');
    await expect(page.locator('#upload-file')).toHaveValue('');
  });
});

test.describe('el foco', () => {
  const resumen = (page: Page) => dialogo(page).locator('[data-mapeo-resumen]');

  test('al entrar al paso 2 el foco queda en el resumen, no se pierde en la página', async ({ page }) => {
    await abrir(page);
    await alPaso2(page);

    await expect(resumen(page)).toBeFocused();
  });

  test('«Cancelar» devuelve el foco a «Continuar», que es lo que queda a la vista', async ({ page }) => {
    await abrir(page);
    await alPaso2(page);

    await dialogo(page).getByRole('button', { name: 'Cancelar' }).click();

    await expect(continuar(page)).toBeFocused();
  });

  test('un borrador vencido al confirmar deja el foco en «Continuar»', async ({ page }) => {
    await abrir(page, ANALISIS_TODO_COINCIDE, { respuestasConfirmar: [codigoDeRechazo(404, 'borrador_no_encontrado')] });
    await alPaso2(page);

    await confirmar(page).click();

    await expect(continuar(page)).toBeFocused();
  });

  test('un borrador vencido al validar deja el foco en «Continuar»', async ({ page }) => {
    await abrir(page, ANALISIS_TODO_COINCIDE, { borradorPerdido: true });
    await alPaso2(page);
    await dialogo(page).getByRole('button', { name: 'Ver columnas' }).click();

    await elegirCampo(page, 1, 'dias_atraso');

    await expect(continuar(page)).toBeFocused();
  });

  test('tras un 422 el foco va al primer campo marcado', async ({ page }) => {
    await abrir(page, ANALISIS_TODO_COINCIDE, {
      respuestasConfirmar: [
        {
          estado: 422,
          cuerpo: {
            detail: 'Hay columnas por revisar',
            codigo: 'mapeo_con_problemas',
            problemas: [{ indice: 1, codigo: 'campo_repetido', detalle: 'Campo repetido', campo: 'dias_atraso' }],
          },
        },
      ],
    });
    await alPaso2(page);
    await dialogo(page).getByRole('button', { name: 'Ver columnas' }).click();
    await elegirCampo(page, 1, 'dias_atraso');
    await expect(confirmar(page)).toBeEnabled();

    await confirmar(page).click();

    await expect(campoDe(page, 1)).toBeFocused();
  });

  test('otro fallo de la API devuelve el foco a «Confirmar y cargar»', async ({ page }) => {
    await abrir(page, ANALISIS_TODO_COINCIDE, { respuestasConfirmar: [{ estado: 500, cuerpo: { detail: 'fallo interno' } }] });
    // A real answer takes time: the button is off meanwhile and the browser takes the focus from it.
    await page.route('**/api/cargas/desde-borrador', async (route) => {
      await new Promise((resolver) => setTimeout(resolver, 300));
      await route.fallback();
    });
    await alPaso2(page);

    await confirmar(page).click();

    await expect(dialogo(page).locator('[data-confirmar-error]')).not.toHaveText('');
    await expect(confirmar(page)).toBeFocused();
  });
});

test.describe('el pie del paso 2', () => {
  const MUCHAS = analisisSintetico([
    columna(0, 'Pagare', 'coincide', 'pagare'),
    ...Array.from({ length: 24 }, (_, i) => columna(i + 1, `Columna ${i + 1}`, 'parecido', 'titular')),
  ]);

  for (const [ancho, alto] of [[1440, 900], [360, 640]] as const) {
    test(`con 25 columnas a ${ancho} px la acción y su motivo están a la vista sin desplazarse`, async ({ page }) => {
      await page.setViewportSize({ width: ancho, height: alto });
      await abrir(page, MUCHAS);
      await alPaso2(page);
      await expect(motivo(page)).not.toHaveText('');

      const desborda = await dialogo(page).evaluate((nodo) => nodo.scrollHeight > nodo.clientHeight);
      expect(desborda).toBe(true);
      await expect(confirmar(page)).toBeInViewport();
      await expect(motivo(page)).toBeInViewport();
    });
  }
});

test.describe('detalles del paso 2', () => {
  test('un Excel de una hoja no deja el hueco de las opciones', async ({ page }) => {
    await abrir(page);
    await alPaso2(page);
    // Not just empty: an empty box still takes its gap in the grid.
    await expect(dialogo(page).locator('[data-opciones-lectura]')).toHaveJSProperty('hidden', true);
  });

  test('un CSV muestra el bloque de opciones', async ({ page }) => {
    await abrir(page, CSV);
    await alPaso2(page, CSV_SINTETICO);
    await expect(dialogo(page).locator('[data-opciones-lectura]')).toBeVisible();
    await expect(dialogo(page).locator('[data-opciones-lectura]')).toHaveJSProperty('hidden', false);
  });

  test('«Volver a leer» y «Mantener lo elegido» leen el aviso como su descripción', async ({ page }) => {
    await abrir(page, VARIAS_HOJAS);
    await alPaso2(page);
    await dialogo(page).getByRole('button', { name: 'Ver columnas' }).click();
    await elegirCampo(page, 1, 'dias_atraso');

    await opcion(page, 'hoja').selectOption('MORA');

    const aviso = /Cambiar la hoja vuelve a leer el archivo/;
    await expect(dialogo(page).getByRole('button', { name: 'Volver a leer' })).toHaveAccessibleDescription(aviso);
    await expect(dialogo(page).getByRole('button', { name: 'Mantener lo elegido' })).toHaveAccessibleDescription(aviso);
  });
});

test.describe('la lista de campos dentro del diálogo (T-MAP-F3)', () => {
  test('el primer Escape cierra la lista; solo el segundo cierra el diálogo', async ({ page }) => {
    await abrir(page, CON_PARECIDOS);
    await alPaso2(page);

    await campoDe(page, 1).fill('dias');
    await campoDe(page, 1).press('Escape');

    await expect(fila(page, 1).getByRole('listbox')).toBeHidden();
    await expect(dialogo(page)).toBeVisible();
    await expect(campoDe(page, 1)).toHaveAttribute('data-valor', 'saldo_capital_pendiente');

    await campoDe(page, 1).press('Escape');
    await expect(dialogo(page)).toBeHidden();
  });

  test('Intro en la lista elige el campo y no envía el formulario', async ({ page }) => {
    const { carga } = await abrir(page, CON_PARECIDOS);
    await alPaso2(page);

    await campoDe(page, 1).fill('atraso');
    await campoDe(page, 1).press('Enter');

    await expect(campoDe(page, 1)).toHaveAttribute('data-valor', 'dias_atraso');
    await expect(pasoActual(page)).toHaveAttribute('data-paso-marca', '2');
    expect(carga.confirmaciones).toEqual([]);
  });

  // At about 930 px the «Campo de carga» column was cut on the right: the field list now shrinks with it.
  // Long headers and three examples each, as a real sheet brings them.
  const LARGO = analisisSintetico([
    columna(0, 'NUMERO DE PAGARE DEL CREDITO', 'coincide', 'pagare', ['PG-0000001', 'PG-0000002', 'PG-0000003']),
    columna(1, 'SALDO CAPITAL PENDIENTE AL CORTE', 'parecido', 'saldo_capital_pendiente', ['1500000.50', '82000.00', '310.75']),
    columna(2, 'NOMBRE COMPLETO DEL CLIENTE', 'parecido', 'titular', ['NOMBRE UNO', 'NOMBRE DOS', 'NOMBRE TRES']),
  ]);
  for (const [ancho, alto] of [[1440, 900], [930, 800], [360, 740]] as const) {
    test(`a ${ancho} px la columna «Campo de carga» entra entera, sin desplazar la tabla de lado`, async ({ page }) => {
      await page.setViewportSize({ width: ancho, height: alto });
      await abrir(page, LARGO);
      await alPaso2(page);

      const medidas = await dialogo(page).evaluate((d) => {
        const tabla = d.querySelector<HTMLElement>('.table-scroll')!;
        const campo = d.querySelector<HTMLElement>('tr[data-fila="1"] [role="combobox"]')!.getBoundingClientRect();
        const caja = d.getBoundingClientRect();
        return { sobra: tabla.scrollWidth - tabla.clientWidth, derecha: campo.right, limite: caja.right };
      });
      expect(medidas.sobra).toBeLessThanOrEqual(0);
      expect(medidas.derecha).toBeLessThanOrEqual(medidas.limite);
    });
  }
});

test.describe('crear un campo adicional desde la carga (RF-64)', () => {
  const CON_UN_DATO_NUEVO = analisisSintetico([
    columna(0, 'Pagare', 'coincide', 'pagare'),
    columna(1, 'Saldo Capital', 'parecido', 'saldo_capital_pendiente'),
    columna(2, 'Monto en mora', 'sin_coincidencia', null, ['1500.50', '82.00']),
  ]);
  const referencia = (page: Page) => dialogo(page).getByRole('button', { name: 'Crear un campo adicional' });
  const formulario = (page: Page) => dialogo(page).getByRole('group', { name: 'Crear un campo adicional' });
  const nombreDelCampo = (page: Page) => formulario(page).getByLabel('Nombre del campo');

  async function crearUno(page: Page) {
    await referencia(page).click();
    await formulario(page).getByRole('radio', { name: 'Número' }).check();
    await formulario(page).getByRole('button', { name: 'Crear campo' }).click();
  }

  test('con una columna por revisar abierta, la fila del campo nuevo sigue a la vista y tiene el foco', async ({ page }) => {
    const { carga } = await abrir(page, CON_UN_DATO_NUEVO);
    await alPaso2(page);
    await expect(dialogo(page).getByRole('button', { name: /^Por revisar/ })).toHaveAttribute('aria-pressed', 'true');
    await expect(fila(page, 2)).toBeHidden();

    await crearUno(page);

    await expect(fila(page, 2)).toBeVisible();
    await expect(campoDe(page, 2)).toBeFocused();
    expect(carga.mapeador.creaciones).toEqual([{ indice: 2, nombre_legible: 'Monto en mora', tipo: 'numero' }]);
  });

  test('el campo creado queda en el catálogo de la página: el siguiente archivo ya lo trae', async ({ page }) => {
    await abrir(page, CON_UN_DATO_NUEVO);
    await alPaso2(page);
    await crearUno(page);
    await dialogo(page).locator('[data-mapeo-cancelar]').click();
    await expect(continuar(page)).toBeVisible();

    await alPaso2(page);
    await dialogo(page).getByRole('button', { name: /^Todas/ }).click();
    await campoDe(page, 1).click();

    await expect(fila(page, 1).getByRole('option', { name: 'Monto en mora' })).toBeVisible();
    await expect(fila(page, 1).locator('.selector-campo__grupo').last()).toHaveText('Campos adicionales');
  });

  test('un borrador vencido al crear devuelve al paso 1 con el texto de la interfaz', async ({ page }) => {
    await abrir(page, CON_UN_DATO_NUEVO, {
      mapeador: { analisis: CON_UN_DATO_NUEVO, pedidos: [], rechazosCrear: [{ estado: 404, cuerpo: codigoDeRechazo(404, 'borrador_no_encontrado').cuerpo }] },
    });
    await alPaso2(page);

    await crearUno(page);

    await expect(dialogo(page).locator('[data-paso-marca][aria-current="step"]')).toHaveAttribute('data-paso-marca', '1');
    await expect(dialogo(page).locator('[data-upload-error]')).toHaveText(
      'La carga en curso venció, ya se confirmó o no existe. Vuelve a elegir el archivo.',
    );
  });

  test('Enter en el nombre crea el campo y no envía el formulario del diálogo', async ({ page }) => {
    const { carga } = await abrir(page, CON_UN_DATO_NUEVO);
    await alPaso2(page);
    await referencia(page).click();
    await formulario(page).getByRole('radio', { name: 'Texto' }).check();

    await nombreDelCampo(page).press('Enter');

    await expect.poll(() => carga.mapeador.creaciones?.length).toBe(1);
    await expect(dialogo(page).locator('[data-paso-marca][aria-current="step"]')).toHaveAttribute('data-paso-marca', '2');
    expect(carga.borradoresCreados).toHaveLength(1);
  });
});

test.describe('dos cargas seguidas en la misma página (T-CA-F3)', () => {
  const columnas = () => [
    columna(0, 'Pagare', 'coincide', 'pagare'),
    columna(1, 'Saldo Capital', 'parecido', 'saldo_capital_pendiente'),
    columna(2, 'Monto en mora', 'sin_coincidencia', null, ['1500.50', '82.00']),
  ];
  const unBorrador = (id: number) => analisisSintetico(columnas(), { borrador_id: id });
  const referencia = (page: Page) => dialogo(page).getByRole('button', { name: 'Crear un campo adicional' });
  const formulario = (page: Page) => dialogo(page).getByRole('group', { name: 'Crear un campo adicional' });
  const hacia = (carga: ApiFalsaCargaMapeada, patron: RegExp) => (carga.mapeador.rutas ?? []).filter((r) => patron.test(r.ruta)).map((r) => r.ruta);

  async function crearUno(page: Page) {
    await referencia(page).click();
    await formulario(page).getByRole('radio', { name: 'Número' }).check();
    await formulario(page).getByRole('button', { name: 'Crear campo' }).click();
  }

  test('la segunda carga crea un campo con un solo POST, al borrador de ahora', async ({ page }) => {
    const { carga } = await abrir(page, unBorrador(14));
    await alPaso2(page);
    await crearUno(page);
    await expect(campoDe(page, 2)).toHaveValue('Monto en mora');
    await dialogo(page).getByRole('button', { name: 'Aceptar sugerencias (1)' }).click();
    await expect(confirmar(page)).toBeEnabled();
    await confirmar(page).click();
    await expect(dialogo(page)).toBeHidden();

    // The second load, in the same page: another draft, the same markup.
    carga.analisis = unBorrador(15);
    carga.mapeador.rutas = [];
    await page.getByRole('button', { name: 'Subir sábana' }).click();
    await alPaso2(page);
    await crearUno(page);

    await expect(campoDe(page, 2)).toHaveValue('Monto en mora');
    await expect(dialogo(page).locator('[data-paso-marca][aria-current="step"]')).toHaveAttribute('data-paso-marca', '2');
    expect(hacia(carga, /campos-adicionales$/)).toEqual(['/mapeador/borradores/15/campos-adicionales']);
  });

  test('con Enter en el nombre, la segunda carga también crea una sola vez y en el borrador de ahora', async ({ page }) => {
    const { carga } = await abrir(page, unBorrador(14));
    await alPaso2(page);
    await dialogo(page).locator('[data-mapeo-cancelar]').click();
    carga.analisis = unBorrador(15);
    carga.mapeador.rutas = [];

    await alPaso2(page);
    await referencia(page).click();
    await formulario(page).getByRole('radio', { name: 'Texto' }).check();
    await formulario(page).getByLabel('Nombre del campo').press('Enter');

    await expect(campoDe(page, 2)).toHaveValue('Monto en mora');
    expect(hacia(carga, /campos-adicionales$/)).toEqual(['/mapeador/borradores/15/campos-adicionales']);
  });

  test('la validación de la segunda carga va una sola vez por cambio, al borrador de ahora', async ({ page }) => {
    const { carga } = await abrir(page, unBorrador(14));
    await alPaso2(page);
    await crearUno(page);
    await dialogo(page).getByRole('button', { name: 'Aceptar sugerencias (1)' }).click();
    await expect(confirmar(page)).toBeEnabled();
    await confirmar(page).click();
    await expect(dialogo(page)).toBeHidden();

    carga.analisis = unBorrador(15);
    await page.getByRole('button', { name: 'Subir sábana' }).click();
    await alPaso2(page);
    carga.mapeador.rutas = [];

    await dialogo(page).getByRole('button', { name: 'Aceptar sugerencias (1)' }).click();
    await expect(confirmar(page)).toBeEnabled();

    expect(hacia(carga, /validacion$/)).toEqual(['/mapeador/borradores/15/validacion']);
  });

  test('cancelar una carga y empezar otra tampoco deja al borrador anterior escuchando', async ({ page }) => {
    const { carga } = await abrir(page, unBorrador(14));
    await alPaso2(page);
    await dialogo(page).locator('[data-mapeo-cancelar]').click();
    carga.analisis = unBorrador(15);
    carga.mapeador.rutas = [];

    await alPaso2(page);
    await crearUno(page);

    await expect(campoDe(page, 2)).toHaveValue('Monto en mora');
    expect(hacia(carga, /campos-adicionales$/)).toEqual(['/mapeador/borradores/15/campos-adicionales']);
  });

  test('cerrar el diálogo con Escape y volver a subir tampoco', async ({ page }) => {
    const { carga } = await abrir(page, unBorrador(14));
    await alPaso2(page);
    await page.keyboard.press('Escape');
    await expect(dialogo(page)).toBeHidden();
    carga.analisis = unBorrador(15);
    carga.mapeador.rutas = [];

    await page.getByRole('button', { name: 'Subir sábana' }).click();
    await alPaso2(page);
    await crearUno(page);

    await expect(campoDe(page, 2)).toHaveValue('Monto en mora');
    expect(hacia(carga, /campos-adicionales$/)).toEqual(['/mapeador/borradores/15/campos-adicionales']);
  });
});

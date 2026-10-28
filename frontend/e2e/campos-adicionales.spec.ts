/**
 * Additional fields on screen (T-CA-F1, docs/campos-adicionales-interfaz.md): creating one from a column
 * of the mapper (RF-64) and telling it apart in the lists (RF-66). The mapper runs on its own test page;
 * the lists run on Cartera and on the text editor. Every name, header and value is synthetic.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import { apiVacia, camposSinteticos, montarApi, seleccionGuardada, version } from './api-falsa';
import {
  CAMPOS_SINTETICOS,
  analisisSintetico,
  campoAdicional,
  columna,
  manejarMapeador,
  type Analisis,
  type ApiFalsaMapeador,
} from './api-falsa-mapeador';
import { apiArchivosCarga, manejadorArchivosCarga } from './api-falsa-archivos-carga';
import { apiDefiniciones, definicionFalsa, manejadorDefiniciones } from './api-falsa-definiciones';
import { apiTextoEnriquecidoVacia, manejarTextoEnriquecido } from './api-falsa-texto-enriquecido';

test.use({ reducedMotion: 'reduce' });

// ---- The mapper -----------------------------------------------------------------------------

async function abrir(
  page: Page,
  analisis: Analisis,
  conCrearCampo = true,
  parcial: Partial<ApiFalsaMapeador> = {},
  campos = CAMPOS_SINTETICOS,
) {
  const mapeador: ApiFalsaMapeador = { analisis, pedidos: [], ...parcial };
  const api = apiVacia();
  api.manejadores = [manejarMapeador(mapeador)];
  await montarApi(page, api);
  await page.addInitScript(
    (caso) => {
      (window as unknown as { casoMapeador: unknown }).casoMapeador = caso;
    },
    { analisis, campos, conCrearCampo },
  );
  await page.goto('/pruebas/mapeador');
  await expect(page.locator('body')).toHaveAttribute('data-montado', 'true');
  return mapeador;
}

const raiz = (page: Page) => page.locator('#mapeador-prueba');
const fila = (page: Page, indice: number) => raiz(page).locator(`tr[data-fila="${indice}"]`);
const campoDe = (page: Page, indice: number) => fila(page, indice).locator('[role="combobox"]');
const referencia = (page: Page) => raiz(page).locator('[data-adicional]');
const abrirFormulario = (page: Page) => referencia(page).getByRole('button', { name: 'Crear un campo adicional' });
const formulario = (page: Page) => raiz(page).getByRole('group', { name: 'Crear un campo adicional' });
const columnaDelFormulario = (page: Page) => formulario(page).getByLabel('Columna del archivo');
const nombre = (page: Page) => formulario(page).getByLabel('Nombre del campo');
const crear = (page: Page) => formulario(page).getByRole('button', { name: 'Crear campo' });
const estadoListo = (page: Page) => page.locator('[data-estado-prueba]');

const CON_UN_DATO_NUEVO = analisisSintetico([
  columna(0, 'Pagare', 'coincide', 'pagare'),
  columna(1, 'Monto en mora', 'sin_coincidencia', null, ['1500.50', '82.00', '310.75']),
  columna(2, 'Titular', 'coincide', 'titular'),
]);

const CON_DOS_DATOS_NUEVOS = analisisSintetico([
  columna(0, 'Pagare', 'coincide', 'pagare'),
  columna(1, 'Monto en mora', 'sin_coincidencia', null, ['1500.50', '82.00', '310.75']),
  columna(2, 'Zona', 'sin_coincidencia', null, ['Norte', 'Sur']),
  columna(3, 'Titular', 'coincide', 'titular'),
]);

test.describe('la referencia', () => {
  test('sin crearCampo no hay referencia ni formulario', async ({ page }) => {
    await abrir(page, CON_UN_DATO_NUEVO, false);

    await expect(referencia(page)).toBeHidden();
  });

  test('sin columnas que se puedan usar tampoco', async ({ page }) => {
    await abrir(page, analisisSintetico([columna(0, 'Pagare', 'coincide', 'pagare'), columna(1, 'Titular', 'coincide', 'titular')]));

    await expect(referencia(page)).toBeHidden();
  });

  test('con una columna sin coincidencia pregunta y ofrece crear, con la tabla a un lado', async ({ page }) => {
    await abrir(page, CON_UN_DATO_NUEVO);

    await expect(referencia(page)).toContainText('¿Una columna trae un dato que no está en la lista?');
    await expect(abrirFormulario(page)).toHaveAttribute('aria-expanded', 'false');
    await expect(formulario(page)).toBeHidden();
  });

  test('con la tabla recogida («todo listo») la referencia sigue a la vista, sin abrir la tabla', async ({ page }) => {
    await abrir(page, CON_UN_DATO_NUEVO);

    await expect(estadoListo(page)).toHaveText('listo');
    await expect(raiz(page).locator('table')).toBeHidden();
    await expect(abrirFormulario(page)).toBeVisible();
  });

  test('una columna que se deja en «No cargar» también se puede usar', async ({ page }) => {
    await abrir(page, CON_UN_DATO_NUEVO);
    await raiz(page).getByRole('button', { name: 'Ver columnas' }).click();
    await campoDe(page, 2).click();
    await fila(page, 2).locator('[role="option"][data-valor=""]').click();

    await abrirFormulario(page).click();

    await expect(columnaDelFormulario(page).locator('option')).toHaveText(['Elige una columna', 'B · «Monto en mora»', 'C · «Titular»']);
  });
});

test.describe('el formulario', () => {
  test('con una sola columna libre viene elegida, con el nombre del encabezado y el foco en el nombre', async ({ page }) => {
    await abrir(page, CON_UN_DATO_NUEVO);

    await abrirFormulario(page).click();

    await expect(abrirFormulario(page)).toHaveAttribute('aria-expanded', 'true');
    await expect(columnaDelFormulario(page)).toHaveValue('1');
    await expect(formulario(page).locator('[data-adicional-ejemplos]')).toHaveText('Ejemplos: 1500.50 · 82.00 · 310.75');
    await expect(nombre(page)).toHaveValue('Monto en mora');
    await expect(nombre(page)).toHaveAttribute('maxlength', '80');
    await expect(nombre(page)).toBeFocused();
  });

  test('con varias columnas libres empieza sin elegir y el foco va a la columna', async ({ page }) => {
    await abrir(page, CON_DOS_DATOS_NUEVOS);

    await abrirFormulario(page).click();

    await expect(columnaDelFormulario(page)).toHaveValue('');
    await expect(columnaDelFormulario(page)).toBeFocused();
    await expect(nombre(page)).toHaveValue('');

    await columnaDelFormulario(page).selectOption('2');

    await expect(nombre(page)).toHaveValue('Zona');
    await expect(formulario(page).locator('[data-adicional-ejemplos]')).toHaveText('Ejemplos: Norte · Sur');
  });

  test('ningún tipo viene marcado, y «Crear campo» espera columna, nombre sin espacios y tipo', async ({ page }) => {
    await abrir(page, CON_UN_DATO_NUEVO);
    await abrirFormulario(page).click();

    await expect(formulario(page).getByRole('radio')).toHaveCount(3);
    await expect(formulario(page).getByRole('radio', { checked: true })).toHaveCount(0);
    await expect(crear(page)).toBeDisabled();

    await formulario(page).getByRole('radio', { name: 'Número' }).check();
    await expect(crear(page)).toBeEnabled();

    await nombre(page).fill('   ');
    await expect(crear(page)).toBeDisabled();

    await nombre(page).fill(' Monto en mora ');
    await expect(crear(page)).toBeEnabled();
  });

  test('«Cancelar» cierra sin cambiar nada y devuelve el foco a la referencia', async ({ page }) => {
    const mapeador = await abrir(page, CON_UN_DATO_NUEVO);
    await abrirFormulario(page).click();

    await formulario(page).getByRole('button', { name: 'Cancelar' }).click();

    await expect(formulario(page)).toBeHidden();
    await expect(abrirFormulario(page)).toBeFocused();
    await expect(abrirFormulario(page)).toHaveAttribute('aria-expanded', 'false');
    expect(mapeador.creaciones ?? []).toEqual([]);
  });

  test('dice, antes de crear, que el campo queda aunque se cancele la carga y que el tipo no cambia', async ({ page }) => {
    await abrir(page, CON_UN_DATO_NUEVO);
    await abrirFormulario(page).click();

    await expect(formulario(page)).toContainText('El campo queda en el catálogo para las próximas sábanas, aunque canceles esta carga.');
    await expect(formulario(page)).toContainText('No se puede cambiar después');
    await expect(formulario(page).getByRole('group', { name: 'Tipo de dato' })).toHaveAccessibleDescription(/No se puede cambiar después/);
  });
});

test.describe('al crear', () => {
  test('manda {indice, nombre_legible, tipo}, asigna la columna y lo dice', async ({ page }) => {
    const mapeador = await abrir(page, CON_DOS_DATOS_NUEVOS);
    await abrirFormulario(page).click();
    await columnaDelFormulario(page).selectOption('1');
    await formulario(page).getByRole('radio', { name: 'Número' }).check();

    await crear(page).click();

    await expect.poll(() => mapeador.creaciones).toEqual([{ indice: 1, nombre_legible: 'Monto en mora', tipo: 'numero' }]);
    await expect(formulario(page)).toBeHidden();
    await expect(fila(page, 1).locator('[data-insignia]')).toHaveText('Campo nuevo');
    await expect(fila(page, 1).locator('[data-nota]')).toHaveText('Creado en esta carga');
    await expect(raiz(page).locator('[data-anuncio-busqueda]')).toHaveText('Se creó el campo «Monto en mora» y se asignó a la columna B.');
    await expect(campoDe(page, 1)).toHaveValue('Monto en mora');
    await expect(campoDe(page, 1)).toBeFocused();
  });

  test('con la tabla recogida, crear la abre para mostrar la columna asignada', async ({ page }) => {
    await abrir(page, CON_UN_DATO_NUEVO);
    await expect(raiz(page).locator('table')).toBeHidden();
    await abrirFormulario(page).click();
    await formulario(page).getByRole('radio', { name: 'Texto' }).check();

    await crear(page).click();

    await expect(raiz(page).locator('table')).toBeVisible();
    await expect(raiz(page).getByRole('button', { name: 'Ver columnas' })).toHaveAttribute('aria-expanded', 'true');
    await expect(campoDe(page, 1)).toBeFocused();
  });

  test('lo elegido en las demás columnas no cambia, y el campo nuevo sale «en uso» en sus listas', async ({ page }) => {
    await abrir(page, CON_DOS_DATOS_NUEVOS);
    await raiz(page).getByRole('button', { name: 'Ver columnas' }).click();
    await campoDe(page, 2).click();
    await fila(page, 2).locator('[role="option"][data-valor="dias_atraso"]').click();
    await abrirFormulario(page).click();
    await formulario(page).getByRole('radio', { name: 'Texto' }).check();

    await crear(page).click();

    await expect(fila(page, 1).locator('[data-insignia]')).toHaveText('Campo nuevo');
    await expect(campoDe(page, 2)).toHaveValue('Días de atraso');
    await campoDe(page, 3).click();
    await expect(fila(page, 3).getByRole('option', { name: /Monto en mora · en uso en B/ })).toBeVisible();
  });

  test('el campo nuevo aparece en su grupo, «Campos adicionales», después de «Otros campos»', async ({ page }) => {
    await abrir(page, CON_DOS_DATOS_NUEVOS);
    await abrirFormulario(page).click();
    await columnaDelFormulario(page).selectOption('1');
    await formulario(page).getByRole('radio', { name: 'Número' }).check();
    await crear(page).click();

    await campoDe(page, 2).click();

    const titulos = await fila(page, 2).locator('.selector-campo__grupo').allTextContents();
    expect(titulos.map((t) => t.trim())).toEqual(['Obligatorios', 'Otros campos', 'Campos adicionales']);
  });

  test('a 1440 px el formulario no se estira: ocupa a lo más 48 rem', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await abrir(page, CON_UN_DATO_NUEVO);
    await abrirFormulario(page).click();

    const ancho = (await formulario(page).boundingBox())!.width;

    expect(ancho).toBeLessThanOrEqual(48 * 16 + 1);
    expect(ancho).toBeGreaterThan(300);
  });

  test('si después se elige otro campo, el tag deja de decir «Campo nuevo»', async ({ page }) => {
    await abrir(page, CON_UN_DATO_NUEVO);
    await abrirFormulario(page).click();
    await formulario(page).getByRole('radio', { name: 'Texto' }).check();
    await crear(page).click();
    await expect(fila(page, 1).locator('[data-insignia]')).toHaveText('Campo nuevo');

    await campoDe(page, 1).click();
    await fila(page, 1).locator('[role="option"][data-valor="dias_atraso"]').click();

    await expect(fila(page, 1).locator('[data-insignia]')).toHaveText('Elegido a mano');
  });

  test('el estado del mapeo se valida como con cualquier cambio', async ({ page }) => {
    const mapeador = await abrir(page, CON_UN_DATO_NUEVO);
    await abrirFormulario(page).click();
    await formulario(page).getByRole('radio', { name: 'Texto' }).check();

    await crear(page).click();

    await expect.poll(() => mapeador.pedidos.at(-1)?.find((a) => a.indice === 1)).toEqual({
      indice: 1,
      campo: 'ad_monto_en_mora',
      origen: 'manual',
    });
    await expect(estadoListo(page)).toHaveText('listo');
  });

  test('Enter en el nombre crea el campo, sin enviar el formulario que contenga al mapeador', async ({ page }) => {
    const mapeador = await abrir(page, CON_UN_DATO_NUEVO);
    await abrirFormulario(page).click();
    await formulario(page).getByRole('radio', { name: 'Texto' }).check();

    await nombre(page).press('Enter');

    await expect.poll(() => mapeador.creaciones?.length).toBe(1);
  });
});

test.describe('los rechazos al crear', () => {
  const rechazo = (estado: number, cuerpo: unknown) => ({ estado, cuerpo });

  test('un nombre repetido lo dice bajo el nombre, con el campo, y ofrece usar ese campo en la columna', async ({ page }) => {
    const titular = CAMPOS_SINTETICOS.find((c) => c.nombre === 'titular')!;
    const mapeador = await abrir(page, analisisSintetico([columna(0, 'Pagare', 'coincide', 'pagare'), columna(1, 'Cliente', 'sin_coincidencia', null)]), true, {
      rechazosCrear: [rechazo(409, { detail: 'Ya existe', codigo: 'nombre_repetido', campo: titular })],
    });
    await abrirFormulario(page).click();
    await nombre(page).fill('Titular');
    await formulario(page).getByRole('radio', { name: 'Texto' }).check();

    await crear(page).click();

    const error = formulario(page).locator('[data-adicional-nombre-error]');
    await expect(error).toHaveText('Ya existe el campo «Titular». Elígelo en la lista o usa otro nombre.');
    await expect(nombre(page)).toHaveAttribute('aria-invalid', 'true');
    await expect(nombre(page)).toBeFocused();
    expect(await nombre(page).getAttribute('aria-describedby')).toContain('adicional-nombre-error');
    await expect(nombre(page)).toHaveValue('Titular');

    await formulario(page).getByRole('button', { name: 'Usar «Titular» en la columna B' }).click();

    await expect(formulario(page)).toBeHidden();
    await expect(campoDe(page, 1)).toHaveValue('Titular');
    await expect(fila(page, 1).locator('[data-insignia]')).toHaveText('Elegido a mano');
    expect(mapeador.creaciones).toHaveLength(1);
  });

  test('un nombre que ya tiene un adicional activo sigue mandando a elegirlo, y ofrece usarlo', async ({ page }) => {
    const zona = campoAdicional('ad_zona', 'Zona de cobranza');
    await abrir(
      page,
      analisisSintetico([columna(0, 'Pagare', 'coincide', 'pagare'), columna(1, 'Cliente', 'sin_coincidencia', null)]),
      true,
      { rechazosCrear: [rechazo(409, { detail: 'Ya existe', codigo: 'nombre_repetido', campo: zona })] },
      [...CAMPOS_SINTETICOS, zona],
    );
    await abrirFormulario(page).click();
    await nombre(page).fill('Zona de cobranza');
    await formulario(page).getByRole('radio', { name: 'Texto' }).check();

    await crear(page).click();

    await expect(formulario(page).locator('[data-adicional-nombre-error]')).toHaveText(
      'Ya existe el campo «Zona de cobranza». Elígelo en la lista o usa otro nombre.',
    );
    await expect(formulario(page).getByRole('button', { name: 'Usar «Zona de cobranza» en la columna B' })).toBeVisible();
  });

  test('un nombre que ya tiene un campo archivado lo dice así, sin mandar a elegirlo en la lista ni ofrecerlo', async ({ page }) => {
    const archivado = campoAdicional('ad_antiguo', 'Campo antiguo');
    await abrir(page, CON_UN_DATO_NUEVO, true, {
      rechazosCrear: [rechazo(409, { detail: 'Ya existe', codigo: 'nombre_repetido', campo: archivado })],
    });
    await abrirFormulario(page).click();
    await nombre(page).fill('Campo antiguo');
    await formulario(page).getByRole('radio', { name: 'Texto' }).check();

    await crear(page).click();

    const error = formulario(page).locator('[data-adicional-nombre-error]');
    await expect(error).toHaveText('Ya existe el campo archivado «Campo antiguo». Usa otro nombre o reactívalo en Campos adicionales.');
    await expect(error).not.toContainText('Elígelo en la lista');
    await expect(formulario(page).getByRole('button', { name: /^Usar/ })).toHaveCount(0);
    await expect(nombre(page)).toHaveValue('Campo antiguo');
    await expect(nombre(page)).toBeFocused();
  });

  test('si el campo que choca ya lo usa otra columna, no ofrece usarlo', async ({ page }) => {
    const titular = CAMPOS_SINTETICOS.find((c) => c.nombre === 'titular')!;
    await abrir(page, CON_UN_DATO_NUEVO, true, {
      rechazosCrear: [rechazo(409, { detail: 'Ya existe', codigo: 'nombre_repetido', campo: titular })],
    });
    await abrirFormulario(page).click();
    await nombre(page).fill('Titular');
    await formulario(page).getByRole('radio', { name: 'Texto' }).check();

    await crear(page).click();

    await expect(formulario(page).locator('[data-adicional-nombre-error]')).toContainText('Ya existe el campo «Titular»');
    await expect(formulario(page).getByRole('button', { name: /^Usar/ })).toHaveCount(0);
  });

  test('escribir de nuevo quita el error y la oferta', async ({ page }) => {
    const titular = CAMPOS_SINTETICOS.find((c) => c.nombre === 'titular')!;
    await abrir(page, analisisSintetico([columna(0, 'Pagare', 'coincide', 'pagare'), columna(1, 'Cliente', 'sin_coincidencia', null)]), true, {
      rechazosCrear: [rechazo(409, { detail: 'Ya existe', codigo: 'nombre_repetido', campo: titular })],
    });
    await abrirFormulario(page).click();
    await nombre(page).fill('Titular');
    await formulario(page).getByRole('radio', { name: 'Texto' }).check();
    await crear(page).click();
    await expect(formulario(page).getByRole('button', { name: /^Usar/ })).toBeVisible();

    await nombre(page).fill('Titular del contrato');

    await expect(formulario(page).locator('[data-adicional-nombre-error]')).toHaveText('');
    await expect(formulario(page).getByRole('button', { name: /^Usar/ })).toHaveCount(0);
    await expect(nombre(page)).not.toHaveAttribute('aria-invalid', 'true');
  });

  test('un 422 (nombre vacío o de más de 80) se reconoce por el estado y conserva lo escrito', async ({ page }) => {
    await abrir(page, CON_UN_DATO_NUEVO, true, { rechazosCrear: [rechazo(422, { detail: [{ type: 'string_too_long' }] })] });
    await abrirFormulario(page).click();
    await formulario(page).getByRole('radio', { name: 'Fecha' }).check();

    await crear(page).click();

    await expect(formulario(page).locator('[data-adicional-nombre-error]')).toHaveText('Escribe un nombre de hasta 80 caracteres.');
    await expect(nombre(page)).toHaveValue('Monto en mora');
    await expect(formulario(page).getByRole('radio', { name: 'Fecha' })).toBeChecked();
  });

  test('una columna que ya no está se dice bajo la columna', async ({ page }) => {
    await abrir(page, CON_UN_DATO_NUEVO, true, {
      rechazosCrear: [rechazo(404, { detail: 'x', codigo: 'columna_inexistente' })],
    });
    await abrirFormulario(page).click();
    await formulario(page).getByRole('radio', { name: 'Texto' }).check();

    await crear(page).click();

    await expect(formulario(page).locator('[data-adicional-columna-error]')).toHaveText('Esa columna no está en el archivo.');
  });

  test('sin red o con otro fallo lo dice en una alerta bajo las acciones, sin perder lo escrito', async ({ page }) => {
    await abrir(page, CON_UN_DATO_NUEVO, true, { rechazosCrear: [rechazo(500, { detail: 'fallo interno' })] });
    await abrirFormulario(page).click();
    await formulario(page).getByRole('radio', { name: 'Texto' }).check();

    await crear(page).click();

    await expect(formulario(page).getByRole('alert').filter({ hasText: /\S/ })).toHaveCount(1);
    await expect(nombre(page)).toHaveValue('Monto en mora');
    await expect(crear(page)).toBeEnabled();
  });
});

// ---- The lists ------------------------------------------------------------------------------

function catalogoConAdicionales() {
  const campos = camposSinteticos();
  const texto = campos.region;
  campos.ad_zona = { ...texto, adicional: true, etiqueta: 'Zona de cobranza' };
  campos.ad_antiguo = { ...texto, adicional: true, etiqueta: 'Campo antiguo', archivado: true };
  return campos;
}

test.describe('Cartera y el selector', () => {
  async function abrirCartera(page: Page, ajustar?: (api: ReturnType<typeof apiVacia>) => void) {
    const api = apiVacia();
    api.versiones = [version()];
    api.campos = catalogoConAdicionales();
    ajustar?.(api);
    await montarApi(page, api);
    await page.goto('/cartera');
    await expect(page.locator('[data-disponibles]')).toHaveText('3,200');
    return api;
  }

  test('en un filtro el adicional va al final, en su grupo, y el archivado no se ofrece', async ({ page }) => {
    await abrirCartera(page);
    await page.getByRole('button', { name: 'Agregar filtro' }).click();

    const campo = page.locator('[data-filtros] > .fila').first().getByLabel('Campo');

    await expect(campo.locator('optgroup')).toHaveAttribute('label', 'Campos adicionales');
    await expect(campo.locator('optgroup option')).toHaveText(['Zona de cobranza']);
    await expect(campo.locator('option', { hasText: 'Campo antiguo' })).toHaveCount(0);
    const ultima = await campo.locator('option').last().textContent();
    expect(ultima).toBe('Zona de cobranza');
  });

  test('un adicional se filtra como cualquier campo, por su nombre técnico', async ({ page }) => {
    const api = await abrirCartera(page);
    await page.getByRole('button', { name: 'Agregar filtro' }).click();
    const fila = page.locator('[data-filtros] > .fila').first();

    await fila.getByLabel('Campo').selectOption('ad_zona');
    await fila.getByLabel('Operador').selectOption('igual');
    await fila.getByLabel('Valor').fill('Norte');

    await expect
      .poll(() => api.pedidos.some((p) => new URL(p.url).searchParams.getAll('filtro').includes('ad_zona:igual:Norte')))
      .toBe(true);
  });

  test('una selección guardada que usa un archivado lo muestra con su nombre y dice que ya no se ofrece', async ({ page }) => {
    await abrirCartera(page, (api) => {
      api.selecciones = [seleccionGuardada({ id: 4, nombre: 'Con archivado', filtros: ['ad_antiguo:igual:X'], orden: null, cantidad: null })];
    });

    await page.getByLabel('Selección guardada').selectOption({ label: 'Con archivado' });

    const fila = page.locator('[data-filtros] > .fila').first();
    await expect(fila.getByLabel('Campo').locator('option:checked')).toHaveText('Campo antiguo (archivado)');
    // The select cuts the long name, so the mark also goes outside it, in words.
    await expect(fila.locator('.tag[data-archivado]')).toHaveText('Archivado');
    await expect(page.locator('[data-selector-archivados]')).toBeVisible();
    await expect(page.locator('[data-selector-archivados]')).toHaveText(
      'Usa el campo archivado «Campo antiguo». Las sábanas cargadas después de archivarlo ya no lo traen: ahí sale vacío. Para evitarlo, reactívalo en Cargas › Campos adicionales.',
    );
    await expect(page.locator('[data-selector-archivados]')).toHaveClass(/notice--warning/);
  });

  test('sin archivados en uso no hay aviso', async ({ page }) => {
    await abrirCartera(page);

    await expect(page.locator('[data-selector-archivados]')).toBeHidden();
  });

  test('en las columnas a mostrar, el adicional lleva «Adicional» en palabras y el archivado no se ofrece', async ({ page }) => {
    await abrirCartera(page);
    await page.locator('[data-columnas] summary').click();

    const opcion = page.locator('.columnas__opcion', { hasText: 'Zona de cobranza' });
    await expect(opcion.locator('.tag')).toHaveText('Adicional');
    await expect(page.locator('.columnas__opcion', { hasText: 'Campo antiguo' })).toHaveCount(0);
    await expect(page.locator('.columnas__opcion', { hasText: 'Región' }).locator('.tag')).toHaveCount(0);
  });

  test('un adicional elegido como columna sale en el encabezado con su nombre legible', async ({ page }) => {
    await abrirCartera(page);
    await page.locator('[data-columnas] summary').click();

    await page.locator('.columnas__opcion', { hasText: 'Zona de cobranza' }).getByRole('checkbox').check();

    await expect(page.getByRole('columnheader', { name: 'Zona de cobranza' })).toBeVisible();
  });

  test('en la segmentación el adicional va en su grupo', async ({ page }) => {
    await abrirCartera(page);

    const segmento = page.locator('[data-segmento]');

    await expect(segmento.locator('optgroup')).toHaveAttribute('label', 'Campos adicionales');
    await expect(segmento.locator('optgroup option')).toHaveText(['Zona de cobranza']);
  });
});

// ---- The text editor ------------------------------------------------------------------------

test.describe('el editor de texto', () => {
  async function abrirEditor(page: Page) {
    const motor = apiTextoEnriquecidoVacia();
    for (const catalogo of Object.values(motor.catalogos)) {
      catalogo.contexto.variables.push(
        { nombre: 'ad_zona', tipo: 'texto', clave_nombre: null, origen: 'cartera', etiqueta: 'Zona de cobranza', adicional: true, archivado: false },
        { nombre: 'ad_antiguo', tipo: 'texto', clave_nombre: null, origen: 'cartera', etiqueta: 'Campo antiguo', adicional: true, archivado: true },
      );
    }
    const api = apiVacia();
    api.manejadores = [manejarTextoEnriquecido(motor)];
    await montarApi(page, api);
    await page.goto('/pruebas/editor-texto?componente=editor');
    await expect(page.locator('body')).toHaveAttribute('data-montado', 'true');
  }

  test('el selector de variables muestra el adicional por su nombre, con «Adicional» y el técnico aparte', async ({ page }) => {
    await abrirEditor(page);
    const editor = page.locator('#editor-prueba');

    await editor.getByRole('button', { name: 'Variable', exact: true }).click();

    const opcion = editor.getByRole('button', { name: /^Zona de cobranza/ });
    await expect(opcion.locator('.tag')).toContainText(['texto', 'Adicional']);
    await expect(opcion.locator('.selector-variable__tecnico')).toHaveText('ad_zona');
    await expect(editor.getByRole('button', { name: /^Campo antiguo/ })).toHaveCount(0);
  });

  test('una ficha con el adicional dice solo su nombre', async ({ page }) => {
    await abrirEditor(page);
    const editor = page.locator('#editor-prueba');
    await editor.getByRole('button', { name: 'Variable', exact: true }).click();
    await editor.getByRole('button', { name: /^Zona de cobranza/ }).click();

    await expect(editor.getByRole('button', { name: /^Variable Zona de cobranza/ })).toHaveText('Zona de cobranza');
  });
});

// ---- The column builder ---------------------------------------------------------------------

test.describe('el constructor de columnas', () => {
  const ad = (nombre: string, etiqueta: string, archivado: boolean) => ({
    nombre,
    tipo: 'texto' as const,
    clave_nombre: null,
    origen: 'cartera',
    etiqueta,
    adicional: true,
    archivado,
  });

  /** A saved definition whose first column is `variable` (a direct variable), opened on /columnas. */
  async function abrirColumnas(page: Page, variable: string) {
    const motor = apiTextoEnriquecidoVacia();
    for (const catalogo of Object.values(motor.catalogos)) {
      catalogo.contexto.variables.push(ad('ad_zona', 'Zona de cobranza', false), ad('ad_antiguo', 'Campo antiguo', true));
    }
    const definiciones = apiDefiniciones();
    const definicion = definicionFalsa({ id: 1, nombre: 'SMS preventivo' });
    definicion.versiones[0].contenido.columnas[0].nombre = 'zona';
    definicion.versiones[0].contenido.columnas[0].expresion = { nodos: [{ tipo: 'variable', nombre: variable, funciones: [], obligatoria: false }] };
    definiciones.definiciones.push(definicion);
    const base = apiVacia();
    base.manejadores = [manejarTextoEnriquecido(motor), manejadorDefiniciones(definiciones)];
    await montarApi(page, base);
    await page.goto('/columnas');
    await page.getByLabel('Definición guardada').selectOption('1');
    await expect(page.getByLabel('Nombre de la columna 1')).toHaveValue('zona');
  }

  test('en la columna de variable directa el adicional dice «· adicional» y el archivado no se ofrece', async ({ page }) => {
    await abrirColumnas(page, 'telefono');
    await page.getByRole('button', { name: 'Editar zona' }).click();

    const opciones = page.locator('#columna-editor-directa option');

    await expect(opciones.filter({ hasText: /^Zona de cobranza \(.+\) · adicional$/ })).toHaveCount(1);
    await expect(opciones.filter({ hasText: 'Campo antiguo' })).toHaveCount(0);
  });

  test('una columna que ya usa un archivado lo conserva en su lista, dicho en palabras', async ({ page }) => {
    await abrirColumnas(page, 'ad_antiguo');
    await page.getByRole('button', { name: 'Editar zona' }).click();

    const elegida = page.locator('#columna-editor-directa option:checked');

    await expect(elegida).toHaveText('Campo antiguo (archivado)');
    await expect(elegida).toHaveAttribute('value', 'ad_antiguo');
  });

  test('la vista previa de una definición que usa un archivado avisa que desde las sábanas siguientes sale vacío', async ({ page }) => {
    await abrirColumnas(page, 'ad_antiguo');

    const aviso = page.locator('[data-previa-archivados]');

    await expect(aviso).toBeVisible();
    await expect(aviso).toHaveText('Usa el campo archivado «Campo antiguo». Las sábanas cargadas después de archivarlo ya no lo traen: ahí sale vacío. Para evitarlo, reactívalo en Cargas › Campos adicionales.');
    await expect(aviso).toHaveClass(/notice--warning/);
  });

  test('sin archivados en uso, la vista previa no avisa nada', async ({ page }) => {
    await abrirColumnas(page, 'ad_zona');

    await expect(page.locator('[data-previa-archivados]')).toBeHidden();
  });
});

// ---- axe ------------------------------------------------------------------------------------

const REGLAS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

async function sinViolaciones(page: Page): Promise<void> {
  const resultado = await new AxeBuilder({ page }).include('[data-ruta-prueba]').withTags(REGLAS).analyze();
  expect(resultado.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
}

for (const tema of ['light', 'dark'] as const) {
  test.describe(`axe de los campos adicionales, tema ${tema === 'light' ? 'claro' : 'oscuro'}`, () => {
    test.beforeEach(async ({ page }) => {
      await page.addInitScript((elegido) => {
        localStorage.setItem('app:appearance', JSON.stringify({ theme: elegido, language: 'es' }));
      }, tema);
    });

    test('el formulario abierto', async ({ page }) => {
      await abrir(page, CON_DOS_DATOS_NUEVOS);
      await abrirFormulario(page).click();
      await columnaDelFormulario(page).selectOption('1');
      await expect(nombre(page)).toHaveValue('Monto en mora');
      await sinViolaciones(page);
    });

    test('el formulario con el nombre repetido y la oferta de usar el campo', async ({ page }) => {
      const titular = CAMPOS_SINTETICOS.find((c) => c.nombre === 'titular')!;
      await abrir(page, analisisSintetico([columna(0, 'Pagare', 'coincide', 'pagare'), columna(1, 'Cliente', 'sin_coincidencia', null)]), true, {
        rechazosCrear: [{ estado: 409, cuerpo: { detail: 'Ya existe', codigo: 'nombre_repetido', campo: titular } }],
      });
      await abrirFormulario(page).click();
      await nombre(page).fill('Titular');
      await formulario(page).getByRole('radio', { name: 'Texto' }).check();
      await crear(page).click();
      await expect(formulario(page).getByRole('button', { name: /^Usar/ })).toBeVisible();
      await sinViolaciones(page);
    });

    test('una columna con el campo recién creado', async ({ page }) => {
      await abrir(page, CON_UN_DATO_NUEVO);
      await abrirFormulario(page).click();
      await formulario(page).getByRole('radio', { name: 'Texto' }).check();
      await crear(page).click();
      await expect(fila(page, 1).locator('[data-insignia]')).toHaveText('Campo nuevo');
      await sinViolaciones(page);
    });
  });
}

test('el formulario a 360 px cabe y no desborda', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await abrir(page, CON_DOS_DATOS_NUEVOS);
  await abrirFormulario(page).click();

  const desborde = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(desborde).toBeLessThanOrEqual(0);
  await crear(page).scrollIntoViewIfNeeded();
  await expect(crear(page)).toBeInViewport();
  await sinViolaciones(page);
});

// ---- Generar carga ----------------------------------------------------------------------------

test.describe('generar carga', () => {
  const ad = (nombre: string, etiqueta: string, archivado: boolean) => ({
    nombre,
    tipo: 'texto' as const,
    clave_nombre: null,
    origen: 'cartera',
    etiqueta,
    adicional: true,
    archivado,
  });

  /** A saved definition whose first column is `variable`, chosen on /generar-carga. */
  async function abrirGenerar(page: Page, variable: string, conCatalogo = true) {
    const motor = apiTextoEnriquecidoVacia();
    for (const catalogo of Object.values(motor.catalogos)) {
      catalogo.contexto.variables.push(ad('ad_zona', 'Zona de cobranza', false), ad('ad_antiguo', 'Campo antiguo', true));
    }
    const definiciones = apiDefiniciones();
    const definicion = definicionFalsa({ id: 7, nombre: 'SMS preventivo' });
    definicion.versiones[0].contenido.columnas[0].expresion = { nodos: [{ tipo: 'variable', nombre: variable, funciones: [], obligatoria: false }] };
    definiciones.definiciones.push(definicion);
    const base = apiVacia();
    base.versiones = [version({ fecha_corte: '2026-09-10', vigente: true })];
    // Without the engine's fake the catalogue answers 404: the notice is a courtesy and nothing else changes.
    base.manejadores = [
      ...(conCatalogo ? [manejarTextoEnriquecido(motor)] : []),
      manejadorDefiniciones(definiciones),
      manejadorArchivosCarga(apiArchivosCarga()),
    ];
    await montarApi(page, base);
    await page.goto('/generar-carga');
    await expect(page.getByRole('heading', { name: 'Generar carga', level: 1 })).toBeVisible();
    await page.getByLabel('Definición guardada').selectOption({ label: 'SMS preventivo' });
    await expect(page.getByLabel('Versión', { exact: true })).toBeVisible();
  }

  test('la definición que usa un archivado avisa, sobre la vista previa, que desde las sábanas siguientes sale vacío', async ({ page }) => {
    await abrirGenerar(page, 'ad_antiguo');

    const aviso = page.locator('[data-previa-archivados]');

    await expect(aviso).toBeVisible();
    await expect(aviso).toHaveText('Usa el campo archivado «Campo antiguo». Las sábanas cargadas después de archivarlo ya no lo traen: ahí sale vacío. Para evitarlo, reactívalo en Cargas › Campos adicionales.');
    await expect(aviso).toHaveClass(/notice--warning/);
  });

  test('sin archivados en uso no hay aviso, y sin elegir definición tampoco', async ({ page }) => {
    await abrirGenerar(page, 'ad_zona');

    await expect(page.locator('[data-previa-archivados]')).toBeHidden();

    await page.getByLabel('Definición guardada').selectOption({ label: 'Elige una definición' });
    await expect(page.locator('[data-previa-archivados]')).toBeHidden();
  });

  test('si el catálogo no responde no hay aviso y la pantalla sigue igual', async ({ page }) => {
    await abrirGenerar(page, 'ad_antiguo', false);

    await expect(page.locator('[data-previa-archivados]')).toBeHidden();
    await expect(page.locator('[data-definicion-resumen]')).toBeVisible();
  });
});

test.describe('un mapeador destruido (T-CA-F3)', () => {
  const CON_TODO = analisisSintetico([
    columna(0, 'Pagare', 'coincide', 'pagare'),
    columna(1, 'Nombre cliente', 'parecido', 'titular'),
    columna(2, 'Monto en mora', 'sin_coincidencia', null, ['1500.50']),
  ]);
  const destruir = (page: Page) => page.evaluate(() => (window as unknown as { controladorPrueba: { destruir(): void } }).controladorPrueba.destruir());

  test('los controles que quedan en la página no reaccionan', async ({ page }) => {
    const mapeador = await abrir(page, CON_TODO);
    await expect(raiz(page).getByRole('button', { name: /^Por revisar/ })).toHaveAttribute('aria-pressed', 'true');
    await expect(abrirFormulario(page)).toHaveAttribute('aria-expanded', 'false');
    const antes = mapeador.pedidos.length;

    await destruir(page);

    await raiz(page).getByRole('button', { name: /^Todas/ }).click();
    await expect(raiz(page).getByRole('button', { name: /^Por revisar/ })).toHaveAttribute('aria-pressed', 'true');
    await raiz(page).getByRole('button', { name: 'Aceptar sugerencias (1)' }).click();
    await expect(raiz(page).getByRole('button', { name: 'Aceptar sugerencias (1)' })).toBeVisible();
    await abrirFormulario(page).click();
    await expect(abrirFormulario(page)).toHaveAttribute('aria-expanded', 'false');
    await expect(formulario(page)).toBeHidden();
    await campoDe(page, 1).click();
    await expect(campoDe(page, 1)).toHaveAttribute('aria-expanded', 'false');
    // Nothing asked the API either: a destroyed mapper validates and creates nothing.
    await page.waitForTimeout(600);
    expect(mapeador.pedidos).toHaveLength(antes);
    expect(mapeador.rutas ?? []).toEqual([]);
  });

  test('antes de destruirlo esos mismos controles sí reaccionan', async ({ page }) => {
    await abrir(page, CON_TODO);

    await raiz(page).getByRole('button', { name: /^Todas/ }).click();
    await expect(raiz(page).getByRole('button', { name: /^Todas/ })).toHaveAttribute('aria-pressed', 'true');
    await abrirFormulario(page).click();
    await expect(abrirFormulario(page)).toHaveAttribute('aria-expanded', 'true');
  });

  test('un cambio de idioma tampoco lo repinta una vez destruido', async ({ page }) => {
    await abrir(page, CON_TODO);
    await destruir(page);
    await page.evaluate(() => {
      const cabecera = document.querySelector('#mapeador-prueba [data-filtro-opcion="revisar"]')!;
      cabecera.textContent = 'sentinela';
      document.dispatchEvent(new Event('languagechange'));
    });

    await expect(raiz(page).locator('[data-filtro-opcion="revisar"]')).toHaveText('sentinela');
  });
});

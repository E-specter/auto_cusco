/**
 * The portfolio selection screen, end to end against an intercepted API.
 *
 * The paths covered are the ones where a wrong screen costs a collections
 * team real work: asking for more products than exist without noticing, a
 * date with no portfolio read as an empty one, a shared selection overwritten
 * or saved under a taken name, and amounts that lose precision on the way.
 */
import { expect, test } from '@playwright/test';

import { apiVacia, montarApi, resumenSintetico, seleccionGuardada, version } from './api-falsa';

const pedidosDeResumen = (api: ReturnType<typeof apiVacia>) =>
  api.pedidos.filter((p) => new URL(p.url).pathname === '/api/cartera/resumen').map((p) => new URL(p.url));

test.describe('métricas lado a lado', () => {
  test('muestra universo y selección, y recalcula una sola vez al escribir la cantidad', async ({ page }) => {
    const api = apiVacia();
    api.versiones = [version()];
    await montarApi(page, api);

    await page.goto('/cartera');
    await expect(page.locator('[data-disponibles]')).toHaveText('3,200');

    await page.getByLabel('Cantidad (primeros n)').pressSequentially('500');

    await expect(page.locator('[data-solicitados]')).toHaveText('500');
    // Montos que no caben en un número de JavaScript llegan exactos a la pantalla.
    await expect(page.getByRole('cell', { name: '9,007,199,254,740,993.01' })).toBeVisible();
    await expect(page.getByRole('cell', { name: '4,812,345.67' })).toBeVisible();

    const conCantidad = pedidosDeResumen(api).filter((url) => url.searchParams.has('cantidad'));
    expect(conCantidad.map((url) => url.searchParams.get('cantidad'))).toEqual(['500']);
  });

  test('un filtro se arma con el catálogo y viaja en la sintaxis de la API', async ({ page }) => {
    const api = apiVacia();
    api.versiones = [version()];
    await montarApi(page, api);

    await page.goto('/cartera');
    await expect(page.locator('[data-disponibles]')).toHaveText('3,200');

    await page.getByRole('button', { name: 'Agregar filtro' }).click();
    const fila = page.locator('[data-filtros] > .fila').first();
    await expect(fila).toHaveAttribute('data-estado', 'incompleta');

    await fila.getByLabel('Campo').selectOption('dias_atraso');
    await fila.getByLabel('Operador').selectOption('mayor');
    await fila.getByLabel('Valor').fill('30');

    await expect(fila).toHaveAttribute('data-estado', 'ok');
    await expect
      .poll(() => pedidosDeResumen(api).some((url) => url.searchParams.getAll('filtro').includes('dias_atraso:mayor:30')))
      .toBe(true);
  });

  test('avisa de forma explícita cuando se piden más productos de los que hay (RF-08)', async ({ page }) => {
    const api = apiVacia();
    api.versiones = [version()];
    api.resumen = (url) => ({ estado: 200, cuerpo: resumenSintetico(url, 320) });
    await montarApi(page, api);

    await page.goto('/cartera');
    await page.getByLabel('Cantidad (primeros n)').fill('500');

    await expect(
      page.getByText('Pediste los primeros 500, pero solo 320 productos cumplen los filtros.'),
    ).toBeVisible();
    await expect(page.locator('[data-flujo]')).toHaveAttribute('data-suficiente', 'false');
  });
});

test.describe('fechas sin cartera', () => {
  test('una fecha sin vigente no se lee como una selección vacía', async ({ page }) => {
    const api = apiVacia();
    api.versiones = [version({ vigente: false, estado: 'fallida' })];
    api.resumen = () => ({ estado: 404, cuerpo: { detail: 'La fecha no tiene una version vigente de sabana' } });
    await montarApi(page, api);

    await page.goto('/cartera');

    await expect(page.getByRole('heading', { name: /no tiene cartera/ })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Ir a la consola de cargas' })).toBeVisible();
    await expect(page.getByText('Ningún producto cumple los filtros.')).toBeHidden();
  });

  test('sin ninguna sábana cargada invita a subir la primera', async ({ page }) => {
    const api = apiVacia();
    await montarApi(page, api);

    await page.goto('/cartera');

    await expect(page.getByRole('heading', { name: 'Todavía no hay cartera que seleccionar.' })).toBeVisible();
    expect(pedidosDeResumen(api)).toHaveLength(0);
  });
});

test.describe('selecciones guardadas y compartidas', () => {
  test('un nombre repetido se avisa junto al nombre, y luego se guarda', async ({ page }) => {
    const api = apiVacia();
    api.versiones = [version()];
    api.respuestasCrearSeleccion = [
      { estado: 409, cuerpo: { detail: 'Ya existe una seleccion con ese nombre' } },
      { estado: 201, cuerpo: seleccionGuardada({ id: 7, nombre: 'Top 500 nueva', filtros: [], orden: null }) },
    ];
    await montarApi(page, api);

    await page.goto('/cartera');
    await page.getByLabel('Cantidad (primeros n)').fill('500');
    await page.getByRole('button', { name: 'Guardar como nueva' }).click();

    const dialogo = page.getByRole('dialog', { name: 'Guardar la selección' });
    await dialogo.getByLabel('Nombre').fill('Top 500');
    await dialogo.getByRole('button', { name: 'Guardar', exact: true }).click();
    await expect(dialogo.getByText('Ya existe una selección con ese nombre. Elige otro.')).toBeVisible();
    await expect(dialogo.getByLabel('Nombre')).toHaveAttribute('aria-invalid', 'true');

    await dialogo.getByLabel('Nombre').fill('Top 500 nueva');
    await dialogo.getByRole('button', { name: 'Guardar', exact: true }).click();

    await expect(dialogo).toBeHidden();
    await expect(page.getByText('«Top 500 nueva», sin cambios.')).toBeVisible();
    const guardado = api.pedidos.filter((p) => p.metodo === 'POST' && p.url.endsWith('/api/selecciones')).at(-1);
    expect(JSON.parse(guardado?.cuerpo ?? '{}')).toMatchObject({ nombre: 'Top 500 nueva', cantidad: 500 });
  });

  test('una selección que dejó de aplicar se carga igual, marcada, y no se calcula', async ({ page }) => {
    const api = apiVacia();
    api.versiones = [version()];
    api.selecciones = [
      seleccionGuardada({
        id: 3,
        nombre: 'Vieja',
        filtros: ['campo_retirado:igual:x'],
        aplicable: false,
        problemas: [{ parte: 'filtro', expresion: 'campo_retirado:igual:x', detalle: 'El campo campo_retirado no existe' }],
      }),
    ];
    await montarApi(page, api);

    await page.goto('/cartera');
    await expect(page.locator('[data-disponibles]')).toHaveText('3,200');
    const antes = pedidosDeResumen(api).length;

    await page.getByLabel('Selección guardada').selectOption({ label: 'Vieja · no aplica' });

    await expect(page.getByRole('heading', { name: 'La selección tiene partes que no aplican.' })).toBeVisible();
    await expect(page.locator('[data-filtros] > .fila').first()).toHaveAttribute('data-estado', 'problema');
    await expect(page.locator('.fila__nota', { hasText: 'El campo campo_retirado no existe' })).toBeVisible();
    await page.waitForTimeout(600);
    expect(pedidosDeResumen(api)).toHaveLength(antes);
  });

  test('cambiar de selección con cambios sin guardar pregunta, y seguir editando es lo preseleccionado', async ({ page }) => {
    const api = apiVacia();
    api.versiones = [version()];
    api.selecciones = [seleccionGuardada({ id: 1, nombre: 'Preventiva' }), seleccionGuardada({ id: 2, nombre: 'Otra' })];
    await montarApi(page, api);

    await page.goto('/cartera');
    await page.getByLabel('Selección guardada').selectOption({ label: 'Preventiva' });
    await page.getByLabel('Cantidad (primeros n)').fill('250');
    await page.getByLabel('Selección guardada').selectOption({ label: 'Otra' });

    const dialogo = page.getByRole('dialog', { name: 'Hay cambios sin guardar' });
    await expect(dialogo).toBeVisible();
    await expect(dialogo.getByRole('button', { name: 'Seguir editando' })).toBeFocused();
    await dialogo.getByRole('button', { name: 'Seguir editando' }).click();

    await expect(page.getByLabel('Cantidad (primeros n)')).toHaveValue('250');
    await expect(page.getByLabel('Selección guardada')).toHaveValue('1');
  });
});

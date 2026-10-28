/**
 * The order of the filters, in Cartera (T-FV-F3, RF-68, docs/filtro-valores-interfaz.md §3): a number on every row,
 * «Subir» and «Bajar» as the keyboard's and the finger's way, a handle for the pointer, the focus that follows the
 * filter, the announcement, the lists below that ask again, and the order that is saved with the selection.
 * Against an intercepted API; every name and value is synthetic.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import { apiVacia, montarApi, seleccionGuardada, version, type ApiFalsa } from './api-falsa';

test.use({ reducedMotion: 'reduce' });

type Valores = Array<{ valor: string | null; cantidad: number }>;

const LISTAS: Record<string, Valores> = {
  region: [
    { valor: 'CUSCO SUR', cantidad: 1820 },
    { valor: 'TACNA', cantidad: 96 },
  ],
  segmento_financiero: [
    { valor: '1. Preventiva', cantidad: 900 },
    { valor: 'Sin asignar', cantidad: 20 },
  ],
};

async function abrir(page: Page, ajustar?: (api: ApiFalsa) => void, conListas = false) {
  const api = apiVacia();
  api.versiones = [version()];
  ajustar?.(api);
  if (conListas) {
    api.valores = (url) => {
      const campo = url.searchParams.get('campo') ?? '';
      return { estado: 200, cuerpo: { campo, umbral: 100, ofrece_lista: true, valores: LISTAS[campo] ?? [] } };
    };
  }
  await montarApi(page, api);
  await page.goto('/cartera');
  await expect(page.locator('[data-disponibles]')).toHaveText('3,200');
  return api;
}

const filas = (page: Page) => page.locator('[data-filtros] > .fila');
const fila = (page: Page, i: number) => filas(page).nth(i);
const subir = (page: Page, i: number) => fila(page, i).locator('[data-mover="subir"]');
const bajar = (page: Page, i: number) => fila(page, i).locator('[data-mover="bajar"]');
const anuncio = (page: Page) => page.locator('[data-orden-anuncio]');
const campos = async (page: Page) => filas(page).evaluateAll((nodos) => nodos.map((n) => (n.querySelector('.fila__campo') as HTMLSelectElement).value));

async function nuevoFiltro(page: Page, campo: string, operador?: string, valor?: string) {
  await page.getByRole('button', { name: 'Agregar filtro' }).click();
  const i = (await filas(page).count()) - 1;
  if (campo) await fila(page, i).getByLabel('Campo').selectOption(campo);
  if (operador) await fila(page, i).getByLabel('Operador').selectOption(operador);
  if (valor !== undefined) await fila(page, i).getByLabel('Valor').fill(valor);
  return i;
}

const dias = (page: Page) => nuevoFiltro(page, 'dias_atraso', 'mayor', '30');
const region = (page: Page) => nuevoFiltro(page, 'region', 'igual', 'TACNA');

const filtrosEnviados = (api: ApiFalsa) =>
  api.pedidos
    .filter((p) => new URL(p.url).pathname === '/api/cartera/resumen')
    .map((p) => new URL(p.url).searchParams.getAll('filtro'))
    .at(-1);

const pedidosDeValores = (api: ApiFalsa, campo: string) =>
  api.pedidos.filter((p) => new URL(p.url).pathname === '/api/cartera/valores').map((p) => new URL(p.url)).filter((u) => u.searchParams.get('campo') === campo);

test.describe('cómo se ve', () => {
  test('con un solo filtro no hay número, ni controles de orden, ni nota', async ({ page }) => {
    await abrir(page);

    await dias(page);

    await expect(page.locator('.fila__numero')).toHaveCount(0);
    await expect(page.locator('[data-mover]')).toHaveCount(0);
    await expect(page.locator('.fila__asa')).toHaveCount(0);
    await expect(page.locator('[data-orden-hint]')).toBeHidden();
  });

  test('con dos aparecen el número, el asa, «Subir» y «Bajar» en cada fila, y la nota una sola vez', async ({ page }) => {
    await abrir(page);
    await dias(page);

    await region(page);

    await expect(page.locator('.fila__numero')).toHaveText(['1', '2']);
    await expect(page.locator('.fila__asa')).toHaveCount(2);
    await expect(subir(page, 1)).toHaveAccessibleName('Subir el filtro «Región»');
    await expect(bajar(page, 0)).toHaveAccessibleName('Bajar el filtro «Días de atraso»');
    await expect(page.locator('[data-orden-hint]')).toBeVisible();
    await expect(page.locator('[data-orden-hint]')).toHaveText('El orden no cambia el resultado: cada filtro muestra los valores que quedan con los de arriba.');
    await expect(page.locator('[data-orden-hint]')).toHaveCount(1);
  });

  test('el primero no sube y el último no baja', async ({ page }) => {
    await abrir(page);
    await dias(page);
    await region(page);
    await nuevoFiltro(page, 'monto_cuota', 'mayor', '100');

    await expect(subir(page, 0)).toBeDisabled();
    await expect(bajar(page, 0)).toBeEnabled();
    await expect(subir(page, 1)).toBeEnabled();
    await expect(bajar(page, 1)).toBeEnabled();
    await expect(subir(page, 2)).toBeEnabled();
    await expect(bajar(page, 2)).toBeDisabled();
  });

  test('el asa es solo para el puntero: oculta al lector de pantalla y fuera del tabulador, con su nombre en title', async ({ page }) => {
    await abrir(page);
    await dias(page);
    await region(page);

    const asa = page.locator('.fila__asa').nth(1);

    await expect(asa).toHaveAttribute('aria-hidden', 'true');
    await expect(asa).toHaveAttribute('tabindex', '-1');
    await expect(asa).toHaveAttribute('title', 'Arrastrar el filtro «Región»');
  });

  test('un filtro sin campo elegido se nombra «Filtro n»', async ({ page }) => {
    await abrir(page);
    await dias(page);

    await nuevoFiltro(page, '');

    await expect(subir(page, 1)).toHaveAccessibleName('Subir el filtro «Filtro 2»');
  });

  test('al quitar hasta quedar uno, desaparecen el número, los controles y la nota', async ({ page }) => {
    await abrir(page);
    await dias(page);
    await region(page);

    await fila(page, 1).getByRole('button', { name: 'Quitar filtro' }).click();

    await expect(page.locator('.fila__numero')).toHaveCount(0);
    await expect(page.locator('[data-mover]')).toHaveCount(0);
    await expect(page.locator('[data-orden-hint]')).toBeHidden();
  });
});

test.describe('Subir y Bajar', () => {
  test('«Subir» mueve el filtro, renumera, lo anuncia y el foco va al otro botón si llegó al borde', async ({ page }) => {
    await abrir(page);
    await dias(page);
    await region(page);

    await subir(page, 1).click();

    expect(await campos(page)).toEqual(['region', 'dias_atraso']);
    await expect(page.locator('.fila__numero')).toHaveText(['1', '2']);
    await expect(anuncio(page)).toHaveText('Movido «Región» a la posición 1 de 2.');
    // «Subir» is off in the first place, so the focus goes to «Bajar» of the same filter.
    await expect(bajar(page, 0)).toBeFocused();
  });

  test('«Bajar» desde el primero: el foco queda en el «Bajar» de su fila nueva mientras siga activo', async ({ page }) => {
    await abrir(page);
    await dias(page);
    await region(page);
    await nuevoFiltro(page, 'monto_cuota', 'mayor', '100');

    await bajar(page, 0).click();

    expect(await campos(page)).toEqual(['region', 'dias_atraso', 'monto_cuota']);
    await expect(anuncio(page)).toHaveText('Movido «Días de atraso» a la posición 2 de 3.');
    await expect(bajar(page, 1)).toBeFocused();
  });

  test('lo escrito en cada filtro viaja con él', async ({ page }) => {
    await abrir(page);
    await dias(page);
    await region(page);

    await bajar(page, 0).click();

    await expect(fila(page, 0).getByLabel('Valor')).toHaveValue('TACNA');
    await expect(fila(page, 1).getByLabel('Valor')).toHaveValue('30');
    await expect(fila(page, 1).getByLabel('Operador')).toHaveValue('mayor');
  });

  test('mover emite el cambio con el orden nuevo: la consulta lo lleva, y los totales no cambian', async ({ page }) => {
    const api = await abrir(page);
    await dias(page);
    await region(page);
    await expect.poll(() => filtrosEnviados(api)).toEqual(['dias_atraso:mayor:30', 'region:igual:TACNA']);
    const antes = await page.locator('[data-disponibles]').textContent();

    await subir(page, 1).click();

    await expect.poll(() => filtrosEnviados(api)).toEqual(['region:igual:TACNA', 'dias_atraso:mayor:30']);
    await expect(page.locator('[data-disponibles]')).toHaveText(antes ?? '');
  });

  test('un filtro incompleto también se mueve, y la consulta sigue dejándolo fuera', async ({ page }) => {
    const api = await abrir(page);
    await dias(page);
    await nuevoFiltro(page, 'region', 'igual');

    await subir(page, 1).click();

    expect(await campos(page)).toEqual(['region', 'dias_atraso']);
    await expect(fila(page, 0)).toHaveAttribute('data-estado', 'incompleta');
    await expect.poll(() => filtrosEnviados(api)).toEqual(['dias_atraso:mayor:30']);
  });
});

test.describe('las listas de abajo', () => {
  test('mover recalcula las listas de los filtros que quedaron debajo de otro, no las demás', async ({ page }) => {
    const api = await abrir(page, undefined, true);
    const a = await nuevoFiltro(page, 'region');
    await fila(page, a).getByRole('checkbox', { name: /^TACNA/ }).check();
    const b = await nuevoFiltro(page, 'segmento_financiero');
    await fila(page, b).getByRole('checkbox', { name: /^Sin asignar/ }).check();
    await expect(fila(page, b).getByRole('group', { name: 'Valores de Segmento financiero' })).toContainText('1 de 2 marcados');
    await page.waitForTimeout(500);
    const regionAntes = pedidosDeValores(api, 'region').length;

    await subir(page, 1).click();

    // The segment filter is now first: the region list asks again, with the segment above it.
    await expect.poll(() => pedidosDeValores(api, 'region').length).toBeGreaterThan(regionAntes);
    expect(pedidosDeValores(api, 'region').at(-1)!.searchParams.getAll('filtro')).toEqual(['segmento_financiero:en:Sin asignar']);
    // And what was checked in each travels with it.
    await expect(fila(page, 0).getByRole('checkbox', { name: /^Sin asignar/ })).toBeChecked();
    await expect(fila(page, 1).getByRole('checkbox', { name: /^TACNA/ })).toBeChecked();
    await expect.poll(() => filtrosEnviados(api)).toEqual(['segmento_financiero:en:Sin asignar', 'region:en:TACNA']);
  });
});

test.describe('arrastrar', () => {
  async function arrastrar(page: Page, desde: number, haciaFila: number, soltar = true) {
    const asa = (await page.locator('.fila__asa').nth(desde).boundingBox())!;
    const destino = (await fila(page, haciaFila).boundingBox())!;
    await page.mouse.move(asa.x + asa.width / 2, asa.y + asa.height / 2);
    await page.mouse.down();
    // Past the centre of the row it should land on.
    await page.mouse.move(asa.x + asa.width / 2, destino.y + (haciaFila < desde ? 2 : destino.height - 2), { steps: 6 });
    if (soltar) await page.mouse.up();
  }

  test('soltar el asa sobre otra fila mueve el filtro, renumera y lo anuncia', async ({ page }) => {
    const api = await abrir(page);
    await dias(page);
    await region(page);
    await expect.poll(() => filtrosEnviados(api)).toEqual(['dias_atraso:mayor:30', 'region:igual:TACNA']);

    await arrastrar(page, 1, 0);

    expect(await campos(page)).toEqual(['region', 'dias_atraso']);
    await expect(anuncio(page)).toHaveText('Movido «Región» a la posición 1 de 2.');
    await expect.poll(() => filtrosEnviados(api)).toEqual(['region:igual:TACNA', 'dias_atraso:mayor:30']);
  });

  test('mientras se arrastra, la fila sigue al puntero y una línea marca dónde caerá', async ({ page }) => {
    await abrir(page);
    await dias(page);
    await region(page);

    await arrastrar(page, 1, 0, false);

    await expect(fila(page, 1)).toHaveClass(/fila--arrastrada/);
    await expect(fila(page, 0)).toHaveClass(/fila--cae-antes/);
    await page.mouse.up();
    await expect(page.locator('.fila--arrastrada')).toHaveCount(0);
    await expect(page.locator('.fila--cae-antes')).toHaveCount(0);
  });

  test('Escape mientras se arrastra cancela: la fila vuelve a su lugar y se dice', async ({ page }) => {
    const api = await abrir(page);
    await dias(page);
    await region(page);
    await expect.poll(() => filtrosEnviados(api)).toEqual(['dias_atraso:mayor:30', 'region:igual:TACNA']);
    const pedidos = api.pedidos.length;

    await arrastrar(page, 1, 0, false);
    await page.keyboard.press('Escape');
    await page.mouse.up();

    expect(await campos(page)).toEqual(['dias_atraso', 'region']);
    await expect(anuncio(page)).toHaveText('Movimiento cancelado.');
    await expect(page.locator('.fila--arrastrada')).toHaveCount(0);
    await page.waitForTimeout(700);
    expect(filtrosEnviados(api)).toEqual(['dias_atraso:mayor:30', 'region:igual:TACNA']);
    expect(api.pedidos.length).toBe(pedidos);
  });

  test('soltarla donde estaba no mueve nada ni avisa', async ({ page }) => {
    await abrir(page);
    await dias(page);
    await region(page);

    await arrastrar(page, 0, 0);

    expect(await campos(page)).toEqual(['dias_atraso', 'region']);
    await expect(anuncio(page)).toHaveText('');
  });
});

test.describe('el orden se guarda con la selección', () => {
  const guardada = () =>
    seleccionGuardada({ id: 7, nombre: 'Dos filtros', filtros: ['dias_atraso:mayor:30', 'region:igual:TACNA'], orden: null, cantidad: null });

  test('mover una selección guardada cuenta como cambio sin guardar, y descartar la deja como estaba', async ({ page }) => {
    await abrir(page, (api) => (api.selecciones = [guardada()]));
    await page.getByLabel('Selección guardada').selectOption({ label: 'Dos filtros' });
    await expect(page.locator('[data-selector-estado]')).toHaveText('«Dos filtros», sin cambios.');

    await subir(page, 1).click();

    await expect(page.locator('[data-selector-estado]')).toHaveText('«Dos filtros», con cambios sin guardar.');
    await expect(page.getByRole('button', { name: 'Guardar cambios' })).toBeEnabled();

    await page.getByRole('button', { name: 'Descartar cambios' }).click();
    expect(await campos(page)).toEqual(['dias_atraso', 'region']);
  });

  test('guardar manda los filtros en el orden nuevo, y al abrirla otra vez vuelve en ese orden', async ({ page }) => {
    const api = await abrir(page, (a) => (a.selecciones = [guardada()]));
    await page.getByLabel('Selección guardada').selectOption({ label: 'Dos filtros' });
    await subir(page, 1).click();

    await page.getByRole('button', { name: 'Guardar cambios' }).click();

    await expect(page.locator('[data-selector-estado]')).toHaveText('«Dos filtros», sin cambios.');
    const guardado = api.pedidos.filter((p) => p.metodo === 'PUT' && p.url.endsWith('/api/selecciones/7')).at(-1);
    expect(JSON.parse(guardado?.cuerpo ?? '{}').filtros).toEqual(['region:igual:TACNA', 'dias_atraso:mayor:30']);

    await page.reload();
    await expect(page.locator('[data-disponibles]')).toHaveText('3,200');
    await page.getByLabel('Selección guardada').selectOption({ label: 'Dos filtros' });
    expect(await campos(page)).toEqual(['region', 'dias_atraso']);
    await expect(page.locator('.fila__numero')).toHaveText(['1', '2']);
  });

  test('guardar como nueva también lleva el orden nuevo', async ({ page }) => {
    const api = await abrir(page);
    await dias(page);
    await region(page);
    await subir(page, 1).click();

    await page.getByRole('button', { name: 'Guardar como nueva' }).click();
    const dialogo = page.getByRole('dialog', { name: 'Guardar la selección' });
    await dialogo.getByLabel('Nombre').fill('Orden nuevo');
    await dialogo.getByRole('button', { name: 'Guardar', exact: true }).click();

    await expect(dialogo).toBeHidden();
    const creado = api.pedidos.filter((p) => p.metodo === 'POST' && p.url.endsWith('/api/selecciones')).at(-1);
    expect(JSON.parse(creado?.cuerpo ?? '{}').filtros).toEqual(['region:igual:TACNA', 'dias_atraso:mayor:30']);
  });
});

// ---- axe ------------------------------------------------------------------------------------

const REGLAS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

async function sinViolaciones(page: Page): Promise<void> {
  // The totals are dimmed while they recalculate; axe would read the dimmed contrast.
  await expect(page.locator('[data-metricas]')).toHaveAttribute('data-calculando', 'false');
  const resultado = await new AxeBuilder({ page }).withTags(REGLAS).analyze();
  expect(resultado.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
}

for (const tema of ['light', 'dark'] as const) {
  test.describe(`axe del orden de los filtros, tema ${tema === 'light' ? 'claro' : 'oscuro'}`, () => {
    test.beforeEach(async ({ page }) => {
      await page.addInitScript((elegido) => {
        localStorage.setItem('app:appearance', JSON.stringify({ theme: elegido, language: 'es' }));
      }, tema);
    });

    test('las filas con sus controles de orden y la nota', async ({ page }) => {
      await abrir(page);
      await dias(page);
      await region(page);
      await nuevoFiltro(page, 'monto_cuota', 'mayor', '100');
      await sinViolaciones(page);
    });

    test('tras mover, con el anuncio dicho', async ({ page }) => {
      await abrir(page);
      await dias(page);
      await region(page);
      await subir(page, 1).click();
      await expect(anuncio(page)).not.toHaveText('');
      await sinViolaciones(page);
    });
  });
}

test('a 360 px las filas con orden caben sin desplazar la página de lado y los botones se alcanzan', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await abrir(page);
  await dias(page);
  await region(page);

  const desborde = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(desborde).toBeLessThanOrEqual(0);
  await bajar(page, 0).focus();
  await page.keyboard.press('Enter');
  expect(await campos(page)).toEqual(['region', 'dias_atraso']);
  await expect(bajar(page, 1)).toBeDisabled();
  await sinViolaciones(page);
});

/**
 * The list of values of a list filter, in Cartera (T-FV-F2, RF-67, docs/filtro-valores-interfaz.md §2 and §7): a text
 * field with «es uno de» or «no es ninguno de» picks from the real values of the date, each filter asks for its own
 * list with the ones above it, and a failure leaves the work on a text area. Against an intercepted API; every
 * value, field and amount is synthetic.
 */
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import { apiVacia, montarApi, seleccionGuardada, version, type ApiFalsa } from './api-falsa';

test.use({ reducedMotion: 'reduce' });

type Valores = Array<{ valor: string | null; cantidad: number }>;

const REGIONES: Valores = [
  { valor: 'CUSCO SUR', cantidad: 1820 },
  { valor: 'TACNA', cantidad: 96 },
  { valor: 'Ñuñoa', cantidad: 40 },
  { valor: null, cantidad: 12 },
];

const SEGMENTOS: Valores = [
  { valor: '1. Preventiva', cantidad: 900 },
  { valor: '2. Mora', cantidad: 300 },
  { valor: 'Sin asignar', cantidad: 20 },
];

interface Respuesta {
  estado?: number;
  umbral?: number;
  ofrece_lista?: boolean;
  valores?: Valores;
}

/** What `GET /cartera/valores` answers for a field, given the filters above it (the cascade). */
type Responder = (campo: string, filtros: string[]) => Respuesta;

const POR_OMISION: Responder = (campo, filtros) => {
  if (campo === 'region') return { valores: REGIONES };
  if (campo === 'segmento_financiero') {
    // A TACNA filter above leaves no «Sin asignar».
    return { valores: filtros.includes('region:en:TACNA') ? SEGMENTOS.slice(0, 2) : SEGMENTOS };
  }
  return { ofrece_lista: false };
};

async function abrir(page: Page, responder: Responder = POR_OMISION, ajustar?: (api: ApiFalsa) => void) {
  const api = apiVacia();
  api.versiones = [version()];
  ajustar?.(api);
  api.valores = (url) => {
    const campo = url.searchParams.get('campo') ?? '';
    const respuesta = responder(campo, url.searchParams.getAll('filtro'));
    if (respuesta.estado && respuesta.estado !== 200) return { estado: respuesta.estado, cuerpo: { detail: 'fallo' } };
    const ofrece = respuesta.ofrece_lista ?? true;
    return {
      estado: 200,
      cuerpo: { campo, umbral: respuesta.umbral ?? 100, ofrece_lista: ofrece, valores: ofrece ? (respuesta.valores ?? []) : [] },
    };
  };
  await montarApi(page, api);
  await page.goto('/cartera');
  await expect(page.locator('[data-disponibles]')).toHaveText('3,200');
  return api;
}

const filas = (page: Page) => page.locator('[data-filtros] > .fila');
const fila = (page: Page, i: number) => filas(page).nth(i);
const lista = (page: Page, i: number, campo: string) => fila(page, i).getByRole('group', { name: `Valores de ${campo}` });
const casilla = (page: Page, i: number, campo: string, nombre: string | RegExp) =>
  lista(page, i, campo).getByRole('checkbox', { name: nombre });

async function nuevoFiltro(page: Page, campo: string, operador?: string) {
  await page.getByRole('button', { name: 'Agregar filtro' }).click();
  const i = (await filas(page).count()) - 1;
  await fila(page, i).getByLabel('Campo').selectOption(campo);
  if (operador) await fila(page, i).getByLabel('Operador').selectOption(operador);
  return i;
}

const pedidosDeValores = (api: ApiFalsa) => api.pedidos.filter((p) => new URL(p.url).pathname === '/api/cartera/valores').map((p) => new URL(p.url));
const delCampo = (api: ApiFalsa, campo: string) => pedidosDeValores(api).filter((url) => url.searchParams.get('campo') === campo);
const filtrosEnviados = (api: ApiFalsa) =>
  api.pedidos
    .filter((p) => new URL(p.url).pathname === '/api/cartera/resumen')
    .map((p) => new URL(p.url).searchParams.getAll('filtro'))
    .at(-1);

test.describe('elegir de una lista', () => {
  test('un campo de texto empieza en «es uno de» y trae la lista en lugar del cuadro de texto', async ({ page }) => {
    await abrir(page);

    const i = await nuevoFiltro(page, 'region');

    await expect(fila(page, i).getByLabel('Operador')).toHaveValue('en');
    await expect(lista(page, i, 'Región').getByRole('checkbox').first()).toBeVisible();
    await expect(casilla(page, i, 'Región', 'CUSCO SUR, 1,820 productos')).toBeVisible();
    await expect(fila(page, i).locator('textarea')).toHaveCount(0);
  });

  test('un campo que no es de texto conserva su primer operador y su control de siempre', async ({ page }) => {
    const api = await abrir(page);

    const i = await nuevoFiltro(page, 'dias_atraso');

    await expect(fila(page, i).getByLabel('Operador')).toHaveValue('igual');
    await expect(fila(page, i).getByLabel('Valor')).toBeVisible();
    expect(pedidosDeValores(api)).toHaveLength(0);
  });

  test('marcar dos valores manda «es uno de» con esos valores', async ({ page }) => {
    const api = await abrir(page);
    const i = await nuevoFiltro(page, 'region');

    await casilla(page, i, 'Región', /^CUSCO SUR/).check();
    await casilla(page, i, 'Región', /^TACNA/).check();

    await expect.poll(() => filtrosEnviados(api)).toEqual(['region:en:CUSCO SUR|TACNA']);
    await expect(lista(page, i, 'Región')).toContainText('2 de 4 marcados');
  });

  test('sin nada marcado la fila queda incompleta y no filtra', async ({ page }) => {
    const api = await abrir(page);

    const i = await nuevoFiltro(page, 'region');

    await expect(fila(page, i)).toHaveAttribute('data-estado', 'incompleta');
    expect(filtrosEnviados(api) ?? []).toEqual([]);
  });

  test('pasar a «no es ninguno de» conserva lo marcado, cambia la línea de ayuda y manda no_en', async ({ page }) => {
    const api = await abrir(page);
    const i = await nuevoFiltro(page, 'region');
    await casilla(page, i, 'Región', /^TACNA/).check();
    await expect(lista(page, i, 'Región')).toContainText('Incluye los productos que tienen alguno de los valores marcados.');

    await fila(page, i).getByLabel('Operador').selectOption('no_en');

    await expect(casilla(page, i, 'Región', /^TACNA/)).toBeChecked();
    await expect(lista(page, i, 'Región')).toContainText('Excluye los productos que tienen alguno de los valores marcados. Los que no tienen valor quedan, salvo que marques «(vacío)».');
    await expect.poll(() => filtrosEnviados(api)).toEqual(['region:no_en:TACNA']);
    // The list is the same one: switching include for exclude does not ask for it again.
    expect(delCampo(api, 'region')).toHaveLength(1);
  });

  test('la lista es un grupo con leyenda, casillas nativas y la línea de ayuda como descripción', async ({ page }) => {
    await abrir(page);
    const i = await nuevoFiltro(page, 'region');

    await expect(lista(page, i, 'Región')).toHaveAccessibleDescription(/Incluye los productos/);
    await expect(fila(page, i).locator('fieldset input[type="checkbox"]').first()).toBeVisible();
  });
});

test.describe('«(vacío)»', () => {
  test('va al final, con su cantidad, y marcarlo manda el elemento vacío', async ({ page }) => {
    const api = await abrir(page);
    const i = await nuevoFiltro(page, 'region');

    const nombres = await lista(page, i, 'Región').locator('.valores__lista .valores__texto').allTextContents();
    expect(nombres).toEqual(['CUSCO SUR', 'TACNA', 'Ñuñoa', '(vacío)']);
    await expect(lista(page, i, 'Región').locator('em.valores__texto')).toHaveText('(vacío)');

    await casilla(page, i, 'Región', /^TACNA/).check();
    await casilla(page, i, 'Región', '(vacío), 12 productos').check();

    await expect.poll(() => filtrosEnviados(api)).toEqual(['region:en:TACNA|']);
  });

  test('solo el vacío es un filtro completo: «con valor» se dice «no es ninguno de» + (vacío)', async ({ page }) => {
    const api = await abrir(page);
    const i = await nuevoFiltro(page, 'region', 'no_en');

    await casilla(page, i, 'Región', /^\(vacío\)/).check();

    await expect(fila(page, i)).toHaveAttribute('data-estado', 'ok');
    await expect.poll(() => filtrosEnviados(api)).toEqual(['region:no_en:']);
  });

  test('no aparece si nadie está sin valor', async ({ page }) => {
    await abrir(page, (campo) => (campo === 'region' ? { valores: REGIONES.filter((v) => v.valor !== null) } : {}));

    const i = await nuevoFiltro(page, 'region');

    await expect(lista(page, i, 'Región').getByRole('checkbox').first()).toBeVisible();
    await expect(lista(page, i, 'Región').getByRole('checkbox', { name: /vacío/ })).toHaveCount(0);
  });

  test('si ya estaba marcado, aparece aunque nadie lo tenga, con 0 productos', async ({ page }) => {
    await abrir(page, (campo) => (campo === 'region' ? { valores: REGIONES.filter((v) => v.valor !== null) } : {}), (api) => {
      api.selecciones = [seleccionGuardada({ id: 2, nombre: 'Con vacío', filtros: ['region:en:TACNA|'], orden: null, cantidad: null })];
    });

    await page.getByLabel('Selección guardada').selectOption({ label: 'Con vacío' });

    await expect(lista(page, 0, 'Región').getByRole('checkbox', { name: '(vacío), 0 productos' })).toBeChecked();
  });
});

test.describe('muchos valores', () => {
  const MUCHOS: Valores = Array.from({ length: 14 }, (_, n) => ({ valor: `Región ${String(n + 1).padStart(2, '0')}`, cantidad: 100 - n })).concat([
    { valor: 'Ñuñoa', cantidad: 3 },
  ]);

  test('con más de 10 aparece la búsqueda, sin mayúsculas ni tildes, y no desmarca lo que oculta', async ({ page }) => {
    await abrir(page, (campo) => (campo === 'region' ? { valores: MUCHOS } : {}));
    const i = await nuevoFiltro(page, 'region');
    await casilla(page, i, 'Región', /^Región 01/).check();
    const buscar = lista(page, i, 'Región').getByRole('searchbox', { name: 'Buscar un valor' });

    await buscar.fill('NUNOA');

    await expect(lista(page, i, 'Región').getByRole('checkbox')).toHaveCount(1);
    await expect(casilla(page, i, 'Región', /^Ñuñoa/)).toBeVisible();
    // The one checked and hidden still counts.
    await expect(lista(page, i, 'Región')).toContainText('1 de 15 marcados');
    await expect(buscar).toBeFocused();

    await buscar.fill('zzz');
    await expect(lista(page, i, 'Región')).toContainText('Ningún valor contiene «zzz».');

    await buscar.fill('');
    await expect(casilla(page, i, 'Región', /^Región 01/)).toBeChecked();
  });

  test('con 10 o menos no hay búsqueda', async ({ page }) => {
    await abrir(page);
    const i = await nuevoFiltro(page, 'region');
    // The loading placeholder is a group too: wait for the values, or "no search box" is true for the wrong reason.
    await expect(lista(page, i, 'Región').getByRole('checkbox').first()).toBeVisible();

    await expect(lista(page, i, 'Región').getByRole('searchbox')).toHaveCount(0);
  });

  test('«Desmarcar todos» aparece con algo marcado, lo quita todo y deja la fila incompleta', async ({ page }) => {
    await abrir(page);
    const i = await nuevoFiltro(page, 'region');
    const desmarcar = lista(page, i, 'Región').getByRole('button', { name: 'Desmarcar todos' });
    await expect(lista(page, i, 'Región').getByRole('checkbox').first()).toBeVisible();
    await expect(desmarcar).toHaveCount(0);
    await casilla(page, i, 'Región', /^TACNA/).check();
    await casilla(page, i, 'Región', /^\(vacío\)/).check();

    await desmarcar.click();

    await expect(lista(page, i, 'Región')).toContainText('0 de 4 marcados');
    await expect(casilla(page, i, 'Región', /^TACNA/)).not.toBeChecked();
    await expect(fila(page, i)).toHaveAttribute('data-estado', 'incompleta');
  });
});

test.describe('lo que no ofrece lista', () => {
  test('un campo sobre el umbral vuelve al cuadro de texto, con el aviso y el umbral de la respuesta', async ({ page }) => {
    await abrir(page, () => ({ ofrece_lista: false, umbral: 250 }));

    const i = await nuevoFiltro(page, 'region');

    await expect(fila(page, i).locator('textarea')).toBeVisible();
    await expect(fila(page, i)).toContainText('Este campo tiene más de 250 valores distintos en esta fecha: escribe los valores, uno por línea.');
    await expect(lista(page, i, 'Región')).toHaveCount(0);
  });

  test('sin versión vigente (404) o un campo que no es de texto (400) no se reporta en la fila: cuadro de texto de siempre', async ({ page }) => {
    for (const estado of [404, 400]) {
      await abrir(page, () => ({ estado }));
      const i = await nuevoFiltro(page, 'region');

      await expect(fila(page, i).locator('textarea')).toBeVisible();
      await expect(fila(page, i).getByRole('alert')).toHaveCount(0);
      await page.reload();
    }
  });

  test('una selección guardada conserva su operador: el de «igual» no pasa a «es uno de»', async ({ page }) => {
    const api = await abrir(page, POR_OMISION, (a) => {
      a.selecciones = [seleccionGuardada({ id: 3, nombre: 'Una región', filtros: ['region:igual:TACNA'], orden: null, cantidad: null })];
    });

    await page.getByLabel('Selección guardada').selectOption({ label: 'Una región' });

    await expect(fila(page, 0).getByLabel('Operador')).toHaveValue('igual');
    await expect(fila(page, 0).getByLabel('Valor')).toHaveValue('TACNA');
    expect(pedidosDeValores(api)).toHaveLength(0);
  });

  test('una selección guardada con «es uno de» se abre con su lista y sus valores marcados', async ({ page }) => {
    await abrir(page, POR_OMISION, (a) => {
      a.selecciones = [seleccionGuardada({ id: 4, nombre: 'Dos regiones', filtros: ['region:en:CUSCO SUR|TACNA'], orden: null, cantidad: null })];
    });

    await page.getByLabel('Selección guardada').selectOption({ label: 'Dos regiones' });

    await expect(casilla(page, 0, 'Región', /^CUSCO SUR/)).toBeChecked();
    await expect(casilla(page, 0, 'Región', /^TACNA/)).toBeChecked();
    await expect(casilla(page, 0, 'Región', /^Ñuñoa/)).not.toBeChecked();
  });
});

test.describe('la cascada', () => {
  test('la lista de abajo pide la fecha y los filtros completos de arriba', async ({ page }) => {
    const api = await abrir(page);
    const i = await nuevoFiltro(page, 'region');
    await casilla(page, i, 'Región', /^TACNA/).check();

    await nuevoFiltro(page, 'segmento_financiero');

    await expect(lista(page, 1, 'Segmento financiero').getByRole('checkbox').first()).toBeVisible();
    const pedido = delCampo(api, 'segmento_financiero').at(-1)!;
    expect(pedido.searchParams.get('fecha_corte')).toBe('2026-09-10');
    expect(pedido.searchParams.getAll('filtro')).toEqual(['region:en:TACNA']);
  });

  test('un filtro de arriba incompleto no cuenta', async ({ page }) => {
    const api = await abrir(page);
    await nuevoFiltro(page, 'region');

    await nuevoFiltro(page, 'segmento_financiero');

    await expect(lista(page, 1, 'Segmento financiero').getByRole('checkbox').first()).toBeVisible();
    expect(delCampo(api, 'segmento_financiero').at(-1)!.searchParams.getAll('filtro')).toEqual([]);
  });

  test('cambiar un filtro de arriba recalcula solo las listas de abajo, tras la espera, y conserva lo marcado', async ({ page }) => {
    const api = await abrir(page);
    const a = await nuevoFiltro(page, 'region');
    await casilla(page, a, 'Región', /^TACNA/).check();
    const b = await nuevoFiltro(page, 'segmento_financiero');
    await casilla(page, b, 'Segmento financiero', /^1\. Preventiva/).check();
    await expect(lista(page, b, 'Segmento financiero')).toContainText('1 de 2 marcados');
    const regionAntes = delCampo(api, 'region').length;
    const segmentoAntes = delCampo(api, 'segmento_financiero').length;

    await casilla(page, a, 'Región', /^CUSCO SUR/).check();

    await expect.poll(() => delCampo(api, 'segmento_financiero').length).toBe(segmentoAntes + 1);
    expect(delCampo(api, 'segmento_financiero').at(-1)!.searchParams.getAll('filtro')).toEqual(['region:en:TACNA|CUSCO SUR']);
    expect(delCampo(api, 'region')).toHaveLength(regionAntes);
    await expect(casilla(page, b, 'Segmento financiero', /^1\. Preventiva/)).toBeChecked();
  });

  test('varios cambios seguidos arriba piden la lista de abajo una sola vez', async ({ page }) => {
    const api = await abrir(page);
    const a = await nuevoFiltro(page, 'region');
    await casilla(page, a, 'Región', /^TACNA/).check();
    await nuevoFiltro(page, 'segmento_financiero');
    await expect(lista(page, 1, 'Segmento financiero').getByRole('checkbox').first()).toBeVisible();
    const antes = delCampo(api, 'segmento_financiero').length;

    await casilla(page, a, 'Región', /^CUSCO SUR/).check();
    await casilla(page, a, 'Región', /^Ñuñoa/).check();
    await casilla(page, a, 'Región', /^CUSCO SUR/).uncheck();
    await page.waitForTimeout(800);

    expect(delCampo(api, 'segmento_financiero')).toHaveLength(antes + 1);
    expect(delCampo(api, 'segmento_financiero').at(-1)!.searchParams.getAll('filtro')).toEqual(['region:en:TACNA|Ñuñoa']);
  });

  test('marcar, desmarcar y volver a marcar dentro de la espera pide la lista de abajo una sola vez', async ({ page }) => {
    const api = await abrir(page);
    const a = await nuevoFiltro(page, 'region');
    await casilla(page, a, 'Región', /^TACNA/).check();
    await nuevoFiltro(page, 'segmento_financiero');
    await expect(lista(page, 1, 'Segmento financiero').getByRole('checkbox').first()).toBeVisible();
    const antes = delCampo(api, 'segmento_financiero').length;

    await casilla(page, a, 'Región', /^CUSCO SUR/).check();
    await casilla(page, a, 'Región', /^CUSCO SUR/).uncheck();
    await casilla(page, a, 'Región', /^CUSCO SUR/).check();
    await page.waitForTimeout(800);

    // The same question twice must not leave two requests alive: the wait is restarted, not stacked.
    expect(delCampo(api, 'segmento_financiero')).toHaveLength(antes + 1);
  });

  test('un valor marcado que se queda sin productos va aparte, con el aviso, y se manda igual', async ({ page }) => {
    const api = await abrir(page);
    const a = await nuevoFiltro(page, 'region');
    const b = await nuevoFiltro(page, 'segmento_financiero');
    await casilla(page, b, 'Segmento financiero', /^Sin asignar/).check();
    await expect(lista(page, b, 'Segmento financiero')).toContainText('1 de 3 marcados');

    await casilla(page, a, 'Región', /^TACNA/).check();

    const aparte = fila(page, b).getByRole('group', { name: 'Marcados sin productos con los filtros de arriba' });
    await expect(aparte).toBeVisible();
    await expect(aparte).toContainText('Ningún producto tiene estos valores con los filtros de arriba. Siguen marcados: desmárcalos si ya no los necesitas.');
    await expect(aparte.getByRole('checkbox', { name: 'Sin asignar, 0 productos' })).toBeChecked();
    await expect(aparte.locator('.tag')).toHaveText('Sin productos');
    await expect(lista(page, b, 'Segmento financiero')).toContainText('1 de 3 marcados');
    await expect.poll(() => filtrosEnviados(api)).toEqual(['region:en:TACNA', 'segmento_financiero:en:Sin asignar']);
  });

  test('si el valor vuelve a tener productos regresa a su lugar; si se desmarca aparte, desaparece', async ({ page }) => {
    await abrir(page);
    const a = await nuevoFiltro(page, 'region');
    const b = await nuevoFiltro(page, 'segmento_financiero');
    await casilla(page, b, 'Segmento financiero', /^Sin asignar/).check();
    await casilla(page, a, 'Región', /^TACNA/).check();
    const aparte = fila(page, b).getByRole('group', { name: 'Marcados sin productos con los filtros de arriba' });
    await expect(aparte).toBeVisible();

    await casilla(page, a, 'Región', /^TACNA/).uncheck();
    await casilla(page, a, 'Región', /^CUSCO SUR/).check();

    await expect(aparte).toBeHidden();
    await expect(casilla(page, b, 'Segmento financiero', /^Sin asignar/)).toBeChecked();

    await casilla(page, a, 'Región', /^CUSCO SUR/).uncheck();
    await casilla(page, a, 'Región', /^TACNA/).check();
    await expect(aparte).toBeVisible();
    await aparte.getByRole('checkbox').click();
    await expect(aparte).toBeHidden();
  });

  test('mientras recalcula, la lista anterior queda a la vista y operable, y lo dice con aria-busy y el texto, no con opacidad', async ({ page }) => {
    const api = await abrir(page);
    const a = await nuevoFiltro(page, 'region');
    const b = await nuevoFiltro(page, 'segmento_financiero');
    await expect(lista(page, b, 'Segmento financiero').getByRole('checkbox').first()).toBeVisible();
    let liberar!: () => void;
    const espera = new Promise<void>((resolver) => (liberar = resolver));
    await page.route('**/api/cartera/valores*', async (route) => {
      if (new URL(route.request().url()).searchParams.get('campo') === 'segmento_financiero') await espera;
      await route.fallback();
    });

    await casilla(page, a, 'Región', /^TACNA/).check();

    await expect(lista(page, b, 'Segmento financiero')).toHaveAttribute('aria-busy', 'true');
    await expect(lista(page, b, 'Segmento financiero')).toContainText('Actualizando valores…');
    // The counts are small and muted: dimming them would leave them under AA, so the list keeps its full colour.
    await expect(lista(page, b, 'Segmento financiero').locator('.valores__lista')).toHaveCSS('opacity', '1');
    await casilla(page, b, 'Segmento financiero', /^2\. Mora/).check();
    await expect(casilla(page, b, 'Segmento financiero', /^2\. Mora/)).toBeChecked();

    liberar();

    await expect(lista(page, b, 'Segmento financiero')).toHaveAttribute('aria-busy', 'false');
    await expect(lista(page, b, 'Segmento financiero')).not.toContainText('Actualizando valores…');
    await expect(casilla(page, b, 'Segmento financiero', /^2\. Mora/)).toBeChecked();
    expect(delCampo(api, 'segmento_financiero').length).toBeGreaterThan(1);
  });

  test('un campo sobre el umbral no se vuelve lista porque cambie un filtro de arriba', async ({ page }) => {
    const api = await abrir(page, (campo, filtros) => (campo === 'region' ? { valores: REGIONES } : { ofrece_lista: false, umbral: filtros.length ? 999 : 100 }));
    const a = await nuevoFiltro(page, 'region');
    const b = await nuevoFiltro(page, 'segmento_financiero');
    await expect(fila(page, b).locator('textarea')).toBeVisible();
    const antes = delCampo(api, 'segmento_financiero').length;

    await casilla(page, a, 'Región', /^TACNA/).check();
    await page.waitForTimeout(700);

    await expect(fila(page, b).locator('textarea')).toBeVisible();
    await expect(fila(page, b)).toContainText('más de 100 valores');
    expect(delCampo(api, 'segmento_financiero')).toHaveLength(antes);
  });

  test('cambiar la fecha de corte pide de nuevo la lista de cada filtro', async ({ page }) => {
    const api = await abrir(page, POR_OMISION, (a) => {
      a.versiones = [version({ id: 8, fecha_corte: '2026-09-11', vigente: true }), version({ id: 7, fecha_corte: '2026-09-10', vigente: true })];
    });
    await nuevoFiltro(page, 'region');
    await expect(lista(page, 0, 'Región').getByRole('checkbox').first()).toBeVisible();
    const antes = delCampo(api, 'region').length;

    await page.getByLabel('Fecha de corte').selectOption('2026-09-10');

    await expect.poll(() => delCampo(api, 'region').length).toBe(antes + 1);
    expect(delCampo(api, 'region').at(-1)!.searchParams.get('fecha_corte')).toBe('2026-09-10');
  });
});

test.describe('si falla la lista', () => {
  async function conFalla(page: Page, filtros: string[]) {
    let falla = true;
    const api = await abrir(
      page,
      (campo) => (campo === 'region' && falla ? { estado: 500 } : campo === 'region' ? { valores: REGIONES } : {}),
      (a) => {
        a.selecciones = [seleccionGuardada({ id: 5, nombre: 'Con valores', filtros, orden: null, cantidad: null })];
      },
    );
    await page.getByLabel('Selección guardada').selectOption({ label: 'Con valores' });
    return { api, arreglar: () => (falla = false) };
  }

  test('vuelve al cuadro de texto con lo marcado, una línea por valor, y dice el error con «Reintentar»', async ({ page }) => {
    await conFalla(page, ['region:en:CUSCO SUR|TACNA']);

    await expect(fila(page, 0).getByRole('alert')).toContainText('No se pudieron cargar los valores.');
    await expect(fila(page, 0).locator('textarea')).toHaveValue('CUSCO SUR\nTACNA');
    await expect(fila(page, 0).getByRole('button', { name: 'Reintentar' })).toBeVisible();
  });

  test('«(vacío)» marcado queda como una casilla debajo, nunca como una línea en blanco, y el filtro que se manda no cambia', async ({ page }) => {
    const { api } = await conFalla(page, ['region:en:TACNA|']);

    await expect(fila(page, 0).locator('textarea')).toHaveValue('TACNA');
    const vacio = fila(page, 0).getByRole('checkbox', { name: '(vacío)' });
    await expect(vacio).toBeChecked();
    await expect.poll(() => filtrosEnviados(api)).toEqual(['region:en:TACNA|']);

    // Editing the text area keeps «(vacío)» in the filter.
    await fila(page, 0).locator('textarea').fill('TACNA\nPUNO');
    await expect.poll(() => filtrosEnviados(api)).toEqual(['region:en:TACNA|PUNO|']);

    // Unchecking removes the box (nothing left to keep), so it is a click and not a state to wait for.
    await vacio.click();
    await expect.poll(() => filtrosEnviados(api)).toEqual(['region:en:TACNA|PUNO']);
  });

  test('«Reintentar» vuelve a pedir la lista y, si llega, vuelve a las casillas con lo que diga el cuadro de texto', async ({ page }) => {
    const { api, arreglar } = await conFalla(page, ['region:en:TACNA|']);
    await fila(page, 0).locator('textarea').fill('TACNA\nCUSCO SUR');
    const antes = delCampo(api, 'region').length;
    arreglar();

    await fila(page, 0).getByRole('button', { name: 'Reintentar' }).click();

    await expect(lista(page, 0, 'Región').getByRole('checkbox').first()).toBeVisible();
    expect(delCampo(api, 'region')).toHaveLength(antes + 1);
    await expect(casilla(page, 0, 'Región', /^TACNA/)).toBeChecked();
    await expect(casilla(page, 0, 'Región', /^CUSCO SUR/)).toBeChecked();
    await expect(casilla(page, 0, 'Región', /^\(vacío\)/)).toBeChecked();
    await expect(fila(page, 0).getByRole('alert')).toHaveCount(0);
  });

  test('dos clics seguidos en «Reintentar» dejan un solo pedido vivo, con la misma clave', async ({ page }) => {
    const { api, arreglar } = await conFalla(page, ['region:en:TACNA']);
    await expect(fila(page, 0).getByRole('alert')).toBeVisible();
    const antes = delCampo(api, 'region').length;
    arreglar();

    await fila(page, 0).getByRole('button', { name: 'Reintentar' }).dblclick();

    await expect(lista(page, 0, 'Región').getByRole('checkbox').first()).toBeVisible();
    await page.waitForTimeout(500);
    const nuevos = delCampo(api, 'region').slice(antes);
    expect(nuevos).toHaveLength(1);
    expect(nuevos[0].searchParams.get('fecha_corte')).toBe('2026-09-10');
    expect(nuevos[0].searchParams.getAll('filtro')).toEqual([]);
  });

  test('lo marcado se sigue mandando mientras la lista falla: la selección se calcula igual', async ({ page }) => {
    const { api } = await conFalla(page, ['region:no_en:TACNA']);

    await expect(fila(page, 0).getByRole('alert')).toBeVisible();

    await expect.poll(() => filtrosEnviados(api)).toEqual(['region:no_en:TACNA']);
  });
});

// ---- axe ------------------------------------------------------------------------------------

const REGLAS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

async function sinViolaciones(page: Page): Promise<void> {
  // The totals above are dimmed while they are recalculated; axe would read the dimmed contrast.
  await expect(page.locator('[data-metricas]')).toHaveAttribute('data-calculando', 'false');
  const resultado = await new AxeBuilder({ page }).withTags(REGLAS).analyze();
  expect(resultado.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
}

for (const tema of ['light', 'dark'] as const) {
  test.describe(`axe de la lista de valores, tema ${tema === 'light' ? 'claro' : 'oscuro'}`, () => {
    test.beforeEach(async ({ page }) => {
      await page.addInitScript((elegido) => {
        localStorage.setItem('app:appearance', JSON.stringify({ theme: elegido, language: 'es' }));
      }, tema);
    });

    test('la lista con marcados y «(vacío)»', async ({ page }) => {
      await abrir(page);
      const i = await nuevoFiltro(page, 'region');
      await casilla(page, i, 'Región', /^TACNA/).check();
      await casilla(page, i, 'Región', /^\(vacío\)/).check();
      await sinViolaciones(page);
    });

    test('la lista con marcados sin productos', async ({ page }) => {
      await abrir(page);
      const a = await nuevoFiltro(page, 'region');
      const b = await nuevoFiltro(page, 'segmento_financiero');
      await casilla(page, b, 'Segmento financiero', /^Sin asignar/).check();
      await casilla(page, a, 'Región', /^TACNA/).check();
      await expect(fila(page, b).getByRole('group', { name: 'Marcados sin productos con los filtros de arriba' })).toBeVisible();
      await sinViolaciones(page);
    });

    test('el error con «Reintentar» y la casilla de «(vacío)»', async ({ page }) => {
      await abrir(page, (campo) => (campo === 'region' ? { estado: 500 } : {}), (api) => {
        api.selecciones = [seleccionGuardada({ id: 6, nombre: 'Con vacío', filtros: ['region:en:TACNA|'], orden: null, cantidad: null })];
      });
      await page.getByLabel('Selección guardada').selectOption({ label: 'Con vacío' });
      await expect(fila(page, 0).getByRole('alert')).toBeVisible();
      await sinViolaciones(page);
    });
  });
}

test('la lista a 360 px cabe sin desplazar la página de lado y se maneja con teclado', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await abrir(page);
  const i = await nuevoFiltro(page, 'region');

  const desborde = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(desborde).toBeLessThanOrEqual(0);
  const primera = casilla(page, i, 'Región', /^CUSCO SUR/);
  await primera.focus();
  await page.keyboard.press('Space');
  await expect(primera).toBeChecked();
  await sinViolaciones(page);
});

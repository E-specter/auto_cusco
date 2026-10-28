/**
 * The order of the filters in the MOWA MES campaign (T-FV-F3, docs/filtro-valores-interfaz.md §3.5 and §4): the
 * campaign mounts the compact selector (the cut-off date and a saved selection), so there are no rows to move there.
 * It takes the order the selection was saved with. What costs when it is wrong: a preview or a campaign that
 * carries the filters in another order than the selection, and a suggested description that does not follow it.
 * Every name and value is synthetic.
 */
import { expect, test, type Page, type Route } from '@playwright/test';

import type { Campos, SeleccionGuardada, Version } from '../src/lib/api';
import { camposSinteticos, seleccionGuardada, version } from './api-falsa';
import { apiMowaMes, montarApiMowaMes, type ApiFalsaMowaMes } from './api-falsa-mowa-mes';

test.use({ timezoneId: 'America/Lima', reducedMotion: 'reduce' });

const json = (route: Route, estado: number, cuerpo: unknown) =>
  route.fulfill({ status: estado, contentType: 'application/json', body: JSON.stringify(cuerpo) });

const DIAS = 'dias_atraso:mayor:30';
const REGION = 'region:igual:TACNA';

const SELECCIONES: SeleccionGuardada[] = [
  seleccionGuardada({ id: 1, nombre: 'Días primero', filtros: [DIAS, REGION], orden: null, cantidad: 1000 }),
  seleccionGuardada({ id: 2, nombre: 'Región primero', filtros: [REGION, DIAS], orden: null, cantidad: 1000 }),
];

async function abrir(page: Page, api: ApiFalsaMowaMes): Promise<void> {
  const versiones: Version[] = [version({ fecha_corte: '2026-09-13', vigente: true })];
  const campos: Campos = camposSinteticos();
  await montarApiMowaMes(page, api);
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const ruta = url.pathname.replace(/^\/api/, '');
    const metodo = route.request().method();
    if (ruta === '/cargas' && metodo === 'GET') return json(route, 200, versiones);
    if (ruta === '/cartera/campos') return json(route, 200, campos);
    if (ruta === '/selecciones' && metodo === 'GET') return json(route, 200, SELECCIONES);
    return route.fallback();
  });
  await page.goto('/mowa-mes/campana');
  await expect(page.getByRole('heading', { name: 'Campaña de MOWA MES', level: 1 })).toBeVisible();
}

const elegir = (page: Page, nombre: string) => page.getByLabel('Selección guardada').selectOption({ label: nombre });
const descripcion = (page: Page) => page.locator('#mm-descripcion');
const previas = (api: ApiFalsaMowaMes) => api.pedidos.filter((p) => p.ruta === '/mowa-mes/campanas/previsualizacion' && p.metodo === 'POST');
const filtrosDe = (pedido: { cuerpo: unknown } | undefined) => (pedido?.cuerpo as { filtros?: string[] } | undefined)?.filtros;

test.describe('el orden de la selección guardada', () => {
  test('no hay filas de filtro que mover: el selector de la campaña es el compacto', async ({ page }) => {
    await abrir(page, apiMowaMes());

    await expect(page.locator('[data-selector]')).toHaveAttribute('data-modo', 'compacto');
    await expect(page.locator('[data-mover]')).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Agregar filtro' })).toHaveCount(0);
  });

  test('la previsualización lleva los filtros en el orden guardado, y la sugerida lo sigue', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);

    await elegir(page, 'Días primero');

    await expect.poll(() => filtrosDe(previas(api).at(-1))).toEqual([DIAS, REGION]);
    await expect(descripcion(page)).toHaveValue('CajaCusco dias_atraso mayor 30, region igual TACNA');
  });

  test('la misma selección en otro orden da otra sugerida y otra petición', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);
    await elegir(page, 'Días primero');
    await expect(descripcion(page)).toHaveValue('CajaCusco dias_atraso mayor 30, region igual TACNA');

    await elegir(page, 'Región primero');

    await expect.poll(() => filtrosDe(previas(api).at(-1))).toEqual([REGION, DIAS]);
    await expect(descripcion(page)).toHaveValue('CajaCusco region igual TACNA, dias_atraso mayor 30');
  });

  test('con la descripción editada, la sugerida no la toca, cambie el orden o no', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);
    await elegir(page, 'Días primero');
    await expect(descripcion(page)).toHaveValue('CajaCusco dias_atraso mayor 30, region igual TACNA');
    await descripcion(page).fill('Mi descripción');

    await elegir(page, 'Región primero');

    await expect.poll(() => filtrosDe(previas(api).at(-1))).toEqual([REGION, DIAS]);
    await expect(descripcion(page)).toHaveValue('Mi descripción');
    // What is registered is what the analyst wrote, in the order of the screen.
    expect((previas(api).at(-1)!.cuerpo as { descripcion?: string }).descripcion).toBe('Mi descripción');
  });

  test('la creación de la campaña lleva los filtros en el orden guardado', async ({ page }) => {
    const api = apiMowaMes();
    await abrir(page, api);
    await elegir(page, 'Región primero');
    await expect.poll(() => filtrosDe(previas(api).at(-1))).toEqual([REGION, DIAS]);

    await page.getByRole('button', { name: 'Crear campaña' }).click();

    await expect.poll(() => api.pedidos.some((p) => p.ruta === '/mowa-mes/campanas' && p.metodo === 'POST')).toBe(true);
    const creacion = api.pedidos.find((p) => p.ruta === '/mowa-mes/campanas' && p.metodo === 'POST')!;
    expect(filtrosDe(creacion)).toEqual([REGION, DIAS]);
  });
});

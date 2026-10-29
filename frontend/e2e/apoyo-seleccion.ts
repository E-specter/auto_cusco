/**
 * The compact selector's own calls, for the screens that mount it over a module's fake (the MOWA MES
 * campaign and the accessibility sweep). Registered AFTER the module's fake, so it answers the three
 * routes the selector reads and falls back to the module's mock (`route.fallback()`) for the rest.
 */
import type { Page } from '@playwright/test';

import type { Campos, SeleccionGuardada, Version } from '../src/lib/api';
import { camposSinteticos, seleccionGuardada, version } from './api-falsa';
import { json } from './apoyo';

export interface SeleccionFalsa {
  versiones: Version[];
  campos: Campos;
  selecciones: SeleccionGuardada[];
}

export function seleccionFalsa(parcial: Partial<SeleccionFalsa> = {}): SeleccionFalsa {
  return {
    versiones: [version({ fecha_corte: '2026-09-13', vigente: true })],
    campos: camposSinteticos(),
    selecciones: [seleccionGuardada({ id: 1, nombre: 'Preventiva top 1000', cantidad: 1000 })],
    ...parcial,
  };
}

export async function montarSeleccion(page: Page, sel: SeleccionFalsa = seleccionFalsa()): Promise<void> {
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const ruta = url.pathname.replace(/^\/api/, '');
    const metodo = route.request().method();

    if (ruta === '/cargas' && metodo === 'GET') return json(route, 200, sel.versiones);
    if (ruta === '/cartera/campos') return json(route, 200, sel.campos);
    if (ruta === '/selecciones' && metodo === 'GET') return json(route, 200, sel.selecciones);

    return route.fallback();
  });
}

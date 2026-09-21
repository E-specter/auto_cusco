/**
 * The top navigation, as data. The header renders this and nothing else, so
 * adding a module or a route is an edit here, never in the markup.
 *
 * Shape: sections separated by a divider (`|`); inside a section, entries
 * separated by a middle dot (`·`). An entry is either a plain link (a step of
 * the daily flow) or a module whose routes open in a dropdown.
 *
 *     Cargas · Cartera  |  MOWA MES ▾ · WhatsMKT ▾ · Cisvox ▾
 *
 * Every visible text carries its i18n key and a Spanish fallback, the same
 * contract as the rest of the markup (`data-i18n`).
 */

export interface EnlaceNav {
  ruta: string;
  /** Key and fallback for the visible text. */
  i18n: string;
  texto: string;
  /**
   * Accessible name when the visible text needs its context to make sense
   * out of the menu ("Campaña" alone vs "MOWA MES: campaña").
   */
  aria?: { i18n: string; texto: string };
}

export interface ModuloNav {
  id: string;
  i18n: string;
  texto: string;
  /** Every route under this prefix belongs to the module. */
  prefijo: string;
  enlaces: EnlaceNav[];
}

export type EntradaNav = { tipo: 'enlace'; enlace: EnlaceNav } | { tipo: 'modulo'; modulo: ModuloNav };

export interface SeccionNav {
  id: string;
  /** Accessible name of the group; sections have no visible title. */
  i18n: string;
  texto: string;
  entradas: EntradaNav[];
}

export const NAVEGACION: SeccionNav[] = [
  {
    id: 'flujo',
    i18n: 'nav.seccion.flujo',
    texto: 'Flujo diario',
    entradas: [
      { tipo: 'enlace', enlace: { ruta: '/cargas', i18n: 'nav.cargas', texto: 'Cargas' } },
      { tipo: 'enlace', enlace: { ruta: '/cartera', i18n: 'nav.cartera', texto: 'Cartera' } },
    ],
  },
  {
    id: 'canales',
    i18n: 'nav.seccion.canales',
    texto: 'Canales',
    entradas: [
      {
        tipo: 'modulo',
        modulo: {
          id: 'mowa-mes',
          i18n: 'nav.mowaMes',
          texto: 'MOWA MES',
          prefijo: '/mowa-mes',
          enlaces: [
            {
              ruta: '/mowa-mes/campana',
              i18n: 'nav.mowaMes.campana',
              texto: 'Campaña',
              aria: { i18n: 'nav.mowaMes.campanaLargo', texto: 'MOWA MES: campaña' },
            },
            {
              ruta: '/mowa-mes/seguimiento',
              i18n: 'nav.mowaMes.seguimiento',
              texto: 'Seguimiento',
              aria: { i18n: 'nav.mowaMes.seguimientoLargo', texto: 'MOWA MES: seguimiento' },
            },
            {
              ruta: '/mowa-mes/configuracion',
              i18n: 'nav.mowaMes.configuracion',
              texto: 'Configuración',
              aria: { i18n: 'nav.mowaMes.configuracionLargo', texto: 'MOWA MES: configuración' },
            },
          ],
        },
      },
    ],
  },
];

/** A path without its trailing slash, so `/cargas/` and `/cargas` match. */
export function normalizarRuta(ruta: string): string {
  return ruta.replace(/\/+$/, '') || '/';
}

export function enlaceActivo(enlace: EnlaceNav, actual: string): boolean {
  return normalizarRuta(enlace.ruta) === normalizarRuta(actual);
}

/** True for the module's own prefix and anything below it, never a lookalike. */
export function moduloActivo(modulo: ModuloNav, actual: string): boolean {
  const ruta = normalizarRuta(actual);
  const prefijo = normalizarRuta(modulo.prefijo);
  return ruta === prefijo || ruta.startsWith(`${prefijo}/`);
}

/** Every route the navigation points to, for tests and sitemaps. */
export function rutasDeNavegacion(secciones: SeccionNav[] = NAVEGACION): string[] {
  return secciones.flatMap((seccion) =>
    seccion.entradas.flatMap((entrada) =>
      entrada.tipo === 'enlace' ? [entrada.enlace.ruta] : entrada.modulo.enlaces.map((e) => e.ruta),
    ),
  );
}

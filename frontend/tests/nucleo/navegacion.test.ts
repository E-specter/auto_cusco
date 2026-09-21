/**
 * The navigation as data. The header renders exactly this, so a route that
 * points nowhere, a missing translation or a lookalike prefix marking the
 * wrong module shows up here before it shows up in the bar.
 */
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import {
  NAVEGACION,
  enlaceActivo,
  moduloActivo,
  normalizarRuta,
  rutasDeNavegacion,
  type ModuloNav,
} from '../../src/lib/navegacion';

const desdeAqui = (ruta: string) => fileURLToPath(new URL(ruta, import.meta.url));
const es = JSON.parse(readFileSync(desdeAqui('../../src/i18n/es.json'), 'utf8')) as Record<string, string>;
const en = JSON.parse(readFileSync(desdeAqui('../../src/i18n/en.json'), 'utf8')) as Record<string, string>;

/** Every i18n key the navigation declares, visible text and accessible names. */
function clavesDeNavegacion(): string[] {
  return NAVEGACION.flatMap((seccion) => [
    seccion.i18n,
    ...seccion.entradas.flatMap((entrada) =>
      entrada.tipo === 'enlace'
        ? [entrada.enlace.i18n]
        : [
            entrada.modulo.i18n,
            ...entrada.modulo.enlaces.flatMap((e) => [e.i18n, ...(e.aria ? [e.aria.i18n] : [])]),
          ],
    ),
  ]);
}

const MOWA = NAVEGACION.flatMap((s) => s.entradas).find(
  (e): e is { tipo: 'modulo'; modulo: ModuloNav } => e.tipo === 'modulo' && e.modulo.id === 'mowa-mes',
)!.modulo;

describe('estructura de la navegación', () => {
  it('agrupa el flujo diario y los canales en secciones separadas', () => {
    expect(NAVEGACION.map((s) => s.id)).toEqual(['flujo', 'canales']);
  });

  it('cada ruta apunta a una página que existe', () => {
    const rutas = rutasDeNavegacion();

    const faltantes = rutas.filter((ruta) => !existsSync(desdeAqui(`../../src/pages${ruta}.astro`)));

    expect(rutas.length).toBeGreaterThan(0);
    expect(faltantes).toEqual([]);
  });

  it('ninguna ruta se repite', () => {
    const rutas = rutasDeNavegacion();

    expect(new Set(rutas).size).toBe(rutas.length);
  });

  it('cada ruta de un módulo vive bajo su prefijo', () => {
    const fuera = MOWA.enlaces.filter((e) => !moduloActivo(MOWA, e.ruta));

    expect(fuera).toEqual([]);
  });

  it('cada texto está traducido en los dos idiomas', () => {
    const claves = clavesDeNavegacion();

    expect(claves.filter((k) => !(k in es))).toEqual([]);
    expect(claves.filter((k) => !(k in en))).toEqual([]);
  });

  it('el texto de respaldo del marcado coincide con el español', () => {
    const distintos = NAVEGACION.flatMap((s) => s.entradas).flatMap((entrada) =>
      entrada.tipo === 'enlace'
        ? [[entrada.enlace.i18n, entrada.enlace.texto]]
        : [
            [entrada.modulo.i18n, entrada.modulo.texto],
            ...entrada.modulo.enlaces.map((e) => [e.i18n, e.texto]),
          ],
    ).filter(([clave, texto]) => es[clave] !== texto);

    expect(distintos).toEqual([]);
  });
});

describe('dónde está el analista', () => {
  it('ignora la barra final de la ruta', () => {
    expect(normalizarRuta('/cargas/')).toBe('/cargas');
    expect(normalizarRuta('/')).toBe('/');
  });

  it('marca solo el enlace exacto', () => {
    const campana = MOWA.enlaces[0];

    expect(enlaceActivo(campana, '/mowa-mes/campana/')).toBe(true);
    expect(enlaceActivo(campana, '/mowa-mes/seguimiento')).toBe(false);
  });

  it('marca el módulo en cualquiera de sus rutas', () => {
    expect(moduloActivo(MOWA, '/mowa-mes/seguimiento')).toBe(true);
    expect(moduloActivo(MOWA, '/mowa-mes')).toBe(true);
  });

  it('no confunde un módulo con otro de nombre parecido', () => {
    expect(moduloActivo(MOWA, '/mowa-mes-2/campana')).toBe(false);
    expect(moduloActivo(MOWA, '/cartera')).toBe(false);
  });
});

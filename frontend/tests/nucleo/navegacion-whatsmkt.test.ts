/**
 * WhatsMKT in the navigation: a second module in Canales, after MOWA MES, with the same three routes
 * and the same dropdown (docs/whatsmkt-interfaz.md §2, RF-WM-02).
 */
import { describe, expect, it } from 'vitest';

import { NAVEGACION, enlaceActivo, moduloActivo, type ModuloNav } from '../../src/lib/navegacion';

const modulos = NAVEGACION.find((seccion) => seccion.id === 'canales')!.entradas.flatMap((entrada) =>
  entrada.tipo === 'modulo' ? [entrada.modulo] : [],
);
const WHATSMKT = modulos.find((modulo) => modulo.id === 'whatsmkt') as ModuloNav;

describe('WhatsMKT en Canales', () => {
  it('va después de MOWA MES', () => {
    expect(modulos.map((modulo) => modulo.id)).toEqual(['mowa-mes', 'whatsmkt']);
  });

  it('abre Campaña, Seguimiento y Configuración, en ese orden, bajo /whatsmkt', () => {
    expect(WHATSMKT.prefijo).toBe('/whatsmkt');
    expect(WHATSMKT.enlaces.map((enlace) => enlace.ruta)).toEqual([
      '/whatsmkt/campana',
      '/whatsmkt/seguimiento',
      '/whatsmkt/configuracion',
    ]);
    expect(WHATSMKT.enlaces.every((enlace) => moduloActivo(WHATSMKT, enlace.ruta))).toBe(true);
  });

  it('cada enlace tiene un nombre accesible que dice de qué módulo es', () => {
    expect(WHATSMKT.enlaces.map((enlace) => enlace.aria?.texto)).toEqual([
      'WhatsMKT: campaña',
      'WhatsMKT: seguimiento',
      'WhatsMKT: configuración',
    ]);
  });

  it('marca su módulo y no el de MOWA MES, y a la inversa', () => {
    const mowa = modulos.find((modulo) => modulo.id === 'mowa-mes')!;

    expect(moduloActivo(WHATSMKT, '/whatsmkt/configuracion')).toBe(true);
    expect(moduloActivo(mowa, '/whatsmkt/configuracion')).toBe(false);
    expect(moduloActivo(WHATSMKT, '/mowa-mes/campana')).toBe(false);
    expect(enlaceActivo(WHATSMKT.enlaces[2], '/whatsmkt/configuracion/')).toBe(true);
    expect(enlaceActivo(WHATSMKT.enlaces[0], '/whatsmkt/configuracion')).toBe(false);
  });
});

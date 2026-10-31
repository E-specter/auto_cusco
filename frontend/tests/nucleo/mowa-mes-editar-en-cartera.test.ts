/**
 * «Editar en Cartera» (T-MM-C11, M-F6, RF-MM-09): where `volver` may send the analyst back to (the one input
 * here that turns a link into a navigation) and the campaign's draft in `sessionStorage` (written by this
 * version of the app or by none, and readable or not).
 */
import { describe, expect, it } from 'vitest';

import en from '../../src/i18n/en.json';
import es from '../../src/i18n/es.json';

import {
  CLAVE_BORRADOR_CAMPANA,
  almacenDeSesion,
  guardarBorrador,
  tomarBorrador,
  type Almacen,
  type BorradorEnPantalla,
} from '../../src/lib/mowa-mes-borrador-campana';
import {
  destinoConSeleccion,
  destinoSinSeleccion,
  enlaceEditarEnCartera,
  seleccionDeLaUrl,
  volverValido,
} from '../../src/lib/volver';

const ORIGEN = 'http://localhost:4321';

describe('volverValido: adónde se puede volver', () => {
  it('acepta una ruta de /mowa-mes/ del mismo origen y devuelve su ruta', () => {
    expect(volverValido('/mowa-mes/campana', ORIGEN)).toBe('/mowa-mes/campana');
    expect(volverValido('/mowa-mes/seguimiento', ORIGEN)).toBe('/mowa-mes/seguimiento');
    expect(volverValido('/mowa-mes/campana?x=1', ORIGEN)).toBe('/mowa-mes/campana?x=1');
  });

  it('acepta una dirección completa del mismo origen, pero devuelve solo la ruta', () => {
    expect(volverValido(`${ORIGEN}/mowa-mes/campana`, ORIGEN)).toBe('/mowa-mes/campana');
  });

  it('ignora una dirección que empieza con // (otro servidor sin esquema)', () => {
    expect(volverValido('//evil.com', ORIGEN)).toBeNull();
    expect(volverValido('//evil.com/mowa-mes/campana', ORIGEN)).toBeNull();
    expect(volverValido('///mowa-mes/campana', ORIGEN)).toBeNull();
    // Even the same host, written protocol-relative: the rule is the text, not only where it lands.
    expect(volverValido('//localhost:4321/mowa-mes/campana', ORIGEN)).toBeNull();
  });

  it('ignora otro origen aunque la ruta sea de /mowa-mes/', () => {
    expect(volverValido('https://evil.com/mowa-mes/', ORIGEN)).toBeNull();
    expect(volverValido('https://evil.com/mowa-mes/campana', ORIGEN)).toBeNull();
    expect(volverValido('http://localhost:9999/mowa-mes/campana', ORIGEN)).toBeNull();
    expect(volverValido('http://localhost:4321.evil.com/mowa-mes/campana', ORIGEN)).toBeNull();
  });

  it('ignora lo que no es una página: javascript:, data:, vacío', () => {
    expect(volverValido('javascript:alert(1)', ORIGEN)).toBeNull();
    expect(volverValido('JaVaScRiPt:alert(1)', ORIGEN)).toBeNull();
    expect(volverValido('data:text/html,<script>alert(1)</script>', ORIGEN)).toBeNull();
    expect(volverValido('', ORIGEN)).toBeNull();
    expect(volverValido(null, ORIGEN)).toBeNull();
    expect(volverValido(undefined, ORIGEN)).toBeNull();
  });

  it('valida la ruta YA normalizada: /mowa-mes/../cartera es /cartera y se ignora', () => {
    expect(volverValido('/mowa-mes/../cartera', ORIGEN)).toBeNull();
    expect(volverValido('/mowa-mes/%2e%2e/cartera', ORIGEN)).toBeNull();
    expect(volverValido('/mowa-mes/./campana', ORIGEN)).toBe('/mowa-mes/campana');
    expect(volverValido('/otra/../mowa-mes/campana', ORIGEN)).toBe('/mowa-mes/campana');
  });

  it('ignora lo que no cuelga de /mowa-mes/', () => {
    expect(volverValido('/cartera', ORIGEN)).toBeNull();
    expect(volverValido('/', ORIGEN)).toBeNull();
    expect(volverValido('/mowa-mes', ORIGEN)).toBeNull();
    expect(volverValido('/mowa-mesx/campana', ORIGEN)).toBeNull();
    // A relative one resolves against the origin's root, which is the same safe place.
    expect(volverValido('mowa-mes/campana', ORIGEN)).toBe('/mowa-mes/campana');
  });

  it('ignora las barras invertidas y los caracteres de control que el navegador convierte en //', () => {
    expect(volverValido('/\\evil.com', ORIGEN)).toBeNull();
    expect(volverValido('\\\\evil.com', ORIGEN)).toBeNull();
    expect(volverValido('/\t/evil.com', ORIGEN)).toBeNull();
    expect(volverValido('\t//evil.com', ORIGEN)).toBeNull();
  });
});

describe('el destino al volver', () => {
  it('con una selección guardada vuelve a ?seleccion=<id>, conservando lo demás', () => {
    expect(destinoConSeleccion('/mowa-mes/campana', 7)).toBe('/mowa-mes/campana?seleccion=7');
    expect(destinoConSeleccion('/mowa-mes/campana?x=1', 7)).toBe('/mowa-mes/campana?x=1&seleccion=7');
    expect(destinoConSeleccion('/mowa-mes/campana?seleccion=3', 7)).toBe('/mowa-mes/campana?seleccion=7');
  });

  it('sin guardar vuelve sin seleccion', () => {
    expect(destinoSinSeleccion('/mowa-mes/campana?seleccion=3')).toBe('/mowa-mes/campana');
    expect(destinoSinSeleccion('/mowa-mes/campana?x=1&seleccion=3')).toBe('/mowa-mes/campana?x=1');
    expect(destinoSinSeleccion('/mowa-mes/campana')).toBe('/mowa-mes/campana');
  });

  it('el enlace a Cartera lleva la selección y adónde volver, bien escapado', () => {
    expect(enlaceEditarEnCartera(7, '/mowa-mes/campana')).toBe('/cartera?seleccion=7&volver=%2Fmowa-mes%2Fcampana');
    const ida = new URL(enlaceEditarEnCartera(7, '/mowa-mes/campana'), ORIGEN);
    expect(volverValido(ida.searchParams.get('volver'), ORIGEN)).toBe('/mowa-mes/campana');
  });

  it('?seleccion= es un id entero positivo, o nada', () => {
    expect(seleccionDeLaUrl('?seleccion=7')).toBe(7);
    expect(seleccionDeLaUrl('?volver=%2Fmowa-mes%2Fcampana&seleccion=12')).toBe(12);
    for (const malo of ['', '?seleccion=', '?seleccion=abc', '?seleccion=0', '?seleccion=-3', '?seleccion=2.5', '?seleccion=1e3', '?x=1']) {
      expect(seleccionDeLaUrl(malo), malo).toBeNull();
    }
  });
});

function borrador(parcial: Partial<BorradorEnPantalla> = {}): BorradorEnPantalla {
  return {
    seleccionId: 7,
    fechaCorte: '2026-10-30',
    descripcion: 'Preventiva 9 a 30',
    descripcionEditada: true,
    plantilla: 'carga_{campana}',
    plantillaEditada: true,
    keyword: true,
    blacklist: false,
    programacion: 'diferentes_horas',
    fechaUnica: '2026-11-02T09:00',
    fechasMultiples: ['2026-11-02T09:00', '2026-11-03T10:30'],
    speech: '4',
    whatsapp: '900000999',
    supervisoresModo: 'propios',
    supervisoresPropios: [{ numero: '900000101', procedencia: 'Procedencia A' }],
    ...parcial,
  };
}

/** A storage in memory, optionally one that refuses what is asked of it. */
function almacenEnMemoria(rechaza: Array<'getItem' | 'setItem' | 'removeItem'> = []): Almacen & { datos: Map<string, string> } {
  const datos = new Map<string, string>();
  const salvo = <T,>(operacion: 'getItem' | 'setItem' | 'removeItem', haz: () => T): T => {
    if (rechaza.includes(operacion)) throw new DOMException('refused', 'SecurityError');
    return haz();
  };
  return {
    datos,
    getItem: (clave) => salvo('getItem', () => datos.get(clave) ?? null),
    setItem: (clave, valor) => salvo('setItem', () => void datos.set(clave, valor)),
    removeItem: (clave) => salvo('removeItem', () => void datos.delete(clave)),
  };
}

describe('el borrador de la campaña', () => {
  it('se guarda y se restaura tal cual, con todos sus campos', () => {
    const almacen = almacenEnMemoria();

    expect(guardarBorrador(almacen, borrador())).toBe(true);

    expect(tomarBorrador(almacen)).toEqual(borrador());
  });

  it('se usa una sola vez: al tomarlo se borra', () => {
    const almacen = almacenEnMemoria();
    guardarBorrador(almacen, borrador());

    expect(tomarBorrador(almacen)).not.toBeNull();
    expect(almacen.datos.has(CLAVE_BORRADOR_CAMPANA)).toBe(false);
    expect(tomarBorrador(almacen)).toBeNull();
  });

  it('sin selección y sin fecha también se guarda', () => {
    const almacen = almacenEnMemoria();
    guardarBorrador(almacen, borrador({ seleccionId: null, fechaCorte: null, programacion: 'enviar_ahora', fechasMultiples: [] }));

    expect(tomarBorrador(almacen)).toEqual(borrador({ seleccionId: null, fechaCorte: null, programacion: 'enviar_ahora', fechasMultiples: [] }));
  });

  it('la clave lleva la versión', () => {
    expect(CLAVE_BORRADOR_CAMPANA).toMatch(/\.v1$/);
  });

  it('un borrador de otra versión no se lee y no se toca', () => {
    const almacen = almacenEnMemoria();
    almacen.datos.set('mowaMes.campana.borrador.v2', JSON.stringify({ version: 2, ...borrador() }));
    almacen.datos.set('mowaMes.campana.borrador.v0', JSON.stringify({ version: 0, ...borrador() }));

    expect(tomarBorrador(almacen)).toBeNull();
    expect(almacen.datos.size).toBe(2);
  });

  it('con la clave nuestra pero otra versión dentro, no se lee (y se borra)', () => {
    const almacen = almacenEnMemoria();
    almacen.datos.set(CLAVE_BORRADOR_CAMPANA, JSON.stringify({ version: 2, ...borrador() }));

    expect(tomarBorrador(almacen)).toBeNull();
    expect(almacen.datos.has(CLAVE_BORRADOR_CAMPANA)).toBe(false);
  });

  it('un JSON roto da nada y no se queda estorbando', () => {
    const almacen = almacenEnMemoria();
    for (const roto of ['{', 'no es json', '', 'null', '[]', '"texto"', '42']) {
      almacen.datos.set(CLAVE_BORRADOR_CAMPANA, roto);
      expect(tomarBorrador(almacen), roto).toBeNull();
      expect(almacen.datos.has(CLAVE_BORRADOR_CAMPANA), roto).toBe(false);
    }
  });

  it('un borrador incompleto o con un campo de otro tipo da nada', () => {
    const almacen = almacenEnMemoria();
    const sano = { version: 1, ...borrador() } as Record<string, unknown>;
    const malos: Array<Record<string, unknown>> = [
      { ...sano, descripcion: 5 },
      { ...sano, keyword: 'si' },
      { ...sano, programacion: 'mañana' },
      { ...sano, supervisoresModo: 'otros' },
      { ...sano, fechasMultiples: [1, 2] },
      { ...sano, supervisoresPropios: [{ numero: 900000101 }] },
      { ...sano, seleccionId: '7' },
      { ...sano, seleccionId: 1.5 },
      { ...sano, fechaCorte: 20261030 },
    ];
    for (const malo of malos) {
      almacen.datos.set(CLAVE_BORRADOR_CAMPANA, JSON.stringify(malo));
      expect(tomarBorrador(almacen)).toBeNull();
    }
    const sinCampo = { ...sano };
    delete sinCampo.whatsapp;
    almacen.datos.set(CLAVE_BORRADOR_CAMPANA, JSON.stringify(sinCampo));
    expect(tomarBorrador(almacen)).toBeNull();
  });

  it('un sessionStorage que tira error al leer da nada, sin romper', () => {
    expect(tomarBorrador(almacenEnMemoria(['getItem']))).toBeNull();
  });

  it('un sessionStorage que tira error al borrar igual devuelve lo leído', () => {
    const almacen = almacenEnMemoria(['removeItem']);
    guardarBorrador(almacen, borrador());

    expect(tomarBorrador(almacen)).toEqual(borrador());
  });

  it('un sessionStorage que tira error al guardar dice que no se pudo, sin romper', () => {
    expect(guardarBorrador(almacenEnMemoria(['setItem']), borrador())).toBe(false);
  });

  it('sin almacén (el navegador no lo da) no guarda ni lee, sin romper', () => {
    expect(guardarBorrador(null, borrador())).toBe(false);
    expect(tomarBorrador(null)).toBeNull();
  });

  it('almacenDeSesion no rompe cuando no hay sessionStorage', () => {
    expect(() => almacenDeSesion()).not.toThrow();
  });
});

describe('los textos de «Editar en Cartera» están en español y en inglés', () => {
  const CLAVES = [
    'cartera.volver.aviso',
    'cartera.volver.sinGuardar',
    'cartera.volver.noExiste',
    'mowaMes.accion.editarEnCartera',
    'mowaMes.campana.editarEnCartera.inactivo',
    'mowaMes.campana.seleccionBorrada',
  ];

  it.each(CLAVES)('%s tiene su texto en es y en en', (clave) => {
    expect((es as Record<string, string>)[clave], `es ${clave}`).toBeTruthy();
    expect((en as Record<string, string>)[clave], `en ${clave}`).toBeTruthy();
  });

  it('el aviso de la selección que no existe es el que aprobó designer', () => {
    expect((es as Record<string, string>)['cartera.volver.noExiste']).toBe('La selección que abriste ya no existe. Arma una nueva o elige otra de la lista.');
    expect((en as Record<string, string>)['cartera.volver.noExiste']).toBe('The selection you opened no longer exists. Build a new one or choose another from the list.');
  });
});

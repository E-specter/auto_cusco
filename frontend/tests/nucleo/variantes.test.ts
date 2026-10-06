/**
 * Per-segment variants. The rules that matter: a segment without its own
 * content uses the column's; an empty variant never hides that fallback;
 * copying makes an independent copy; and a segment that would come out empty
 * is visible before generating the load.
 */
import { describe, expect, it } from 'vitest';

import type { Expresion } from '../../src/lib/expresion';
import {
  copiarVariante,
  estaVacia,
  expresionDeSegmento,
  fijarVariante,
  problemasPorDefecto,
  quitarVariante,
  resumirSegmentos,
  segmentosVacios,
  variantesHuerfanas,
  type Segmento,
  type Variante,
} from '../../src/lib/variantes';

const texto = (valor: string): Expresion => ({ nodos: [{ tipo: 'texto', valor }] });
const VACIA: Expresion = { nodos: [] };

const SEGMENTOS: Segmento[] = [
  { clave: 'preventiva', etiqueta: 'Preventiva', desde: null, hasta: 0 },
  { clave: '1_a_8', etiqueta: '1 a 8', desde: 1, hasta: 8 },
  { clave: '9_a_30', etiqueta: '9 a 30', desde: 9, hasta: 30 },
];

describe('expresión vacía', () => {
  it('sin nodos o con solo texto vacío no produce nada', () => {
    expect(estaVacia(VACIA)).toBe(true);
    expect(estaVacia(texto(''))).toBe(true);
    expect(estaVacia(null)).toBe(true);
    expect(estaVacia(texto(' '))).toBe(false);
    expect(estaVacia({ nodos: [{ tipo: 'variable', nombre: 'titular', funciones: [] }] })).toBe(false);
  });
});

describe('contenido de cada segmento', () => {
  it('usa el propio si lo tiene y el de la columna si no', () => {
    const variantes: Variante[] = [{ segmento: '1_a_8', expresion: texto('temprano') }];

    expect(expresionDeSegmento(texto('general'), variantes, '1_a_8')).toEqual(texto('temprano'));
    expect(expresionDeSegmento(texto('general'), variantes, '9_a_30')).toEqual(texto('general'));
  });

  it('fijar una variante vacía la quita, para no tapar el contenido de la columna', () => {
    const variantes: Variante[] = [{ segmento: '1_a_8', expresion: texto('temprano') }];

    expect(fijarVariante(variantes, '1_a_8', VACIA)).toEqual([]);
  });

  it('fijar reemplaza en su lugar y agrega al final si no existía', () => {
    const variantes: Variante[] = [
      { segmento: '1_a_8', expresion: texto('a') },
      { segmento: '9_a_30', expresion: texto('b') },
    ];

    expect(fijarVariante(variantes, '1_a_8', texto('c')).map((v) => v.segmento)).toEqual(['1_a_8', '9_a_30']);
    expect(fijarVariante(variantes, 'preventiva', texto('d')).map((v) => v.segmento)).toEqual(['1_a_8', '9_a_30', 'preventiva']);
  });

  it('nunca modifica la lista que recibe', () => {
    const variantes: Variante[] = [{ segmento: '1_a_8', expresion: texto('a') }];

    fijarVariante(variantes, '1_a_8', texto('b'));
    quitarVariante(variantes, '1_a_8');

    expect(variantes).toEqual([{ segmento: '1_a_8', expresion: texto('a') }]);
  });
});

describe('copiar de otro segmento', () => {
  it('copia lo que usa el origen, propio o de la columna', () => {
    const variantes: Variante[] = [{ segmento: '1_a_8', expresion: texto('temprano') }];

    expect(expresionDeSegmento(VACIA, copiarVariante(VACIA, variantes, '1_a_8', '9_a_30'), '9_a_30')).toEqual(texto('temprano'));
    expect(expresionDeSegmento(VACIA, copiarVariante(texto('general'), [], 'preventiva', '9_a_30'), '9_a_30')).toEqual(texto('general'));
  });

  it('la copia es independiente del origen', () => {
    const origen: Expresion = { nodos: [{ tipo: 'variable', nombre: 'titular', funciones: [{ nombre: 'primeros', args: [8] }] }] };
    const variantes = copiarVariante(VACIA, [{ segmento: '1_a_8', expresion: origen }], '1_a_8', '9_a_30');

    const copia = variantes.find((v) => v.segmento === '9_a_30')!.expresion;
    (copia.nodos[0] as { funciones: Array<{ args: unknown[] }> }).funciones[0].args[0] = 99;

    expect((origen.nodos[0] as { funciones: Array<{ args: unknown[] }> }).funciones[0].args[0]).toBe(8);
  });
});

describe('estado de cada segmento en el selector', () => {
  it('distingue propio, por defecto, vacío y con problema', () => {
    const variantes: Variante[] = [{ segmento: '1_a_8', expresion: texto('temprano') }];
    const problemas = [{ codigo: 'parametro_invalido', detalle: 'x', ubicacion: null, segmento: '9_a_30' }];

    const conDefecto = resumirSegmentos(SEGMENTOS, texto('general'), variantes, problemas);
    const sinDefecto = resumirSegmentos(SEGMENTOS, VACIA, variantes, []);

    expect(conDefecto.map((s) => s.estado)).toEqual(['por_defecto', 'propia', 'con_problema']);
    expect(sinDefecto.map((s) => s.estado)).toEqual(['vacia', 'propia', 'vacia']);
  });

  it('los problemas con segmento nulo son del contenido de la columna, no de un segmento', () => {
    const problemas = [
      { codigo: 'x', detalle: 'x', ubicacion: null, segmento: null, campo: 'expresion' },
      { codigo: 'x', detalle: 'x', ubicacion: null, segmento: null, campo: 'nombre' },
      { codigo: 'x', detalle: 'x', ubicacion: null, segmento: '1_a_8' },
    ];

    expect(problemasPorDefecto(problemas)).toBe(1);
  });

  it('avisa qué segmentos saldrían vacíos', () => {
    const variantes: Variante[] = [{ segmento: '1_a_8', expresion: texto('temprano') }];

    expect(segmentosVacios(SEGMENTOS, VACIA, variantes).map((s) => s.clave)).toEqual(['preventiva', '9_a_30']);
    expect(segmentosVacios(SEGMENTOS, texto('general'), variantes)).toEqual([]);
  });

  it('detecta variantes de segmentos que el criterio ya no tiene', () => {
    const variantes: Variante[] = [
      { segmento: '1_a_8', expresion: texto('a') },
      { segmento: '121_a_150', expresion: texto('b') },
    ];

    expect(variantesHuerfanas(SEGMENTOS, variantes).map((v) => v.segmento)).toEqual(['121_a_150']);
  });
});

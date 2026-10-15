/**
 * How the constructor opens a definition and what it lets the analyst do
 * (docs/motor-texto-enriquecido-interfaz.md §5.1, decided 2026-10-03). The rule: looking at the
 * history must never leave a save armed that would replace the current version. An old version
 * opens read-only; "Usar como base" is the explicit step that makes it editable.
 */
import { describe, expect, it } from 'vitest';

import type { DefinicionRespuesta } from '../../src/lib/constructor-columnas';
import {
  aviso,
  descartar,
  esEditable,
  guardadoDeUnaVersionAntigua,
  hayContenido,
  modoInicial,
  puedeGuardar,
  usarComoBase,
} from '../../src/lib/constructor-version';
import {
  agregarColumna,
  definicionNueva,
  fijarExpresion,
  fijarValorPorDefecto,
  fijarVariantes,
  renombrarColumna,
  renombrarDefinicion,
} from '../../src/lib/constructor-columnas';

/** The definition as the API answers it, looking at `mostrada` while `vigente` is the latest. */
function respuesta(mostrada: number, vigente: number): DefinicionRespuesta {
  const numeros = Array.from({ length: vigente }, (_, i) => i + 1);
  return {
    id: 7,
    nombre: 'SMS preventivo',
    creado_en: '2026-10-01T09:00:00-05:00',
    actualizado_en: '2026-10-03T09:00:00-05:00',
    version_vigente: vigente,
    versiones: numeros.map((numero) => ({
      numero,
      creado_en: '2026-10-01T09:00:00-05:00',
      usada_en: null,
      usada: false,
    })),
    version: {
      numero: mostrada,
      creado_en: '2026-10-01T09:00:00-05:00',
      usada_en: null,
      usada: false,
      contenido: { proteger_formulas: true, segmentacion: null, columnas: [] },
    },
  };
}

describe('cómo se abre una definición', () => {
  it('una definición que no se ha guardado es nueva', () => {
    expect(modoInicial(null)).toBe('nueva');
  });

  it('la versión vigente se abre editable, como siempre', () => {
    expect(modoInicial(respuesta(5, 5))).toBe('editable');
  });

  it('una versión que no es la vigente se abre en solo lectura', () => {
    expect(modoInicial(respuesta(2, 5))).toBe('lectura');
  });

  it('también la primera cuando ya hay más', () => {
    expect(modoInicial(respuesta(1, 2))).toBe('lectura');
  });
});

describe('qué se puede editar', () => {
  it.each([
    ['nueva', true],
    ['editable', true],
    ['base', true],
    ['lectura', false],
  ] as const)('%s → editable: %s', (modo, editable) => {
    expect(esEditable(modo)).toBe(editable);
  });
});

describe('usar como base y descartar', () => {
  it('«Usar como base» habilita la edición de una versión antigua', () => {
    expect(usarComoBase('lectura')).toBe('base');
  });

  it('«Usar como base» no cambia nada en los otros modos', () => {
    expect(usarComoBase('editable')).toBe('editable');
    expect(usarComoBase('nueva')).toBe('nueva');
    expect(usarComoBase('base')).toBe('base');
  });

  it('descartar lo armado desde una versión antigua la devuelve a solo lectura', () => {
    expect(descartar('base')).toBe('lectura');
  });

  it('descartar en la vigente o en una nueva deja el modo: solo se restaura el borrador', () => {
    expect(descartar('editable')).toBe('editable');
    expect(descartar('nueva')).toBe('nueva');
    expect(descartar('lectura')).toBe('lectura');
  });
});

describe('cuándo se puede guardar', () => {
  it('nunca en solo lectura', () => {
    expect(puedeGuardar('lectura', true)).toBe(false);
    expect(puedeGuardar('lectura', false)).toBe(false);
  });

  it('la vigente solo con cambios', () => {
    expect(puedeGuardar('editable', true)).toBe(true);
    expect(puedeGuardar('editable', false)).toBe(false);
  });

  it('una versión usada como base se guarda aunque no cambie: ese es el propósito', () => {
    expect(puedeGuardar('base', false)).toBe(true);
    expect(puedeGuardar('base', true)).toBe(true);
  });

  it('una nueva se guarda cuando ya hay algo escrito', () => {
    expect(puedeGuardar('nueva', true)).toBe(true);
    expect(puedeGuardar('nueva', false)).toBe(false);
  });

  it('un guardado en curso no se repite', () => {
    expect(puedeGuardar('editable', true, true)).toBe(false);
    expect(puedeGuardar('base', true, true)).toBe(false);
  });
});

describe('qué avisa la pantalla', () => {
  it('en solo lectura dice qué versión se ve y cuál es la vigente', () => {
    expect(aviso('lectura', respuesta(2, 5))).toEqual({ tipo: 'lectura', vista: 2, vigente: 5 });
  });

  it('con «Usar como base» advierte qué versión crea y que la vigente no cambia', () => {
    expect(aviso('base', respuesta(2, 5))).toEqual({ tipo: 'base', base: 2, nueva: 6, vigente: 5 });
  });

  it('la vigente editable y la definición nueva no llevan aviso', () => {
    expect(aviso('editable', respuesta(5, 5))).toEqual({ tipo: 'ninguno' });
    expect(aviso('nueva', null)).toEqual({ tipo: 'ninguno' });
  });
});

describe('qué es guardar desde una versión antigua', () => {
  it('es una versión nueva con el contenido de la antigua, que pasa a ser la vigente', () => {
    expect(guardadoDeUnaVersionAntigua(respuesta(2, 5))).toEqual({ base: 2, nueva: 6, vigenteAntes: 5 });
  });

  it('desde la vigente no es nada especial', () => {
    expect(guardadoDeUnaVersionAntigua(respuesta(5, 5))).toBeNull();
  });
});

describe('hay algo escrito en la definición nueva', () => {
  it('una definición recién abierta no tiene contenido', () => {
    expect(hayContenido(definicionNueva())).toBe(false);
  });

  it('un nombre ya cuenta', () => {
    expect(hayContenido(renombrarDefinicion(definicionNueva(), 'SMS'))).toBe(true);
  });

  it('un nombre de solo espacios no cuenta', () => {
    expect(hayContenido(renombrarDefinicion(definicionNueva(), '   '))).toBe(false);
  });

  it('el nombre de una columna cuenta', () => {
    const b = definicionNueva();

    expect(hayContenido(renombrarColumna(b, b.columnas[0].id, 'telefono'))).toBe(true);
  });

  it('el contenido de una columna cuenta', () => {
    const b = definicionNueva();

    expect(
      hayContenido(fijarExpresion(b, b.columnas[0].id, { nodos: [{ tipo: 'texto', valor: 'hola' }] })),
    ).toBe(true);
  });

  it('un valor por defecto cuenta', () => {
    const b = definicionNueva();

    expect(hayContenido(fijarValorPorDefecto(b, b.columnas[0].id, 'sin dato'))).toBe(true);
  });

  it('una variante por segmento cuenta', () => {
    const b = definicionNueva();

    expect(
      hayContenido(fijarVariantes(b, b.columnas[0].id, [{ segmento: 'preventiva', expresion: { nodos: [] } }])),
    ).toBe(true);
  });

  it('una expresión de solo un texto vacío no es contenido (la misma regla que el selector de variantes)', () => {
    const b = definicionNueva();

    expect(hayContenido(fijarExpresion(b, b.columnas[0].id, { nodos: [{ tipo: 'texto', valor: '' }] }))).toBe(false);
  });

  it('una columna más ya es contenido', () => {
    expect(hayContenido(agregarColumna(definicionNueva()).borrador)).toBe(true);
  });
});

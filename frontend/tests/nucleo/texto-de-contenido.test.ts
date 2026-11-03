/**
 * The sentence a list says of a column's content (`textoDeContenido`, T-HI-F6): what the column-builder shows in each row and what
 * a channel's campaign shows when it lists the same columns. Pure: the screen hands in how a variable is called and, if it has it,
 * the result of the backend's preview. All data is invented.
 */
import { describe, expect, it } from 'vitest';

import type { Expresion } from '../../src/lib/expresion';
import { MAXIMO_RESUMEN, textoDeContenido } from '../../src/lib/constructor-pantalla';

const etiqueta = (nombre: string) => ({ titular: 'Titular', fecha_vencimiento_cuota: 'Vencimiento', telefono: 'Teléfono' })[nombre] ?? nombre;

const vacia: Expresion = { nodos: [] };
const variable = (nombre = 'telefono', funciones = 0): Expresion => ({
  nodos: [{ tipo: 'variable', nombre, funciones: Array.from({ length: funciones }, () => ({ nombre: 'sumar_dias', args: [3] })) }],
});
const texto = (valor: string): Expresion => ({ nodos: [{ tipo: 'texto', valor }] });
const variantes = (n: number) => Array.from({ length: n }, (_, i) => ({ segmento: `s${i}`, expresion: texto('x') }));

describe('una columna sin contenido', () => {
  it('lo dice, y es la única que cuenta como vacía', () => {
    expect(textoDeContenido({ expresion: vacia, variantes: [] }, etiqueta)).toEqual({ texto: 'Sin contenido', vacio: true });
  });

  it('ignora el resultado de la vista previa', () => {
    expect(textoDeContenido({ expresion: vacia, variantes: [] }, etiqueta, '51900000123')).toEqual({ texto: 'Sin contenido', vacio: true });
  });
});

describe('una variable directa', () => {
  it('nombra la variable por su nombre visible', () => {
    expect(textoDeContenido({ expresion: variable('telefono'), variantes: [] }, etiqueta)).toEqual({ texto: 'Variable: Teléfono', vacio: false });
  });

  it('una variable que el catálogo no conoce se nombra como llega', () => {
    expect(textoDeContenido({ expresion: variable('otra'), variantes: [] }, etiqueta).texto).toBe('Variable: otra');
  });

  it('con funciones cuenta cuántas, sin leerlas', () => {
    expect(textoDeContenido({ expresion: variable('fecha_vencimiento_cuota', 2), variantes: [] }, etiqueta).texto).toBe(
      'Variable: Vencimiento · 2 funciones',
    );
  });

  it('ignora el resultado de la vista previa: lo que se muestra es la variable', () => {
    expect(textoDeContenido({ expresion: variable(), variantes: [] }, etiqueta, '51900000123').texto).toBe('Variable: Teléfono');
  });
});

describe('un texto compuesto', () => {
  const compuesto: Expresion = {
    nodos: [
      { tipo: 'variable', nombre: 'titular', funciones: [] },
      { tipo: 'texto', valor: ' te recuerda que tu cuota vence el ' },
      { tipo: 'variable', nombre: 'fecha_vencimiento_cuota', funciones: [] },
    ],
  };

  it('sin resultado muestra el principio del texto, con el nombre visible de cada variable', () => {
    expect(textoDeContenido({ expresion: texto('Hola'), variantes: [] }, etiqueta)).toEqual({ texto: 'Texto: Hola', vacio: false });
    expect(textoDeContenido({ expresion: compuesto, variantes: [] }, etiqueta, null).texto).toMatch(/^Texto: Titular te recuerda/);
  });

  it('uno largo se corta en el máximo y termina en «…»', () => {
    const largo = textoDeContenido({ expresion: texto('a'.repeat(100)), variantes: [] }, etiqueta);
    expect(largo.texto).toBe(`Texto: ${'a'.repeat(MAXIMO_RESUMEN)}…`);
    // Uno que cabe justo no lleva «…».
    expect(textoDeContenido({ expresion: texto('a'.repeat(MAXIMO_RESUMEN)), variantes: [] }, etiqueta).texto).toBe(`Texto: ${'a'.repeat(MAXIMO_RESUMEN)}`);
  });

  it('con resultado muestra lo que sale, no el texto: lo que el analista lee es lo que se envía', () => {
    expect(textoDeContenido({ expresion: compuesto, variantes: [] }, etiqueta, 'Ana te recuerda que tu cuota vence el 15/11').texto).toBe(
      'Texto: Ana te recuerda que tu cuota vence el 15/11',
    );
  });

  it('un resultado largo se corta y termina en «…»; uno que cabe justo no', () => {
    expect(textoDeContenido({ expresion: compuesto, variantes: [] }, etiqueta, 'b'.repeat(MAXIMO_RESUMEN + 1)).texto).toBe(
      `Texto: ${'b'.repeat(MAXIMO_RESUMEN)}…`,
    );
    expect(textoDeContenido({ expresion: compuesto, variantes: [] }, etiqueta, 'b'.repeat(MAXIMO_RESUMEN)).texto).toBe(`Texto: ${'b'.repeat(MAXIMO_RESUMEN)}`);
  });

  it('el máximo es un parámetro, y con él se corta el texto y el resultado', () => {
    expect(textoDeContenido({ expresion: texto('abcdefghij'), variantes: [] }, etiqueta, null, 4).texto).toBe('Texto: abcd…');
    expect(textoDeContenido({ expresion: compuesto, variantes: [] }, etiqueta, 'abcdefghij', 4).texto).toBe('Texto: abcd…');
  });

  it('el máximo por defecto es 60', () => {
    expect(MAXIMO_RESUMEN).toBe(60);
  });
});

describe('una columna que varía por segmento', () => {
  it('suma «1 variante» o «N variantes» al final, sea cual sea su contenido', () => {
    expect(textoDeContenido({ expresion: variable(), variantes: variantes(1) }, etiqueta).texto).toBe('Variable: Teléfono · 1 variante');
    expect(textoDeContenido({ expresion: texto('Hola'), variantes: variantes(3) }, etiqueta).texto).toBe('Texto: Hola · 3 variantes');
  });

  it('sin contenido propio sigue contando como vacía, con sus variantes dichas', () => {
    expect(textoDeContenido({ expresion: vacia, variantes: variantes(2) }, etiqueta)).toEqual({ texto: 'Sin contenido · 2 variantes', vacio: true });
  });

  it('el resultado de la vista previa no cambia la cuenta de variantes', () => {
    expect(textoDeContenido({ expresion: texto('x'), variantes: variantes(2) }, etiqueta, 'Ana').texto).toBe('Texto: Ana · 2 variantes');
  });
});

describe('no toca lo que recibe', () => {
  it('ni la columna ni su expresión', () => {
    const columna = { expresion: texto('Hola'), variantes: variantes(1) };
    const antes = JSON.stringify(columna);
    textoDeContenido(columna, etiqueta, 'Ana');
    expect(JSON.stringify(columna)).toBe(antes);
  });
});

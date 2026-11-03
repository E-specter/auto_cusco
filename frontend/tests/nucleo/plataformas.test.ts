/**
 * What a platform fixes in a column definition (RF-72, docs/motor-texto-enriquecido-interfaz.md §11.2):
 * which rows are fixed, the header a position gives, the starting content of a fixed column, and the
 * words of the rules. All data is invented.
 */
import { describe, expect, it } from 'vitest';

import {
  cantidadDeFijas,
  encabezadoEditado,
  encabezadoPorPosicion,
  expresionDeTexto,
  numeroPorPosicion,
  reglasDe,
  type ReglasPlataforma,
} from '../../src/lib/plataformas';
import { fraseDeReglas, textoDeProblema } from '../../src/lib/plataformas-texto';

const reglas = (parcial: Partial<ReglasPlataforma> = {}): ReglasPlataforma => ({
  clave: 'sintetica',
  etiqueta: 'Sintética',
  columnas_fijas: [
    { posicion: 1, nombre: 'destino', contenido_por_defecto: '51[@telefono]', tipo: 'texto', celda_texto: true, contenido_editable: true },
    { posicion: 2, nombre: 'canal', contenido_por_defecto: 'sms', tipo: 'texto', celda_texto: false, contenido_editable: false },
  ],
  encabezado_por_posicion: '[$VAR{n}$]',
  tipo_resto: 'texto',
  admite_mas_columnas: true,
  ...parcial,
});

const nombres = (...n: string[]) => n.map((nombre) => ({ nombre }));

describe('reglasDe', () => {
  it('encuentra la plataforma por su clave, y un archivo libre o una clave que nadie registró no tiene reglas', () => {
    const lista = [reglas(), reglas({ clave: 'otra' })];
    expect(reglasDe(lista, 'otra')?.clave).toBe('otra');
    expect(reglasDe(lista, null)).toBeNull();
    expect(reglasDe(lista, 'borrada')).toBeNull();
    expect(reglasDe([], 'sintetica')).toBeNull();
  });
});

describe('encabezado por posición', () => {
  it('cuenta desde 1 después de las fijas', () => {
    const r = reglas();
    expect(encabezadoPorPosicion(r, 2)).toBe('[$VAR1$]');
    expect(encabezadoPorPosicion(r, 3)).toBe('[$VAR2$]');
    expect(numeroPorPosicion(r, 4)).toBe(3);
  });

  it('una posición fija no tiene encabezado por posición', () => {
    const r = reglas();
    expect(encabezadoPorPosicion(r, 0)).toBeNull();
    expect(encabezadoPorPosicion(r, 1)).toBeNull();
    expect(numeroPorPosicion(r, 1)).toBe(0);
  });

  it('una plataforma sin patrón no pone encabezados', () => {
    expect(encabezadoPorPosicion(reglas({ encabezado_por_posicion: null }), 5)).toBeNull();
  });

  it('sin columnas fijas la primera es la 1', () => {
    expect(encabezadoPorPosicion(reglas({ columnas_fijas: [] }), 0)).toBe('[$VAR1$]');
  });

  it('un encabezado está editado cuando no es el de su posición', () => {
    const r = reglas();
    expect(encabezadoEditado(r, 2, '[$VAR1$]')).toBe(false);
    expect(encabezadoEditado(r, 2, 'Nombres del titular')).toBe(true);
    expect(encabezadoEditado(r, 2, '[$VAR2$]')).toBe(true);
    expect(encabezadoEditado(r, 2, '')).toBe(true);
    // Nada que comparar en una posición fija ni sin patrón.
    expect(encabezadoEditado(r, 0, 'lo que sea')).toBe(false);
    expect(encabezadoEditado(reglas({ encabezado_por_posicion: null }), 2, 'x')).toBe(false);
  });
});

describe('cantidadDeFijas', () => {
  it('cuenta las filas de arriba que llevan el nombre de la plataforma en su posición', () => {
    const r = reglas();
    expect(cantidadDeFijas(nombres('destino', 'canal', 'otra'), r)).toBe(2);
    expect(cantidadDeFijas(nombres('destino'), r)).toBe(1);
    expect(cantidadDeFijas(nombres(), r)).toBe(0);
  });

  it('una fija movida, ausente o renombrada no es fija en pantalla, y corta la cuenta', () => {
    const r = reglas();
    expect(cantidadDeFijas(nombres('canal', 'destino'), r)).toBe(0);
    expect(cantidadDeFijas(nombres('otra', 'canal'), r)).toBe(0);
    expect(cantidadDeFijas(nombres('destino', 'otra', 'canal'), r)).toBe(1);
    expect(cantidadDeFijas(nombres('Destino', 'canal'), r)).toBe(0);
  });

  it('sin plataforma no hay filas fijas', () => {
    expect(cantidadDeFijas(nombres('destino', 'canal'), null)).toBe(0);
  });
});

describe('expresionDeTexto', () => {
  it('lee una referencia sola, con un prefijo y con texto en los dos lados', () => {
    expect(expresionDeTexto('[@telefono]').nodos).toEqual([{ tipo: 'variable', nombre: 'telefono', funciones: [] }]);
    expect(expresionDeTexto('51[@telefono]').nodos).toEqual([
      { tipo: 'texto', valor: '51' },
      { tipo: 'variable', nombre: 'telefono', funciones: [] },
    ]);
    expect(expresionDeTexto('Hola [@titular], pagas [@monto] hoy').nodos.map((n) => n.tipo)).toEqual([
      'texto',
      'variable',
      'texto',
      'variable',
      'texto',
    ]);
  });

  it('un texto sin referencias es un solo literal, y vacío o nulo no tiene nodos', () => {
    expect(expresionDeTexto('sms').nodos).toEqual([{ tipo: 'texto', valor: 'sms' }]);
    expect(expresionDeTexto('').nodos).toEqual([]);
  });

  it('[@@] es el escape de un [@ literal y se junta con el texto de al lado', () => {
    expect(expresionDeTexto('a[@@]b').nodos).toEqual([{ tipo: 'texto', valor: 'a[@b' }]);
  });

  it('una referencia con funciones queda como texto: el lector de verdad es el del backend', () => {
    expect(expresionDeTexto('[@titular | primeros(8)]').nodos).toEqual([{ tipo: 'texto', valor: '[@titular | primeros(8)]' }]);
  });
});

describe('las palabras de las reglas', () => {
  it('arman la frase de las reglas con la plataforma, las fijas, la posición y el tipo', () => {
    expect(fraseDeReglas(reglas({ columnas_fijas: reglas().columnas_fijas.slice(0, 1) }))).toBe(
      'Sintética: la 1.ª columna, «destino», es fija; las siguientes se llaman por su posición, [$VAR1$], [$VAR2$]…, y son de texto.',
    );
  });

  it('dice que no se agregan más columnas solo cuando la plataforma no las admite', () => {
    expect(fraseDeReglas(reglas({ admite_mas_columnas: false }))).toContain('y no se agregan más columnas');
    expect(fraseDeReglas(reglas())).not.toContain('no se agregan más columnas');
  });

  it('una regla que no está puesta no agrega nada', () => {
    const frase = fraseDeReglas(reglas({ encabezado_por_posicion: null, tipo_resto: null }));
    expect(frase).toBe('Sintética: la 1.ª columna, «destino», es fija; la 2.ª columna, «canal», es fija.');
  });

  it('un código de la plataforma se dice con el nombre de la columna; cualquier otro, con su detalle', () => {
    const base = { detalle: 'Del backend', nombre: 'destino' };
    expect(textoDeProblema({ ...base, codigo: 'plataforma_columna_fija_ausente' })).toBe(
      'Falta la columna fija «destino» de la plataforma. Agrégala en su posición.',
    );
    expect(textoDeProblema({ ...base, codigo: 'nombre_repetido' })).toBe('Del backend');
    // Un código de plataforma que esta versión no conoce cae al detalle, nunca a la clave.
    expect(textoDeProblema({ ...base, codigo: 'plataforma_que_no_existe' as never })).toBe('Del backend');
  });
});

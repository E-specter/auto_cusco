/**
 * The default supervisors' drafts and problems (the screen logic of `/supervisores`). Numbers are
 * synthetic, in the 900000xxx range.
 */
import { describe, expect, it } from 'vitest';

import { formatNumber } from '../../src/lib/format';
import { t } from '../../src/lib/i18n';
import {
  borradorDeSupervision,
  entradaSupervision,
  LARGO_MAXIMO_PROCEDENCIA,
  moverElemento,
  problemasSupervision,
  renombrarProcedencia,
  supervisionCambio,
  textoDeProblemaSupervision,
} from '../../src/lib/supervision';
import { setLanguageForTests } from './idioma';

describe('borrador de supervisores', () => {
  const guardada = {
    procedencias: ['Procedencia A', 'Procedencia B'],
    supervisores: [
      { numero: '900000101', procedencia: 'Procedencia A', documento: '00000001' },
      { numero: '900000102', procedencia: 'Procedencia B', documento: '00000002' },
    ],
  };

  it('parte de lo guardado sin cambios', () => {
    expect(supervisionCambio(guardada, borradorDeSupervision(guardada))).toBe(false);
  });

  it('los espacios de los extremos no cuentan como cambio y no viajan', () => {
    const borrador = borradorDeSupervision(guardada);
    borrador.supervisores[0].numero = ' 900000101 ';
    expect(supervisionCambio(guardada, borrador)).toBe(false);
    expect(entradaSupervision(borrador).supervisores[0].numero).toBe('900000101');
  });

  it('renombrar una procedencia arrastra a sus supervisores', () => {
    const renombrado = renombrarProcedencia(borradorDeSupervision(guardada), 0, 'Procedencia C');
    expect(renombrado.procedencias).toEqual(['Procedencia C', 'Procedencia B']);
    expect(renombrado.supervisores.map((s) => s.procedencia)).toEqual(['Procedencia C', 'Procedencia B']);
    expect(supervisionCambio(guardada, renombrado)).toBe(true);
  });

  it('mover cambia el orden, y fuera de rango no hace nada', () => {
    expect(moverElemento(['a', 'b', 'c'], 0, 1)).toEqual(['b', 'a', 'c']);
    expect(moverElemento(['a', 'b', 'c'], 2, -1)).toEqual(['a', 'c', 'b']);
    expect(moverElemento(['a', 'b', 'c'], 0, -1)).toEqual(['a', 'b', 'c']);
    expect(moverElemento(['a', 'b', 'c'], 2, 1)).toEqual(['a', 'b', 'c']);
  });

  it('una lista válida no tiene problemas', () => {
    expect(problemasSupervision(borradorDeSupervision(guardada))).toEqual([]);
  });

  it('señala procedencias vacías, largas y repetidas sin distinguir mayúsculas', () => {
    const problemas = problemasSupervision({
      procedencias: ['Procedencia A', ' ', 'procedencia a', 'x'.repeat(61)],
      supervisores: [],
    });
    expect(problemas).toEqual([
      { tipo: 'procedencia_vacia', indice: 1 },
      { tipo: 'procedencia_repetida', indice: 2 },
      { tipo: 'procedencia_larga', indice: 3 },
    ]);
  });

  it('señala un supervisor sin número o con una procedencia que ya no está', () => {
    const problemas = problemasSupervision({
      procedencias: ['Procedencia A'],
      supervisores: [
        { numero: '', procedencia: 'Procedencia A' },
        { numero: '900000103', procedencia: 'Procedencia borrada' },
      ],
    });
    expect(problemas).toEqual([
      { tipo: 'numero_vacio', indice: 0 },
      { tipo: 'procedencia_desconocida', indice: 1 },
    ]);
  });

  it('sin procedencias no se puede guardar', () => {
    expect(problemasSupervision({ procedencias: [], supervisores: [] })).toEqual([
      { tipo: 'sin_procedencias' },
    ]);
  });
});

describe('textoDeProblemaSupervision (el largo de la procedencia sale de la constante que valida)', () => {
  it('en español y en inglés, con el número de la procedencia y el máximo', () => {
    setLanguageForTests('es');
    expect(textoDeProblemaSupervision({ tipo: 'procedencia_larga', indice: 2 })).toBe('La procedencia 3 pasa de 60 caracteres.');
    setLanguageForTests('en');
    expect(textoDeProblemaSupervision({ tipo: 'procedencia_larga', indice: 2 })).toBe('Origin 3 is longer than 60 characters.');
    setLanguageForTests('es');
  });

  it.each(['es', 'en'] as const)('(%s) el máximo que dice es exactamente LARGO_MAXIMO_PROCEDENCIA, formateado', (idioma) => {
    setLanguageForTests(idioma);
    expect(textoDeProblemaSupervision({ tipo: 'procedencia_larga', indice: 0 })).toContain(
      formatNumber(LARGO_MAXIMO_PROCEDENCIA),
    );
    setLanguageForTests('es');
  });

  it('la constante es la que valida problemasSupervision: justo en el borde', () => {
    const conLargo = (largo: number) =>
      problemasSupervision({ procedencias: ['x'.repeat(largo)], supervisores: [{ numero: '900000101', procedencia: 'x'.repeat(largo) }] });
    expect(conLargo(LARGO_MAXIMO_PROCEDENCIA).map((p) => p.tipo)).not.toContain('procedencia_larga');
    expect(conLargo(LARGO_MAXIMO_PROCEDENCIA + 1).map((p) => p.tipo)).toContain('procedencia_larga');
  });

  it('el diccionario no lleva el número escrito: es el placeholder {max}', () => {
    for (const idioma of ['es', 'en'] as const) {
      setLanguageForTests(idioma);
      const marcado = t('supervisores.problema.procedencia_larga', { n: 'N', max: 'MAX' });
      expect(marcado, idioma).toContain('MAX');
      expect(marcado.replace(/MAX|N/g, ''), idioma).not.toMatch(/\d/);
    }
    setLanguageForTests('es');
  });

  it('los demás problemas siguen diciendo su número de fila', () => {
    setLanguageForTests('es');
    expect(textoDeProblemaSupervision({ tipo: 'numero_vacio', indice: 2 })).toBe('El supervisor 3 no tiene número.');
  });
});

/**
 * Which fields a definition uses, so a preview can say it still uses an archived one (RF-65).
 */
import { describe, expect, it } from 'vitest';

import type { Borrador } from '../../src/lib/constructor-columnas';
import { variablesEnUso } from '../../src/lib/variables-en-uso';

const columna = (nodos: Borrador['columnas'][number]['expresion']['nodos'], variantes: Borrador['columnas'][number]['variantes'] = []) =>
  ({
    id: 'c',
    nombre: 'n',
    tipo: 'texto',
    formato_fecha: null,
    formato_financiero: { decimales: 2, separador_miles: true, simbolo: null } as never,
    expresion: { nodos },
    valor_por_defecto: null,
    variantes,
  }) as Borrador['columnas'][number];

const borrador = (columnas: Borrador['columnas'], segmentacion: Borrador['segmentacion'] = null): Borrador => ({
  nombre: 'd',
  columnas,
  segmentacion,
  proteger_formulas: false,
});

describe('los campos que usa una definición', () => {
  it('toma las variables de las columnas, texto aparte', () => {
    const b = borrador([
      columna([
        { tipo: 'texto', valor: 'Hola ' },
        { tipo: 'variable', nombre: 'titular', funciones: [] },
      ]),
      columna([{ tipo: 'variable', nombre: 'ad_zona', funciones: [] }]),
    ]);
    expect(variablesEnUso(b)).toEqual(['titular', 'ad_zona']);
  });

  it('cuenta las variables a las que apunta el argumento de una función', () => {
    const b = borrador([
      columna([{ tipo: 'variable', nombre: 'titular', funciones: [{ nombre: 'si_vacio', args: [{ variable: 'ad_viejo' }, 'x', 3] }] }]),
    ]);
    expect(variablesEnUso(b)).toEqual(['titular', 'ad_viejo']);
  });

  it('cuenta las variantes por segmento y el campo por el que se segmenta', () => {
    const b = borrador(
      [
        columna(
          [{ tipo: 'texto', valor: 'x' }],
          [{ segmento: 'a', expresion: { nodos: [{ tipo: 'variable', nombre: 'ad_zona', funciones: [] }] } }],
        ),
      ],
      { criterio: { tipo: 'campo', campo: 'ad_region' }, politica: 'excluir' },
    );
    expect(variablesEnUso(b)).toEqual(['ad_zona', 'ad_region']);
  });

  it('una segmentación por días no suma ningún campo', () => {
    const b = borrador([columna([{ tipo: 'texto', valor: 'x' }])], {
      criterio: { tipo: 'calculado', tabla: [], variable_dias: 'dias_atraso' },
      politica: 'excluir',
    });
    expect(variablesEnUso(b)).toEqual([]);
  });
});

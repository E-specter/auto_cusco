/**
 * Pure state of the header mapper: the origin each gesture sends (the backend
 * counts `manual` as a review), what the tag says, fields in use and what is
 * left to review. Every header and field is synthetic.
 */
import { describe, expect, it } from 'vitest';

import {
  aceptar,
  aceptarTodas,
  asignacionesIniciales,
  elegir,
  etiquetaColumna,
  insignia,
  modificado,
  pendiente,
  porRevisar,
  usos,
  type Analisis,
} from '../../src/lib/mapeador';

const ANALISIS: Analisis = {
  borrador_id: 1,
  catalogo_id: 'sabana_vencida',
  formato: 'xlsx',
  hojas: ['VENCIDA'],
  hoja: 'VENCIDA',
  separador: null,
  codificacion: null,
  filas: 10,
  columnas: [
    { indice: 0, encabezado: 'Pagare', ejemplos: ['1'], estado: 'coincide', sugerido: 'pagare', similitud: null },
    { indice: 1, encabezado: 'Saldo Capital', ejemplos: ['1.5'], estado: 'parecido', sugerido: 'saldo_capital_pendiente', similitud: 0.8 },
    { indice: 2, encabezado: 'Nombre', ejemplos: ['X'], estado: 'recordado', sugerido: 'titular', similitud: null },
    { indice: 3, encabezado: 'Otra cosa', ejemplos: [], estado: 'sin_coincidencia', sugerido: null, similitud: null },
  ],
  problemas: [],
  advertencias: [],
  detectados: [],
};

const iniciales = asignacionesIniciales(ANALISIS);
const de = (a: ReturnType<typeof asignacionesIniciales>, indice: number) => a.find((x) => x.indice === indice)!;

describe('columna como la ve el analista', () => {
  it('letras en una hoja de cálculo y números en CSV o JSON', () => {
    expect(etiquetaColumna(0, 'xlsx')).toBe('A');
    expect(etiquetaColumna(25, 'ods')).toBe('Z');
    expect(etiquetaColumna(26, 'xls')).toBe('AA');
    expect(etiquetaColumna(701, 'xlsb')).toBe('ZZ');
    expect(etiquetaColumna(702, 'xlsx')).toBe('AAA');
    expect(etiquetaColumna(0, 'csv')).toBe('1');
    expect(etiquetaColumna(9, 'json')).toBe('10');
  });
});

describe('origen de cada gesto', () => {
  it('al empezar: un parecido queda sin revisar (coincide), nunca manual; sin coincidencia en «No cargar» es manual', () => {
    expect(iniciales.map((a) => a.origen)).toEqual(['coincide', 'coincide', 'recordado', 'manual']);
    expect(de(iniciales, 1).campo).toBe('saldo_capital_pendiente');
  });

  it('volver a elegir el sugerido en la lista no lo acepta', () => {
    const otra = elegir(iniciales, ANALISIS, 1, 'titular');
    const devuelta = elegir(otra, ANALISIS, 1, 'saldo_capital_pendiente');

    expect(de(otra, 1).origen).toBe('manual');
    expect(de(devuelta, 1).origen).toBe('coincide');
    expect(pendiente(ANALISIS.columnas[1], de(devuelta, 1))).toBe(true);
  });

  it('«Aceptar» manda parecido_aceptado con el sugerido; «Aceptar sugerencias» solo los pendientes', () => {
    expect(de(aceptar(iniciales, ANALISIS, 1), 1)).toEqual({ indice: 1, campo: 'saldo_capital_pendiente', origen: 'parecido_aceptado' });

    const conOtro = elegir(iniciales, ANALISIS, 1, null);
    expect(aceptarTodas(conOtro, ANALISIS)).toEqual(conOtro);
    expect(de(aceptarTodas(iniciales, ANALISIS), 1).origen).toBe('parecido_aceptado');
  });

  it('en una columna no parecida, el campo del análisis conserva su origen y otro es manual', () => {
    expect(de(elegir(iniciales, ANALISIS, 2, 'telefono'), 2).origen).toBe('manual');
    expect(de(elegir(elegir(iniciales, ANALISIS, 2, 'telefono'), ANALISIS, 2, 'titular'), 2).origen).toBe('recordado');
  });
});

describe('lo que dice el tag', () => {
  it('el estado del análisis mientras tenga su campo; «Elegido a mano» solo con otro, y vuelve al original', () => {
    expect(ANALISIS.columnas.map((c) => insignia(c, de(iniciales, c.indice)))).toEqual(['coincide', 'por_revisar', 'recordado', 'sin_coincidencia']);
    expect(insignia(ANALISIS.columnas[1], de(aceptar(iniciales, ANALISIS, 1), 1))).toBe('aceptado');

    const cambiada = elegir(iniciales, ANALISIS, 2, 'telefono');
    expect(insignia(ANALISIS.columnas[2], de(cambiada, 2))).toBe('manual');
    expect(insignia(ANALISIS.columnas[2], de(elegir(cambiada, ANALISIS, 2, 'titular'), 2))).toBe('recordado');
  });
});

describe('si el analista cambió algo', () => {
  it('no al empezar; sí al elegir otro campo o al aceptar; volver a lo de antes ya no cuenta', () => {
    expect(modificado(iniciales, ANALISIS)).toBe(false);
    expect(modificado(elegir(iniciales, ANALISIS, 2, 'telefono'), ANALISIS)).toBe(true);
    expect(modificado(aceptar(iniciales, ANALISIS, 1), ANALISIS)).toBe(true);
    expect(modificado(elegir(elegir(iniciales, ANALISIS, 2, 'telefono'), ANALISIS, 2, 'titular'), ANALISIS)).toBe(false);
  });
});

describe('campos en uso y lo que falta revisar', () => {
  it('cada campo con las columnas que lo usan; «No cargar» no cuenta', () => {
    const repetido = elegir(iniciales, ANALISIS, 3, 'pagare');
    expect(usos(repetido).get('pagare')).toEqual([0, 3]);
    expect(usos(iniciales).has('null')).toBe(false);
  });

  it('por revisar: los parecidos pendientes y las columnas con un problema; el problema sin columna no suma', () => {
    const problemas = [
      { indice: 2, codigo: 'campo_repetido' as const, detalle: '', campo: 'titular' },
      { indice: null, codigo: 'obligatorio_sin_columna' as const, detalle: '', campo: 'pagare' },
    ];
    expect([...porRevisar(ANALISIS, iniciales, problemas)].sort()).toEqual([1, 2]);
    expect([...porRevisar(ANALISIS, aceptar(iniciales, ANALISIS, 1), [])]).toEqual([]);
  });
});

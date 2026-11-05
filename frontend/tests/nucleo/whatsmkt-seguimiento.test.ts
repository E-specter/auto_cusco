/**
 * What the WhatsMKT tracking screen decides on its own (T-WM-F3a): which campaigns a filter keeps, the options of the filters, what a row says
 * about its report, the pending count, and the head, the figures and the «fuera del lote» of a detail. The API counts; this orders and reads.
 */
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';

import type { DetalleCampana, ResumenCampana } from '../../src/lib/api-whatsmkt';
import { detalleDeExclusion } from '../../src/lib/whatsmkt';
import {
  SEGMENTO_GLOBAL,
  SIN_FILTRO,
  avisoDeTotalDistinto,
  cifrasDeDetalle,
  encabezadoDeDetalle,
  estadoDeFila,
  fechasDeDetalle,
  filtrarCampanas,
  fueraDelLoteVisible,
  lineaDeInforme,
  lotesDeLista,
  mesDeEnvio,
  mesesDeLista,
  pendienteDeInforme,
  segmentosDeLista,
  tablasDeConciliacion,
  textoDeHorarios,
  textoDeNombreInformado,
  textoDePendientes,
  textoSinCorrespondencia,
} from '../../src/lib/whatsmkt-seguimiento';
import { setLanguageForTests } from './idioma';

beforeAll(() => setLanguageForTests('es'));
afterEach(() => setLanguageForTests('es'));

const horario = (nombre: string) => ({ nombre, inicio: '08:00', fin: '14:00' });
const campana = (id: number, parcial: Partial<ResumenCampana> = {}): ResumenCampana => ({
  id,
  nombre: `CUZCO ${id}`,
  lote_id: 12,
  segmento: 'preventivo',
  segmento_etiqueta: 'Preventivo',
  fecha_envio: '2026-10-15',
  horarios: [horario('horario_1')],
  cantidad: 520,
  creada_en: '2026-10-14T10:00:00-05:00',
  descartada_en: null,
  con_informe: false,
  ...parcial,
});

const LISTA = [
  campana(5, { lote_id: 13, segmento: null, segmento_etiqueta: null, fecha_envio: '2026-11-02', con_informe: true }),
  campana(4, { lote_id: 12, segmento: 'tramo_2', segmento_etiqueta: 'Tramo 2' }),
  campana(3, { lote_id: 12 }),
  campana(2, { lote_id: 11, fecha_envio: '2026-09-28', segmento: 'mayores_2', segmento_etiqueta: 'Tramos mayores al 2' }),
];

describe('los filtros de la lista', () => {
  it('sin filtro deja todas, en el orden en que llegaron', () => {
    expect(filtrarCampanas(LISTA, SIN_FILTRO).map((c) => c.id)).toEqual([5, 4, 3, 2]);
  });

  it('por mes de envío, por lote y por segmento, cada uno aparte y juntos', () => {
    expect(filtrarCampanas(LISTA, { ...SIN_FILTRO, mes: '2026-10' }).map((c) => c.id)).toEqual([4, 3]);
    expect(filtrarCampanas(LISTA, { ...SIN_FILTRO, lote: 11 }).map((c) => c.id)).toEqual([2]);
    expect(filtrarCampanas(LISTA, { ...SIN_FILTRO, segmento: 'tramo_2' }).map((c) => c.id)).toEqual([4]);
    expect(filtrarCampanas(LISTA, { mes: '2026-10', lote: 12, segmento: 'preventivo' }).map((c) => c.id)).toEqual([3]);
  });

  it('una campaña global (sin segmento) se filtra como «global»', () => {
    expect(filtrarCampanas(LISTA, { ...SIN_FILTRO, segmento: SEGMENTO_GLOBAL }).map((c) => c.id)).toEqual([5]);
  });

  it('el mes de envío es el de la fecha de envío, no el de creación', () => {
    expect(mesDeEnvio(campana(1, { fecha_envio: '2026-12-31', creada_en: '2026-10-01T00:00:00-05:00' }))).toBe('2026-12');
  });
});

describe('las opciones de los filtros', () => {
  it('los meses, del más nuevo al más viejo y una sola vez', () => {
    expect(mesesDeLista(LISTA)).toEqual(['2026-11', '2026-10', '2026-09']);
  });

  it('los lotes, del último al primero y una sola vez', () => {
    expect(lotesDeLista(LISTA)).toEqual([13, 12, 11]);
  });

  it('los segmentos, con «Global» para los que no tienen, en el orden en que aparecen', () => {
    expect(segmentosDeLista(LISTA)).toEqual([
      { valor: SEGMENTO_GLOBAL, texto: 'Global' },
      { valor: 'tramo_2', texto: 'Tramo 2' },
      { valor: 'preventivo', texto: 'Preventivo' },
      { valor: 'mayores_2', texto: 'Tramos mayores al 2' },
    ]);
  });
});

describe('lo que dice una fila', () => {
  it('una campaña viva sin informe está pendiente; con informe no dice nada; una descartada se dice descartada', () => {
    expect(estadoDeFila(campana(1))).toBe('pendiente');
    expect(estadoDeFila(campana(1, { con_informe: true }))).toBe('conciliada');
    expect(estadoDeFila(campana(1, { descartada_en: '2026-10-20T09:00:00-05:00' }))).toBe('descartada');
  });

  it('una descartada nunca está pendiente, aunque no tenga informe', () => {
    expect(pendienteDeInforme(campana(1))).toBe(true);
    expect(pendienteDeInforme(campana(1, { descartada_en: '2026-10-20T09:00:00-05:00' }))).toBe(false);
    expect(pendienteDeInforme(campana(1, { con_informe: true }))).toBe(false);
  });

  it('los horarios se nombran como en la configuración', () => {
    expect(textoDeHorarios({ horarios: [horario('horario_1'), horario('horario_2')] })).toBe('Horario 1 · Horario 2');
  });

  it('los pendientes, en singular o plural y nada con cero', () => {
    expect(textoDePendientes(0)).toBeNull();
    expect(textoDePendientes(1)).toBe('1 campaña pendiente del informe');
    expect(textoDePendientes(2)).toBe('2 campañas pendientes del informe');
  });
});

describe('el detalle', () => {
  const pagina = (total: number): DetalleCampana['exclusiones'] => ({ total, limite: 100, desplazamiento: 0, exclusiones: [] });
  const detalle = (parcial: Partial<DetalleCampana> = {}): DetalleCampana =>
    ({
      ...campana(37),
      lote: { id: 12, modo: 'por_segmento' },
      fecha_corte: '2026-09-13',
      productos: 1000,
      supervisores: 2,
      archivo: { nombre: 'a.xlsx', tamano: 1, filas: 1002 },
      exclusiones: pagina(12),
      exclusiones_fuera_del_lote: pagina(87),
      ...parcial,
    }) as DetalleCampana;

  it('el encabezado dice la campaña, su segmento y su lote; una global no dice segmento', () => {
    expect(encabezadoDeDetalle(detalle())).toBe('Campaña 37 · Preventivo · lote 12');
    expect(encabezadoDeDetalle(detalle({ segmento: null, segmento_etiqueta: null }))).toBe('Campaña 37 · lote 12');
  });

  it('las fechas dicen el corte, el envío y los horarios', () => {
    expect(fechasDeDetalle(detalle())).toMatch(/^Corte 13 set\.? 2026 · envío 15 oct\.? 2026 · Horario 1$/);
  });

  it('las cifras son los productos, la supervisión, el total cargado y los excluidos', () => {
    expect(cifrasDeDetalle(detalle())).toEqual([
      { clave: 'productos', valor: 1000 },
      { clave: 'supervision', valor: 2 },
      { clave: 'total', valor: 1002 },
      { clave: 'excluidos', valor: 12 },
    ]);
  });

  it('los productos fuera del lote se ven solo con alguno y nunca en un lote global', () => {
    expect(fueraDelLoteVisible(detalle())).toBe(true);
    expect(fueraDelLoteVisible(detalle({ exclusiones_fuera_del_lote: pagina(0) }))).toBe(false);
    expect(fueraDelLoteVisible(detalle({ lote: { id: 12, modo: 'global' } }))).toBe(false);
  });
});

describe('el informe y su conciliación', () => {
  // The day of an instant is the browser's: the zone is fixed so that the test does not depend on the machine.
  const zonaAntes = process.env.TZ;
  beforeAll(() => {
    process.env.TZ = 'America/Lima';
  });
  afterAll(() => {
    if (zonaAntes === undefined) delete process.env.TZ;
    else process.env.TZ = zonaAntes;
  });

  const informe = { fecha_informada: '2026-10-30', importado_en: '2026-10-31T09:00:00-05:00', total_informado: 101, filas: 101, coincide_total: true as boolean | null };
  const conciliacion = {
    productos: { cargados: 99, enviados: 97, no_enviados: 2 },
    supervision: { cargados: 2, enviados: 2, no_enviados: 0 },
    total: { cargados: 101, enviados: 99, no_enviados: 2 },
    sin_correspondencia: ['900000901', '900000902'],
    total_sin_correspondencia: 2,
  };

  it('la línea del informe dice su fecha, el total que informó y sus filas', () => {
    expect(lineaDeInforme(informe)).toMatch(/^Informe del 30 oct\.? 2026 · total informado 101 · 101 filas$/);
  });

  it('lo que el informe no dijo queda en un guion, y la fecha cae en el día en que se importó', () => {
    expect(lineaDeInforme({ ...informe, fecha_informada: null, total_informado: null })).toMatch(/^Informe del 31 oct\.? 2026 · total informado — · 101 filas$/);
  });

  it('el día de importación es el de Lima aunque el instante, en UTC, ya sea el siguiente', () => {
    // 20:00 in Lima on the 30th is 01:00Z on the 31st: the first ten characters of the text say 31, and the analyst lives on the 30th.
    expect(lineaDeInforme({ ...informe, fecha_informada: null, importado_en: '2026-10-31T01:00:00Z' })).toMatch(/^Informe del 30 oct\.? 2026/);
    // And an instant early in the day, in UTC, that is still the day before in Lima.
    expect(lineaDeInforme({ ...informe, fecha_informada: null, importado_en: '2026-10-31T04:59:00Z' })).toMatch(/^Informe del 30 oct\.? 2026/);
    expect(lineaDeInforme({ ...informe, fecha_informada: null, importado_en: '2026-10-31T05:00:00Z' })).toMatch(/^Informe del 31 oct\.? 2026/);
  });

  it('la línea va en inglés', () => {
    setLanguageForTests('en');
    expect(lineaDeInforme(informe)).toMatch(/^Report of 30 Oct\.? 2026 · reported total 101 · 101 rows$/);
  });

  it('el aviso de total distinto solo sale cuando el informe dijo uno y no es el de sus filas', () => {
    expect(avisoDeTotalDistinto({ ...informe, total_informado: 101, filas: 99, coincide_total: false })).toBe(
      'El informe dice 101 enviados y trae 99 filas. La conciliación usa las filas.',
    );
    expect(avisoDeTotalDistinto(informe)).toBeNull();
    // No total said: there is nothing to compare, and it does not invent one.
    expect(avisoDeTotalDistinto({ ...informe, total_informado: null, coincide_total: null })).toBeNull();
  });

  it('los productos y la supervisión van cada uno en su tabla, sin sumarse', () => {
    expect(tablasDeConciliacion(conciliacion)).toEqual([
      { clave: 'productos', cargados: 99, enviados: 97, noEnviados: 2 },
      { clave: 'supervision', cargados: 2, enviados: 2, noEnviados: 0 },
    ]);
  });

  it('con informe las cifras suman los enviados y los no enviados del total; sin él no', () => {
    const detalle = { productos: 99, supervisores: 2, archivo: { nombre: 'a.xlsx', tamano: 1, filas: 101 }, exclusiones: { total: 12, limite: 100, desplazamiento: 0, exclusiones: [] } };
    expect(cifrasDeDetalle(detalle).map((c) => c.clave)).toEqual(['productos', 'supervision', 'total', 'excluidos']);
    expect(cifrasDeDetalle(detalle, conciliacion).slice(4)).toEqual([
      { clave: 'enviados', valor: 99 },
      { clave: 'noEnviados', valor: 2 },
    ]);
  });

  it('los números sin correspondencia se dicen con su cuenta, y con cero no se dicen', () => {
    expect(textoSinCorrespondencia(conciliacion)).toBe('Números del informe que no están en la carga: 2');
    expect(textoSinCorrespondencia({ total_sin_correspondencia: 0 })).toBeNull();
  });

  it('el nombre que trae el informe se lee, y sin nombre no se dice nada', () => {
    expect(textoDeNombreInformado({ campana_informada: 'CUZCO_Vencida (Tramo 2)' })).toBe('Nombre en el informe: CUZCO_Vencida (Tramo 2)');
    expect(textoDeNombreInformado({ campana_informada: null })).toBeNull();
  });
});

describe('el detalle de una exclusión', () => {
  const base = { detalle: 'frase del servidor', macro: null, etiqueta: null };

  it('cada código dice su frase, no la del servidor', () => {
    expect(detalleDeExclusion({ ...base, codigo: 'sin_telefono' })).toBe('No tiene un teléfono registrado.');
    expect(detalleDeExclusion({ ...base, codigo: 'telefono_invalido' })).toBe('El teléfono no es un celular válido.');
  });

  it('una macro vacía nombra la macro y la etiqueta de su columna; sin etiqueta, solo la macro', () => {
    expect(detalleDeExclusion({ ...base, codigo: 'macro_vacia', macro: 2, etiqueta: 'Nombres del titular' })).toBe(
      'La macro 2 (Nombres del titular) queda vacía y su columna no tiene valor por defecto.',
    );
    expect(detalleDeExclusion({ ...base, codigo: 'macro_vacia', macro: 3, etiqueta: null })).toBe('La macro 3 queda vacía y su columna no tiene valor por defecto.');
    expect(detalleDeExclusion({ ...base, codigo: 'macro_vacia', macro: 3, etiqueta: '' })).toBe('La macro 3 queda vacía y su columna no tiene valor por defecto.');
  });

  it('un código sin clave, o una macro vacía sin su número, cae en la frase del servidor', () => {
    expect(detalleDeExclusion({ ...base, codigo: 'sin_mensaje' })).toBe('frase del servidor');
    expect(detalleDeExclusion({ ...base, codigo: 'macro_vacia' })).toBe('frase del servidor');
  });

  it('en inglés', () => {
    setLanguageForTests('en');
    expect(detalleDeExclusion({ ...base, codigo: 'sin_telefono' })).toBe('It has no phone number on record.');
    expect(detalleDeExclusion({ ...base, codigo: 'macro_vacia', macro: 2, etiqueta: 'Holder names' })).toBe('Macro 2 (Holder names) is empty and its column has no default value.');
  });
});

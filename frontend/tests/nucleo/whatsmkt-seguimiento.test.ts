/**
 * What the WhatsMKT tracking screen decides on its own (T-WM-F3a): which campaigns a filter keeps, the options of the filters, what a row says
 * about its report, the pending count, and the head, the figures and the «fuera del lote» of a detail. The API counts; this orders and reads.
 */
import { afterEach, beforeAll, describe, expect, it } from 'vitest';

import type { DetalleCampana, ResumenCampana } from '../../src/lib/api-whatsmkt';
import {
  SEGMENTO_GLOBAL,
  SIN_FILTRO,
  cifrasDeDetalle,
  encabezadoDeDetalle,
  estadoDeFila,
  fechasDeDetalle,
  filtrarCampanas,
  fueraDelLoteVisible,
  lotesDeLista,
  mesDeEnvio,
  mesesDeLista,
  pendienteDeInforme,
  segmentosDeLista,
  textoDeHorarios,
  textoDePendientes,
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

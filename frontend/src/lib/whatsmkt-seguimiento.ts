/**
 * Logic of the WhatsMKT tracking screen (T-WM-F3a, docs/whatsmkt-interfaz.md §4), kept out of the page so it can be tested without a browser.
 * The API counts and the screen only orders, filters and reads what arrived. What is generic to any follow-up (the `?campana=` and `?vista=` of
 * the URL, the months of a select, the day a campaign was discarded) is MOWA MES's own and is used from there, not copied.
 *
 * shortcut: the list is asked once per view with the most the API gives (500) and filtered and paged here, because the API has no filter by
 * segment and no list of months; with more than 500 campaigns in a view the oldest do not show. Upgrade with a month list and a segment filter
 * in the API, and ask for each page.
 */

import type { DetalleCampana, ResumenCampana } from './api-whatsmkt';
import { formatDate } from './format';
import { t } from './i18n';
import { ordenarMeses } from './mowa-mes-seguimiento';
import { nombreDeFranja, type Franja } from './whatsmkt';

export { busquedaConVista, campanaDeLaUrl, fechaDeDescarte, opcionesDeMeses, vistaDeLaUrl, type VistaCampanas } from './mowa-mes-seguimiento';

/** The most campaigns the API gives in one answer. */
export const LIMITE_DE_CAMPANAS = 500;
/** Rows of the list per page. */
export const CAMPANAS_POR_PAGINA = 20;
/** The value of the segment filter for the campaigns that have none (the global ones). */
export const SEGMENTO_GLOBAL = 'global';

// ---- The list --------------------------------------------------------------------------------------------

export interface FiltroDeLista {
  /** `YYYY-MM` or `''` for every month. */
  mes: string;
  /** A lot number, or `null` for every lot. */
  lote: number | null;
  /** The key of a segment, `SEGMENTO_GLOBAL` or `''` for every one. */
  segmento: string;
}

export const SIN_FILTRO: FiltroDeLista = { mes: '', lote: null, segmento: '' };

/** The month a campaign is sent in (`YYYY-MM`). */
export const mesDeEnvio = (campana: Pick<ResumenCampana, 'fecha_envio'>): string => campana.fecha_envio.slice(0, 7);

/** Whether the report of a live campaign is still to be imported: a discarded one is never pending. */
export const pendienteDeInforme = (campana: Pick<ResumenCampana, 'con_informe' | 'descartada_en'>): boolean =>
  !campana.con_informe && campana.descartada_en === null;

/** The campaigns that pass the filter, in the order they came (the latest first, a lot together). */
export function filtrarCampanas(campanas: readonly ResumenCampana[], filtro: FiltroDeLista): ResumenCampana[] {
  return campanas.filter(
    (campana) =>
      (filtro.mes === '' || mesDeEnvio(campana) === filtro.mes) &&
      (filtro.lote === null || campana.lote_id === filtro.lote) &&
      (filtro.segmento === '' || (campana.segmento ?? SEGMENTO_GLOBAL) === filtro.segmento),
  );
}

/** The months of the campaigns, newest first, each once: the options of «Mes de envío». */
export const mesesDeLista = (campanas: readonly ResumenCampana[]): string[] => ordenarMeses(campanas.map(mesDeEnvio));

/** The lots of the campaigns, the latest first, each once: the options of «Lote». */
export const lotesDeLista = (campanas: readonly ResumenCampana[]): number[] =>
  [...new Set(campanas.map((campana) => campana.lote_id))].sort((a, b) => b - a);

/** The segments the campaigns have, in the order they first appear, with «Global» for the ones with none: the options of «Segmento». */
export function segmentosDeLista(campanas: readonly ResumenCampana[]): Array<{ valor: string; texto: string }> {
  const vistos = new Map<string, string>();
  for (const campana of campanas) {
    const valor = campana.segmento ?? SEGMENTO_GLOBAL;
    if (!vistos.has(valor)) vistos.set(valor, campana.segmento_etiqueta ?? t('whatsmkt.seguimiento.filtro.global'));
  }
  return [...vistos].map(([valor, texto]) => ({ valor, texto }));
}

/** The time slots of a campaign as the settings name them: «Horario 1», or «Horario 1 · Horario 2». */
export const textoDeHorarios = (campana: Pick<ResumenCampana, 'horarios'>): string =>
  campana.horarios.map((horario) => nombreDeFranja(horario.nombre as Franja)).join(' · ');

/** What the row says about the report: discarded, pending, or nothing at all when it is already reconciled. */
export type EstadoDeFila = 'descartada' | 'pendiente' | 'conciliada';

export const estadoDeFila = (campana: Pick<ResumenCampana, 'con_informe' | 'descartada_en'>): EstadoDeFila =>
  campana.descartada_en !== null ? 'descartada' : campana.con_informe ? 'conciliada' : 'pendiente';

/** «2 campañas pendientes del informe» or «1 campaña…»; `null` when there is none. */
export function textoDePendientes(cantidad: number): string | null {
  if (cantidad <= 0) return null;
  return cantidad === 1 ? t('whatsmkt.seguimiento.pendientesUna') : t('whatsmkt.seguimiento.pendientes', { n: cantidad });
}

// ---- The detail --------------------------------------------------------------------------------------------

/** «Campaña 37 · Preventivo · lote 12», or without the segment for a global one. */
export function encabezadoDeDetalle(detalle: Pick<DetalleCampana, 'id' | 'segmento_etiqueta' | 'lote'>): string {
  return detalle.segmento_etiqueta === null
    ? t('whatsmkt.seguimiento.encabezadoGlobal', { id: detalle.id, lote: detalle.lote.id })
    : t('whatsmkt.seguimiento.encabezado', { id: detalle.id, segmento: detalle.segmento_etiqueta, lote: detalle.lote.id });
}

/** «Corte 13 set. 2026 · envío 15 set. 2026 · Horario 1»: the dates the campaign was made with. */
export const fechasDeDetalle = (detalle: Pick<DetalleCampana, 'fecha_corte' | 'fecha_envio' | 'horarios'>): string =>
  t('whatsmkt.seguimiento.fechas', {
    corte: formatDate(detalle.fecha_corte),
    envio: formatDate(detalle.fecha_envio),
    horarios: textoDeHorarios(detalle),
  });

export interface CifraDeDetalle {
  clave: 'productos' | 'supervision' | 'total' | 'excluidos';
  valor: number;
}

/** The figures of a campaign without a report: the products loaded, the supervision rows, the total loaded and the ones left out. */
export function cifrasDeDetalle(detalle: Pick<DetalleCampana, 'productos' | 'supervisores' | 'archivo' | 'exclusiones'>): CifraDeDetalle[] {
  return [
    { clave: 'productos', valor: detalle.productos },
    { clave: 'supervision', valor: detalle.supervisores },
    { clave: 'total', valor: detalle.archivo.filas },
    { clave: 'excluidos', valor: detalle.exclusiones.total },
  ];
}

/**
 * Whether the products left out of every campaign of the lot are shown: only when there are some, and never in a global lot (there every
 * product has a campaign). They belong to the lot, so any campaign of it shows them.
 */
export const fueraDelLoteVisible = (detalle: Pick<DetalleCampana, 'lote' | 'exclusiones_fuera_del_lote'>): boolean =>
  detalle.lote.modo !== 'global' && detalle.exclusiones_fuera_del_lote.total > 0;

/**
 * Logic of the MOWA MES campaign screen (T-MM-F2, part A), kept out of the
 * page so it can be tested without a browser: building the request body from
 * a selection and the platform inputs, and reading a preview's answer. The
 * screen itself and its selection picker are part B.
 *
 * Nothing here re-implements a rule that decides data — the API is the judge
 * of exclusions, warnings and the monthly limit. This module only shapes the
 * request and reads the response.
 */

import type {
  ArchivoPrevisto,
  ConsumoLimite,
  CreacionCampanaEntrada,
  HerramientasEntrada,
  PeticionCampanaEntrada,
  PrevisualizacionCampana,
  ProgramacionCampana,
  SupervisorCampanaEntrada,
} from './api-mowa-mes';
import { formatNumber } from './format';
import { t } from './i18n';
import { traducirCodigo } from './mowa-mes';

/** RF-MM-03, RF-MM-05: the only options the platform has enabled today. */
export const TIPO_CARGA_FIJO = 'masiva' as const;
export const SALIDA_FIJA = 'numero_largo' as const;

/** Same cap as `/cartera` and the load-generation screens (`CANTIDAD_MAXIMA`). */
export const CANTIDAD_MAXIMA_CAMPANA = 120_000;

// ---- Draft shapes ----------------------------------------------------------------

/**
 * What the campaign is built from. Deliberately not the selector's own draft
 * types (`src/lib/seleccion.ts`): this is the reduced shape the API needs,
 * read from whatever the selector emits once part B wires it in.
 */
export interface SeleccionCampana {
  fechaCorte: string;
  filtros: readonly string[];
  orden: string | null;
  cantidad: number;
  seleccionId?: number | null;
}

/** RF-MM-06: `respuesta_automatica` and `speech_optimizado` are not user inputs. */
export interface HerramientasCampana {
  keyword: boolean;
  blacklistIndecopi: boolean;
}

export interface SupervisorBorrador {
  numero: string;
  procedencia: string;
}

export interface ProgramacionBorrador {
  modo: ProgramacionCampana;
  /**
   * Wall-clock `YYYY-MM-DDTHH:mm` entries, as a `datetime-local` input reads
   * them. `hora_determinada` takes exactly one, `diferentes_horas` one or
   * more, `enviar_ahora` none.
   */
  fechas: readonly string[];
}

export interface CampanaBorrador {
  seleccion: SeleccionCampana;
  /** Starts at the API's `descripcion_sugerida`; the analyst can edit it. */
  descripcion: string;
  herramientas: HerramientasCampana;
  programacion: ProgramacionBorrador;
  /** `null` uses the Speech original, same as leaving the field blank. */
  speechId: number | null;
  /** `''` falls back to the configured contact WhatsApp. */
  whatsapp: string;
  /** `null` uses the configured default supervisors. */
  supervisores: SupervisorBorrador[] | null;
}

// ---- Lima's wall clock -------------------------------------------------------------

const PATRON_FECHA_HORA_LOCAL = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/;

export function fechaHoraValida(fechaHora: string): boolean {
  return PATRON_FECHA_HORA_LOCAL.test(fechaHora);
}

/**
 * A `datetime-local` value read as Lima's wall clock, not the browser's.
 * Peru has no daylight-saving time, so its offset is always `-05:00`: no
 * timezone lookup is needed to make the reading unambiguous.
 */
export function horaLimaISO(fechaHora: string): string {
  if (!fechaHoraValida(fechaHora)) {
    throw new Error(`Fecha y hora invalidas: ${fechaHora}`);
  }
  return `${fechaHora}:00-05:00`;
}

// ---- Validation --------------------------------------------------------------------

export type ProblemaCampana =
  | { tipo: 'cantidad_invalida' }
  | { tipo: 'whatsapp_invalido' }
  | { tipo: 'envios_enviar_ahora' }
  | { tipo: 'envios_hora_determinada' }
  | { tipo: 'envios_diferentes_horas' }
  | { tipo: 'fecha_envio_invalida'; indice: number };

/**
 * Shape problems the form can point at before asking the API — the same
 * checks `_validar_opciones` and `_fecha_envio` make in the backend
 * (docs/mowa-mes.md §9). `tipo_carga` and `salida` are not user inputs, so
 * they are never wrong here; a WhatsApp or supervisor rejected by RF-02 is
 * still the API's call, reported from its 400.
 */
export function problemasCampana(borrador: CampanaBorrador): ProblemaCampana[] {
  const problemas: ProblemaCampana[] = [];

  if (!Number.isInteger(borrador.seleccion.cantidad) || borrador.seleccion.cantidad < 1 || borrador.seleccion.cantidad > CANTIDAD_MAXIMA_CAMPANA) {
    problemas.push({ tipo: 'cantidad_invalida' });
  }

  const whatsapp = borrador.whatsapp.trim();
  if (whatsapp !== '' && !/^9\d{8}$/.test(whatsapp)) {
    problemas.push({ tipo: 'whatsapp_invalido' });
  }

  const { modo, fechas } = borrador.programacion;
  if (modo === 'enviar_ahora' && fechas.length > 0) {
    problemas.push({ tipo: 'envios_enviar_ahora' });
  } else if (modo === 'hora_determinada' && fechas.length !== 1) {
    problemas.push({ tipo: 'envios_hora_determinada' });
  } else if (modo === 'diferentes_horas' && fechas.length < 1) {
    problemas.push({ tipo: 'envios_diferentes_horas' });
  }
  if (modo !== 'enviar_ahora') {
    fechas.forEach((fecha, indice) => {
      if (!fechaHoraValida(fecha)) problemas.push({ tipo: 'fecha_envio_invalida', indice });
    });
  }

  return problemas;
}

// ---- Building the request -----------------------------------------------------------

/** Only for a draft with no `problemasCampana`: the shape checks are not repeated here. */
export function entradaCampana(borrador: CampanaBorrador): PeticionCampanaEntrada {
  const herramientas: HerramientasEntrada = {
    keyword: borrador.herramientas.keyword,
    respuesta_automatica: false,
    blacklist_indecopi: borrador.herramientas.blacklistIndecopi,
    speech_optimizado: false,
  };
  const supervisores: SupervisorCampanaEntrada[] | null =
    borrador.supervisores === null
      ? null
      : borrador.supervisores.map((s) => ({ numero: s.numero.trim(), procedencia: s.procedencia.trim() }));

  return {
    fecha_corte: borrador.seleccion.fechaCorte,
    filtros: [...borrador.seleccion.filtros],
    orden: borrador.seleccion.orden,
    cantidad: borrador.seleccion.cantidad,
    seleccion_id: borrador.seleccion.seleccionId ?? null,
    tipo_carga: TIPO_CARGA_FIJO,
    descripcion: borrador.descripcion.trim() || null,
    salida: SALIDA_FIJA,
    herramientas,
    programacion: borrador.programacion.modo,
    envios: borrador.programacion.modo === 'enviar_ahora' ? [] : borrador.programacion.fechas.map(horaLimaISO),
    speech_id: borrador.speechId,
    whatsapp: borrador.whatsapp.trim() || null,
    supervisores,
  };
}

/** The preview's request plus what creation adds: the speech huella it must match. */
export function entradaCreacion(
  borrador: CampanaBorrador,
  speechHuella: string,
  confirmarLimite = false,
): CreacionCampanaEntrada {
  return { ...entradaCampana(borrador), speech_huella: speechHuella, confirmar_limite: confirmarLimite };
}

// ---- Reading the preview -------------------------------------------------------------

/** Whether the description is still the API's suggestion, or the analyst edited it. */
export function descripcionSigueSugerida(actual: string, sugerida: string): boolean {
  return actual.trim() === sugerida.trim();
}

/**
 * One sentence per problem, errors before warnings, in the order the API
 * evaluated them. For a screen-reader status line, updated once per preview.
 */
export function resumenProblemasCampana(
  previsualizacion: Pick<PrevisualizacionCampana, 'errores' | 'advertencias'>,
): string {
  const frases = [...previsualizacion.errores, ...previsualizacion.advertencias].map((aviso) =>
    traducirCodigo(aviso.codigo, aviso.detalle),
  );
  return frases.length > 0 ? frases.join(' ') : t('mowaMes.campana.resumen.sinProblemas');
}

/**
 * `archivos_previstos_por_filas` only counts rows (docs/mowa-mes.md §9): the
 * real division can still split a file further once its bytes are measured.
 */
export function etiquetaArchivoPrevisto(archivo: ArchivoPrevisto, indice: number, total: number): string {
  return t('mowaMes.campana.archivoPrevisto', {
    n: indice + 1,
    total,
    filas: formatNumber(archivo.filas),
    supervision: formatNumber(archivo.supervision),
  });
}

export function mensajeLimiteExcedido(consumo: ConsumoLimite): string {
  return t('mowaMes.campana.limite.excedido', {
    cargados: formatNumber(consumo.total),
    limite: formatNumber(consumo.limite),
  });
}

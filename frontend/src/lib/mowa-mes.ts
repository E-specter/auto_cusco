/**
 * Screen logic of the MOWA MES configuration, kept out of the page so it can
 * be tested without a browser. Nothing here re-implements a backend rule that
 * decides data (RF-02, document numbering, message length): the API answers
 * those, and this module only shapes drafts and reads the answers.
 */

import type {
  ConfiguracionSupervision,
  ConfiguracionSupervisionEntrada,
  DiaNoLaborable,
  LargoSegmento,
  PartesEntrada,
  PartesSpeech,
  Segmento,
  VersionSpeech,
} from './api-mowa-mes';
import { t } from './i18n';

/** Segment order of RF-MM-15, the order every speech table reads in. */
export const ORDEN_SEGMENTOS: readonly Segmento[] = [
  'preventiva',
  '1_a_8',
  '9_a_30',
  '31_a_60',
  '61_a_90',
  '91_a_120',
];

/** Same limit the API enforces on a procedencia name. */
export const LARGO_MAXIMO_PROCEDENCIA = 60;

const posicion = (segmento: Segmento) => ORDEN_SEGMENTOS.indexOf(segmento);

// ---- Speech ------------------------------------------------------------------

/** The editable parts of a version, in segment order. */
export function borradorDesdeVersion(version: VersionSpeech): PartesEntrada[] {
  return [...version.partes]
    .sort((a, b) => posicion(a.segmento) - posicion(b.segmento))
    .map(({ segmento, parte_1, parte_2 }) => ({ segmento, parte_1, parte_2 }));
}

/**
 * Whether the draft differs from the saved version. Parts are compared exactly:
 * the leading and trailing spaces of a part are text the message carries.
 */
export function hayCambiosSpeech(version: VersionSpeech, borrador: PartesEntrada[]): boolean {
  const guardado = borradorDesdeVersion(version);
  if (guardado.length !== borrador.length) return true;
  return guardado.some((parte) => {
    const otra = borrador.find((b) => b.segmento === parte.segmento);
    return !otra || otra.parte_1 !== parte.parte_1 || otra.parte_2 !== parte.parte_2;
  });
}

/**
 * RF-MM-17: a version that a campaign used, and the original, never change.
 * Saving one of them creates a new version based on it.
 */
export function modoGuardado(version: VersionSpeech): 'editar' | 'nueva' {
  return version.editable && !version.original && !version.usada ? 'editar' : 'nueva';
}

export type NivelLargo = 'falta_whatsapp' | 'excede' | 'advertencia' | 'ok';

/** How a segment's preview reads, worst first (RF-MM-16, RF-MM-19). */
export function nivelLargo(segmento: LargoSegmento): NivelLargo {
  if (segmento.falta_whatsapp) return 'falta_whatsapp';
  if (segmento.codigo === 'mensaje_excede_160') return 'excede';
  if (segmento.codigo === 'mensaje_excede_150') return 'advertencia';
  return 'ok';
}

/**
 * One sentence for assistive tech about the whole preview: how many segments
 * cannot be generated, are excluded or are warned. It is written once per
 * preview (after the same debounce), never per keystroke. No preview, no text.
 */
export function resumenNiveles(segmentos: readonly LargoSegmento[]): string {
  if (segmentos.length === 0) return '';
  const cuenta = { falta_whatsapp: 0, excede: 0, advertencia: 0 };
  segmentos.forEach((segmento) => {
    const nivel = nivelLargo(segmento);
    if (nivel !== 'ok') cuenta[nivel] += 1;
  });
  const frases = (['falta_whatsapp', 'excede', 'advertencia'] as const)
    .filter((nivel) => cuenta[nivel] > 0)
    .map((nivel) =>
      t(`mowaMes.speech.resumen.${nivel}${cuenta[nivel] === 1 ? '.uno' : ''}`, { n: cuenta[nivel] }),
    );
  return frases.length > 0 ? frases.join(' ') : t('mowaMes.speech.resumen.ok');
}

/** The adjusted-days range of a segment, shown after its name as "(9–30 días)". */
export function rangoSegmento(
  parte: Pick<PartesSpeech, 'dias_desde' | 'dias_hasta'>,
): { clave: string; params: Record<string, number> } {
  if (parte.dias_desde === null) {
    return { clave: 'mowaMes.speech.rango.hasta', params: { hasta: parte.dias_hasta } };
  }
  return {
    clave: 'mowaMes.speech.rango.entre',
    params: { desde: parte.dias_desde, hasta: parte.dias_hasta },
  };
}

/**
 * Codes are translated by key with the server's sentence as the fallback, the
 * same way ingestion issues are: a code the dictionaries do not know yet
 * degrades to Spanish prose instead of to a raw key.
 */
export function traducirCodigo(codigo: string, respaldo: string): string {
  const clave = `mowaMes.codigo.${codigo}`;
  const traducido = t(clave);
  return traducido === clave ? respaldo : traducido;
}

// ---- Connector configuration ---------------------------------------------------

/**
 * Accepted ranges, the same the API declares. The per-file limits (RF-MM-11)
 * can only go down from the platform's own 50 000 rows and 2 MB.
 */
export const RANGOS_CONFIGURACION = {
  limite_mensual: { minimo: 1, maximo: 1_000_000_000 },
  registros_por_archivo: { minimo: 1, maximo: 50_000 },
  bytes_por_archivo: { minimo: 100_000, maximo: 2_000_000 },
} as const;

export type CampoConfiguracion = keyof typeof RANGOS_CONFIGURACION;

/** The fields whose typed value is not a whole number inside its range, in form order. */
export function problemasConfiguracion(valores: Record<CampoConfiguracion, string>): CampoConfiguracion[] {
  return (Object.keys(RANGOS_CONFIGURACION) as CampoConfiguracion[]).filter((campo) => {
    const texto = valores[campo].trim();
    if (!/^\d+$/.test(texto)) return true;
    const valor = Number(texto);
    const { minimo, maximo } = RANGOS_CONFIGURACION[campo];
    return valor < minimo || valor > maximo;
  });
}

// ---- Calendar ----------------------------------------------------------------

export type AccionDia = 'retirar' | 'restaurar' | 'quitar';

/**
 * What a non-working day offers. Law holidays are computed by rule, so they
 * are never deleted: a year that does not observe one records a `retirado`
 * exception, and undoing that deletes the exception. An added day is itself an
 * exception, so removing it deletes it.
 */
export function accionDia(dia: DiaNoLaborable): AccionDia {
  if (dia.origen === 'agregado') return 'quitar';
  return dia.retirado ? 'restaurar' : 'retirar';
}

// ---- Supervisors -------------------------------------------------------------

export interface BorradorSupervision {
  procedencias: string[];
  supervisores: Array<{ numero: string; procedencia: string }>;
}

export function borradorDeSupervision(guardada: ConfiguracionSupervision): BorradorSupervision {
  return {
    procedencias: [...guardada.procedencias],
    supervisores: guardada.supervisores.map(({ numero, procedencia }) => ({ numero, procedencia })),
  };
}

/** What the API receives: surrounding spaces are typing, not data. */
export function entradaSupervision(borrador: BorradorSupervision): ConfiguracionSupervisionEntrada {
  return {
    procedencias: borrador.procedencias.map((p) => p.trim()),
    supervisores: borrador.supervisores.map((s) => ({
      numero: s.numero.trim(),
      procedencia: s.procedencia.trim(),
    })),
  };
}

export function supervisionCambio(
  guardada: ConfiguracionSupervision,
  borrador: BorradorSupervision,
): boolean {
  const antes = entradaSupervision(borradorDeSupervision(guardada));
  return JSON.stringify(antes) !== JSON.stringify(entradaSupervision(borrador));
}

/**
 * Rename a procedencia and carry its supervisors along, so editing a name does
 * not silently orphan the people assigned to it.
 */
export function renombrarProcedencia(
  borrador: BorradorSupervision,
  indice: number,
  nombre: string,
): BorradorSupervision {
  const anterior = borrador.procedencias[indice];
  if (anterior === undefined) return borrador;
  return {
    procedencias: borrador.procedencias.map((p, i) => (i === indice ? nombre : p)),
    supervisores: borrador.supervisores.map((s) =>
      s.procedencia === anterior ? { ...s, procedencia: nombre } : s,
    ),
  };
}

/** Move one element up (-1) or down (+1); out of range leaves the list as is. */
export function moverElemento<T>(lista: readonly T[], indice: number, delta: -1 | 1): T[] {
  const destino = indice + delta;
  const copia = [...lista];
  if (indice < 0 || indice >= lista.length || destino < 0 || destino >= lista.length) return copia;
  [copia[indice], copia[destino]] = [copia[destino], copia[indice]];
  return copia;
}

export type ProblemaSupervision =
  | { tipo: 'sin_procedencias' }
  | { tipo: 'procedencia_vacia' | 'procedencia_larga' | 'procedencia_repetida'; indice: number }
  | { tipo: 'numero_vacio' | 'procedencia_desconocida'; indice: number };

/**
 * The shape problems the form can point at before asking the API. Whether a
 * number is a valid phone (RF-02) is the API's call, reported from its 400.
 */
export function problemasSupervision(borrador: BorradorSupervision): ProblemaSupervision[] {
  const problemas: ProblemaSupervision[] = [];
  const nombres = borrador.procedencias.map((p) => p.trim());

  if (nombres.length === 0) problemas.push({ tipo: 'sin_procedencias' });

  const vistos = new Set<string>();
  nombres.forEach((nombre, indice) => {
    if (nombre === '') {
      problemas.push({ tipo: 'procedencia_vacia', indice });
      return;
    }
    if (nombre.length > LARGO_MAXIMO_PROCEDENCIA) {
      problemas.push({ tipo: 'procedencia_larga', indice });
    }
    const clave = nombre.toLocaleLowerCase('es');
    if (vistos.has(clave)) problemas.push({ tipo: 'procedencia_repetida', indice });
    vistos.add(clave);
  });

  borrador.supervisores.forEach((supervisor, indice) => {
    if (supervisor.numero.trim() === '') problemas.push({ tipo: 'numero_vacio', indice });
    if (!nombres.includes(supervisor.procedencia.trim())) {
      problemas.push({ tipo: 'procedencia_desconocida', indice });
    }
  });

  return problemas;
}

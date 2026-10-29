/**
 * Screen logic of the default supervisors, shared by every connector. Nothing here re-implements a
 * rule that decides data (RF-02, document numbering): the API answers those, and this module only
 * shapes drafts and reads the answers.
 */

import type { ConfiguracionSupervision, ConfiguracionSupervisionEntrada } from './api-supervision';
import { formatNumber } from './format';
import { t } from './i18n';

/** Same limit the API enforces on a procedencia name. */
export const LARGO_MAXIMO_PROCEDENCIA = 60;

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

/** The sentence for one problem; the origin's length bound is the constant the validation uses. */
export function textoDeProblemaSupervision(problema: ProblemaSupervision): string {
  const n = 'indice' in problema ? problema.indice + 1 : 0;
  return t(`supervisores.problema.${problema.tipo}`, { n, max: formatNumber(LARGO_MAXIMO_PROCEDENCIA) });
}

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

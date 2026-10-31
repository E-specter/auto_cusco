/**
 * The campaign form's draft while the analyst is away editing its selection in Cartera (T-MM-C11, M-F6,
 * RF-MM-09; docs/mowa-mes-interfaz.md §4.7). «Editar en Cartera» leaves the page, so what was typed is kept in
 * `sessionStorage` (it dies with the tab) and taken back when the campaign opens again.
 *
 * Pure on purpose (the storage is handed in) and defensive: the draft comes from a place the page does not
 * control (another version of the app wrote it, the browser may refuse storage, the JSON may be broken), so
 * reading it can only give a draft that is whole and of this version, or nothing: the campaign then starts
 * empty, as on any other visit. The key carries the version; a new shape gets a new key.
 */

import type { SupervisorBorrador } from './mowa-mes-campana';

/** Versioned: a draft written under another key is not read (and not deleted, it is not ours). */
export const CLAVE_BORRADOR_CAMPANA = 'mowaMes.campana.borrador.v1';

const VERSION = 1;

export type ModoDeProgramacion = 'enviar_ahora' | 'hora_determinada' | 'diferentes_horas';
export type ModoDeSupervisores = 'defecto' | 'propios';

/** Everything the form holds, as the page reads it from its fields. */
export interface BorradorEnPantalla {
  seleccionId: number | null;
  fechaCorte: string | null;
  descripcion: string;
  /** False while the field still holds the API's suggestion, which then fills it again. */
  descripcionEditada: boolean;
  plantilla: string;
  plantillaEditada: boolean;
  keyword: boolean;
  blacklist: boolean;
  programacion: ModoDeProgramacion;
  fechaUnica: string;
  fechasMultiples: string[];
  speech: string;
  whatsapp: string;
  supervisoresModo: ModoDeSupervisores;
  supervisoresPropios: SupervisorBorrador[];
}

/** The part of `Storage` this needs: what a test stands in for, and what a refusing browser breaks. */
export type Almacen = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

/** `sessionStorage`, or `null` if the browser has none or refuses to hand it over (private modes, blocked data). */
export function almacenDeSesion(): Almacen | null {
  try {
    return globalThis.sessionStorage ?? null;
  } catch {
    return null;
  }
}

const esTexto = (valor: unknown): valor is string => typeof valor === 'string';
const esLogico = (valor: unknown): valor is boolean => typeof valor === 'boolean';
const esListaDeTextos = (valor: unknown): valor is string[] => Array.isArray(valor) && valor.every(esTexto);

function esSupervisor(valor: unknown): valor is SupervisorBorrador {
  if (typeof valor !== 'object' || valor === null) return false;
  const candidato = valor as Record<string, unknown>;
  return esTexto(candidato.numero) && esTexto(candidato.procedencia);
}

/** The draft in `valor` if it is whole and of this version; `null` for anything else. */
export function borradorValido(valor: unknown): BorradorEnPantalla | null {
  if (typeof valor !== 'object' || valor === null) return null;
  const c = valor as Record<string, unknown>;
  const programacion = c.programacion;
  const supervisoresModo = c.supervisoresModo;
  const seleccionOk = c.seleccionId === null || (typeof c.seleccionId === 'number' && Number.isSafeInteger(c.seleccionId));
  const fechaOk = c.fechaCorte === null || esTexto(c.fechaCorte);
  if (
    c.version !== VERSION ||
    !seleccionOk ||
    !fechaOk ||
    !esTexto(c.descripcion) ||
    !esLogico(c.descripcionEditada) ||
    !esTexto(c.plantilla) ||
    !esLogico(c.plantillaEditada) ||
    !esLogico(c.keyword) ||
    !esLogico(c.blacklist) ||
    (programacion !== 'enviar_ahora' && programacion !== 'hora_determinada' && programacion !== 'diferentes_horas') ||
    !esTexto(c.fechaUnica) ||
    !esListaDeTextos(c.fechasMultiples) ||
    !esTexto(c.speech) ||
    !esTexto(c.whatsapp) ||
    (supervisoresModo !== 'defecto' && supervisoresModo !== 'propios') ||
    !Array.isArray(c.supervisoresPropios) ||
    !c.supervisoresPropios.every(esSupervisor)
  ) {
    return null;
  }
  return {
    seleccionId: c.seleccionId as number | null,
    fechaCorte: c.fechaCorte as string | null,
    descripcion: c.descripcion as string,
    descripcionEditada: c.descripcionEditada as boolean,
    plantilla: c.plantilla as string,
    plantillaEditada: c.plantillaEditada as boolean,
    keyword: c.keyword as boolean,
    blacklist: c.blacklist as boolean,
    programacion,
    fechaUnica: c.fechaUnica as string,
    fechasMultiples: [...(c.fechasMultiples as string[])],
    speech: c.speech as string,
    whatsapp: c.whatsapp as string,
    supervisoresModo,
    supervisoresPropios: (c.supervisoresPropios as SupervisorBorrador[]).map((s) => ({
      numero: s.numero,
      procedencia: s.procedencia,
    })),
  };
}

/**
 * Keeps the draft. `false` if it could not be (no storage, a refusal, no room): the analyst still goes to
 * Cartera, and comes back to an empty form rather than to an error.
 */
export function guardarBorrador(almacen: Almacen | null, borrador: BorradorEnPantalla): boolean {
  if (!almacen) return false;
  try {
    almacen.setItem(CLAVE_BORRADOR_CAMPANA, JSON.stringify({ version: VERSION, ...borrador }));
    return true;
  } catch {
    return false;
  }
}

/**
 * Takes the draft back: reads it AND deletes it, always, so it is used once (a reload does not bring it
 * again, and a broken one does not stay in the way). `null` if there is none or it cannot be read.
 */
export function tomarBorrador(almacen: Almacen | null): BorradorEnPantalla | null {
  if (!almacen) return null;
  let texto: string | null = null;
  try {
    texto = almacen.getItem(CLAVE_BORRADOR_CAMPANA);
  } catch {
    return null;
  } finally {
    try {
      almacen.removeItem(CLAVE_BORRADOR_CAMPANA);
    } catch {
      /* A storage that refuses to delete has nothing more to say. */
    }
  }
  if (texto === null) return null;
  try {
    return borradorValido(JSON.parse(texto));
  } catch {
    return null;
  }
}

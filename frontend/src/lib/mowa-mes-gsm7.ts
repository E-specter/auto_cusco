/**
 * What the speech screen says about the characters GSM-7 deletes (RF-MM-27; docs/motor-texto-
 * enriquecido-interfaz.md §10.2): the line «Al enviar se borran: …» under a segment.
 *
 * The backend returns, per segment, the graphemes the normalisation DELETES (`caracteres_quitados`):
 * without repeats, in order of appearance, and without counting what is only replaced (accents,
 * «…», «“”»). This decides how each one reads, and nothing else: it neither dedupes nor sorts, and
 * it never looks at the text of the message.
 *
 * Each element reads in one of three ways:
 *  - visible: the grapheme itself, in mono (an emoji, a «✓»);
 *  - named: a known invisible, by its name, with its code point in mono;
 *  - invisible: any other one with no visible part, as «carácter invisible U+XXXX».
 */

import type { components } from './contrato-api';
import { t } from './i18n';

export type CaracterQuitado = components['schemas']['CaracterQuitadoRespuesta'];

/** Separates the elements of the line; a plain space no longer does once some of them have names. */
export const SEPARADOR_BORRADOS = ' · ';

/** The invisibles that have a name (§10.2), by their code point: the key of their text in the dictionary. */
const CLAVE_DEL_NOMBRE: Readonly<Record<string, string>> = {
  'U+200B': 'mowaMes.speech.borrados.nombre.u200b',
  'U+200C': 'mowaMes.speech.borrados.nombre.u200c',
  'U+200D': 'mowaMes.speech.borrados.nombre.u200d',
  'U+2060': 'mowaMes.speech.borrados.nombre.u2060',
  'U+00AD': 'mowaMes.speech.borrados.nombre.u00ad',
  'U+FEFF': 'mowaMes.speech.borrados.nombre.ufeff',
  'U+200E': 'mowaMes.speech.borrados.nombre.u200e',
  'U+200F': 'mowaMes.speech.borrados.nombre.u200f',
  'U+2028': 'mowaMes.speech.borrados.nombre.u2028',
  'U+2029': 'mowaMes.speech.borrados.nombre.u2029',
  'U+000B': 'mowaMes.speech.borrados.nombre.u000b',
};

const CLAVE_GENERICA = 'mowaMes.speech.borrados.invisible';

/**
 * A code point with no form of its own: a mark (Mn, Me), a format character (Cf), a control (Cc) or
 * a space separator (Zs). A grapheme is invisible only if ALL of its points are (§10.2): «U+FE0F U+20E3»,
 * the rest of a keycap whose digit stays, is.
 */
const SIN_FORMA = /^[\p{Mn}\p{Me}\p{Cf}\p{Cc}\p{Zs}]$/u;

/** One element of the line, ready to be drawn: `nombre` is `null` for a visible one. */
export interface ElementoBorrado {
  tipo: 'visible' | 'con_nombre' | 'invisible';
  /** What is shown in mono when the element is visible. */
  caracter: string;
  /** Its code points as the backend sent them, to draw in mono next to the name. */
  codigo: string;
  /** The translated name of a named invisible, or «carácter invisible»; `null` if it is visible. */
  nombre: string | null;
}

/** «U+1F44D U+1F3FD» → [0x1F44D, 0x1F3FD]; `null` if any part is not a code point. */
export function puntosDeCodigo(punto: string): number[] | null {
  const partes = punto.trim().split(/\s+/);
  const puntos: number[] = [];
  for (const parte of partes) {
    const coincide = /^U\+([0-9A-F]{4,6})$/.exec(parte);
    if (!coincide) return null;
    const valor = Number.parseInt(coincide[1], 16);
    if (valor > 0x10ffff) return null;
    puntos.push(valor);
  }
  return puntos;
}

/** Whether the grapheme has no visible part: every one of its code points is without a form of its own. */
export function esInvisible(punto: string): boolean {
  const puntos = puntosDeCodigo(punto);
  if (puntos === null) return false;
  return puntos.every((valor) => SIN_FORMA.test(String.fromCodePoint(valor)));
}

export function elementoBorrado(quitado: CaracterQuitado): ElementoBorrado {
  const codigo = quitado.punto_de_codigo.trim();
  const base = { caracter: quitado.caracter, codigo };
  const clave = CLAVE_DEL_NOMBRE[codigo];
  if (clave !== undefined) return { ...base, tipo: 'con_nombre', nombre: t(clave) };
  if (esInvisible(codigo)) return { ...base, tipo: 'invisible', nombre: t(CLAVE_GENERICA) };
  return { ...base, tipo: 'visible', nombre: null };
}

/**
 * The elements of the line of a segment, in the order the backend sent. An empty list is no line at
 * all: the screen draws nothing then. A repeat would be drawn twice; it is the backend that does not
 * send it, and here it only has to not break.
 */
export function elementosBorrados(quitados: readonly CaracterQuitado[]): ElementoBorrado[] {
  return quitados.map(elementoBorrado);
}

/** The line as plain text, for the tests and for an accessible name: «👍🏽 · ✓ · espacio de ancho cero U+200B». */
export function textoDeBorrados(elementos: readonly ElementoBorrado[]): string {
  return elementos.map((e) => (e.nombre === null ? e.caracter : `${e.nombre} ${e.codigo}`)).join(SEPARADOR_BORRADOS);
}

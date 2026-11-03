/**
 * The message of a WhatsMKT campaign, as the editor of the settings sees it (T-WM-F1b2, docs/whatsmkt-interfaz.md §5.1): a
 * plain text with `[$MACROn$]` markers that WhatsMKT replaces per row and a `[whatsapp]` that this system replaces with the
 * contact link. The backend decides (`mensaje.py`): it rejects emojis and a text over the limit when it is saved, and the macros
 * against the definition when the campaign is previewed or created. This mirrors its rules so the editor can say them at once;
 * the saved text is always the backend's judgement, never this one's.
 */

import { t } from './i18n';

export const MARCADOR_WHATSAPP = '[whatsapp]';
export const ENLACE_WHATSAPP = 'https://wa.me/+51';
/** `[whatsapp]` counts as the link it becomes, of fixed length: the prefix and the 9 digits of the number. */
export const LARGO_ENLACE_WHATSAPP = ENLACE_WHATSAPP.length + 9;

// The same explicit ranges as the backend (`_RANGOS_EMOJI`): what is drawn as an emoji, the pictogram plane, the flags and the
// pieces of a composed emoji. Symbols that are text unless asked otherwise (© ® ™ ✓ ← → ♥ ☎ ✈) pass; their variation selector does not.
const RANGOS_EMOJI: ReadonlyArray<readonly [number, number]> = [
  [0x200d, 0x200d],
  [0xfe0e, 0xfe0f],
  [0x20e3, 0x20e3],
  [0xe0020, 0xe007f],
  [0x1f000, 0x1f2ff],
  [0x1f300, 0x1f64f],
  [0x1f680, 0x1f6ff],
  [0x1f7e0, 0x1f7eb],
  [0x1f90c, 0x1f9ff],
  [0x1fa70, 0x1faff],
  [0x231a, 0x231b],
  [0x23e9, 0x23ec],
  [0x23f0, 0x23f0],
  [0x23f3, 0x23f3],
  [0x25fd, 0x25fe],
  [0x2614, 0x2615],
  [0x2648, 0x2653],
  [0x267f, 0x267f],
  [0x2693, 0x2693],
  [0x26a1, 0x26a1],
  [0x26aa, 0x26ab],
  [0x26bd, 0x26be],
  [0x26c4, 0x26c5],
  [0x26ce, 0x26ce],
  [0x26d4, 0x26d4],
  [0x26ea, 0x26ea],
  [0x26f2, 0x26f3],
  [0x26f5, 0x26f5],
  [0x26fa, 0x26fa],
  [0x26fd, 0x26fd],
  [0x2705, 0x2705],
  [0x270a, 0x270b],
  [0x2728, 0x2728],
  [0x274c, 0x274c],
  [0x274e, 0x274e],
  [0x2753, 0x2755],
  [0x2757, 0x2757],
  [0x2795, 0x2797],
  [0x27b0, 0x27b0],
  [0x27bf, 0x27bf],
  [0x2b1b, 0x2b1c],
  [0x2b50, 0x2b50],
  [0x2b55, 0x2b55],
  [0x3297, 0x3297],
  [0x3299, 0x3299],
];

const esEmoji = (punto: number): boolean => RANGOS_EMOJI.some(([desde, hasta]) => desde <= punto && punto <= hasta);

export interface EmojiEncontrado {
  caracter: string;
  /** Counted in Unicode characters from 1, as the backend says it (an emoji of two UTF-16 units counts one). */
  posicion: number;
  /** Where it starts in the text as the browser indexes it (UTF-16 units): what `setSelectionRange` takes. */
  indice: number;
}

/** The first rejected character of the text, or `null` (RF-WM-24). */
export function primerEmoji(texto: string): EmojiEncontrado | null {
  let posicion = 0;
  let indice = 0;
  for (const caracter of texto) {
    posicion += 1;
    if (esEmoji(caracter.codePointAt(0)!)) return { caracter, posicion, indice };
    indice += caracter.length;
  }
  return null;
}

/** The UTF-16 index of the character at `posicion` (from 1, in Unicode characters), or `null` past the end: the backend's position, in the browser's terms. */
export function indiceDePosicion(texto: string, posicion: number): number | null {
  let actual = 0;
  let indice = 0;
  for (const caracter of texto) {
    actual += 1;
    if (actual === posicion) return indice;
    indice += caracter.length;
  }
  return null;
}

/** What the limit counts (RF-WM-26): the text with its macros as written (DU-WM-3) and each `[whatsapp]` as the link it will be. */
export function largoDelMensaje(texto: string): number {
  const usos = texto.split(MARCADOR_WHATSAPP).length - 1;
  return Array.from(texto).length + usos * (LARGO_ENLACE_WHATSAPP - MARCADOR_WHATSAPP.length);
}

/** The first `[$MACROn$]` of the text, in order, whose macro the definition does not have (RF-WM-25), or `null`. */
export function primeraMacroInexistente(texto: string, cantidadDeMacros: number): string | null {
  for (const encontrada of texto.matchAll(/\[\$MACRO(\d+)\$\]/g)) {
    const n = Number(encontrada[1]);
    if (n < 1 || n > cantidadDeMacros) return encontrada[0];
  }
  return null;
}

export interface MacroDeDefinicion {
  n: number;
  /** The label of its column, or `null` when it has none. */
  etiqueta: string | null;
}

/** The macros of a definition: its columns but the first (the number, which is fixed), numbered from 1 by position (RF-WM-11). */
export function macrosDeLaDefinicion(columnas: ReadonlyArray<{ etiqueta: string | null }>): MacroDeDefinicion[] {
  return columnas.slice(1).map((columna, indice) => ({ n: indice + 1, etiqueta: columna.etiqueta?.trim() ? columna.etiqueta.trim() : null }));
}

/** The text of an «Insertar macro» button: «MACRO1 · Nombres del titular», or only «MACRO1» without a label. */
export function textoDeMacro(macro: MacroDeDefinicion): string {
  return macro.etiqueta === null ? `MACRO${macro.n}` : t('whatsmkt.mensaje.macro', { n: macro.n, etiqueta: macro.etiqueta });
}

export interface ParteDeLaVista {
  texto: string;
  /** The placeholder said when there is no contact WhatsApp: it reads in muted text. */
  apagado: boolean;
}

/**
 * The message as the customer will see it (RF-WM-27), in parts so the placeholder can be muted. `[$MACROn$]` becomes the value
 * of macro n of the row (nothing if it is empty; left as written if the row has no such macro, so the mistake shows) and
 * `[whatsapp]` the contact link, or `sinWhatsapp` when no number is set. Same order as the backend: the link first, then the macros,
 * so a value that looks like a marker is never read as one.
 */
export function partesDeLaVista(
  texto: string,
  valoresDeLaFila: ReadonlyArray<string | null>,
  whatsapp: string | null,
  sinWhatsapp: string,
): ParteDeLaVista[] {
  const macros = (fragmento: string): string =>
    fragmento.replace(/\[\$MACRO(\d+)\$\]/g, (encontrada, n: string) => {
      const indice = Number(n);
      return indice >= 1 && indice <= valoresDeLaFila.length ? (valoresDeLaFila[indice - 1] ?? '') : encontrada;
    });
  const trozos = texto.split(MARCADOR_WHATSAPP);
  const partes: ParteDeLaVista[] = [];
  trozos.forEach((trozo, i) => {
    if (i > 0) partes.push({ texto: whatsapp ? `${ENLACE_WHATSAPP}${whatsapp}` : sinWhatsapp, apagado: !whatsapp });
    partes.push({ texto: macros(trozo), apagado: false });
  });
  return partes.filter((parte) => parte.texto !== '' || parte.apagado);
}

/** The sentence of a problem the backend says about a message when it is saved (`codigo_contexto` is the module's own code), or `null` for any other. */
export function textoDeProblemaDelMensaje(problema: {
  codigo_contexto?: string | null;
  parametros?: Readonly<Record<string, string | number>> | null;
}): string | null {
  if (!problema.codigo_contexto) return null;
  const clave = `whatsmkt.codigo.${problema.codigo_contexto}`;
  const texto = t(clave, { ...(problema.parametros ?? {}) });
  return texto === clave ? null : texto;
}

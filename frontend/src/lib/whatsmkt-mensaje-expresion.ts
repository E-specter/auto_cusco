/**
 * The message of a WhatsMKT campaign between what is saved and what the common editor edits (T-WM-F4, docs/motor-texto-enriquecido-interfaz.md
 * §13.7): the saved text is plain, with `[$MACROn$]` markers that WhatsMKT replaces per row and `[whatsapp]` that this system replaces with the
 * contact link (RF-WM-17, RF-WM-51); the editor edits an engine expression whose variables are `macroN` and `whatsapp` (the context
 * `whatsmkt.mensaje`, which the backend builds per request from the default definition).
 *
 * Pure and exact: the same text goes in and comes out, byte for byte, whatever it holds: double spaces, a space before a comma (the seeded
 * speeches carry both, DU-WM-2), line breaks, or a macro the definition does not have. That one is a variable like any other: the engine
 * marks it unknown, and it never turns into mute text or disappears. Only the markers the backend reads are markers (`\[\$MACRO(\d+)\$\]`
 * and `[whatsapp]`, in this case); anything else, `[$macro1$]` or `[whatsapp ]`, is text.
 */

import type { Expresion, Nodo } from './expresion';
import { MARCADOR_WHATSAPP } from './whatsmkt-mensaje';

/** The variable of the context that is the contact link. */
export const VARIABLE_WHATSAPP = 'whatsapp';

// The same pattern as the backend's (`mensaje._MACRO`) and `[whatsapp]` literal. The digits are kept as they are written (`[$MACRO07$]` is
// `macro07`, not `macro7`), so what comes back is what went in.
const MARCADOR = /\[\$MACRO(\d+)\$\]|\[whatsapp\]/g;
const VARIABLE_MACRO = /^macro(\d+)$/;

/** The saved text as an expression: its markers are variables, the rest is text. An empty text is an expression with no nodes. */
export function expresionDeMensaje(texto: string): Expresion {
  const nodos: Nodo[] = [];
  let desde = 0;
  for (const encontrado of texto.matchAll(MARCADOR)) {
    const inicio = encontrado.index;
    if (inicio > desde) nodos.push({ tipo: 'texto', valor: texto.slice(desde, inicio) });
    nodos.push({ tipo: 'variable', nombre: encontrado[1] === undefined ? VARIABLE_WHATSAPP : `macro${encontrado[1]}`, funciones: [] });
    desde = inicio + encontrado[0].length;
  }
  if (desde < texto.length) nodos.push({ tipo: 'texto', valor: texto.slice(desde) });
  return { nodos };
}

/**
 * The expression of the editor as the text that is saved. A variable that is neither a macro nor the link is not a marker of the message (the
 * context offers no other), so it says nothing; functions do not exist here (the context admits none) and are not written.
 */
export function textoDeMensaje(expresion: Expresion | null | undefined): string {
  return (expresion?.nodos ?? [])
    .map((nodo) => {
      if (nodo.tipo === 'texto') return nodo.valor;
      if (nodo.nombre === VARIABLE_WHATSAPP) return MARCADOR_WHATSAPP;
      const macro = VARIABLE_MACRO.exec(nodo.nombre);
      return macro ? `[$MACRO${macro[1]}$]` : '';
    })
    .join('');
}

/** The number of the macro a variable of the context names, or `null` for any other (`macro3` → 3). */
export function numeroDeMacro(nombreDeVariable: string): number | null {
  const macro = VARIABLE_MACRO.exec(nombreDeVariable);
  return macro ? Number(macro[1]) : null;
}

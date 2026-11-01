/**
 * Versions of the MOWA MES speech with something GSM-7 deletes (T-MM-F7), shared by the specs that look
 * at the line «Al enviar se borran: …»: the behaviour one and the accessibility one. Every text is synthetic.
 */
import type { ApiFalsaMowaMes } from './api-falsa-mowa-mes';
import { versionV2Sintetica } from './api-falsa-speech-v2';

export const ZWSP = '\u200b';

/** Accents and typographic signs are replaced, not deleted: none of them may show up in the line. */
export const SOLO_SE_CAMBIA = ' Pagá “ya” — «hoy»… 50° ñandú ';

/**
 * The extended table of GSM-7 is transliterated too (RF-MM-27, 2026-10-26): none of these is deleted, so
 * none may show up in the line. Only `^` has no equivalent and is the one that does.
 */
export const EXTENDIDOS = ' [€5] {a} b\\c|d ~ uno\ftres ^ ';

/** A v2 whose «preventiva» loses an emoji, an invisible character and `^`, and whose «9 a 30» loses another emoji. */
export function v2ConBorrados(api: ApiFalsaMowaMes): void {
  const v2 = versionV2Sintetica(api.versiones[0]);
  const texto = (segmento: string, valor: string) => {
    const e = v2.expresiones.find((x) => x.segmento === segmento)!;
    e.expresion = { nodos: [...e.expresion.nodos, { tipo: 'texto', valor }] };
  };
  texto('preventiva', ` 👍🏽${ZWSP}${SOLO_SE_CAMBIA}${EXTENDIDOS}`);
  texto('9_a_30', ' 🙂');
  api.versiones.push(v2);
}

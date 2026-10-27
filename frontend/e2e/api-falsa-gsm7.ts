/**
 * The GSM-7 normalisation of MOWA MES (RF-MM-27) as the fake API needs it: what the backend deletes
 * from a text, by grapheme. It mirrors the backend's rules, not its code: accents are removed and the
 * typographic signs and the extended characters of GSM-7 are replaced by a simple one (neither is
 * reported), special spaces and the form feed become a plain space, and what has no equivalent
 * (an emoji, `^`, a vertical tab) is DELETED and reported, without repeats and in order of
 * appearance. The message ends up in the basic alphabet only, so its length is just its length.
 * In a grapheme that keeps a part (the «1» of a keycap), only the deleted part is reported.
 * Every text a spec uses is synthetic.
 */
import type { CaracterQuitado } from '../src/lib/mowa-mes-gsm7';

const BASICO =
  '@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !"#¤%&\'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà';

const REEMPLAZOS: Readonly<Record<string, string>> = {
  '“': '"',
  '”': '"',
  '«': '"',
  '»': '"',
  '‘': "'",
  '’': "'",
  '…': '...',
  '–': '-',
  '—': '-',
  '°': 'o',
  'º': 'o',
  'ª': 'a',
  // The extended table of GSM-7 is transliterated too (decision of 2026-10-26); `^` has no equivalent.
  '€': 'EUR',
  '[': '(',
  '{': '(',
  ']': ')',
  '}': ')',
  '\\': '/',
  '|': '/',
  '~': '-',
};

const ESPACIO_ESPECIAL = /^[\p{Zs}\t\f]$/u;
const SEGMENTADOR = new Intl.Segmenter('es', { granularity: 'grapheme' });

const enGsm7 = (c: string) => BASICO.includes(c);
const punto = (c: string) => `U+${c.codePointAt(0)!.toString(16).toUpperCase().padStart(4, '0')}`;

/** What stays of a grapheme once normalised, and the code points that are deleted. */
function normalizarGrafema(grafema: string): { queda: string; quitados: string[] } {
  let queda = '';
  const quitados: string[] = [];
  for (const c of grafema.normalize('NFD')) {
    // Accents and the like (combining marks of the Latin script) go without a trace.
    if (/^[̀-ͯ]$/u.test(c)) continue;
    if (REEMPLAZOS[c] !== undefined) queda += REEMPLAZOS[c];
    else if (ESPACIO_ESPECIAL.test(c) && c !== ' ') queda += ' ';
    else if (enGsm7(c)) queda += c;
    else quitados.push(c);
  }
  return { queda, quitados };
}

export function normalizarGsm7(texto: string): string {
  return [...SEGMENTADOR.segment(texto)].map((s) => normalizarGrafema(s.segment).queda).join('');
}

/** What the normalisation deletes from `texto`, by grapheme, without repeats and in order. */
export function caracteresQuitados(texto: string): CaracterQuitado[] {
  const vistos = new Set<string>();
  const lista: CaracterQuitado[] = [];
  for (const { segment } of SEGMENTADOR.segment(texto)) {
    const { quitados } = normalizarGrafema(segment);
    if (quitados.length === 0) continue;
    const caracter = quitados.join('');
    if (vistos.has(caracter)) continue;
    vistos.add(caracter);
    lista.push({ caracter, punto_de_codigo: quitados.map(punto).join(' ') });
  }
  return lista;
}

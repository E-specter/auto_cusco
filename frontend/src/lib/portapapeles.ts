/**
 * Copying text to the clipboard: the async clipboard first, the classic way as the fallback. Generic: it
 * knows nothing about a screen.
 */

/** How a copy ended: with the async clipboard, with the classic fallback, or not at all. */
export type ResultadoCopia = 'portapapeles' | 'respaldo' | 'fallo';

export interface OperacionesCopia {
  /** `navigator.clipboard.writeText`; absent where the browser has no async clipboard (plain http outside localhost). */
  escribir?: (texto: string) => Promise<void>;
  /** The classic way: select the text and `document.execCommand('copy')`; `false` when the browser refuses. */
  seleccionarYCopiar: () => boolean;
}

/**
 * The order of attempts: the async clipboard first; only if it is missing or rejects, the classic
 * fallback; only if that returns `false` or throws, the failure. The fallback is never tried when the
 * clipboard worked.
 */
export async function copiarConRespaldo(
  texto: string,
  { escribir, seleccionarYCopiar }: OperacionesCopia,
): Promise<ResultadoCopia> {
  if (escribir) {
    try {
      await escribir(texto);
      return 'portapapeles';
    } catch {
      // Falls through to the classic way.
    }
  }
  try {
    return seleccionarYCopiar() ? 'respaldo' : 'fallo';
  } catch {
    return 'fallo';
  }
}

/**
 * The classic way for a text that is not in a field: an off-screen textarea, selected, copied and taken
 * out in `finally`. `false` when the browser refuses.
 */
export function copiarDesdeTextareaTemporal(texto: string): boolean {
  const temporal = document.createElement('textarea');
  temporal.value = texto;
  temporal.setAttribute('readonly', '');
  temporal.setAttribute('aria-hidden', 'true');
  temporal.style.cssText = 'position:fixed;inset-block-start:0;inset-inline-start:-9999px;opacity:0';
  document.body.append(temporal);
  try {
    temporal.select();
    return document.execCommand('copy');
  } finally {
    temporal.remove();
  }
}

/** Copy `texto` from anywhere: the clipboard if the browser has it, the temporary textarea if not. */
export function copiarTexto(texto: string): Promise<ResultadoCopia> {
  return copiarConRespaldo(texto, {
    escribir: navigator.clipboard?.writeText ? (t) => navigator.clipboard.writeText(t) : undefined,
    seleccionarYCopiar: () => copiarDesdeTextareaTemporal(texto),
  });
}

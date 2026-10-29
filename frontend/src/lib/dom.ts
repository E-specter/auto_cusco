/**
 * Small DOM helpers the pages' inline scripts share. Nothing here knows a screen.
 */

// shortcut: `!` assumes the element exists in the page; a missing one fails on first use. Upgrade if a
// caller needs a soft lookup (cargas.astro keeps its own `$` that returns null, which is not this).
export const $ = <T extends Element>(selector: string) => document.querySelector<T>(selector)!;

/** A button that is busy: `data-loading` drives the spinner in `ui.css`, `disabled` stops a double click. */
export function ocupado(boton: HTMLButtonElement, si: boolean): void {
  boton.dataset.loading = String(si);
  boton.disabled = si;
}

/**
 * Write a snake_case identifier with break opportunities at its underscores. Left alone in a narrow
 * cell it splits mid-word; the underscore is the only honest place to wrap one.
 */
export function appendBreakable(nodo: HTMLElement, valor: string): void {
  const partes = valor.split('_');
  partes.forEach((parte, indice) => {
    const ultima = indice === partes.length - 1;
    nodo.append(ultima ? parte : `${parte}_`);
    if (!ultima) nodo.append(document.createElement('wbr'));
  });
}

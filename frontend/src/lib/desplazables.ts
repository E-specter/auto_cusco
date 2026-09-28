/**
 * Keyboard access to scrolling table containers (WCAG 2.1.1).
 *
 * A `.table-scroll` that overflows hides columns a keyboard user cannot reach:
 * nothing inside it is focusable, so the arrow keys have nowhere to act. The
 * fix is to make the container itself a focusable, named region — but only
 * while it actually overflows. A tab stop on a table that fits is a detour
 * that leads nowhere.
 *
 * This runs once from the shell for every screen, including tables that page
 * scripts build later, so no page has to remember it.
 */

import { t } from './i18n';

const SELECTOR = '.table-scroll';
/** Marks the attributes this module added, so it never removes an author's. */
const MARCA = 'desplazable';

function desborda(contenedor: HTMLElement): boolean {
  return (
    contenedor.scrollWidth > contenedor.clientWidth + 1 ||
    contenedor.scrollHeight > contenedor.clientHeight + 1
  );
}

/**
 * The region's name: the table's caption, else the heading of the panel or
 * section it sits in, else a generic label. Reusing a visible heading keeps
 * what a screen reader announces identical to what a sighted user reads.
 */
function nombrar(contenedor: HTMLElement): void {
  if (contenedor.hasAttribute('aria-label') || contenedor.hasAttribute('aria-labelledby')) return;

  const leyenda = contenedor.querySelector('caption');
  if (leyenda?.id) {
    contenedor.setAttribute('aria-labelledby', leyenda.id);
    return;
  }

  const seccion = contenedor.closest<HTMLElement>('[aria-labelledby]');
  const titulo = seccion?.getAttribute('aria-labelledby');
  if (titulo && document.getElementById(titulo)) {
    contenedor.setAttribute('aria-labelledby', titulo);
    return;
  }

  // Declared as a translated attribute so a language switch renames it too.
  contenedor.dataset.i18nAttr = 'aria-label:common.tablaDesplazable';
  contenedor.setAttribute('aria-label', t('common.tablaDesplazable'));
}

/** Make one container reachable by keyboard while it overflows, and only then. */
export function actualizarDesplazable(contenedor: HTMLElement): void {
  const propio = contenedor.dataset[MARCA] === 'auto';
  // A page that already set its own tabindex made the decision; respect it.
  if (!propio && contenedor.hasAttribute('tabindex')) return;

  if (desborda(contenedor)) {
    contenedor.dataset[MARCA] = 'auto';
    contenedor.tabIndex = 0;
    if (!contenedor.hasAttribute('role')) contenedor.setAttribute('role', 'region');
    nombrar(contenedor);
  } else if (propio) {
    contenedor.removeAttribute('tabindex');
    delete contenedor.dataset[MARCA];
  }
}

/**
 * Watch every current and future `.table-scroll` under `raiz`: size changes
 * (a narrower window, a table that grew) and containers added by scripts.
 * Returns a function that stops watching, for tests.
 */
export function observarDesplazables(raiz: ParentNode = document): () => void {
  const vistos = new WeakSet<HTMLElement>();
  const tamanos =
    typeof ResizeObserver === 'undefined'
      ? null
      : new ResizeObserver((entradas) => {
          entradas.forEach((e) => actualizarDesplazable(e.target as HTMLElement));
        });

  const registrar = (contenedor: HTMLElement): void => {
    if (vistos.has(contenedor)) {
      actualizarDesplazable(contenedor);
      return;
    }
    vistos.add(contenedor);
    tamanos?.observe(contenedor);
    // The table inside can grow without the container changing size.
    const tabla = contenedor.querySelector('table');
    if (tabla) tamanos?.observe(tabla);
    actualizarDesplazable(contenedor);
  };

  const recorrer = (nodo: ParentNode): void => {
    if (nodo instanceof HTMLElement && nodo.matches(SELECTOR)) registrar(nodo);
    nodo.querySelectorAll<HTMLElement>(SELECTOR).forEach(registrar);
  };

  recorrer(raiz);

  const cambios = new MutationObserver((mutaciones) => {
    for (const m of mutaciones) {
      m.addedNodes.forEach((nodo) => {
        if (nodo instanceof HTMLElement) recorrer(nodo);
      });
      // Rows added into an existing container change its overflow too.
      const contenedor = (m.target as Element).closest?.(SELECTOR);
      if (contenedor instanceof HTMLElement) registrar(contenedor);
    }
  });
  const destino = raiz instanceof Document ? raiz.body : (raiz as Node);
  cambios.observe(destino, { childList: true, subtree: true });

  return () => {
    cambios.disconnect();
    tamanos?.disconnect();
  };
}

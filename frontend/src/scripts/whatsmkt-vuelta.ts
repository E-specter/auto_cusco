/**
 * What a WhatsMKT screen shows when Columnas de carga sent the analyst back (T-WM-F2b): the announcement of the definition chosen, the notice of one
 * that is gone, and the URL cleaned so that reloading does not apply it twice. The campaign and the settings share the three elements, by data
 * attribute: `data-definicion-anuncio`, `data-definicion-noexiste` and the error of the select (`data-definicion-error`, which each page owns).
 */

import { $ } from '../lib/dom';
import { destinoSinDefinicion } from '../lib/volver';
import { textoDeVuelta, type VueltaDeDefinicion } from '../lib/whatsmkt-vuelta';

/**
 * Says what came back: announces the definition chosen or shows the notice of the one that is gone. Returns the text for the error of the select
 * («definicion_no_whatsmkt»), which the page puts where it keeps its own, and an empty one for anything else. `sinGuardar` is the settings: the
 * definition is only on the select, and the announcement says it still has to be saved.
 */
export function decirLaVuelta(vuelta: VueltaDeDefinicion, sinGuardar = false): string {
  $<HTMLElement>('[data-definicion-anuncio]').textContent = vuelta.tipo === 'elegida' ? textoDeVuelta(vuelta, sinGuardar) : '';
  $<HTMLElement>('[data-definicion-noexiste]').hidden = vuelta.tipo !== 'noExiste';
  return vuelta.tipo === 'noEsDeWhatsmkt' ? textoDeVuelta(vuelta) : '';
}

/** Choosing another definition takes the announcement and the notice away. */
export function olvidarLaVuelta(): void {
  $<HTMLElement>('[data-definicion-anuncio]').textContent = '';
  $<HTMLElement>('[data-definicion-noexiste]').hidden = true;
}

/** Once read, `definicion` and `version` leave the URL; whatever else it carries (the selection of the campaign) stays. */
export function limpiarLaUrl(): void {
  window.history.replaceState(null, '', destinoSinDefinicion(`${window.location.pathname}${window.location.search}`));
}

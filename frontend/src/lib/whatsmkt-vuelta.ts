/**
 * Going to Columnas de carga from WhatsMKT and coming back (T-WM-F2b, docs/motor-texto-enriquecido-interfaz.md §12): the link that goes, and what the
 * screen of origin finds in its own URL when it is back. Pure on purpose: the pages hand in the list of definitions and the query, and these decide.
 */

import { t } from './i18n';
import { definicionDeLaUrl, enlaceCrearDefinicion, enlaceEditarDefinicion } from './volver';

/** The platform of WhatsMKT in the definitions API. */
const PLATAFORMA = 'whatsmkt';

export type VueltaDeDefinicion =
  /** Nothing came back (the common case): the screen opens as it always does. */
  | { tipo: 'ninguna' }
  | { tipo: 'elegida'; id: number; version: number; nombre: string }
  /** The definition, or that version of it, is gone. */
  | { tipo: 'noExiste' }
  /** It exists but it is not a WhatsMKT one (a free one was opened, say). */
  | { tipo: 'noEsDeWhatsmkt' };

interface DefinicionDeLaLista {
  id: number;
  nombre: string;
  plataforma: string | null;
  version_vigente: number;
}

/**
 * What `?definicion=<id>&version=<n>` says against the definitions the API listed (all of them, not only WhatsMKT's: telling a definition that
 * is gone from one that is another platform's needs both). A version above the latest does not exist; the ones below it do. What is chosen is the
 * latest one (the campaign always uses it), so that is the `version` that comes back, not the one the URL asked for.
 */
export function vueltaDeDefinicion(busqueda: string, definiciones: readonly DefinicionDeLaLista[]): VueltaDeDefinicion {
  const pedida = definicionDeLaUrl(busqueda);
  if (pedida === null) return { tipo: 'ninguna' };
  const definicion = definiciones.find((d) => d.id === pedida.id);
  if (definicion === undefined || pedida.version > definicion.version_vigente) return { tipo: 'noExiste' };
  if (definicion.plataforma !== PLATAFORMA) return { tipo: 'noEsDeWhatsmkt' };
  return { tipo: 'elegida', id: definicion.id, version: definicion.version_vigente, nombre: definicion.nombre };
}

/**
 * The sentence of a way back; empty when nothing came back. The name goes quoted, as everywhere else. The settings only put the definition on the
 * select, so their announcement adds that it still has to be saved (`sinGuardar`).
 */
export function textoDeVuelta(vuelta: VueltaDeDefinicion, sinGuardar = false): string {
  switch (vuelta.tipo) {
    case 'ninguna':
      return '';
    case 'elegida': {
      const nombre = t('camposAdicionales.nombreCitado', { campo: vuelta.nombre });
      return sinGuardar
        ? t('whatsmkt.configuracion.definicion.elegidaSinGuardar', { nombreCitado: nombre, n: vuelta.version })
        : t('herramientas.volver.elegida', { nombre, n: vuelta.version });
    }
    case 'noExiste':
      return t('herramientas.volver.noExiste');
    case 'noEsDeWhatsmkt':
      return t('whatsmkt.codigo.definicion_no_whatsmkt');
  }
}

/**
 * Where «Editar en Columnas de carga» goes: the definition chosen; a new one of the platform when there is none to choose (the label says «Crear»);
 * and Columnas itself, with only the way back, when there are some and none is chosen yet. All of them come back to `volver`, the screen with its query.
 */
export function destinoDeColumnas(elegida: number | null, hayDefiniciones: boolean, volver: string): { href: string; clave: string } {
  if (elegida !== null) return { href: enlaceEditarDefinicion(elegida, volver), clave: 'whatsmkt.archivo.editar' };
  return hayDefiniciones
    ? { href: enlaceConVolver('/columnas', volver), clave: 'whatsmkt.archivo.editar' }
    : { href: enlaceCrearDefinicion(PLATAFORMA, volver), clave: 'whatsmkt.archivo.crear' };
}

/** `ruta` (Supervisores, Calendario, Columnas) with the screen it came from, so it can say «Volver a WhatsMKT». */
export function enlaceConVolver(ruta: string, volver: string): string {
  return `${ruta}?${new URLSearchParams({ volver }).toString()}`;
}

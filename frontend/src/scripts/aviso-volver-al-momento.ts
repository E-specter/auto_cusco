/**
 * The notice of Supervisores and Calendario laboral when a channel sent the analyst there (T-HI-F3,
 * docs/motor-texto-enriquecido-interfaz.md §12.2 and §12.3): they save each change as it is made, so there is nothing to
 * save and nothing to go back with on its own; the link says «Volver a {canal}». Without a valid `volver` it does nothing.
 * The page imports this module and renders `components/AvisoVolver.astro` under its header.
 */

import { volverValido } from '../lib/volver';
import { montarAvisoVolver } from './aviso-volver';

const volver = volverValido(new URLSearchParams(window.location.search).get('volver'), window.location.origin);

montarAvisoVolver(document, {
  volver,
  destino: volver ?? '/',
  linea: () => ({ clave: 'herramientas.volver.alMomento' }),
  enlace: 'volver',
});

/**
 * Behaviour of the notice of a tool that a channel sent the analyst to (T-HI-F3, RF-74,
 * docs/motor-texto-enriquecido-interfaz.md §12). The markup is `components/AvisoVolver.astro`; the page validates `volver`
 * with `volverValido` (`lib/volver.ts`) and hands it here.
 *
 *     const aviso = montarAvisoVolver(document, { volver, destino, linea, enlace });
 *     aviso.pintar();   // after a change of what the line says or of the language
 *
 * With no valid `volver` nothing is shown and nothing is changed: the tool is what it was. The channel's name comes from the
 * prefix of `volver`, with the keys of the bar (`nav.mowaMes`, `nav.whatsmkt`), so a new channel is a new prefix and its key.
 */

import { t } from '../lib/i18n';
import { origenDeVolver } from '../lib/volver';

export interface OpcionesAvisoVolver {
  /** The `volver` that `volverValido` accepted, or `null`: then nothing is shown. */
  volver: string | null;
  /** Where the link goes. «Back without saving» goes to `volver` as it came (it is the page that says so). */
  destino: string;
  /** The line: its key and the values besides `{canal}`. It is read again every time the notice is painted. */
  linea: () => { clave: string; valores?: Record<string, string | number> };
  /** The text of the link: «Volver a {canal} sin guardar» (a tool with something to save) or «Volver a {canal}». */
  enlace: 'sinGuardar' | 'volver';
  /** The key of the screen's own text for the link, when it has one (`/cartera`: «Volver a la campaña sin guardar»). */
  claveEnlace?: string;
  /** Asked before going back; `false` stays. A click with a modifier is the browser's own and is not asked. */
  antesDeVolver?: () => Promise<boolean>;
}

export interface AvisoVolver {
  /** Paints the line and the link again: the text depends on the language and, in a tool, on what is on screen. */
  pintar(): void;
}

/** The name of the channel a valid `volver` belongs to, in the language of the screen; `null` if it is not one of a channel. */
export function canalDeVolver(volver: string): string | null {
  const origen = origenDeVolver(volver);
  return origen === null ? null : t(origen === 'whatsmkt' ? 'nav.whatsmkt' : 'nav.mowaMes');
}

export function montarAvisoVolver(raiz: ParentNode, opciones: OpcionesAvisoVolver): AvisoVolver {
  const aviso = raiz.querySelector<HTMLElement>('[data-volver]');
  const enlace = raiz.querySelector<HTMLAnchorElement>('[data-volver-enlace]');
  const linea = raiz.querySelector<HTMLElement>('[data-volver-linea]');
  const texto = raiz.querySelector<HTMLElement>('[data-volver-enlace-texto]');
  const { volver } = opciones;
  // Not a path of a channel (it did not go through `volverValido`): nothing is shown, as if no `volver` had come.
  if (!aviso || !enlace || !linea || !texto || volver === null || canalDeVolver(volver) === null) return { pintar: () => undefined };

  function pintar(): void {
    const canal = canalDeVolver(volver!)!;
    const { clave, valores } = opciones.linea();
    linea!.textContent = t(clave, { canal, ...valores });
    texto!.textContent = t(
      opciones.claveEnlace ?? (opciones.enlace === 'sinGuardar' ? 'herramientas.volver.sinGuardar' : 'herramientas.volver.volver'),
      { canal },
    );
    enlace!.href = opciones.destino;
  }

  enlace.addEventListener('click', async (evento) => {
    // A click with a modifier is the browser's own (new tab): it keeps its link.
    if (evento.button !== 0 || evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.altKey) return;
    evento.preventDefault();
    if (opciones.antesDeVolver && !(await opciones.antesDeVolver())) return;
    window.location.assign(opciones.destino);
  });
  document.addEventListener('languagechange', pintar);

  aviso.hidden = false;
  pintar();
  return { pintar };
}

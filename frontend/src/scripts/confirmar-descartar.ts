/**
 * The question «Hay cambios sin guardar» before leaving what has changed, with the selector's own words
 * (`selector.descartar.*`, «Seguir editando» stays). The dialog is the page's: `data-descartar-si` and `data-descartar-no` are
 * its buttons. Escape and the backdrop are «no». It answers `true` when the analyst chose to discard.
 */

import { openWhenFree } from '../lib/dialogs';

export function confirmarDescartar(dialogo: HTMLDialogElement): Promise<boolean> {
  return new Promise((resolver) => {
    const si = dialogo.querySelector<HTMLButtonElement>('[data-descartar-si]')!;
    const no = dialogo.querySelector<HTMLButtonElement>('[data-descartar-no]')!;
    let respuesta = false;
    // The dialog may wait its turn behind another one: until it is shown, and while it is open, a `close` is not this answer's.
    let listo = false;
    const alSi = () => {
      respuesta = true;
      dialogo.close();
    };
    const alNo = () => dialogo.close();
    si.addEventListener('click', alSi, { once: true });
    no.addEventListener('click', alNo, { once: true });
    const alCerrar = () => {
      if (!listo || dialogo.open) return;
      si.removeEventListener('click', alSi);
      no.removeEventListener('click', alNo);
      dialogo.removeEventListener('close', alCerrar);
      resolver(respuesta);
    };
    dialogo.addEventListener('close', alCerrar);
    void openWhenFree(dialogo).then(() => {
      listo = true;
      no.focus();
    });
  });
}

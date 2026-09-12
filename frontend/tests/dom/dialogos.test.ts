/**
 * Modal sequencing (V-6 then V-4).
 *
 * The identical-file warning answers the upload; the current-version question
 * answers background processing that finishes on its own clock. They collide
 * in real use — it happened on a real run — and when they do, the question
 * that decides what the portfolio reads must not end up under a notice.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { openWhenFree } from '../../src/lib/dialogs';

/**
 * jsdom implements `<dialog>` but not the modal top layer, so `showModal` is
 * stubbed to do the one thing this logic depends on: mark the dialog open.
 */
function crearDialogo(nombre: string): HTMLDialogElement {
  const dialogo = document.createElement('dialog');
  dialogo.dataset.dialog = nombre;
  dialogo.showModal = vi.fn(() => dialogo.setAttribute('open', ''));
  dialogo.close = vi.fn(() => {
    dialogo.removeAttribute('open');
    dialogo.dispatchEvent(new Event('close'));
  });
  document.body.append(dialogo);
  return dialogo;
}

const estaAbierto = (d: HTMLDialogElement) => d.hasAttribute('open');

beforeEach(() => {
  document.body.replaceChildren();
});

describe('cola de diálogos', () => {
  it('abre de inmediato cuando no hay nada abierto', async () => {
    const vigente = crearDialogo('vigente');

    await openWhenFree(vigente);

    expect(estaAbierto(vigente)).toBe(true);
  });

  it('espera su turno en vez de apilarse sobre el aviso de archivo idéntico', async () => {
    const duplicado = crearDialogo('duplicate');
    const vigente = crearDialogo('vigente');
    duplicado.showModal();

    const turno = openWhenFree(vigente);

    expect(estaAbierto(vigente)).toBe(false);
    expect(vigente.showModal).not.toHaveBeenCalled();

    duplicado.close();
    await turno;

    expect(estaAbierto(vigente)).toBe(true);
  });

  it('no pierde la pregunta de vigente: aparece siempre, solo que después', async () => {
    // El caso que de verdad importa. Antes de la cola, la pregunta de V-4
    // quedaba tapada y el analista no la veía nunca.
    const duplicado = crearDialogo('duplicate');
    const vigente = crearDialogo('vigente');
    duplicado.showModal();

    const turno = openWhenFree(vigente);
    duplicado.close();
    await turno;

    expect(estaAbierto(duplicado)).toBe(false);
    expect(estaAbierto(vigente)).toBe(true);
  });

  it('drena una cadena de tres diálogos en orden', async () => {
    const primero = crearDialogo('duplicate');
    const segundo = crearDialogo('error');
    const tercero = crearDialogo('vigente');
    primero.showModal();

    const turnoSegundo = openWhenFree(segundo);
    const turnoTercero = openWhenFree(tercero);

    primero.close();
    await turnoSegundo;
    expect(estaAbierto(segundo)).toBe(true);
    expect(estaAbierto(tercero)).toBe(false);

    segundo.close();
    await turnoTercero;
    expect(estaAbierto(tercero)).toBe(true);
  });

  it('no se bloquea a sí mismo si ya estaba abierto', async () => {
    const vigente = crearDialogo('vigente');
    vigente.setAttribute('open', '');

    await openWhenFree(vigente);

    expect(estaAbierto(vigente)).toBe(true);
  });
});

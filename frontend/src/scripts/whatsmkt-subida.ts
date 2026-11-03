/**
 * Uploading a file from the campaign (T-WM-F2a2, docs/whatsmkt-interfaz.md §3.6): the same library of the settings, with its same rules, from
 * the screen that uses it. «Subir un archivo» beside the select of the file and «Subir una foto» beside the one of the photo.
 *
 * What an upload leaves is chosen in its select at once and said in a status line. A file the library already had (same fingerprint) is
 * the one that is chosen; one that was there archived is not brought back by itself: the status offers «Restaurar y usar». A refusal is the
 * module's own, by its code, under the select. The file is judged by the server on upload (it recognises the type by the file's own
 * signature and measures a photo), so choosing a file is already validating it.
 *
 * It binds to the markup by `data-subir*="adjunto|foto"` and keeps nothing but the archived attachment it offers to restore.
 */

import { mensajeDeError } from '../lib/api';
import { desarchivarAdjunto, subirAdjunto, type AdjuntoWhatsmkt } from '../lib/api-whatsmkt';
import { $, ocupado } from '../lib/dom';
import { t } from '../lib/i18n';
import { quedoArchivado, textoDeSubida } from '../lib/whatsmkt-campana';
import { errorDeModulo, textoDeErrorAdjunto } from '../lib/whatsmkt';

export interface OpcionesSubida {
  proposito: 'adjunto' | 'foto';
  /** The select the file ends up chosen in: it carries the error and its mark. */
  select: HTMLSelectElement;
  /** The attachment is in the library and to be used (new, the same one again, or restored): the screen lists it and chooses it. */
  alUsar(adjunto: AdjuntoWhatsmkt): void;
}

export function montarSubida({ proposito, select, alUsar }: OpcionesSubida): void {
  const nodo = <T extends HTMLElement>(parte: string) => $<T>(`[data-subir-${parte}="${proposito}"]`);
  const boton = $<HTMLButtonElement>(`[data-subir="${proposito}"]`);
  const entrada = nodo<HTMLInputElement>('entrada');
  const error = nodo('error');
  const estado = nodo('estado');
  const restaurar = nodo<HTMLButtonElement>('restaurar');
  /** The attachment an upload found already archived, which the status offers to restore. */
  let archivado: AdjuntoWhatsmkt | null = null;

  function limpiar(): void {
    error.textContent = '';
    estado.textContent = '';
    select.removeAttribute('aria-invalid');
    restaurar.hidden = true;
    archivado = null;
  }

  function fallar(caido: unknown): void {
    const delModulo = errorDeModulo(caido);
    error.textContent = delModulo ? textoDeErrorAdjunto(delModulo) : mensajeDeError(caido);
    select.setAttribute('aria-invalid', 'true');
  }

  boton.addEventListener('click', () => entrada.click());

  entrada.addEventListener('change', async () => {
    const archivo = entrada.files?.[0];
    if (!archivo) return;
    limpiar();
    ocupado(boton, true);
    try {
      const subido = await subirAdjunto(archivo, proposito);
      if (quedoArchivado(subido)) {
        archivado = subido;
        restaurar.hidden = false;
        estado.textContent = t('whatsmkt.envio.repetidoArchivado', { nombre: subido.nombre });
      } else {
        alUsar(subido);
        estado.textContent = textoDeSubida(subido);
      }
    } catch (caido) {
      fallar(caido);
    } finally {
      // The same file can be chosen again after a refusal: the field is cleared.
      entrada.value = '';
      ocupado(boton, false);
    }
  });

  restaurar.addEventListener('click', async () => {
    if (!archivado) return;
    ocupado(restaurar, true);
    try {
      const vuelto = await desarchivarAdjunto(archivado.id);
      limpiar();
      alUsar(vuelto);
      estado.textContent = t('whatsmkt.envio.subido', { nombre: vuelto.nombre });
      select.focus();
    } catch (caido) {
      fallar(caido);
    } finally {
      ocupado(restaurar, false);
    }
  });
}

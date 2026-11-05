/**
 * «Para subir a WhatsMKT» (T-WM-F2a2, docs/whatsmkt-interfaz.md §3.10): what the analyst needs to upload the lot that was just created, one
 * campaign at a time, in three numbered steps: the files to download (the contact list, the profile photo and the attachment, if there are),
 * the data of the WhatsMKT form each with its «Copiar», and the link to the follow-up where the report is imported afterwards.
 *
 * It is the pattern of «Para subir a MES». The text of the message arrives with `[whatsapp]` already written as the link, and a campaign
 * whose message uses it with no contact WhatsApp set up says so (`avisos`). It binds to the markup by data attributes and keeps only what it
 * was shown, so a language switch can draw it again.
 */

import { descargarAdjunto, descargarArchivoCampana, type AdjuntoWhatsmkt, type CampanaCreada } from '../lib/api-whatsmkt';
import { $ } from '../lib/dom';
import { t } from '../lib/i18n';
import { datosDeFicha } from '../lib/whatsmkt-campana';
import { textoDeCodigo } from '../lib/whatsmkt';
import { filaDeArchivo, pintarDatosDeFicha } from './whatsmkt-ficha-partes';

export interface Ficha {
  /** Shows the card of the lot just created. `etiquetaDe` names a campaign in the `.segmented` (its segment), when the lot has more than one. */
  mostrar(creadas: readonly CampanaCreada[], adjuntos: readonly AdjuntoWhatsmkt[], etiquetaDe: (campana: CampanaCreada) => string): void;
  /** Draws what is shown again, in the language that is on. */
  repintar(): void;
}

export function montarFicha(): Ficha {
  const panel = $<HTMLElement>('[data-ficha]');
  const aviso = $<HTMLElement>('[data-ficha-aviso]');
  const campanas = $<HTMLElement>('[data-ficha-campanas]');
  const archivos = $<HTMLElement>('[data-ficha-archivos]');
  const errorDescarga = $<HTMLElement>('[data-ficha-descarga-error]');
  const avisos = $<HTMLElement>('[data-ficha-avisos]');
  const datos = $<HTMLElement>('[data-ficha-datos]');
  const estadoCopia = $<HTMLElement>('[data-ficha-copia-estado]');
  const seguimiento = $<HTMLAnchorElement>('[data-ficha-seguimiento]');

  let creadas: readonly CampanaCreada[] = [];
  let adjuntos: readonly AdjuntoWhatsmkt[] = [];
  let etiquetaDe: (campana: CampanaCreada) => string = (campana) => campana.nombre;
  let elegida = 0;

  const alFallar = (texto: string): void => {
    errorDescarga.textContent = texto;
  };
  const nombreDeAdjunto = (id: number, respaldo: string): string => adjuntos.find((a) => a.id === id)?.nombre ?? respaldo;

  function pintarCampana(): void {
    const campana = creadas[elegida];
    if (!campana) return;
    const ficha = campana.ficha;
    errorDescarga.textContent = '';
    estadoCopia.textContent = '';

    // Step 1: the files, in the order they are asked for: the list of contacts, the photo, the attachment.
    const lista: HTMLElement[] = [filaDeArchivo(t('whatsmkt.subir.archivo.lista'), campana.archivo.nombre, () => descargarArchivoCampana(campana.id), alFallar)];
    if (ficha.foto_id !== null) {
      const id = ficha.foto_id;
      lista.push(filaDeArchivo(t('whatsmkt.subir.archivo.foto'), nombreDeAdjunto(id, t('whatsmkt.envio.foto')), () => descargarAdjunto(id), alFallar));
    }
    if (ficha.adjunto_id !== null) {
      const id = ficha.adjunto_id;
      lista.push(filaDeArchivo(t('whatsmkt.subir.archivo.adjunto'), nombreDeAdjunto(id, t('whatsmkt.envio.adjunto')), () => descargarAdjunto(id), alFallar));
    }
    archivos.replaceChildren(...lista);

    // Step 2: the data of the form, one line each: what it asks, what to write, «Copiar».
    avisos.hidden = !ficha.avisos.includes('sin_whatsapp');
    avisos.textContent = ficha.avisos.includes('sin_whatsapp') ? textoDeCodigo({ codigo: 'sin_whatsapp', detail: '' }) : '';
    pintarDatosDeFicha(datos, datosDeFicha(ficha, adjuntos), (texto) => (estadoCopia.textContent = texto));

    // Step 3: the follow-up of this campaign, where its report is imported.
    seguimiento.href = `/whatsmkt/seguimiento?campana=${campana.id}`;
  }

  function pintar(): void {
    if (creadas.length === 0) return;
    aviso.textContent =
      creadas.length > 1
        ? t('whatsmkt.subir.creadas', { n: creadas.length, lote: creadas[0].lote_id })
        : t('whatsmkt.subir.creada', { id: creadas[0].id });
    campanas.hidden = creadas.length < 2;
    campanas.replaceChildren(
      ...(creadas.length < 2
        ? []
        : creadas.map((campana, i) => {
            const boton = document.createElement('button');
            boton.type = 'button';
            boton.className = 'segmented__item';
            boton.textContent = etiquetaDe(campana);
            boton.setAttribute('aria-pressed', String(i === elegida));
            boton.addEventListener('click', () => {
              elegida = i;
              pintar();
              // The buttons were drawn again: the focus goes back to the one that was pressed.
              campanas.querySelectorAll<HTMLElement>('button')[i]?.focus();
            });
            return boton;
          })),
    );
    pintarCampana();
  }

  return {
    mostrar(nuevas, lista, nombrar) {
      creadas = nuevas;
      adjuntos = lista;
      etiquetaDe = nombrar;
      elegida = 0;
      panel.hidden = false;
      pintar();
      panel.focus();
      panel.scrollIntoView({ block: 'start' });
    },
    repintar: pintar,
  };
}

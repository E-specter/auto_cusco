/**
 * The two pieces of the card of a campaign that the screen of creating and the one of tracking share (docs/whatsmkt-interfaz.md §3.10 and §4.2):
 * a file to download with what it is in front, and the data of the WhatsMKT form each with its «Copiar». They draw into what the page hands over
 * and say their results through a callback, so each page keeps its own status line. The icons come from the page's templates
 * (`template[data-icono-copiar]` and `[data-icono-descargar]`).
 */

import { mensajeDeError } from '../lib/api';
import { guardarArchivo, type ArchivoDescargado } from '../lib/descargas';
import { $ } from '../lib/dom';
import { t } from '../lib/i18n';
import { copiarTexto } from '../lib/portapapeles';
import type { DatoDeFicha } from '../lib/whatsmkt-campana';

const icono = (clave: string): Node => $<HTMLTemplateElement>(`template[data-icono-${clave}]`).content.cloneNode(true);

/**
 * A file to download with what it is in front (the photo and the attachment can be the same file, and two equal names would confuse).
 * `alFallar` gets the reason a download failed, and an empty text when a new one starts.
 */
export function filaDeArchivo(
  rotulo: string,
  nombre: string,
  pedir: () => Promise<ArchivoDescargado>,
  alFallar: (texto: string) => void,
): HTMLElement {
  const fila = document.createElement('li');
  fila.className = 'wm-ficha__archivo';
  const queEs = document.createElement('span');
  queEs.className = 'muted wm-ficha__rotulo';
  queEs.textContent = rotulo;
  const texto = document.createElement('span');
  texto.className = 'mono wm-ficha__valor';
  texto.textContent = nombre;
  const boton = document.createElement('button');
  boton.type = 'button';
  boton.className = 'btn btn--sm';
  boton.setAttribute('aria-label', `${t('whatsmkt.biblioteca.descargar')} ${rotulo}: ${nombre}`);
  boton.append(icono('descargar'), document.createTextNode(t('whatsmkt.biblioteca.descargar')));
  boton.addEventListener('click', async () => {
    alFallar('');
    try {
      const archivo = await pedir();
      guardarArchivo(archivo.blob, archivo.nombre || nombre);
    } catch (caido) {
      alFallar(mensajeDeError(caido));
    }
  });
  fila.append(queEs, texto, boton);
  return fila;
}

/** Marks a text as selected: when the clipboard is refused, the analyst copies it with Ctrl+C. */
function seleccionar(nodo: HTMLElement): void {
  const seleccion = window.getSelection();
  if (!seleccion) return;
  seleccion.removeAllRanges();
  const rango = document.createRange();
  rango.selectNodeContents(nodo);
  seleccion.addRange(rango);
}

/** The data of the form in one `dl`: what it asks, what to write, and a «Copiar» that names it. `anunciar` says «Copiado: {dato}» or why it could not. */
export function pintarDatosDeFicha(destino: HTMLElement, datos: readonly DatoDeFicha[], anunciar: (texto: string) => void): void {
  destino.replaceChildren(
    ...datos.map((dato) => {
      const fila = document.createElement('div');
      fila.className = 'wm-ficha__dato';
      const nombre = document.createElement('dt');
      nombre.textContent = dato.etiqueta;
      const valor = document.createElement('dd');
      const texto = document.createElement('span');
      texto.className = `mono wm-ficha__valor${dato.multilinea ? ' wm-ficha__valor--bloque' : ''}`;
      texto.textContent = dato.valor;
      valor.append(texto);
      const copiar = document.createElement('dd');
      copiar.className = 'wm-ficha__copiar';
      const boton = document.createElement('button');
      boton.type = 'button';
      boton.className = 'btn btn--sm btn--icon';
      boton.setAttribute('aria-label', t('mowaMes.accion.copiar', { dato: dato.etiqueta }));
      boton.title = t('mowaMes.accion.copiar', { dato: dato.etiqueta });
      boton.append(icono('copiar'));
      boton.addEventListener('click', async () => {
        if ((await copiarTexto(dato.valor)) === 'fallo') {
          seleccionar(texto);
          anunciar(t('mowaMes.campana.subir.copiarFallo', { dato: dato.etiqueta }));
        } else {
          anunciar(t('mowaMes.estado.copiado', { dato: dato.etiqueta }));
        }
      });
      copiar.append(boton);
      fila.append(nombre, valor, copiar);
      return fila;
    }),
  );
}

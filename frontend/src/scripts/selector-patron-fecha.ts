/**
 * A parameter with known options, above all a date pattern (interface rules
 * §2.3, §9.5): a select with each option and its example ("dd/mm/aaaa —
 * 05/10/2026") and, when the options are not closed, "Personalizado", which
 * shows a text field and the readable date marks as buttons that insert at
 * the caret. The analyst never sees `strftime`.
 */

import { t } from '../lib/i18n';
import type { components } from '../lib/contrato-api';

type Esquemas = components['schemas'];

export interface OpcionesSelectorPatron {
  /** Id of the select; the custom field gets `${id}-propio`. */
  id: string;
  /** Visible label, already translated. */
  etiqueta: string;
  opciones: readonly Esquemas['OpcionRespuesta'][];
  /** Whether a value outside the options is allowed. */
  cerradas: boolean;
  /** Date marks to insert in a custom pattern; empty for other parameters. */
  marcas: readonly Esquemas['MarcaFechaRespuesta'][];
  valor: string;
  /** Ids to add to the controls' aria-describedby (an error slot). */
  describe?: string;
  onCambio: (valor: string) => void;
}

const PROPIO = '__propio__';

export function crearSelectorPatronFecha(opciones: OpcionesSelectorPatron): HTMLElement {
  const raiz = document.createElement('div');
  raiz.className = 'field selector-patron';

  const etiqueta = document.createElement('label');
  etiqueta.className = 'field__label';
  etiqueta.htmlFor = opciones.id;
  etiqueta.textContent = opciones.etiqueta;

  const select = document.createElement('select');
  select.className = 'input';
  select.id = opciones.id;
  if (opciones.describe) select.setAttribute('aria-describedby', opciones.describe);

  const conocido = opciones.opciones.some((o) => o.valor === opciones.valor);
  for (const opcion of opciones.opciones) {
    const elemento = document.createElement('option');
    elemento.value = opcion.valor;
    elemento.textContent = opcion.ejemplo ? `${opcion.valor} — ${opcion.ejemplo}` : opcion.valor;
    elemento.selected = opcion.valor === opciones.valor;
    select.append(elemento);
  }
  if (!opciones.cerradas) {
    const propio = document.createElement('option');
    propio.value = PROPIO;
    propio.textContent = t('editorTexto.patron.personalizado');
    propio.selected = !conocido;
    select.append(propio);
  }

  const bloquePropio = document.createElement('div');
  bloquePropio.className = 'selector-patron__propio';
  const etiquetaPropio = document.createElement('label');
  etiquetaPropio.className = 'visually-hidden';
  etiquetaPropio.htmlFor = `${opciones.id}-propio`;
  etiquetaPropio.textContent = t('editorTexto.patron.propio', { campo: opciones.etiqueta });
  const campo = document.createElement('input');
  campo.type = 'text';
  campo.className = 'input mono';
  campo.id = `${opciones.id}-propio`;
  campo.autocomplete = 'off';
  campo.value = conocido ? '' : opciones.valor;
  if (opciones.describe) campo.setAttribute('aria-describedby', opciones.describe);
  bloquePropio.append(etiquetaPropio, campo);

  if (opciones.marcas.length > 0) {
    const marcas = document.createElement('div');
    marcas.className = 'selector-patron__marcas';
    marcas.setAttribute('role', 'group');
    marcas.setAttribute('aria-label', t('editorTexto.patron.marcas'));
    for (const marca of opciones.marcas) {
      const boton = document.createElement('button');
      boton.type = 'button';
      boton.className = 'btn btn--sm btn--quiet mono';
      boton.textContent = marca.marca;
      const nombre = t(marca.clave);
      boton.title = `${nombre === marca.clave ? marca.marca : nombre} — ${marca.ejemplo}`;
      boton.setAttribute('aria-label', boton.title);
      boton.addEventListener('click', () => {
        const inicio = campo.selectionStart ?? campo.value.length;
        const fin = campo.selectionEnd ?? inicio;
        campo.value = `${campo.value.slice(0, inicio)}${marca.marca}${campo.value.slice(fin)}`;
        const cursor = inicio + marca.marca.length;
        campo.focus();
        campo.setSelectionRange(cursor, cursor);
        opciones.onCambio(campo.value);
      });
      marcas.append(boton);
    }
    bloquePropio.append(marcas);
  }

  const mostrarPropio = () => {
    bloquePropio.hidden = select.value !== PROPIO;
  };
  select.addEventListener('change', () => {
    mostrarPropio();
    if (select.value === PROPIO) {
      campo.focus();
      opciones.onCambio(campo.value);
    } else {
      opciones.onCambio(select.value);
    }
  });
  campo.addEventListener('input', () => opciones.onCambio(campo.value));
  mostrarPropio();

  raiz.append(etiqueta, select, bloquePropio);
  return raiz;
}

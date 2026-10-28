/**
 * The field list of one header in the mapper: a combobox you can type into to filter it
 * (docs/mapeador-encabezados-interfaz.md §3.5, RF-59). The ARIA pattern of a combobox with list
 * autocomplete and manual selection: only Enter or a click chooses; Escape, Tab and leaving close
 * without changing anything. The list opens inside the cell, in the flow, so no scroll clips it.
 */

import { filtrarVariables } from '../lib/editor-texto';
import { t } from '../lib/i18n';

/** A field as the list shows it. `texto` may carry «· en uso en C»; the search uses `etiqueta`. */
export interface OpcionCampo {
  nombre: string;
  etiqueta: string;
  alias: readonly string[];
  texto: string;
  grupo: 'obligatorios' | 'otros' | 'adicionales';
  deshabilitada: boolean;
}

export interface OpcionesSelectorCampo {
  /** The input's id; the list and its options hang from it. */
  id: string;
  nombre: string;
  /** The fields now, in order; asked on every paint, so «en uso» is always current. */
  opciones: () => OpcionCampo[];
  /** The chosen field, or '' for «No cargar esta columna». */
  valor: () => string;
  onElegir: (valor: string) => void;
  /** Says the number of results while typing, in the component's status region. */
  anunciar: (texto: string) => void;
}

export interface SelectorCampo {
  raiz: HTMLElement;
  input: HTMLInputElement;
  /** Repaints the closed text and, if open, the list. */
  pintar(): void;
}

const NO_CARGAR = '';
const GRUPOS = [
  ['obligatorios', 'mapeador.vista.obligatorios'],
  ['otros', 'mapeador.vista.otros'],
  ['adicionales', 'camposAdicionales.grupo'],
] as const;

export function crearSelectorCampo(opciones: OpcionesSelectorCampo): SelectorCampo {
  const { id } = opciones;
  const raiz = document.createElement('div');
  raiz.className = 'selector-campo';

  const input = document.createElement('input');
  input.type = 'text';
  input.className = 'input selector-campo__input';
  input.id = id;
  input.autocomplete = 'off';
  input.spellcheck = false;
  input.setAttribute('role', 'combobox');
  input.setAttribute('aria-label', opciones.nombre);
  input.setAttribute('aria-autocomplete', 'list');
  input.setAttribute('aria-expanded', 'false');
  input.setAttribute('aria-controls', `${id}-lista`);

  const lista = document.createElement('div');
  lista.className = 'selector-campo__lista';
  lista.id = `${id}-lista`;
  lista.setAttribute('role', 'listbox');
  lista.setAttribute('aria-label', opciones.nombre);
  lista.hidden = true;

  const vacio = document.createElement('p');
  vacio.className = 'field__hint selector-campo__vacio';
  vacio.hidden = true;

  raiz.append(input, lista, vacio);

  let abierto = false;
  let consulta = '';
  let activa = '';

  const textoDe = (valor: string) =>
    valor === NO_CARGAR ? t('mapeador.vista.noCargar') : (opciones.opciones().find((o) => o.nombre === valor)?.etiqueta ?? valor);
  // The visible name, the technical one (inside `filtrarVariables`) and the catalogue's aliases.
  const buscar = (texto: string) => filtrarVariables(opciones.opciones(), texto, (o) => [o.etiqueta, ...o.alias].join(' '));
  const nodos = () => [...lista.querySelectorAll<HTMLElement>('[role="option"]')];

  function crearOpcion(valor: string, texto: string, deshabilitada: boolean): HTMLElement {
    const nodo = document.createElement('div');
    nodo.className = 'selector-campo__opcion';
    nodo.id = `${id}-op-${valor || 'no-cargar'}`;
    nodo.setAttribute('role', 'option');
    nodo.dataset.valor = valor;
    nodo.setAttribute('aria-selected', String(valor === opciones.valor()));
    if (deshabilitada) nodo.setAttribute('aria-disabled', 'true');
    nodo.textContent = texto;
    return nodo;
  }

  function marcarActiva(valor: string): void {
    activa = valor;
    for (const nodo of nodos()) nodo.classList.toggle('is-activa', nodo.dataset.valor === valor);
    const nodo = nodos().find((n) => n.dataset.valor === valor);
    if (nodo) {
      input.setAttribute('aria-activedescendant', nodo.id);
      nodo.scrollIntoView({ block: 'nearest' });
    } else {
      input.removeAttribute('aria-activedescendant');
    }
  }

  function pintarLista(): void {
    const encontradas = buscar(consulta);
    lista.replaceChildren(crearOpcion(NO_CARGAR, t('mapeador.vista.noCargar'), false));
    for (const [grupo, clave] of GRUPOS) {
      const delGrupo = encontradas.filter((o) => o.grupo === grupo);
      if (delGrupo.length === 0) continue;
      const nodo = document.createElement('div');
      nodo.setAttribute('role', 'group');
      nodo.setAttribute('aria-label', t(clave));
      const titulo = document.createElement('div');
      titulo.className = 'selector-campo__grupo';
      titulo.setAttribute('aria-hidden', 'true');
      titulo.textContent = t(clave);
      nodo.append(titulo, ...delGrupo.map((o) => crearOpcion(o.nombre, o.texto, o.deshabilitada)));
      lista.append(nodo);
    }
    vacio.hidden = encontradas.length > 0;
    vacio.textContent = encontradas.length > 0 ? '' : t('mapeador.vista.sinResultados', { texto: consulta.trim() });
    // Typing puts the first field that can be chosen under Enter; an empty search goes back to the chosen one.
    const primera = encontradas.find((o) => !o.deshabilitada);
    marcarActiva(consulta.trim() && primera ? primera.nombre : nodos().some((n) => n.dataset.valor === activa) ? activa : opciones.valor());
  }

  function abrir(nuevaConsulta: string): void {
    if (!abierto) activa = opciones.valor();
    abierto = true;
    consulta = nuevaConsulta;
    lista.hidden = false;
    input.setAttribute('aria-expanded', 'true');
    pintarLista();
  }

  function cerrar(): void {
    abierto = false;
    consulta = '';
    lista.hidden = true;
    vacio.hidden = true;
    lista.replaceChildren();
    input.setAttribute('aria-expanded', 'false');
    input.removeAttribute('aria-activedescendant');
    input.value = textoDe(opciones.valor());
  }

  function elegir(valor: string): void {
    const nodo = nodos().find((n) => n.dataset.valor === valor);
    if (!nodo || nodo.getAttribute('aria-disabled') === 'true') return;
    cerrar();
    if (valor !== opciones.valor()) opciones.onElegir(valor);
    input.value = textoDe(opciones.valor());
    input.select();
  }

  function mover(paso: number): void {
    const todos = nodos();
    const actual = todos.findIndex((n) => n.dataset.valor === activa);
    const siguiente = todos[Math.min(todos.length - 1, Math.max(0, actual + paso))];
    if (siguiente) marcarActiva(siguiente.dataset.valor!);
  }

  input.addEventListener('focus', () => input.select());
  input.addEventListener('click', () => {
    if (!abierto) abrir('');
  });
  input.addEventListener('input', () => {
    if (!input.value.trim()) activa = opciones.valor();
    abrir(input.value);
    const n = buscar(consulta).length;
    opciones.anunciar(
      n === 0
        ? t('mapeador.vista.sinResultados', { texto: consulta.trim() })
        : t(n === 1 ? 'mapeador.vista.resultadosUno' : 'mapeador.vista.resultados', { n }),
    );
  });
  input.addEventListener('keydown', (evento) => {
    switch (evento.key) {
      case 'ArrowDown':
        evento.preventDefault();
        if (!abierto) abrir('');
        else if (!evento.altKey) mover(1);
        break;
      case 'ArrowUp':
        if (!abierto) return;
        evento.preventDefault();
        mover(-1);
        break;
      case 'Enter':
        // Never the form's implicit submit: in /cargas that would close the dialog.
        evento.preventDefault();
        if (abierto) elegir(activa);
        break;
      case 'Escape':
        if (!abierto) return;
        // The first Escape is the list's; only the next one reaches the dialog.
        evento.preventDefault();
        evento.stopPropagation();
        cerrar();
        input.select();
        break;
      case 'Tab':
        if (abierto) cerrar();
        break;
    }
  });
  // The focus stays in the input while clicking an option.
  lista.addEventListener('mousedown', (evento) => evento.preventDefault());
  lista.addEventListener('click', (evento) => {
    const nodo = (evento.target as HTMLElement).closest<HTMLElement>('[role="option"]');
    if (nodo) elegir(nodo.dataset.valor!);
  });
  raiz.addEventListener('focusout', (evento) => {
    if (abierto && !raiz.contains(evento.relatedTarget as Node | null)) cerrar();
  });

  return {
    raiz,
    input,
    pintar() {
      input.dataset.valor = opciones.valor();
      if (abierto) pintarLista();
      else input.value = textoDe(opciones.valor());
      // A narrow column cuts the chosen name with an ellipsis; the whole name is here.
      input.title = textoDe(opciones.valor());
    },
  };
}

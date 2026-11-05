/**
 * The list of functions a piece can add (interface rules §13.4): a search field and the compatible functions grouped by
 * family, each with its description and, when it needs no parameter, what it gives with the piece's example value, so the
 * analyst sees it before choosing. The field holds the focus and is the combobox (`aria-activedescendant` on the list).
 * Built at runtime, like the variable search, so it is a function and not an Astro component.
 *
 * shortcut: repite la lista de selector-variable.ts (campo, listbox, flechas); unificar si aparece un tercer buscador.
 */

import { filtrarVariables } from '../lib/editor-texto';
import { t } from '../lib/i18n';
import type { components } from '../lib/contrato-api';

type Funcion = components['schemas']['FuncionRespuesta'];

export interface OpcionesBuscadorFunciones {
  /** Prefix for every id inside. */
  id: string;
  /** The functions the piece accepts at this point of its chain, in the family order they show. */
  grupos: ReadonlyArray<{ familia: string; nombre: string; funciones: readonly Funcion[] }>;
  nombreDe: (funcion: Funcion) => string;
  descripcionDe: (funcion: Funcion) => string;
  /**
   * What each function would give with the piece's example value, by function name, asked once for all of them. A function
   * that needs parameters, or whose node failed, is not in the answer and its row stays without a result.
   */
  resultados: (funciones: readonly Funcion[]) => Promise<ReadonlyMap<string, string>>;
  onElegir: (nombre: string) => void;
  /** Escape (`true`) or leaving the field: the search closes. */
  onCerrar: (porEscape: boolean) => void;
}

export interface BuscadorFunciones {
  raiz: HTMLElement;
  campo: HTMLInputElement;
}

export function crearBuscadorFunciones(opciones: OpcionesBuscadorFunciones): BuscadorFunciones {
  const raiz = document.createElement('div');
  raiz.className = 'panel selector-variable selector-funcion';

  const listaId = `${opciones.id}-lista`;
  const idDe = (nombre: string) => `${opciones.id}-opcion-${nombre}`;

  const campo = document.createElement('input');
  campo.type = 'search';
  campo.className = 'input selector-variable__buscar';
  campo.autocomplete = 'off';
  campo.placeholder = t('editorTexto.funcion.buscar');
  campo.setAttribute('aria-label', t('editorTexto.funcion.buscar'));
  campo.setAttribute('role', 'combobox');
  campo.setAttribute('aria-expanded', 'true');
  campo.setAttribute('aria-controls', listaId);
  campo.setAttribute('aria-autocomplete', 'list');
  const cajaCampo = document.createElement('div');
  cajaCampo.className = 'selector-variable__campo';
  cajaCampo.append(campo);

  const lista = document.createElement('div');
  lista.className = 'selector-variable__lista';
  lista.id = listaId;
  lista.setAttribute('role', 'listbox');
  lista.setAttribute('aria-label', t('editorTexto.funcion.agregar'));
  // The field drives the list: the list is not a tab stop, so Tab leaves the search (and closes it) in one step.
  lista.tabIndex = -1;

  const vacio = document.createElement('p');
  vacio.className = 'empty selector-variable__vacio';
  vacio.hidden = true;
  raiz.append(cajaCampo, lista, vacio);

  let encontradas: Funcion[] = [];
  let indice = 0;
  // The answer arrives after the first paint, and a filter rebuilds the rows: the rows ask this map every time they are drawn.
  const respuestas = new Map<string, string>();

  function marcar(): void {
    const filas = [...lista.querySelectorAll<HTMLElement>('[role="option"]')];
    filas.forEach((fila, i) => {
      fila.setAttribute('aria-selected', String(i === indice));
      if (i === indice) fila.scrollIntoView({ block: 'nearest' });
    });
    const activa = encontradas[indice];
    if (activa) campo.setAttribute('aria-activedescendant', idDe(activa.nombre));
    else campo.removeAttribute('aria-activedescendant');
  }

  function pintarResultado(fila: HTMLElement, funcion: Funcion): void {
    const resultado = respuestas.get(funcion.nombre);
    if (resultado === undefined) return;
    let sitio = fila.querySelector<HTMLElement>('.selector-variable__ejemplo');
    if (!sitio) {
      sitio = document.createElement('span');
      sitio.className = 'mono muted selector-variable__ejemplo';
      fila.querySelector('.selector-variable__nombre')!.after(sitio);
    }
    sitio.textContent = t('editorTexto.funcion.ejemploResultado', { funcion: opciones.nombreDe(funcion), resultado });
  }

  function crearFila(funcion: Funcion): HTMLElement {
    const fila = document.createElement('div');
    fila.className = 'selector-variable__opcion';
    fila.id = idDe(funcion.nombre);
    fila.setAttribute('role', 'option');
    const nombre = document.createElement('span');
    nombre.className = 'selector-variable__nombre';
    nombre.textContent = opciones.nombreDe(funcion);
    fila.append(nombre);
    const descripcion = opciones.descripcionDe(funcion);
    if (descripcion) {
      const texto = document.createElement('p');
      texto.className = 'field__hint selector-funcion__descripcion';
      texto.textContent = descripcion;
      fila.append(texto);
    }
    pintarResultado(fila, funcion);
    // The mouse picks without taking the focus away from the field.
    fila.addEventListener('mousedown', (evento) => evento.preventDefault());
    fila.addEventListener('click', () => opciones.onElegir(funcion.nombre));
    return fila;
  }

  function pintar(consulta: string): void {
    const todas = opciones.grupos.flatMap((g) => g.funciones);
    const coinciden = new Set(filtrarVariables(todas, consulta, opciones.nombreDe).map((f) => f.nombre));
    indice = 0;
    lista.replaceChildren();
    encontradas = todas.filter((f) => coinciden.has(f.nombre));
    vacio.hidden = encontradas.length > 0;
    vacio.textContent = t('editorTexto.disparador.ninguna', {
      textoCitado: t('camposAdicionales.nombreCitado', { campo: consulta }),
    });
    for (const grupo of opciones.grupos) {
      const deLaFamilia = grupo.funciones.filter((f) => coinciden.has(f.nombre));
      if (deLaFamilia.length === 0) continue;
      const bloque = document.createElement('div');
      bloque.setAttribute('role', 'group');
      const titulo = document.createElement('div');
      titulo.className = 'selector-variable__tema';
      titulo.id = `${opciones.id}-familia-${grupo.familia}`;
      titulo.textContent = grupo.nombre;
      bloque.setAttribute('aria-labelledby', titulo.id);
      bloque.append(titulo, ...deLaFamilia.map(crearFila));
      lista.append(bloque);
    }
    marcar();
  }

  function mover(paso: 1 | -1): void {
    indice = Math.min(encontradas.length - 1, Math.max(0, indice + paso));
    marcar();
  }

  pintar('');
  // One request for every function; the rows that are on screen get their result when it comes (or never, if it fails).
  const todas = opciones.grupos.flatMap((g) => g.funciones);
  void opciones
    .resultados(todas)
    .then((resultados) => {
      resultados.forEach((resultado, nombre) => respuestas.set(nombre, resultado));
      for (const funcion of todas) {
        const fila = lista.querySelector<HTMLElement>(`#${CSS.escape(idDe(funcion.nombre))}`);
        if (fila) pintarResultado(fila, funcion);
      }
    })
    .catch(() => undefined);
  campo.addEventListener('input', () => pintar(campo.value));
  campo.addEventListener('keydown', (evento) => {
    if (evento.isComposing) return;
    if (evento.key === 'ArrowDown' || evento.key === 'ArrowUp') {
      evento.preventDefault();
      mover(evento.key === 'ArrowDown' ? 1 : -1);
    } else if (evento.key === 'Enter') {
      evento.preventDefault();
      const elegida = encontradas[indice];
      if (elegida) opciones.onElegir(elegida.nombre);
    } else if (evento.key === 'Escape') {
      evento.preventDefault();
      evento.stopPropagation();
      opciones.onCerrar(true);
    }
  });
  // Leaving the search (Tab, a click elsewhere) closes it; a click on a row keeps the focus here.
  raiz.addEventListener('focusout', (evento) => {
    if (!raiz.contains(evento.relatedTarget as Node | null)) opciones.onCerrar(false);
  });
  return { raiz, campo };
}

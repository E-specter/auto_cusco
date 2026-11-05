/**
 * The variable search of the rich-text editor (interface rules §2.2 and §13.2): a listbox of the variables grouped by
 * origin — the module's own first, then the portfolio — each with its visible name, its type and its technical name.
 * Opened from `[@`, the focus never leaves the text run the analyst types in: the run drives it as a combobox
 * (`aria-activedescendant`), so this exposes `filtrar`, `mover` and `activa`. Opened from the button (`conCampo`), it has its
 * own search field, which holds the focus and is the combobox. Built at runtime, so it is a function, not an Astro component.
 */

import { etiquetaVariable } from '../lib/campos';
import { agruparPorTema, ejemploDeVariable, filtrarVariables } from '../lib/editor-texto';
import { t } from '../lib/i18n';
import type { components } from '../lib/contrato-api';

type Esquemas = components['schemas'];
type Variable = Esquemas['VariableRespuesta'];

export interface OpcionesBuscadorVariables {
  /** Prefix for every id inside, so several editors can share a page. */
  id: string;
  variables: readonly Variable[];
  /** The context's example record (`contexto.ejemplo`): each row shows its variable's value. */
  ejemplo: Readonly<Record<string, unknown>>;
  /** What the context does not offer (`clave_alcance`, already translated); a line at the foot. Without it, no line. */
  alcance?: string;
  onElegir: (nombre: string) => void;
  /** With a search field of its own (opened from the button). Without it, the text run drives the list. */
  conCampo?: boolean;
  /** The field's Escape, and leaving it: close the search. Only with `conCampo`. */
  onCerrar?: (porEscape: boolean) => void;
}

export interface BuscadorVariables {
  raiz: HTMLElement;
  /** The search field, with `conCampo`. */
  campo: HTMLInputElement | null;
  /** The id of the listbox, for the run's `aria-controls`. */
  listaId: string;
  /** Shows the variables that match what was typed and highlights the first one. */
  filtrar(consulta: string): void;
  /** Moves the highlight one option, and stops at the ends. */
  mover(paso: 1 | -1): void;
  /** The highlighted variable's name, or `null` when nothing matches. */
  activa(): string | null;
  /** The id of the highlighted option, for the run's `aria-activedescendant`. */
  idActiva(): string | null;
}

/** Visible name of a variable's type: texto, número, fecha, sí/no. */
export function etiquetaTipo(tipo: string): string {
  const clave = `editorTexto.tipo.${tipo}`;
  const texto = t(clave);
  return texto === clave ? tipo : texto;
}

export function crearBuscadorVariables(opciones: OpcionesBuscadorVariables): BuscadorVariables {
  const raiz = document.createElement('div');
  raiz.className = 'panel selector-variable';

  const listaId = `${opciones.id}-lista`;
  const lista = document.createElement('div');
  lista.className = 'selector-variable__lista';
  lista.id = listaId;
  lista.setAttribute('role', 'listbox');
  lista.setAttribute('aria-label', t('editorTexto.variable.elegir'));
  // The field (or the text run) drives the list: the list is not a tab stop, so Tab leaves the search in one step.
  lista.tabIndex = -1;

  const vacio = document.createElement('p');
  vacio.className = 'empty selector-variable__vacio';
  vacio.hidden = true;
  let campo: HTMLInputElement | null = null;
  if (opciones.conCampo) {
    campo = document.createElement('input');
    campo.type = 'search';
    campo.className = 'input selector-variable__buscar';
    campo.autocomplete = 'off';
    campo.placeholder = t('editorTexto.variable.buscarPlaceholder');
    campo.setAttribute('aria-label', t('editorTexto.variable.buscar'));
    campo.setAttribute('role', 'combobox');
    campo.setAttribute('aria-expanded', 'true');
    campo.setAttribute('aria-controls', listaId);
    campo.setAttribute('aria-autocomplete', 'list');
  }
  // The field sits in a padded box so its focus ring (outside the input) stays inside the panel instead of running past its edges.
  const cajaCampo = document.createElement('div');
  cajaCampo.className = 'selector-variable__campo';
  if (campo) cajaCampo.append(campo);
  raiz.append(...(campo ? [cajaCampo] : []), lista, vacio);
  if (opciones.alcance) {
    const alcance = document.createElement('p');
    alcance.className = 'field__hint selector-variable__alcance';
    alcance.textContent = opciones.alcance;
    raiz.append(alcance);
  }

  let encontradas: Variable[] = [];
  let indice = 0;
  const idDe = (nombre: string) => `${opciones.id}-opcion-${nombre}`;
  const opcionesPintadas = () => [...lista.querySelectorAll<HTMLElement>('[role="option"]')];

  function marcar(): void {
    opcionesPintadas().forEach((opcion, i) => {
      opcion.setAttribute('aria-selected', String(i === indice));
      if (i === indice) opcion.scrollIntoView({ block: 'nearest' });
    });
    const activa = encontradas[indice] ? idDe(encontradas[indice].nombre) : null;
    if (activa) campo?.setAttribute('aria-activedescendant', activa);
    else campo?.removeAttribute('aria-activedescendant');
  }

  function crearOpcion(variable: Variable): HTMLElement {
    const opcion = document.createElement('div');
    opcion.className = 'selector-variable__opcion';
    opcion.id = idDe(variable.nombre);
    opcion.setAttribute('role', 'option');
    const nombre = document.createElement('span');
    nombre.className = 'selector-variable__nombre';
    nombre.textContent = etiquetaVariable(variable);
    const tipo = document.createElement('span');
    tipo.className = 'tag tag--neutral';
    tipo.textContent = etiquetaTipo(variable.tipo);
    opcion.append(nombre, tipo);
    if (variable.adicional) {
      const marca = document.createElement('span');
      marca.className = 'tag tag--neutral';
      marca.textContent = t('camposAdicionales.adicional');
      opcion.append(marca);
    }
    // The technical name is not in the row: it is in the tooltip, and the search finds it all the same.
    opcion.title = variable.nombre;
    const valor = ejemploDeVariable(variable.tipo, opciones.ejemplo[variable.nombre], (si) =>
      t(si ? 'editorTexto.ejemplo.si' : 'editorTexto.ejemplo.no'),
    );
    if (valor !== null) {
      const ejemplo = document.createElement('span');
      ejemplo.className = 'mono muted selector-variable__ejemplo';
      ejemplo.textContent = valor;
      opcion.append(ejemplo);
    }
    // The mouse picks without taking the focus away from the text run.
    opcion.addEventListener('mousedown', (evento) => evento.preventDefault());
    opcion.addEventListener('click', () => opciones.onElegir(variable.nombre));
    return opcion;
  }

  function pintar(consulta: string): void {
    encontradas = filtrarVariables(opciones.variables, consulta, etiquetaVariable);
    indice = 0;
    lista.replaceChildren();
    vacio.hidden = encontradas.length > 0;
    vacio.textContent = t('editorTexto.disparador.ninguna', {
      textoCitado: t('camposAdicionales.nombreCitado', { campo: consulta }),
    });
    // Grouped by theme; `encontradas` follows the groups' order so the arrows walk the list as it reads.
    const grupos = agruparPorTema(encontradas);
    encontradas = grupos.flatMap(([, variables]) => variables);
    for (const [tema, variables] of grupos) {
      const grupo = document.createElement('div');
      grupo.setAttribute('role', 'group');
      const nombreGrupo = document.createElement('div');
      nombreGrupo.className = 'selector-variable__tema';
      nombreGrupo.id = `${opciones.id}-tema-${tema}`;
      nombreGrupo.textContent = t(`editorTexto.tema.${tema}`);
      grupo.setAttribute('aria-labelledby', nombreGrupo.id);
      grupo.append(nombreGrupo, ...variables.map(crearOpcion));
      lista.append(grupo);
    }
    marcar();
  }

  function mover(paso: 1 | -1): void {
    indice = Math.min(encontradas.length - 1, Math.max(0, indice + paso));
    marcar();
  }
  const activa = () => encontradas[indice]?.nombre ?? null;

  pintar('');
  if (campo) {
    const buscar = campo;
    buscar.addEventListener('input', () => pintar(buscar.value));
    buscar.addEventListener('keydown', (evento) => {
      if (evento.isComposing) return;
      if (evento.key === 'ArrowDown' || evento.key === 'ArrowUp') {
        evento.preventDefault();
        mover(evento.key === 'ArrowDown' ? 1 : -1);
      } else if (evento.key === 'Enter') {
        evento.preventDefault();
        const nombre = activa();
        if (nombre !== null) opciones.onElegir(nombre);
      } else if (evento.key === 'Escape') {
        evento.preventDefault();
        evento.stopPropagation();
        opciones.onCerrar?.(true);
      }
    });
    // Leaving the search (Tab, a click elsewhere) closes it; a click on an option keeps the focus here.
    raiz.addEventListener('focusout', (evento) => {
      if (!raiz.contains(evento.relatedTarget as Node | null)) opciones.onCerrar?.(false);
    });
  }
  return {
    raiz,
    campo,
    listaId,
    filtrar: pintar,
    mover,
    activa,
    idActiva: () => (encontradas[indice] ? idDe(encontradas[indice].nombre) : null),
  };
}

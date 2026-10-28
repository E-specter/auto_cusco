/**
 * The variable picker of the rich-text editor (interface rules §2.2), also
 * used by the column builder for a direct-variable column (§9.5).
 *
 * A search field and the variables grouped by origin — the module's own
 * first, then the portfolio — each as a button with its visible name, its
 * type and its technical name. Built at runtime, so it is a function, not an
 * Astro component.
 */

import { etiquetaVariable } from '../lib/campos';
import { agruparPorOrigen, filtrarVariables } from '../lib/editor-texto';
import { t } from '../lib/i18n';
import type { components } from '../lib/contrato-api';

type Esquemas = components['schemas'];
type Variable = Esquemas['VariableRespuesta'];
type Contexto = Esquemas['ContextoDisponibleRespuesta'];

export interface OpcionesSelectorVariable {
  /** Prefix for every id inside, so several pickers can share a page. */
  id: string;
  variables: readonly Variable[];
  contextos: readonly Contexto[];
  /** Hides variables that do not fit (for example, a type a parameter rejects). */
  admite?: (variable: Variable) => boolean;
  onElegir: (nombre: string) => void;
  onCerrar: () => void;
}

/** Visible name of a variable's type: texto, número, fecha, sí/no. */
export function etiquetaTipo(tipo: string): string {
  const clave = `editorTexto.tipo.${tipo}`;
  const texto = t(clave);
  return texto === clave ? tipo : texto;
}

function nombreDeOrigen(origen: string, contextos: readonly Contexto[]): string {
  const contexto = contextos.find((c) => c.nombre === origen);
  if (contexto) {
    const texto = t(contexto.clave_nombre);
    if (texto !== contexto.clave_nombre) return texto;
  }
  return origen;
}

export function crearSelectorVariable(opciones: OpcionesSelectorVariable): HTMLElement {
  const disponibles = opciones.variables.filter((v) => opciones.admite?.(v) ?? true);

  const raiz = document.createElement('div');
  raiz.className = 'panel selector-variable';
  raiz.id = `${opciones.id}-selector`;
  raiz.setAttribute('role', 'group');
  raiz.setAttribute('aria-labelledby', `${opciones.id}-selector-titulo`);

  const cabeza = document.createElement('div');
  cabeza.className = 'panel__head';
  const titulo = document.createElement('h3');
  titulo.className = 'panel__title';
  titulo.id = `${opciones.id}-selector-titulo`;
  titulo.textContent = t('editorTexto.variable.elegir');
  cabeza.append(titulo);

  const cuerpo = document.createElement('div');
  cuerpo.className = 'panel__body selector-variable__cuerpo';

  const etiquetaBuscar = document.createElement('label');
  etiquetaBuscar.className = 'visually-hidden';
  etiquetaBuscar.htmlFor = `${opciones.id}-buscar`;
  etiquetaBuscar.textContent = t('editorTexto.variable.buscar');
  const buscar = document.createElement('input');
  buscar.type = 'search';
  buscar.className = 'input selector-variable__buscar';
  buscar.id = `${opciones.id}-buscar`;
  buscar.placeholder = t('editorTexto.variable.buscarPlaceholder');
  buscar.autocomplete = 'off';

  const lista = document.createElement('div');
  lista.className = 'selector-variable__lista';

  const botones = () => [...lista.querySelectorAll<HTMLButtonElement>('button[data-variable]')];

  function pintar(): void {
    const encontradas = filtrarVariables(disponibles, buscar.value, etiquetaVariable);
    lista.replaceChildren();
    if (encontradas.length === 0) {
      const vacio = document.createElement('p');
      vacio.className = 'empty';
      vacio.textContent = t('editorTexto.variable.ninguna');
      lista.append(vacio);
      return;
    }
    for (const [origen, variables] of agruparPorOrigen(encontradas)) {
      const grupo = document.createElement('section');
      grupo.className = 'selector-variable__grupo';
      const nombreGrupo = document.createElement('h4');
      nombreGrupo.className = 'selector-variable__origen';
      nombreGrupo.id = `${opciones.id}-origen-${origen.replace(/[^a-z0-9]+/gi, '-')}`;
      nombreGrupo.textContent = nombreDeOrigen(origen, opciones.contextos);
      const ul = document.createElement('ul');
      ul.setAttribute('aria-labelledby', nombreGrupo.id);
      for (const variable of variables) {
        const li = document.createElement('li');
        const boton = document.createElement('button');
        boton.type = 'button';
        boton.className = 'selector-variable__opcion';
        boton.dataset.variable = variable.nombre;
        const nombre = document.createElement('span');
        nombre.className = 'selector-variable__nombre';
        nombre.textContent = etiquetaVariable(variable);
        const tipo = document.createElement('span');
        tipo.className = 'tag tag--neutral';
        tipo.textContent = etiquetaTipo(variable.tipo);
        const tecnico = document.createElement('span');
        tecnico.className = 'mono muted selector-variable__tecnico';
        tecnico.textContent = variable.nombre;
        boton.append(nombre, tipo);
        if (variable.adicional) {
          const marca = document.createElement('span');
          marca.className = 'tag tag--neutral';
          marca.textContent = t('camposAdicionales.adicional');
          boton.append(marca);
        }
        boton.append(tecnico);
        boton.addEventListener('click', () => opciones.onElegir(variable.nombre));
        li.append(boton);
        ul.append(li);
      }
      grupo.append(nombreGrupo, ul);
      lista.append(grupo);
    }
  }

  buscar.addEventListener('input', pintar);
  buscar.addEventListener('keydown', (evento) => {
    if (evento.key === 'ArrowDown') {
      evento.preventDefault();
      botones()[0]?.focus();
    }
  });
  lista.addEventListener('keydown', (evento) => {
    if (evento.key !== 'ArrowDown' && evento.key !== 'ArrowUp') return;
    const todos = botones();
    const actual = todos.indexOf(document.activeElement as HTMLButtonElement);
    if (actual < 0) return;
    evento.preventDefault();
    if (evento.key === 'ArrowUp' && actual === 0) buscar.focus();
    else todos[Math.min(todos.length - 1, Math.max(0, actual + (evento.key === 'ArrowDown' ? 1 : -1)))]?.focus();
  });
  raiz.addEventListener('keydown', (evento) => {
    if (evento.key === 'Escape') {
      evento.preventDefault();
      evento.stopPropagation();
      opciones.onCerrar();
    }
  });

  cuerpo.append(etiquetaBuscar, buscar, lista);
  raiz.append(cabeza, cuerpo);
  pintar();
  return raiz;
}

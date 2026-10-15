/**
 * Pure helpers of the rich-text editor component: search, grouping, length
 * levels and reading what the analyst typed into a parameter. The component
 * (`scripts/editor-texto.ts`) calls these; the tests call them directly.
 */

import type { Argumento, LlamadaFuncion, TipoValor } from './expresion';

/** Lowercase, without accents: "Días" and "dias" find each other. */
export function normalizarBusqueda(texto: string): string {
  return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
}

type VariableConEtiqueta = { nombre: string; origen: string };

/** Variables whose label or technical name contains every word of `consulta`. */
export function filtrarVariables<V extends VariableConEtiqueta>(
  variables: readonly V[],
  consulta: string,
  etiqueta: (variable: V) => string,
): V[] {
  const palabras = normalizarBusqueda(consulta).split(/\s+/).filter(Boolean);
  if (palabras.length === 0) return [...variables];
  return variables.filter((variable) => {
    const texto = normalizarBusqueda(`${etiqueta(variable)} ${variable.nombre.replace(/_/g, ' ')}`);
    return palabras.every((palabra) => texto.includes(palabra));
  });
}

/**
 * Variables grouped by where they come from. The module's own variables come
 * first: there are few of them, and they are the reason the module uses the
 * engine; the portfolio's long list follows.
 */
export function agruparPorOrigen<V extends VariableConEtiqueta>(variables: readonly V[]): Array<[string, V[]]> {
  const grupos = new Map<string, V[]>();
  for (const variable of variables) {
    grupos.set(variable.origen, [...(grupos.get(variable.origen) ?? []), variable]);
  }
  return [...grupos].sort(([a], [b]) => (a === 'cartera' ? 1 : 0) - (b === 'cartera' ? 1 : 0));
}

export type NivelLargo = 'sin_limite' | 'dentro' | 'cerca' | 'excedido';

/**
 * How a length sits against the module's limit. `largo` is the maximum the
 * text can reach when the backend could bound it, else the sample's length.
 */
export function nivelDeLargo(largo: number, limite: number | null, umbral: number | null): NivelLargo {
  if (limite === null) return 'sin_limite';
  if (largo > limite) return 'excedido';
  if (umbral !== null && largo > umbral) return 'cerca';
  return 'dentro';
}

/**
 * The value to send for what was typed in a parameter field. A number
 * parameter sends a number when the text is one; anything else goes as typed
 * and the backend reports `parametro_invalido` on that exact field. The
 * interface never decides validity on its own.
 */
export function leerArgumento(texto: string, tipo: TipoValor | 'entrada' | null): Argumento {
  const limpio = texto.trim();
  if (tipo === 'numero' && /^-?\d+(\.\d+)?$/.test(limpio)) return Number(limpio);
  return tipo === 'numero' ? limpio : texto;
}

/** What a parameter field shows for a stored argument. */
export function textoArgumento(argumento: Argumento | undefined): string {
  if (argumento === undefined || argumento === null) return '';
  if (typeof argumento === 'object') return '';
  return String(argumento);
}

export function esReferencia(argumento: Argumento | undefined): argumento is { variable: string } {
  return typeof argumento === 'object' && argumento !== null && 'variable' in argumento;
}

/**
 * A short reading of a chain for the piece's pill: "primeros caracteres 8 ·
 * mayúsculas". Arguments that refer to another variable show its name.
 */
export function resumenFunciones(
  funciones: readonly LlamadaFuncion[],
  nombreFuncion: (nombre: string) => string,
  nombreVariable: (nombre: string) => string,
): string {
  return funciones
    .map((funcion) => {
      const args = funcion.args
        .map((a) => (esReferencia(a) ? nombreVariable(a.variable) : textoArgumento(a)))
        .filter(Boolean);
      return [nombreFuncion(funcion.nombre).toLowerCase(), ...args].join(' ');
    })
    .join(' · ');
}

// ---- Arguments of a new function ---------------------------------------------------------

type ParametroCatalogo = {
  obligatorio: boolean;
  por_defecto: unknown;
  opciones?: ReadonlyArray<{ valor: string }>;
};

/**
 * The arguments a function starts with when the analyst adds it: each
 * parameter's default; for a required one without default, its first option
 * (a date pattern starts as dd/mm/aaaa, not empty) or an empty value whose
 * field waits to be filled; and nothing for the optional ones after the last
 * value, so an untouched optional parameter is never sent.
 */
export function argumentosIniciales(parametros: readonly ParametroCatalogo[]): Argumento[] {
  const args: Array<Argumento | undefined> = parametros.map((p) => {
    if (typeof p.por_defecto === 'string' || typeof p.por_defecto === 'number') return p.por_defecto;
    if (!p.obligatorio) return undefined;
    return p.opciones?.[0]?.valor ?? '';
  });
  return recortarArgumentos(args);
}

/**
 * `args` with position `indice` set to `valor`, or cleared when `valor` is
 * `undefined`. Positions left empty before it are filled with '' so the
 * array never has holes; trailing cleared positions are dropped.
 */
export function conArgumento(
  args: readonly Argumento[],
  indice: number,
  valor: Argumento | undefined,
): Argumento[] {
  const nuevos: Array<Argumento | undefined> = [...args];
  while (nuevos.length <= indice) nuevos.push(undefined);
  nuevos[indice] = valor;
  return recortarArgumentos(nuevos);
}

function recortarArgumentos(args: Array<Argumento | undefined>): Argumento[] {
  let fin = args.length;
  while (fin > 0 && args[fin - 1] === undefined) fin -= 1;
  return args.slice(0, fin).map((a) => a ?? '');
}

// ---- Keeping a problem on its piece while the analyst edits ------------------------------

/**
 * Where a problem stays while the analyst keeps typing: a variable by its
 * stable id, a text run by the variable just before it (`null` for the first
 * run). Indices would point at the wrong piece after an insertion; these do
 * not. `null` is the whole expression.
 */
export type Ancla = { tipo: 'variable'; id: string } | { tipo: 'tramo'; despuesDe: string | null } | null;

type PiezaMinima = { tipo: 'texto' } | { tipo: 'variable'; id: string };

export function anclaDe(piezas: readonly PiezaMinima[], indice: number | null): Ancla {
  if (indice === null) return null;
  const pieza = piezas[indice];
  if (!pieza) return null;
  if (pieza.tipo === 'variable') return { tipo: 'variable', id: pieza.id };
  const anterior = piezas[indice - 1];
  return { tipo: 'tramo', despuesDe: anterior?.tipo === 'variable' ? anterior.id : null };
}

/** The piece an anchor points at now, or `null` when it is gone (or is the whole expression). */
export function piezaDeAncla(piezas: readonly PiezaMinima[], ancla: Ancla): number | null {
  if (ancla === null) return null;
  if (ancla.tipo === 'tramo' && ancla.despuesDe === null) return 0;
  const id = ancla.tipo === 'variable' ? ancla.id : ancla.despuesDe;
  const indice = piezas.findIndex((p) => p.tipo === 'variable' && p.id === id);
  if (indice < 0) return null;
  return ancla.tipo === 'variable' ? indice : indice + 1;
}

/** For each variable piece's id, the contract node it becomes (inverse of `nodosAPiezas`). */
export function nodoDePieza(piezas: readonly (PiezaMinima & { valor?: string })[]): Map<string, number> {
  const mapa = new Map<string, number>();
  let nodo = 0;
  for (const pieza of piezas) {
    if (pieza.tipo === 'variable') {
      mapa.set(pieza.id, nodo);
      nodo += 1;
    } else if (pieza.valor !== '') {
      nodo += 1;
    }
  }
  return mapa;
}

// ---- Direct variable (interface rules §5.3) ------------------------------------------------

type NodoMinimo = { tipo: 'texto'; valor: string } | { tipo: 'variable'; nombre: string };

/**
 * A direct-variable column holds one variable and no text, so its value keeps
 * the variable's type. An expression from elsewhere is reduced to its first
 * variable, with that variable's chain; one without variables is empty.
 */
export function aVariableDirecta<N extends NodoMinimo>(expresion: { nodos: readonly N[] } | null | undefined): {
  nodos: N[];
} {
  const variable = expresion?.nodos.find((nodo) => nodo.tipo === 'variable');
  return { nodos: variable ? [variable] : [] };
}

/** The same direct variable under another name, keeping its chain and its required mark. */
export function cambiarVariableDirecta<N extends NodoMinimo>(
  expresion: { nodos: readonly N[] },
  nombre: string,
): { nodos: N[] } {
  const actual = aVariableDirecta(expresion).nodos[0];
  if (!nombre) return { nodos: [] };
  if (actual && actual.tipo === 'variable') return { nodos: [{ ...actual, nombre }] };
  return { nodos: [{ tipo: 'variable', nombre, funciones: [] } as unknown as N] };
}

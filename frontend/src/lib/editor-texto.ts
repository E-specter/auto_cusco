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

/**
 * Variables whose label or technical name contains every word of `consulta`. The header mapper
 * searches its fields with it too (docs/mapeador-encabezados-interfaz.md §3.5).
 */
export function filtrarVariables<V extends { nombre: string }>(
  variables: readonly V[],
  consulta: string,
  etiqueta: (variable: V) => string,
): V[] {
  const palabras = normalizarBusqueda(consulta).split(/\s+/).filter(Boolean);
  if (palabras.length === 0) return [...variables];
  return variables.filter((variable) => {
    // The technical name counts as it is written («fecha_venc») and with spaces («fecha venc»).
    const texto = normalizarBusqueda(`${etiqueta(variable)} ${variable.nombre} ${variable.nombre.replace(/_/g, ' ')}`);
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

// ---- The compact line (interface rules §13.5) ------------------------------------------------

/**
 * How wide, in characters (`ch`), a text run must be to show its text on its own lines: the longest line plus one for the caret,
 * and never under two. It is what a browser without `field-sizing: content` (Firefox) is told, measured by characters and not by
 * UTF-16 units, so an emoji counts as one.
 */
export function anchoDeTramo(valor: string): number {
  return Math.max(2, ...valor.split('\n').map((linea) => [...linea].length + 1));
}

/**
 * Whether a text run, after a pill, stays glued to it instead of taking a row of its own: an empty one (or only blanks) or a
 * single punctuation sign or symbol («.», «,», «)»). Anything with a letter or a number, or longer, flows on its own.
 */
export function tramoPegado(valor: string): boolean {
  return /^\s*[\p{P}\p{S}]?\s*$/u.test(valor);
}

// ---- The `[@` trigger (interface rules §13.2) ------------------------------------------------

/** What the analyst types in a text run to open the variable search at the caret. */
export const DISPARADOR = '[@';

/** Where the trigger starts when the caret sits right after one, else `null`. */
export function disparadorEn(valor: string, cursor: number): number | null {
  return cursor >= DISPARADOR.length && valor.slice(cursor - DISPARADOR.length, cursor) === DISPARADOR
    ? cursor - DISPARADOR.length
    : null;
}

/**
 * What the analyst typed after the trigger to filter the search, or `null` when the search must close: the `@` was erased,
 * the caret went back before it, or the text broke into a new line. `inicio` is where the trigger starts.
 */
export function consultaDelBuscador(valor: string, inicio: number, cursor: number): string | null {
  if (!valor.startsWith(DISPARADOR, inicio) || cursor < inicio + DISPARADOR.length) return null;
  const consulta = valor.slice(inicio + DISPARADOR.length, cursor);
  return consulta.includes('\n') ? null : consulta;
}

// ---- The search by theme (interface rules §13.3) -------------------------------------------

/** The themes the variable search groups by, in the order they show. The backend assigns each variable one (`tema`). */
export const TEMAS = ['archivo', 'persona', 'deuda', 'fechas', 'credito', 'gestion', 'riesgo', 'adicionales', 'otros'] as const;
export type Tema = (typeof TEMAS)[number];

/**
 * The variables grouped by theme, in the order of `TEMAS`; inside a theme, in the order they came. A theme with no variable
 * is left out, and so is one a search emptied. A variable whose theme this does not know goes to «otros», so none is lost.
 */
export function agruparPorTema<V extends { tema: string }>(variables: readonly V[]): Array<[Tema, V[]]> {
  const conocido = (tema: string): Tema => (TEMAS as readonly string[]).includes(tema) ? (tema as Tema) : 'otros';
  return TEMAS.map((tema): [Tema, V[]] => [tema, variables.filter((v) => conocido(v.tema) === tema)]).filter(
    ([, lista]) => lista.length > 0,
  );
}

/**
 * How a variable's example value reads in its row, or `null` when the context has none for it. A date shows as dd/mm/aaaa and
 * a yes/no as the word; anything else as it is. The backend's preview is what really evaluates: this only reads the value.
 */
export function ejemploDeVariable(tipo: string, valor: unknown, siNo: (si: boolean) => string): string | null {
  if (valor === undefined || valor === null || valor === '') return null;
  if (typeof valor === 'boolean') return siNo(valor);
  const fecha = tipo === 'fecha' && typeof valor === 'string' ? /^(\d{4})-(\d{2})-(\d{2})/.exec(valor) : null;
  return fecha ? `${fecha[3]}/${fecha[2]}/${fecha[1]}` : String(valor);
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

/**
 * What a parameter's error says when the analyst typed something it refuses (interface rules §13.4): the range it accepts,
 * from the catalogue, or that a required text is missing. `null` when the catalogue gives nothing more specific, and the
 * generic message stays as a fallback. The values go in the `valores` of the text; `parametro` is added by the caller.
 */
export function errorDeParametro(
  parametro: { tipo: string; obligatorio: boolean; minimo: number | null; maximo: number | null },
  argumento: Argumento | undefined,
): { clave: string; valores: { min?: number; max?: number } } | null {
  if (esReferencia(argumento)) return null;
  const { minimo, maximo } = parametro;
  if (parametro.tipo === 'numero') {
    if (minimo !== null && maximo !== null) return { clave: 'editorTexto.parametro.rango', valores: { min: minimo, max: maximo } };
    if (minimo !== null) return { clave: 'editorTexto.parametro.minimo', valores: { min: minimo } };
    if (maximo !== null) return { clave: 'editorTexto.parametro.maximo', valores: { max: maximo } };
    return null;
  }
  if (parametro.tipo === 'texto' && parametro.obligatorio && (argumento === undefined || argumento === '')) {
    return { clave: 'editorTexto.parametro.vacio', valores: {} };
  }
  return null;
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

/**
 * Draft of a column definition (docs/motor-texto-enriquecido-interfaz.md §5).
 *
 * A definition is an ordered list of columns, each with its content as an
 * expression of the rich-text engine, a type, a format and an optional default
 * value, plus a segmentation and the CSV formula protection. The screen edits
 * a *draft*: the saved definition plus what the editor needs for itself (a
 * stable id per column, for focus and DOM identity). Nothing the editor adds
 * reaches the backend: `aDefinicion` strips it.
 *
 * Everything here is pure: no DOM, no fetch. The screen calls these and
 * renders the result; the tests call them directly. It does not validate
 * business rules: the backend does, and its 400 decides. The one local hint is
 * a repeated column name (`nombresRepetidos`), so the screen does not offer a
 * save that cannot work.
 *
 * Variants per segment are carried, never edited: whoever owns the variants
 * selector (`VariantesSegmento`) hands the new list to `fijarVariantes`.
 *
 * PROVISIONAL: the shapes follow `entities/mapeo.py` and
 * `entities/segmentacion.py` and the contract answers of the coordinator
 * (explicit `orden`, marks such as `dd/mm/aaaa` for dates, expressions only).
 * When B4b fixes the contract they become aliases of the generated types and
 * the functions below stay as they are.
 */

import type { components } from './contrato-api';
import type { Expresion } from './expresion';

export type { Expresion } from './expresion';

// ---- Contract shapes (provisional until B4b) ------------------------------------------

// These are `type`s, not `interface`s, on purpose: the backend's input models accept extra keys, so
// the generated types carry an index signature (`[key: string]: unknown`), and TypeScript lets a
// type alias, but not an interface, be assigned to one.

export type TipoSalida = 'texto' | 'numero' | 'fecha' | 'financiero';

export type FormatoFinanciero = {
  separador_miles: string;
  separador_decimal: string;
  decimales: number;
}

/** The content of a column for one segment; the column's own content is the default. */
export type VarianteColumna = {
  /** A range key of the table (calculated criterion) or a field value (field criterion). */
  segmento: string;
  expresion: Expresion;
}

export type ColumnaGuardada = {
  /** Explicit position, from 0. */
  orden: number;
  nombre: string;
  tipo: TipoSalida;
  /** Marks such as `dd/mm/aaaa`; only meaningful for a `fecha` column. */
  formato_fecha: string | null;
  formato_financiero: FormatoFinanciero;
  expresion: Expresion;
  valor_por_defecto: string | null;
  variantes: VarianteColumna[];
}

/** The row of a segment table, as the catalogue and the saved definitions give it. */
export type RangoDias = components['schemas']['RangoRespuesta'];

export type Criterio =
  | { tipo: 'calculado'; tabla: RangoDias[]; variable_dias: string }
  | { tipo: 'campo'; campo: string };

export type PoliticaSinSegmento = 'excluir' | 'usar_por_defecto';

export type Segmentacion = {
  criterio: Criterio;
  politica: PoliticaSinSegmento;
}

export type DefinicionGuardada = {
  nombre: string;
  columnas: ColumnaGuardada[];
  segmentacion: Segmentacion | null;
  proteger_formulas: boolean;
}

// ---- The draft ------------------------------------------------------------------------------

export type Columna = Omit<ColumnaGuardada, 'orden'> & {
  /** Stable key for focus and DOM identity; never sent to the backend. */
  id: string;
}

export type Borrador = {
  nombre: string;
  columnas: Columna[];
  segmentacion: Segmentacion | null;
  proteger_formulas: boolean;
}

export const FORMATO_FINANCIERO_POR_DEFECTO: Readonly<FormatoFinanciero> = {
  separador_miles: ',',
  separador_decimal: '.',
  decimales: 2,
};

let siguienteId = 0;
const nuevoId = (): string => `columna-${(siguienteId += 1)}`;

const copia = <T>(valor: T): T => structuredClone(valor);

function columnaVacia(nombre = ''): Columna {
  return {
    id: nuevoId(),
    nombre,
    tipo: 'texto',
    formato_fecha: null,
    formato_financiero: { ...FORMATO_FINANCIERO_POR_DEFECTO },
    expresion: { nodos: [] },
    valor_por_defecto: null,
    variantes: [],
  };
}

/** A new definition: one empty column and the formula protection on (RF-53). */
export function definicionNueva(): Borrador {
  return { nombre: '', columnas: [columnaVacia()], segmentacion: null, proteger_formulas: true };
}

/** Saved definition → draft. The result shares nothing with its input. */
export function desdeDefinicion(definicion: DefinicionGuardada): Borrador {
  const ordenadas = [...definicion.columnas].sort((a, b) => a.orden - b.orden);
  return {
    nombre: definicion.nombre,
    segmentacion: copia(definicion.segmentacion),
    proteger_formulas: definicion.proteger_formulas,
    columnas: ordenadas.map(({ orden: _orden, ...resto }) => ({ id: nuevoId(), ...copia(resto) })),
  };
}

/** Draft → what the backend receives: no ids, `orden` as the position. Shares nothing. */
export function aDefinicion(borrador: Borrador): DefinicionGuardada {
  return {
    nombre: borrador.nombre,
    segmentacion: copia(borrador.segmentacion),
    proteger_formulas: borrador.proteger_formulas,
    columnas: borrador.columnas.map(({ id: _id, ...resto }, orden) => ({ orden, ...copia(resto) })),
  };
}

// ---- Names ---------------------------------------------------------------------------------------

/** Name as compared for repetition: no accents, no case, no edge spaces. */
export function normalizarNombre(nombre: string): string {
  return nombre
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .trim()
    .toLowerCase();
}

/** Ids of the columns whose name another column shares. Empty names do not count. */
export function nombresRepetidos(borrador: Borrador): Set<string> {
  const porNombre = new Map<string, string[]>();
  for (const columna of borrador.columnas) {
    const clave = normalizarNombre(columna.nombre);
    if (clave === '') continue;
    porNombre.set(clave, [...(porNombre.get(clave) ?? []), columna.id]);
  }
  return new Set([...porNombre.values()].filter((ids) => ids.length > 1).flat());
}

/** `base (etiqueta)`, then `base (etiqueta 2)`, … the first one nobody has. */
function nombreDeCopia(base: string, etiqueta: string, ocupados: Set<string>): string {
  if (normalizarNombre(base) === '') return base;
  let candidato = `${base} (${etiqueta})`;
  for (let n = 2; ocupados.has(normalizarNombre(candidato)); n += 1) candidato = `${base} (${etiqueta} ${n})`;
  return candidato;
}

// ---- Columns ----------------------------------------------------------------------------------------

const indiceDe = (borrador: Borrador, id: string): number => borrador.columnas.findIndex((c) => c.id === id);

function conColumna(borrador: Borrador, id: string, cambio: (columna: Columna) => Columna): Borrador {
  const indice = indiceDe(borrador, id);
  if (indice < 0) return borrador;
  return { ...borrador, columnas: borrador.columnas.map((c, i) => (i === indice ? cambio(c) : c)) };
}

function insertarDespues(
  borrador: Borrador,
  despuesDe: string | null,
  columna: Columna,
): Borrador {
  const indice = despuesDe === null ? -1 : indiceDe(borrador, despuesDe);
  const posicion = indice < 0 ? borrador.columnas.length : indice + 1;
  const columnas = [...borrador.columnas.slice(0, posicion), columna, ...borrador.columnas.slice(posicion)];
  return { ...borrador, columnas };
}

/** An empty column after `despuesDe`, or at the end. Returns its id so the screen opens it. */
export function agregarColumna(borrador: Borrador, despuesDe: string | null = null): { borrador: Borrador; id: string } {
  const columna = columnaVacia();
  return { borrador: insertarDespues(borrador, despuesDe, columna), id: columna.id };
}

/** Removes a column. `foco` is where focus belongs afterwards: the next one, else the previous. */
export function quitarColumna(borrador: Borrador, id: string): { borrador: Borrador; foco: string | null } {
  const indice = indiceDe(borrador, id);
  if (indice < 0) return { borrador, foco: null };
  const columnas = borrador.columnas.filter((_, i) => i !== indice);
  const foco = columnas[indice]?.id ?? columnas[indice - 1]?.id ?? null;
  return { borrador: { ...borrador, columnas }, foco };
}

/** One step up (-1) or down (+1); at an end, or for an unknown id, the same draft. */
export function moverColumna(borrador: Borrador, id: string, paso: -1 | 1): Borrador {
  const indice = indiceDe(borrador, id);
  const destino = indice + paso;
  if (indice < 0 || destino < 0 || destino >= borrador.columnas.length) return borrador;
  const columnas = [...borrador.columnas];
  [columnas[indice], columnas[destino]] = [columnas[destino], columnas[indice]];
  return { ...borrador, columnas };
}

/**
 * A copy right after the original, with a new id and a name nobody has.
 * `etiqueta` is the word for "copy" in the screen's language.
 */
export function duplicarColumna(
  borrador: Borrador,
  id: string,
  etiqueta = 'copia',
): { borrador: Borrador; id: string | null } {
  const original = borrador.columnas.find((c) => c.id === id);
  if (!original) return { borrador, id: null };
  const ocupados = new Set(borrador.columnas.map((c) => normalizarNombre(c.nombre)));
  const duplicada: Columna = { ...copia(original), id: nuevoId(), nombre: nombreDeCopia(original.nombre, etiqueta, ocupados) };
  return { borrador: insertarDespues(borrador, id, duplicada), id: duplicada.id };
}

/** The analyst's text is kept as typed, edge spaces included: the backend decides what is valid. */
export const renombrarColumna = (borrador: Borrador, id: string, nombre: string): Borrador =>
  conColumna(borrador, id, (c) => ({ ...c, nombre }));

export const fijarExpresion = (borrador: Borrador, id: string, expresion: Expresion): Borrador =>
  conColumna(borrador, id, (c) => ({ ...c, expresion: copia(expresion) }));

/** Carries the variants the selector produced; the column's own content stays the default. */
export const fijarVariantes = (borrador: Borrador, id: string, variantes: VarianteColumna[]): Borrador =>
  conColumna(borrador, id, (c) => ({ ...c, variantes: copia(variantes) }));

/** A format that does not apply to the new type is dropped, so it never travels. */
export const cambiarTipo = (borrador: Borrador, id: string, tipo: TipoSalida): Borrador =>
  conColumna(borrador, id, (c) => ({
    ...c,
    tipo,
    formato_fecha: tipo === 'fecha' ? c.formato_fecha : null,
    formato_financiero: tipo === 'financiero' ? c.formato_financiero : { ...FORMATO_FINANCIERO_POR_DEFECTO },
  }));

export const fijarFormatoFecha = (borrador: Borrador, id: string, formato: string | null): Borrador =>
  conColumna(borrador, id, (c) => ({ ...c, formato_fecha: formato }));

export const fijarFormatoFinanciero = (
  borrador: Borrador,
  id: string,
  parcial: Partial<FormatoFinanciero>,
): Borrador => conColumna(borrador, id, (c) => ({ ...c, formato_financiero: { ...c.formato_financiero, ...parcial } }));

/** An empty value means "none", not an empty text (RF-45). */
export const fijarValorPorDefecto = (borrador: Borrador, id: string, valor: string): Borrador =>
  conColumna(borrador, id, (c) => ({ ...c, valor_por_defecto: valor === '' ? null : valor }));

// ---- The definition ------------------------------------------------------------------------------

export const renombrarDefinicion = (borrador: Borrador, nombre: string): Borrador => ({ ...borrador, nombre });

export const fijarProteccion = (borrador: Borrador, proteger: boolean): Borrador => ({
  ...borrador,
  proteger_formulas: proteger,
});

export const fijarSegmentacion = (borrador: Borrador, segmentacion: Segmentacion | null): Borrador => ({
  ...borrador,
  segmentacion: copia(segmentacion),
});

// ---- Reading a column ------------------------------------------------------------------------------

/**
 * How the column's content is edited: a single variable node (with or without
 * functions) is a direct variable, which keeps its type (RF-49); anything else
 * is composed text.
 */
export function modoContenido(expresion: Expresion): 'vacio' | 'variable' | 'texto' {
  if (expresion.nodos.length === 0) return 'vacio';
  return expresion.nodos.length === 1 && expresion.nodos[0].tipo === 'variable' ? 'variable' : 'texto';
}

// ---- Unsaved changes ----------------------------------------------------------------------------------

function iguales(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (typeof a !== 'object' || typeof b !== 'object' || a === null || b === null) return false;
  if (Array.isArray(a) !== Array.isArray(b)) return false;
  const clavesA = Object.keys(a);
  if (clavesA.length !== Object.keys(b).length) return false;
  return clavesA.every((clave) => iguales((a as Record<string, unknown>)[clave], (b as Record<string, unknown>)[clave]));
}

/**
 * The same definition with what is not a real difference made equal: the marks the backend always
 * sends and the editor omits ("required: false" and no mark), and the order of the variants.
 */
function comparable(definicion: DefinicionGuardada): DefinicionGuardada {
  const expresion = (e: Expresion): Expresion => ({
    nodos: e.nodos.map((n) => (n.tipo === 'variable' ? { ...n, obligatoria: Boolean(n.obligatoria) } : n)),
  });
  return {
    ...definicion,
    columnas: definicion.columnas.map((c) => ({
      ...c,
      expresion: expresion(c.expresion),
      // A segment's variant is identified by its segment, not by where it sits in the list: the
      // selector appends a variant that is set again, and the backend does not care about the order.
      variantes: [...c.variantes]
        .sort((x, y) => x.segmento.localeCompare(y.segmento))
        .map((v) => ({ ...v, expresion: expresion(v.expresion) })),
    })),
  };
}

/**
 * Whether the draft differs from the saved definition. Compared as the backend
 * would receive them, exactly: the edge spaces of a name are a change.
 */
export function hayCambios(guardada: DefinicionGuardada, borrador: Borrador): boolean {
  return !iguales(comparable(aDefinicion(desdeDefinicion(guardada))), comparable(aDefinicion(borrador)));
}

// ---- Saved definitions (B4b) -----------------------------------------------------------------------

export type DefinicionRespuesta = components['schemas']['DefinicionRespuesta'];

/**
 * What `GET /definiciones-columnas/{id}` answers → the saved definition the draft starts from. The
 * generated response types are closed unions (text | variable node, calculated | field criterion),
 * so this reads them with no casts: if the contract moves, it stops compiling here. The name lives
 * outside the version's content, so it joins it here.
 */
export function guardadaDesdeRespuesta(respuesta: DefinicionRespuesta): DefinicionGuardada {
  const { proteger_formulas, segmentacion, columnas } = respuesta.version.contenido;
  return copia({ nombre: respuesta.nombre, proteger_formulas, segmentacion, columnas });
}

/**
 * What saving does and what the header shows (docs/motor-texto-enriquecido-interfaz.md §5.1). No
 * version is ever modified: every save creates the one after the *latest*, even when the analyst
 * is looking at an older one. The name is typed when the definition is created and read-only after.
 * `null` is a definition that has not been saved yet.
 */
export function versionAlGuardar(respuesta: DefinicionRespuesta | null): {
  nueva: number;
  mostrada: number | null;
  usada: boolean;
  nombreEditable: boolean;
} {
  if (respuesta === null) return { nueva: 1, mostrada: null, usada: false, nombreEditable: true };
  return {
    nueva: respuesta.version_vigente + 1,
    mostrada: respuesta.version.numero,
    usada: respuesta.version.usada,
    nombreEditable: false,
  };
}

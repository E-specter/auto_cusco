/**
 * Editor state for a rich-text expression (docs/motor-texto-enriquecido.md
 * §4.1, rules in docs/motor-texto-enriquecido-interfaz.md §2).
 *
 * The backend owns the expression: an array of nodes, either literal text or
 * a variable with a chain of functions. The editor shows it as a sentence of
 * pieces — text runs the user types in, variables as pills — so it keeps one
 * invariant the backend does not need: pieces alternate text / variable and
 * always start and end with a text run, possibly empty. That is what lets the
 * analyst type before, between and after any variable.
 *
 * Everything here is pure: no DOM, no fetch. The component calls these and
 * renders the result; the tests call them directly.
 *
 * The shapes below are the minimum the editor reads, not copies of the
 * contract: the generated response types (`ExpresionGuardadaRespuesta`,
 * `VariableRespuesta`, `FuncionRespuesta`, `ProblemaTextoRespuesta`) are
 * assignable to them, and what the editor builds is assignable to the request
 * models. `tests/tipos/contrato-expresion.ts` pins both directions, so the
 * contract and these shapes cannot drift apart without `npm run tipos` failing.
 */

import type { components } from './contrato-api';

// ---- Contract shapes ------------------------------------------------------------------
//
// Shapes that travel to the backend are `type` aliases, never `interface`s:
// the generated request models accept extra keys (an index signature), and
// TypeScript lets an object type alias be assigned to one but not an
// interface. An `interface` here would stop `aExpresion(...)` from being sent.

type Esquemas = components['schemas'];

export type TipoValor = Esquemas['VariableRespuesta']['tipo'];

/** A function argument: a literal, or a reference to another variable. */
export type Argumento = string | number | { variable: string };

export type LlamadaFuncion = {
  nombre: string;
  args: Argumento[];
};

export type Nodo =
  | { tipo: 'texto'; valor: string }
  | { tipo: 'variable'; nombre: string; funciones: LlamadaFuncion[]; obligatoria?: boolean };

export type Expresion = {
  nodos: Nodo[];
};

/** What type checking needs from a catalogue variable (`VariableRespuesta`). */
export type VariableCatalogo = Pick<Esquemas['VariableRespuesta'], 'nombre' | 'tipo'>;

/**
 * What type checking needs from a catalogue function (`FuncionRespuesta`).
 * `devuelve: 'entrada'` means "the same type it received" (`si_vacio`).
 */
export type FuncionCatalogo = Pick<Esquemas['FuncionRespuesta'], 'nombre' | 'recibe' | 'devuelve'>;

export type Catalogo<F extends FuncionCatalogo = FuncionCatalogo> = {
  variables: VariableCatalogo[];
  funciones: F[];
};

/** The editor's view of `GET /texto-enriquecido/catalogo`. */
export function catalogoDe(
  respuesta: Esquemas['CatalogoRespuesta'],
): Catalogo<Esquemas['FuncionRespuesta']> {
  return { variables: respuesta.contexto.variables, funciones: respuesta.funciones };
}

/**
 * Where the backend says a problem is. Indices count the nodes the backend
 * received, not the editor's pieces: `aExpresion` drops empty runs, so the two
 * differ, and `ubicarProblemas` translates. `null` means the whole expression.
 */
export type Ubicacion = {
  nodo: number;
  funcion?: number | null;
  parametro?: string | null;
};

export type Problema = {
  codigo: string;
  detalle: string;
  ubicacion: Ubicacion | null;
};

// ---- Editor pieces ----------------------------------------------------------------------

export interface TramoTexto {
  tipo: 'texto';
  valor: string;
}

export interface PiezaVariable {
  tipo: 'variable';
  /** Stable key for focus and DOM identity; never sent to the backend. */
  id: string;
  nombre: string;
  funciones: LlamadaFuncion[];
  obligatoria: boolean;
}

export type Pieza = TramoTexto | PiezaVariable;

let siguienteId = 0;
const nuevoId = (): string => `pieza-${(siguienteId += 1)}`;

const tramo = (valor = ''): TramoTexto => ({ tipo: 'texto', valor });

/**
 * Restore the invariant: text runs at both ends, never two runs in a row
 * (merged), never two variables in a row (an empty run between them).
 */
export function normalizar(piezas: Pieza[]): Pieza[] {
  const salida: Pieza[] = [];
  for (const pieza of piezas) {
    const ultima = salida.at(-1);
    if (pieza.tipo === 'texto') {
      if (ultima?.tipo === 'texto') {
        salida[salida.length - 1] = tramo(ultima.valor + pieza.valor);
      } else {
        salida.push(tramo(pieza.valor));
      }
    } else {
      if (!ultima || ultima.tipo === 'variable') salida.push(tramo());
      salida.push(pieza);
    }
  }
  if (salida.at(-1)?.tipo !== 'texto') salida.push(tramo());
  return salida;
}

/** Contract nodes → editor pieces. */
export function desdeExpresion(expresion: Expresion | null | undefined): Pieza[] {
  const piezas: Pieza[] = (expresion?.nodos ?? []).map((nodo) =>
    nodo.tipo === 'texto'
      ? tramo(nodo.valor)
      : {
          tipo: 'variable',
          id: nuevoId(),
          nombre: nodo.nombre,
          funciones: nodo.funciones.map((f) => ({ nombre: f.nombre, args: [...f.args] })),
          obligatoria: Boolean(nodo.obligatoria),
        },
  );
  return normalizar(piezas);
}

/** Editor pieces → contract nodes. Empty runs are the editor's, not data. */
export function aExpresion(piezas: Pieza[]): Expresion {
  const nodos: Nodo[] = [];
  for (const pieza of piezas) {
    if (pieza.tipo === 'texto') {
      if (pieza.valor !== '') nodos.push({ tipo: 'texto', valor: pieza.valor });
    } else {
      nodos.push({
        tipo: 'variable',
        nombre: pieza.nombre,
        funciones: pieza.funciones.map((f) => ({ nombre: f.nombre, args: [...f.args] })),
        ...(pieza.obligatoria ? { obligatoria: true } : {}),
      });
    }
  }
  return { nodos };
}

/** For each contract node index, the editor piece it came from. */
export function nodosAPiezas(piezas: Pieza[]): number[] {
  const mapa: number[] = [];
  piezas.forEach((pieza, indice) => {
    if (pieza.tipo === 'variable' || pieza.valor !== '') mapa.push(indice);
  });
  return mapa;
}

// ---- Editing -------------------------------------------------------------------------------

/**
 * Insert a variable at the caret of a text run, splitting the run in two.
 * Returns the new pieces and the index of the inserted variable, which the
 * component opens and focuses.
 */
export function insertarVariable(
  piezas: Pieza[],
  indiceTramo: number,
  cursor: number,
  nombre: string,
): { piezas: Pieza[]; indiceVariable: number } {
  const destino = piezas[indiceTramo];
  // No run had focus, or the index is stale: append at the end.
  const indice = destino?.tipo === 'texto' ? indiceTramo : piezas.length - 1;
  const actual = piezas[indice] as TramoTexto;
  const corte = Math.max(0, Math.min(cursor, actual.valor.length));

  const variable: PiezaVariable = { tipo: 'variable', id: nuevoId(), nombre, funciones: [], obligatoria: false };
  const nuevas = [
    ...piezas.slice(0, indice),
    tramo(actual.valor.slice(0, corte)),
    variable,
    tramo(actual.valor.slice(corte)),
    ...piezas.slice(indice + 1),
  ];
  return { piezas: nuevas, indiceVariable: indice + 1 };
}

/**
 * Remove a variable and merge its neighbouring runs. Returns where the caret
 * belongs afterwards: the merged run, at the join point.
 */
export function quitarVariable(
  piezas: Pieza[],
  indiceVariable: number,
): { piezas: Pieza[]; indiceTramo: number; cursor: number } {
  const antes = piezas[indiceVariable - 1];
  const despues = piezas[indiceVariable + 1];
  if (piezas[indiceVariable]?.tipo !== 'variable' || antes?.tipo !== 'texto' || despues?.tipo !== 'texto') {
    return { piezas, indiceTramo: Math.max(0, indiceVariable - 1), cursor: 0 };
  }
  const nuevas = [
    ...piezas.slice(0, indiceVariable - 1),
    tramo(antes.valor + despues.valor),
    ...piezas.slice(indiceVariable + 2),
  ];
  return { piezas: nuevas, indiceTramo: indiceVariable - 1, cursor: antes.valor.length };
}

export function editarTramo(piezas: Pieza[], indice: number, valor: string): Pieza[] {
  if (piezas[indice]?.tipo !== 'texto') return piezas;
  return piezas.map((p, i) => (i === indice ? tramo(valor) : p));
}

function conVariable(
  piezas: Pieza[],
  indice: number,
  cambio: (variable: PiezaVariable) => PiezaVariable,
): Pieza[] {
  const pieza = piezas[indice];
  if (pieza?.tipo !== 'variable') return piezas;
  return piezas.map((p, i) => (i === indice ? cambio(pieza) : p));
}

export function agregarFuncion(piezas: Pieza[], indiceVariable: number, funcion: LlamadaFuncion): Pieza[] {
  return conVariable(piezas, indiceVariable, (v) => ({
    ...v,
    funciones: [...v.funciones, { nombre: funcion.nombre, args: [...funcion.args] }],
  }));
}

export function quitarFuncion(piezas: Pieza[], indiceVariable: number, indiceFuncion: number): Pieza[] {
  return conVariable(piezas, indiceVariable, (v) => ({
    ...v,
    funciones: v.funciones.filter((_, i) => i !== indiceFuncion),
  }));
}

/** Move a function one step up (-1) or down (+1); out of range is a no-op. */
export function moverFuncion(
  piezas: Pieza[],
  indiceVariable: number,
  indiceFuncion: number,
  paso: -1 | 1,
): Pieza[] {
  return conVariable(piezas, indiceVariable, (v) => {
    const destino = indiceFuncion + paso;
    if (destino < 0 || destino >= v.funciones.length) return v;
    const funciones = [...v.funciones];
    [funciones[indiceFuncion], funciones[destino]] = [funciones[destino], funciones[indiceFuncion]];
    return { ...v, funciones };
  });
}

export function cambiarArgumento(
  piezas: Pieza[],
  indiceVariable: number,
  indiceFuncion: number,
  indiceArgumento: number,
  valor: Argumento,
): Pieza[] {
  return conVariable(piezas, indiceVariable, (v) => ({
    ...v,
    funciones: v.funciones.map((f, i) => {
      if (i !== indiceFuncion) return f;
      const args = [...f.args];
      args[indiceArgumento] = valor;
      return { ...f, args };
    }),
  }));
}

export function marcarObligatoria(piezas: Pieza[], indiceVariable: number, obligatoria: boolean): Pieza[] {
  return conVariable(piezas, indiceVariable, (v) => ({ ...v, obligatoria }));
}

// ---- Types along a chain ---------------------------------------------------------------------

/**
 * The type that reaches position `hasta` of a variable's chain (the input of
 * the function there, or the output of the whole chain when `hasta` is the
 * chain length). `null` when a function in between is unknown or does not
 * accept what it receives: the backend reports that; the editor just stops
 * offering functions after it.
 */
export function tipoEnPosicion(
  catalogo: Catalogo,
  variable: Pick<PiezaVariable, 'nombre' | 'funciones'>,
  hasta = variable.funciones.length,
): TipoValor | null {
  let tipo: TipoValor | null = catalogo.variables.find((v) => v.nombre === variable.nombre)?.tipo ?? null;
  for (const llamada of variable.funciones.slice(0, hasta)) {
    if (tipo === null) return null;
    const funcion = catalogo.funciones.find((f) => f.nombre === llamada.nombre);
    if (!funcion || !funcion.recibe.includes(tipo)) return null;
    tipo = funcion.devuelve === 'entrada' ? tipo : funcion.devuelve;
  }
  return tipo;
}

/** Functions that accept `tipo`, the only ones `+ Agregar función` offers. */
export function funcionesCompatibles<F extends FuncionCatalogo>(
  catalogo: Catalogo<F>,
  tipo: TipoValor | null,
): F[] {
  if (tipo === null) return [];
  return catalogo.funciones.filter((f) => f.recibe.includes(tipo));
}

// ---- Problems from the backend ------------------------------------------------------------------

export type ProblemaUbicado = Problema & {
  /** The editor piece, or `null` for a problem of the whole expression. */
  pieza: number | null;
};

/**
 * Translate each problem's node index into the editor piece it points at.
 * A problem whose node no longer exists (the analyst kept editing) is kept
 * for the whole expression rather than pinned to the wrong piece.
 */
export function ubicarProblemas(problemas: Problema[], piezas: Pieza[]): ProblemaUbicado[] {
  const mapa = nodosAPiezas(piezas);
  return problemas.map((problema) => {
    const pieza = problema.ubicacion ? (mapa[problema.ubicacion.nodo] ?? null) : null;
    return { ...problema, pieza };
  });
}

// ---- Accessible names -------------------------------------------------------------------------

/**
 * Where a text run sits, for its accessible name ("Texto después de Titular"):
 * position words come from i18n, so this only says which case applies.
 */
export function posicionTramo(
  piezas: Pieza[],
  indice: number,
): { caso: 'unico' | 'inicio' | 'despues' | 'final'; variable?: string } {
  const hayVariables = piezas.some((p) => p.tipo === 'variable');
  if (!hayVariables) return { caso: 'unico' };
  if (indice === 0) return { caso: 'inicio' };
  if (indice === piezas.length - 1) return { caso: 'final' };
  const anterior = piezas[indice - 1];
  return { caso: 'despues', variable: anterior?.tipo === 'variable' ? anterior.nombre : undefined };
}

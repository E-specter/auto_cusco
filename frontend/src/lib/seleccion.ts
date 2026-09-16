/**
 * A portfolio selection as the interface edits it: filters, order, the n of
 * the top n and the analyst's own indicators (RF-04, RF-05, RF-08, RF-27).
 *
 * The API speaks one text syntax for all of it (docs/consulta-cartera.md §3,
 * backend `seleccion_cartera/expresiones.py`):
 *
 *     filter:     field:operator:value   (several values joined with `|`)
 *     order:      field, or -field for descending
 *     indicator:  name:function:field    (`conteo` may omit the field)
 *
 * The editor works on structured drafts and only writes that syntax at the
 * edge, so a half-typed filter never reaches the API: an incomplete part is
 * held back and marked, instead of coming back as a 400.
 *
 * Pure on purpose: the upload console, this screen and the MOWA MES campaign
 * all read selections, and none of this needs a document to be tested.
 */

import type { Campos, Problema, SeleccionGuardada } from './api';

export type TipoCampo = 'texto' | 'numero' | 'fecha' | 'booleano';
export type Funcion = 'suma' | 'conteo' | 'promedio' | 'minimo' | 'maximo';

export const SEPARADOR_VALORES = '|';
/** The API's ceiling for the top n (`CANTIDAD_MAXIMA` in the backend). */
export const CANTIDAD_MAXIMA = 120_000;

/** Reading order for the operator menu: equality, sets, text, ranges, emptiness. */
const ORDEN_OPERADORES = [
  'igual',
  'distinto',
  'en',
  'contiene',
  'empieza_con',
  'mayor',
  'mayor_igual',
  'menor',
  'menor_igual',
  'entre',
  'vacio',
  'no_vacio',
];

export const FUNCIONES: Funcion[] = ['conteo', 'suma', 'promedio', 'minimo', 'maximo'];
const FUNCIONES_NUMERICAS: ReadonlySet<Funcion> = new Set(['suma', 'promedio']);

export interface FiltroBorrador {
  campo: string;
  operador: string;
  valores: string[];
}

export interface OrdenBorrador {
  campo: string;
  descendente: boolean;
}

export interface IndicadorBorrador {
  nombre: string;
  funcion: Funcion;
  campo: string | null;
}

export interface SeleccionBorrador {
  filtros: FiltroBorrador[];
  orden: OrdenBorrador | null;
  cantidad: number | null;
  indicadores: IndicadorBorrador[];
}

/** What the API receives: only complete parts, already written as text. */
export interface Consulta {
  filtros: string[];
  orden: string | null;
  cantidad: number | null;
  indicadores: string[];
}

export function seleccionVacia(): SeleccionBorrador {
  return { filtros: [], orden: null, cantidad: null, indicadores: [] };
}

// ---- Catalogue ---------------------------------------------------------------

/**
 * How many values an operator takes: 0, a fixed count, or `null` for one or
 * more (`en`). Mirrors `VALORES_POR_OPERADOR` in the backend.
 */
export function valoresQuePide(operador: string): number | null {
  if (operador === 'vacio' || operador === 'no_vacio') return 0;
  if (operador === 'entre') return 2;
  if (operador === 'en') return null;
  return 1;
}

/** The field's operators, as the API lists them, in reading order. */
export function operadoresPara(campos: Campos, campo: string): string[] {
  const disponibles = campos[campo]?.operadores ?? [];
  const conocidos = ORDEN_OPERADORES.filter((operador) => disponibles.includes(operador));
  const otros = disponibles.filter((operador) => !ORDEN_OPERADORES.includes(operador));
  return [...conocidos, ...otros];
}

export function tipoDe(campos: Campos, campo: string | null): TipoCampo | null {
  if (!campo) return null;
  const tipo = campos[campo]?.tipo;
  return tipo === 'texto' || tipo === 'numero' || tipo === 'fecha' || tipo === 'booleano'
    ? tipo
    : null;
}

/** Sum and average only mean something over numbers (RF-27). */
export function funcionAdmiteCampo(funcion: Funcion, tipo: TipoCampo | null): boolean {
  return !FUNCIONES_NUMERICAS.has(funcion) || tipo === 'numero';
}

/** `saldo_capital_pendiente` → `saldo capital pendiente`. Honest, not invented. */
export function humanizarCampo(nombre: string): string {
  return nombre.replace(/_/g, ' ');
}

// ---- Completeness ------------------------------------------------------------

export function filtroCompleto(filtro: FiltroBorrador): boolean {
  if (!filtro.campo || !filtro.operador) return false;
  const pide = valoresQuePide(filtro.operador);
  const valores = filtro.valores.map((valor) => valor.trim()).filter(Boolean);
  if (pide === 0) return true;
  if (pide === null) return valores.length > 0;
  return valores.length === pide && filtro.valores.length === pide;
}

export function indicadorCompleto(indicador: IndicadorBorrador): boolean {
  if (!indicador.nombre.trim()) return false;
  if (indicador.campo === null) return indicador.funcion === 'conteo';
  return true;
}

/** Positions of the parts still being written, to mark them in the editor. */
export function partesIncompletas(borrador: SeleccionBorrador): {
  filtros: number[];
  indicadores: number[];
} {
  return {
    filtros: borrador.filtros.flatMap((filtro, i) => (filtroCompleto(filtro) ? [] : [i])),
    indicadores: borrador.indicadores.flatMap((indicador, i) =>
      indicadorCompleto(indicador) ? [] : [i],
    ),
  };
}

// ---- Writing and reading the syntax ---------------------------------------------

export function escribirFiltro(filtro: FiltroBorrador): string {
  const base = `${filtro.campo}:${filtro.operador}`;
  if (valoresQuePide(filtro.operador) === 0) return base;
  const valores = filtro.valores.map((valor) => valor.trim()).filter(Boolean);
  return `${base}:${valores.join(SEPARADOR_VALORES)}`;
}

/**
 * The backend splits on the first two colons only, so a value may itself
 * carry a colon ("hora:10:30" is field, operator and "10:30").
 */
export function leerFiltro(texto: string): FiltroBorrador {
  const primero = texto.indexOf(':');
  if (primero < 0) return { campo: texto.trim(), operador: '', valores: [] };
  const segundo = texto.indexOf(':', primero + 1);
  const campo = texto.slice(0, primero).trim();
  if (segundo < 0) {
    return { campo, operador: texto.slice(primero + 1).trim(), valores: [] };
  }
  return {
    campo,
    operador: texto.slice(primero + 1, segundo).trim(),
    valores: texto.slice(segundo + 1).split(SEPARADOR_VALORES),
  };
}

export function escribirOrden(orden: OrdenBorrador | null): string | null {
  if (!orden || !orden.campo) return null;
  return `${orden.descendente ? '-' : ''}${orden.campo}`;
}

export function leerOrden(texto: string | null): OrdenBorrador | null {
  if (!texto) return null;
  const descendente = texto.startsWith('-');
  const campo = texto.replace(/^-+/, '').trim();
  return campo ? { campo, descendente } : null;
}

export function escribirIndicador(indicador: IndicadorBorrador): string {
  const base = `${indicador.nombre.trim()}:${indicador.funcion}`;
  return indicador.campo ? `${base}:${indicador.campo}` : base;
}

export function leerIndicador(texto: string): IndicadorBorrador {
  const [nombre = '', funcion = 'conteo', campo] = texto.split(':').map((parte) => parte.trim());
  return {
    nombre,
    funcion: (FUNCIONES as string[]).includes(funcion) ? (funcion as Funcion) : 'conteo',
    campo: campo ? campo : null,
  };
}

// ---- Between the draft, the query and a saved selection -------------------------

export function consultaDe(borrador: SeleccionBorrador): Consulta {
  return {
    filtros: borrador.filtros.filter(filtroCompleto).map(escribirFiltro),
    orden: escribirOrden(borrador.orden),
    cantidad: borrador.cantidad,
    indicadores: borrador.indicadores.filter(indicadorCompleto).map(escribirIndicador),
  };
}

export function borradorDe(
  guardada: Pick<SeleccionGuardada, 'filtros' | 'orden' | 'cantidad' | 'indicadores'>,
): SeleccionBorrador {
  return {
    filtros: guardada.filtros.map(leerFiltro),
    orden: leerOrden(guardada.orden),
    cantidad: guardada.cantidad,
    indicadores: guardada.indicadores.map(leerIndicador),
  };
}

export function mismaConsulta(a: Consulta, b: Consulta): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

/** A valid n for the top n, or null when the analyst wants the whole universe. */
export function leerCantidad(texto: string): number | null {
  const limpio = texto.trim();
  if (!/^\d+$/.test(limpio)) return null;
  const n = Number(limpio);
  return n >= 1 && n <= CANTIDAD_MAXIMA ? n : null;
}

// ---- Problems reported by the API ---------------------------------------------

/** Where a problem lands in the editor: which part and, for lists, which row. */
export interface ProblemaUbicado {
  parte: Problema['parte'];
  indice: number | null;
  detalle: string;
  expresion: string;
}

/**
 * Pin each problem the API reports to the row that caused it. The API names
 * the part and quotes the expression; a filter or indicator is found by
 * writing each row back to text and comparing.
 */
export function ubicarProblemas(
  problemas: Problema[],
  borrador: SeleccionBorrador,
): ProblemaUbicado[] {
  const normalizar = (texto: string) => texto.replace(/\s+/g, ' ').trim();
  return problemas.map((problema) => {
    const buscada = normalizar(problema.expresion);
    let indice: number | null = null;
    if (problema.parte === 'filtro') {
      const i = borrador.filtros.findIndex((filtro) => normalizar(escribirFiltro(filtro)) === buscada);
      indice = i >= 0 ? i : null;
    } else if (problema.parte === 'indicador') {
      const i = borrador.indicadores.findIndex(
        (indicador) => normalizar(escribirIndicador(indicador)) === buscada,
      );
      indice = i >= 0 ? i : null;
    }
    return { parte: problema.parte, indice, detalle: problema.detalle, expresion: problema.expresion };
  });
}

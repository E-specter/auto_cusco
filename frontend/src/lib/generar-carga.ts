/**
 * State of the "Generar carga" screen (docs/generacion-cargas.md, plan-f5.md).
 *
 * The screen turns a selection (cut-off date, filters, order, top n), a saved column definition and
 * a file format into one request to `/archivos-carga`. Pure on purpose: no DOM, no fetch. The page
 * reads these functions and draws; the tests call them directly.
 *
 * What lives here and what does not:
 *   - The request is built from what the user sees and nothing else. Filters and order travel exactly
 *     as the selector wrote them (same syntax as `/cartera`); the indicators are never sent.
 *   - The backend is the authority. Nothing here validates a platform rule (sheet name, encodings,
 *     delimiters, formulas): the API refuses what it refuses and the screen shows its reason. The
 *     only limits checked are the ones the contract itself declares for `cantidad`.
 *   - Wording is the screen's (i18n): this only says which case applies and with which numbers.
 */

import { ApiError } from './api';
import type { components } from './contrato-api';
import { CANTIDAD_MAXIMA, leerCantidad, type Consulta } from './seleccion';

type Esquemas = components['schemas'];

export type FormatoArchivo = Esquemas['FormatoArchivo'];
export type PeticionGeneracion = Esquemas['PeticionGeneracion'];
/** What `GET /archivos-carga/formatos` says about a format: its extension and each option it admits. */
export type FormatoDisponible = Esquemas['FormatoRespuesta'];
export type OpcionFormato = Esquemas['OpcionFormatoRespuesta'];
export type OpcionesEntrada = Esquemas['OpcionesEntrada'];
export type PrevisualizacionCarga = Esquemas['app__api__archivos_carga__PrevisualizacionRespuesta'];

export { CANTIDAD_MAXIMA };

/** The contract's default for `cantidad` (`PeticionGeneracion`, "@default 1000"). */
export const CANTIDAD_POR_DEFECTO = 1_000;

/** Same order as the buttons on screen. */
export const FORMATOS: readonly FormatoArchivo[] = ['csv', 'xlsx', 'json'];

/**
 * What the user has chosen. `version` is `null` while the latest version is the one wanted: the
 * request then leaves it out and the API picks the current one, so a definition saved in another
 * tab is picked up without the screen knowing.
 */
export type Borrador = {
  fechaCorte: string | null;
  /**
   * The send date as written in its field (RF-55): by default today in Lima. It always travels, so what
   * the analyst sees is what is generated. Whether it is not before the cut-off is the backend's to say.
   */
  fechaEnvio: string;
  /** The selection as the selector last emitted it. */
  consulta: Consulta;
  /** False while the API says a part of the selection does not apply. */
  aplicable: boolean;
  definicionId: number | null;
  /** The latest version of the chosen definition; `null` until one is chosen. */
  versionVigente: number | null;
  /** A specific version the user picked; `null` for "the latest". */
  version: number | null;
  formato: FormatoArchivo;
  /** What is written in the amount field. */
  cantidadTexto: string;
  /** True from the first edit on: the field stops following the selection. */
  cantidadTocada: boolean;
  /** What `/formatos` announced; the options of each format come from here and nowhere else. */
  formatos: readonly FormatoDisponible[];
  /**
   * The options the user edited, by name, as written in the control: text stays text (an integer is
   * read when the request is built). An option never touched is not here and the API's default applies.
   */
  opciones: Readonly<Record<string, ValorOpcion>>;
};

/** A control's value: a checkbox is a boolean, anything else is what the user typed. */
export type ValorOpcion = string | boolean;

/** The time zone of the operation: the send date "today" is the date in Lima, never the UTC one. */
export const ZONA_HORARIA = 'America/Lima';

/**
 * Today's date in Lima as `YYYY-MM-DD`. At night UTC is already tomorrow (Lima is UTC-5), so the
 * browser's own zone is not asked either: a machine set to another zone would give another day.
 */
export function hoyEnLima(ahora: Date = new Date()): string {
  const partes = new Intl.DateTimeFormat('en-CA', {
    timeZone: ZONA_HORARIA,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(ahora);
  const de = (tipo: string) => partes.find((p) => p.type === tipo)!.value;
  return `${de('year')}-${de('month')}-${de('day')}`;
}

const FECHA_ISO = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Calendar days from `desde` to `hasta` (both `YYYY-MM-DD`); negative if `hasta` is earlier. Only for
 * showing "N days after the cut-off": the adjustment of the days past due is the backend's.
 */
export function diasEntre(desde: string, hasta: string): number {
  const dia = (fecha: string) => {
    const [anio, mes, dd] = fecha.split('-').map(Number);
    return Date.UTC(anio, mes - 1, dd) / 86_400_000;
  };
  return Math.round(dia(hasta) - dia(desde));
}

export const consultaVacia = (): Consulta => ({ filtros: [], orden: null, cantidad: null, indicadores: [] });

/** The amount the selection suggests: its top n, or the contract's default when it has none. */
export function cantidadInicial(consulta: Pick<Consulta, 'cantidad'>): number {
  return consulta.cantidad ?? CANTIDAD_POR_DEFECTO;
}

export function borradorNuevo(hoy: string = hoyEnLima()): Borrador {
  return {
    fechaCorte: null,
    fechaEnvio: hoy,
    consulta: consultaVacia(),
    aplicable: true,
    definicionId: null,
    versionVigente: null,
    version: null,
    formato: 'xlsx',
    cantidadTexto: String(CANTIDAD_POR_DEFECTO),
    cantidadTocada: false,
    formatos: [],
    opciones: {},
  };
}

/**
 * A new selection arrived. The amount follows it until the user edits the field once; after that it
 * stays as written, whatever the selection does.
 */
export function conSeleccion(
  borrador: Borrador,
  seleccion: { fechaCorte: string | null; consulta: Consulta; aplicable: boolean },
): Borrador {
  return {
    ...borrador,
    fechaCorte: seleccion.fechaCorte,
    consulta: seleccion.consulta,
    aplicable: seleccion.aplicable,
    cantidadTexto: borrador.cantidadTocada ? borrador.cantidadTexto : String(cantidadInicial(seleccion.consulta)),
  };
}

export function conCantidad(borrador: Borrador, texto: string): Borrador {
  return { ...borrador, cantidadTexto: texto, cantidadTocada: true };
}

/** Choosing another definition drops a version picked on the previous one. */
export function conDefinicion(borrador: Borrador, id: number | null, versionVigente: number | null): Borrador {
  return { ...borrador, definicionId: id, versionVigente, version: null };
}

/** The latest version is "no explicit version", so the request never pins what is already current. */
export function conVersion(borrador: Borrador, numero: number): Borrador {
  return { ...borrador, version: numero === borrador.versionVigente ? null : numero };
}

export function conFechaEnvio(borrador: Borrador, fecha: string): Borrador {
  return { ...borrador, fechaEnvio: fecha };
}

export function conFormato(borrador: Borrador, formato: FormatoArchivo): Borrador {
  return { ...borrador, formato };
}

export function conFormatos(borrador: Borrador, formatos: readonly FormatoDisponible[]): Borrador {
  return { ...borrador, formatos };
}

// ---- Format options ----------------------------------------------------------------------

/** The options the chosen format admits, in the order the API lists them. */
export function opcionesDe(formatos: readonly FormatoDisponible[], formato: FormatoArchivo): readonly OpcionFormato[] {
  return formatos.find((f) => f.formato === formato)?.opciones ?? [];
}

/** What a control shows for an option: what the user wrote, else the API's default. */
export function valorDeOpcion(borrador: Pick<Borrador, 'opciones'>, opcion: OpcionFormato): ValorOpcion {
  const editado = borrador.opciones[opcion.nombre];
  if (editado !== undefined) return editado;
  if (opcion.tipo === 'booleano') return opcion.defecto === true;
  return opcion.defecto === null ? '' : String(opcion.defecto);
}

export function conOpcion(borrador: Borrador, nombre: string, valor: ValorOpcion): Borrador {
  return { ...borrador, opciones: { ...borrador.opciones, [nombre]: valor } };
}

const ENTERO = /^-?\d+$/;

/**
 * The options as the request carries them, and the ones of the chosen format that are not what their
 * type says. `opciones` is `null` while the user has not touched any (the API's defaults apply) or
 * `/formatos` does not describe one of the five the request needs.
 *
 * Only the *kind* of value is read here (a whole number is digits). Ranges, lengths, encodings and
 * every other rule of the platform stay with the backend: it answers and the screen shows its reason.
 * An empty text is "nothing written": the default applies, as it does for an option never touched.
 */
export function opcionesParaEnviar(
  borrador: Pick<Borrador, 'formato' | 'formatos' | 'opciones'>,
): { opciones: OpcionesEntrada | null; invalidas: string[] } {
  if (Object.keys(borrador.opciones).length === 0) return { opciones: null, invalidas: [] };

  const todas = new Map<string, OpcionFormato>();
  borrador.formatos.forEach((f) => f.opciones.forEach((o) => todas.has(o.nombre) || todas.set(o.nombre, o)));
  const delFormato = new Set(opcionesDe(borrador.formatos, borrador.formato).map((o) => o.nombre));
  const invalidas: string[] = [];

  const texto = (nombre: string): string | undefined => {
    const opcion = todas.get(nombre);
    if (!opcion) return undefined;
    const editado = borrador.opciones[nombre];
    if (typeof editado === 'string' && editado !== '') return editado;
    return typeof opcion.defecto === 'string' ? opcion.defecto : undefined;
  };
  const booleano = (nombre: string): boolean | undefined => {
    const opcion = todas.get(nombre);
    if (!opcion) return undefined;
    const editado = borrador.opciones[nombre];
    return typeof editado === 'boolean' ? editado : typeof opcion.defecto === 'boolean' ? opcion.defecto : undefined;
  };
  const entero = (nombre: string): number | null => {
    const opcion = todas.get(nombre);
    const porDefecto = typeof opcion?.defecto === 'number' ? opcion.defecto : null;
    const editado = borrador.opciones[nombre];
    if (typeof editado !== 'string') return porDefecto;
    const limpio = editado.trim();
    if (limpio === '') return null;
    if (ENTERO.test(limpio)) return Number(limpio);
    if (delFormato.has(nombre)) invalidas.push(nombre);
    return porDefecto;
  };

  const delimitador = texto('delimitador');
  const codificacion = texto('codificacion');
  const hoja = texto('hoja');
  const conCabeceras = booleano('con_cabeceras');
  const sangria = entero('sangria');
  if (delimitador === undefined || codificacion === undefined || hoja === undefined || conCabeceras === undefined) {
    return { opciones: null, invalidas };
  }
  return {
    opciones: { delimitador, codificacion, con_cabeceras: conCabeceras, hoja, sangria },
    invalidas,
  };
}

/** The version the request will use: the explicit one, or the latest. */
export function versionEfectiva(borrador: Borrador): number | null {
  return borrador.version ?? borrador.versionVigente;
}

/** The amount in the field as a number, or `null` while it is not a whole number in range. */
export function cantidadDe(borrador: Pick<Borrador, 'cantidadTexto'>): number | null {
  return leerCantidad(borrador.cantidadTexto);
}

/**
 * Whether the amount still follows the selection. The hint under the field changes when it stops:
 * "takes the selection's amount until you change it" / "no longer follows the selection".
 */
export const cantidadSigueLaSeleccion = (borrador: Pick<Borrador, 'cantidadTocada'>): boolean =>
  !borrador.cantidadTocada;

/** Whether the field holds something that is not a valid amount (an empty field is invalid too). */
export function cantidadInvalida(borrador: Pick<Borrador, 'cantidadTexto'>): boolean {
  return cantidadDe(borrador) === null;
}

/**
 * Why the button is off, or `null` when it is on. The screen writes the reason as text next to the
 * button; a disabled button without a reason is not accepted (designer, 2026-10-16). The first
 * missing thing wins, in the order the user meets them.
 */
export type MotivoInactivo =
  | 'sin_fecha'
  | 'sin_fecha_envio'
  | 'seleccion_no_aplica'
  | 'sin_definicion'
  | 'cantidad_invalida'
  | 'opcion_invalida';

export function motivoInactivo(borrador: Borrador): MotivoInactivo | null {
  if (!borrador.fechaCorte) return 'sin_fecha';
  if (!FECHA_ISO.test(borrador.fechaEnvio)) return 'sin_fecha_envio';
  if (!borrador.aplicable) return 'seleccion_no_aplica';
  if (borrador.definicionId === null) return 'sin_definicion';
  if (cantidadInvalida(borrador)) return 'cantidad_invalida';
  if (opcionesParaEnviar(borrador).invalidas.length > 0) return 'opcion_invalida';
  return null;
}

/**
 * The body for `/archivos-carga` and `/archivos-carga/previsualizacion`, or `null` while something is
 * missing. Both endpoints take the same body, so the preview shows what the download will produce.
 * `opciones` goes only when the user edited one (see `opcionesParaEnviar`).
 */
export function peticionDe(borrador: Borrador): PeticionGeneracion | null {
  if (motivoInactivo(borrador) !== null) return null;
  const cantidad = cantidadDe(borrador)!;
  const { opciones } = opcionesParaEnviar(borrador);
  const guardada: Esquemas['DefinicionGuardadaEntrada'] =
    borrador.version === null
      ? { id: borrador.definicionId! }
      : { id: borrador.definicionId!, version: borrador.version };
  return {
    fecha_corte: borrador.fechaCorte!,
    fecha_envio: borrador.fechaEnvio,
    definicion_guardada: guardada,
    formato: borrador.formato,
    filtros: [...borrador.consulta.filtros],
    orden: borrador.consulta.orden,
    cantidad,
    ...(opciones ? { opciones } : {}),
  };
}

/** Two requests are the same call: the preview that is already on screen does not need to run again. */
export function mismaPeticion(a: PeticionGeneracion | null, b: PeticionGeneracion | null): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

// ---- What the generation reports -----------------------------------------------------

/** The numbers that come with a generated file (`X-Carga-*` headers, read without the prefix). */
export type ResumenDeCarga = {
  generados: number;
  disponibles: number;
  solicitados: number;
  suficiente: boolean;
  errores: number;
  /** Products left out of the file because they fall in no segment (RF-50). */
  excluidos: number;
};

function entero(valor: string | undefined): number | null {
  if (valor === undefined || !/^\d+$/.test(valor.trim())) return null;
  return Number(valor.trim());
}

/**
 * The summary from the headers of a download (`descargarArchivo(..., 'X-Carga-').resumen`). `null` when
 * any of them is missing or is not a number: the screen then says it could not read the summary
 * instead of showing zeros it made up.
 */
export function resumenDeCabeceras(resumen: Record<string, string>): ResumenDeCarga | null {
  const generados = entero(resumen.generados);
  const disponibles = entero(resumen.disponibles);
  const solicitados = entero(resumen.solicitados);
  const errores = entero(resumen.errores);
  const excluidos = entero(resumen.excluidos);
  const suficiente = resumen.suficiente === '1' ? true : resumen.suficiente === '0' ? false : null;
  if (
    generados === null ||
    disponibles === null ||
    solicitados === null ||
    errores === null ||
    excluidos === null ||
    suficiente === null
  ) {
    return null;
  }
  return { generados, disponibles, solicitados, suficiente, errores, excluidos };
}

/**
 * Whether there were enough products for the amount asked (RF-08). The file is generated either way,
 * with the ones there are; the notice says how many.
 */
export type Suficiencia = { suficiente: true } | { suficiente: false; disponibles: number; solicitados: number };

export function suficienciaDe(resumen: Pick<ResumenDeCarga, 'suficiente' | 'disponibles' | 'solicitados'>): Suficiencia {
  return resumen.suficiente
    ? { suficiente: true }
    : { suficiente: false, disponibles: resumen.disponibles, solicitados: resumen.solicitados };
}

/**
 * The most rows the file can have, for the line next to the button: the amount asked, capped by what
 * the selection has once the preview knows it. It is a ceiling, not a promise: products that fall in
 * no segment are left out of the file (RF-50), and the preview only evaluates a sample of them, so the
 * screen says "up to N" whenever the preview reported exclusions.
 */
export function filasMaximas(solicitados: number, disponibles: number | null): number {
  return disponibles === null ? solicitados : Math.min(solicitados, disponibles);
}

// ---- Problems of the preview ---------------------------------------------------------------

/** Past this many of the same kind, the list shows one group that opens instead of every row. */
export const UMBRAL_AGRUPAR = 5;

/**
 * One thing that went wrong with the sample, whichever way it went wrong:
 * - `error`: a column could not be generated. `fila` is the row of the table; it has a `campo`.
 * - `exclusion`: the product is left out of the file. `fila` is its place in the selection (from 1)
 *   and `pagare` identifies it; it has a `codigo` the screen translates.
 */
export type ProblemaDeCarga =
  | { tipo: 'error'; fila: number; campo: string; detalle: string }
  | { tipo: 'exclusion'; fila: number; pagare: string | null; codigo: string; detalle: string };

export type ElementoDeProblemas =
  | { tipo: 'fila'; problema: ProblemaDeCarga }
  | { tipo: 'grupo'; clave: string; problemas: ProblemaDeCarga[] };

/** Errors first, then exclusions, each by row: the two kinds count rows differently. */
export function problemasDeCarga(
  previa: Pick<PrevisualizacionCarga, 'errores' | 'exclusiones'>,
): ProblemaDeCarga[] {
  const porFila = (a: ProblemaDeCarga, b: ProblemaDeCarga) => a.fila - b.fila;
  const errores = previa.errores
    .map((e): ProblemaDeCarga => ({ tipo: 'error', fila: e.fila, campo: e.campo, detalle: e.detalle }))
    .sort(porFila);
  const exclusiones = previa.exclusiones
    .map(
      (e): ProblemaDeCarga => ({
        tipo: 'exclusion',
        fila: e.fila,
        pagare: e.pagare,
        codigo: e.codigo,
        detalle: e.detalle,
      }),
    )
    .sort(porFila);
  return [...errores, ...exclusiones];
}

/** What groups rows: the same code for exclusions, the same column for errors. */
const claveDe = (p: ProblemaDeCarga): string => (p.tipo === 'error' ? `error:${p.campo}` : `exclusion:${p.codigo}`);

/**
 * The list the screen draws. A kind with more than `UMBRAL_AGRUPAR` rows becomes one group, at the
 * place of its first row, and the rest keep their order; the group says how many there are and opens
 * to show them all.
 */
export function agruparProblemas(problemas: readonly ProblemaDeCarga[], umbral = UMBRAL_AGRUPAR): ElementoDeProblemas[] {
  const porClave = new Map<string, ProblemaDeCarga[]>();
  problemas.forEach((p) => porClave.set(claveDe(p), [...(porClave.get(claveDe(p)) ?? []), p]));

  const elementos: ElementoDeProblemas[] = [];
  const puestos = new Set<string>();
  for (const problema of problemas) {
    const clave = claveDe(problema);
    const grupo = porClave.get(clave)!;
    if (grupo.length <= umbral) {
      elementos.push({ tipo: 'fila', problema });
    } else if (!puestos.has(clave)) {
      puestos.add(clave);
      elementos.push({ tipo: 'grupo', clave, problemas: grupo });
    }
  }
  return elementos;
}

// ---- The send date refused (RF-55) ------------------------------------------------------------------

/** The two dates of a 400 `fecha_envio_anterior`, as the backend sent them (ISO). */
export type FechasRechazadas = { fechaEnvio: string; fechaCorte: string };

/**
 * Reads the refusal "the send date is before the cut-off". The 400 carries both dates as fields of its
 * own, so the text can name them; anything that is not that refusal (or lacks a date) is `null`.
 */
export function fechasDeEnvioRechazadas(error: unknown): FechasRechazadas | null {
  if (!(error instanceof ApiError) || error.status !== 400 || error.codigo !== 'fecha_envio_anterior') return null;
  const envio = error.cuerpo?.fecha_envio;
  const corte = error.cuerpo?.fecha_corte;
  if (typeof envio !== 'string' || typeof corte !== 'string' || !FECHA_ISO.test(envio) || !FECHA_ISO.test(corte)) {
    return null;
  }
  return { fechaEnvio: envio, fechaCorte: corte };
}

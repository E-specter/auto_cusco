/**
 * The rules of the WhatsMKT configuration screen that do not need a browser: reading what was typed,
 * the MB <-> bytes conversion of the limits, the campaign-name example, and the texts of the
 * module's error codes (`whatsmkt.codigo.*`, docs/whatsmkt-interfaz.md §7).
 *
 * The API stays the judge of every rule (a 422 with its code); what is checked here is what the
 * fields can say on leaving them (RF-WM-43), with the same ranges the API declares.
 */

import { ApiError } from './api';
import type { ErrorWhatsmkt, SegmentoWhatsmktEntrada } from './api-whatsmkt';
import { t } from './i18n';

// ---- Limits (RF-WM-26, RF-WM-31) ---------------------------------------------------------------

/** The screen shows megabytes in decimal base (1 MB = 1 000 000 bytes); the API keeps bytes. */
export const BYTES_POR_MB = 1_000_000;

/** What the API accepts for a limit (`le` of its model), in its own unit: characters or bytes. */
const TOPE_MAXIMO_API = 2_000_000_000;

export type CampoTope = 'tope_mensaje' | 'tope_video' | 'tope_audio' | 'tope_pdf';

/** A limit in the unit the field shows: the message in characters, the attachments in MB. */
export const RANGOS_TOPES: Record<CampoTope, { minimo: number; maximo: number; enMb: boolean }> = {
  tope_mensaje: { minimo: 1, maximo: TOPE_MAXIMO_API, enMb: false },
  tope_video: { minimo: 1, maximo: TOPE_MAXIMO_API / BYTES_POR_MB, enMb: true },
  tope_audio: { minimo: 1, maximo: TOPE_MAXIMO_API / BYTES_POR_MB, enMb: true },
  tope_pdf: { minimo: 1, maximo: TOPE_MAXIMO_API / BYTES_POR_MB, enMb: true },
};

export const bytesAMb = (bytes: number): number => bytes / BYTES_POR_MB;
export const mbABytes = (mb: number): number => Math.round(mb * BYTES_POR_MB);

/** What a limit's field shows for the value the API holds. */
export function textoDeTope(campo: CampoTope, valorApi: number): string {
  return String(RANGOS_TOPES[campo].enMb ? bytesAMb(valorApi) : valorApi);
}

/**
 * The value to send for what was typed in a limit's field, in the API's unit, or `null` if it is not
 * a number in range (the characters are whole; the megabytes may carry decimals).
 */
export function leerTope(campo: CampoTope, texto: string): number | null {
  const { minimo, maximo, enMb } = RANGOS_TOPES[campo];
  const limpio = texto.trim();
  if (!/^\d+(\.\d+)?$/.test(limpio)) return null;
  const numero = Number(limpio);
  if (numero < minimo || numero > maximo) return null;
  if (!enMb) return Number.isInteger(numero) ? numero : null;
  return mbABytes(numero);
}

// ---- Time slots (RF-WM-07) -----------------------------------------------------------------------

export type Franja = 'horario_1' | 'horario_2';

const HORA = /^([01]\d|2[0-3]):[0-5]\d$/;

/** `HH:MM` both, the start earlier than the end (the API's rule: equal or reversed is refused). */
export const horarioValido = (inicio: string, fin: string): boolean =>
  HORA.test(inicio) && HORA.test(fin) && inicio < fin;

/** «Horario 1» / «Horario 2»: the slot's name, which the code's text puts in its sentence. */
export const nombreDeFranja = (franja: Franja): string =>
  t('whatsmkt.configuracion.horario', { n: franja === 'horario_1' ? 1 : 2 });

export const textoDeHorarioInvalido = (franja: Franja): string =>
  t('whatsmkt.codigo.horario_invalido', { horario: nombreDeFranja(franja) });

// ---- Campaign name (RF-WM-33) ----------------------------------------------------------------------

export const LARGO_MAXIMO_NOMBRE = 75;

/**
 * The cut-off date the examples use, in the `AAAA.MM.DD` the name carries it. A fixed illustration:
 * the real date is the campaign's, and the example is there to show the shape of the name.
 */
export const FECHA_DE_EJEMPLO = '2026.10.29';

/** The name a template gives with these values; a `{name}` it has no value for stays as written. */
export function nombreDeCampana(plantilla: string, valores: Readonly<Record<string, string>>): string {
  return plantilla.replace(/\{(\w+)\}/g, (literal, nombre: string) => valores[nombre] ?? literal);
}

/** One example per segment (the template is the same; the label changes the name). */
export function nombresDeEjemplo(plantilla: string, etiquetas: readonly string[]): string[] {
  return etiquetas.map((segmento) => nombreDeCampana(plantilla, { fecha_corte: FECHA_DE_EJEMPLO, segmento }));
}

// ---- Segment table (RF-WM-20) ----------------------------------------------------------------------

/** The API accepts days overdue between -RANGO_DIAS and RANGO_DIAS. */
export const RANGO_DIAS = 100_000;
export const LARGO_MAXIMO_ETIQUETA = 80;

/** A row as typed. A bound that is `null` is fixed (the first has no floor, the last no ceiling). */
export interface FilaSegmentoTexto {
  clave: string;
  etiqueta: string;
  desde: string | null;
  hasta: string | null;
}

export interface ProblemaDeFila {
  clave: string;
  campo: 'etiqueta' | 'desde' | 'hasta';
  texto: string;
}

function entero(texto: string): number | null {
  const limpio = texto.trim();
  if (!/^-?\d+$/.test(limpio)) return null;
  const numero = Number(limpio);
  return Math.abs(numero) <= RANGO_DIAS ? numero : null;
}

/** The body for the API from the rows as typed, or the problems found; overlaps and holes are the API's. */
export function leerSegmentos(filas: readonly FilaSegmentoTexto[]): {
  entrada: SegmentoWhatsmktEntrada[];
  problemas: ProblemaDeFila[];
} {
  const problemas: ProblemaDeFila[] = [];
  const entrada = filas.map((fila) => {
    const etiqueta = fila.etiqueta.trim();
    if (etiqueta === '' || etiqueta.length > LARGO_MAXIMO_ETIQUETA) {
      problemas.push({ clave: fila.clave, campo: 'etiqueta', texto: t('whatsmkt.configuracion.segmento.etiquetaVacia') });
    }
    const dias = (campo: 'desde' | 'hasta'): number | null => {
      const texto = fila[campo];
      if (texto === null) return null;
      const valor = entero(texto);
      if (valor === null) {
        problemas.push({ clave: fila.clave, campo, texto: t('whatsmkt.configuracion.segmento.diasInvalido') });
      }
      return valor;
    };
    const desde = dias('desde');
    const hasta = dias('hasta');
    if (desde !== null && hasta !== null && desde > hasta) {
      problemas.push({ clave: fila.clave, campo: 'desde', texto: t('whatsmkt.configuracion.segmento.rangoInvalido') });
    }
    return { clave: fila.clave, etiqueta, desde, hasta };
  });
  return { entrada, problemas };
}

// ---- Error codes (§7) -------------------------------------------------------------------------------

/** The module's 422 (`{detail, codigo, ...parameters}`), or `null` for any other failure. */
export function errorDeModulo(error: unknown): ErrorWhatsmkt | null {
  if (!(error instanceof ApiError) || error.status !== 422 || typeof error.cuerpo?.codigo !== 'string') return null;
  // The body is the contract's `ErrorWhatsmktRespuesta`; `ApiError` keeps it unread on purpose.
  return error.cuerpo as unknown as ErrorWhatsmkt;
}

/** The text of a code with its parameters, or the server's own sentence if this build lacks the key. */
export function textoDeCodigo(
  error: Pick<ErrorWhatsmkt, 'codigo' | 'detail'>,
  parametros: Readonly<Record<string, string | number | null | undefined>> = {},
): string {
  const presentes = Object.fromEntries(
    Object.entries(parametros).filter((par): par is [string, string | number] => par[1] != null),
  );
  const clave = `whatsmkt.codigo.${error.codigo}`;
  const texto = t(clave, presentes);
  return texto === clave ? error.detail : texto;
}

/** Where the segment table's error goes and what it says: under a row (overlap) or under the table. */
export function errorDeSegmentos(
  error: ErrorWhatsmkt,
  etiquetas: Readonly<Record<string, string>>,
): { fila: string | null; texto: string } {
  const nombre = (clave: string | null): string => (clave === null ? '' : (etiquetas[clave] ?? clave));
  if (error.codigo === 'segmentos_superpuestos') {
    // A row that overlaps itself (its «desde» past its «hasta») has nothing to be compared with: the server's reason.
    if (error.segmento === error.fila) return { fila: error.fila, texto: error.detail };
    return { fila: error.fila, texto: textoDeCodigo(error, { segmento: nombre(error.segmento) }) };
  }
  if (error.codigo === 'segmentos_con_hueco') {
    return {
      fila: null,
      texto: textoDeCodigo(error, { desde: error.desde ?? '−∞', hasta: error.hasta ?? '+∞' }),
    };
  }
  return { fila: null, texto: error.detail };
}

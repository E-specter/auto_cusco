/**
 * The v2 speech of MOWA MES (docs/motor-texto-enriquecido-interfaz.md §5.6; backend B6): one
 * expression of the rich-text engine per segment, instead of the two fixed parts of v1.
 *
 * What the screen decides from a version, a draft and the API's answers, kept out of the page so it
 * can be tested without a browser. It evaluates nothing and validates nothing: lengths, levels and
 * problems are the backend's; this only says how they read and where they go.
 *
 * v1 is not touched: `mowa-mes.ts` keeps its parts, its levels and its tests as they were.
 */

import type { components } from './contrato-api';
import type { Expresion } from './expresion';
import { t } from './i18n';
import type { LargoSegmento, VersionSpeech } from './api-mowa-mes';
import { ORDEN_SEGMENTOS } from './mowa-mes';
import { estaVacia, type Segmento, type Variante } from './variantes';

type Esquemas = components['schemas'];

export type ProblemaSpeech = Esquemas['ProblemaSpeechRespuesta'];
export type BorradorV2 = Esquemas['BorradorV2Respuesta'];
export type ExpresionSegmentoEntrada = Esquemas['ExpresionSegmentoEntrada'];

const posicion = (segmento: string) => ORDEN_SEGMENTOS.indexOf(segmento as (typeof ORDEN_SEGMENTOS)[number]);
const copia = <T>(valor: T): T => structuredClone(valor);

/** Whether a version holds expressions (`expresiones`) and not parts (`partes`). */
export const esV2 = (version: Pick<VersionSpeech, 'formato'>): boolean => version.formato === 'v2';

type ConExpresion = { segmento: string; expresion: Expresion };

/** The expressions of a version or of a draft, one per segment, in the segments' order. */
export function variantesDeVersion(version: Pick<VersionSpeech, 'expresiones'>): Variante[] {
  return [...version.expresiones]
    .sort((a, b) => posicion(a.segmento) - posicion(b.segmento))
    .map((e) => ({ segmento: e.segmento, expresion: copia(e.expresion) as Expresion }));
}

/** The segments the selector offers, with their ranges of adjusted days (RF-MM-15). */
export function segmentosDeVersion(version: Pick<VersionSpeech, 'expresiones'>): Segmento[] {
  return [...version.expresiones]
    .sort((a, b) => posicion(a.segmento) - posicion(b.segmento))
    .map((e) => ({ clave: e.segmento, etiqueta: e.etiqueta, desde: e.dias_desde, hasta: e.dias_hasta }));
}

/**
 * The same expressions with what is not a real difference made equal: the order, and the
 * `obligatoria: false` the backend always sends and the editor omits.
 */
function comparable(lista: readonly ConExpresion[]): unknown {
  return [...lista]
    .sort((a, b) => posicion(a.segmento) - posicion(b.segmento))
    .map((x) => ({
      segmento: x.segmento,
      nodos: x.expresion.nodos.map((n) => (n.tipo === 'variable' ? { ...n, obligatoria: Boolean(n.obligatoria) } : n)),
    }));
}

/**
 * Whether the draft differs from the saved version. Texts are compared exactly: the spaces at the
 * ends of a part are text the message carries (RF-MM-14).
 */
export function hayCambiosV2(version: Pick<VersionSpeech, 'expresiones'>, borrador: readonly Variante[]): boolean {
  return (
    JSON.stringify(comparable(version.expresiones as unknown as ConExpresion[])) !== JSON.stringify(comparable(borrador))
  );
}

/**
 * What is sent when saving: the segments that have content, in the segments' order. A segment
 * with nothing is left out, never sent empty: the backend refuses it, and saying it was saved
 * would be false.
 */
export function entradaDeExpresiones(borrador: readonly Variante[]): ExpresionSegmentoEntrada[] {
  return [...borrador]
    .filter((v) => posicion(v.segmento) >= 0 && !estaVacia(v.expresion))
    .sort((a, b) => posicion(a.segmento) - posicion(b.segmento))
    .map((v) => ({
      segmento: v.segmento as ExpresionSegmentoEntrada['segmento'],
      expresion: copia(v.expresion) as ExpresionSegmentoEntrada['expresion'],
    }));
}

/** The segments that would have no message: nothing written, or missing from the draft. */
export function segmentosSinContenido(borrador: readonly Variante[], segmentos: readonly Segmento[]): Segmento[] {
  return segmentos.filter((s) => {
    const propia = borrador.find((v) => v.segmento === s.clave);
    return !propia || estaVacia(propia.expresion);
  });
}

// ---- Levels --------------------------------------------------------------------------------

export type TonoNivel = 'vigente' | 'advertencia' | 'error' | 'neutral';
export type NivelesV2 = Record<string, { tono: TonoNivel; texto: string }>;

/** The text of a code of the engine, or the backend's own sentence for one this build lacks. */
function textoDeCodigoDelMotor(codigo: string, respaldo: string): string {
  const clave = `textoEnriquecido.codigo.${codigo}`;
  const texto = t(clave);
  return texto === clave ? respaldo : texto;
}

/**
 * What `VariantesSegmento.fijarNiveles` shows beside each segment, from the backend's per-segment
 * preview. A level is never claimed without a maximum: a segment with no bound says why
 * (`sin_maximo`), and one with neither says nothing at all.
 */
export function nivelesDeV2(largos: readonly LargoSegmento[]): NivelesV2 {
  const niveles: NivelesV2 = {};
  for (const largo of largos) {
    if (largo.falta_whatsapp) {
      niveles[largo.segmento] = { tono: 'neutral', texto: t('mowaMes.speech.nivel.falta_whatsapp') };
    } else if (largo.largo_maximo === null) {
      if (largo.sin_maximo) {
        niveles[largo.segmento] = {
          tono: 'advertencia',
          texto: textoDeCodigoDelMotor(largo.sin_maximo.codigo, largo.sin_maximo.detalle),
        };
      }
    } else {
      const nivel =
        largo.codigo === 'mensaje_excede_160' ? 'excede' : largo.codigo === 'mensaje_excede_150' ? 'advertencia' : 'ok';
      niveles[largo.segmento] = {
        tono: nivel === 'ok' ? 'vigente' : nivel === 'excede' ? 'error' : 'advertencia',
        texto: t('mowaMes.speech.v2.nivelConLargo', {
          nivel: t(`mowaMes.speech.nivel.${nivel}`),
          n: largo.largo_maximo,
        }),
      };
    }
  }
  return niveles;
}

// ---- Problems ------------------------------------------------------------------------------

/**
 * A problem's text from the catalogue it came from: the engine's codes and MOWA MES's share a
 * name (`telefono_invalido`) with different texts, so the catalogue — not the name — picks the
 * key. A code this build does not know reads as the backend's sentence, never as a raw key.
 */
export function mensajeDeProblema(problema: Pick<ProblemaSpeech, 'codigo' | 'catalogo' | 'detalle'>): string {
  if (!problema.codigo || !problema.catalogo) return problema.detalle;
  const clave = `${problema.catalogo === 'mowa_mes' ? 'mowaMes' : 'textoEnriquecido'}.codigo.${problema.codigo}`;
  const texto = t(clave);
  return texto === clave ? problema.detalle : texto;
}

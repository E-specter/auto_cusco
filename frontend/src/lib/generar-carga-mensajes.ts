/**
 * The words of the "Generar carga" screen that depend on state (docs/agents/…/plan-f5.md §13 and §14).
 *
 * Kept out of the page so each sentence is tested once: the line next to the button, the reason it
 * is off, how a refusal reads, what a problem of the sample says and the notices after a download or
 * a cancel. The keys live in `es.json`/`en.json` under `generar.*`; a code of the engine reads from
 * `textoEnriquecido.codigo.*`, as everywhere else, and falls back to the backend's own sentence for a
 * code this build does not know.
 *
 * The screen does not guess what the server did. After a cancel it says what it cannot know ("may
 * appear as used"), and it never reads the definition again to find out.
 */

import { ApiError } from './api';
import type { ElementoDeProblemas, FormatoArchivo, MotivoInactivo, ProblemaDeCarga, ResumenDeCarga } from './generar-carga';
import { t } from './i18n';

/** The text of a code of the engine, or the backend's own sentence when this build lacks it. */
export function textoDeCodigo(codigo: string, respaldo: string): string {
  const clave = `textoEnriquecido.codigo.${codigo}`;
  const texto = t(clave);
  return texto === clave ? respaldo : texto;
}

/**
 * Why a call was refused or failed. The server's `codigo` wins when the catalogue knows it; else its
 * `detail`; else a generic sentence. An unreachable API is not a refusal.
 */
export function mensajeDeError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.codigo) {
      const traducido = textoDeCodigo(error.codigo, '');
      if (traducido) return traducido;
    }
    return error.detail || t('generar.error.generico', { estado: error.status });
  }
  return t('generar.error.red');
}

/** Why the button is off, in words. `opcion` names the option that is not what its type says. */
export function textoMotivo(motivo: MotivoInactivo, opcion?: string): string {
  if (motivo === 'opcion_invalida') {
    const clave = `generar.opcion.${opcion ?? ''}`;
    const nombre = opcion && t(clave) !== clave ? t(clave) : (opcion ?? '');
    return t('generar.motivo.opcion_invalida', { opcion: nombre });
  }
  return t(`generar.motivo.${motivo}`);
}

/** Names of the usual delimiters, for the ones that do not read on their own (a tab is blank). */
const NOMBRES_DE_DELIMITADOR: Readonly<Record<string, string>> = {
  ',': 'generar.delimitador.coma',
  ';': 'generar.delimitador.puntoycoma',
  '	': 'generar.delimitador.tabulacion',
  '|': 'generar.delimitador.barraVertical',
};

/**
 * The visible name of a suggested value of an option, or `undefined` when the value reads by itself
 * (an encoding: `utf-8`). Only the delimiter has names; the API's suggestions drive the rest.
 */
export function etiquetaDeSugerido(opcion: string, valor: string): string | undefined {
  if (opcion !== 'delimitador') return undefined;
  const clave = NOMBRES_DE_DELIMITADOR[valor];
  return clave ? t(clave) : undefined;
}

export function etiquetaDeFormato(formato: FormatoArchivo): string {
  return formato.toUpperCase();
}

/**
 * "Se generarán N filas en XLSX con la versión 4 de «SMS preventivo»". With a definition that leaves
 * out products with no segment the preview only evaluates a sample, so the total is a ceiling
 * ("hasta N").
 */
export function lineaDeSalida(datos: {
  filas: number;
  esTope: boolean;
  formato: FormatoArchivo;
  version: number | null;
  nombre: string;
}): string {
  const clave = datos.esTope ? 'generar.linea.hasta' : 'generar.linea.exacta';
  return t(clave, {
    n: datos.filas,
    formato: etiquetaDeFormato(datos.formato),
    version: datos.version ?? '—',
    nombre: datos.nombre,
  });
}

/** What the sample's problem says and where it is: a column row, or a product left out. */
export function descripcionDeProblema(problema: ProblemaDeCarga): { donde: string; mensaje: string } {
  if (problema.tipo === 'error') {
    return {
      donde: t('generar.problemas.error', { campo: problema.campo, fila: problema.fila }),
      mensaje: problema.detalle,
    };
  }
  return {
    donde: problema.pagare
      ? t('generar.problemas.exclusion', { fila: problema.fila, pagare: problema.pagare })
      : t('generar.problemas.exclusionSinPagare', { fila: problema.fila }),
    mensaje: textoDeCodigo(problema.codigo, problema.detalle),
  };
}

/**
 * A group of rows of the same kind, in the two cells of the problems table: where (how many) and what
 * happened (what they have in common), plus the label of the button that opens them.
 */
export function descripcionDeGrupo(grupo: Extract<ElementoDeProblemas, { tipo: 'grupo' }>): {
  donde: string;
  mensaje: string;
  ver: string;
} {
  const primero = grupo.problemas[0];
  const n = grupo.problemas.length;
  const ver = t('generar.problemas.ver', { n });
  if (primero.tipo === 'error') {
    return { donde: t('generar.problemas.grupo.filas', { n, campo: primero.campo }), mensaje: primero.detalle, ver };
  }
  return {
    donde: t('generar.problemas.grupo.productos', { n }),
    mensaje: textoDeCodigo(primero.codigo, primero.detalle),
    ver,
  };
}

/** Not enough products for the amount asked (RF-08): the file still comes out with the ones there are. */
export function avisoDeSuficiencia(datos: { disponibles: number; solicitados: number }): string {
  return t('generar.suficiencia.insuficiente', datos);
}

/** Products of the sample left out for lack of a segment (RF-50). `muestra` is how many were evaluated. */
export function avisoDeExclusiones(datos: { excluidos: number; muestra: number }): string {
  return t('generar.exclusiones.aviso', datos);
}

export function avisoDeErrores(n: number): string {
  return t('generar.errores.aviso', { n });
}

/** After a download. The summary is the server's own, read from its headers. */
export function avisoDeExito(datos: {
  archivo: string;
  resumen: ResumenDeCarga | null;
  version: number | null;
  nombre: string;
}): string[] {
  const lineas: string[] = [];
  if (datos.resumen) {
    // Nothing left out is not worth a clause: "300 filas generadas y 0 excluidas" reads like a problem.
    const clave = datos.resumen.excluidos > 0 ? 'generar.exito.cuerpo' : 'generar.exito.cuerpoSinExcluidos';
    lineas.push(
      t(clave, {
        archivo: datos.archivo,
        generados: datos.resumen.generados,
        excluidos: datos.resumen.excluidos,
      }),
    );
    if (!datos.resumen.suficiente) {
      // Not the preview's "the file comes out with the ones there are": with exclusions that would
      // contradict the rows just reported. Only what happened.
      lineas.push(
        t('generar.exito.suficiencia', {
          disponibles: datos.resumen.disponibles,
          solicitados: datos.resumen.solicitados,
        }),
      );
    }
  } else {
    lineas.push(t('generar.exito.sinResumen', { archivo: datos.archivo }));
  }
  lineas.push(t('generar.exito.usada', { version: datos.version ?? '—', nombre: datos.nombre }));
  return lineas;
}

/**
 * After Cancel. The server runs to the end whatever the browser does, so this promises nothing: the
 * file may still be generated and the version may be marked used.
 */
export function avisoDeCancelacion(version: number | null): string {
  return t('generar.cancelado', { version: version ?? '—' });
}

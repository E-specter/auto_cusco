/**
 * The rules of the WhatsMKT campaign screen that need no browser (T-WM-F2a1, docs/whatsmkt-interfaz.md §3): what the
 * form holds, the request for the preview it builds, the problems that stop creating (the API's and the ones the form
 * can say on its own), the names the lot would have, and how a definition's columns, a segment's days and an attachment
 * read on screen.
 *
 * The API stays the judge of every rule; the preview is its answer. What is checked here is what the fields can say
 * before asking, and the text of what comes back.
 */

import type {
  AdjuntoWhatsmkt,
  ConfiguracionWhatsmkt,
  ModoCampana,
  PeticionPrevisualizacion,
  ProblemaCampana,
  SegmentoWhatsmkt,
  TipoEnvio,
} from './api-whatsmkt';
import type { Expresion } from './expresion';
import { resumenDeContenido } from './constructor-pantalla';
import { formatDate } from './format';
import { t } from './i18n';
import type { Consulta } from './seleccion';
import {
  LARGO_MAXIMO_NOMBRE,
  nombreDeCampana,
  nombreDeTipo,
  tamanoLegible,
  textoDeCodigo,
  type Franja,
} from './whatsmkt';

// ---- What the form holds ------------------------------------------------------------------------------

export interface BorradorCampana {
  modo: ModoCampana;
  /** The definition of the platform chosen; `null` until one is. */
  definicionId: number | null;
  /** The text of the global message (`texto_guardado_id`), or `null`. */
  mensajeGlobal: number | null;
  /** The text of each segment's message by the segment's key; the segment's own from the configuration to begin with. */
  mensajesPorSegmento: Record<string, number | null>;
  /** `YYYY-MM-DD` or `''` while none is chosen. */
  fechaEnvio: string;
  horarios: Record<Franja, boolean>;
  antes: boolean;
  tipoEnvio: TipoEnvio;
  /** What each type keeps while the analyst looks at another: only the chosen type's is sent. */
  adjuntoId: number | null;
  fotoId: number | null;
  etiquetaVcard: string;
  plantilla: string;
}

/**
 * The form as it opens: by segment, each segment with its own message, the configuration's default definition and name
 * template. No time slot is chosen (the analyst decides, RF-WM-07), and no date until one is picked.
 */
export function borradorInicial(configuracion: ConfiguracionWhatsmkt, segmentos: readonly SegmentoWhatsmkt[]): BorradorCampana {
  return {
    modo: 'por_segmento',
    definicionId: configuracion.definicion_defecto_id,
    mensajeGlobal: null,
    mensajesPorSegmento: Object.fromEntries(segmentos.map((segmento) => [segmento.clave, segmento.texto_guardado_id])),
    fechaEnvio: '',
    horarios: { horario_1: false, horario_2: false },
    antes: false,
    tipoEnvio: 'solo_texto',
    adjuntoId: null,
    fotoId: null,
    etiquetaVcard: '',
    plantilla: configuracion.plantilla_nombre,
  };
}

export const horariosElegidos = (borrador: BorradorCampana): Franja[] =>
  (['horario_1', 'horario_2'] as const).filter((franja) => borrador.horarios[franja]);

// ---- The request ------------------------------------------------------------------------------------------

/** What the selection says: a cut-off date, its parts in the API's syntax and, if it came from one, its id. */
export interface SeleccionBase {
  fechaCorte: string;
  consulta: Consulta;
  guardadaId: number | null;
}

/**
 * The preview request, or `null` while it cannot be asked: no cut-off date, no top n in the selection (a campaign takes
 * a fixed number of products) or no definition. The message goes by mode (one for the lot, or one per segment, leaving
 * out a segment that has none: the API then takes the one of the configuration). A date that is not typed is not sent.
 */
export function entradaDePrevisualizacion(base: SeleccionBase, borrador: BorradorCampana): PeticionPrevisualizacion | null {
  if (base.consulta.cantidad === null || borrador.definicionId === null) return null;
  const entrada: PeticionPrevisualizacion = {
    fecha_corte: base.fechaCorte,
    filtros: base.consulta.filtros,
    orden: base.consulta.orden,
    cantidad: base.consulta.cantidad,
    seleccion_id: base.guardadaId,
    definicion: { id: borrador.definicionId },
    modo: borrador.modo,
  };
  if (borrador.fechaEnvio !== '') entrada.fecha_envio = borrador.fechaEnvio;
  if (borrador.modo === 'global') {
    if (borrador.mensajeGlobal !== null) entrada.mensaje = { texto_guardado_id: borrador.mensajeGlobal };
  } else {
    const elegidos = Object.entries(borrador.mensajesPorSegmento).filter(
      (par): par is [string, number] => par[1] !== null,
    );
    entrada.mensajes = Object.fromEntries(elegidos.map(([clave, id]) => [clave, { texto_guardado_id: id }]));
  }
  return entrada;
}

// ---- Names of the lot (RF-WM-33, DU-WM-6) -------------------------------------------------------------------

/**
 * The name each campaign of the lot would have. In a lot, a template that does not use `{segmento}` gets the segment
 * added at the end so the names do not repeat (DU-WM-6).
 *
 * shortcut: this mirrors the backend's rule to show the names before creating; the real ones are the API's, and the sheet
 * of F2a2 shows them. Upgrade if the rule stops being this one (the preview could return the names).
 */
export function nombresDeLote(
  plantilla: string,
  campanas: ReadonlyArray<{ etiqueta_segmento: string | null }>,
  fechaCorte: string,
): string[] {
  const fecha = fechaCorte.replaceAll('-', '.');
  const agregarSegmento = campanas.length > 1 && !plantilla.includes('{segmento}');
  return campanas.map((campana) => {
    const etiqueta = campana.etiqueta_segmento ?? '';
    const nombre = nombreDeCampana(plantilla, { fecha_corte: fecha, segmento: etiqueta });
    return agregarSegmento ? `${nombre} ${etiqueta}` : nombre;
  });
}

/** `{variable}` names the template uses that the API does not list, each once, in order. */
export function variablesDesconocidasDeNombre(plantilla: string, validas: readonly string[]): string[] {
  const vistas: string[] = [];
  for (const [, nombre] of plantilla.matchAll(/\{([^{}]*)\}/g)) {
    if (!validas.includes(nombre) && !vistas.includes(nombre)) vistas.push(nombre);
  }
  return vistas;
}

// ---- Problems -----------------------------------------------------------------------------------------------

/** The section of the screen a problem is about, where its «Ir al campo» takes the focus. */
export type SeccionDeProblema = 'archivo' | 'mensaje' | 'programacion' | 'envio' | 'nombre' | 'supervisores' | 'whatsapp';

export function seccionDeProblema(codigo: string): SeccionDeProblema | null {
  if (codigo === 'definicion_no_whatsmkt') return 'archivo';
  if (['sin_mensaje', 'mensaje_deshabilitado', 'macro_inexistente', 'mensaje_con_emoji', 'mensaje_largo'].includes(codigo)) return 'mensaje';
  if (codigo === 'sin_horario' || codigo === 'fecha_no_gestionable') return 'programacion';
  if (codigo === 'nombre_largo' || codigo === 'variable_inexistente') return 'nombre';
  if (codigo.startsWith('foto_') || codigo.startsWith('adjunto_')) return 'envio';
  if (codigo === 'sin_supervisores') return 'supervisores';
  if (codigo === 'sin_whatsapp') return 'whatsapp';
  return null;
}

/**
 * The text of a problem the API answered. A message missing in a global campaign has its own sentence (there is no
 * segment to name); every other code reads under `whatsmkt.codigo.<codigo>` with its parameters, or in the API's own words.
 */
export function textoDeProblema(problema: Pick<ProblemaCampana, 'codigo' | 'detalle' | 'segmento' | 'parametros'>): string {
  if (problema.codigo === 'sin_mensaje' && problema.segmento === null) return t('whatsmkt.problema.sin_mensaje.global');
  if (problema.codigo === 'fecha_no_gestionable') {
    // The API sends both dates as AAAA-MM-DD; the sentence reads them as the rest of the app does («16 oct 2026»).
    const { fecha, sugerida } = problema.parametros as Record<string, string | undefined>;
    return textoDeCodigo(
      { codigo: problema.codigo, detail: problema.detalle },
      { fecha: fecha ? formatDate(fecha) : undefined, sugerida: sugerida ? formatDate(sugerida) : undefined },
    );
  }
  return textoDeCodigo({ codigo: problema.codigo, detail: problema.detalle }, problema.parametros);
}

/** A problem with its segment's name in front when it has one: «Tramo 2 · El mensaje usa [whatsapp] y…». */
export function textoDeProblemaConSegmento(
  problema: Pick<ProblemaCampana, 'codigo' | 'detalle' | 'segmento' | 'parametros'>,
  etiquetas: Readonly<Record<string, string>>,
): string {
  const texto = textoDeProblema(problema);
  return problema.segmento === null ? texto : `${etiquetas[problema.segmento] ?? problema.segmento} · ${texto}`;
}

/** A problem the form finds without asking: where it is, its code (for the text) and what it says. */
export interface ProblemaLocal {
  seccion: SeccionDeProblema;
  codigo: string;
  texto: string;
}

/**
 * What stops creating that the form knows by itself: no definition, no time slot chosen, a type of sending that lacks its
 * file or its label, a template with a variable the API does not list, or a name over the 75 characters WhatsMKT takes.
 */
export function problemasLocales(
  borrador: BorradorCampana,
  variablesValidas: readonly string[],
  nombres: readonly string[],
): ProblemaLocal[] {
  const problemas: ProblemaLocal[] = [];
  if (borrador.definicionId === null) {
    problemas.push({ seccion: 'archivo', codigo: 'sin_definicion', texto: t('whatsmkt.archivo.elegirDefinicion') });
  }
  if (horariosElegidos(borrador).length === 0) {
    problemas.push({ seccion: 'programacion', codigo: 'sin_horario', texto: t('whatsmkt.codigo.sin_horario') });
  }
  if (borrador.tipoEnvio === 'archivo' && borrador.adjuntoId === null) {
    problemas.push({ seccion: 'envio', codigo: 'sin_adjunto', texto: t('whatsmkt.envio.sinAdjunto') });
  }
  if (borrador.tipoEnvio === 'vcard' && borrador.etiquetaVcard.trim() === '') {
    problemas.push({ seccion: 'envio', codigo: 'sin_etiqueta', texto: t('whatsmkt.envio.sinEtiqueta') });
  }
  const desconocidas = variablesDesconocidasDeNombre(borrador.plantilla, variablesValidas);
  if (desconocidas.length > 0) {
    problemas.push({
      seccion: 'nombre',
      codigo: 'variable_inexistente',
      texto: textoDeCodigo({ codigo: 'variable_inexistente', detail: '' }, { variable: `{${desconocidas[0]}}` }),
    });
  } else {
    const largo = Math.max(0, ...nombres.map((nombre) => nombre.length));
    if (largo > LARGO_MAXIMO_NOMBRE) {
      problemas.push({ seccion: 'nombre', codigo: 'nombre_largo', texto: textoDeCodigo({ codigo: 'nombre_largo', detail: '' }, { largo }) });
    }
  }
  return problemas;
}

/** The sentence beside «Crear» while there are problems: «Corrige 2 problemas para crear.» */
export function motivoDeCrear(cantidad: number): string {
  return cantidad === 1 ? t('whatsmkt.crear.problemasUno') : t('whatsmkt.crear.problemas', { n: cantidad });
}

// ---- How things read ------------------------------------------------------------------------------------------

/** A segment's days overdue as a range: «hasta 0», «1 a 8», «9 o más». */
export function diasDeSegmento(segmento: Pick<SegmentoWhatsmkt, 'desde' | 'hasta'>): string {
  const { desde, hasta } = segmento;
  if (desde !== null && hasta !== null) return t('whatsmkt.campana.diasRango', { desde, hasta });
  if (hasta !== null) return t('whatsmkt.campana.diasHasta', { n: hasta });
  if (desde !== null) return t('whatsmkt.campana.diasDesde', { n: desde });
  return t('whatsmkt.campana.diasTodos');
}

/** An attachment in a select: «afiche-octubre.jpg · Imagen JPEG · 240 KB». */
export const etiquetaDeAdjunto = (adjunto: Pick<AdjuntoWhatsmkt, 'nombre' | 'tipo' | 'tamano'>): string =>
  `${adjunto.nombre} · ${nombreDeTipo(adjunto.tipo)} · ${tamanoLegible(adjunto.tamano)}`;

/** A column of a saved definition, as far as the table of the screen needs it. */
export interface ColumnaDeDefinicion {
  nombre: string;
  etiqueta: string | null;
  expresion: Expresion;
  /** How many segment variants the column has; the list of the builder says so after the content. */
  variantes?: number;
}

export interface FilaDeColumna {
  /** The position the message uses as `[$MACROn$]`; `null` for the first column, the number, which is fixed (RF-WM-11). */
  macro: number | null;
  encabezado: string;
  etiqueta: string | null;
  contenido: string;
}

/**
 * The columns of a definition at a glance: the first is the number (no macro); each of the others is macro 1, 2, 3 by its
 * position. The content reads like the list of the builder (`resumenDeContenido` is its function; the words are its keys
 * `columnas.contenido.*`): a variable by its visible name, or the start of a composed text.
 *
 * shortcut: the assembly of those words (10 lines) is `textoDeContenido` of `pages/columnas.astro`, which is not exported; this
 * repeats it until it is a function of a module (then import it and delete this).
 */
const MAXIMO_RESUMEN = 60;

export function filasDeColumnas(
  columnas: readonly ColumnaDeDefinicion[],
  etiquetaDeVariable: (nombre: string) => string = (nombre) => nombre,
): FilaDeColumna[] {
  return columnas.map((columna, indice) => {
    const resumen = resumenDeContenido(columna.expresion, etiquetaDeVariable, MAXIMO_RESUMEN);
    let contenido: string;
    if (resumen.modo === 'vacio') contenido = t('columnas.contenido.vacio');
    else if (resumen.modo === 'variable') {
      contenido = resumen.funciones
        ? t('columnas.contenido.variableConFunciones', { variable: resumen.variable, n: resumen.funciones })
        : t('columnas.contenido.variable', { variable: resumen.variable });
    } else {
      contenido = t(resumen.recortado ? 'columnas.contenido.textoRecortado' : 'columnas.contenido.texto', { fragmento: resumen.fragmento });
    }
    if (columna.variantes) {
      contenido += ` · ${t(columna.variantes === 1 ? 'columnas.variantes.uno' : 'columnas.variantes.otras', { n: columna.variantes })}`;
    }
    return { macro: indice === 0 ? null : indice, encabezado: columna.nombre, etiqueta: columna.etiqueta, contenido };
  });
}

/** The columns that are macros, for the five-variables note (DU-WM-1, provisional: it warns and does not block). */
export const cantidadDeMacros = (columnas: readonly unknown[]): number => Math.max(0, columnas.length - 1);

/** WhatsMKT publishes up to this many variables per message (DU-WM-1, provisional). */
export const MACROS_PUBLICADAS = 5;

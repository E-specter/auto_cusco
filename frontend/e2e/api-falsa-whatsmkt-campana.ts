/**
 * What the WhatsMKT campaign screen reads besides the configuration (T-WM-F2a1): the preview of the lot, the saved texts
 * of the context `whatsmkt.mensaje`, and the columns of a definition. It is registered AFTER `montarApiWhatsmkt` and falls
 * back to it (`route.fallback()`) for everything else, like `apoyo-seleccion.ts`.
 *
 * Typed against the generated contract. Every value is invented; the phones are synthetic (900000xxx).
 */
import type { Page } from '@playwright/test';

import type { ResumenTexto } from '../src/lib/api-textos-guardados';
import type {
  CampanaCreada,
  CampanaPrevista,
  CodigoWhatsmkt,
  ExclusionCampana,
  PeticionCreacion,
  PeticionPrevisualizacion,
  PrevisualizacionCampanas,
  ProblemaCampana,
} from '../src/lib/api-whatsmkt';
import { catalogoSintetico } from './api-falsa-texto-enriquecido';
import { json, siguiente } from './apoyo';

type Guion = { estado: number; cuerpo?: unknown };

export interface CampanaFalsa {
  /** The saved texts of `whatsmkt.mensaje`, enabled and disabled (`deshabilitado_en`). */
  textos: ResumenTexto[];
  /** Problems the API adds to the ones the fake works out (no message, a disabled one): `sin_supervisores`, `sin_whatsapp`… */
  problemasExtra: ProblemaCampana[];
  /** How many products fall outside every campaign (by segment), and how many of them the API lists (the first 100). */
  fuera: { total: number; listadas: number };
  /** How many exclusions the first campaign has. */
  exclusiones: number;
  /** The label of each segment as the preview names it (a long one makes a long campaign name). */
  etiquetas: Record<string, string>;
  /** Scripted answers to the preview, taken in order (the last repeats); empty means the fake builds it. */
  respuestasPrevia: Guion[];
  /** The requests of the preview, in order. */
  previas: PeticionPrevisualizacion[];
  /** What `GET /whatsmkt/programacion` says: the suggested working day and the earliest date. */
  programacion: { sugerida: string; minima: string; proximas: string[] };
  /** The send dates the preview answers `fecha_no_gestionable` to; the suggestion that comes with it is the next working day after (Monday to Saturday). */
  fechasNoGestionables: string[];
  /** The requests that create the lot, in order. */
  creaciones: PeticionCreacion[];
  /** Scripted answers to creating, taken in order (the last repeats); empty means the fake creates the lot from the preview. */
  respuestasCrear: Guion[];
  /** What the card of each campaign warns about (`sin_whatsapp`). */
  avisosFicha: CodigoWhatsmkt[];
  /** The ids of the campaigns whose file was downloaded. */
  descargas: number[];
}

const ENLACE_FALSO = 'https://wa.me/+51900000123';

/**
 * The text of a version of a message. The block under the select, «Así lo verá el cliente» and the card of the campaign created all come from
 * it, so each says what the message chosen says; a version after the first carries its number, which tells it from the latest.
 */
export function textoDeMensaje(resumen: Pick<ResumenTexto, 'nombre' | 'version_vigente'>, version = resumen.version_vigente): string {
  return `Hola [$MACRO1$], ${resumen.nombre}: tu saldo es [$MACRO2$]. INFO por [whatsapp]${version > 1 ? ` (v${version})` : ''}`;
}

export function texto(id: number, nombre: string, parcial: Partial<ResumenTexto> = {}): ResumenTexto {
  return {
    id,
    contexto: 'whatsmkt.mensaje',
    nombre,
    version_vigente: 1,
    cantidad_versiones: 1,
    actualizado_en: '2026-10-09T10:00:00-05:00',
    vigente_usada: false,
    deshabilitado_en: null,
    eliminable: true,
    ...parcial,
  };
}

export function campanaFalsa(parcial: Partial<CampanaFalsa> = {}): CampanaFalsa {
  return {
    textos: [texto(101, 'Preventivo'), texto(102, 'Tramo 2'), texto(103, 'Oferta de octubre')],
    problemasExtra: [],
    fuera: { total: 3, listadas: 3 },
    exclusiones: 12,
    etiquetas: ETIQUETAS,
    respuestasPrevia: [],
    previas: [],
    // The clock of `montarApiWhatsmkt` is Thursday 15 Oct 2026: tomorrow is the first working day.
    programacion: { sugerida: '2026-10-16', minima: '2026-10-16', proximas: ['2026-10-16', '2026-10-17', '2026-10-19'] },
    fechasNoGestionables: ['2026-10-18'],
    creaciones: [],
    respuestasCrear: [],
    avisosFicha: [],
    descargas: [],
    ...parcial,
  };
}

const ETIQUETAS: Record<string, string> = { preventivo: 'Preventivo', tramo_2: 'Tramo 2', mayores_2: 'Tramos mayores al 2' };

const exclusion = (fila: number, codigo: ExclusionCampana['codigo'], detalle: string): ExclusionCampana => ({
  codigo,
  fila,
  pagare: `00000000000${String(1000 + fila)}`,
  detalle,
  macro: null,
  etiqueta: null,
});

/** What the customer would read: the message with the first row's values and the contact link. */
function ejemploDe(mensaje: CampanaPrevista['mensaje'], estado: CampanaFalsa): string | null {
  const resumen = mensaje === null ? undefined : estado.textos.find((t) => t.id === mensaje.texto_guardado_id);
  if (!mensaje || !resumen) return null;
  return textoDeMensaje(resumen, mensaje.version).replace('[whatsapp]', ENLACE_FALSO).replace('[$MACRO1$]', 'Maria').replace('[$MACRO2$]', '1500.50');
}

function campanaPrevista(clave: string | null, cantidad: number, estado: CampanaFalsa, mensaje: CampanaPrevista['mensaje']): CampanaPrevista {
  const exclusiones = Array.from({ length: estado.exclusiones }, (_, i) =>
    exclusion(i + 1, i % 2 === 0 ? 'sin_telefono' : 'telefono_invalido', i % 2 === 0 ? 'No tiene teléfono' : 'El teléfono no es válido'),
  );
  return {
    segmento: clave,
    etiqueta_segmento: clave === null ? null : estado.etiquetas[clave],
    cantidad,
    productos: cantidad - 2,
    supervisores: 2,
    cabeceras: [
      { nombre: 'número', etiqueta: 'Número con prefijo' },
      { nombre: '[$MACRO1$]', etiqueta: 'Nombres del titular' },
      { nombre: '[$MACRO2$]', etiqueta: null },
    ],
    total_exclusiones: exclusiones.length,
    exclusiones,
    muestra: [
      { supervision: true, celdas: ['51900000501', 'Supervisor Uno', '1500.50'] },
      { supervision: true, celdas: ['51900000502', 'Supervisor Dos', '1500.50'] },
      { supervision: false, celdas: ['51900000001', 'Maria', '230.00'] },
      { supervision: false, celdas: ['51900000002', 'Jose', '410.75'] },
    ],
    mensaje,
    mensaje_ejemplo: ejemploDe(mensaje, estado),
  };
}

/** The preview the fake builds: by segment, Preventivo and Tramo 2 have products and the third does not; global is one campaign. */
function previsualizacion(entrada: PeticionPrevisualizacion, estado: CampanaFalsa): PrevisualizacionCampanas {
  const mensajeDe = (pedido: { texto_guardado_id: number } | null | undefined): CampanaPrevista['mensaje'] => {
    const encontrado = pedido ? estado.textos.find((t) => t.id === pedido.texto_guardado_id) : undefined;
    return encontrado
      ? { texto_guardado_id: encontrado.id, nombre: encontrado.nombre, version: encontrado.version_vigente, deshabilitado: encontrado.deshabilitado_en !== null }
      : null;
  };
  const claves = entrada.modo === 'global' ? [null] : ['preventivo', 'tramo_2'];
  const problemas: ProblemaCampana[] = [];
  const campanas = claves.map((clave, i) => {
    const mensaje = mensajeDe(clave === null ? entrada.mensaje : entrada.mensajes?.[clave]);
    if (mensaje === null) problemas.push({ codigo: 'sin_mensaje', detalle: 'La campaña no tiene mensaje', segmento: clave, parametros: {} });
    else if (mensaje.deshabilitado) problemas.push({ codigo: 'mensaje_deshabilitado', detalle: 'El mensaje está deshabilitado', segmento: clave, parametros: {} });
    return campanaPrevista(clave, clave === null ? 1000 : i === 0 ? 520 : 480, estado, mensaje);
  });
  if (entrada.fecha_envio && estado.fechasNoGestionables.includes(entrada.fecha_envio)) {
    problemas.push({
      codigo: 'fecha_no_gestionable',
      detalle: 'La fecha de envío no es un día gestionable',
      segmento: null,
      parametros: { fecha: entrada.fecha_envio, sugerida: siguienteDiaGestionable(entrada.fecha_envio) },
    });
  }
  const fuera = entrada.modo === 'global' ? { total: 0, listadas: 0 } : estado.fuera;
  return {
    campanas,
    problemas: [...problemas, ...estado.problemasExtra],
    disponibles: 1205,
    solicitados: entrada.cantidad,
    total_exclusiones: campanas.reduce((suma, c) => suma + c.total_exclusiones, 0) + fuera.total,
    total_exclusiones_sin_campana: fuera.total,
    exclusiones_sin_campana: Array.from({ length: fuera.listadas }, (_, i) =>
      exclusion(100 + i, 'sin_dias_atraso', 'No tiene días de atraso, así que no cae en ningún segmento. En el modo «Global» sí entraría.'),
    ),
  };
}

/** The text of the card: the version of the message the request names (the one the preview showed), with the macros as they are and `[whatsapp]` as the link. */
function mensajeDeLaFicha(entrada: PeticionCreacion, segmento: string | null, estado: CampanaFalsa): string {
  const pedido = segmento === null ? entrada.mensaje : entrada.mensajes?.[segmento];
  const resumen = estado.textos.find((t) => t.id === pedido?.texto_guardado_id);
  if (!pedido || !resumen) return '';
  return textoDeMensaje(resumen, pedido.version ?? resumen.version_vigente).replace('[whatsapp]', ENLACE_FALSO);
}

/** The lot the backend answers (201): one campaign per campaign of the preview, with the card of its form written as the request says. */
function loteCreado(entrada: PeticionCreacion, estado: CampanaFalsa): CampanaCreada[] {
  const previa = previsualizacion(entrada, estado);
  return previa.campanas.map((campana, i) => {
    const nombre =
      campana.segmento === null
        ? (entrada.nombre ?? 'CUZCO_Vencida whatsapp')
        : (entrada.nombres?.[campana.segmento] ?? `CUZCO_Vencida (${campana.etiqueta_segmento}) whatsapp`);
    const franja = (h: string) => (h === 'horario_1' ? { inicio: '08:00', fin: '14:00' } : { inicio: '14:00', fin: '20:00' });
    return {
      id: 37 + i,
      lote_id: 12,
      nombre,
      segmento: campana.segmento,
      archivo: { nombre: `${nombre}.xlsx`, tamano: 18_000, filas: campana.cantidad },
      ficha: {
        nombre,
        fecha_envio: entrada.fecha_envio ?? estado.programacion.sugerida,
        horarios: entrada.horarios.map((h) => ({ nombre: h, ...franja(h) })),
        lo_antes_posible: entrada.lo_antes_posible ?? false,
        pais: 'Perú',
        foto_id: entrada.foto_id ?? null,
        cantidad: campana.cantidad,
        tipo_envio: entrada.tipo_envio ?? 'solo_texto',
        adjunto_id: entrada.adjunto_id ?? null,
        etiqueta_vcard: entrada.etiqueta_vcard ?? null,
        mensaje: mensajeDeLaFicha(entrada, campana.segmento, estado),
        avisos: estado.avisosFicha,
      },
    };
  });
}

/** The next working day after `fecha` (AAAA-MM-DD): the next one that is not a Sunday. The fake has no holidays. */
export function siguienteDiaGestionable(fecha: string): string {
  const dia = new Date(`${fecha}T12:00:00Z`);
  do dia.setUTCDate(dia.getUTCDate() + 1);
  while (dia.getUTCDay() === 0);
  return dia.toISOString().slice(0, 10);
}

/** The columns of a definition: the number, then the macros (the first with a label, the second without). */
export function definicionConColumnas(id: number) {
  const variable = (nombre: string) => ({ nodos: [{ tipo: 'variable' as const, nombre, funciones: [], obligatoria: false }] });
  const columna = (orden: number, nombre: string, etiqueta: string | null, expresion: { nodos: unknown[] }) => ({
    nombre,
    orden,
    expresion,
    tipo: 'texto' as const,
    formato_fecha: null,
    formato_financiero: null,
    valor_por_defecto: null,
    variantes: [],
    celda_texto: false,
    etiqueta,
  });
  return {
    id,
    nombre: `Definición ${id}`,
    creado_en: '2026-10-09T10:00:00-05:00',
    actualizado_en: '2026-10-09T10:00:00-05:00',
    version_vigente: 3,
    versiones: [],
    plataforma: 'whatsmkt',
    problemas: [],
    version: {
      numero: 3,
      creado_en: '2026-10-09T10:00:00-05:00',
      usada_en: null,
      usada: false,
      contenido: {
        proteger_formulas: true,
        segmentacion: null,
        columnas: [
          columna(0, 'número', 'Número con prefijo', { nodos: [{ tipo: 'texto', valor: '51' }, ...variable('telefono').nodos] }),
          columna(1, '[$MACRO1$]', 'Nombres del titular', variable('titular')),
          columna(2, '[$MACRO2$]', null, variable('saldo_capital_pendiente')),
        ],
      },
    },
  };
}

export async function montarCampanaWhatsmkt(page: Page, estado: CampanaFalsa): Promise<void> {
  await page.route('**/api/**', async (route) => {
    const peticion = route.request();
    const url = new URL(peticion.url());
    const ruta = url.pathname.replace(/^\/api/, '');
    const metodo = peticion.method();

    if (ruta === '/whatsmkt/campanas/previsualizacion' && metodo === 'POST') {
      const entrada = JSON.parse(peticion.postData() ?? '{}') as PeticionPrevisualizacion;
      estado.previas.push(entrada);
      const guion = siguiente(estado.respuestasPrevia);
      return guion ? json(route, guion.estado, guion.cuerpo ?? {}) : json(route, 200, previsualizacion(entrada, estado));
    }
    if (ruta === '/whatsmkt/campanas' && metodo === 'POST') {
      const entrada = JSON.parse(peticion.postData() ?? '{}') as PeticionCreacion;
      estado.creaciones.push(entrada);
      const guion = siguiente(estado.respuestasCrear);
      return guion ? json(route, guion.estado, guion.cuerpo ?? {}) : json(route, 201, loteCreado(entrada, estado));
    }
    const archivo = /^\/whatsmkt\/campanas\/(\d+)\/archivo$/.exec(ruta);
    if (archivo && metodo === 'GET') {
      estado.descargas.push(Number(archivo[1]));
      return route.fulfill({
        status: 200,
        headers: {
          'content-type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          'content-disposition': `attachment; filename="campana-${archivo[1]}.xlsx"`,
        },
        body: 'contenido sintetico de la campana',
      });
    }
    if (ruta === '/whatsmkt/programacion' && metodo === 'GET') return json(route, 200, estado.programacion);
    if (ruta === '/texto-enriquecido/catalogo' && metodo === 'GET' && url.searchParams.get('contexto') === 'cartera') {
      return json(route, 200, catalogoSintetico('cartera'));
    }
    if (ruta === '/textos-guardados' && metodo === 'GET') {
      const deshabilitados = url.searchParams.get('deshabilitados') === 'true';
      return json(route, 200, estado.textos.filter((t) => (t.deshabilitado_en !== null) === deshabilitados));
    }
    const delTexto = /^\/textos-guardados\/(\d+)$/.exec(ruta);
    if (delTexto && metodo === 'GET') {
      const resumen = estado.textos.find((t) => t.id === Number(delTexto[1]));
      if (!resumen) return json(route, 404, { detail: 'No existe el texto', codigo: 'texto_guardado_no_encontrado' });
      const version = {
        numero: resumen.version_vigente,
        creado_en: resumen.actualizado_en,
        usada_en: null,
        usada: false,
        contenido: { texto: textoDeMensaje(resumen) },
      };
      return json(route, 200, {
        id: resumen.id,
        contexto: resumen.contexto,
        nombre: resumen.nombre,
        creado_en: resumen.actualizado_en,
        actualizado_en: resumen.actualizado_en,
        deshabilitado_en: resumen.deshabilitado_en,
        version_vigente: resumen.version_vigente,
        versiones: [{ numero: version.numero, creado_en: version.creado_en, usada_en: null, usada: false }],
        version,
      });
    }
    const definicion = /^\/definiciones-columnas\/(\d+)$/.exec(ruta);
    if (definicion && metodo === 'GET') return json(route, 200, definicionConColumnas(Number(definicion[1])));

    return route.fallback();
  });
}

/**
 * What the WhatsMKT tracking screen reads (T-WM-F3a): the campaigns, one detail each (card, lot, exclusions and the products left out of the lot),
 * and discarding, restoring, deleting and downloading. It is registered AFTER `montarApiWhatsmkt` and falls back to it (`route.fallback()`) for
 * everything else; the library (`/whatsmkt/adjuntos`) is the main fake's. The state is a plain object a spec reads and changes.
 *
 * Typed against the generated contract. Every value is invented; the phones and the promissory notes are synthetic.
 */
import type { Page, Route } from '@playwright/test';

import type { DetalleCampana, ExclusionCampana, ListaCampanas, PaginaExclusiones, ResumenCampana } from '../src/lib/api-whatsmkt';
import { json, siguiente } from './apoyo';

/** What the API answers instead of its normal answer: a status with its body, or the connection lost. */
type Guion = { estado: number; cuerpo?: unknown } | 'red';

export interface CampanaGuardada {
  resumen: ResumenCampana;
  modo: 'por_segmento' | 'global';
  /** How many exclusions the campaign has of its own. */
  exclusiones: number;
  fotoId: number | null;
  adjuntoId: number | null;
  /** The message as it was frozen when the campaign was created. */
  mensaje: string;
}

export interface SeguimientoFalso {
  campanas: CampanaGuardada[];
  /** The products left out of every campaign, by lot: the same list from any campaign of the lot. */
  fueraPorLote: Record<number, number>;
  /** Scripted answers to the actions, taken in order (the last repeats; `null` is the normal answer); empty means the fake behaves. */
  respuestas: { descartar: Array<Guion | null>; restaurar: Array<Guion | null>; eliminar: Array<Guion | null> };
  /** The same for the reads: the list, one detail, the download of the file. */
  fallos: { lista: Array<Guion | null>; detalle: Array<Guion | null>; archivo: Array<Guion | null> };
  /** Every action the screen asked: `DESCARTAR 37`, `RESTAURAR 30`, `ELIMINAR 30`. */
  acciones: string[];
  /** The ids whose file was downloaded. */
  descargas: number[];
  /** The `limite` of every list request, to see that the screen asks once with the most the API gives. */
  pedidosDeLista: Array<Record<string, string>>;
}

const horario1 = { nombre: 'horario_1', inicio: '08:00', fin: '14:00' };

export function campanaGuardada(id: number, parcial: Partial<ResumenCampana> = {}, resto: Partial<Omit<CampanaGuardada, 'resumen'>> = {}): CampanaGuardada {
  return {
    resumen: {
      id,
      nombre: `CUZCO_Vencida (Preventivo) whatsapp ${id}`,
      lote_id: 12,
      segmento: 'preventivo',
      segmento_etiqueta: 'Preventivo',
      fecha_envio: '2026-10-15',
      horarios: [horario1],
      cantidad: 520,
      creada_en: '2026-10-14T10:00:00-05:00',
      descartada_en: null,
      con_informe: false,
      ...parcial,
    },
    modo: 'por_segmento',
    exclusiones: 12,
    fotoId: null,
    adjuntoId: null,
    mensaje: `Hola [$MACRO1$], tu cuota vence pronto. INFO por https://wa.me/+51900000123 (campaña ${id})`,
    ...resto,
  };
}

export function seguimientoFalso(): SeguimientoFalso {
  return {
    campanas: [
      campanaGuardada(38, { nombre: 'CUZCO_Vencida (Tramo 2) whatsapp 2026.09.13', segmento: 'tramo_2', segmento_etiqueta: 'Tramo 2', cantidad: 480 }),
      campanaGuardada(37, { nombre: 'CUZCO_Vencida (Preventivo) whatsapp 2026.09.13' }, { fotoId: 1, adjuntoId: 1 }),
      campanaGuardada(36, { nombre: 'CUZCO_Vencida whatsapp especial', lote_id: 11, segmento: null, segmento_etiqueta: null, fecha_envio: '2026-11-02', cantidad: 1000, con_informe: true }, { modo: 'global' }),
      campanaGuardada(35, { lote_id: 10, fecha_envio: '2026-09-28', con_informe: true, nombre: 'CUZCO_Vencida (Preventivo) whatsapp 2026.08.30' }),
      campanaGuardada(30, { lote_id: 9, fecha_envio: '2026-09-10', descartada_en: '2026-09-12T09:00:00-05:00', nombre: 'CUZCO_Vencida (Preventivo) whatsapp 2026.08.01' }),
    ],
    fueraPorLote: { 12: 15, 11: 0, 10: 3, 9: 0 },
    respuestas: { descartar: [], restaurar: [], eliminar: [] },
    fallos: { lista: [], detalle: [], archivo: [] },
    acciones: [],
    descargas: [],
    pedidosDeLista: [],
  };
}

/** `cantidad` more active campaigns of a lot of their own, to have a list that does not fit one page. */
export function conMuchasCampanas(estado: SeguimientoFalso, cantidad: number): SeguimientoFalso {
  for (let i = 0; i < cantidad; i += 1) {
    estado.campanas.push(campanaGuardada(100 + i, { lote_id: 8, con_informe: true, nombre: `CUZCO_Vencida lote 8 número ${i + 1}` }));
  }
  return estado;
}

const exclusion = (fila: number, i: number): ExclusionCampana => ({
  codigo: i % 2 === 0 ? 'sin_telefono' : 'telefono_invalido',
  fila,
  pagare: `00000000000${String(1000 + fila)}`,
  detalle: i % 2 === 0 ? 'No tiene teléfono' : 'El teléfono no es válido',
  macro: null,
  etiqueta: null,
});

/** The products left out of every campaign of a lot have no days overdue (or a segment without products): never a phone problem. */
const sinDiasDeAtraso = (fila: number, i: number): ExclusionCampana => ({
  ...exclusion(fila, i),
  codigo: 'sin_dias_atraso',
  detalle: 'No tiene días de atraso',
});

const pagina = (total: number, desde = 1, fuera = false): PaginaExclusiones => ({
  total,
  limite: 1000,
  desplazamiento: 0,
  exclusiones: Array.from({ length: total }, (_, i) => (fuera ? sinDiasDeAtraso(desde + i, i) : exclusion(desde + i, i))),
});

function lista(estado: SeguimientoFalso, descartadas: boolean): ListaCampanas {
  const activas = estado.campanas.filter((c) => c.resumen.descartada_en === null);
  const seleccion = estado.campanas.filter((c) => (c.resumen.descartada_en !== null) === descartadas);
  return {
    total: seleccion.length,
    limite: 500,
    desplazamiento: 0,
    campanas: seleccion.map((c) => c.resumen),
    total_activas: activas.length,
    total_descartadas: estado.campanas.length - activas.length,
    total_pendientes: activas.filter((c) => !c.resumen.con_informe).length,
  };
}

function detalle(estado: SeguimientoFalso, campana: CampanaGuardada): DetalleCampana {
  const r = campana.resumen;
  return {
    ...r,
    lote: { id: r.lote_id, modo: campana.modo },
    fecha_corte: '2026-09-13',
    productos: r.cantidad - 2,
    supervisores: 2,
    definicion_nombre: 'Contactos WhatsMKT',
    definicion_version: 3,
    texto_version: 1,
    archivo: { nombre: `${r.nombre}.xlsx`, tamano: 18_000, filas: r.cantidad },
    ficha: {
      nombre: r.nombre,
      fecha_envio: r.fecha_envio,
      horarios: r.horarios,
      lo_antes_posible: false,
      pais: 'Perú',
      foto_id: campana.fotoId,
      cantidad: r.cantidad,
      tipo_envio: campana.adjuntoId === null ? 'solo_texto' : 'archivo',
      adjunto_id: campana.adjuntoId,
      etiqueta_vcard: null,
      mensaje: campana.mensaje,
      avisos: [],
    },
    exclusiones: pagina(campana.exclusiones),
    exclusiones_fuera_del_lote: pagina(campana.modo === 'global' ? 0 : (estado.fueraPorLote[r.lote_id] ?? 0), 2000, true),
  };
}

function responder(route: Route, guion: Exclude<Guion, null>): Promise<void> {
  return guion === 'red' ? route.abort('failed') : json(route, guion.estado, guion.cuerpo ?? {});
}

export async function montarSeguimientoWhatsmkt(page: Page, estado: SeguimientoFalso): Promise<void> {
  await page.route('**/api/**', async (route) => {
    const peticion = route.request();
    const url = new URL(peticion.url());
    const ruta = url.pathname.replace(/^\/api/, '');
    const metodo = peticion.method();

    if (ruta === '/whatsmkt/campanas' && metodo === 'GET') {
      estado.pedidosDeLista.push(Object.fromEntries(url.searchParams));
      const fallo = siguiente(estado.fallos.lista);
      if (fallo) return responder(route, fallo);
      return json(route, 200, lista(estado, url.searchParams.get('estado') === 'descartadas'));
    }
    const de = /^\/whatsmkt\/campanas\/(\d+)(?:\/(descartar|restaurar|archivo))?$/.exec(ruta);
    if (!de) return route.fallback();
    const id = Number(de[1]);
    const campana = estado.campanas.find((c) => c.resumen.id === id);
    if (!campana) return json(route, 404, { detail: 'No existe la campaña' });

    if (de[2] === undefined && metodo === 'GET') {
      const fallo = siguiente(estado.fallos.detalle);
      if (fallo) return responder(route, fallo);
      return json(route, 200, detalle(estado, campana));
    }
    if (de[2] === 'archivo' && metodo === 'GET') {
      const fallo = siguiente(estado.fallos.archivo);
      if (fallo) return responder(route, fallo);
      estado.descargas.push(id);
      return route.fulfill({
        status: 200,
        headers: {
          'content-type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          'content-disposition': `attachment; filename="campana-${id}.xlsx"`,
        },
        body: 'contenido sintetico de la campana',
      });
    }
    if ((de[2] === 'descartar' || de[2] === 'restaurar') && metodo === 'POST') {
      estado.acciones.push(`${de[2].toUpperCase()} ${id}`);
      const guion = siguiente(estado.respuestas[de[2]]);
      if (guion) return responder(route, guion);
      campana.resumen.descartada_en = de[2] === 'descartar' ? '2026-10-15T11:00:00-05:00' : null;
      return json(route, 200, campana.resumen);
    }
    if (de[2] === undefined && metodo === 'DELETE') {
      estado.acciones.push(`ELIMINAR ${id}`);
      const guion = siguiente(estado.respuestas.eliminar);
      if (guion) return responder(route, guion);
      if (campana.resumen.descartada_en === null) {
        return json(route, 409, { detail: 'La campaña está activa: solo se elimina una descartada', codigo: 'campana_no_descartada' });
      }
      estado.campanas = estado.campanas.filter((c) => c.resumen.id !== id);
      return route.fulfill({ status: 204 });
    }
    return route.fallback();
  });
}

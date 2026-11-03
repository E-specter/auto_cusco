/**
 * A stand-in for the WhatsMKT API, driven entirely from the test.
 *
 * Typed against the generated contract, so a fake the backend could never send fails to compile. Every
 * value is invented. It keeps the rules the screen's behaviour depends on (the partial PUT, the time slots,
 * the template variables, the segment table) and a scripted answer (`respuestas`) overrides them to test
 * the paths that are hard to reach otherwise.
 */
import type { Page } from '@playwright/test';

import type {
  CodigoWhatsmkt,
  ConfiguracionWhatsmkt,
  ErrorWhatsmkt,
  SegmentoWhatsmkt,
  SegmentoWhatsmktEntrada,
} from '../src/lib/api-whatsmkt';
import { json, siguiente } from './apoyo';

/**
 * The clock every WhatsMKT spec runs on: mid-month at noon, so Lima (UTC-5) and UTC fall on the same day. The
 * browser reads it through `page.clock`; a spec never reads Node's own clock, which on a runner in UTC says
 * another day in the first hours after Lima's midnight (the lesson of the MOWA MES CI of 1 November).
 */
export const AHORA_WHATSMKT = '2026-10-15T12:00:00-05:00';

type Guion = { estado: number; cuerpo?: unknown };

export interface ApiFalsaWhatsmkt {
  configuracion: ConfiguracionWhatsmkt;
  segmentos: SegmentoWhatsmkt[];
  /** Scripted answers, taken in order (the last repeats); an empty queue means the fake decides. */
  respuestas: { guardarConfiguracion: Guion[]; guardarSegmentos: Guion[] };
  sinRed: boolean;
  /** Every call the screen made, with its JSON body. */
  pedidos: Array<{ metodo: string; ruta: string; cuerpo: unknown }>;
}

/** The 422 body of a module rule: every parameter travels, the ones the code does not use are null. */
export function errorWhatsmkt(codigo: CodigoWhatsmkt, parcial: Partial<ErrorWhatsmkt> = {}): ErrorWhatsmkt {
  return {
    detail: `Regla ${codigo}`,
    codigo,
    horarios: null,
    variable: null,
    segmento: null,
    fila: null,
    desde: null,
    hasta: null,
    peso: null,
    maximo: null,
    tipo: null,
    ancho: null,
    alto: null,
    ...parcial,
  };
}

export function apiWhatsmkt(): ApiFalsaWhatsmkt {
  return {
    configuracion: {
      horario_1: { inicio: '08:00', fin: '14:00' },
      horario_2: { inicio: '14:00', fin: '20:00' },
      plantilla_nombre: 'CUZCO_Vencida ({segmento}) whatsapp {fecha_corte}',
      definicion_defecto_id: null,
      whatsapp_contacto: null,
      tope_mensaje: 4096,
      tope_video: 16_000_000,
      tope_audio: 16_000_000,
      tope_pdf: 16_000_000,
      actualizado_en: '2026-10-14T10:00:00-05:00',
      variables_plantilla: ['fecha_corte', 'segmento'],
    },
    segmentos: [
      { clave: 'preventivo', etiqueta: 'Preventivo', desde: null, hasta: 0, orden: 0, texto_guardado_id: null },
      { clave: 'tramo_2', etiqueta: 'Tramo 2', desde: 1, hasta: 8, orden: 1, texto_guardado_id: null },
      { clave: 'mayores_2', etiqueta: 'Tramos mayores al 2', desde: 9, hasta: null, orden: 2, texto_guardado_id: null },
    ],
    respuestas: { guardarConfiguracion: [], guardarSegmentos: [] },
    sinRed: false,
    pedidos: [],
  };
}

const horarioValido = (inicio: string, fin: string) => inicio < fin;

/** The API's rule for the segment table, in the order it applies it: overlap and holes. */
function errorDeSegmentos(entrada: SegmentoWhatsmktEntrada[]): ErrorWhatsmkt | null {
  const ordenados = [...entrada].sort((a, b) => (a.desde ?? -Infinity) - (b.desde ?? -Infinity));
  for (let i = 1; i < ordenados.length; i++) {
    const anterior = ordenados[i - 1];
    const actual = ordenados[i];
    if (anterior.hasta === null || actual.desde === null || actual.desde <= anterior.hasta) {
      return errorWhatsmkt('segmentos_superpuestos', { segmento: anterior.clave, fila: actual.clave });
    }
    if (actual.desde > anterior.hasta + 1) {
      return errorWhatsmkt('segmentos_con_hueco', { desde: anterior.hasta + 1, hasta: actual.desde - 1 });
    }
  }
  return null;
}

/** FastAPI's validation answer: `detail` is a list of objects, not a sentence, and carries no code. */
const invalido = (campo: string) => ({ detail: [{ loc: ['body', campo], msg: 'Input should be greater than 0', type: 'value_error' }] });

/** Route every `/api` call to `estado`. Anything not handled answers 404, so a missing fake fails loudly. */
export async function montarApiWhatsmkt(page: Page, estado: ApiFalsaWhatsmkt): Promise<void> {
  // `setFixedTime`, not `install`: the timers keep running, so the waits and the debounces are the real ones.
  await page.clock.setFixedTime(new Date(AHORA_WHATSMKT));
  await page.route('**/api/**', async (route) => {
    const pedido = route.request();
    const url = new URL(pedido.url());
    const ruta = url.pathname.replace(/^\/api/, '');
    const metodo = pedido.method();
    const texto = pedido.postData();
    let cuerpo: unknown = null;
    if (texto) {
      try {
        cuerpo = JSON.parse(texto);
      } catch {
        cuerpo = texto;
      }
    }
    estado.pedidos.push({ metodo, ruta: `${ruta}${url.search}`, cuerpo });

    if (estado.sinRed) return route.abort('connectionrefused');
    if (ruta === '/health') return json(route, 200, { api: true, database: true, ok: true });

    if (ruta === '/whatsmkt/configuracion' && metodo === 'GET') return json(route, 200, estado.configuracion);
    if (ruta === '/whatsmkt/configuracion' && metodo === 'PUT') {
      const guion = siguiente(estado.respuestas.guardarConfiguracion);
      if (guion) return json(route, guion.estado, guion.cuerpo ?? estado.configuracion);

      // The partial PUT: a field left out keeps what is saved.
      const entrada = (cuerpo && typeof cuerpo === 'object' ? cuerpo : {}) as Record<string, unknown>;
      for (const campo of ['tope_mensaje', 'tope_video', 'tope_audio', 'tope_pdf'] as const) {
        if (campo in entrada && !(typeof entrada[campo] === 'number' && entrada[campo] > 0)) {
          return json(route, 422, invalido(campo));
        }
      }
      const siguienteConfiguracion = { ...estado.configuracion, ...entrada } as ConfiguracionWhatsmkt;
      const malos = (['horario_1', 'horario_2'] as const).filter(
        (franja) => !horarioValido(siguienteConfiguracion[franja].inicio, siguienteConfiguracion[franja].fin),
      );
      if (malos.length > 0) return json(route, 422, errorWhatsmkt('horario_invalido', { horarios: malos }));
      const desconocida = String(siguienteConfiguracion.plantilla_nombre).match(/\{(\w+)\}/g)?.find(
        (variable) => !estado.configuracion.variables_plantilla.includes(variable.slice(1, -1)),
      );
      if (desconocida) return json(route, 422, errorWhatsmkt('variable_inexistente', { variable: desconocida }));

      estado.configuracion = { ...siguienteConfiguracion, actualizado_en: '2026-10-15T12:00:00-05:00' };
      return json(route, 200, estado.configuracion);
    }

    if (ruta === '/whatsmkt/segmentos' && metodo === 'GET') return json(route, 200, estado.segmentos);
    if (ruta === '/whatsmkt/segmentos' && metodo === 'PUT') {
      const guion = siguiente(estado.respuestas.guardarSegmentos);
      if (guion) return json(route, guion.estado, guion.cuerpo ?? estado.segmentos);

      const entrada = cuerpo as SegmentoWhatsmktEntrada[];
      const error = errorDeSegmentos(entrada);
      if (error) return json(route, 422, error);
      estado.segmentos = [...entrada]
        .sort((a, b) => (a.desde ?? -Infinity) - (b.desde ?? -Infinity))
        // A PUT that leaves the saved text out keeps the one the segment has.
        .map((segmento, orden) => ({
          ...segmento,
          orden,
          texto_guardado_id:
            segmento.texto_guardado_id ?? estado.segmentos.find((s) => s.clave === segmento.clave)?.texto_guardado_id ?? null,
        }));
      return json(route, 200, estado.segmentos);
    }

    return json(route, 404, { detail: `Sin fake para ${metodo} ${ruta}` });
  });
}

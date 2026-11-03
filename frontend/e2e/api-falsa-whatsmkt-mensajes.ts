/**
 * What the messages of the WhatsMKT settings read besides the configuration (T-WM-F1b2): the saved texts of the context
 * `whatsmkt.mensaje`, the default definition and the example rows of the text preview. It is registered AFTER `montarApiWhatsmkt`
 * and falls back to it (`route.fallback()`) for everything else, like `api-falsa-whatsmkt-campana.ts`.
 *
 * The saved texts are the generic fake of `api-falsa-textos-guardados.ts` (names unique per context, a save makes a version…), with the
 * context of WhatsMKT registered. The module's own rules (no emojis, the limit) are the backend's: a spec scripts its 400 with
 * `respuestaDeRegla`. Typed against the generated contract. Every value is invented; the phones are synthetic (900000xxx).
 */
import type { Page } from '@playwright/test';

import type { PeticionPrevisualizacion } from '../src/lib/api-texto-enriquecido';
import { definicionConColumnas } from './api-falsa-whatsmkt-campana';
import {
  apiTextosGuardados,
  manejadorTextosGuardados,
  textoFalso,
  type ApiFalsaTextosGuardados,
  type Respuesta,
  type TextoFalso,
} from './api-falsa-textos-guardados';
import { json } from './apoyo';

export const CONTEXTO_MENSAJE = 'whatsmkt.mensaje';

export interface MensajesFalsos {
  /** The saved texts and their contexts: the generic fake, with `whatsmkt.mensaje` among them. */
  textos: ApiFalsaTextosGuardados;
  /**
   * The values of the example rows the text preview answers: one array per row and, inside, the value of every column of the
   * definition (the first is the number). `null` makes the preview fail with a 400.
   */
  filas: string[][] | null;
  /** The requests the preview received, in order. */
  previas: PeticionPrevisualizacion[];
}

/** A text of the context with the content of each of its versions written out (the generic fake writes «Hola {nombre}, vN»). */
export function mensajeFalso(id: number, nombre: string, versiones: string[], parcial: Partial<Omit<TextoFalso, 'versiones'>> = {}): TextoFalso {
  const base = textoFalso({ id, nombre, contexto: CONTEXTO_MENSAJE, versiones: versiones.length, ...parcial });
  return { ...base, versiones: base.versiones.map((version, i) => ({ ...version, contenido: { texto: versiones[i] } })) };
}

export function mensajesFalsos(): MensajesFalsos {
  const textos = apiTextosGuardados();
  textos.contextos.push({ clave: CONTEXTO_MENSAJE, etiqueta: 'Mensaje de WhatsMKT', tipo: 'texto_plano' });
  textos.textos.push(
    // The two of the segments, as the seed leaves them, and two the analyst wrote: those are global.
    mensajeFalso(101, 'Preventivo inicial', ['Hola [$MACRO1$], tu cuota vence el [$MACRO2$]. INFO por [whatsapp]']),
    mensajeFalso(102, 'Tramo 2 inicial', ['Hola [$MACRO1$], tu cuota venció el [$MACRO2$]. INFO por [whatsapp]', 'Hola [$MACRO1$], ponte al día. INFO por [whatsapp]']),
    mensajeFalso(103, 'Oferta de octubre', ['Hola [$MACRO1$], tienes una oferta de octubre.']),
    mensajeFalso(104, 'Aviso de pago', ['Hola [$MACRO1$], recuerda pagar tu cuota.']),
  );
  return {
    textos,
    filas: [
      ['51900000001', 'Maria Perez', '05/10/2026'],
      ['51900000002', 'Jose Rojas', '12/10/2026'],
      ['51900000003', 'Ana Torres', '20/10/2026'],
    ],
    previas: [],
  };
}

/** The 400 the backend answers when a saved message breaks a rule of the module: the problem carries the module's own code (`codigo_contexto`). */
export function respuestaDeRegla(codigoContexto: 'mensaje_con_emoji' | 'mensaje_largo', parametros: Record<string, string | number>, detalle: string): Respuesta {
  return {
    estado: 400,
    cuerpo: {
      detail: `El texto no se puede guardar. ${detalle}`,
      codigo: 'texto_guardado_invalido',
      problemas: [
        {
          codigo: 'regla_del_contexto',
          detalle,
          ubicacion: null,
          nombre: null,
          columna: null,
          segmento: null,
          campo: 'contenido',
          codigo_contexto: codigoContexto,
          parametros,
        },
      ],
    },
  };
}

const columnaDeFila = (texto: string, i: number) => ({
  nombre: i === 0 ? 'número' : `[$MACRO${i}$]`,
  tipo: 'texto' as const,
  texto,
  largo: texto.length,
  cota: null,
  sin_cota: null,
  usa_variante: false,
  nodos: [],
  problemas: [],
});

export async function montarMensajesWhatsmkt(page: Page, estado: MensajesFalsos): Promise<void> {
  const manejarTextos = manejadorTextosGuardados(estado.textos);
  await page.route('**/api/**', async (route) => {
    const peticion = route.request();
    const url = new URL(peticion.url());
    const ruta = url.pathname.replace(/^\/api/, '');
    const metodo = peticion.method();

    if (await manejarTextos(route, ruta, metodo, url)) return;
    const definicion = /^\/definiciones-columnas\/(\d+)$/.exec(ruta);
    if (definicion && metodo === 'GET') return json(route, 200, definicionConColumnas(Number(definicion[1])));
    if (ruta === '/texto-enriquecido/previsualizacion' && metodo === 'POST') {
      estado.previas.push(JSON.parse(peticion.postData() ?? '{}') as PeticionPrevisualizacion);
      if (estado.filas === null) return json(route, 400, { detail: 'No se pudo armar la muestra', codigo: 'definicion_invalida' });
      return json(route, 200, {
        problemas: [],
        limite_largo: null,
        umbral_advertencia: null,
        disponibles: null,
        fecha_envio: null,
        filas: estado.filas.map((valores, i) => ({
          numero: i + 1,
          etiqueta: null,
          segmento: null,
          pagare: null,
          fecha_corte: null,
          excluida: null,
          columnas: valores.map(columnaDeFila),
        })),
      });
    }
    return route.fallback();
  });
}

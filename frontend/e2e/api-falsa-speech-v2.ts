/**
 * The v2 speech of MOWA MES, as a layer over `api-falsa-mowa-mes.ts` (that file is the MOWA MES
 * team's and is not touched). `montarApiSpeechV2` registers a route AFTER `montarApiMowaMes`, so it
 * runs first; it answers only what is v2 and lets everything else fall back to the module's fake.
 * The rich-text engine's fake (catalogue, validation, preview of an expression) is chained here too.
 *
 * It behaves like the backend where a spec depends on it: a v1 becomes a v2 draft with the same
 * messages (titular and date required), a v2 is saved as `expresiones` or refused with located
 * problems, a segment with nothing is refused, and a preview gives each segment's maximum length,
 * its level or the reason it has none. Every value is invented.
 */
import type { Page, Route } from '@playwright/test';

import type { LargoSegmento, PartesSpeech, VersionSpeech } from '../src/lib/api-mowa-mes';
import type { BorradorV2, ExpresionSegmentoEntrada, ProblemaSpeech } from '../src/lib/mowa-mes-speech-v2';
import type { components } from '../src/lib/contrato-api';
import { caracteresQuitados, normalizarGsm7 } from './api-falsa-gsm7';
import type { ApiFalsaMowaMes } from './api-falsa-mowa-mes';
import type { ApiFalsaTextoEnriquecido, } from './api-falsa-texto-enriquecido';
import { manejarTextoEnriquecido } from './api-falsa-texto-enriquecido';

type Esquemas = components['schemas'];
type ExpresionRespuesta = Esquemas['ExpresionSegmentoRespuesta'];
type NodoGuardado = ExpresionRespuesta['expresion']['nodos'][number];

export interface ApiFalsaSpeechV2 {
  /** Requests this layer answered, with their parsed body. */
  pedidos: Array<{ metodo: string; ruta: string; cuerpo: unknown }>;
  /** Answers to `POST /mowa-mes/speech` with `expresiones`, in order; the last one repeats. */
  respuestasCrear: Array<{ estado: number; cuerpo: unknown }>;
}

export function apiSpeechV2(): ApiFalsaSpeechV2 {
  return { pedidos: [], respuestasCrear: [] };
}

const json = (route: Route, estado: number, cuerpo: unknown) =>
  route.fulfill({ status: estado, contentType: 'application/json', body: JSON.stringify(cuerpo) });

const texto = (valor: string): NodoGuardado => ({ tipo: 'texto', valor });
const variable = (nombre: string, funciones: Array<{ nombre: string; args: Array<string | number> }> = [], obligatoria = false): NodoGuardado => ({
  tipo: 'variable',
  nombre,
  funciones,
  obligatoria,
});

/** The expressions of a v1 as the engine writes them: titular(8) + part 1 + date + part 2. */
function expresionDeSegmento(parte: PartesSpeech): ExpresionRespuesta {
  const conWhatsapp = (cadena: string): NodoGuardado[] =>
    cadena
      .split('[whatsapp]')
      .flatMap((trozo, i, todos) => [
        ...(trozo ? [texto(trozo)] : []),
        ...(i < todos.length - 1 ? [variable('whatsapp_contacto', [{ nombre: 'enlace_whatsapp', args: [] }])] : []),
      ]);
  const nodos: NodoGuardado[] = [
    variable('titular', [{ nombre: 'primeros', args: [8] }], true),
    ...conWhatsapp(parte.parte_1),
    variable('fecha_vencimiento_cuota', [{ nombre: 'formato_fecha', args: ['dd/mm/aaaa'] }], true),
    ...conWhatsapp(parte.parte_2),
  ];
  const usa = (nombre: string) => nodos.some((n) => n.tipo === 'variable' && n.nombre === nombre);
  return {
    segmento: parte.segmento,
    etiqueta: parte.etiqueta,
    dias_desde: parte.dias_desde,
    dias_hasta: parte.dias_hasta,
    expresion: { nodos },
    usa_titular: usa('titular'),
    usa_vencimiento: usa('fecha_vencimiento_cuota'),
    usa_whatsapp: usa('whatsapp_contacto'),
  };
}

/** A v2 saved version, for specs that start from one. */
export function versionV2Sintetica(base: VersionSpeech, parcial: Partial<VersionSpeech> = {}): VersionSpeech {
  return {
    id: 20,
    nombre: 'Speech v2',
    formato: 'v2',
    original: false,
    basada_en_id: base.id,
    usada: false,
    editable: true,
    creado_en: '2026-10-10T09:00:00-05:00',
    partes: [],
    expresiones: base.partes.map(expresionDeSegmento),
    ...parcial,
  };
}

function maximoDe(expresion: ExpresionRespuesta['expresion']): { maximo: number | null; sinCota: boolean } {
  let total = 0;
  for (const nodo of expresion.nodos) {
    if (nodo.tipo === 'texto') {
      total += nodo.valor.length;
      continue;
    }
    const f = nodo.funciones.map((x) => x.nombre);
    if (f.includes('primeros')) total += Number(nodo.funciones.find((x) => x.nombre === 'primeros')?.args[0] ?? 0);
    else if (f.includes('formato_fecha')) total += 10;
    else if (f.includes('enlace_whatsapp')) total += 26;
    else return { maximo: null, sinCota: true };
  }
  return { maximo: total, sinCota: false };
}

const NODOS_PROHIBIDOS = new Set(['inexistente']);

function problemasDe(expresiones: ExpresionSegmentoEntrada[]): ProblemaSpeech[] {
  const problemas: ProblemaSpeech[] = [];
  for (const e of expresiones) {
    e.expresion.nodos.forEach((nodo, indice) => {
      if (nodo.tipo === 'variable' && NODOS_PROHIBIDOS.has(nodo.nombre ?? '')) {
        problemas.push({
          segmento: e.segmento,
          campo: 'expresion',
          detalle: `La variable ${nodo.nombre} no existe`,
          codigo: 'variable_desconocida',
          catalogo: 'texto',
          ubicacion: { nodo: indice, funcion: null, parametro: null },
        });
      }
    });
  }
  return problemas;
}

/**
 * Layer the v2 speech over the module's fake. Call it after `montarApiMowaMes(page, api)`.
 * `api.versiones` is the module's own list: a v2 created here is pushed into it, so the module's
 * `GET /mowa-mes/speech` shows it.
 */
export async function montarApiSpeechV2(
  page: Page,
  api: ApiFalsaMowaMes,
  estado: ApiFalsaSpeechV2,
  motor: ApiFalsaTextoEnriquecido,
): Promise<void> {
  const manejarMotor = manejarTextoEnriquecido(motor);
  await page.route('**/api/**', async (route) => {
    const pedido = route.request();
    const url = new URL(pedido.url());
    const ruta = url.pathname.replace(/^\/api/, '');
    const metodo = pedido.method();
    const crudo = pedido.postData();
    let cuerpo: Record<string, unknown> | null = null;
    if (crudo) {
      try {
        cuerpo = JSON.parse(crudo) as Record<string, unknown>;
      } catch {
        cuerpo = null;
      }
    }

    // The engine's routes (catalogue, validation, preview of an expression).
    if (await manejarMotor(route, ruta, metodo, url)) return;

    const coincidencia = ruta.match(/^\/mowa-mes\/speech\/(\d+)\/como-v2$/);
    if (coincidencia && metodo === 'GET') {
      estado.pedidos.push({ metodo, ruta, cuerpo });
      const version = api.versiones.find((v) => v.id === Number(coincidencia[1]));
      if (!version) return json(route, 404, { detail: 'No existe la version' });
      if (version.formato === 'v2') {
        return json(route, 400, {
          detail: 'La version ya es v2: no hay nada que convertir',
          problemas: [
            { segmento: null, campo: 'formato', detalle: 'La version ya es v2', codigo: null, catalogo: null, ubicacion: null },
          ],
        });
      }
      const borrador: BorradorV2 = {
        basada_en_id: version.id,
        nombre_sugerido: `Speech ${api.versiones.length + 1}`,
        expresiones: version.partes.map(expresionDeSegmento),
        problemas: [],
      };
      return json(route, 200, borrador);
    }

    if (ruta === '/mowa-mes/speech/previsualizacion' && metodo === 'POST' && cuerpo && 'expresiones' in cuerpo) {
      estado.pedidos.push({ metodo, ruta, cuerpo });
      const expresiones = (cuerpo.expresiones ?? []) as ExpresionSegmentoEntrada[];
      const problemas = problemasDe(expresiones);
      const whatsapp = (cuerpo.whatsapp as string | null | undefined) ?? api.configuracion.whatsapp_contacto ?? null;
      const segmentos: LargoSegmento[] = [];
      for (const e of expresiones) {
        if (e.expresion.nodos.length === 0) continue;
        const guardada = {
          nodos: e.expresion.nodos.map((n) =>
            n.tipo === 'texto'
              ? texto(n.valor ?? '')
              : variable(n.nombre ?? '', (n.funciones ?? []).map((f) => ({ nombre: f.nombre, args: (f.args ?? []) as Array<string | number> }))),
          ),
        };
        const { maximo, sinCota } = maximoDe(guardada);
        const usaWhatsapp = guardada.nodos.some((n) => n.tipo === 'variable' && n.nombre === 'whatsapp_contacto');
        const etiqueta = api.versiones[0]?.partes.find((p) => p.segmento === e.segmento)?.etiqueta ?? String(e.segmento);
        segmentos.push({
          segmento: e.segmento,
          etiqueta,
          usa_whatsapp: usaWhatsapp,
          falta_whatsapp: usaWhatsapp && !whatsapp,
          largo_maximo: maximo,
          sin_maximo: sinCota
            ? { codigo: 'sin_cota_variable', detalle: 'El largo depende del dato', ubicacion: { nodo: 0, funcion: null, parametro: null } }
            : null,
          codigo: maximo === null ? null : maximo > 160 ? 'mensaje_excede_160' : maximo > 150 ? 'mensaje_excede_150' : null,
          // Normalised like the backend's (RF-MM-27); what is deleted comes from the segment's fixed text.
          ejemplo: maximo === null ? null : normalizarGsm7('Ejemplo sintético'),
          caracteres_quitados: caracteresQuitados(
            guardada.nodos.map((n) => (n.tipo === 'texto' ? (n.valor ?? '') : '')).join(' '),
          ),
        });
      }
      return json(route, 200, { whatsapp, largo_advertencia: 150, largo_maximo: 160, problemas, segmentos, campos_archivados: [] });
    }

    if (ruta === '/mowa-mes/speech' && metodo === 'POST' && cuerpo && Array.isArray(cuerpo.expresiones)) {
      estado.pedidos.push({ metodo, ruta, cuerpo });
      const guion = estado.respuestasCrear.length > 1 ? estado.respuestasCrear.shift() : estado.respuestasCrear[0];
      if (guion) return json(route, guion.estado, guion.cuerpo);
      const expresiones = cuerpo.expresiones as ExpresionSegmentoEntrada[];
      const problemas = problemasDe(expresiones);
      const base = api.versiones.find((v) => v.id === cuerpo?.basada_en_id) ?? api.versiones[0];
      const segmentosBase = base.partes.length > 0 ? base.partes : (api.versiones.find((v) => v.partes.length > 0)?.partes ?? []);
      const vacios = segmentosBase.filter((p) => !expresiones.some((e) => e.segmento === p.segmento && e.expresion.nodos.length > 0));
      if (vacios.length > 0) {
        return json(route, 400, {
          detail: 'Hay segmentos sin contenido',
          problemas: vacios.map((p) => ({
            segmento: p.segmento,
            campo: 'expresion',
            detalle: `El segmento ${p.etiqueta} no tiene contenido`,
            codigo: null,
            catalogo: null,
            ubicacion: null,
          })),
        });
      }
      if (problemas.length > 0) return json(route, 400, { detail: 'La expresion no es valida', problemas });
      const nombre = ((cuerpo.nombre as string | null) ?? '').trim() || `Speech ${api.versiones.length + 1}`;
      if (api.versiones.some((v) => v.nombre.toLowerCase() === nombre.toLowerCase())) {
        return json(route, 409, { detail: 'Ya existe una version con ese nombre', codigo: null });
      }
      const nueva: VersionSpeech = {
        id: Math.max(...api.versiones.map((v) => v.id)) + 1,
        nombre,
        formato: 'v2',
        original: false,
        basada_en_id: (cuerpo.basada_en_id as number | null) ?? null,
        usada: false,
        editable: true,
        creado_en: new Date().toISOString(),
        partes: [],
        expresiones: segmentosBase.map((p) => {
          const entrada = expresiones.find((e) => e.segmento === p.segmento)!;
          const nodos: NodoGuardado[] = entrada.expresion.nodos.map((n) =>
            n.tipo === 'texto'
              ? texto(n.valor ?? '')
              : variable(n.nombre ?? '', (n.funciones ?? []).map((f) => ({ nombre: f.nombre, args: (f.args ?? []) as Array<string | number> })), Boolean(n.obligatoria)),
          );
          const usa = (x: string) => nodos.some((n) => n.tipo === 'variable' && n.nombre === x);
          return {
            segmento: p.segmento,
            etiqueta: p.etiqueta,
            dias_desde: p.dias_desde,
            dias_hasta: p.dias_hasta,
            expresion: { nodos },
            usa_titular: usa('titular'),
            usa_vencimiento: usa('fecha_vencimiento_cuota'),
            usa_whatsapp: usa('whatsapp_contacto'),
          };
        }),
      };
      api.versiones.push(nueva);
      return json(route, 201, nueva);
    }

    const edicion = ruta.match(/^\/mowa-mes\/speech\/(\d+)$/);
    if (edicion && metodo === 'PUT' && cuerpo && Array.isArray(cuerpo.expresiones)) {
      estado.pedidos.push({ metodo, ruta, cuerpo });
      const version = api.versiones.find((v) => v.id === Number(edicion[1]));
      if (!version) return json(route, 404, { detail: 'No existe la version' });
      version.nombre = String(cuerpo.nombre);
      const entradas = cuerpo.expresiones as ExpresionSegmentoEntrada[];
      version.expresiones = version.expresiones.map((e) => {
        const nueva = entradas.find((x) => x.segmento === e.segmento);
        return nueva
          ? { ...e, expresion: { nodos: nueva.expresion.nodos.map((n) => (n.tipo === 'texto' ? texto(n.valor ?? '') : variable(n.nombre ?? '', [], Boolean(n.obligatoria)))) } }
          : e;
      });
      return json(route, 200, version);
    }

    return route.fallback();
  });
}

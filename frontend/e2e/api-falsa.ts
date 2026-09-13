/**
 * A stand-in for the REST API, driven entirely from the test.
 *
 * Every value here is invented. No sheet, name, document or phone from the
 * real data ever reaches a test (see the data rules in /AGENTS.md).
 */
import type { Page, Route } from '@playwright/test';

import type { Incidencia, Version } from '../src/lib/api';

/**
 * Fake responses are typed against the real contract, so a fake the backend
 * could never send fails to compile instead of passing a test that proves
 * nothing about the real API.
 */
export type VersionFalsa = Version;

export function version(parcial: Partial<VersionFalsa> = {}): VersionFalsa {
  return {
    id: 1,
    fecha_corte: '2026-09-10',
    version: 1,
    estado: 'terminada',
    vigente: true,
    nombre_archivo: 'SABANA_10.09.2026.xlsx',
    tamano_bytes: 3_200_000,
    hoja: 'VENCIDA',
    creado_en: '2026-09-10T08:15:00-05:00',
    procesado_en: '2026-09-10T08:15:04-05:00',
    huella_formato: 'aaaa1111',
    filas_total: 1500,
    filas_ingestadas: 1498,
    incidencias_error: 2,
    incidencias_advertencia: 31,
    incidencias_info: 12,
    motivo_fallo: null,
    ...parcial,
  };
}

export interface ApiFalsa {
  /** Versions the listing returns, newest first. */
  versiones: VersionFalsa[];
  /** Issues the table pages through. */
  incidencias: Incidencia[];
  /** Answers `POST /cargas` in order; the last one repeats. */
  respuestasSubida: Array<{ estado: number; cuerpo: unknown }>;
  /** Answers `DELETE /cargas/{id}` in order; the last one repeats. */
  respuestasEliminar: Array<{ estado: number; cuerpo?: unknown }>;
  /** Statuses `GET /cargas/{id}` walks through while following a load. */
  seguimiento: VersionFalsa[];
  /** Requests the page actually made, for asserting on the call itself. */
  pedidos: Array<{ metodo: string; url: string }>;
}

export function apiVacia(): ApiFalsa {
  return {
    versiones: [],
    incidencias: [],
    respuestasSubida: [],
    respuestasEliminar: [],
    seguimiento: [],
    pedidos: [],
  };
}

const json = (route: Route, estado: number, cuerpo: unknown) =>
  route.fulfill({ status: estado, contentType: 'application/json', body: JSON.stringify(cuerpo) });

/** Take the next scripted answer, repeating the last one once exhausted. */
function siguiente<T>(cola: T[]): T | undefined {
  return cola.length > 1 ? cola.shift() : cola[0];
}

/**
 * Route every `/api` call to `estado`. Preview serves a static build with no
 * proxy, so anything not handled here would fail loudly rather than silently
 * reaching a real server.
 */
export async function montarApi(page: Page, estado: ApiFalsa): Promise<void> {
  await page.route('**/api/**', async (route) => {
    const pedido = route.request();
    const url = new URL(pedido.url());
    const ruta = url.pathname.replace(/^\/api/, '');
    const metodo = pedido.method();
    estado.pedidos.push({ metodo, url: pedido.url() });

    if (ruta === '/health') {
      return json(route, 200, { api: true, database: true, ok: true });
    }

    if (ruta === '/cargas' && metodo === 'GET') {
      const fecha = url.searchParams.get('fecha_corte');
      const lista = fecha
        ? estado.versiones.filter((v) => v.fecha_corte === fecha)
        : estado.versiones;
      return json(route, 200, lista);
    }

    if (ruta === '/cargas' && metodo === 'POST') {
      const respuesta = siguiente(estado.respuestasSubida) ?? {
        estado: 202,
        cuerpo: { id: 99, fecha_corte: '2026-09-10', version: 2, estado: 'en_cola', versiones_identicas: [], aviso: null },
      };
      return json(route, respuesta.estado, respuesta.cuerpo);
    }

    const incidencias = ruta.match(/^\/cargas\/(\d+)\/incidencias$/);
    if (incidencias) {
      const severidad = url.searchParams.get('severidad');
      const limite = Number(url.searchParams.get('limite') ?? 50);
      const desplazamiento = Number(url.searchParams.get('desplazamiento') ?? 0);
      const filtradas = severidad
        ? estado.incidencias.filter((i) => i.severidad === severidad)
        : estado.incidencias;
      return json(route, 200, {
        total: filtradas.length,
        incidencias: filtradas.slice(desplazamiento, desplazamiento + limite),
      });
    }

    const detalle = ruta.match(/^\/cargas\/(\d+)$/);
    if (detalle && metodo === 'GET') {
      const paso = siguiente(estado.seguimiento);
      if (paso) return json(route, 200, paso);
      const encontrada = estado.versiones.find((v) => v.id === Number(detalle[1]));
      return encontrada
        ? json(route, 200, encontrada)
        : json(route, 404, { detail: `No existe la carga ${detalle[1]}` });
    }

    if (detalle && metodo === 'DELETE') {
      const respuesta = siguiente(estado.respuestasEliminar) ?? { estado: 204 };
      return respuesta.estado === 204
        ? route.fulfill({ status: 204, body: '' })
        : json(route, respuesta.estado, respuesta.cuerpo ?? {});
    }

    const vigente = ruta.match(/^\/cargas\/(\d+)\/vigente$/);
    if (vigente && metodo === 'POST') {
      const id = Number(vigente[1]);
      estado.versiones = estado.versiones.map((v) => ({
        ...v,
        vigente: v.fecha_corte === estado.versiones.find((x) => x.id === id)?.fecha_corte
          ? v.id === id
          : v.vigente,
      }));
      const elegida = estado.versiones.find((v) => v.id === id);
      return elegida ? json(route, 200, elegida) : json(route, 404, { detail: 'no existe' });
    }

    return json(route, 404, { detail: `sin ruta falsa para ${metodo} ${ruta}` });
  });
}

/** A synthetic sheet to attach to the upload field; never a real one. */
export const ARCHIVO_SINTETICO = {
  name: 'SABANA_10.09.2026.xlsx',
  mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  buffer: Buffer.from('contenido sintetico de prueba'),
};

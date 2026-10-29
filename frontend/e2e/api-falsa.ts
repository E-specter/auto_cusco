/**
 * A stand-in for the REST API, driven entirely from the test.
 *
 * Every value here is invented. No sheet, name, document or phone from the
 * real data ever reaches a test (see the data rules in /AGENTS.md).
 */
import type { Page, Route } from '@playwright/test';

import type {
  Campos,
  Incidencia,
  Resumen,
  Revision,
  SeleccionGuardada,
  Version,
} from '../src/lib/api';
import type { ConfiguracionSupervision, ConfiguracionSupervisionEntrada } from '../src/lib/api-supervision';
import type { DiaNoLaborable, ExcepcionEntrada } from '../src/lib/api-calendario';
import { json, siguiente } from './apoyo';

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
  pedidos: Array<{ metodo: string; url: string; cuerpo?: string | null }>;
  /** The portfolio catalogue `GET /cartera/campos` returns. */
  campos: Campos;
  /** Answers `GET /cartera/resumen`, given the request URL. */
  resumen: (url: URL) => { estado: number; cuerpo: unknown };
  /** Answers `GET /cartera/valores` (the list of values of a text field), given the request URL. */
  valores: (url: URL) => { estado: number; cuerpo: unknown };
  /** Products `GET /cartera` pages through. */
  productos: Array<Record<string, unknown>>;
  /** Saved selections `GET /selecciones` lists. */
  selecciones: SeleccionGuardada[];
  /** Answers `POST /selecciones/revision`. */
  revision: Revision;
  /** Answers `POST /selecciones` in order; the last one repeats. */
  respuestasCrearSeleccion: Array<{ estado: number; cuerpo: unknown }>;
  /**
   * Extra routes a feature's own fake contributes (the rich-text engine,
   * saved column definitions), asked in order before the 404.
   */
  manejadores?: Manejador[];
}

/**
 * A feature fake's routes: answers the request and returns `true`, or returns
 * `false` to let the next handler try (interface rules §9.3).
 */
export type Manejador = (route: Route, ruta: string, metodo: string, url: URL) => Promise<boolean>;

/** A synthetic catalogue: the operational fields plus one text field. */
export function camposSinteticos(): Campos {
  const base = { adicional: false, etiqueta: null, archivado: false };
  const numero = { ...base, tipo: 'numero', operadores: ['igual', 'mayor', 'menor', 'entre', 'en', 'no_en', 'vacio', 'no_vacio'] };
  const texto = { ...base, tipo: 'texto', operadores: ['igual', 'distinto', 'en', 'no_en', 'contiene', 'vacio', 'no_vacio'] };
  return {
    pagare: texto,
    segmento_financiero: texto,
    region: texto,
    dias_atraso: numero,
    saldo_capital_pendiente: numero,
    monto_cuota: numero,
  };
}

const metricas = (cuentas: number, capital: string) => ({
  cuentas,
  capital_total: capital,
  cuota_minima: '85.10',
  cuota_maxima: '4210.75',
  cuentas_por_segmento: {},
  adicionales: {},
});

/**
 * A summary that honours the request: 3 200 products meet any filter, and the
 * selection block exists only when a count was asked for (RF-08).
 */
export function resumenSintetico(url: URL, disponibles = 3200): Resumen {
  const cantidad = url.searchParams.get('cantidad');
  const solicitados = cantidad ? Number(cantidad) : null;
  const segmento = url.searchParams.get('segmento');
  const segmentacion = (a: number, b: number) =>
    segmento
      ? {
          campo: segmento,
          grupos: [
            { valor: '1. Preventiva', cuentas: a, capital: '120000.00' },
            { valor: null, cuentas: b, capital: '5000.50' },
          ],
        }
      : null;
  return {
    disponibles,
    solicitados,
    suficiente: solicitados === null || solicitados <= disponibles,
    // The universe carries an amount no JavaScript number can hold exactly.
    universo: { metricas: metricas(disponibles, '9007199254740993.01'), segmentacion: segmentacion(3000, 200) },
    seleccion: solicitados
      ? {
          metricas: metricas(Math.min(solicitados, disponibles), '4812345.67'),
          segmentacion: segmentacion(Math.min(solicitados, disponibles), 0),
        }
      : null,
  };
}

/** Synthetic products: no names, documents or phones, ever. */
export function productosSinteticos(n: number): Array<Record<string, unknown>> {
  return Array.from({ length: n }, (_, i) => ({
    pagare: String(100 + i).padStart(18, '0'),
    segmento_financiero: '1. Preventiva',
    region: 'REGION SINTETICA',
    dias_atraso: i % 90,
    saldo_capital_pendiente: `${1500 + i}.50`,
    monto_cuota: '120.00',
  }));
}

export function seleccionGuardada(parcial: Partial<SeleccionGuardada> = {}): SeleccionGuardada {
  return {
    id: 1,
    nombre: 'Preventiva mayor saldo',
    filtros: ['segmento_financiero:igual:1. Preventiva'],
    orden: '-saldo_capital_pendiente',
    cantidad: 500,
    indicadores: [],
    creado_en: '2026-09-10T08:15:00-05:00',
    actualizado_en: '2026-09-10T08:15:00-05:00',
    aplicable: true,
    problemas: [],
    ...parcial,
  };
}

/**
 * The default answer of `GET /cartera/valores`: the field has more distinct values than the threshold, so no list
 * is offered and the filter keeps its text area. A spec that is not about the list never notices it.
 */
export function valoresSobreUmbral(url: URL): ValoresFalsos {
  return { campo: url.searchParams.get('campo') ?? '', umbral: 100, ofrece_lista: false, valores: [] };
}

export interface ValoresFalsos {
  campo: string;
  umbral: number;
  ofrece_lista: boolean;
  valores: Array<{ valor: string | null; cantidad: number }>;
}

export function apiVacia(): ApiFalsa {
  return {
    versiones: [],
    incidencias: [],
    respuestasSubida: [],
    respuestasEliminar: [],
    seguimiento: [],
    pedidos: [],
    campos: camposSinteticos(),
    resumen: (url) => ({ estado: 200, cuerpo: resumenSintetico(url) }),
    valores: (url) => ({ estado: 200, cuerpo: valoresSobreUmbral(url) }),
    productos: productosSinteticos(120),
    selecciones: [],
    revision: { aplicable: true, problemas: [] },
    respuestasCrearSeleccion: [],
  };
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
    estado.pedidos.push({ metodo, url: pedido.url(), cuerpo: pedido.postData() });

    if (ruta === '/health') {
      return json(route, 200, { api: true, database: true, ok: true });
    }

    if (ruta === '/cartera/campos') return json(route, 200, estado.campos);

    if (ruta === '/cartera/valores') {
      const respuesta = estado.valores(url);
      return json(route, respuesta.estado, respuesta.cuerpo);
    }

    if (ruta === '/cartera/resumen') {
      const respuesta = estado.resumen(url);
      return json(route, respuesta.estado, respuesta.cuerpo);
    }

    if (ruta === '/cartera') {
      const limite = Number(url.searchParams.get('limite') ?? 50);
      const desplazamiento = Number(url.searchParams.get('desplazamiento') ?? 0);
      return json(route, 200, {
        total: estado.productos.length,
        limite,
        desplazamiento,
        suficiente: estado.productos.length >= limite + desplazamiento,
        productos: estado.productos.slice(desplazamiento, desplazamiento + limite),
      });
    }

    if (ruta === '/selecciones' && metodo === 'GET') return json(route, 200, estado.selecciones);

    if (ruta === '/selecciones/revision') return json(route, 200, estado.revision);

    if (ruta === '/selecciones' && metodo === 'POST') {
      const entrada = JSON.parse(pedido.postData() ?? '{}') as Partial<SeleccionGuardada>;
      const respuesta = siguiente(estado.respuestasCrearSeleccion) ?? {
        estado: 201,
        cuerpo: seleccionGuardada({ ...entrada, id: 99 }),
      };
      if (respuesta.estado === 201) estado.selecciones.push(respuesta.cuerpo as SeleccionGuardada);
      return json(route, respuesta.estado, respuesta.cuerpo);
    }

    const seleccion = ruta.match(/^\/selecciones\/(\d+)$/);
    if (seleccion && metodo === 'PUT') {
      const id = Number(seleccion[1]);
      const entrada = JSON.parse(pedido.postData() ?? '{}') as Partial<SeleccionGuardada>;
      const actualizada = seleccionGuardada({ ...entrada, id });
      estado.selecciones = estado.selecciones.map((s) => (s.id === id ? actualizada : s));
      return json(route, 200, actualizada);
    }
    if (seleccion && metodo === 'DELETE') {
      estado.selecciones = estado.selecciones.filter((s) => s.id !== Number(seleccion[1]));
      return route.fulfill({ status: 204, body: '' });
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

    for (const manejar of estado.manejadores ?? []) {
      if (await manejar(route, ruta, metodo, url)) return;
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

// ---- Default supervisors and working-day calendar (shared by every connector) ----------------------------

type RespuestaGuionada = { estado: number; cuerpo?: unknown };

/** RF-02: 9 digits starting with 9. */
export const esTelefono = (valor: string) => /^9\d{8}$/.test(valor);

/** Three law holidays, one of them withdrawn this year, and one added day. */
export function diasSinteticos(anio: number): DiaNoLaborable[] {
  return [
    { fecha: `${anio}-01-01`, descripcion: 'Año Nuevo', origen: 'ley', retirado: false },
    { fecha: `${anio}-05-01`, descripcion: 'Día del Trabajo', origen: 'ley', retirado: false },
    { fecha: `${anio}-06-07`, descripcion: 'Batalla de Arica', origen: 'ley', retirado: true },
    { fecha: `${anio}-12-24`, descripcion: 'Día no laborable sintético', origen: 'agregado', retirado: false },
  ];
}

/** What `/supervisores` and `/calendario/*` answer from; any connector's fake can carry it. */
export interface EstadoSupervisionCalendario {
  supervision: ConfiguracionSupervision;
  /** Non-working days per year; missing years get `diasSinteticos`. */
  dias: Map<number, DiaNoLaborable[]>;
  siguienteDia: string;
  /** Scripted answers, in order; the last one repeats. Empty means "behave". */
  respuestas: { guardarSupervision: RespuestaGuionada[]; crearExcepcion: RespuestaGuionada[] };
}

export function estadoSupervisionCalendario(): EstadoSupervisionCalendario {
  return {
    supervision: {
      procedencias: ['Procedencia A', 'Procedencia B'],
      supervisores: [
        { numero: '900000101', procedencia: 'Procedencia A', documento: '00000001' },
        { numero: '900000102', procedencia: 'Procedencia B', documento: '00000002' },
      ],
    },
    dias: new Map(),
    siguienteDia: '2026-09-14',
    respuestas: { guardarSupervision: [], crearExcepcion: [] },
  };
}

/** Same numbering rule as the backend: one sequence, procedencia by procedencia. */
function conDocumentos(entrada: ConfiguracionSupervisionEntrada): ConfiguracionSupervision {
  let secuencia = 0;
  const documentos = new Map<number, string>();
  entrada.procedencias.forEach((procedencia) => {
    entrada.supervisores.forEach((s, indice) => {
      if (s.procedencia === procedencia) documentos.set(indice, String(++secuencia).padStart(8, '0'));
    });
  });
  return {
    procedencias: entrada.procedencias,
    supervisores: entrada.supervisores.map((s, i) => ({ ...s, documento: documentos.get(i) ?? '' })),
  };
}

/** The routes of `/supervisores` and `/calendario/*`; `false` for any other, so the next handler tries. */
export function manejadorSupervisionCalendario(estado: EstadoSupervisionCalendario): Manejador {
  return async (route, ruta, metodo, url) => {
    const cuerpo = (): unknown => JSON.parse(route.request().postData() ?? 'null');

    if (ruta === '/supervisores' && metodo === 'GET') return (await json(route, 200, estado.supervision), true);
    if (ruta === '/supervisores' && metodo === 'PUT') {
      const guion = siguiente(estado.respuestas.guardarSupervision);
      if (guion) return (await json(route, guion.estado, guion.cuerpo ?? {}), true);
      // Same checks as the API, after trimming: procedencias present, unique and
      // named; every supervisor's number valid and its procedencia listed.
      const recibida = cuerpo() as ConfiguracionSupervisionEntrada;
      const entrada: ConfiguracionSupervisionEntrada = {
        procedencias: recibida.procedencias.map((p) => p.trim()),
        supervisores: recibida.supervisores.map((s) => ({ numero: s.numero.trim(), procedencia: s.procedencia.trim() })),
      };
      const claves = entrada.procedencias.map((p) => p.toLowerCase());
      if (claves.length === 0 || claves.some((p) => p === '') || new Set(claves).size !== claves.length) {
        return (await json(route, 400, { detail: 'Las procedencias deben tener nombre y no repetirse' }), true);
      }
      const desconocido = entrada.supervisores.find((s) => !entrada.procedencias.includes(s.procedencia));
      if (desconocido) {
        return (await json(route, 400, { detail: `La procedencia ${desconocido.procedencia} no esta en la lista` }), true);
      }
      const invalidoTelefono = entrada.supervisores.find((s) => !esTelefono(s.numero));
      if (invalidoTelefono) {
        return (await json(route, 400, { detail: `El numero ${invalidoTelefono.numero} no cumple RF-02` }), true);
      }
      estado.supervision = conDocumentos(entrada);
      return (await json(route, 200, estado.supervision), true);
    }

    if (ruta === '/calendario/feriados' && metodo === 'GET') {
      const anio = Number(url.searchParams.get('anio') ?? 2026);
      if (!estado.dias.has(anio)) estado.dias.set(anio, diasSinteticos(anio));
      return (await json(route, 200, { anio, dias: estado.dias.get(anio) }), true);
    }
    if (ruta === '/calendario/siguiente-dia-gestionable') {
      return (await json(route, 200, { desde: url.searchParams.get('desde') ?? '2026-09-13', fecha: estado.siguienteDia }), true);
    }
    if (ruta === '/calendario/excepciones' && metodo === 'POST') {
      const guion = siguiente(estado.respuestas.crearExcepcion);
      if (guion) return (await json(route, guion.estado, guion.cuerpo ?? {}), true);
      const recibida = cuerpo() as ExcepcionEntrada;
      const entrada = { ...recibida, descripcion: recibida.descripcion.trim() };
      const anio = Number(entrada.fecha.slice(0, 4));
      const dias = estado.dias.get(anio) ?? diasSinteticos(anio);
      const delDia = dias.find((d) => d.fecha === entrada.fecha);
      // The rule decides what an exception can mean: withdraw only a law holiday,
      // add only a day that is not one; a date already carrying one is a 409.
      if (entrada.tipo === 'retirado' && delDia?.origen !== 'ley') {
        return (await json(route, 400, { detail: 'Solo se retira un feriado de ley' }), true);
      }
      if (entrada.tipo === 'agregado' && delDia?.origen === 'ley') {
        return (await json(route, 400, { detail: 'La fecha ya es un feriado de ley' }), true);
      }
      if (delDia && (delDia.origen === 'agregado' || delDia.retirado)) {
        return (await json(route, 409, { detail: 'La fecha ya tiene una excepcion' }), true);
      }
      estado.dias.set(
        anio,
        entrada.tipo === 'retirado'
          ? dias.map((d) => (d.fecha === entrada.fecha ? { ...d, retirado: true } : d))
          : [...dias, { fecha: entrada.fecha, descripcion: entrada.descripcion, origen: 'agregado', retirado: false }],
      );
      return (await json(route, 201, { ...entrada, creado_en: '2026-09-13T12:00:00-05:00' }), true);
    }
    const excepcion = ruta.match(/^\/calendario\/excepciones\/(\d{4}-\d{2}-\d{2})$/);
    if (excepcion && metodo === 'DELETE') {
      const fecha = excepcion[1];
      const anio = Number(fecha.slice(0, 4));
      const dias = estado.dias.get(anio) ?? diasSinteticos(anio);
      if (!dias.some((d) => d.fecha === fecha && (d.origen === 'agregado' || d.retirado))) {
        return (await json(route, 404, { detail: `No hay una excepcion el ${fecha}` }), true);
      }
      estado.dias.set(
        anio,
        dias
          .filter((d) => !(d.fecha === fecha && d.origen === 'agregado'))
          .map((d) => (d.fecha === fecha ? { ...d, retirado: false } : d)),
      );
      return (await route.fulfill({ status: 204, body: '' }), true);
    }

    return false;
  };
}

/** A fake of just these two screens: `/health`, their routes, and a loud 404 for anything else. */
export interface ApiFalsaSupervisionCalendario extends EstadoSupervisionCalendario {
  /** When true, every call fails at the network level. */
  sinRed: boolean;
  /** Requests the page made, with their JSON bodies, for asserting on the call. */
  pedidos: Array<{ metodo: string; ruta: string; cuerpo: unknown }>;
}

export function apiSupervisionCalendario(): ApiFalsaSupervisionCalendario {
  return { ...estadoSupervisionCalendario(), sinRed: false, pedidos: [] };
}

export async function montarApiSupervisionCalendario(page: Page, estado: ApiFalsaSupervisionCalendario): Promise<void> {
  const rutas = manejadorSupervisionCalendario(estado);
  await page.route('**/api/**', async (route) => {
    const pedido = route.request();
    const url = new URL(pedido.url());
    const ruta = url.pathname.replace(/^\/api/, '');
    const metodo = pedido.method();
    const texto = pedido.postData();
    estado.pedidos.push({ metodo, ruta: `${ruta}${url.search}`, cuerpo: texto ? JSON.parse(texto) : null });

    if (estado.sinRed) return route.abort('connectionrefused');
    if (ruta === '/health') return json(route, 200, { api: true, database: true, ok: true });
    if (await rutas(route, ruta, metodo, url)) return;
    return json(route, 404, { detail: `sin ruta falsa para ${metodo} ${ruta}` });
  });
}

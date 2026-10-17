/**
 * A stand-in for `/archivos-carga` (B12), driven entirely from the test.
 *
 * It answers the three routes the "Generar carga" screen uses and keeps every body it received, so a
 * spec can assert on exactly what the screen asked for. The numbers close the way the backend's do:
 * the preview evaluates a sample of at most 20 products, `generados + excluidos` is what it
 * evaluated, and `suficiente` speaks of the whole selection and says nothing about exclusions. The
 * download carries the file and its `X-Carga-*` summary. Typed against the generated contract, so a
 * fake the backend could never send fails to compile. All data is invented.
 *
 * It is a *handler* so it chains with the other fakes (`api.manejadores = [...]` in `api-falsa.ts`).
 */
import type { Route } from '@playwright/test';

import type { FormatoDisponible, OpcionFormato, PeticionGeneracion, PrevisualizacionCarga } from '../src/lib/generar-carga';
import type { Manejador } from './api-falsa';

export type Respuesta = { estado: number; cuerpo?: unknown };

const RUTA = '/archivos-carga';
/** `FILAS_DE_MUESTRA` of the backend. */
const FILAS_DE_MUESTRA = 20;

type Error = PrevisualizacionCarga['errores'][number];
type Exclusion = PrevisualizacionCarga['exclusiones'][number];

export interface ApiFalsaArchivosCarga {
  /** What `GET /formatos` lists. */
  formatos: FormatoDisponible[];
  /** Products the selection holds (what `disponibles` says). */
  disponibles: number;
  /**
   * Ids of the definitions that segment and leave out products with no segment. The backend only excludes
   * for that reason, so a definition not listed here never reports exclusions, whatever the fields below say.
   */
  segmentadas: number[];
  /** Column errors the sample reports. */
  errores: Error[];
  /** Products of the sample left out for lack of a segment; their detail is listed. */
  exclusiones: Exclusion[];
  /** Products left out of the whole file (the download's `X-Carga-Excluidos`). */
  excluidosEnLaCarga: number;
  /** Name of the generated file. */
  nombreArchivo: string;
  /** Scripted answers, in order; the last one repeats. Empty means "behave". */
  respuestas: { previsualizar: Respuesta[]; generar: Respuesta[] };
  /**
   * When set, the download waits for it before answering, so a spec can cancel it mid-way or press the
   * button twice. Call `liberar` to let it go.
   */
  compuerta: Promise<void> | null;
  /**
   * Holds the *next* preview (and only that one) until it opens, so a spec can send a newer one
   * meanwhile and check that the old answer, arriving late, does not overwrite it.
   */
  compuertaPrevia: Promise<void> | null;
  /** When true, every call fails at the network level. */
  sinRed: boolean;
  /** What the screen sent, in order, with the JSON body already read. */
  pedidos: Array<{ metodo: string; ruta: string; cuerpo: PeticionGeneracion | null }>;
}

/** The options B12 announces, copied from the backend's constants. */
export function formatosSinteticos(): FormatoDisponible[] {
  const delimitador: OpcionFormato = {
    nombre: 'delimitador',
    tipo: 'texto',
    defecto: ',',
    sugeridos: [',', ';', '\t', '|'],
    minimo: 1,
    maximo: 1,
  };
  const codificacion: OpcionFormato = {
    nombre: 'codificacion',
    tipo: 'texto',
    defecto: 'utf-8',
    sugeridos: ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252'],
    minimo: null,
    maximo: null,
  };
  const conCabeceras: OpcionFormato = { nombre: 'con_cabeceras', tipo: 'booleano', defecto: true, sugeridos: null, minimo: null, maximo: null };
  const hoja: OpcionFormato = { nombre: 'hoja', tipo: 'texto', defecto: 'Carga', sugeridos: null, minimo: null, maximo: 31 };
  const sangria: OpcionFormato = { nombre: 'sangria', tipo: 'entero', defecto: null, sugeridos: null, minimo: 0, maximo: 8 };
  return [
    { formato: 'xlsx', extension: 'xlsx', opciones: [conCabeceras, hoja] },
    { formato: 'csv', extension: 'csv', opciones: [delimitador, codificacion, conCabeceras] },
    { formato: 'json', extension: 'json', opciones: [codificacion, sangria] },
  ];
}

export function apiArchivosCarga(): ApiFalsaArchivosCarga {
  return {
    formatos: formatosSinteticos(),
    disponibles: 3200,
    segmentadas: [],
    errores: [],
    exclusiones: [],
    excluidosEnLaCarga: 0,
    nombreArchivo: 'sms_preventivo.xlsx',
    respuestas: { previsualizar: [], generar: [] },
    compuerta: null,
    compuertaPrevia: null,
    sinRed: false,
    pedidos: [],
  };
}

/** A gate to hold a download and a function to open it. */
export function crearCompuerta(): { compuerta: Promise<void>; liberar: () => void } {
  let liberar = () => {};
  const compuerta = new Promise<void>((resolver) => {
    liberar = resolver;
  });
  return { compuerta, liberar };
}

/** Synthetic rows for the sample; pagares are 900000xxx and nothing here is a real person. */
function filasSinteticas(cantidad: number): Array<Record<string, unknown>> {
  return Array.from({ length: cantidad }, (_, i) => ({
    anexo: 1010,
    numero: `5190000${String(i).padStart(4, '0')}`,
    mensaje: `Estimado ZZPRUEBA${i}, su cuota vence pronto`,
  }));
}

/** Whether the definition of the request is one that segments and so can leave products out. */
const excluye = (estado: ApiFalsaArchivosCarga, peticion: PeticionGeneracion): boolean =>
  peticion.definicion_guardada ? estado.segmentadas.includes(peticion.definicion_guardada.id) : false;

/** The preview the screen shows for `peticion`, closing the numbers the way the backend does. */
export function previsualizacionSintetica(estado: ApiFalsaArchivosCarga, peticion: PeticionGeneracion): PrevisualizacionCarga {
  const muestra = Math.min(peticion.cantidad, FILAS_DE_MUESTRA);
  const evaluados = Math.min(estado.disponibles, muestra);
  const excluidos = excluye(estado, peticion) ? Math.min(estado.exclusiones.length, evaluados) : 0;
  const generados = evaluados - excluidos;
  const extension = peticion.formato;
  return {
    nombre_archivo: estado.nombreArchivo.replace(/\.\w+$/, `.${extension}`),
    cabeceras: ['anexo', 'numero', 'mensaje'],
    filas: filasSinteticas(generados),
    disponibles: estado.disponibles,
    solicitados: peticion.cantidad,
    generados,
    excluidos,
    suficiente: estado.disponibles >= peticion.cantidad,
    completa: estado.errores.length === 0,
    errores: estado.errores,
    exclusiones: estado.exclusiones.slice(0, excluidos),
  };
}

const json = (route: Route, estado: number, cuerpo: unknown) =>
  route.fulfill({ status: estado, contentType: 'application/json', body: JSON.stringify(cuerpo) });

function siguiente(cola: Respuesta[]): Respuesta | undefined {
  return cola.length > 1 ? cola.shift() : cola[0];
}

const TIPOS = { xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', csv: 'text/csv', json: 'application/json' };

export function manejadorArchivosCarga(estado: ApiFalsaArchivosCarga): Manejador {
  return async (route, ruta, metodo) => {
    const camino = ruta.split('?')[0];
    if (camino !== RUTA && !camino.startsWith(`${RUTA}/`)) return false;

    if (estado.sinRed) {
      await route.abort('failed');
      return true;
    }

    const texto = route.request().postData();
    const cuerpo = texto ? (JSON.parse(texto) as PeticionGeneracion) : null;
    estado.pedidos.push({ metodo, ruta: camino, cuerpo });

    if (camino === `${RUTA}/formatos` && metodo === 'GET') {
      await json(route, 200, estado.formatos);
      return true;
    }

    if (camino === `${RUTA}/previsualizacion` && metodo === 'POST') {
      const espera = estado.compuertaPrevia;
      estado.compuertaPrevia = null;
      if (espera) await espera;
      try {
        const guionada = siguiente(estado.respuestas.previsualizar);
        if (guionada) {
          await json(route, guionada.estado, guionada.cuerpo ?? {});
          return true;
        }
        await json(route, 200, previsualizacionSintetica(estado, cuerpo!));
      } catch {
        /* The screen replaced this preview with a newer one and dropped the connection. */
      }
      return true;
    }

    if (camino === RUTA && metodo === 'POST') {
      if (estado.compuerta) await estado.compuerta;
      const guionada = siguiente(estado.respuestas.generar);
      try {
        if (guionada) {
          await json(route, guionada.estado, guionada.cuerpo ?? {});
          return true;
        }
        const pedida = cuerpo!;
        const excluidosEnLaCarga = excluye(estado, pedida) ? estado.excluidosEnLaCarga : 0;
        const generados = Math.min(estado.disponibles, pedida.cantidad) - excluidosEnLaCarga;
        const extension = pedida.formato;
        const nombre = estado.nombreArchivo.replace(/\.\w+$/, `.${extension}`);
        await route.fulfill({
          status: 200,
          headers: {
            'content-type': TIPOS[extension],
            'content-disposition': `attachment; filename="${nombre}"`,
            'x-carga-generados': String(generados),
            'x-carga-disponibles': String(estado.disponibles),
            'x-carga-solicitados': String(pedida.cantidad),
            'x-carga-suficiente': estado.disponibles >= pedida.cantidad ? '1' : '0',
            'x-carga-errores': String(estado.errores.length),
            'x-carga-excluidos': String(excluidosEnLaCarga),
          },
          body: `archivo sintetico de ${generados} filas`,
        });
      } catch {
        /* The screen cancelled and dropped the connection: nobody is left to answer. */
      }
      return true;
    }

    return false;
  };
}

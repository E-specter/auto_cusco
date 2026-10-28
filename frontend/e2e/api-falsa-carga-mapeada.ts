/**
 * The upload in two steps against an intercepted API (T-MAP-F2): the mapper's catalogue, the drafts, the
 * re-reading, the validation and `POST /cargas/desde-borrador`. A confirmation answers like `POST /cargas`
 * did (`api.respuestasSubida`) unless a test queues its own. Every file, header and field is synthetic.
 */
import { expect, type Page, type Route } from '@playwright/test';

import type { components } from '../src/lib/contrato-api';
import type { ApiFalsa, Manejador } from './api-falsa';
import {
  CAMPOS_SINTETICOS,
  analisisSintetico,
  columna,
  manejarMapeador,
  type Analisis,
  type ApiFalsaMapeador,
} from './api-falsa-mapeador';

type Esquemas = components['schemas'];
type Respuesta = { estado: number; cuerpo?: unknown };

/** A sheet whose columns the reader already relates to the fields: the everyday case. */
export const ANALISIS_TODO_COINCIDE: Analisis = analisisSintetico([
  columna(0, 'Pagare', 'coincide', 'pagare'),
  columna(1, 'Titular', 'coincide', 'titular'),
  columna(2, 'Telefono', 'recordado', 'telefono'),
]);

export interface ApiFalsaCargaMapeada {
  /** What `POST /mapeador/{catalogo}/borradores` reads from the file. */
  analisis: Analisis;
  /** Refusals of the draft's creation, in order; once spent, the creation succeeds. */
  erroresBorrador: Respuesta[];
  /** Refusals of the re-reading, in order; once spent, it re-reads. */
  erroresAnalisis: Respuesta[];
  /** Answers of `POST /cargas/desde-borrador`, in order; once spent, the load's own (`respuestasSubida`). */
  respuestasConfirmar: Respuesta[];
  /** The draft no longer exists: validating it answers 404 `borrador_no_encontrado`. */
  borradorPerdido: boolean;
  /** Reads the file of a re-reading gives back, by the options asked for. */
  analisisPara: (opciones: Record<string, string>) => Analisis;
  /** What the page asked for, to assert on the calls themselves. */
  borradoresCreados: string[];
  reanalisis: Array<Record<string, string>>;
  confirmaciones: Array<Esquemas['ConfirmacionEntrada']>;
  descartados: number[];
  mapeador: ApiFalsaMapeador;
}

export function codigoDeRechazo(estado: number, codigo: string, datos: Record<string, unknown> = {}): Respuesta {
  return { estado, cuerpo: { detail: `Rechazo de prueba: ${codigo}`, codigo, ...datos } };
}

const json = (route: Route, status: number, body: unknown) =>
  route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

/**
 * Chains the two-step upload's routes onto `api` and returns the state to steer and inspect them. The
 * validation route is the mapper's own, so a mapping is judged by the same rules as on its test page.
 */
export function conCargaMapeada(api: ApiFalsa, parcial: Partial<ApiFalsaCargaMapeada> = {}): ApiFalsaCargaMapeada {
  const analisis = parcial.analisis ?? ANALISIS_TODO_COINCIDE;
  const estado: ApiFalsaCargaMapeada = {
    analisis,
    erroresBorrador: [],
    erroresAnalisis: [],
    respuestasConfirmar: [],
    borradorPerdido: false,
    analisisPara: () => estado.analisis,
    borradoresCreados: [],
    reanalisis: [],
    confirmaciones: [],
    descartados: [],
    mapeador: { analisis, pedidos: [] },
    ...parcial,
  };

  const catalogo: Esquemas['CatalogoMapeadorRespuesta'] = {
    id: 'sabana_vencida',
    // A field created from a draft is in the catalogue the next draft starts from.
    campos: estado.mapeador.catalogo ?? CAMPOS_SINTETICOS,
    codificaciones: ['utf-8', 'latin-1', 'cp1252'],
    separadores: [';', '\t', ','],
  };

  const manejador: Manejador = async (route, ruta, metodo) => {
    if (metodo === 'GET' && ruta === '/mapeador/catalogos/sabana_vencida') return (await json(route, 200, catalogo), true);

    if (metodo === 'POST' && ruta === '/mapeador/sabana_vencida/borradores') {
      estado.borradoresCreados.push(route.request().postData() ?? '');
      const rechazo = estado.erroresBorrador.shift();
      if (rechazo) return (await json(route, rechazo.estado, rechazo.cuerpo), true);
      estado.mapeador.analisis = estado.analisis;
      return (await json(route, 201, estado.analisis), true);
    }

    if (metodo === 'POST' && /^\/mapeador\/borradores\/\d+\/analisis$/.test(ruta)) {
      const opciones = JSON.parse(route.request().postData() ?? '{}') as Record<string, string>;
      estado.reanalisis.push(opciones);
      const rechazo = estado.erroresAnalisis.shift();
      if (rechazo) return (await json(route, rechazo.estado, rechazo.cuerpo), true);
      estado.mapeador.analisis = estado.analisisPara(opciones);
      return (await json(route, 200, estado.mapeador.analisis), true);
    }

    if (metodo === 'POST' && /^\/mapeador\/borradores\/\d+\/validacion$/.test(ruta) && estado.borradorPerdido) {
      const { cuerpo } = codigoDeRechazo(404, 'borrador_no_encontrado');
      return (await json(route, 404, cuerpo), true);
    }

    const borrador = ruta.match(/^\/mapeador\/borradores\/(\d+)$/);
    if (metodo === 'DELETE' && borrador) {
      estado.descartados.push(Number(borrador[1]));
      return (await route.fulfill({ status: 204, body: '' }), true);
    }

    if (metodo === 'POST' && ruta === '/cargas/desde-borrador') {
      estado.confirmaciones.push(JSON.parse(route.request().postData() ?? '{}'));
      const propia = estado.respuestasConfirmar.shift();
      const carga = propia ?? api.respuestasSubida[0] ?? {
        estado: 202,
        cuerpo: { id: 99, fecha_corte: '2026-09-10', version: 2, estado: 'en_cola', versiones_identicas: [], aviso: null },
      };
      if (!propia && api.respuestasSubida.length > 1) api.respuestasSubida.shift();
      return (await json(route, carga.estado, carga.cuerpo), true);
    }

    return false;
  };

  api.manejadores = [...(api.manejadores ?? []), manejador, manejarMapeador(estado.mapeador)];
  return estado;
}

/** Step 1 to step 2 to the load: what «Registrar versión» was before the header mapper. */
export async function confirmarCarga(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'Continuar' }).click();
  const confirmar = page.getByRole('button', { name: 'Confirmar y cargar' });
  await expect(confirmar).toBeEnabled();
  await confirmar.click();
}

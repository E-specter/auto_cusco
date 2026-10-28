/**
 * The additional fields of the catalogue (T-CA-F2): the list and the change of one, as the backend answers
 * them (`GET` and `PATCH …/campos-adicionales`, T-CA-B2). A name is unique among all of them, archived ones
 * included, and the technical name never changes. Every name is synthetic.
 */
import type { Route } from '@playwright/test';

import type { components } from '../src/lib/contrato-api';
import type { Manejador } from './api-falsa';
import { campoAdicional } from './api-falsa-mapeador';

type Esquemas = components['schemas'];
export type CampoAdicionalFalso = Esquemas['CampoAdicionalRespuesta'];

export interface ApiFalsaAdicionales {
  campos: CampoAdicionalFalso[];
  /** What the page asked to change, in order. */
  cambios: Array<{ nombre: string; cuerpo: Esquemas['CambioCampoAdicionalEntrada'] }>;
  /** Refusals of the next changes, in order; once spent, the change is made. */
  rechazos: Array<{ estado: number; cuerpo: unknown }>;
  /** The list cannot be read. */
  sinLista: boolean;
  /** How many times the list was read. */
  lecturas: number;
}

export const adicionalFalso = (nombre: string, nombreLegible: string, parcial: Partial<CampoAdicionalFalso> = {}): CampoAdicionalFalso => ({
  nombre,
  nombre_legible: nombreLegible,
  tipo: 'texto',
  encabezado_origen: nombreLegible.toLowerCase().replace(/[^a-z0-9]+/g, '_'),
  archivado: false,
  ...parcial,
});

export function apiAdicionales(campos: CampoAdicionalFalso[] = []): ApiFalsaAdicionales {
  return { campos, cambios: [], rechazos: [], sinLista: false, lecturas: 0 };
}

const json = (route: Route, status: number, body: unknown) =>
  route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

const normalizar = (texto: string) => texto.normalize('NFD').replace(/\p{M}/gu, '').trim().toLowerCase();

export function manejarAdicionales(estado: ApiFalsaAdicionales): Manejador {
  return async (route, ruta, metodo) => {
    if (metodo === 'GET' && ruta === '/mapeador/sabana_vencida/campos-adicionales') {
      estado.lecturas += 1;
      if (estado.sinLista) return (await json(route, 500, { detail: 'fallo' }), true);
      return (await json(route, 200, estado.campos), true);
    }

    const cambio = ruta.match(/^\/mapeador\/sabana_vencida\/campos-adicionales\/([^/]+)$/);
    if (metodo !== 'PATCH' || !cambio) return false;
    const nombre = decodeURIComponent(cambio[1]);
    const cuerpo = JSON.parse(route.request().postData() ?? '{}') as Esquemas['CambioCampoAdicionalEntrada'];
    estado.cambios.push({ nombre, cuerpo });

    const rechazo = estado.rechazos.shift();
    if (rechazo) return (await json(route, rechazo.estado, rechazo.cuerpo), true);

    const campo = estado.campos.find((c) => c.nombre === nombre);
    if (!campo) return (await json(route, 404, { detail: 'No existe', codigo: 'campo_adicional_no_encontrado' }), true);
    if (cuerpo.nombre_legible != null) {
      const choca = estado.campos.find((c) => c.nombre !== nombre && normalizar(c.nombre_legible) === normalizar(cuerpo.nombre_legible!));
      if (choca) {
        return (await json(route, 409, { detail: 'Ya existe', codigo: 'nombre_repetido', campo: campoAdicional(choca.nombre, choca.nombre_legible) }), true);
      }
      campo.nombre_legible = cuerpo.nombre_legible.trim();
    }
    if (cuerpo.archivado != null) campo.archivado = cuerpo.archivado;
    return (await json(route, 200, campo), true);
  };
}

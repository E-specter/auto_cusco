/**
 * A stand-in for the header mapper's validation, typed against the contract,
 * and the synthetic cases the test page mounts. It answers like the backend's
 * `validar` for the codes the screen can meet: a similar header without review,
 * a required field without a column, a field in two columns. Every header,
 * example and field is invented.
 */
import type { Route } from '@playwright/test';

import type { components } from '../src/lib/contrato-api';
import type { Manejador } from './api-falsa';

type Esquemas = components['schemas'];
export type Analisis = Esquemas['AnalisisRespuesta'];
type Campo = Esquemas['CampoDestinoRespuesta'];
type Asignacion = Esquemas['AsignacionEntrada'];
type Problema = Esquemas['ProblemaMapeoRespuesta'];
type Columna = Esquemas['ColumnaAnalizadaRespuesta'];

const campo = (nombre: string, obligatorio = false): Campo => ({
  nombre,
  clave_etiqueta: `campo.${nombre}`,
  tipo: 'texto',
  obligatorio,
  alias: [], // T-MAP-B4: los alias literales; la busqueda (T-MAP-F3) los usa
});

/** A slice of the sheet's catalogue, with its one required field. */
export const CAMPOS_SINTETICOS: Campo[] = [
  campo('pagare', true),
  campo('pagare_duplicado'),
  campo('titular'),
  campo('saldo_capital_pendiente'),
  campo('telefono'),
  campo('dias_atraso'),
  campo('documento'),
];

export const columna = (indice: number, encabezado: string, estado: Columna['estado'], sugerido: string | null, ejemplos: string[] = ['X1', 'X2']): Columna => ({
  indice,
  encabezado,
  ejemplos,
  estado,
  sugerido,
  similitud: estado === 'parecido' ? 0.8 : null,
});

export function analisisSintetico(columnas: Columna[], cambios: Partial<Analisis> = {}): Analisis {
  const analisis: Analisis = {
    borrador_id: 7,
    catalogo_id: 'sabana_vencida',
    formato: 'xlsx',
    hojas: ['VENCIDA'],
    hoja: 'VENCIDA',
    separador: null,
    codificacion: null,
    filas: 3200,
    columnas,
    problemas: [],
    advertencias: [],
    detectados: [],
    ...cambios,
  };
  if (!cambios.problemas) {
    analisis.problemas = validarSintetico(
      columnas.map((c) => ({ indice: c.indice, campo: c.sugerido, origen: c.estado === 'recordado' ? 'recordado' : c.estado === 'sin_coincidencia' ? 'manual' : 'coincide' })),
      analisis,
    );
  }
  return analisis;
}

/** The backend's rules for the codes the screen meets (§3.4 of the design). */
export function validarSintetico(asignaciones: Asignacion[], analisis: Analisis, campos: Campo[] = CAMPOS_SINTETICOS): Problema[] {
  const problemas: Problema[] = [];
  for (const a of asignaciones) {
    const c = analisis.columnas.find((x) => x.indice === a.indice)!;
    if (c.estado === 'parecido' && a.campo === c.sugerido && a.origen !== 'parecido_aceptado' && a.origen !== 'manual') {
      problemas.push({ indice: a.indice, codigo: 'parecido_sin_revisar', detalle: 'Parecido sin revisar', campo: a.campo });
    }
  }
  for (const a of asignaciones) {
    if (a.campo !== null && asignaciones.filter((b) => b.campo === a.campo).length > 1) {
      problemas.push({ indice: a.indice, codigo: 'campo_repetido', detalle: 'Campo repetido', campo: a.campo });
    }
  }
  for (const c of campos.filter((x) => x.obligatorio)) {
    if (!asignaciones.some((a) => a.campo === c.nombre)) {
      problemas.push({ indice: null, codigo: 'obligatorio_sin_columna', detalle: 'Falta el obligatorio', campo: c.nombre });
    }
  }
  return problemas;
}

export interface ApiFalsaMapeador {
  analisis: Analisis;
  pedidos: Asignacion[][];
}

/** The validation route, as a handler `montarApi` chains before its 404. */
export function manejarMapeador(estado: ApiFalsaMapeador): Manejador {
  return async (route: Route, ruta: string, metodo: string) => {
    if (metodo !== 'POST' || !/^\/mapeador\/borradores\/\d+\/validacion$/.test(ruta)) return false;
    const { asignaciones } = JSON.parse(route.request().postData() ?? '{}') as Esquemas['ValidacionEntrada'];
    estado.pedidos.push(asignaciones);
    const cuerpo: Esquemas['ValidacionMapeoRespuesta'] = { problemas: validarSintetico(asignaciones, estado.analisis) };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(cuerpo) });
    return true;
  };
}

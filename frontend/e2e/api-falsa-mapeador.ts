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

const campo = (nombre: string, obligatorio = false, alias: string[] = []): Campo => ({
  nombre,
  clave_etiqueta: `campo.${nombre}`,
  tipo: 'texto',
  obligatorio,
  alias, // T-MAP-B4: the literal aliases; the search of the field list uses them (T-MAP-F3)
  etiqueta: null, // T-CA-B2: only an additional field (RF-64) carries its own label
  adicional: false,
});

/** A slice of the sheet's catalogue, with its one required field. */
export const CAMPOS_SINTETICOS: Campo[] = [
  campo('pagare', true),
  campo('pagare_duplicado'),
  campo('titular'),
  campo('saldo_capital_pendiente'),
  campo('telefono', false, ['celular', 'movil']),
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

/** An additional field as the catalogue lists it (RF-64): its own label, never a dictionary key. */
export const campoAdicional = (nombre: string, etiqueta: string): Campo => ({
  nombre,
  clave_etiqueta: `campo.${nombre}`,
  tipo: 'texto',
  obligatorio: false,
  alias: [etiqueta],
  etiqueta,
  adicional: true,
});

type Rechazo = { estado: number; cuerpo: unknown };

export interface ApiFalsaMapeador {
  analisis: Analisis;
  pedidos: Asignacion[][];
  /** What `POST …/campos-adicionales` received, to assert on the call itself. */
  creaciones?: Array<Esquemas['NuevoCampoAdicionalEntrada']>;
  /** Refusals of the creation, in order; once spent, it creates. */
  rechazosCrear?: Rechazo[];
  /** The catalogue the creation answers with and grows. */
  catalogo?: Campo[];
}

/** The validation route, as a handler `montarApi` chains before its 404. */
export function manejarMapeador(estado: ApiFalsaMapeador): Manejador {
  return async (route: Route, ruta: string, metodo: string) => {
    if (metodo === 'POST' && /^\/mapeador\/borradores\/\d+\/campos-adicionales$/.test(ruta)) {
      const entrada = JSON.parse(route.request().postData() ?? '{}') as Esquemas['NuevoCampoAdicionalEntrada'];
      (estado.creaciones ??= []).push(entrada);
      const rechazo = estado.rechazosCrear?.shift();
      if (rechazo) {
        await route.fulfill({ status: rechazo.estado, contentType: 'application/json', body: JSON.stringify(rechazo.cuerpo) });
        return true;
      }
      const nuevo = campoAdicional(`ad_${entrada.nombre_legible.toLowerCase().replace(/[^a-z0-9]+/g, '_')}`, entrada.nombre_legible);
      const catalogo = (estado.catalogo ??= [...CAMPOS_SINTETICOS]);
      catalogo.push(nuevo);
      const cuerpo: Esquemas['CampoAdicionalCreadoRespuesta'] = { campo: nuevo, campos: [...catalogo] };
      await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(cuerpo) });
      return true;
    }
    if (metodo !== 'POST' || !/^\/mapeador\/borradores\/\d+\/validacion$/.test(ruta)) return false;
    const { asignaciones } = JSON.parse(route.request().postData() ?? '{}') as Esquemas['ValidacionEntrada'];
    estado.pedidos.push(asignaciones);
    const cuerpo: Esquemas['ValidacionMapeoRespuesta'] = { problemas: validarSintetico(asignaciones, estado.analisis, estado.catalogo ?? CAMPOS_SINTETICOS) };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(cuerpo) });
    return true;
  };
}

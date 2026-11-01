/**
 * A stand-in for the MOWA MES API, driven entirely from the test.
 *
 * Typed against the generated contract, so a fake the backend could never
 * send fails to compile. Every value is invented: supervisor numbers sit in
 * the synthetic 900000xxx range and no real name, document or phone appears.
 * The speech texts are the product's own default (RF-MM-18), not personal data.
 */
import type { Page, Route } from '@playwright/test';

import {
  esTelefono,
  estadoSupervisionCalendario,
  manejadorSupervisionCalendario,
  valoresSobreUmbral,
  type EstadoSupervisionCalendario,
} from './api-falsa';
import type {
  AvisoCampana,
  Campana,
  CodigoMowaMes,
  Conciliacion,
  ConsumoLimite,
  CreacionCampanaEntrada,
  Exclusion,
  PeticionCampanaEntrada,
  PrevisualizacionCampana,
  ConfiguracionMowaMes,
  SpeechParcialEntrada,
  VersionSpeech,
} from '../src/lib/api-mowa-mes';
import { json, siguiente } from './apoyo';
import { expresionesDelOriginal } from './speech-original';

type Respuesta = { estado: number; cuerpo?: unknown };

/** The Speech original, as the database holds it since M-B3: a v2, with the migration's expressions. */
export function speechOriginal(): VersionSpeech {
  return {
    id: 1,
    nombre: 'Speech original',
    formato: 'v2',
    original: true,
    basada_en_id: null,
    usada: false,
    editable: false,
    creado_en: '2026-09-13T08:00:00-05:00',
    deshabilitada_en: null,
    eliminable: false,
    motivo_no_eliminable: 'original',
    partes: [],
    expresiones: expresionesDelOriginal(),
  };
}

/** The moment `PATCH {habilitada: false}` stamps. */
export const DESHABILITADA_EN = '2026-10-31T09:00:00-05:00';

/**
 * What the API works out for a version from the rest of it (RF-MM-29, RF-MM-30): a disabled one is not
 * editable, and it can be deleted only if it is disabled, unused and not the Speech original. The reason it
 * never can be (`original`, `usada`) comes whether or not it is disabled.
 */
export function conEliminable(version: VersionSpeech): VersionSpeech {
  const deshabilitada = version.deshabilitada_en !== null;
  return {
    ...version,
    editable: !deshabilitada && !version.usada && !version.original,
    eliminable: deshabilitada && !version.usada && !version.original,
    motivo_no_eliminable: version.original ? 'original' : version.usada ? 'usada' : null,
  };
}

/** A version as the API lists it once it can be disabled: `eliminable`, `motivo_no_eliminable` and `editable` agree. */
export function versionAdministrable(parcial: Partial<VersionSpeech> = {}): VersionSpeech {
  return conEliminable({ ...versionSpeech(), ...parcial });
}

export function versionSpeech(parcial: Partial<VersionSpeech> = {}): VersionSpeech {
  return {
    id: 2,
    nombre: 'Speech 2',
    formato: 'v2',
    original: false,
    basada_en_id: 1,
    usada: false,
    editable: true,
    creado_en: '2026-09-13T09:00:00-05:00',
    deshabilitada_en: null,
    eliminable: false,
    motivo_no_eliminable: null,
    partes: [],
    expresiones: expresionesDelOriginal(),
    ...parcial,
  };
}

// ---- Costs and file names (T-MM-F6, B8's contract) ----------------------------------

/** The formats the report accepts (RF-57): the sheet's, recognised by the general reader. */
export const FORMATOS_REPORTE = ['.xlsx', '.xlsb', '.xls', '.ods', '.csv', '.tsv', '.txt', '.json'] as const;

/** The file name a multipart body carries, or `null` when it names none. */
function nombreSubido(cuerpo: unknown): string | null {
  return typeof cuerpo === 'string' ? (cuerpo.match(/filename="([^"]*)"/)?.[1] ?? null) : null;
}

/** What the API stores by default (RF-MM-23, RF-MM-25). Amounts travel as text, 4 decimals. */
export const TARIFA_POR_DEFECTO = '0.0200';
export const PLANTILLA_POR_DEFECTO = 'mowa_mes_campana_{campana}_{archivo}_de_{total}';

/** The valid variables, in the order the requirement lists them. */
export const VARIABLES_PLANTILLA: Array<{ nombre: string; descripcion: string }> = [
  { nombre: 'campana', descripcion: 'Numero de la campana en el sistema' },
  { nombre: 'descripcion', descripcion: 'Descripcion de la campana' },
  { nombre: 'fecha_envio', descripcion: 'Fecha de envio, en formato AAAA-MM-DD' },
  { nombre: 'fecha_corte', descripcion: 'Fecha de corte de la sabana, en formato AAAA-MM-DD' },
  { nombre: 'archivo', descripcion: 'Numero del archivo dentro de la campana (1, 2, ...)' },
  { nombre: 'total', descripcion: 'Cantidad de archivos de la campana' },
  { nombre: 'cantidad', descripcion: 'Filas de ese archivo, incluida la supervision si va en el' },
];

/** `unidades` × `tarifa`, both as the API sends them, without floats: 4 decimals. */
export function montoSintetico(unidades: number, tarifa: string = TARIFA_POR_DEFECTO): string {
  const [enteros, decimales = ''] = tarifa.split('.');
  const diezmilesimas = Number(enteros + decimales.padEnd(4, '0').slice(0, 4));
  const total = unidades * diezmilesimas;
  return `${Math.floor(total / 10_000)}.${String(total % 10_000).padStart(4, '0')}`;
}

/**
 * A test double of the API's template check: the same message for an unknown
 * variable (named) or an unclosed brace, so a scenario can show a 400. It does
 * not reproduce the name sanitising rules, which are the backend's own.
 */
export function errorDePlantilla(plantilla: string): string | null {
  if (plantilla.length > 300) return 'La plantilla no puede pasar de 300 caracteres';
  const resto = plantilla.replace(/\{([^{}]*)\}/g, '');
  if (resto.includes('{')) return 'La plantilla tiene una llave { sin cerrar';
  if (resto.includes('}')) return 'La plantilla tiene una llave } sin abrir';
  for (const coincidencia of plantilla.matchAll(/\{([^{}]*)\}/g)) {
    if (!VARIABLES_PLANTILLA.some((v) => v.nombre === coincidencia[1])) {
      const validas = VARIABLES_PLANTILLA.map((v) => `{${v.nombre}}`).join(', ');
      return `{${coincidencia[1]}} no es una variable de la plantilla. Variables validas: ${validas}`;
    }
  }
  return null;
}

interface ContextoNombreFalso {
  campana: string;
  descripcion: string;
  fechaEnvio: string;
  fechaCorte: string;
}

/** One name per file; the automatic suffix enters when several files and no `{archivo}`. */
function nombresSinteticos(plantilla: string, contexto: ContextoNombreFalso, cantidades: number[]): string[] {
  const efectiva = plantilla.trim() === '' ? PLANTILLA_POR_DEFECTO : plantilla;
  const usaArchivo = efectiva.includes('{archivo}');
  return cantidades.map((cantidad, i) => {
    const valores: Record<string, string> = {
      campana: contexto.campana,
      descripcion: contexto.descripcion,
      fecha_envio: contexto.fechaEnvio,
      fecha_corte: contexto.fechaCorte,
      archivo: String(i + 1),
      total: String(cantidades.length),
      cantidad: String(cantidad),
    };
    // The API replaces what Windows does not accept in a file name by an underscore.
    const cuerpo = efectiva
      .replace(/\{([^{}]*)\}/g, (_, nombre: string) => valores[nombre] ?? '')
      .replace(/[\\/:*?"<>|]/g, '_');
    const sufijo = cantidades.length > 1 && !usaArchivo ? `_${i + 1}de${cantidades.length}` : '';
    return `${cuerpo}${sufijo}.xlsx`;
  });
}

/** The API's own sample for the configuration screen: two files, RF-MM-25's example. */
export function nombresDeEjemplo(plantilla: string): string[] {
  return nombresSinteticos(
    plantilla,
    { campana: '1234', descripcion: 'CajaCusco', fechaEnvio: '2026-10-01', fechaCorte: '2026-09-30' },
    [50_000, 1_200],
  );
}

/** What the campaign preview and creation are built with: the configured rate and template. */
export interface ContextoCostos {
  tarifa: string;
  plantilla: string;
}

const CONTEXTO_POR_DEFECTO: ContextoCostos = { tarifa: TARIFA_POR_DEFECTO, plantilla: PLANTILLA_POR_DEFECTO };

/** The amounts fields of a campaign created without a stored rate (before RF-MM-23). */
export const SIN_TARIFA_GUARDADA = {
  tarifa_sms: null,
  costo_estimado: null,
  costo_estimado_estado: 'no_disponible',
  costo_real: null,
  costo_real_estado: 'no_disponible',
} as const;

// ---- Follow-up (T-MM-F3) ----------------------------------------------------------

/** A generated campaign with synthetic figures: 980 products and 2 supervisors. */
export function campanaSintetica(parcial: Partial<Campana> = {}): Campana {
  return {
    id: 1,
    // A timestamptz comes back in UTC. This one is already the 15th in UTC but
    // still the 14th in Lima (21:00), so a screen that skips the conversion shows it.
    creado_en: '2026-09-15T02:00:00+00:00',
    fecha_corte: '2026-09-13',
    filtros: ['dias_atraso:entre:9|30'],
    orden: '-saldo_capital_pendiente',
    cantidad: 1000,
    seleccion_id: null,
    tipo_carga: 'masiva',
    descripcion: 'CajaCusco 9 <= dias atraso <= 30',
    salida: 'numero_largo',
    herramientas: { keyword: false, respuesta_automatica: false, blacklist_indecopi: true, speech_optimizado: false },
    programacion: 'hora_determinada',
    envios: ['2026-09-15T09:00:00-05:00'],
    fecha_envio: '2026-09-15',
    mes_imputacion: '2026-09',
    speech: { id: 1, nombre: 'Speech original' },
    whatsapp: '900000999',
    supervisores: [
      { numero: '900000101', procedencia: 'Procedencia A', documento: '00000001' },
      { numero: '900000102', procedencia: 'Procedencia B', documento: '00000002' },
    ],
    disponibles: 1200,
    evaluados: 1000,
    productos_cargados: 980,
    supervision_cargados: 2,
    total_cargados: 982,
    excluidos: 20,
    advertencias: 35,
    confirmo_limite: false,
    archivos: [{ numero: 1, filas: 982, supervision: 2, bytes: 41_500, nombre: 'mowa_mes_campana_1_1_de_1.xlsx' }],
    tarifa_sms: TARIFA_POR_DEFECTO,
    costo_estimado: montoSintetico(982),
    costo_estimado_estado: 'calculado',
    costo_real: null,
    costo_real_estado: 'pendiente',
    pendiente_reporte: true,
    descartada_en: null,
    ...parcial,
  };
}

/**
 * A reconciliation where sent (952) is lower than the rows that match the
 * campaign (977): 25 matched rows came back with another status (E-1).
 */
export function conciliacionSintetica(campanaId = 1, parcial: Partial<Conciliacion> = {}): Conciliacion {
  return {
    campana_id: campanaId,
    reportes: [{ mes_id: 990000001, nombre_archivo: 'REPORTE_SINTETICO.xlsx', filas: 985, importado_en: '2026-09-16T02:30:00+00:00' }],
    productos: {
      cargados: 980,
      enviados: 950,
      no_enviados: 30,
      por_estado: [{ estado: 'enviado', cantidad: 950 }, { estado: 'rechazado', cantidad: 25 }],
    },
    supervision: { cargados: 2, enviados: 2, no_enviados: 0, por_estado: [{ estado: 'enviado', cantidad: 2 }] },
    total: {
      cargados: 982,
      enviados: 952,
      no_enviados: 30,
      por_estado: [{ estado: 'enviado', cantidad: 952 }, { estado: 'rechazado', cantidad: 25 }],
    },
    sin_correspondencia: 8,
    sin_correspondencia_por_estado: [{ estado: 'enviado', cantidad: 8 }],
    por_id: [{ mes_id: 990000001, filas: 985, con_correspondencia: 977 }],
    advertencias: [],
    tarifa_sms: TARIFA_POR_DEFECTO,
    costo_real: montoSintetico(952),
    costo_real_estado: 'calculado',
    ...parcial,
  };
}

export function consumoSintetico(mes: string, parcial: Partial<ConsumoLimite> = {}): ConsumoLimite {
  return {
    mes,
    limite: 2_500_000,
    cargados_mes: 982,
    esta_campana: 0,
    total: 982,
    disponible: 2_499_018,
    excedido: false,
    costo_mes: montoSintetico(982),
    campanas_sin_tarifa: 0,
    // Only the preview knows this campaign's cost; the month's own reads leave it out.
    costo_esta_campana: null,
    costo_total: montoSintetico(982),
    ...parcial,
  };
}

/** What a scenario may hand back for a month: the original fields, the cost ones optional. */
export type ConsumoParcial = Omit<ConsumoLimite, 'costo_mes' | 'campanas_sin_tarifa' | 'costo_esta_campana' | 'costo_total'> &
  Partial<ConsumoLimite>;

const EXCLUSIONES_EN_ORDEN: CodigoMowaMes[] = [
  'telefono_invalido',
  'falta_documento',
  'sin_speech',
  'falta_titular',
  'falta_vencimiento',
  'mensaje_excede_160',
];

/** The whole `CodigoMowaMes` catalogue (13 codes), for the API's 422 on anything else. */
const CODIGOS_CATALOGO: CodigoMowaMes[] = [
  ...EXCLUSIONES_EN_ORDEN,
  // T-MM-B12: an exclusion too, but not in the rotation of `EXCLUSIONES_EN_ORDEN`, so the counts of other specs stay.
  'falta_campo_adicional',
  'mensaje_excede_150',
  'documento_no_estandar',
  'limite_mensual_excedido',
  'id_sin_correspondencia',
  'falta_whatsapp',
  'sin_supervisores',
  'sin_productos_cargables',
];

/** `n` exclusions rotating through the six reasons; synthetic promissory notes. */
export function exclusionesSinteticas(n: number): Exclusion[] {
  return Array.from({ length: n }, (_, i) => ({
    pagare: String(900 + i).padStart(18, '0'),
    codigo: EXCLUSIONES_EN_ORDEN[i % EXCLUSIONES_EN_ORDEN.length],
    campos: [],
  }));
}

// ---- Campaign preview and creation (T-MM-F2, part A) --------------------------------

/**
 * The description of a request as the backend takes it (T-MM-B11): every line break is a space (`\r\n` as
 * one, plus `\r`, `\n`, U+2028 and U+2029), then the spaces at the ends go.
 */
export function normalizarDescripcion(texto: string): string {
  return texto.replace(/\r\n|[\r\n\u2028\u2029]/g, ' ').trim();
}

/**
 * The suggested description as the backend shortens it (RF-MM-04, T-MM-B10): the prefix and the filters
 * joined; if it does not fit in 100 (UTF-16 units, like `.length`), whole filters are dropped from the
 * end and it closes with `...`; if not even the first one fits, the text is cut at 97 and `...` is added.
 */
export function acortarDescripcion(prefijo: string, filtros: string[], tope = 100): string {
  const completa = [prefijo, filtros.join(', ')].filter(Boolean).join(' ');
  if (completa.length <= tope) return completa;
  for (let n = filtros.length - 1; n >= 1; n--) {
    const candidata = `${prefijo} ${filtros.slice(0, n).join(', ')}...`;
    if (candidata.length <= tope) return candidata;
  }
  return `${prefijo} ${filtros[0] ?? ''}`.slice(0, tope - 3) + '...';
}

const SIN_ERRORES_NI_ADVERTENCIAS: { errores: AvisoCampana[]; advertencias: AvisoCampana[] } = {
  errores: [],
  advertencias: [],
};

/**
 * A happy-path preview built from the request: 2% of the evaluated products
 * excluded, 2 supervisors, one file. Override any field with `parcial`, the
 * same pattern as `campanaSintetica` and `conciliacionSintetica` — this does
 * not simulate the backend's rules (whatsapp missing, no supervisors, huella,
 * the limit), which a scenario states explicitly through `parcial` instead.
 */
export function previsualizacionCampanaSintetica(
  entrada: PeticionCampanaEntrada,
  parcial: Omit<Partial<PrevisualizacionCampana>, 'limite'> & { limite?: ConsumoParcial } = {},
  contexto: ContextoCostos = CONTEXTO_POR_DEFECTO,
): PrevisualizacionCampana {
  const cantidad = entrada.cantidad;
  const excluidos = Math.min(20, Math.max(0, Math.floor(cantidad * 0.02)));
  const evaluados = cantidad;
  const productos = evaluados - excluidos;
  const supervision = 2;
  const totalCargados = productos + supervision;
  const speechId = entrada.speech_id ?? 1;
  // The backend summarises the filters IN THEIR ORDER (docs/filtro-valores-interfaz.md §3.5). With two or more the
  // fake does the same, in its own words; with none or one it keeps the text every other scenario expects.
  const filtros = entrada.filtros ?? [];
  const descripcionSugerida = acortarDescripcion(
    'CajaCusco',
    filtros.length >= 2 ? filtros.map((filtro) => filtro.replace(/:/g, ' ')) : ['9 <= dias atraso <= 30'],
  );
  const plantilla = entrada.plantilla_nombre_archivo?.trim() || contexto.plantilla;
  const usadas = new Set([...plantilla.matchAll(/\{([^{}]*)\}/g)].map((m) => m[1]));
  const { limite: limiteParcial, ...resto } = parcial;
  const nombres = (parcial.archivos_previstos_por_filas ?? [{ numero: 1 }]).length;

  return {
    descripcion: normalizarDescripcion(entrada.descripcion ?? '') || descripcionSugerida,
    descripcion_sugerida: descripcionSugerida,
    fecha_generacion: '2026-09-16',
    fecha_envio: '2026-09-17',
    speech: {
      id: speechId,
      nombre: speechId === 1 ? 'Speech original' : `Speech ${speechId}`,
      formato: 'v2',
      huella: 'a'.repeat(64),
    },
    whatsapp: entrada.whatsapp?.trim() || '900000999',
    supervisores: (
      entrada.supervisores ?? [
        { numero: '900000101', procedencia: 'Procedencia A' },
        { numero: '900000102', procedencia: 'Procedencia B' },
      ]
    ).map((s, i) => ({ ...s, documento: String(i + 1).padStart(8, '0') })),
    disponibles: Math.max(cantidad, 1200),
    solicitados: cantidad,
    evaluados,
    productos_cargados: productos,
    supervision_cargados: supervision,
    total_cargados: totalCargados,
    excluidos,
    exclusiones_por_codigo: excluidos > 0 ? [{ codigo: 'telefono_invalido', tipo: 'exclusion', cantidad: excluidos }] : [],
    advertencias_por_codigo: [],
    productos_por_segmento: [{ segmento: '9_a_30', etiqueta: '9 a 30', cantidad: productos }],
    muestra: [],
    exclusiones: {
      total: excluidos,
      limite: 100,
      desplazamiento: 0,
      exclusiones: exclusionesSinteticas(Math.min(excluidos, 5)),
    },
    archivos_previstos_por_filas: [{ numero: 1, filas: totalCargados, supervision }],
    limite: consumoSintetico('2026-09', {
      esta_campana: totalCargados,
      total: 982 + totalCargados,
      costo_esta_campana: montoSintetico(totalCargados, contexto.tarifa),
      costo_total: montoSintetico(982 + totalCargados, contexto.tarifa),
      ...limiteParcial,
    }),
    ...SIN_ERRORES_NI_ADVERTENCIAS,
    // The archived additional fields the speech reads (T-MM-B13): none unless a spec says otherwise.
    campos_archivados: [],
    puede_crear: true,
    tarifa_sms: contexto.tarifa,
    costo_estimado: montoSintetico(totalCargados, contexto.tarifa),
    plantilla_nombre_archivo: plantilla,
    // `[campana]` stands for the id the campaign does not have yet.
    nombre_primer_archivo: nombresSinteticos(
      plantilla,
      { campana: '[campana]', descripcion: descripcionSugerida, fechaEnvio: '2026-09-17', fechaCorte: entrada.fecha_corte },
      [totalCargados],
    )[0],
    nombre_estimado:
      usadas.has('archivo') ||
      usadas.has('total') ||
      usadas.has('cantidad') ||
      // The automatic suffix depends on how the load is split.
      (nombres > 1 && !usadas.has('archivo')),
    ...resto,
  };
}

/**
 * The campaign a successful `POST /mowa-mes/campanas` would answer with,
 * built from the same happy-path preview so the two stay consistent. As with
 * the other generators, override anything through `parcial`.
 */
export function campanaDesdeEntrada(
  entrada: CreacionCampanaEntrada,
  id: number,
  parcial: Partial<Campana> = {},
  contexto: ContextoCostos = CONTEXTO_POR_DEFECTO,
): Campana {
  const previa = previsualizacionCampanaSintetica(entrada, {}, contexto);
  return {
    id,
    creado_en: '2026-09-16T15:00:00+00:00',
    fecha_corte: entrada.fecha_corte,
    filtros: entrada.filtros ?? [],
    orden: entrada.orden ?? null,
    cantidad: entrada.cantidad,
    seleccion_id: entrada.seleccion_id ?? null,
    tipo_carga: entrada.tipo_carga ?? 'masiva',
    descripcion: normalizarDescripcion(entrada.descripcion ?? '') || previa.descripcion_sugerida,
    salida: entrada.salida ?? 'numero_largo',
    herramientas: {
      keyword: entrada.herramientas?.keyword ?? false,
      respuesta_automatica: false,
      blacklist_indecopi: entrada.herramientas?.blacklist_indecopi ?? false,
      speech_optimizado: false,
    },
    programacion: entrada.programacion ?? 'hora_determinada',
    envios: entrada.envios ?? [],
    fecha_envio: previa.fecha_envio,
    mes_imputacion: previa.fecha_envio.slice(0, 7),
    speech: { id: previa.speech.id, nombre: previa.speech.nombre },
    whatsapp: previa.whatsapp,
    supervisores: previa.supervisores,
    disponibles: previa.disponibles,
    evaluados: previa.evaluados,
    productos_cargados: previa.productos_cargados,
    supervision_cargados: previa.supervision_cargados,
    total_cargados: previa.total_cargados,
    excluidos: previa.excluidos,
    advertencias: previa.advertencias_por_codigo.reduce((total, c) => total + c.cantidad, 0),
    confirmo_limite: entrada.confirmar_limite ?? false,
    archivos: nombresSinteticos(
      previa.plantilla_nombre_archivo,
      { campana: String(id), descripcion: previa.descripcion, fechaEnvio: previa.fecha_envio, fechaCorte: entrada.fecha_corte },
      previa.archivos_previstos_por_filas.map((archivo) => archivo.filas),
    ).map((nombre, i) => ({ ...previa.archivos_previstos_por_filas[i], bytes: previa.archivos_previstos_por_filas[i].filas * 60, nombre })),
    tarifa_sms: contexto.tarifa,
    costo_estimado: previa.costo_estimado,
    costo_estimado_estado: 'calculado',
    costo_real: null,
    costo_real_estado: 'pendiente',
    pendiente_reporte: true,
    descartada_en: null,
    ...parcial,
  };
}

/** The moment `POST /mowa-mes/campanas/{id}/descartar` stamps, so a test can read the day it shows. */
export const DESCARTADA_EN = '2026-10-30T10:00:00-05:00';

export interface ApiFalsaMowaMes extends EstadoSupervisionCalendario {
  configuracion: ConfiguracionMowaMes;
  versiones: VersionSpeech[];
  /** Campaigns `GET /mowa-mes/campanas` pages through, most recent first. */
  campanas: Campana[];
  /** Exclusions per campaign id. */
  exclusiones: Map<number, Exclusion[]>;
  /** Reconciliation per campaign id; a campaign missing here has no report yet. */
  conciliaciones: Map<number, Conciliacion>;
  /** Answers `GET /mowa-mes/limite-mensual` for a month. */
  consumo: (mes: string) => ConsumoParcial;
  /** Scripted answers, in order; the last one repeats. Empty means "behave". */
  respuestas: EstadoSupervisionCalendario['respuestas'] & {
    guardarConfiguracion: Respuesta[];
    crearSpeech: Respuesta[];
    editarSpeech: Respuesta[];
    importarReporte: Respuesta[];
    previsualizarCampana: Respuesta[];
    crearCampana: Respuesta[];
    previsualizarPlantilla: Respuesta[];
  };
  /** When true, every call fails at the network level. */
  sinRed: boolean;
  /** Requests the page made, with their JSON bodies, for asserting on the call. */
  pedidos: Array<{ metodo: string; ruta: string; cuerpo: unknown }>;
}

export function apiMowaMes(): ApiFalsaMowaMes {
  const compartido = estadoSupervisionCalendario();
  return {
    ...compartido,
    configuracion: {
      limite_mensual: 2_500_000,
      registros_por_archivo: 50_000,
      bytes_por_archivo: 2_000_000,
      whatsapp_contacto: '900000999',
      actualizado_en: '2026-09-13T10:00:00-05:00',
      tarifa_sms: TARIFA_POR_DEFECTO,
      plantilla_nombre_archivo: PLANTILLA_POR_DEFECTO,
      variables_plantilla: VARIABLES_PLANTILLA,
    },
    versiones: [speechOriginal()],
    campanas: [campanaSintetica()],
    exclusiones: new Map([[1, exclusionesSinteticas(20)]]),
    conciliaciones: new Map(),
    consumo: (mes) => consumoSintetico(mes),
    respuestas: {
      ...compartido.respuestas,
      guardarConfiguracion: [],
      crearSpeech: [],
      editarSpeech: [],
      importarReporte: [],
      previsualizarCampana: [],
      crearCampana: [],
      previsualizarPlantilla: [],
    },
    sinRed: false,
    pedidos: [],
  };
}

/** FastAPI's validation answer: `detail` is a list of objects, not a sentence. */
const invalido = (route: Route, campo: string, mensaje: string) =>
  json(route, 422, { detail: [{ loc: ['body', campo], msg: mensaje, type: 'value_error' }] });

const enRango = (valor: unknown, minimo: number, maximo: number) =>
  typeof valor === 'number' && Number.isInteger(valor) && valor >= minimo && valor <= maximo;

/** The rate and template the campaign endpoints read from the saved configuration. */
function contextoDe(estado: ApiFalsaMowaMes): ContextoCostos {
  return { tarifa: estado.configuracion.tarifa_sms, plantilla: estado.configuracion.plantilla_nombre_archivo };
}

/**
 * Route every `/api` call to `estado`. Anything not handled answers 404 so a
 * missing fake fails loudly instead of reaching a real server.
 */
export async function montarApiMowaMes(page: Page, estado: ApiFalsaMowaMes): Promise<void> {
  const supervisionYCalendario = manejadorSupervisionCalendario(estado);
  await page.route('**/api/**', async (route) => {
    const pedido = route.request();
    const url = new URL(pedido.url());
    const ruta = url.pathname.replace(/^\/api/, '');
    const metodo = pedido.method();
    const texto = pedido.postData();
    // JSON bodies are parsed; a multipart upload is kept as its raw text.
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

    // The selector of the campaign is the portfolio's: a text field asks for its values (RF-67). Here none is offered.
    if (ruta === '/cartera/valores') return json(route, 200, valoresSobreUmbral(url));

    if (ruta === '/mowa-mes/configuracion' && metodo === 'GET') {
      return json(route, 200, estado.configuracion);
    }
    if (ruta === '/mowa-mes/configuracion' && metodo === 'PUT') {
      const guion = siguiente(estado.respuestas.guardarConfiguracion);
      if (guion) return json(route, guion.estado, guion.cuerpo ?? {});
      // The API's partial PUT: an omitted field keeps its value; an explicit
      // null WhatsApp clears it; a null limit, or a missing monthly limit, is a
      // 422 that leaves everything saved as it was.
      const entrada = (cuerpo && typeof cuerpo === 'object' ? cuerpo : {}) as Record<string, unknown>;
      if (!enRango(entrada.limite_mensual, 1, 1_000_000_000)) {
        return invalido(route, 'limite_mensual', 'Input should be between 1 and 1000000000');
      }
      for (const [campo, minimo, maximo] of [
        ['registros_por_archivo', 1, 50_000],
        ['bytes_por_archivo', 100_000, 2_000_000],
      ] as const) {
        if (campo in entrada && !enRango(entrada[campo], minimo, maximo)) {
          return invalido(route, campo, `Input should be between ${minimo} and ${maximo}`);
        }
      }
      let whatsapp = estado.configuracion.whatsapp_contacto;
      if ('whatsapp_contacto' in entrada) {
        const recibido = entrada.whatsapp_contacto === null ? '' : String(entrada.whatsapp_contacto).trim();
        if (recibido !== '' && !esTelefono(recibido)) {
          return json(route, 400, { detail: 'El numero de WhatsApp no cumple RF-02', campo: 'whatsapp_contacto' });
        }
        whatsapp = recibido === '' ? null : recibido;
      }
      // RF-MM-23 and RF-MM-25: omitted keeps, null is a 422, an invalid value a 400 that says why.
      let tarifa = estado.configuracion.tarifa_sms;
      if ('tarifa_sms' in entrada) {
        // A JSON number is not a string: Pydantic answers 422, like for a null.
        if (typeof entrada.tarifa_sms !== 'string') return invalido(route, 'tarifa_sms', 'Input should be a valid string');
        const recibida = entrada.tarifa_sms.trim();
        if (!/^\d+(\.\d{1,4})?$/.test(recibida)) {
          return json(route, 400, {
            detail: 'La tarifa debe ser un numero decimal mayor o igual a 0, con hasta 4 decimales (por ejemplo 0.02)',
            campo: 'tarifa_sms',
          });
        }
        const [enteros, decimales = ''] = recibida.split('.');
        tarifa = `${enteros}.${decimales.padEnd(4, '0')}`;
      }
      let plantilla = estado.configuracion.plantilla_nombre_archivo;
      if ('plantilla_nombre_archivo' in entrada) {
        if (typeof entrada.plantilla_nombre_archivo !== 'string') {
          return invalido(route, 'plantilla_nombre_archivo', 'Input should be a valid string');
        }
        const recibida = entrada.plantilla_nombre_archivo;
        const motivo = errorDePlantilla(recibida);
        if (motivo) return json(route, 400, { detail: motivo, campo: 'plantilla_nombre_archivo' });
        plantilla = recibida.trim() === '' ? PLANTILLA_POR_DEFECTO : recibida;
      }
      estado.configuracion = {
        ...estado.configuracion,
        tarifa_sms: tarifa,
        plantilla_nombre_archivo: plantilla,
        limite_mensual: entrada.limite_mensual as number,
        registros_por_archivo:
          'registros_por_archivo' in entrada
            ? (entrada.registros_por_archivo as number)
            : estado.configuracion.registros_por_archivo,
        bytes_por_archivo:
          'bytes_por_archivo' in entrada ? (entrada.bytes_por_archivo as number) : estado.configuracion.bytes_por_archivo,
        whatsapp_contacto: whatsapp,
        actualizado_en: '2026-09-13T11:00:00-05:00',
      };
      return json(route, 200, estado.configuracion);
    }

    if (ruta === '/mowa-mes/plantilla-nombre-archivo/previsualizacion' && metodo === 'POST') {
      const guion = siguiente(estado.respuestas.previsualizarPlantilla);
      if (guion) return json(route, guion.estado, guion.cuerpo ?? {});
      const recibida = (cuerpo as { plantilla?: unknown } | null)?.plantilla;
      if (typeof recibida !== 'string') return invalido(route, 'plantilla', 'Field required');
      const motivo = errorDePlantilla(recibida);
      if (motivo) return json(route, 400, { detail: motivo, campo: 'plantilla_nombre_archivo' });
      const plantilla = recibida.trim() === '' ? PLANTILLA_POR_DEFECTO : recibida;
      return json(route, 200, { plantilla, nombres_ejemplo: nombresDeEjemplo(plantilla) });
    }

    // The default supervisors and the working-day calendar are shared by every connector (`api-falsa.ts`).
    if (await supervisionYCalendario(route, ruta, metodo, url)) return;

    if (ruta === '/mowa-mes/speech' && metodo === 'GET') return json(route, 200, estado.versiones);
    if (ruta === '/mowa-mes/speech' && metodo === 'POST') {
      const guion = siguiente(estado.respuestas.crearSpeech);
      if (guion) return json(route, guion.estado, guion.cuerpo ?? {});
      // Every version is a v2 (M-B3): creating one, and the preview of its expressions, are answered by
      // `api-falsa-speech-v2.ts`, layered over this one.
      return json(route, 404, { detail: 'sin ruta falsa para crear una version aqui: la contesta api-falsa-speech-v2' });
    }
    const unaVersion = ruta.match(/^\/mowa-mes\/speech\/(\d+)$/);
    // Rename and/or disable or enable (RF-MM-28, RF-MM-29); with both, a refused name changes nothing.
    if (unaVersion && metodo === 'PATCH') {
      const id = Number(unaVersion[1]);
      const entrada = cuerpo as SpeechParcialEntrada;
      const actual = estado.versiones.find((v) => v.id === id);
      if (!actual) return json(route, 404, { detail: 'No existe la version' });
      let nueva = actual;
      if (entrada.nombre !== undefined && entrada.nombre !== null) {
        const nombre = entrada.nombre.trim();
        if (nombre === '' || nombre.length > 120) {
          return json(route, 400, { detail: 'El nombre debe tener de 1 a 120 caracteres' });
        }
        if (estado.versiones.some((v) => v.id !== id && v.nombre.trim().toLowerCase() === nombre.toLowerCase())) {
          return json(route, 409, { detail: `Ya existe una version llamada ${nombre}` });
        }
        nueva = { ...nueva, nombre };
      }
      if (entrada.habilitada === true) nueva = { ...nueva, deshabilitada_en: null };
      else if (entrada.habilitada === false) nueva = { ...nueva, deshabilitada_en: nueva.deshabilitada_en ?? DESHABILITADA_EN };
      nueva = conEliminable(nueva);
      estado.versiones = estado.versiones.map((v) => (v.id === id ? nueva : v));
      return json(route, 200, nueva);
    }
    // Deleting for good (RF-MM-30): only a disabled, unused version that is not the original.
    if (unaVersion && metodo === 'DELETE') {
      const id = Number(unaVersion[1]);
      const actual = estado.versiones.find((v) => v.id === id);
      if (!actual) return json(route, 404, { detail: 'No existe la version' });
      if (!conEliminable(actual).eliminable) {
        const codigo = actual.original ? 'speech_original' : actual.usada ? 'speech_usado' : 'speech_no_deshabilitado';
        return json(route, 409, { detail: `No se puede eliminar la version ${id}`, codigo });
      }
      estado.versiones = estado.versiones.filter((v) => v.id !== id);
      return route.fulfill({ status: 204 });
    }
    if (unaVersion && metodo === 'PUT') {
      const guion = siguiente(estado.respuestas.editarSpeech);
      if (guion) return json(route, guion.estado, guion.cuerpo ?? {});
      const id = Number(unaVersion[1]);
      const actual = estado.versiones.find((v) => v.id === id);
      if (!actual) return json(route, 404, { detail: 'No existe la version' });
      if (!actual.editable) return json(route, 409, { detail: 'La version ya se uso y no se modifica' });
      return json(route, 404, { detail: 'sin ruta falsa para editar una version aqui: la contesta api-falsa-speech-v2' });
    }

    // ---- Follow-up -----------------------------------------------------------------

    // The API's defaults when the page does not say: 50 campaigns, 100 exclusions.
    const pagina = <T,>(lista: T[], porDefecto: number) => {
      const limite = Number(url.searchParams.get('limite') ?? porDefecto);
      const desplazamiento = Number(url.searchParams.get('desplazamiento') ?? 0);
      return { total: lista.length, limite, desplazamiento, elementos: lista.slice(desplazamiento, desplazamiento + limite) };
    };

    if (ruta === '/mowa-mes/campanas' && metodo === 'GET') {
      // A discarded campaign is in no active total (RF-MM-31): neither the list, nor its count, nor the pending one.
      const activas = estado.campanas.filter((c) => c.descartada_en === null);
      const { elementos, ...resto } = pagina(activas, 50);
      // The count of the whole list, not of the page: the API counts them in the repository.
      const totalPendientes = activas.filter((c) => c.pendiente_reporte).length;
      return json(route, 200, { ...resto, total_pendientes: totalPendientes, campanas: elementos });
    }

    // The discarded ones (RF-MM-32): those of a management month, the months that have any (not trimmed by the
    // filter, newest first) and how many there are in all.
    if (ruta === '/mowa-mes/campanas/descartadas' && metodo === 'GET') {
      const mes = url.searchParams.get('mes');
      if (mes !== null && !/^\d{4}-(0[1-9]|1[0-2])$/.test(mes)) {
        return json(route, 422, { detail: [{ loc: ['query', 'mes'], msg: 'Input should be YYYY-MM', type: 'value_error' }] });
      }
      const descartadas = estado.campanas.filter((c) => c.descartada_en !== null);
      const meses = [...new Set(descartadas.map((c) => c.mes_imputacion))].sort().reverse();
      return json(route, 200, {
        campanas: mes === null ? descartadas : descartadas.filter((c) => c.mes_imputacion === mes),
        meses,
        total_descartadas: descartadas.length,
      });
    }

    if (ruta === '/mowa-mes/campanas/previsualizacion' && metodo === 'POST') {
      const guion = siguiente(estado.respuestas.previsualizarCampana);
      if (guion) return json(route, guion.estado, guion.cuerpo ?? {});
      const entrada = cuerpo as PeticionCampanaEntrada;
      // Same order and text as the backend's `_validar_opciones` (docs/mowa-mes.md §9).
      if (entrada.tipo_carga && entrada.tipo_carga !== 'masiva') {
        return json(route, 400, { detail: 'El tipo de carga Personalizada todavia no esta habilitado', campo: null });
      }
      if (entrada.salida && entrada.salida !== 'numero_largo') {
        return json(route, 400, { detail: 'Solo la salida Numero largo esta habilitada', campo: null });
      }
      if (entrada.herramientas?.respuesta_automatica) {
        return json(route, 400, { detail: 'La respuesta automatica todavia no esta habilitada', campo: null });
      }
      const errorPlantilla = entrada.plantilla_nombre_archivo ? errorDePlantilla(entrada.plantilla_nombre_archivo) : null;
      if (errorPlantilla) return json(route, 400, { detail: errorPlantilla, campo: 'plantilla_nombre_archivo' });
      // `cantidad` is bounded by FastAPI's own field validation (ge=1, le=120000)
      // before the request ever reaches the service, so out-of-range values are
      // a 422 there, not the core's 400 — and PeticionCampanaEntrada['cantidad']
      // is `number` in the generated types, so this route should not need to
      // reject it at all. A scenario that must simulate the 422 scripts it
      // through `respuestas.previsualizarCampana`.
      if (entrada.speech_id != null && !estado.versiones.some((v) => v.id === entrada.speech_id)) {
        return json(route, 404, { detail: `No existe la version ${entrada.speech_id}` });
      }
      return json(route, 200, previsualizacionCampanaSintetica(entrada, {}, contextoDe(estado)));
    }

    if (ruta === '/mowa-mes/campanas' && metodo === 'POST') {
      const guion = siguiente(estado.respuestas.crearCampana);
      if (guion) return json(route, guion.estado, guion.cuerpo ?? {});
      const entrada = cuerpo as CreacionCampanaEntrada;
      if (!entrada.speech_huella) {
        return json(route, 422, { detail: [{ loc: ['body', 'speech_huella'], msg: 'Field required', type: 'missing' }] });
      }
      const errorPlantilla = entrada.plantilla_nombre_archivo ? errorDePlantilla(entrada.plantilla_nombre_archivo) : null;
      if (errorPlantilla) return json(route, 400, { detail: errorPlantilla, campo: 'plantilla_nombre_archivo' });
      // A stale huella or an exceeded limit are scripted through
      // `respuestas.crearCampana`, not modeled here: this default is the
      // happy path, like `previsualizacionCampanaSintetica`.
      const id = Math.max(0, ...estado.campanas.map((c) => c.id)) + 1;
      const nueva = campanaDesdeEntrada(entrada, id, {}, contextoDe(estado));
      estado.campanas = [nueva, ...estado.campanas];
      return json(route, 201, nueva);
    }

    if (ruta === '/mowa-mes/limite-mensual' && metodo === 'GET') {
      const mes = url.searchParams.get('mes');
      if (mes !== null && !/^\d{4}-(0[1-9]|1[0-2])$/.test(mes)) {
        return json(route, 422, { detail: [{ loc: ['query', 'mes'], msg: 'String should match YYYY-MM', type: 'string_pattern_mismatch' }] });
      }
      const hoy = new Date();
      const mesActual = `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, '0')}`;
      return json(route, 200, consumoSintetico(mes ?? mesActual, estado.consumo(mes ?? mesActual)));
    }

    const unaCampana = ruta.match(/^\/mowa-mes\/campanas\/(\d+)(\/.*)?$/);
    if (unaCampana) {
      const id = Number(unaCampana[1]);
      const resto = unaCampana[2] ?? '';
      const campana = estado.campanas.find((c) => c.id === id);
      if (!campana) return json(route, 404, { detail: `No existe la campana ${id}` });

      if (resto === '' && metodo === 'GET') return json(route, 200, campana);

      // Discarding and restoring are idempotent, as in the API: discarding a discarded one keeps its date.
      if (resto === '/descartar' && metodo === 'POST') {
        const descartada = campana.descartada_en === null ? { ...campana, descartada_en: DESCARTADA_EN } : campana;
        estado.campanas = estado.campanas.map((c) => (c.id === id ? descartada : c));
        return json(route, 200, descartada);
      }
      if (resto === '/restaurar' && metodo === 'POST') {
        const activa = { ...campana, descartada_en: null };
        estado.campanas = estado.campanas.map((c) => (c.id === id ? activa : c));
        return json(route, 200, activa);
      }
      // Only a discarded one is deleted, and its files, exclusions and reports go with it.
      if (resto === '' && metodo === 'DELETE') {
        if (campana.descartada_en === null) {
          return json(route, 409, { detail: `La campana ${id} esta activa; descartala primero`, codigo: 'campana_no_descartada' });
        }
        estado.campanas = estado.campanas.filter((c) => c.id !== id);
        estado.exclusiones.delete(id);
        estado.conciliaciones.delete(id);
        return route.fulfill({ status: 204 });
      }

      if (resto === '/exclusiones' && metodo === 'GET') {
        const codigo = url.searchParams.get('codigo');
        // Any catalogue code filters (a non-exclusion one simply finds nothing);
        // only a code outside the catalogue is a 422.
        if (codigo !== null && !CODIGOS_CATALOGO.includes(codigo as CodigoMowaMes)) {
          return json(route, 422, { detail: [{ loc: ['query', 'codigo'], msg: 'Input should be a valid code', type: 'enum' }] });
        }
        const todas = estado.exclusiones.get(id) ?? [];
        const { elementos, ...datos } = pagina(codigo ? todas.filter((e) => e.codigo === codigo) : todas, 100);
        return json(route, 200, { ...datos, exclusiones: elementos });
      }

      const archivo = resto.match(/^\/archivos\/(\d+)$/);
      if (archivo && metodo === 'GET') {
        const numero = Number(archivo[1]);
        const datos = campana.archivos.find((a) => a.numero === numero);
        if (!datos) return json(route, 404, { detail: `No existe el archivo ${numero}` });
        return route.fulfill({
          status: 200,
          headers: {
            'content-type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'content-disposition': `attachment; filename="mowa_mes_campana_${id}_${numero}_de_${campana.archivos.length}.xlsx"`,
            'x-mowa-mes-campana': String(id),
            'x-mowa-mes-archivo': String(numero),
            'x-mowa-mes-archivos-total': String(campana.archivos.length),
            'x-mowa-mes-filas': String(datos.filas),
            'x-mowa-mes-supervision': String(datos.supervision),
            'x-mowa-mes-bytes': String(datos.bytes),
          },
          body: Buffer.from('contenido xlsx sintetico'),
        });
      }

      if (resto === '/reportes' && metodo === 'POST') {
        const guion = siguiente(estado.respuestas.importarReporte);
        if (guion) return json(route, guion.estado, guion.cuerpo ?? {});
        if (campana.descartada_en !== null) {
          return json(route, 409, { detail: `La campana ${id} esta descartada; restaurala primero`, codigo: 'campana_descartada' });
        }
        const nombre = nombreSubido(cuerpo);
        if (nombre !== null && !FORMATOS_REPORTE.some((extension) => nombre.toLowerCase().endsWith(extension))) {
          return json(route, 400, { detail: `El formato de ${nombre} no es reconocido: usa ${FORMATOS_REPORTE.join(', ')}` });
        }
        const conciliacion = conciliacionSintetica(
          id,
          campana.tarifa_sms === null
            ? { tarifa_sms: null, costo_real: null, costo_real_estado: 'no_disponible' }
            : { tarifa_sms: campana.tarifa_sms },
        );
        estado.conciliaciones.set(id, conciliacion);
        // The real cost is not stored: the list recomputes it from the reconciliation in force.
        estado.campanas = estado.campanas.map((c) =>
          c.id === id
            ? { ...c, costo_real: conciliacion.costo_real, costo_real_estado: conciliacion.costo_real_estado, pendiente_reporte: false }
            : c,
        );
        return json(route, 201, conciliacion);
      }

      if (resto === '/conciliacion' && metodo === 'GET') {
        return json(
          route,
          200,
          estado.conciliaciones.get(id) ??
            conciliacionSintetica(id, {
              reportes: [],
              productos: { cargados: campana.productos_cargados, enviados: 0, no_enviados: campana.productos_cargados, por_estado: [] },
              supervision: { cargados: campana.supervision_cargados, enviados: 0, no_enviados: campana.supervision_cargados, por_estado: [] },
              total: { cargados: campana.total_cargados, enviados: 0, no_enviados: campana.total_cargados, por_estado: [] },
              sin_correspondencia: 0,
              sin_correspondencia_por_estado: [],
              por_id: [],
              // Without a report the real cost is pending, or unknown if no rate was ever stored.
              tarifa_sms: campana.tarifa_sms,
              costo_real: null,
              costo_real_estado: campana.tarifa_sms === null ? 'no_disponible' : 'pendiente',
            }),
        );
      }
    }

    return json(route, 404, { detail: `sin ruta falsa para ${metodo} ${ruta}` });
  });
}

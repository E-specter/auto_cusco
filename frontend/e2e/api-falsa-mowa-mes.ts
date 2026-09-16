/**
 * A stand-in for the MOWA MES API, driven entirely from the test.
 *
 * Typed against the generated contract, so a fake the backend could never
 * send fails to compile. Every value is invented: supervisor numbers sit in
 * the synthetic 900000xxx range and no real name, document or phone appears.
 * The speech texts are the product's own default (RF-MM-18), not personal data.
 */
import type { Page, Route } from '@playwright/test';

import type {
  Campana,
  CodigoMowaMes,
  Conciliacion,
  ConsumoLimite,
  Exclusion,
  ConfiguracionMowaMes,
  ConfiguracionSupervision,
  ConfiguracionSupervisionEntrada,
  DiaNoLaborable,
  ExcepcionEntrada,
  PartesEntrada,
  PartesSpeech,
  PrevisualizacionSpeech,
  PrevisualizacionSpeechEntrada,
  Segmento,
  SpeechEdicionEntrada,
  SpeechNuevoEntrada,
  VersionSpeech,
} from '../src/lib/api-mowa-mes';

type Respuesta = { estado: number; cuerpo?: unknown };

const SEGMENTOS: Array<{ segmento: Segmento; etiqueta: string; desde: number | null; hasta: number }> = [
  { segmento: 'preventiva', etiqueta: 'Preventiva', desde: null, hasta: 0 },
  { segmento: '1_a_8', etiqueta: '1 a 8', desde: 1, hasta: 8 },
  { segmento: '9_a_30', etiqueta: '9 a 30', desde: 9, hasta: 30 },
  { segmento: '31_a_60', etiqueta: '31 a 60', desde: 31, hasta: 60 },
  { segmento: '61_a_90', etiqueta: '61 a 90', desde: 61, hasta: 90 },
  { segmento: '91_a_120', etiqueta: '91 a 120', desde: 91, hasta: 120 },
];

/** RF-MM-18: the default speech, the only one sown by the migration. */
const TEXTO_ORIGINAL: Record<Segmento, [string, string]> = {
  preventiva: [' Caja Cusco te recuerda que tu cuota Vence el ', '. Si ya pagaste, omite este mensaje.'],
  '1_a_8': [
    ' Caja Cusco te informa que tu cuota venció el ',
    ', acércate a pagar a nuestras agencias, agentes KASNET o a través de Wayki app.',
  ],
  '9_a_30': [
    ' Caja Cusco te informa que tu cuota venció el ',
    ', evita estar mal calificado, acércate a pagar a nuestras agencias y/o canales alternativos.',
  ],
  '31_a_60': [
    ' Caja Cusco te informa que tu cuota venció el ',
    ', ponte al día y participa del sorteo de 06 autos. INFO por [whatsapp]',
  ],
  '61_a_90': [
    ' cancela tu deuda CAJA CUSCO vencida el ',
    ', pague a tiempo y evite estar mal calificado. Más INFO por [whatsapp]',
  ],
  '91_a_120': [
    ' cancela tu deuda CAJA CUSCO vencida el ',
    ', pague a tiempo y evite estar mal calificado. Más INFO por [whatsapp]',
  ],
};

const usaWhatsapp = (parte: { parte_1: string; parte_2: string }) =>
  `${parte.parte_1}${parte.parte_2}`.includes('[whatsapp]');

/** The missing and repeated segments in one sentence, or null when all six arrive once. */
function problemaDeSegmentos(partes: PartesEntrada[]): string | null {
  const faltan = SEGMENTOS.filter(({ segmento }) => !partes.some((p) => p.segmento === segmento)).map((s) => s.segmento);
  const repetidos = SEGMENTOS.filter(({ segmento }) => partes.filter((p) => p.segmento === segmento).length > 1).map(
    (s) => s.segmento,
  );
  const frases = [];
  if (faltan.length) frases.push(`Faltan segmentos: ${faltan.join(', ')}`);
  if (repetidos.length) frases.push(`Segmentos repetidos: ${repetidos.join(', ')}`);
  return frases.length ? frases.join('. ') : null;
}

function partesCompletas(partes: PartesEntrada[]): PartesSpeech[] {
  return SEGMENTOS.map(({ segmento, etiqueta, desde, hasta }) => {
    const parte = partes.find((p) => p.segmento === segmento) ?? { segmento, parte_1: '', parte_2: '' };
    return {
      segmento,
      etiqueta,
      dias_desde: desde,
      dias_hasta: hasta,
      parte_1: parte.parte_1,
      parte_2: parte.parte_2,
      usa_whatsapp: usaWhatsapp(parte),
    };
  });
}

export function partesOriginales(): PartesEntrada[] {
  return SEGMENTOS.map(({ segmento }) => ({
    segmento,
    parte_1: TEXTO_ORIGINAL[segmento][0],
    parte_2: TEXTO_ORIGINAL[segmento][1],
  }));
}

export function speechOriginal(): VersionSpeech {
  return {
    id: 1,
    nombre: 'Speech original',
    original: true,
    basada_en_id: null,
    usada: false,
    editable: false,
    creado_en: '2026-09-13T08:00:00-05:00',
    partes: partesCompletas(partesOriginales()),
  };
}

export function versionSpeech(parcial: Partial<VersionSpeech> = {}): VersionSpeech {
  return {
    id: 2,
    nombre: 'Speech 2',
    original: false,
    basada_en_id: 1,
    usada: false,
    editable: true,
    creado_en: '2026-09-13T09:00:00-05:00',
    partes: partesCompletas(partesOriginales()),
    ...parcial,
  };
}

/**
 * Mirrors the backend's worst case: titular of 8, date of 10 and a WhatsApp
 * link of 26 characters. Without a number, a segment that uses it cannot be
 * built, so it reports `falta_whatsapp` and no example.
 */
export function previsualizacionSintetica(
  entrada: PrevisualizacionSpeechEntrada,
  whatsappConfigurado: string | null,
): PrevisualizacionSpeech {
  const whatsapp = entrada.whatsapp ?? whatsappConfigurado;
  // Like the backend: the length always counts a 26-character link, with or
  // without a number; only the example needs the real one.
  const enlaceLargo = `https://wa.me/+51${'9'.repeat(9)}`;
  const enlace = whatsapp ? `https://wa.me/+51${whatsapp}` : '';
  const problemas: PrevisualizacionSpeech['problemas'] = [];
  const segmentos: PrevisualizacionSpeech['segmentos'] = [];

  // Like the backend: missing or repeated segments are ONE problem that lists
  // them all, and those segments are left out of `segmentos`.
  const detalleSegmentos = problemaDeSegmentos(entrada.partes);
  if (detalleSegmentos) problemas.push({ segmento: null, campo: 'segmentos', detalle: detalleSegmentos });

  SEGMENTOS.forEach(({ segmento, etiqueta }) => {
    const recibidas = entrada.partes.filter((p) => p.segmento === segmento);
    if (recibidas.length !== 1) return;
    const [parte] = recibidas;
    (['parte_1', 'parte_2'] as const).forEach((campo) => {
      if (parte[campo].includes('[@')) {
        problemas.push({ segmento, campo, detalle: 'La parte no puede contener [@' });
      }
    });
    const usa = usaWhatsapp(parte);
    const falta = usa && !whatsapp;
    const largo =
      8 +
      parte.parte_1.replaceAll('[whatsapp]', enlaceLargo).length +
      10 +
      parte.parte_2.replaceAll('[whatsapp]', enlaceLargo).length;
    segmentos.push({
      segmento,
      etiqueta,
      usa_whatsapp: usa,
      falta_whatsapp: falta,
      largo_maximo: largo,
      codigo: largo > 160 ? 'mensaje_excede_160' : largo > 150 ? 'mensaje_excede_150' : null,
      // The backend's worst case: an 8-character holder and the date as a pattern.
      ejemplo: falta
        ? null
        : `XXXXXXXX${parte.parte_1.replaceAll('[whatsapp]', enlace)}dd/mm/yyyy${parte.parte_2.replaceAll('[whatsapp]', enlace)}`,
    });
  });

  return { whatsapp, largo_advertencia: 150, largo_maximo: 160, problemas, segmentos };
}

/** Three law holidays, one of them withdrawn this year, and one added day. */
export function diasSinteticos(anio: number): DiaNoLaborable[] {
  return [
    { fecha: `${anio}-01-01`, descripcion: 'Año Nuevo', origen: 'ley', retirado: false },
    { fecha: `${anio}-05-01`, descripcion: 'Día del Trabajo', origen: 'ley', retirado: false },
    { fecha: `${anio}-06-07`, descripcion: 'Batalla de Arica', origen: 'ley', retirado: true },
    { fecha: `${anio}-12-24`, descripcion: 'Día no laborable sintético', origen: 'agregado', retirado: false },
  ];
}

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
    archivos: [{ numero: 1, filas: 982, supervision: 2, bytes: 41_500 }],
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
    ...parcial,
  };
}

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
  }));
}

export interface ApiFalsaMowaMes {
  configuracion: ConfiguracionMowaMes;
  supervision: ConfiguracionSupervision;
  versiones: VersionSpeech[];
  /** Non-working days per year; missing years get `diasSinteticos`. */
  dias: Map<number, DiaNoLaborable[]>;
  siguienteDia: string;
  /** Campaigns `GET /mowa-mes/campanas` pages through, most recent first. */
  campanas: Campana[];
  /** Exclusions per campaign id. */
  exclusiones: Map<number, Exclusion[]>;
  /** Reconciliation per campaign id; a campaign missing here has no report yet. */
  conciliaciones: Map<number, Conciliacion>;
  /** Answers `GET /mowa-mes/limite-mensual` for a month. */
  consumo: (mes: string) => ConsumoLimite;
  /** Scripted answers, in order; the last one repeats. Empty means "behave". */
  respuestas: {
    guardarConfiguracion: Respuesta[];
    guardarSupervision: Respuesta[];
    crearSpeech: Respuesta[];
    editarSpeech: Respuesta[];
    crearExcepcion: Respuesta[];
    importarReporte: Respuesta[];
  };
  /** When true, every call fails at the network level. */
  sinRed: boolean;
  /** Requests the page made, with their JSON bodies, for asserting on the call. */
  pedidos: Array<{ metodo: string; ruta: string; cuerpo: unknown }>;
}

export function apiMowaMes(): ApiFalsaMowaMes {
  return {
    configuracion: {
      limite_mensual: 2_500_000,
      registros_por_archivo: 50_000,
      bytes_por_archivo: 2_000_000,
      whatsapp_contacto: '900000999',
      actualizado_en: '2026-09-13T10:00:00-05:00',
    },
    supervision: {
      procedencias: ['Procedencia A', 'Procedencia B'],
      supervisores: [
        { numero: '900000101', procedencia: 'Procedencia A', documento: '00000001' },
        { numero: '900000102', procedencia: 'Procedencia B', documento: '00000002' },
      ],
    },
    versiones: [speechOriginal()],
    dias: new Map(),
    siguienteDia: '2026-09-14',
    campanas: [campanaSintetica()],
    exclusiones: new Map([[1, exclusionesSinteticas(20)]]),
    conciliaciones: new Map(),
    consumo: (mes) => consumoSintetico(mes),
    respuestas: {
      guardarConfiguracion: [],
      guardarSupervision: [],
      crearSpeech: [],
      editarSpeech: [],
      crearExcepcion: [],
      importarReporte: [],
    },
    sinRed: false,
    pedidos: [],
  };
}

const json = (route: Route, estado: number, cuerpo: unknown) =>
  route.fulfill({ status: estado, contentType: 'application/json', body: JSON.stringify(cuerpo) });

/** FastAPI's validation answer: `detail` is a list of objects, not a sentence. */
const invalido = (route: Route, campo: string, mensaje: string) =>
  json(route, 422, { detail: [{ loc: ['body', campo], msg: mensaje, type: 'value_error' }] });

/** RF-02: 9 digits starting with 9. */
const esTelefono = (valor: string) => /^9\d{8}$/.test(valor);

const enRango = (valor: unknown, minimo: number, maximo: number) =>
  typeof valor === 'number' && Number.isInteger(valor) && valor >= minimo && valor <= maximo;

function siguiente(cola: Respuesta[]): Respuesta | undefined {
  return cola.length > 1 ? cola.shift() : cola[0];
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

/**
 * Route every `/api` call to `estado`. Anything not handled answers 404 so a
 * missing fake fails loudly instead of reaching a real server.
 */
export async function montarApiMowaMes(page: Page, estado: ApiFalsaMowaMes): Promise<void> {
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
          return json(route, 400, { detail: 'El numero de WhatsApp no cumple RF-02' });
        }
        whatsapp = recibido === '' ? null : recibido;
      }
      estado.configuracion = {
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

    if (ruta === '/supervisores' && metodo === 'GET') return json(route, 200, estado.supervision);
    if (ruta === '/supervisores' && metodo === 'PUT') {
      const guion = siguiente(estado.respuestas.guardarSupervision);
      if (guion) return json(route, guion.estado, guion.cuerpo ?? {});
      // Same checks as the API, after trimming: procedencias present, unique and
      // named; every supervisor's number valid and its procedencia listed.
      const recibida = cuerpo as ConfiguracionSupervisionEntrada;
      const entrada: ConfiguracionSupervisionEntrada = {
        procedencias: recibida.procedencias.map((p) => p.trim()),
        supervisores: recibida.supervisores.map((s) => ({ numero: s.numero.trim(), procedencia: s.procedencia.trim() })),
      };
      const claves = entrada.procedencias.map((p) => p.toLowerCase());
      if (claves.length === 0 || claves.some((p) => p === '') || new Set(claves).size !== claves.length) {
        return json(route, 400, { detail: 'Las procedencias deben tener nombre y no repetirse' });
      }
      const desconocido = entrada.supervisores.find((s) => !entrada.procedencias.includes(s.procedencia));
      if (desconocido) {
        return json(route, 400, { detail: `La procedencia ${desconocido.procedencia} no esta en la lista` });
      }
      const invalidoTelefono = entrada.supervisores.find((s) => !esTelefono(s.numero));
      if (invalidoTelefono) {
        return json(route, 400, { detail: `El numero ${invalidoTelefono.numero} no cumple RF-02` });
      }
      estado.supervision = conDocumentos(entrada);
      return json(route, 200, estado.supervision);
    }

    if (ruta === '/mowa-mes/speech' && metodo === 'GET') return json(route, 200, estado.versiones);
    if (ruta === '/mowa-mes/speech' && metodo === 'POST') {
      const guion = siguiente(estado.respuestas.crearSpeech);
      if (guion) return json(route, guion.estado, guion.cuerpo ?? {});
      const entrada = cuerpo as SpeechNuevoEntrada;
      const segmentosMal = problemaDeSegmentos(entrada.partes);
      if (segmentosMal) return json(route, 400, { detail: segmentosMal });
      if (entrada.partes.some((p) => `${p.parte_1}${p.parte_2}`.includes('[@'))) {
        return json(route, 400, { detail: 'Una parte no puede contener [@' });
      }
      if (entrada.basada_en_id != null && !estado.versiones.some((v) => v.id === entrada.basada_en_id)) {
        return json(route, 404, { detail: `No existe la version ${entrada.basada_en_id}` });
      }
      // Like the backend: without a name, one more than the highest "Speech N"
      // already used (at least "Speech 2"), whatever the ids are.
      const usados = estado.versiones
        .map((v) => /^speech (\d+)$/i.exec(v.nombre.trim())?.[1])
        .filter((n): n is string => n !== undefined)
        .map(Number);
      const nombre = entrada.nombre?.trim() || `Speech ${Math.max(1, ...usados) + 1}`;
      if (estado.versiones.some((v) => v.nombre.toLowerCase() === nombre.toLowerCase())) {
        return json(route, 409, { detail: 'Ya existe una version con ese nombre' });
      }
      const id = Math.max(...estado.versiones.map((v) => v.id)) + 1;
      const nueva = versionSpeech({
        id,
        nombre,
        basada_en_id: entrada.basada_en_id ?? null,
        partes: partesCompletas(entrada.partes),
      });
      estado.versiones = [...estado.versiones, nueva];
      return json(route, 201, nueva);
    }
    if (ruta === '/mowa-mes/speech/previsualizacion' && metodo === 'POST') {
      const pedido = cuerpo as PrevisualizacionSpeechEntrada;
      if (pedido.whatsapp && !esTelefono(pedido.whatsapp.trim())) {
        return json(route, 400, { detail: 'El numero de WhatsApp no cumple RF-02' });
      }
      return json(
        route,
        200,
        previsualizacionSintetica(cuerpo as PrevisualizacionSpeechEntrada, estado.configuracion.whatsapp_contacto),
      );
    }
    const unaVersion = ruta.match(/^\/mowa-mes\/speech\/(\d+)$/);
    if (unaVersion && metodo === 'PUT') {
      const guion = siguiente(estado.respuestas.editarSpeech);
      if (guion) return json(route, guion.estado, guion.cuerpo ?? {});
      const id = Number(unaVersion[1]);
      const actual = estado.versiones.find((v) => v.id === id);
      if (!actual) return json(route, 404, { detail: 'No existe la version' });
      if (!actual.editable) return json(route, 409, { detail: 'La version ya se uso y no se modifica' });
      const entrada = cuerpo as SpeechEdicionEntrada;
      const segmentosMal = problemaDeSegmentos(entrada.partes);
      if (segmentosMal) return json(route, 400, { detail: segmentosMal });
      if (entrada.partes.some((p) => `${p.parte_1}${p.parte_2}`.includes('[@'))) {
        return json(route, 400, { detail: 'Una parte no puede contener [@' });
      }
      if (estado.versiones.some((v) => v.id !== id && v.nombre.toLowerCase() === entrada.nombre.trim().toLowerCase())) {
        return json(route, 409, { detail: 'Ya existe una version con ese nombre' });
      }
      const editada = { ...actual, nombre: entrada.nombre, partes: partesCompletas(entrada.partes) };
      estado.versiones = estado.versiones.map((v) => (v.id === id ? editada : v));
      return json(route, 200, editada);
    }

    if (ruta === '/calendario/feriados' && metodo === 'GET') {
      const anio = Number(url.searchParams.get('anio') ?? 2026);
      if (!estado.dias.has(anio)) estado.dias.set(anio, diasSinteticos(anio));
      return json(route, 200, { anio, dias: estado.dias.get(anio) });
    }
    if (ruta === '/calendario/siguiente-dia-gestionable') {
      return json(route, 200, { desde: url.searchParams.get('desde') ?? '2026-09-13', fecha: estado.siguienteDia });
    }
    if (ruta === '/calendario/excepciones' && metodo === 'POST') {
      const guion = siguiente(estado.respuestas.crearExcepcion);
      if (guion) return json(route, guion.estado, guion.cuerpo ?? {});
      const recibida = cuerpo as ExcepcionEntrada;
      const entrada = { ...recibida, descripcion: recibida.descripcion.trim() };
      const anio = Number(entrada.fecha.slice(0, 4));
      const dias = estado.dias.get(anio) ?? diasSinteticos(anio);
      const delDia = dias.find((d) => d.fecha === entrada.fecha);
      // The rule decides what an exception can mean: withdraw only a law holiday,
      // add only a day that is not one; a date already carrying one is a 409.
      if (entrada.tipo === 'retirado' && delDia?.origen !== 'ley') {
        return json(route, 400, { detail: 'Solo se retira un feriado de ley' });
      }
      if (entrada.tipo === 'agregado' && delDia?.origen === 'ley') {
        return json(route, 400, { detail: 'La fecha ya es un feriado de ley' });
      }
      if (delDia && (delDia.origen === 'agregado' || delDia.retirado)) {
        return json(route, 409, { detail: 'La fecha ya tiene una excepcion' });
      }
      estado.dias.set(
        anio,
        entrada.tipo === 'retirado'
          ? dias.map((d) => (d.fecha === entrada.fecha ? { ...d, retirado: true } : d))
          : [...dias, { fecha: entrada.fecha, descripcion: entrada.descripcion, origen: 'agregado', retirado: false }],
      );
      return json(route, 201, { ...entrada, creado_en: '2026-09-13T12:00:00-05:00' });
    }
    const excepcion = ruta.match(/^\/calendario\/excepciones\/(\d{4}-\d{2}-\d{2})$/);
    if (excepcion && metodo === 'DELETE') {
      const fecha = excepcion[1];
      const anio = Number(fecha.slice(0, 4));
      const dias = estado.dias.get(anio) ?? diasSinteticos(anio);
      if (!dias.some((d) => d.fecha === fecha && (d.origen === 'agregado' || d.retirado))) {
        return json(route, 404, { detail: `No hay una excepcion el ${fecha}` });
      }
      estado.dias.set(
        anio,
        dias
          .filter((d) => !(d.fecha === fecha && d.origen === 'agregado'))
          .map((d) => (d.fecha === fecha ? { ...d, retirado: false } : d)),
      );
      return route.fulfill({ status: 204, body: '' });
    }

    // ---- Follow-up -----------------------------------------------------------------

    // The API's defaults when the page does not say: 50 campaigns, 100 exclusions.
    const pagina = <T,>(lista: T[], porDefecto: number) => {
      const limite = Number(url.searchParams.get('limite') ?? porDefecto);
      const desplazamiento = Number(url.searchParams.get('desplazamiento') ?? 0);
      return { total: lista.length, limite, desplazamiento, elementos: lista.slice(desplazamiento, desplazamiento + limite) };
    };

    if (ruta === '/mowa-mes/campanas' && metodo === 'GET') {
      const { elementos, ...resto } = pagina(estado.campanas, 50);
      return json(route, 200, { ...resto, campanas: elementos });
    }

    if (ruta === '/mowa-mes/limite-mensual' && metodo === 'GET') {
      const mes = url.searchParams.get('mes');
      if (mes !== null && !/^\d{4}-(0[1-9]|1[0-2])$/.test(mes)) {
        return json(route, 422, { detail: [{ loc: ['query', 'mes'], msg: 'String should match YYYY-MM', type: 'string_pattern_mismatch' }] });
      }
      const hoy = new Date();
      const mesActual = `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, '0')}`;
      return json(route, 200, estado.consumo(mes ?? mesActual));
    }

    const unaCampana = ruta.match(/^\/mowa-mes\/campanas\/(\d+)(\/.*)?$/);
    if (unaCampana) {
      const id = Number(unaCampana[1]);
      const resto = unaCampana[2] ?? '';
      const campana = estado.campanas.find((c) => c.id === id);
      if (!campana) return json(route, 404, { detail: `No existe la campana ${id}` });

      if (resto === '' && metodo === 'GET') return json(route, 200, campana);

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
        const conciliacion = conciliacionSintetica(id);
        estado.conciliaciones.set(id, conciliacion);
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
            }),
        );
      }
    }

    return json(route, 404, { detail: `sin ruta falsa para ${metodo} ${ruta}` });
  });
}

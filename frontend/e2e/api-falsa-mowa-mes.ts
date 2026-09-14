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
  const enlace = whatsapp ? `https://wa.me/+51${whatsapp}` : '';
  const segmentos = partesCompletas(entrada.partes).map((parte) => {
    const usa = parte.usa_whatsapp;
    const falta = usa && !whatsapp;
    const p1 = parte.parte_1.replaceAll('[whatsapp]', enlace);
    const p2 = parte.parte_2.replaceAll('[whatsapp]', enlace);
    const largo = 8 + p1.length + 10 + p2.length;
    return {
      segmento: parte.segmento,
      etiqueta: parte.etiqueta,
      usa_whatsapp: usa,
      falta_whatsapp: falta,
      largo_maximo: largo,
      codigo: largo > 160 ? ('mensaje_excede_160' as const) : largo > 150 ? ('mensaje_excede_150' as const) : null,
      ejemplo: falta ? null : `TITULAR8${p1}31/12/2099${p2}`,
    };
  });
  return { whatsapp, largo_advertencia: 150, largo_maximo: 160, problemas: [], segmentos };
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

export interface ApiFalsaMowaMes {
  configuracion: ConfiguracionMowaMes;
  supervision: ConfiguracionSupervision;
  versiones: VersionSpeech[];
  /** Non-working days per year; missing years get `diasSinteticos`. */
  dias: Map<number, DiaNoLaborable[]>;
  siguienteDia: string;
  /** Scripted answers, in order; the last one repeats. Empty means "behave". */
  respuestas: {
    guardarConfiguracion: Respuesta[];
    guardarSupervision: Respuesta[];
    crearSpeech: Respuesta[];
    editarSpeech: Respuesta[];
    crearExcepcion: Respuesta[];
  };
  /** When true, every call fails at the network level. */
  sinRed: boolean;
  /** Requests the page made, with their JSON bodies, for asserting on the call. */
  pedidos: Array<{ metodo: string; ruta: string; cuerpo: unknown }>;
}

/**
 * Per-file limits (RF-MM-11) that the configuration gains with B6b. Spread from
 * a constant rather than written in the literal, so this fake compiles against
 * the contract both before and after that cut lands.
 */
const LIMITES_POR_ARCHIVO = { registros_por_archivo: 50_000, bytes_por_archivo: 2_000_000 };

export function apiMowaMes(): ApiFalsaMowaMes {
  return {
    configuracion: {
      ...LIMITES_POR_ARCHIVO,
      limite_mensual: 2_500_000,
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
    respuestas: {
      guardarConfiguracion: [],
      guardarSupervision: [],
      crearSpeech: [],
      editarSpeech: [],
      crearExcepcion: [],
    },
    sinRed: false,
    pedidos: [],
  };
}

const json = (route: Route, estado: number, cuerpo: unknown) =>
  route.fulfill({ status: estado, contentType: 'application/json', body: JSON.stringify(cuerpo) });

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
    const cuerpo = texto ? JSON.parse(texto) : null;
    estado.pedidos.push({ metodo, ruta: `${ruta}${url.search}`, cuerpo });

    if (estado.sinRed) return route.abort('connectionrefused');

    if (ruta === '/health') return json(route, 200, { api: true, database: true, ok: true });

    if (ruta === '/mowa-mes/configuracion' && metodo === 'GET') {
      return json(route, 200, estado.configuracion);
    }
    if (ruta === '/mowa-mes/configuracion' && metodo === 'PUT') {
      const guion = siguiente(estado.respuestas.guardarConfiguracion);
      if (guion) return json(route, guion.estado, guion.cuerpo ?? {});
      // Like the API: a field the request leaves out or sends as null keeps its value.
      const recibidos = Object.fromEntries(
        Object.entries(cuerpo as Record<string, unknown>).filter(
          ([campo, valor]) => valor !== null || campo === 'whatsapp_contacto',
        ),
      );
      estado.configuracion = {
        ...estado.configuracion,
        ...recibidos,
        actualizado_en: '2026-09-13T11:00:00-05:00',
      };
      return json(route, 200, estado.configuracion);
    }

    if (ruta === '/supervisores' && metodo === 'GET') return json(route, 200, estado.supervision);
    if (ruta === '/supervisores' && metodo === 'PUT') {
      const guion = siguiente(estado.respuestas.guardarSupervision);
      if (guion) return json(route, guion.estado, guion.cuerpo ?? {});
      estado.supervision = conDocumentos(cuerpo as ConfiguracionSupervisionEntrada);
      return json(route, 200, estado.supervision);
    }

    if (ruta === '/mowa-mes/speech' && metodo === 'GET') return json(route, 200, estado.versiones);
    if (ruta === '/mowa-mes/speech' && metodo === 'POST') {
      const guion = siguiente(estado.respuestas.crearSpeech);
      if (guion) return json(route, guion.estado, guion.cuerpo ?? {});
      const entrada = cuerpo as SpeechNuevoEntrada;
      const id = Math.max(...estado.versiones.map((v) => v.id)) + 1;
      const nueva = versionSpeech({
        id,
        nombre: entrada.nombre ?? `Speech ${id}`,
        basada_en_id: entrada.basada_en_id ?? null,
        partes: partesCompletas(entrada.partes),
      });
      estado.versiones = [...estado.versiones, nueva];
      return json(route, 201, nueva);
    }
    if (ruta === '/mowa-mes/speech/previsualizacion' && metodo === 'POST') {
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
      return json(route, 200, { desde: '2026-09-13', fecha: estado.siguienteDia });
    }
    if (ruta === '/calendario/excepciones' && metodo === 'POST') {
      const guion = siguiente(estado.respuestas.crearExcepcion);
      if (guion) return json(route, guion.estado, guion.cuerpo ?? {});
      const entrada = cuerpo as ExcepcionEntrada;
      const anio = Number(entrada.fecha.slice(0, 4));
      const dias = estado.dias.get(anio) ?? diasSinteticos(anio);
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
      estado.dias.set(
        anio,
        dias
          .filter((d) => !(d.fecha === fecha && d.origen === 'agregado'))
          .map((d) => (d.fecha === fecha ? { ...d, retirado: false } : d)),
      );
      return route.fulfill({ status: 204, body: '' });
    }

    return json(route, 404, { detail: `sin ruta falsa para ${metodo} ${ruta}` });
  });
}

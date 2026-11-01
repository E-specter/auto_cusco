/**
 * The Speech original as the database holds it since M-B3 (T-MM-C11): every version is v2, so the original is the
 * expressions of the migration `d7a3e5b9c241_speech_solo_v2` (`EXPRESIONES_ORIGINAL`, the template RF-MM-18 names,
 * not personal data), with what the API adds to each segment: its label, its range of adjusted days and what the
 * expression uses. The fakes build every version from this, so none invents another structure.
 */
import type { components } from '../src/lib/contrato-api';

type ExpresionRespuesta = components['schemas']['ExpresionSegmentoRespuesta'];
type NodoGuardado = ExpresionRespuesta['expresion']['nodos'][number];

type Segmento = ExpresionRespuesta['segmento'];

/** RF-MM-15: the six segments, in order, with the label and the adjusted days the API gives each. */
export const SEGMENTOS: Array<{ segmento: Segmento; etiqueta: string; desde: number | null; hasta: number }> = [
  { segmento: 'preventiva', etiqueta: 'Preventiva', desde: null, hasta: 0 },
  { segmento: '1_a_8', etiqueta: '1 a 8', desde: 1, hasta: 8 },
  { segmento: '9_a_30', etiqueta: '9 a 30', desde: 9, hasta: 30 },
  { segmento: '31_a_60', etiqueta: '31 a 60', desde: 31, hasta: 60 },
  { segmento: '61_a_90', etiqueta: '61 a 90', desde: 61, hasta: 90 },
  { segmento: '91_a_120', etiqueta: '91 a 120', desde: 91, hasta: 120 },
];

/** `EXPRESIONES_ORIGINAL` of the migration, node by node (a copy: the test does not read the backend). */
const NODOS_DEL_ORIGINAL: Array<{ segmento: Segmento; nodos: NodoGuardado[] }> = [
  {
    segmento: 'preventiva',
    nodos: [
        { tipo: "variable", nombre: "titular", funciones: [{ nombre: "primeros", args: [8] }], obligatoria: true },
        { tipo: "texto", valor: " Caja Cusco te recuerda que tu cuota Vence el " },
        { tipo: "variable", nombre: "fecha_vencimiento_cuota", funciones: [{ nombre: "formato_fecha", args: ["dd/mm/aaaa"] }], obligatoria: true },
        { tipo: "texto", valor: ". Si ya pagaste, omite este mensaje." },
    ],
  },
  {
    segmento: '1_a_8',
    nodos: [
        { tipo: "variable", nombre: "titular", funciones: [{ nombre: "primeros", args: [8] }], obligatoria: true },
        { tipo: "texto", valor: " Caja Cusco te informa que tu cuota venció el " },
        { tipo: "variable", nombre: "fecha_vencimiento_cuota", funciones: [{ nombre: "formato_fecha", args: ["dd/mm/aaaa"] }], obligatoria: true },
        { tipo: "texto", valor: ", acércate a pagar a nuestras agencias, agentes KASNET o a través de Wayki app." },
    ],
  },
  {
    segmento: '9_a_30',
    nodos: [
        { tipo: "variable", nombre: "titular", funciones: [{ nombre: "primeros", args: [8] }], obligatoria: true },
        { tipo: "texto", valor: " Caja Cusco te informa que tu cuota venció el " },
        { tipo: "variable", nombre: "fecha_vencimiento_cuota", funciones: [{ nombre: "formato_fecha", args: ["dd/mm/aaaa"] }], obligatoria: true },
        { tipo: "texto", valor: ", evita estar mal calificado, acércate a pagar a nuestras agencias y/o canales alternativos." },
    ],
  },
  {
    segmento: '31_a_60',
    nodos: [
        { tipo: "variable", nombre: "titular", funciones: [{ nombre: "primeros", args: [8] }], obligatoria: true },
        { tipo: "texto", valor: " Caja Cusco te informa que tu cuota venció el " },
        { tipo: "variable", nombre: "fecha_vencimiento_cuota", funciones: [{ nombre: "formato_fecha", args: ["dd/mm/aaaa"] }], obligatoria: true },
        { tipo: "texto", valor: ", ponte al día y participa del sorteo de 06 autos. INFO por " },
        { tipo: "variable", nombre: "whatsapp_contacto", funciones: [{ nombre: "enlace_whatsapp", args: [] }], obligatoria: false },
    ],
  },
  {
    segmento: '61_a_90',
    nodos: [
        { tipo: "variable", nombre: "titular", funciones: [{ nombre: "primeros", args: [8] }], obligatoria: true },
        { tipo: "texto", valor: " cancela tu deuda CAJA CUSCO vencida el " },
        { tipo: "variable", nombre: "fecha_vencimiento_cuota", funciones: [{ nombre: "formato_fecha", args: ["dd/mm/aaaa"] }], obligatoria: true },
        { tipo: "texto", valor: ", pague a tiempo y evite estar mal calificado. Más INFO por " },
        { tipo: "variable", nombre: "whatsapp_contacto", funciones: [{ nombre: "enlace_whatsapp", args: [] }], obligatoria: false },
    ],
  },
  {
    segmento: '91_a_120',
    nodos: [
        { tipo: "variable", nombre: "titular", funciones: [{ nombre: "primeros", args: [8] }], obligatoria: true },
        { tipo: "texto", valor: " cancela tu deuda CAJA CUSCO vencida el " },
        { tipo: "variable", nombre: "fecha_vencimiento_cuota", funciones: [{ nombre: "formato_fecha", args: ["dd/mm/aaaa"] }], obligatoria: true },
        { tipo: "texto", valor: ", pague a tiempo y evite estar mal calificado. Más INFO por " },
        { tipo: "variable", nombre: "whatsapp_contacto", funciones: [{ nombre: "enlace_whatsapp", args: [] }], obligatoria: false },
    ],
  },
];

/** One segment as the API answers it: its expression and what it uses. */
export function expresionRespuesta(segmento: Segmento, nodos: NodoGuardado[]): ExpresionRespuesta {
  const meta = SEGMENTOS.find((s) => s.segmento === segmento)!;
  const usa = (nombre: string) => nodos.some((n) => n.tipo === 'variable' && n.nombre === nombre);
  return {
    segmento,
    etiqueta: meta.etiqueta,
    dias_desde: meta.desde,
    dias_hasta: meta.hasta,
    expresion: { nodos: structuredClone(nodos) },
    usa_titular: usa('titular'),
    usa_vencimiento: usa('fecha_vencimiento_cuota'),
    usa_whatsapp: usa('whatsapp_contacto'),
  };
}

/** The six expressions of the Speech original, as `GET /mowa-mes/speech` lists them. A new copy each time. */
export function expresionesDelOriginal(): ExpresionRespuesta[] {
  return NODOS_DEL_ORIGINAL.map(({ segmento, nodos }) => expresionRespuesta(segmento, nodos));
}

/**
 * A stand-in for the rich-text engine API (catalogue, validation, preview),
 * typed against the generated contract: a fake the backend could never send
 * fails to compile (interface rules §9.3).
 *
 * It does not reimplement the engine. The preview applies a handful of
 * functions just well enough for a screen to show something believable;
 * anything a test needs to assert precisely goes through `validacion` or
 * `previsualizacion`, which a test can replace.
 *
 * Every value is invented: no sheet, name, document or phone from the real
 * data reaches a test (/AGENTS.md). Phones use the synthetic 900000xxx range.
 */
import type { Route } from '@playwright/test';

import type { components } from '../src/lib/contrato-api';
import type { Manejador } from './api-falsa';

type Esquemas = components['schemas'];
type Catalogo = Esquemas['CatalogoRespuesta'];
type Funcion = Esquemas['FuncionRespuesta'];
type Parametro = Esquemas['ParametroRespuesta'];
type Validacion = Esquemas['ValidacionRespuesta'];
type Previsualizacion = Esquemas['PrevisualizacionTextoRespuesta'];
type Peticion = Esquemas['PeticionPrevisualizacion'];
type ExpresionEntrada = Esquemas['ExpresionEntrada'];

// ---- Synthetic catalogue -------------------------------------------------------------

function parametro(nombre: string, funcion: string, cambios: Partial<Parametro> = {}): Parametro {
  return {
    nombre,
    clave_nombre: `textoEnriquecido.funcion.${funcion}.parametro.${nombre}`,
    tipo: 'numero',
    obligatorio: true,
    por_defecto: null,
    acepta_variable: false,
    entero: false,
    minimo: null,
    maximo: null,
    largo_minimo: null,
    largo_maximo: null,
    opciones: [],
    opciones_cerradas: false,
    ...cambios,
  };
}

function funcion(
  nombre: string,
  familia: string,
  recibe: Funcion['recibe'],
  devuelve: Funcion['devuelve'],
  parametros: Parametro[] = [],
  aceptaNulo = false,
): Funcion {
  return {
    nombre,
    familia,
    clave_familia: `textoEnriquecido.familia.${familia}`,
    clave_nombre: `textoEnriquecido.funcion.${nombre}.nombre`,
    clave_descripcion: `textoEnriquecido.funcion.${nombre}.descripcion`,
    recibe,
    devuelve,
    acepta_nulo: aceptaNulo,
    parametros,
  };
}

export const FUNCIONES_SINTETICAS: Funcion[] = [
  funcion('primeros', 'texto', ['texto'], 'texto', [parametro('n', 'primeros', { entero: true, minimo: 1 })]),
  funcion('mayusculas', 'texto', ['texto'], 'texto'),
  funcion('sin_tildes', 'texto', ['texto'], 'texto'),
  funcion('redondear', 'numero', ['numero'], 'numero', [
    parametro('decimales', 'redondear', { entero: true, minimo: 0, maximo: 6 }),
  ]),
  funcion('sumar_dias', 'fecha', ['fecha'], 'fecha', [
    parametro('dias', 'sumar_dias', { entero: true, acepta_variable: true }),
  ]),
  funcion('formato_fecha', 'fecha', ['fecha'], 'texto', [
    parametro('patron', 'formato_fecha', {
      tipo: 'texto',
      opciones: [
        { valor: 'dd/mm/aaaa', ejemplo: '05/10/2026' },
        { valor: 'dd-mm-aa', ejemplo: '05-10-26' },
      ],
      opciones_cerradas: false,
    }),
  ]),
  funcion('si_vacio', 'nulos', ['texto', 'numero', 'fecha'], 'entrada', [
    parametro('alternativo', 'si_vacio', { tipo: 'entrada', acepta_variable: true }),
  ], true),
  funcion('enlace_whatsapp', 'enlaces', ['texto'], 'texto', [
    parametro('prefijo', 'enlace_whatsapp', { tipo: 'texto', obligatorio: false, por_defecto: 'https://wa.me/+51' }),
  ]),
];

const SEGMENTOS_SINTETICOS: Esquemas['RangoRespuesta'][] = [
  { clave: 'preventiva', etiqueta: 'Preventiva', desde: null, hasta: 0 },
  { clave: '1_a_8', etiqueta: '1 a 8', desde: 1, hasta: 8 },
  { clave: '9_a_30', etiqueta: '9 a 30', desde: 9, hasta: 30 },
];

/** A catalogue for `contexto`, with the speech's limit when it is the speech. */
export function catalogoSintetico(contexto = 'mowa_mes.speech'): Catalogo {
  const esSpeech = contexto === 'mowa_mes.speech';
  const variables: Esquemas['VariableRespuesta'][] = [
    { nombre: 'titular', tipo: 'texto', clave_nombre: null, origen: 'cartera' },
    { nombre: 'fecha_vencimiento_cuota', tipo: 'fecha', clave_nombre: null, origen: 'cartera' },
    { nombre: 'saldo_capital_pendiente', tipo: 'numero', clave_nombre: null, origen: 'cartera' },
    { nombre: 'telefono', tipo: 'texto', clave_nombre: null, origen: 'cartera' },
    { nombre: 'cliente_fallecido', tipo: 'booleano', clave_nombre: null, origen: 'cartera' },
  ];
  if (esSpeech) {
    variables.push(
      { nombre: 'whatsapp_contacto', tipo: 'texto', clave_nombre: 'textoEnriquecido.variable.whatsapp_contacto', origen: contexto },
      { nombre: 'dias_atraso_ajustados', tipo: 'numero', clave_nombre: 'textoEnriquecido.variable.dias_atraso_ajustados', origen: contexto },
    );
  }

  return {
    contexto: {
      nombre: contexto,
      clave_nombre: `textoEnriquecido.contexto.${contexto}`,
      variables,
      ejemplo: {
        titular: 'NOMBRE SINTETICO DE PRUEBA',
        fecha_vencimiento_cuota: '2026-10-05',
        saldo_capital_pendiente: '1500.50',
        telefono: '900000123',
        cliente_fallecido: false,
        ...(esSpeech ? { whatsapp_contacto: '900000124', dias_atraso_ajustados: 12 } : {}),
      },
      limite_largo: esSpeech ? 160 : null,
      umbral_advertencia: esSpeech ? 150 : null,
      variable_dias: esSpeech ? 'dias_atraso_ajustados' : 'dias_atraso',
      segmentos: SEGMENTOS_SINTETICOS,
    },
    contextos: [
      { nombre: 'cartera', clave_nombre: 'textoEnriquecido.contexto.cartera' },
      { nombre: 'mowa_mes.speech', clave_nombre: 'textoEnriquecido.contexto.mowa_mes.speech' },
    ],
    funciones: FUNCIONES_SINTETICAS,
    familias: ['texto', 'numero', 'conversion', 'fecha', 'nulos', 'enlaces'],
    patrones_fecha: [
      { patron: 'dd/mm/aaaa', ejemplo: '05/10/2026' },
      { patron: 'dd-mm-aa', ejemplo: '05-10-26' },
    ],
    marcas_fecha: [
      { marca: 'dd', clave: 'textoEnriquecido.marcaFecha.dd', ejemplo: '05' },
      { marca: 'mm', clave: 'textoEnriquecido.marcaFecha.mm', ejemplo: '10' },
      { marca: 'aaaa', clave: 'textoEnriquecido.marcaFecha.aaaa', ejemplo: '2026' },
      { marca: 'aa', clave: 'textoEnriquecido.marcaFecha.aa', ejemplo: '26' },
      { marca: 'nombre_mes', clave: 'textoEnriquecido.marcaFecha.nombre_mes', ejemplo: 'octubre' },
    ],
    limites: {
      nodos: 200,
      funciones_por_nodo: 10,
      argumentos_por_funcion: 4,
      largo_literal: 2000,
      columnas_por_definicion: 100,
      variantes_por_columna: 50,
      largo_nombre_definicion: 120,
    },
  };
}

// ---- A believable preview ----------------------------------------------------------------

type NodoEntrada = ExpresionEntrada['nodos'][number];

/** Apply the few functions the fake knows; the rest pass the value through. */
function aplicar(valor: unknown, funciones: NodoEntrada['funciones']): string {
  let actual = valor === null || valor === undefined ? '' : String(valor);
  for (const f of funciones ?? []) {
    const arg = f.args?.[0];
    if (f.nombre === 'primeros' && typeof arg === 'number') actual = actual.slice(0, arg);
    else if (f.nombre === 'mayusculas') actual = actual.toUpperCase();
    else if (f.nombre === 'formato_fecha' && /^\d{4}-\d{2}-\d{2}$/.test(actual)) {
      const [a, m, d] = actual.split('-');
      actual = arg === 'dd-mm-aa' ? `${d}-${m}-${a.slice(2)}` : `${d}/${m}/${a}`;
    } else if (f.nombre === 'enlace_whatsapp' && actual) actual = `${typeof arg === 'string' ? arg : 'https://wa.me/+51'}${actual}`;
    else if (f.nombre === 'si_vacio' && !actual && typeof arg === 'string') actual = arg;
  }
  return actual;
}

function columna(expresion: ExpresionEntrada, registro: Record<string, unknown>, nombre = 'texto'): Esquemas['ColumnaRespuesta'] {
  const nodos = expresion.nodos.map((nodo, indice) => {
    if (nodo.tipo === 'texto') return { indice, tipo: 'texto', texto: nodo.valor ?? '', vacio: false };
    const crudo = registro[nodo.nombre ?? ''];
    const vacio = crudo === null || crudo === undefined || crudo === '';
    return { indice, tipo: 'variable', texto: vacio ? '' : aplicar(crudo, nodo.funciones), vacio };
  });
  const texto = nodos.map((n) => n.texto).join('');
  return {
    nombre,
    tipo: 'texto',
    texto,
    valor: texto,
    largo: [...texto].length,
    cota: null,
    sin_cota: null,
    usa_variante: false,
    nodos,
    problemas: [],
  };
}

// ---- Fake state and handler -----------------------------------------------------------------

export interface ApiFalsaTextoEnriquecido {
  /** Catalogue per context; a context not listed answers 404 `contexto_desconocido`. */
  catalogos: Record<string, Catalogo>;
  /** Answers `POST /validacion`. By default: no problems, type texto, no bound. */
  validacion: (cuerpo: Esquemas['PeticionValidacion']) => Validacion;
  /** Answers `POST /previsualizacion`, or `{ estado, cuerpo }` to fail. */
  previsualizacion: (cuerpo: Peticion, catalogo: Catalogo) => Previsualizacion | { estado: number; cuerpo: unknown };
  /** Synthetic products by pagaré, for `producto_real`. */
  productos: Record<string, Record<string, unknown>>;
  /** Requests received, with their parsed body. */
  pedidos: Array<{ metodo: string; ruta: string; cuerpo: unknown }>;
}

/** Cut-off date of the synthetic products when the request does not name one. */
const FECHA_CORTE_SINTETICA = '2026-10-05';

/** Send date of a real-portfolio sample that does not name one (the backend answers today in Lima). */
const FECHA_ENVIO_SINTETICA = '2026-10-19';

export function previsualizacionSintetica(cuerpo: Peticion, catalogo: Catalogo, productos: ApiFalsaTextoEnriquecido['productos'] = {}): Previsualizacion | { estado: number; cuerpo: unknown } {
  const expresion = cuerpo.expresion ?? { nodos: [] };
  const ejemplo = catalogo.contexto.ejemplo;
  const base = {
    problemas: [],
    limite_largo: catalogo.contexto.limite_largo,
    umbral_advertencia: catalogo.contexto.umbral_advertencia,
    disponibles: null,
    fecha_envio: null as string | null,
  };
  // `pagare` and `fecha_corte` say which product a row is, like the backend: only a real
  // product or a selection has one; the example record answers null and null.
  const fila = (
    numero: number,
    registro: Record<string, unknown>,
    etiqueta: string | null,
    segmento: string | null,
    producto: { pagare: string; fecha_corte: string } | null = null,
  ) => ({
    numero,
    etiqueta,
    segmento,
    pagare: producto?.pagare ?? null,
    fecha_corte: producto?.fecha_corte ?? null,
    excluida: null,
    columnas: [columna(expresion, registro)],
  });

  if (cuerpo.muestra.tipo === 'producto_real') {
    const producto = productos[cuerpo.muestra.pagare ?? ''];
    if (!producto) {
      return { estado: 404, cuerpo: { detail: 'No hay un producto con ese pagaré', codigo: 'producto_no_encontrado' } };
    }
    const fecha = cuerpo.muestra.fecha_corte ?? FECHA_CORTE_SINTETICA;
    return {
      ...base,
      fecha_envio: cuerpo.muestra.fecha_envio ?? FECHA_ENVIO_SINTETICA,
      filas: [fila(1, producto, null, null, { pagare: cuerpo.muestra.pagare!, fecha_corte: fecha })],
    };
  }
  if (cuerpo.muestra.tipo === 'ejemplo') return { ...base, filas: [fila(1, ejemplo, null, null)] };
  if (cuerpo.muestra.tipo === 'primeros_de_seleccion') {
    // One synthetic product per segment, with the example's values and a pagaré of its own.
    const fecha = cuerpo.muestra.fecha_corte ?? FECHA_CORTE_SINTETICA;
    return {
      ...base,
      fecha_envio: cuerpo.muestra.fecha_envio ?? FECHA_ENVIO_SINTETICA,
      filas: catalogo.contexto.segmentos.map((s, i) =>
        fila(i + 1, ejemplo, s.etiqueta, s.clave, { pagare: String(100 + i).padStart(18, '0'), fecha_corte: fecha }),
      ),
    };
  }
  // ejemplos_por_segmento: the example record, one row per segment, no product.
  return {
    ...base,
    filas: catalogo.contexto.segmentos.map((s, i) => fila(i + 1, ejemplo, s.etiqueta, s.clave)),
  };
}

export function apiTextoEnriquecidoVacia(): ApiFalsaTextoEnriquecido {
  const estado: ApiFalsaTextoEnriquecido = {
    catalogos: { 'mowa_mes.speech': catalogoSintetico('mowa_mes.speech'), cartera: catalogoSintetico('cartera') },
    validacion: () => ({ problemas: [], tipo: 'texto', cota: null, sin_cota: null, variables: [] }),
    // Reads `estado.productos` at call time, so a test can add products later.
    previsualizacion: (cuerpo, catalogo) => previsualizacionSintetica(cuerpo, catalogo, estado.productos),
    productos: {},
    pedidos: [],
  };
  return estado;
}

const json = (route: Route, estado: number, cuerpo: unknown) =>
  route.fulfill({ status: estado, contentType: 'application/json', body: JSON.stringify(cuerpo) });

/**
 * The engine's routes, as a handler `montarApi` chains before its 404
 * (`ApiFalsa.manejadores`). Returns `true` when it answered.
 */
export function manejarTextoEnriquecido(estado: ApiFalsaTextoEnriquecido): Manejador {
  return async (route, ruta, metodo, url) => {
    if (!ruta.startsWith('/texto-enriquecido/')) return false;
    let cuerpo: unknown = null;
    const texto = route.request().postData();
    if (texto) cuerpo = JSON.parse(texto);
    estado.pedidos.push({ metodo, ruta: `${ruta}${url.search}`, cuerpo });

    if (ruta === '/texto-enriquecido/catalogo' && metodo === 'GET') {
      const contexto = url.searchParams.get('contexto') ?? 'cartera';
      const catalogo = estado.catalogos[contexto];
      if (!catalogo) await json(route, 404, { detail: `No existe el contexto ${contexto}`, codigo: 'contexto_desconocido' });
      else await json(route, 200, catalogo);
      return true;
    }

    if (ruta === '/texto-enriquecido/validacion' && metodo === 'POST') {
      await json(route, 200, estado.validacion(cuerpo as Esquemas['PeticionValidacion']));
      return true;
    }

    if (ruta === '/texto-enriquecido/previsualizacion' && metodo === 'POST') {
      const peticion = cuerpo as Peticion;
      const catalogo = estado.catalogos[peticion.contexto];
      if (!catalogo) {
        await json(route, 404, { detail: `No existe el contexto ${peticion.contexto}`, codigo: 'contexto_desconocido' });
        return true;
      }
      const respuesta = estado.previsualizacion(peticion, catalogo);
      if ('estado' in respuesta) await json(route, respuesta.estado, respuesta.cuerpo);
      else await json(route, 200, respuesta);
      return true;
    }

    return false;
  };
}

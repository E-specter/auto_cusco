/**
 * A stand-in for `/textos-guardados` (T-HI-B4, RF-69), driven entirely from the test.
 *
 * It behaves like the backend where a spec depends on it (`docs/textos-guardados.md`): the name is unique per context
 * on its normalised form and a disabled text keeps it, a blank name or content is a 400 with located problems, a
 * disabled text takes no new version, a used one cannot be deleted (409), enabling and disabling are idempotent, and
 * every save creates a new version without touching the earlier ones. Typed against the generated contract, so a
 * fake the backend could never send fails to compile. The contexts are synthetic: the real ones belong to their
 * modules. All data is invented.
 *
 * It is a *handler* so it chains with the other fakes (`api.manejadores = [...]` in `api-falsa.ts`).
 * `montarApiTextosGuardados` is the standalone version: anything not handled answers 404, so a missing fake fails loudly.
 */
import type { Page, Route } from '@playwright/test';

import type { ContextoGuardado, ContenidoTexto, ProblemaTexto, ResumenTexto, TextoRespuesta } from '../src/lib/api-textos-guardados';
import type { Manejador } from './api-falsa';
import { json, siguiente } from './apoyo';

export type Respuesta = { estado: number; cuerpo?: unknown };

const RUTA = '/textos-guardados';
const LARGO_NOMBRE = 120;
const LARGO_TEXTO = 200;

export interface VersionFalsa {
  numero: number;
  creado_en: string;
  usada_en: string | null;
  contenido: ContenidoTexto;
}

export interface TextoFalso {
  id: number;
  contexto: string;
  nombre: string;
  creado_en: string;
  deshabilitado_en: string | null;
  versiones: VersionFalsa[];
}

export interface ApiFalsaTextosGuardados {
  /** The contexts a module registered. */
  contextos: ContextoGuardado[];
  textos: TextoFalso[];
  /** Scripted answers, in order; the last one repeats. Empty means "behave". */
  respuestas: { crear: Respuesta[]; versionar: Respuesta[]; renombrar: Respuesta[]; eliminar: Respuesta[] };
  /** When true, every call fails at the network level. */
  sinRed: boolean;
  /** Requests the page made, with their JSON bodies, for asserting on the call. */
  pedidos: Array<{ metodo: string; ruta: string; cuerpo: unknown }>;
}

export const CONTEXTO_PLANO = 'sintetico.texto';
export const CONTEXTO_EXPRESION = 'sintetico.expresion';

export function apiTextosGuardados(): ApiFalsaTextosGuardados {
  return {
    contextos: [
      { clave: CONTEXTO_PLANO, etiqueta: 'Texto sintético', tipo: 'texto_plano' },
      { clave: CONTEXTO_EXPRESION, etiqueta: 'Expresión sintética', tipo: 'expresion' },
    ],
    textos: [],
    respuestas: { crear: [], versionar: [], renombrar: [], eliminar: [] },
    sinRed: false,
    pedidos: [],
  };
}

/**
 * A saved text with `versiones` versions; the first `usadasHasta` of them were used (so they carry `usada_en`).
 * Each version has its own content, so a spec can tell them apart: «Hola {nombre}, v1», «…, v2».
 */
export function textoFalso(
  parcial: Partial<Omit<TextoFalso, 'versiones'>> & { versiones?: number; usadasHasta?: number } = {},
): TextoFalso {
  const { versiones = 1, usadasHasta = 0, ...resto } = parcial;
  const nombre = resto.nombre ?? 'Preventivo';
  return {
    id: 1,
    contexto: CONTEXTO_PLANO,
    nombre,
    creado_en: '2026-10-01T09:00:00-05:00',
    deshabilitado_en: null,
    ...resto,
    versiones: Array.from({ length: versiones }, (_, i) => ({
      numero: i + 1,
      creado_en: `2026-10-0${Math.min(i + 1, 9)}T09:00:00-05:00`,
      usada_en: i < usadasHasta ? '2026-10-03T10:00:00-05:00' : null,
      contenido: { texto: `Hola ${nombre}, v${i + 1}` },
    })),
  };
}

// ---- Reading what the page sent ------------------------------------------------------------------

/** Same normalisation as the backend: no edge spaces, no case; an accent tells names apart. */
const normalizar = (texto: string) => texto.trim().toLowerCase();

const problema = (parcial: Partial<ProblemaTexto> & { detalle: string }): ProblemaTexto => ({
  codigo: 'texto_guardado_invalido',
  ubicacion: null,
  nombre: null,
  columna: null,
  segmento: null,
  campo: null,
  ...parcial,
});

function problemasDe(nombre: unknown, contenido: unknown, contexto: ContextoGuardado): ProblemaTexto[] {
  const problemas: ProblemaTexto[] = [];
  if (nombre !== undefined) {
    if (typeof nombre !== 'string' || nombre.trim().length < 1 || nombre.trim().length > LARGO_NOMBRE) {
      problemas.push(problema({ campo: 'nombre', detalle: `El nombre debe tener entre 1 y ${LARGO_NOMBRE} caracteres` }));
    }
  }
  if (typeof contenido !== 'object' || contenido === null || Array.isArray(contenido)) {
    problemas.push(problema({ campo: 'contenido', detalle: 'El contenido debe ser un objeto' }));
  } else if (contexto.tipo === 'texto_plano') {
    const texto = (contenido as { texto?: unknown }).texto;
    if (typeof texto !== 'string' || texto.trim() === '') {
      problemas.push(problema({ campo: 'contenido', codigo: 'expresion_invalida', detalle: 'El texto no puede estar vacío' }));
    } else if (texto.length > LARGO_TEXTO) {
      problemas.push(problema({ campo: 'contenido', codigo: 'limite_excedido', detalle: `El texto pasa de ${LARGO_TEXTO} caracteres` }));
    }
  } else {
    const nodos = (contenido as { expresion?: { nodos?: unknown[] } }).expresion?.nodos;
    if (!Array.isArray(nodos) || nodos.length === 0) {
      problemas.push(problema({ campo: 'contenido', codigo: 'expresion_invalida', detalle: 'La expresión está vacía' }));
    }
  }
  return problemas;
}

// ---- What the backend answers --------------------------------------------------------------------

const vigente = (t: TextoFalso) => t.versiones[t.versiones.length - 1];
const usada = (v: VersionFalsa) => v.usada_en !== null;

function resumen(t: TextoFalso): ResumenTexto {
  return {
    id: t.id,
    contexto: t.contexto,
    nombre: t.nombre,
    version_vigente: vigente(t).numero,
    cantidad_versiones: t.versiones.length,
    actualizado_en: vigente(t).creado_en,
    vigente_usada: usada(vigente(t)),
    deshabilitado_en: t.deshabilitado_en,
    // T-HI-B6: true when no version was ever used, so the list never offers what the backend would refuse.
    eliminable: !t.versiones.some(usada),
  };
}

function respuestaDe(t: TextoFalso, version: VersionFalsa = vigente(t)): TextoRespuesta {
  return {
    id: t.id,
    contexto: t.contexto,
    nombre: t.nombre,
    creado_en: t.creado_en,
    actualizado_en: vigente(t).creado_en,
    deshabilitado_en: t.deshabilitado_en,
    version_vigente: vigente(t).numero,
    versiones: t.versiones.map((v) => ({ numero: v.numero, creado_en: v.creado_en, usada_en: v.usada_en, usada: usada(v) })),
    version: {
      numero: version.numero,
      creado_en: version.creado_en,
      usada_en: version.usada_en,
      usada: usada(version),
      contenido: version.contenido,
    },
  };
}

const error = (route: Route, estado: number, codigo: string, detalle: string) => json(route, estado, { detail: detalle, codigo });

const invalido = (route: Route, problemas: ProblemaTexto[]) =>
  json(route, 400, {
    detail: `El texto no se puede guardar. ${problemas.map((p) => p.detalle).join('; ')}`,
    codigo: 'texto_guardado_invalido',
    problemas,
  });

/** Anything under `/textos-guardados`; false for any other route. */
export function manejadorTextosGuardados(estado: ApiFalsaTextosGuardados): Manejador {
  return async (route, ruta, metodo, url) => {
    const camino = ruta.split('?')[0];
    if (camino !== RUTA && !camino.startsWith(`${RUTA}/`)) return false;

    if (estado.sinRed) {
      await route.abort('failed');
      return true;
    }

    const texto = route.request().postData();
    const cuerpo: unknown = texto ? JSON.parse(texto) : null;
    estado.pedidos.push({ metodo, ruta, cuerpo });

    const guionada = (cola: Respuesta[]) => {
      const respuesta = siguiente(cola);
      return respuesta ? json(route, respuesta.estado, respuesta.cuerpo ?? {}) : null;
    };
    const contextoDe = (clave: string) => estado.contextos.find((c) => c.clave === clave);
    const desconocido = (clave: string) => error(route, 400, 'contexto_guardado_desconocido', `El contexto ${clave} no esta registrado`);
    const noExiste = () => error(route, 404, 'texto_guardado_no_encontrado', 'No existe el texto');

    if (camino === `${RUTA}/contextos` && metodo === 'GET') {
      await json(route, 200, estado.contextos);
      return true;
    }

    if (camino === RUTA && metodo === 'GET') {
      const clave = url.searchParams.get('contexto') ?? '';
      if (!contextoDe(clave)) {
        await desconocido(clave);
        return true;
      }
      const con = url.searchParams.get('deshabilitados') === 'true';
      const lista = estado.textos
        .filter((t) => t.contexto === clave && (con || t.deshabilitado_en === null))
        .sort((a, b) => normalizar(a.nombre).localeCompare(normalizar(b.nombre)) || a.id - b.id);
      await json(route, 200, lista.map(resumen));
      return true;
    }

    if (camino === RUTA && metodo === 'POST') {
      const entrada = (cuerpo ?? {}) as { contexto?: string; nombre?: unknown; contenido?: unknown };
      const guionado = guionada(estado.respuestas.crear);
      if (guionado) {
        await guionado;
        return true;
      }
      const contexto = contextoDe(entrada.contexto ?? '');
      if (!contexto) {
        await desconocido(entrada.contexto ?? '');
        return true;
      }
      const problemas = problemasDe(entrada.nombre ?? '', entrada.contenido, contexto);
      if (problemas.length) {
        await invalido(route, problemas);
        return true;
      }
      const nombre = (entrada.nombre as string).trim();
      if (estado.textos.some((t) => t.contexto === contexto.clave && normalizar(t.nombre) === normalizar(nombre))) {
        await error(route, 409, 'nombre_repetido', 'Ya existe un texto con ese nombre');
        return true;
      }
      const ahora = new Date().toISOString();
      const nuevo: TextoFalso = {
        id: Math.max(0, ...estado.textos.map((t) => t.id)) + 1,
        contexto: contexto.clave,
        nombre,
        creado_en: ahora,
        deshabilitado_en: null,
        versiones: [{ numero: 1, creado_en: ahora, usada_en: null, contenido: entrada.contenido as ContenidoTexto }],
      };
      estado.textos.push(nuevo);
      await json(route, 201, respuestaDe(nuevo));
      return true;
    }

    const coincidencia = camino.match(/^\/textos-guardados\/(\d+)(\/(versiones|deshabilitar|habilitar))?$/);
    if (!coincidencia) {
      await json(route, 404, { detail: 'Ruta desconocida' });
      return true;
    }
    const existente = estado.textos.find((t) => t.id === Number(coincidencia[1]));
    const accion = coincidencia[3] ?? null;

    if (accion === null && metodo === 'GET') {
      if (!existente) {
        await noExiste();
        return true;
      }
      const pedida = url.searchParams.get('version');
      if (pedida === null) {
        await json(route, 200, respuestaDe(existente));
        return true;
      }
      const version = existente.versiones.find((v) => v.numero === Number(pedida));
      if (!version) {
        await error(route, 404, 'version_no_encontrada', `El texto no tiene la version ${pedida}`);
        return true;
      }
      await json(route, 200, respuestaDe(existente, version));
      return true;
    }

    if (accion === null && metodo === 'PATCH') {
      const guionado = guionada(estado.respuestas.renombrar);
      if (guionado) {
        await guionado;
        return true;
      }
      if (!existente) {
        await noExiste();
        return true;
      }
      const dado = (cuerpo as { nombre?: unknown } | null)?.nombre;
      if (typeof dado !== 'string' || dado.trim().length < 1 || dado.trim().length > LARGO_NOMBRE) {
        await invalido(route, [problema({ campo: 'nombre', detalle: `El nombre debe tener entre 1 y ${LARGO_NOMBRE} caracteres` })]);
        return true;
      }
      const nombre = dado.trim();
      if (estado.textos.some((t) => t.id !== existente.id && t.contexto === existente.contexto && normalizar(t.nombre) === normalizar(nombre))) {
        await error(route, 409, 'nombre_repetido', 'Ya existe un texto con ese nombre');
        return true;
      }
      existente.nombre = nombre;
      await json(route, 200, respuestaDe(existente));
      return true;
    }

    if (accion === 'versiones' && metodo === 'POST') {
      const guionado = guionada(estado.respuestas.versionar);
      if (guionado) {
        await guionado;
        return true;
      }
      if (!existente) {
        await noExiste();
        return true;
      }
      if (existente.deshabilitado_en !== null) {
        await error(route, 409, 'texto_guardado_deshabilitado', 'El texto esta deshabilitado y no admite versiones nuevas');
        return true;
      }
      const contenido = (cuerpo as { contenido?: unknown } | null)?.contenido;
      const problemas = problemasDe(undefined, contenido, contextoDe(existente.contexto)!);
      if (problemas.length) {
        await invalido(route, problemas);
        return true;
      }
      existente.versiones.push({
        numero: vigente(existente).numero + 1,
        creado_en: new Date().toISOString(),
        usada_en: null,
        contenido: contenido as ContenidoTexto,
      });
      await json(route, 201, respuestaDe(existente));
      return true;
    }

    if ((accion === 'deshabilitar' || accion === 'habilitar') && metodo === 'POST') {
      if (!existente) {
        await noExiste();
        return true;
      }
      // Idempotent: asking for the state it already has changes nothing and answers 200.
      if (accion === 'deshabilitar' && existente.deshabilitado_en === null) existente.deshabilitado_en = new Date().toISOString();
      if (accion === 'habilitar') existente.deshabilitado_en = null;
      await json(route, 200, respuestaDe(existente));
      return true;
    }

    if (accion === null && metodo === 'DELETE') {
      const guionado = guionada(estado.respuestas.eliminar);
      if (guionado) {
        await guionado;
        return true;
      }
      if (!existente) {
        await noExiste();
        return true;
      }
      if (existente.versiones.some(usada)) {
        await error(route, 409, 'texto_guardado_usado', 'El texto tiene una version usada: solo se puede deshabilitar');
        return true;
      }
      estado.textos.splice(estado.textos.indexOf(existente), 1);
      await route.fulfill({ status: 204 });
      return true;
    }

    await json(route, 404, { detail: 'Ruta desconocida' });
    return true;
  };
}

/** Route every `/api` call to `estado`; anything else answers 404 so a missing fake fails loudly. */
export async function montarApiTextosGuardados(page: Page, estado: ApiFalsaTextosGuardados): Promise<void> {
  const manejar = manejadorTextosGuardados(estado);
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const atendido = await manejar(route, url.pathname.replace(/^\/api/, ''), route.request().method(), url);
    if (!atendido) await route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"Not Found"}' });
  });
}

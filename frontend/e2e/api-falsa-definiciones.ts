/**
 * A stand-in for `/definiciones-columnas` (B4b), driven entirely from the test.
 *
 * It behaves like the backend where a spec depends on it: a repeated name is a 409
 * `nombre_repetido` (case, accents and edge spaces ignored), a name never changes between
 * versions, a blank column name or no columns is a 400 with located problems, and every save
 * creates a new version without touching the earlier ones. Typed against the generated contract,
 * so a fake the backend could never send fails to compile. All data is invented.
 *
 * It is a *handler* so it chains with the other fakes (`api.manejadores = [...]` in `api-falsa.ts`:
 * true when it answered, false to let the next one try). `montarApiDefiniciones` is the standalone
 * version: anything not handled answers 404 so a missing fake fails loudly.
 */
import type { Page, Route } from '@playwright/test';

import type {
  DefinicionColumnasEntrada,
  DefinicionGuardadaRespuesta,
  ProblemaDefinicion,
  ResumenDefinicion,
} from '../src/lib/api-definiciones';
import type { components } from '../src/lib/contrato-api';
import type { Manejador } from './api-falsa';

type Contenido = components['schemas']['ContenidoGuardadoRespuesta'];
type ColumnaGuardada = components['schemas']['ColumnaGuardadaRespuesta'];
type Expresion = components['schemas']['ExpresionGuardadaRespuesta'];

export type Respuesta = { estado: number; cuerpo?: unknown };

const LARGO_MAXIMO_NOMBRE = 120;
const RUTA = '/definiciones-columnas';

export interface VersionFalsa {
  numero: number;
  creado_en: string;
  usada_en: string | null;
  contenido: Contenido;
}

export interface DefinicionFalsa {
  id: number;
  nombre: string;
  creado_en: string;
  versiones: VersionFalsa[];
}

export interface ApiFalsaDefiniciones {
  definiciones: DefinicionFalsa[];
  /** Scripted answers, in order; the last one repeats. Empty means "behave". */
  respuestas: { crear: Respuesta[]; guardarVersion: Respuesta[]; renombrar: Respuesta[] };
  /** When true, every call fails at the network level. */
  sinRed: boolean;
  /** Requests the page made, with their JSON bodies, for asserting on the call. */
  pedidos: Array<{ metodo: string; ruta: string; cuerpo: unknown }>;
}

export function apiDefiniciones(): ApiFalsaDefiniciones {
  return { definiciones: [], respuestas: { crear: [], guardarVersion: [], renombrar: [] }, sinRed: false, pedidos: [] };
}

const FORMATO_FINANCIERO = { separador_miles: ',', separador_decimal: '.', decimales: 2 } as const;

const variable = (nombre: string, obligatoria = false): Expresion['nodos'][number] => ({
  tipo: 'variable',
  nombre,
  funciones: [],
  obligatoria,
});

/** Two columns every version starts from: enough to render, reorder and edit. */
export function contenidoSintetico(sufijo = ''): Contenido {
  const columna = (orden: number, nombre: string, nodos: Expresion['nodos']): ColumnaGuardada => ({
    nombre,
    orden,
    tipo: 'texto',
    formato_fecha: null,
    formato_financiero: { ...FORMATO_FINANCIERO },
    expresion: { nodos },
    valor_por_defecto: null,
    variantes: [],
  });
  return {
    proteger_formulas: true,
    segmentacion: null,
    columnas: [
      columna(0, `telefono${sufijo}`, [variable('telefono')]),
      columna(1, `mensaje${sufijo}`, [
        variable('titular', true),
        { tipo: 'texto', valor: ' te recuerda tu cuota' },
      ]),
    ],
  };
}

/**
 * A saved definition with `versiones` versions; the first `usadasHasta` of them were used in a
 * load (so they carry `usada_en`). Each version gets its own column names so a spec can tell them apart.
 */
export function definicionFalsa(
  parcial: Partial<Omit<DefinicionFalsa, 'versiones'>> & { versiones?: number; usadasHasta?: number } = {},
): DefinicionFalsa {
  const { versiones = 1, usadasHasta = 0, ...resto } = parcial;
  return {
    id: 1,
    nombre: 'SMS preventivo',
    creado_en: '2026-10-01T09:00:00-05:00',
    ...resto,
    versiones: Array.from({ length: versiones }, (_, i) => ({
      numero: i + 1,
      creado_en: `2026-10-0${Math.min(i + 1, 9)}T09:00:00-05:00`,
      usada_en: i < usadasHasta ? '2026-10-03T10:00:00-05:00' : null,
      contenido: contenidoSintetico(versiones > 1 ? `_v${i + 1}` : ''),
    })),
  };
}

// ---- Reading what the page sent ---------------------------------------------------------------

/** Same normalisation as the backend: no accents, no case, no edge spaces. */
const normalizar = (texto: string) =>
  texto
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .trim()
    .toLowerCase();

type Entrada = DefinicionColumnasEntrada;

const problema = (parcial: Partial<ProblemaDefinicion> & { detalle: string }): ProblemaDefinicion => ({
  codigo: 'definicion_invalida',
  ubicacion: null,
  nombre: null,
  columna: null,
  segmento: null,
  campo: null,
  ...parcial,
});

function problemasDe(entrada: Entrada, nombreExistente: string | null): ProblemaDefinicion[] {
  const problemas: ProblemaDefinicion[] = [];
  const nombre = entrada.nombre;
  if (nombreExistente === null) {
    if (typeof nombre !== 'string' || nombre.trim().length < 1 || nombre.trim().length > LARGO_MAXIMO_NOMBRE) {
      problemas.push(
        problema({ campo: 'nombre', detalle: `El nombre debe tener entre 1 y ${LARGO_MAXIMO_NOMBRE} caracteres` }),
      );
    }
  } else if (typeof nombre === 'string' && nombre.trim() && normalizar(nombre) !== normalizar(nombreExistente)) {
    problemas.push(problema({ campo: 'nombre', detalle: 'El nombre de una definicion no cambia con una version nueva' }));
  }
  if (!entrada.columnas.length) {
    problemas.push(problema({ campo: 'columnas', detalle: 'Una definicion necesita al menos una columna' }));
  }
  entrada.columnas.forEach((columna, indice) => {
    if (!columna.nombre.trim()) {
      problemas.push(problema({ columna: indice, campo: 'nombre', detalle: `La columna ${indice + 1} necesita un nombre` }));
    }
  });
  return problemas;
}

function expresionDe(entrada: Entrada['columnas'][number]['expresion']): Expresion {
  return {
    nodos: entrada.nodos.map((nodo) =>
      nodo.tipo === 'texto'
        ? { tipo: 'texto' as const, valor: nodo.valor ?? '' }
        : {
            tipo: 'variable' as const,
            nombre: nodo.nombre ?? '',
            funciones: (nodo.funciones ?? []).map((f) => ({ nombre: f.nombre, args: (f.args ?? []) as never })),
            obligatoria: Boolean(nodo.obligatoria),
          },
    ),
  };
}

/** What the backend stores: the request completed with its defaults and closed types. */
function contenidoDe(entrada: Entrada): Contenido {
  const criterio = entrada.segmentacion?.criterio;
  return {
    proteger_formulas: entrada.proteger_formulas ?? true,
    segmentacion: criterio
      ? {
          criterio:
            criterio.tipo === 'campo'
              ? { tipo: 'campo', campo: criterio.campo ?? '' }
              : {
                  tipo: 'calculado',
                  variable_dias: criterio.variable_dias ?? 'dias_atraso',
                  tabla: (criterio.tabla ?? []).map((r) => ({
                    clave: r.clave,
                    etiqueta: r.etiqueta,
                    desde: r.desde ?? null,
                    hasta: r.hasta ?? null,
                  })),
                },
          politica: entrada.segmentacion?.politica === 'usar_por_defecto' ? 'usar_por_defecto' : 'excluir',
        }
      : null,
    columnas: [...entrada.columnas]
      .sort((a, b) => a.orden - b.orden)
      .map((c, orden) => ({
        nombre: c.nombre,
        orden,
        tipo: (c.tipo ?? 'texto') as ColumnaGuardada['tipo'],
        formato_fecha: c.formato_fecha ?? null,
        formato_financiero: {
          separador_miles: c.formato_financiero?.separador_miles ?? FORMATO_FINANCIERO.separador_miles,
          separador_decimal: c.formato_financiero?.separador_decimal ?? FORMATO_FINANCIERO.separador_decimal,
          decimales: c.formato_financiero?.decimales ?? FORMATO_FINANCIERO.decimales,
        },
        expresion: expresionDe(c.expresion),
        valor_por_defecto: c.valor_por_defecto ?? null,
        variantes: (c.variantes ?? []).map((v) => ({ segmento: v.segmento as never, expresion: expresionDe(v.expresion) })),
      })),
  };
}

// ---- What the backend answers ---------------------------------------------------------------------

const vigente = (d: DefinicionFalsa) => d.versiones[d.versiones.length - 1];
const esUsada = (v: VersionFalsa) => v.usada_en !== null;

function resumen(d: DefinicionFalsa): ResumenDefinicion {
  return {
    id: d.id,
    nombre: d.nombre,
    version_vigente: vigente(d).numero,
    cantidad_versiones: d.versiones.length,
    actualizado_en: vigente(d).creado_en,
    vigente_usada: esUsada(vigente(d)),
  };
}

function respuestaDe(d: DefinicionFalsa, version: VersionFalsa = vigente(d)): DefinicionGuardadaRespuesta {
  return {
    id: d.id,
    nombre: d.nombre,
    creado_en: d.creado_en,
    actualizado_en: vigente(d).creado_en,
    version_vigente: vigente(d).numero,
    versiones: d.versiones.map((v) => ({
      numero: v.numero,
      creado_en: v.creado_en,
      usada_en: v.usada_en,
      usada: esUsada(v),
    })),
    version: {
      numero: version.numero,
      creado_en: version.creado_en,
      usada_en: version.usada_en,
      usada: esUsada(version),
      contenido: version.contenido,
    },
  };
}

const json = (route: Route, estado: number, cuerpo: unknown) =>
  route.fulfill({ status: estado, contentType: 'application/json', body: JSON.stringify(cuerpo) });

const noExiste = (route: Route, codigo: string, detalle: string) =>
  json(route, 404, { detail: detalle, codigo });

const invalida = (route: Route, problemas: ProblemaDefinicion[]) =>
  json(route, 400, {
    detail: `La definicion no se puede guardar. ${problemas.map((p) => p.detalle).join('; ')}`,
    codigo: 'definicion_invalida',
    problemas,
  });

function siguiente(cola: Respuesta[]): Respuesta | undefined {
  return cola.length > 1 ? cola.shift() : cola[0];
}

/** Anything under `/definiciones-columnas`; false for any other route. */
export function manejadorDefiniciones(estado: ApiFalsaDefiniciones): Manejador {
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

    if (camino === RUTA && metodo === 'GET') {
      const ordenadas = [...estado.definiciones].sort(
        (a, b) => normalizar(a.nombre).localeCompare(normalizar(b.nombre)) || a.id - b.id,
      );
      await json(route, 200, ordenadas.map(resumen));
      return true;
    }

    if (camino === RUTA && metodo === 'POST') {
      const entrada = cuerpo as Entrada;
      const respuesta = guionada(estado.respuestas.crear);
      if (respuesta) {
        await respuesta;
        return true;
      }
      const problemas = problemasDe(entrada, null);
      if (problemas.length) {
        await invalida(route, problemas);
        return true;
      }
      const nombre = (entrada.nombre ?? '').trim();
      if (estado.definiciones.some((d) => normalizar(d.nombre) === normalizar(nombre))) {
        await json(route, 409, { detail: 'Ya existe una definicion con ese nombre', codigo: 'nombre_repetido' });
        return true;
      }
      const ahora = new Date().toISOString();
      const nueva: DefinicionFalsa = {
        id: Math.max(0, ...estado.definiciones.map((d) => d.id)) + 1,
        nombre,
        creado_en: ahora,
        versiones: [{ numero: 1, creado_en: ahora, usada_en: null, contenido: contenidoDe(entrada) }],
      };
      estado.definiciones.push(nueva);
      await json(route, 201, respuestaDe(nueva));
      return true;
    }

    const coincidencia = camino.match(/^\/definiciones-columnas\/(\d+)(\/versiones)?$/);
    if (!coincidencia) {
      await json(route, 404, { detail: 'Ruta desconocida' });
      return true;
    }
    const definicion = estado.definiciones.find((d) => d.id === Number(coincidencia[1]));

    if (!coincidencia[2] && metodo === 'GET') {
      if (!definicion) {
        await noExiste(route, 'definicion_no_encontrada', `No existe la definicion ${coincidencia[1]}`);
        return true;
      }
      const pedida = url.searchParams.get('version');
      if (pedida === null) {
        await json(route, 200, respuestaDe(definicion));
        return true;
      }
      const version = definicion.versiones.find((v) => v.numero === Number(pedida));
      if (!version) {
        await noExiste(route, 'version_no_encontrada', `La definicion no tiene la version ${pedida}`);
        return true;
      }
      await json(route, 200, respuestaDe(definicion, version));
      return true;
    }

    // RF-56 (B14): only the name, no version. The same name (after trimming) answers 200 and changes
    // nothing; a case-only change is a change; another definition's name, in any case or accent, is 409.
    if (!coincidencia[2] && metodo === 'PATCH') {
      const respuesta = guionada(estado.respuestas.renombrar);
      if (respuesta) {
        await respuesta;
        return true;
      }
      if (!definicion) {
        await noExiste(route, 'definicion_no_encontrada', `No existe la definicion ${coincidencia[1]}`);
        return true;
      }
      const nombre = typeof (cuerpo as { nombre?: unknown } | null)?.nombre === 'string' ? (cuerpo as { nombre: string }).nombre.trim() : '';
      if (nombre.length < 1 || nombre.length > LARGO_MAXIMO_NOMBRE) {
        await invalida(route, [
          problema({ campo: 'nombre', detalle: `El nombre debe tener entre 1 y ${LARGO_MAXIMO_NOMBRE} caracteres` }),
        ]);
        return true;
      }
      if (nombre === definicion.nombre) {
        await json(route, 200, respuestaDe(definicion));
        return true;
      }
      if (estado.definiciones.some((d) => d.id !== definicion.id && normalizar(d.nombre) === normalizar(nombre))) {
        await json(route, 409, { detail: 'Ya existe una definicion con ese nombre', codigo: 'nombre_repetido' });
        return true;
      }
      definicion.nombre = nombre;
      await json(route, 200, respuestaDe(definicion));
      return true;
    }

    if (coincidencia[2] && metodo === 'POST') {
      const respuesta = guionada(estado.respuestas.guardarVersion);
      if (respuesta) {
        await respuesta;
        return true;
      }
      if (!definicion) {
        await noExiste(route, 'definicion_no_encontrada', `No existe la definicion ${coincidencia[1]}`);
        return true;
      }
      const entrada = cuerpo as Entrada;
      const problemas = problemasDe(entrada, definicion.nombre);
      if (problemas.length) {
        await invalida(route, problemas);
        return true;
      }
      definicion.versiones.push({
        numero: vigente(definicion).numero + 1,
        creado_en: new Date().toISOString(),
        usada_en: null,
        contenido: contenidoDe(entrada),
      });
      await json(route, 201, respuestaDe(definicion));
      return true;
    }

    await json(route, 404, { detail: 'Ruta desconocida' });
    return true;
  };
}

/** Route every `/api` call to `estado`; anything else answers 404 so a missing fake fails loudly. */
export async function montarApiDefiniciones(page: Page, estado: ApiFalsaDefiniciones): Promise<void> {
  const manejar = manejadorDefiniciones(estado);
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const atendido = await manejar(route, url.pathname.replace(/^\/api/, ''), route.request().method(), url);
    if (!atendido) await route.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"Not Found"}' });
  });
}

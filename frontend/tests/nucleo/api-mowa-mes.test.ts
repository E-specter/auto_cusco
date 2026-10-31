/**
 * The MOWA MES configuration calls. What is worth pinning is what the backend
 * reads: the method, the path, JSON bodies, and that a refusal reaches the
 * screen as an ApiError carrying the server's reason.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../src/lib/api';
import {
  consumoLimite,
  descargarArchivoCampana,
  descartarCampana,
  eliminarCampana,
  importarReporte,
  listarCampanas,
  listarDescartadas,
  listarExclusiones,
  obtenerConciliacion,
  crearSpeech,
  editarSpeech,
  eliminarSpeech,
  guardarConfiguracion,
  modificarSpeech,
  previsualizarSpeech,
  restaurarCampana,
} from '../../src/lib/api-mowa-mes';

function responderCon(estado: number, cuerpo: unknown = {}): ReturnType<typeof vi.fn> {
  const falso = vi.fn(async () =>
    estado === 204
      ? new Response(null, { status: 204 })
      : new Response(JSON.stringify(cuerpo), {
          status: estado,
          headers: { 'content-type': 'application/json' },
        }),
  );
  vi.stubGlobal('fetch', falso);
  return falso;
}

const llamada = (falso: ReturnType<typeof vi.fn>) => ({
  url: String(falso.mock.calls[0][0]),
  opciones: (falso.mock.calls[0][1] ?? {}) as RequestInit,
});

const cuerpoDe = (opciones: RequestInit) => JSON.parse(String(opciones.body));

const PARTES = [{ segmento: 'preventiva' as const, parte_1: ' uno ', parte_2: ' dos' }];

beforeEach(() => vi.unstubAllGlobals());
afterEach(() => vi.unstubAllGlobals());

describe('configuración del conector', () => {
  it('guarda con PUT y manda el WhatsApp vacío como null', async () => {
    const falso = responderCon(200, {});

    await guardarConfiguracion({ limite_mensual: 2_500_000, whatsapp_contacto: null });

    const { url, opciones } = llamada(falso);
    expect(url).toBe('/api/mowa-mes/configuracion');
    expect(opciones.method).toBe('PUT');
    expect(new Headers(opciones.headers).get('content-type')).toBe('application/json');
    expect(cuerpoDe(opciones)).toEqual({ limite_mensual: 2500000, whatsapp_contacto: null });
  });

  it('un WhatsApp fuera de RF-02 llega como 400 con el motivo', async () => {
    responderCon(400, { detail: 'El numero de WhatsApp no es valido' });

    const fallo = await guardarConfiguracion({ limite_mensual: 1, whatsapp_contacto: '12' }).catch(
      (error: unknown) => error,
    );

    expect(fallo).toBeInstanceOf(ApiError);
    expect((fallo as ApiError).status).toBe(400);
    expect((fallo as ApiError).detail).toBe('El numero de WhatsApp no es valido');
  });
});

describe('speech', () => {
  it('una versión nueva viaja con POST y su base', async () => {
    const falso = responderCon(201, {});

    await crearSpeech({ nombre: null, basada_en_id: 1, partes: PARTES });

    const { url, opciones } = llamada(falso);
    expect(url).toBe('/api/mowa-mes/speech');
    expect(opciones.method).toBe('POST');
    // Los espacios de los extremos son parte del mensaje: no se recortan.
    expect(cuerpoDe(opciones)).toEqual({ nombre: null, basada_en_id: 1, partes: PARTES });
  });

  it('editar usa PUT sobre su id, y una versión usada responde 409', async () => {
    const falso = responderCon(409, { detail: 'La version ya se uso' });

    const fallo = await editarSpeech(7, { nombre: 'Speech 2', partes: PARTES }).catch(
      (error: unknown) => error,
    );

    const { url, opciones } = llamada(falso);
    expect(url).toBe('/api/mowa-mes/speech/7');
    expect(opciones.method).toBe('PUT');
    expect((fallo as ApiError).status).toBe(409);
  });

  it('la previsualización pasa la señal de cancelación', async () => {
    const falso = responderCon(200, {});
    const control = new AbortController();

    await previsualizarSpeech({ partes: PARTES }, control.signal);

    const { url, opciones } = llamada(falso);
    expect(url).toBe('/api/mowa-mes/speech/previsualizacion');
    expect(opciones.method).toBe('POST');
    expect(opciones.signal).toBe(control.signal);
    expect(cuerpoDe(opciones)).toEqual({ partes: PARTES });
  });
});

describe('administración de versiones de speech', () => {
  it('renombrar es un PATCH con solo el nombre', async () => {
    const falso = responderCon(200, { id: 7 });

    await modificarSpeech(7, { nombre: 'Nuevo nombre' });

    const { url, opciones } = llamada(falso);
    expect(url).toBe('/api/mowa-mes/speech/7');
    expect(opciones.method).toBe('PATCH');
    expect(cuerpoDe(opciones)).toEqual({ nombre: 'Nuevo nombre' });
  });

  it('deshabilitar y habilitar mandan solo `habilitada`', async () => {
    const deshabilitar = responderCon(200, { id: 7 });
    await modificarSpeech(7, { habilitada: false });
    expect(cuerpoDe(llamada(deshabilitar).opciones)).toEqual({ habilitada: false });

    const habilitar = responderCon(200, { id: 7 });
    await modificarSpeech(7, { habilitada: true });
    expect(cuerpoDe(llamada(habilitar).opciones)).toEqual({ habilitada: true });
  });

  it('un nombre repetido llega como 409 con el motivo del servidor', async () => {
    responderCon(409, { detail: 'Ya existe una version llamada X' });
    const error = await modificarSpeech(7, { nombre: 'X' }).catch((caido: unknown) => caido);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(409);
    expect((error as ApiError).detail).toBe('Ya existe una version llamada X');
  });

  it('eliminar es un DELETE y contesta 204', async () => {
    const falso = responderCon(204);

    await expect(eliminarSpeech(7)).resolves.toBeUndefined();

    expect(llamada(falso).url).toBe('/api/mowa-mes/speech/7');
    expect(llamada(falso).opciones.method).toBe('DELETE');
  });

  it('el 409 de eliminar trae su código', async () => {
    responderCon(409, { detail: 'usada', codigo: 'speech_usado' });
    const error = await eliminarSpeech(7).catch((caido: unknown) => caido);
    expect((error as ApiError).status).toBe(409);
    expect((error as ApiError).codigo).toBe('speech_usado');
  });
});

describe('campañas y seguimiento', () => {
  it('lista campañas paginando con límite y desplazamiento', async () => {
    const falso = responderCon(200, { total: 0, limite: 20, desplazamiento: 40, campanas: [] });

    await listarCampanas({ limite: 20, desplazamiento: 40 });

    const url = new URL(llamada(falso).url, 'http://x');
    expect(url.pathname).toBe('/api/mowa-mes/campanas');
    expect(url.searchParams.get('limite')).toBe('20');
    expect(url.searchParams.get('desplazamiento')).toBe('40');
  });

  it('las descartadas mandan `mes` solo cuando se elige uno', async () => {
    const todas = responderCon(200, { campanas: [], meses: [], total_descartadas: 0 });
    await listarDescartadas();
    const sinMes = new URL(llamada(todas).url, 'http://x');
    expect(sinMes.pathname).toBe('/api/mowa-mes/campanas/descartadas');
    expect(sinMes.searchParams.has('mes')).toBe(false);

    const delMes = responderCon(200, { campanas: [], meses: [], total_descartadas: 0 });
    await listarDescartadas('2026-10');
    expect(new URL(llamada(delMes).url, 'http://x').searchParams.get('mes')).toBe('2026-10');
  });

  it('descartar y restaurar son POST sin cuerpo; eliminar es DELETE y contesta 204', async () => {
    const descartar = responderCon(200, { id: 7 });
    await descartarCampana(7);
    expect(llamada(descartar).url).toBe('/api/mowa-mes/campanas/7/descartar');
    expect(llamada(descartar).opciones.method).toBe('POST');
    expect(llamada(descartar).opciones.body).toBeUndefined();

    const restaurar = responderCon(200, { id: 7 });
    await restaurarCampana(7);
    expect(llamada(restaurar).url).toBe('/api/mowa-mes/campanas/7/restaurar');
    expect(llamada(restaurar).opciones.method).toBe('POST');

    const eliminar = responderCon(204);
    await expect(eliminarCampana(7)).resolves.toBeUndefined();
    expect(llamada(eliminar).url).toBe('/api/mowa-mes/campanas/7');
    expect(llamada(eliminar).opciones.method).toBe('DELETE');
  });

  it('eliminar una activa llega como 409 con su código', async () => {
    responderCon(409, { detail: 'activa', codigo: 'campana_no_descartada' });
    const error = await eliminarCampana(7).catch((caido: unknown) => caido);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(409);
    expect((error as ApiError).codigo).toBe('campana_no_descartada');
  });

  it('las exclusiones mandan `codigo` solo cuando hay filtro', async () => {
    const sinFiltro = responderCon(200, {});
    await listarExclusiones(7);
    const url = new URL(llamada(sinFiltro).url, 'http://x');
    expect(url.pathname).toBe('/api/mowa-mes/campanas/7/exclusiones');
    expect(url.searchParams.has('codigo')).toBe(false);

    const conFiltro = responderCon(200, {});
    await listarExclusiones(7, { codigo: 'telefono_invalido', desplazamiento: 50 });
    const filtrada = new URL(llamada(conFiltro).url, 'http://x');
    expect(filtrada.searchParams.get('codigo')).toBe('telefono_invalido');
    expect(filtrada.searchParams.get('desplazamiento')).toBe('50');
  });

  it('el consumo del límite manda el mes solo si se indica', async () => {
    const actual = responderCon(200, {});
    await consumoLimite();
    expect(llamada(actual).url).toBe('/api/mowa-mes/limite-mensual');

    const otro = responderCon(200, {});
    await consumoLimite('2099-01');
    expect(new URL(llamada(otro).url, 'http://x').searchParams.get('mes')).toBe('2099-01');
  });

  it('descarga el archivo y lee su resumen con el prefijo X-Mowa-Mes-', async () => {
    const falso = vi.fn(
      async () =>
        new Response('xlsx sintetico', {
          status: 200,
          headers: {
            'content-type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'content-disposition': 'attachment; filename="CAMPANA_7_ARCHIVO_2.xlsx"',
            'x-mowa-mes-archivo': '2',
            'x-mowa-mes-filas': '45851',
            'x-otra-cabecera': 'no',
          },
        }),
    );
    vi.stubGlobal('fetch', falso);

    const descargado = await descargarArchivoCampana(7, 2);

    expect(llamada(falso).url).toBe('/api/mowa-mes/campanas/7/archivos/2');
    expect(descargado.nombre).toBe('CAMPANA_7_ARCHIVO_2.xlsx');
    expect(descargado.resumen).toEqual({ archivo: '2', filas: '45851' });
  });

  it('importa el reporte como multipart con archivo y reemplazar', async () => {
    const falso = responderCon(201, {});
    const archivo = new File(['reporte sintetico'], 'REPORTE_SINTETICO.xlsx');

    await importarReporte(7, archivo, true);

    const { url, opciones } = llamada(falso);
    expect(url).toBe('/api/mowa-mes/campanas/7/reportes');
    expect(opciones.method).toBe('POST');
    const cuerpo = opciones.body as FormData;
    expect((cuerpo.get('archivo') as File).name).toBe('REPORTE_SINTETICO.xlsx');
    expect(cuerpo.get('reemplazar')).toBe('true');
  });

  it('un id ya importado llega como 409 con el motivo', async () => {
    responderCon(409, { detail: 'El id de MES 990000001 ya estaba importado' });

    const fallo = await importarReporte(7, new File(['x'], 'r.xlsx')).catch((error: unknown) => error);

    expect((fallo as ApiError).status).toBe(409);
    expect((fallo as ApiError).detail).toBe('El id de MES 990000001 ya estaba importado');
  });

  it('pide la conciliación de su campaña', async () => {
    const falso = responderCon(200, {});
    await obtenerConciliacion(7);
    expect(llamada(falso).url).toBe('/api/mowa-mes/campanas/7/conciliacion');
  });
});

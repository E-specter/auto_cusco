/**
 * State of the "Generar carga" screen. The request is built from what the user sees and nothing
 * else: a wrong filter, a pinned version nobody chose or an indicator that slips in would generate
 * the wrong file for a collections team.
 */
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

import {
  CANTIDAD_MAXIMA,
  CANTIDAD_POR_DEFECTO,
  borradorNuevo,
  cantidadDe,
  cantidadInicial,
  cantidadInvalida,
  UMBRAL_AGRUPAR,
  agruparProblemas,
  cantidadSigueLaSeleccion,
  conCantidad,
  conDefinicion,
  conFormato,
  conFormatos,
  conOpcion,
  conSeleccion,
  conVersion,
  consultaVacia,
  filasMaximas,
  mismaPeticion,
  motivoInactivo,
  opcionesDe,
  opcionesParaEnviar,
  peticionDe,
  problemasDeCarga,
  resumenDeCabeceras,
  suficienciaDe,
  valorDeOpcion,
  versionEfectiva,
  type Borrador,
  type FormatoDisponible,
} from '../../src/lib/generar-carga';
import type { Consulta } from '../../src/lib/seleccion';

const CONSULTA: Consulta = {
  filtros: ['segmento_financiero:igual:1. Preventiva', 'telefono:no_vacio'],
  orden: '-saldo_capital_pendiente',
  cantidad: 500,
  indicadores: ['total:suma:saldo_capital_pendiente'],
};

/** A screen with everything chosen: ready to generate. */
function listo(): Borrador {
  let b = borradorNuevo();
  b = conSeleccion(b, { fechaCorte: '2026-09-10', consulta: CONSULTA, aplicable: true });
  b = conDefinicion(b, 7, 4);
  return b;
}

describe('cantidadInicial', () => {
  it('toma el top n de la selección', () => {
    expect(cantidadInicial({ cantidad: 500 })).toBe(500);
  });

  it('usa el valor por defecto del contrato cuando la selección no tiene cantidad', () => {
    expect(cantidadInicial({ cantidad: null })).toBe(CANTIDAD_POR_DEFECTO);
    expect(CANTIDAD_POR_DEFECTO).toBe(1000);
  });
});

describe('cantidad que sigue a la selección', () => {
  it('sigue a la selección hasta que el usuario la edita', () => {
    let b = conSeleccion(borradorNuevo(), { fechaCorte: '2026-09-10', consulta: CONSULTA, aplicable: true });
    expect(b.cantidadTexto).toBe('500');
    expect(cantidadSigueLaSeleccion(b)).toBe(true);

    b = conSeleccion(b, { fechaCorte: '2026-09-10', consulta: { ...CONSULTA, cantidad: 80 }, aplicable: true });
    expect(b.cantidadTexto).toBe('80');
    b = conSeleccion(b, { fechaCorte: '2026-09-10', consulta: { ...CONSULTA, cantidad: null }, aplicable: true });
    expect(b.cantidadTexto).toBe('1000');
  });

  it('deja de seguirla con la primera edición, aunque el texto quede igual', () => {
    let b = conSeleccion(borradorNuevo(), { fechaCorte: '2026-09-10', consulta: CONSULTA, aplicable: true });
    b = conCantidad(b, '500');
    expect(cantidadSigueLaSeleccion(b)).toBe(false);

    b = conSeleccion(b, { fechaCorte: '2026-09-10', consulta: { ...CONSULTA, cantidad: 80 }, aplicable: true });
    expect(b.cantidadTexto).toBe('500');
  });

  it('un campo vacío también cuenta como editado', () => {
    const b = conCantidad(listo(), '');
    expect(cantidadSigueLaSeleccion(b)).toBe(false);
    expect(cantidadInvalida(b)).toBe(true);
  });
});

describe('cantidadDe', () => {
  const con = (texto: string) => cantidadDe({ cantidadTexto: texto });

  it('acepta enteros entre 1 y el tope', () => {
    expect(con('1')).toBe(1);
    expect(con(' 1200 ')).toBe(1200);
    expect(con(String(CANTIDAD_MAXIMA))).toBe(CANTIDAD_MAXIMA);
    expect(CANTIDAD_MAXIMA).toBe(120_000);
  });

  it('rechaza cero, el tope más uno, decimales, negativos y texto', () => {
    for (const texto of ['0', String(CANTIDAD_MAXIMA + 1), '1.5', '-3', 'abc', '', ' ', '1e3', '12 mil']) {
      expect(con(texto), texto).toBeNull();
    }
  });
});

describe('versiones', () => {
  it('elegir la vigente no fija versión: el pedido deja que la API tome la actual', () => {
    const b = conVersion(listo(), 4);
    expect(b.version).toBeNull();
    expect(versionEfectiva(b)).toBe(4);
    expect(peticionDe(b)!.definicion_guardada).toEqual({ id: 7 });
  });

  it('elegir una anterior la fija', () => {
    const b = conVersion(listo(), 2);
    expect(b.version).toBe(2);
    expect(versionEfectiva(b)).toBe(2);
    expect(peticionDe(b)!.definicion_guardada).toEqual({ id: 7, version: 2 });
  });

  it('volver a la vigente suelta la versión fijada', () => {
    const b = conVersion(conVersion(listo(), 2), 4);
    expect(b.version).toBeNull();
  });

  it('cambiar de definición suelta la versión fijada en la anterior', () => {
    const b = conDefinicion(conVersion(listo(), 2), 9, 1);
    expect(b.version).toBeNull();
    expect(versionEfectiva(b)).toBe(1);
    expect(peticionDe(b)!.definicion_guardada).toEqual({ id: 9 });
  });
});

describe('peticionDe', () => {
  it('lleva filtros y orden tal como los escribió el selector', () => {
    const p = peticionDe(listo())!;
    expect(p.filtros).toEqual(['segmento_financiero:igual:1. Preventiva', 'telefono:no_vacio']);
    expect(p.orden).toBe('-saldo_capital_pendiente');
    expect(p.fecha_corte).toBe('2026-09-10');
    expect(p.formato).toBe('xlsx');
  });

  it('conserva el orden de los filtros, que es el que escribió el analista', () => {
    const filtros = ['telefono:no_vacio', 'dias_atraso:mayor:30', 'agencia:igual:A'];
    const b = conSeleccion(listo(), { fechaCorte: '2026-09-10', consulta: { ...CONSULTA, filtros }, aplicable: true });
    expect(peticionDe(b)!.filtros).toEqual(filtros);
  });

  it('nunca envía indicadores ni una definición en línea', () => {
    const p = peticionDe(listo()) as Record<string, unknown>;
    expect(p).not.toHaveProperty('indicadores');
    expect(p).not.toHaveProperty('definicion');
    expect(p).not.toHaveProperty('seleccion_id');
  });

  it('usa la cantidad del campo, no la de la selección', () => {
    expect(peticionDe(listo())!.cantidad).toBe(500);
    expect(peticionDe(conCantidad(listo(), '1200'))!.cantidad).toBe(1200);
  });

  it('copia los filtros: cambiarlos después no altera lo ya pedido', () => {
    const b = listo();
    const p = peticionDe(b)!;
    b.consulta.filtros.push('otro:igual:x');
    expect(p.filtros).toHaveLength(2);
  });

  it('sin filtros ni orden envía lista vacía y orden nulo', () => {
    const b = conSeleccion(listo(), { fechaCorte: '2026-09-10', consulta: consultaVacia(), aplicable: true });
    const p = peticionDe(b)!;
    expect(p.filtros).toEqual([]);
    expect(p.orden).toBeNull();
    expect(p.cantidad).toBe(1000);
  });

  it('lleva el formato elegido', () => {
    expect(peticionDe(conFormato(listo(), 'csv'))!.formato).toBe('csv');
    expect(peticionDe(conFormato(listo(), 'json'))!.formato).toBe('json');
  });

  it('es nula mientras falte algo', () => {
    expect(peticionDe(borradorNuevo())).toBeNull();
    expect(peticionDe(conCantidad(listo(), '0'))).toBeNull();
    expect(peticionDe(conDefinicion(listo(), null, null))).toBeNull();
    expect(peticionDe(conSeleccion(listo(), { fechaCorte: null, consulta: CONSULTA, aplicable: true }))).toBeNull();
    expect(peticionDe(conSeleccion(listo(), { fechaCorte: '2026-09-10', consulta: CONSULTA, aplicable: false }))).toBeNull();
  });
});

describe('motivoInactivo', () => {
  it('es nulo cuando todo está elegido', () => {
    expect(motivoInactivo(listo())).toBeNull();
  });

  it('dice lo primero que falta, en el orden en que el usuario lo encuentra', () => {
    expect(motivoInactivo(borradorNuevo())).toBe('sin_fecha');

    const sinAplicar = conSeleccion(borradorNuevo(), { fechaCorte: '2026-09-10', consulta: CONSULTA, aplicable: false });
    expect(motivoInactivo(sinAplicar)).toBe('seleccion_no_aplica');

    const sinDefinicion = conSeleccion(borradorNuevo(), { fechaCorte: '2026-09-10', consulta: CONSULTA, aplicable: true });
    expect(motivoInactivo(sinDefinicion)).toBe('sin_definicion');

    expect(motivoInactivo(conCantidad(listo(), '0'))).toBe('cantidad_invalida');
  });

  it('con varias cosas faltando gana la primera', () => {
    const b = conCantidad(borradorNuevo(), 'x');
    expect(motivoInactivo(b)).toBe('sin_fecha');
    const c = conCantidad(conSeleccion(borradorNuevo(), { fechaCorte: '2026-09-10', consulta: CONSULTA, aplicable: true }), 'x');
    expect(motivoInactivo(c)).toBe('sin_definicion');
  });
});

describe('mismaPeticion', () => {
  it('reconoce el mismo pedido y distingue cualquier cambio', () => {
    const a = peticionDe(listo());
    expect(mismaPeticion(a, peticionDe(listo()))).toBe(true);
    expect(mismaPeticion(a, peticionDe(conCantidad(listo(), '501')))).toBe(false);
    expect(mismaPeticion(a, peticionDe(conFormato(listo(), 'csv')))).toBe(false);
    expect(mismaPeticion(a, peticionDe(conVersion(listo(), 2)))).toBe(false);
    expect(mismaPeticion(null, null)).toBe(true);
    expect(mismaPeticion(a, null)).toBe(false);
  });
});

describe('resumenDeCabeceras', () => {
  const completo = {
    generados: '3200',
    disponibles: '3200',
    solicitados: '5000',
    suficiente: '0',
    errores: '2',
    excluidos: '4',
  };

  it('lee los números de la descarga', () => {
    expect(resumenDeCabeceras(completo)).toEqual({
      generados: 3200,
      disponibles: 3200,
      solicitados: 5000,
      suficiente: false,
      errores: 2,
      excluidos: 4,
    });
    expect(resumenDeCabeceras({ ...completo, suficiente: '1' })!.suficiente).toBe(true);
  });

  it('es nulo si falta una cabecera o no es un número, en vez de inventar ceros', () => {
    for (const clave of Object.keys(completo)) {
      const sin: Record<string, string> = { ...completo };
      delete sin[clave];
      expect(resumenDeCabeceras(sin), clave).toBeNull();
    }
    expect(resumenDeCabeceras({ ...completo, generados: 'muchos' })).toBeNull();
    expect(resumenDeCabeceras({ ...completo, errores: '-1' })).toBeNull();
    expect(resumenDeCabeceras({ ...completo, suficiente: 'si' })).toBeNull();
    expect(resumenDeCabeceras({})).toBeNull();
  });

  it('ignora cabeceras que no conoce', () => {
    expect(resumenDeCabeceras({ ...completo, otra: 'x' })).not.toBeNull();
  });
});

describe('suficienciaDe', () => {
  it('suficiente no lleva números', () => {
    expect(suficienciaDe({ suficiente: true, disponibles: 9000, solicitados: 5000 })).toEqual({ suficiente: true });
  });

  it('insuficiente dice cuántos había y cuántos se pidieron', () => {
    expect(suficienciaDe({ suficiente: false, disponibles: 3200, solicitados: 5000 })).toEqual({
      suficiente: false,
      disponibles: 3200,
      solicitados: 5000,
    });
  });
});

describe('filasMaximas', () => {
  it('antes de la vista previa es lo pedido', () => {
    expect(filasMaximas(5000, null)).toBe(5000);
  });

  it('con la vista previa no pasa de lo disponible ni de lo pedido', () => {
    expect(filasMaximas(5000, 3200)).toBe(3200);
    expect(filasMaximas(500, 3200)).toBe(500);
    expect(filasMaximas(500, 0)).toBe(0);
  });
});

/** What `/formatos` says in B12: every option with its type, default and limits. */
const FORMATOS: FormatoDisponible[] = [
  {
    formato: 'csv',
    extension: 'csv',
    opciones: [
      { nombre: 'delimitador', tipo: 'texto', defecto: ',', sugeridos: [',', ';', '\t', '|'], minimo: 1, maximo: 1 },
      { nombre: 'codificacion', tipo: 'texto', defecto: 'utf-8', sugeridos: ['utf-8', 'latin-1'], minimo: null, maximo: null },
      { nombre: 'con_cabeceras', tipo: 'booleano', defecto: true, sugeridos: null, minimo: null, maximo: null },
    ],
  },
  {
    formato: 'xlsx',
    extension: 'xlsx',
    opciones: [
      { nombre: 'con_cabeceras', tipo: 'booleano', defecto: true, sugeridos: null, minimo: null, maximo: null },
      { nombre: 'hoja', tipo: 'texto', defecto: 'Carga', sugeridos: null, minimo: null, maximo: 31 },
    ],
  },
  {
    formato: 'json',
    extension: 'json',
    opciones: [
      { nombre: 'codificacion', tipo: 'texto', defecto: 'utf-8', sugeridos: ['utf-8', 'latin-1'], minimo: null, maximo: null },
      { nombre: 'sangria', tipo: 'entero', defecto: null, sugeridos: null, minimo: 0, maximo: 8 },
    ],
  },
];

const conFormatosListos = (): Borrador => conFormatos(listo(), FORMATOS);

describe('opciones del formato', () => {
  it('cada formato muestra solo las suyas, en el orden de la API', () => {
    expect(opcionesDe(FORMATOS, 'csv').map((o) => o.nombre)).toEqual(['delimitador', 'codificacion', 'con_cabeceras']);
    expect(opcionesDe(FORMATOS, 'xlsx').map((o) => o.nombre)).toEqual(['con_cabeceras', 'hoja']);
    expect(opcionesDe(FORMATOS, 'json').map((o) => o.nombre)).toEqual(['codificacion', 'sangria']);
    expect(opcionesDe([], 'csv')).toEqual([]);
  });

  it('sin tocar nada se muestra el defecto del backend y no se envía nada', () => {
    const b = conFormato(conFormatosListos(), 'csv');
    const [delimitador, , cabeceras] = opcionesDe(FORMATOS, 'csv');
    expect(valorDeOpcion(b, delimitador)).toBe(',');
    expect(valorDeOpcion(b, cabeceras)).toBe(true);
    expect(opcionesParaEnviar(b)).toEqual({ opciones: null, invalidas: [] });
    expect(peticionDe(b)).not.toHaveProperty('opciones');
  });

  it('un defecto nulo (la sangria: una línea) se muestra vacío', () => {
    const sangria = opcionesDe(FORMATOS, 'json')[1];
    expect(valorDeOpcion({ opciones: {} }, sangria)).toBe('');
  });

  it('lo editado se muestra y se envía junto a los defectos de las demás, completo', () => {
    const b = conOpcion(conFormato(conFormatosListos(), 'csv'), 'delimitador', ';');
    expect(valorDeOpcion(b, opcionesDe(FORMATOS, 'csv')[0])).toBe(';');
    expect(peticionDe(b)!.opciones).toEqual({
      delimitador: ';',
      codificacion: 'utf-8',
      con_cabeceras: true,
      hoja: 'Carga',
      sangria: null,
    });
  });

  it('un booleano editado se envía como booleano', () => {
    const b = conOpcion(conFormato(conFormatosListos(), 'xlsx'), 'con_cabeceras', false);
    expect(peticionDe(b)!.opciones!.con_cabeceras).toBe(false);
  });

  it('una sangria con dígitos se envía como número; vacía vuelve a «una línea»', () => {
    const json = conFormato(conFormatosListos(), 'json');
    expect(peticionDe(conOpcion(json, 'sangria', '4'))!.opciones!.sangria).toBe(4);
    expect(peticionDe(conOpcion(json, 'sangria', ' 2 '))!.opciones!.sangria).toBe(2);
    expect(peticionDe(conOpcion(json, 'sangria', ''))!.opciones!.sangria).toBeNull();
  });

  it('no valida rangos: 99 espacios se envían y el backend decide', () => {
    const b = conOpcion(conFormato(conFormatosListos(), 'json'), 'sangria', '99');
    expect(peticionDe(b)!.opciones!.sangria).toBe(99);
  });

  it('no valida reglas de plataforma: una hoja con caracteres raros o muy larga se envía tal cual', () => {
    const larga = 'Hoja:de/carga?'.repeat(5);
    const b = conOpcion(conFormato(conFormatosListos(), 'xlsx'), 'hoja', larga);
    expect(peticionDe(b)!.opciones!.hoja).toBe(larga);
  });

  it('una sangria que no es un número impide pedir y lo dice', () => {
    const b = conOpcion(conFormato(conFormatosListos(), 'json'), 'sangria', 'cuatro');
    expect(opcionesParaEnviar(b).invalidas).toEqual(['sangria']);
    expect(motivoInactivo(b)).toBe('opcion_invalida');
    expect(peticionDe(b)).toBeNull();
  });

  it('una opción inválida de otro formato no bloquea este', () => {
    const malo = conOpcion(conFormato(conFormatosListos(), 'json'), 'sangria', 'cuatro');
    const csv = conFormato(malo, 'csv');
    expect(motivoInactivo(csv)).toBeNull();
    expect(peticionDe(csv)!.opciones!.sangria).toBeNull();
  });

  it('un texto vacío es «nada escrito»: aplica el defecto', () => {
    const b = conOpcion(conFormato(conFormatosListos(), 'csv'), 'delimitador', '');
    expect(peticionDe(b)!.opciones!.delimitador).toBe(',');
  });

  it('cambiar de formato conserva lo editado de una opción que comparten', () => {
    const csv = conOpcion(conFormato(conFormatosListos(), 'csv'), 'codificacion', 'latin-1');
    const json = conFormato(csv, 'json');
    expect(valorDeOpcion(json, opcionesDe(FORMATOS, 'json')[0])).toBe('latin-1');
  });

  it('sin /formatos que describan las opciones no inventa un cuerpo', () => {
    const b = conOpcion(conFormato(listo(), 'csv'), 'delimitador', ';');
    expect(opcionesParaEnviar(b).opciones).toBeNull();
  });
});

describe('problemas de la vista previa', () => {
  const error = (fila: number, campo: string) => ({ fila, campo, detalle: `falla ${campo}` });
  const exclusion = (fila: number, codigo = 'sin_segmento', pagare: string | null = `900000${fila}`) => ({
    fila,
    pagare,
    codigo,
    detalle: 'no cae en un segmento',
  });

  it('une errores y exclusiones: primero los errores, cada tipo por su fila', () => {
    const lista = problemasDeCarga({
      errores: [error(3, 'mensaje'), error(1, 'mensaje')],
      exclusiones: [exclusion(9), exclusion(5)],
    } as never);
    expect(lista.map((p) => `${p.tipo}${p.fila}`)).toEqual(['error1', 'error3', 'exclusion5', 'exclusion9']);
  });

  it('no inventa problemas: sin errores ni exclusiones no hay lista', () => {
    expect(problemasDeCarga({ errores: [], exclusiones: [] })).toEqual([]);
    expect(agruparProblemas([])).toEqual([]);
  });

  it('hasta el umbral cada fila va suelta', () => {
    const lista = problemasDeCarga({
      errores: [],
      exclusiones: Array.from({ length: UMBRAL_AGRUPAR }, (_, i) => exclusion(i + 1)),
    } as never);
    expect(agruparProblemas(lista).map((e) => e.tipo)).toEqual(Array(UMBRAL_AGRUPAR).fill('fila'));
  });

  it('pasado el umbral, las del mismo código son un grupo con todas dentro, en el lugar de la primera', () => {
    const lista = problemasDeCarga({
      errores: [error(2, 'mensaje')],
      exclusiones: [
        ...Array.from({ length: UMBRAL_AGRUPAR + 1 }, (_, i) => exclusion(i + 1)),
        exclusion(20, 'otro_codigo'),
      ],
    } as never);
    const elementos = agruparProblemas(lista);
    expect(elementos.map((e) => e.tipo)).toEqual(['fila', 'grupo', 'fila']);
    const grupo = elementos[1];
    expect(grupo.tipo === 'grupo' && grupo.problemas).toHaveLength(UMBRAL_AGRUPAR + 1);
    expect(grupo.tipo === 'grupo' && grupo.clave).toBe('exclusion:sin_segmento');
  });

  it('agrupa los errores por columna, no por código', () => {
    const lista = problemasDeCarga({
      errores: Array.from({ length: UMBRAL_AGRUPAR + 1 }, (_, i) => error(i + 1, 'mensaje')),
      exclusiones: [],
    } as never);
    const elementos = agruparProblemas(lista);
    expect(elementos).toHaveLength(1);
    expect(elementos[0].tipo === 'grupo' && elementos[0].clave).toBe('error:mensaje');
  });

  it('errores de columnas distintas no se mezclan en un grupo', () => {
    const lista = problemasDeCarga({
      errores: [
        ...Array.from({ length: UMBRAL_AGRUPAR }, (_, i) => error(i + 1, 'a')),
        ...Array.from({ length: UMBRAL_AGRUPAR }, (_, i) => error(i + 1, 'b')),
      ],
      exclusiones: [],
    } as never);
    expect(agruparProblemas(lista).every((e) => e.tipo === 'fila')).toBe(true);
  });
});

describe('el módulo no declara interfaces', () => {
  // `PeticionGeneracion` y compañía tienen firma de índice (`extra="allow"`): un `interface` que las
  // extienda o use como campo no compila con `tsc`, aunque `astro check` no lo note.
  it('usa `type`', () => {
    const fuente = readFileSync(new URL('../../src/lib/generar-carga.ts', import.meta.url), 'utf-8');
    expect(fuente).not.toMatch(/^\s*(export\s+)?interface\s/m);
  });
});

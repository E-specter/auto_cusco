/**
 * What the WhatsMKT campaign screen decides on its own (T-WM-F2a1): the request for the preview it builds from the form,
 * the problems that stop creating (the API's and the form's), the names of the lot, and how a definition's columns, a
 * segment's days and an attachment read. The API stays the judge; the preview is its answer.
 */
import { afterEach, beforeAll, describe, expect, it } from 'vitest';

import type { ConfiguracionWhatsmkt, SegmentoWhatsmkt } from '../../src/lib/api-whatsmkt';
import {
  borradorInicial,
  cantidadDeMacros,
  datosDeFicha,
  diasDeSegmento,
  entradaDeCreacion,
  entradaDePrevisualizacion,
  etiquetaDeAdjunto,
  fechaDeFormulario,
  filasDeColumnas,
  horariosElegidos,
  motivoDeCrear,
  nombresDeLote,
  problemasLocales,
  quedoArchivado,
  seccionDeProblema,
  textoDeProblema,
  textoDeProblemaConSegmento,
  textoDeSubida,
  variablesDesconocidasDeNombre,
  type BorradorCampana,
  type SeleccionBase,
} from '../../src/lib/whatsmkt-campana';
import { setLanguageForTests } from './idioma';

beforeAll(() => setLanguageForTests('es'));
afterEach(() => setLanguageForTests('es'));

const CONFIGURACION: ConfiguracionWhatsmkt = {
  horario_1: { inicio: '08:00', fin: '14:00' },
  horario_2: { inicio: '14:00', fin: '20:00' },
  plantilla_nombre: 'CUZCO_Vencida ({segmento}) whatsapp {fecha_corte}',
  definicion_defecto_id: 11,
  whatsapp_contacto: null,
  tope_mensaje: 4096,
  tope_video: 16_000_000,
  tope_audio: 16_000_000,
  tope_pdf: 16_000_000,
  actualizado_en: null,
  variables_plantilla: ['fecha_corte', 'segmento'],
};

const SEGMENTOS: SegmentoWhatsmkt[] = [
  { clave: 'preventivo', etiqueta: 'Preventivo', desde: null, hasta: 0, orden: 0, texto_guardado_id: 7 },
  { clave: 'tramo_2', etiqueta: 'Tramo 2', desde: 1, hasta: 8, orden: 1, texto_guardado_id: 8 },
  { clave: 'mayores_2', etiqueta: 'Tramos mayores al 2', desde: 9, hasta: null, orden: 2, texto_guardado_id: null },
];

const BASE: SeleccionBase = {
  fechaCorte: '2026-09-13',
  consulta: { filtros: ['saldo > 100'], orden: 'saldo desc', cantidad: 1000, indicadores: [] },
  guardadaId: 5,
};

const conHorario = (cambios: Partial<BorradorCampana> = {}): BorradorCampana => ({
  ...borradorInicial(CONFIGURACION, SEGMENTOS),
  horarios: { horario_1: true, horario_2: false },
  ...cambios,
});

describe('el formulario al abrir', () => {
  it('parte por segmento, con el mensaje propio de cada segmento y la definición y plantilla de la configuración', () => {
    const borrador = borradorInicial(CONFIGURACION, SEGMENTOS);

    expect(borrador.modo).toBe('por_segmento');
    expect(borrador.definicionId).toBe(11);
    expect(borrador.plantilla).toBe('CUZCO_Vencida ({segmento}) whatsapp {fecha_corte}');
    expect(borrador.mensajesPorSegmento).toEqual({ preventivo: 7, tramo_2: 8, mayores_2: null });
    expect(borrador.tipoEnvio).toBe('solo_texto');
  });

  it('no trae ningún horario marcado: el analista decide (RF-WM-07)', () => {
    expect(horariosElegidos(borradorInicial(CONFIGURACION, SEGMENTOS))).toEqual([]);
    expect(horariosElegidos(conHorario({ horarios: { horario_1: true, horario_2: true } }))).toEqual(['horario_1', 'horario_2']);
  });
});

describe('el pedido de la previsualización', () => {
  it('por segmento manda el mensaje de cada segmento que lo tiene, sin la versión (la API toma la vigente)', () => {
    const entrada = entradaDePrevisualizacion(BASE, conHorario())!;

    expect(entrada.modo).toBe('por_segmento');
    expect(entrada.mensajes).toEqual({ preventivo: { texto_guardado_id: 7 }, tramo_2: { texto_guardado_id: 8 } });
    expect(entrada.mensaje).toBeUndefined();
    expect(entrada.definicion).toEqual({ id: 11 });
    expect(entrada).toMatchObject({ fecha_corte: '2026-09-13', cantidad: 1000, seleccion_id: 5, filtros: ['saldo > 100'], orden: 'saldo desc' });
  });

  it('global manda un solo mensaje y ninguno por segmento', () => {
    const entrada = entradaDePrevisualizacion(BASE, conHorario({ modo: 'global', mensajeGlobal: 12 }))!;

    expect(entrada.modo).toBe('global');
    expect(entrada.mensaje).toEqual({ texto_guardado_id: 12 });
    expect(entrada.mensajes).toBeUndefined();
  });

  it('global sin mensaje elegido no manda ninguno: la API lo dirá como problema', () => {
    const entrada = entradaDePrevisualizacion(BASE, conHorario({ modo: 'global' }))!;

    expect(entrada.mensaje).toBeUndefined();
  });

  it('la fecha de envío solo se manda si se escribió', () => {
    expect(entradaDePrevisualizacion(BASE, conHorario())!.fecha_envio).toBeUndefined();
    expect(entradaDePrevisualizacion(BASE, conHorario({ fechaEnvio: '2026-09-15' }))!.fecha_envio).toBe('2026-09-15');
  });

  it('no se puede pedir sin definición ni sin la cantidad (el top n) de la selección', () => {
    expect(entradaDePrevisualizacion(BASE, conHorario({ definicionId: null }))).toBeNull();
    expect(entradaDePrevisualizacion({ ...BASE, consulta: { ...BASE.consulta, cantidad: null } }, conHorario())).toBeNull();
  });

  it('lo que no es del pedido (tipo de envío, foto, plantilla) no viaja en la previsualización', () => {
    const entrada = entradaDePrevisualizacion(BASE, conHorario({ tipoEnvio: 'vcard', etiquetaVcard: 'Caja', fotoId: 3 }))!;

    expect(Object.keys(entrada)).not.toEqual(expect.arrayContaining(['tipo_envio', 'foto_id', 'etiqueta_vcard', 'horarios']));
  });
});

describe('los nombres del lote', () => {
  const lote = [{ etiqueta_segmento: 'Preventivo' }, { etiqueta_segmento: 'Tramo 2' }];

  it('reemplaza las dos variables, con la fecha de corte como AAAA.MM.DD', () => {
    expect(nombresDeLote('CUZCO_Vencida ({segmento}) whatsapp {fecha_corte}', lote, '2026-10-29')).toEqual([
      'CUZCO_Vencida (Preventivo) whatsapp 2026.10.29',
      'CUZCO_Vencida (Tramo 2) whatsapp 2026.10.29',
    ]);
  });

  it('en un lote, una plantilla sin {segmento} lo recibe al final para que los nombres no se repitan (DU-WM-6)', () => {
    expect(nombresDeLote('Campaña {fecha_corte}', lote, '2026-10-29')).toEqual([
      'Campaña 2026.10.29 Preventivo',
      'Campaña 2026.10.29 Tramo 2',
    ]);
  });

  it('una campaña sola (global) no agrega nada, aunque la plantilla no use {segmento}', () => {
    expect(nombresDeLote('Campaña {fecha_corte}', [{ etiqueta_segmento: null }], '2026-10-29')).toEqual(['Campaña 2026.10.29']);
  });

  it('detecta las variables que la API no lista, una vez cada una y en orden', () => {
    expect(variablesDesconocidasDeNombre('{fecha} {segmento} {x} {fecha}', ['fecha_corte', 'segmento'])).toEqual(['fecha', 'x']);
    expect(variablesDesconocidasDeNombre('sin variables', ['segmento'])).toEqual([]);
  });
});

describe('los problemas de la API', () => {
  const problema = (codigo: string, extra: Record<string, unknown> = {}) =>
    ({ codigo, detalle: 'motivo del servidor', segmento: null, parametros: {}, ...extra }) as Parameters<typeof textoDeProblema>[0];

  it('cada código lleva a su sección, y los que se arreglan en otra pantalla, a la suya', () => {
    expect(seccionDeProblema('sin_mensaje')).toBe('mensaje');
    expect(seccionDeProblema('mensaje_con_emoji')).toBe('mensaje');
    expect(seccionDeProblema('macro_inexistente')).toBe('mensaje');
    expect(seccionDeProblema('sin_horario')).toBe('programacion');
    expect(seccionDeProblema('nombre_largo')).toBe('nombre');
    expect(seccionDeProblema('adjunto_peso')).toBe('envio');
    expect(seccionDeProblema('foto_medidas')).toBe('envio');
    expect(seccionDeProblema('definicion_no_whatsmkt')).toBe('archivo');
    expect(seccionDeProblema('sin_supervisores')).toBe('supervisores');
    expect(seccionDeProblema('sin_whatsapp')).toBe('whatsapp');
    expect(seccionDeProblema('sin_productos')).toBeNull();
  });

  it('un mensaje que falta en una campaña global tiene su propia frase: no hay segmento al que nombrar', () => {
    expect(textoDeProblema(problema('sin_mensaje'))).toBe('Elige el mensaje de la campaña.');
    expect(textoDeProblema(problema('sin_mensaje', { segmento: 'tramo_2' }))).toBe('No tiene mensaje: elige uno, o configura el del segmento.');
  });

  it('el texto del código lleva sus parámetros, como macro_inexistente con la macro y cuántas hay', () => {
    expect(textoDeProblema(problema('macro_inexistente', { parametros: { macro: '[$MACRO4$]', n: 3 } }))).toBe(
      '[$MACRO4$] no existe en la definición elegida: tiene 3 macros.',
    );
  });

  it('una fecha no gestionable nombra las dos fechas como el resto de la app, no como las manda la API', () => {
    const frase = textoDeProblema(problema('fecha_no_gestionable', { parametros: { fecha: '2026-10-18', sugerida: '2026-10-16' } }));

    expect(frase).toMatch(/^El 18 oct.? 2026 no es un día gestionable. El siguiente es el 16 oct.? 2026.$/);
    expect(frase).not.toContain('2026-10');
  });

  it('un código que esta versión no traduce cae en la frase del servidor', () => {
    expect(textoDeProblema(problema('codigo_nuevo'))).toBe('motivo del servidor');
  });

  it('en el resumen, un problema con segmento lleva delante su nombre; sin segmento, no', () => {
    const etiquetas = { tramo_2: 'Tramo 2' };

    expect(textoDeProblemaConSegmento(problema('mensaje_largo', { segmento: 'tramo_2', parametros: { largo: 5000, maximo: 4096 } }), etiquetas)).toBe(
      'Tramo 2 · El mensaje tiene 5000 caracteres: el máximo es 4096.',
    );
    expect(textoDeProblemaConSegmento(problema('sin_mensaje'), etiquetas)).toBe('Elige el mensaje de la campaña.');
  });

  it('el resumen conserva el orden en que llegan, y un segmento que la lista no conoce se nombra por su clave', () => {
    expect(textoDeProblemaConSegmento(problema('sin_mensaje', { segmento: 'otro' }), {})).toBe(
      'otro · No tiene mensaje: elige uno, o configura el del segmento.',
    );
  });
});

describe('los problemas que el formulario ve solo', () => {
  const valida = ['fecha_corte', 'segmento'];
  const nombres = ['CUZCO_Vencida (Preventivo) whatsapp 2026.09.13'];

  it('sin horario marcado es un problema de la programación', () => {
    const problemas = problemasLocales(borradorInicial(CONFIGURACION, SEGMENTOS), valida, nombres);

    expect(problemas.map((p) => [p.seccion, p.codigo])).toEqual([['programacion', 'sin_horario']]);
    expect(problemas[0].texto).toBe('Marca al menos un horario.');
  });

  it('con un horario y todo en orden no hay problemas', () => {
    expect(problemasLocales(conHorario(), valida, nombres)).toEqual([]);
  });

  it('sin definición, con tipo archivo sin archivo o vCard sin etiqueta, cada uno en su sección', () => {
    expect(problemasLocales(conHorario({ definicionId: null }), valida, nombres).map((p) => p.codigo)).toEqual(['sin_definicion']);
    expect(problemasLocales(conHorario({ tipoEnvio: 'archivo' }), valida, nombres).map((p) => [p.seccion, p.codigo])).toEqual([['envio', 'sin_adjunto']]);
    expect(problemasLocales(conHorario({ tipoEnvio: 'vcard', etiquetaVcard: '   ' }), valida, nombres).map((p) => p.codigo)).toEqual(['sin_etiqueta']);
    expect(problemasLocales(conHorario({ tipoEnvio: 'archivo', adjuntoId: 2 }), valida, nombres)).toEqual([]);
  });

  it('cambiar de tipo conserva lo elegido en los otros, pero solo cuenta lo del tipo elegido', () => {
    // A vCard label written and then the type changed to text only: it is kept in the form and asked for nothing.
    expect(problemasLocales(conHorario({ tipoEnvio: 'solo_texto', etiquetaVcard: '', adjuntoId: null }), valida, nombres)).toEqual([]);
    expect(conHorario({ tipoEnvio: 'archivo', etiquetaVcard: 'Caja' }).etiquetaVcard).toBe('Caja');
  });

  it('una variable de la plantilla que no existe se dice, y no se juzga el largo del nombre a la vez', () => {
    const problemas = problemasLocales(conHorario({ plantilla: 'Campaña {fecha}' }), valida, ['x'.repeat(200)]);

    expect(problemas.map((p) => p.codigo)).toEqual(['variable_inexistente']);
    expect(problemas[0].texto).toBe('La variable {fecha} no existe. Usa las de la lista.');
  });

  it('un nombre de más de 75 caracteres es nombre_largo, con el del nombre más largo', () => {
    const problemas = problemasLocales(conHorario(), valida, ['corto', 'x'.repeat(83)]);

    expect(problemas.map((p) => p.codigo)).toEqual(['nombre_largo']);
    expect(problemas[0].texto).toBe('El nombre tiene 83 caracteres: el máximo es 75.');
    expect(problemasLocales(conHorario(), valida, ['x'.repeat(75)])).toEqual([]);
  });

  it('la frase junto a «Crear» cuenta los problemas, en singular y en plural', () => {
    expect(motivoDeCrear(1)).toBe('Corrige 1 problema para crear.');
    expect(motivoDeCrear(3)).toBe('Corrige 3 problemas para crear.');
  });
});

describe('cómo se leen las cosas', () => {
  it('los días de un segmento: hasta, un rango, o en adelante', () => {
    expect(diasDeSegmento(SEGMENTOS[0])).toBe('hasta 0');
    expect(diasDeSegmento(SEGMENTOS[1])).toBe('1 a 8');
    expect(diasDeSegmento(SEGMENTOS[2])).toBe('9 o más');
    expect(diasDeSegmento({ desde: null, hasta: null })).toBe('todos');
    setLanguageForTests('en');
    expect(diasDeSegmento(SEGMENTOS[1])).toBe('1 to 8');
  });

  it('un adjunto en un select: nombre, tipo y tamaño', () => {
    expect(etiquetaDeAdjunto({ nombre: 'afiche.jpg', tipo: 'imagen_jpeg', tamano: 240_000 })).toBe('afiche.jpg · Imagen JPEG · 240 KB');
  });

  it('las columnas de una definición: la primera es el número, sin macro; las demás, macro 1, 2, 3 por su posición', () => {
    const variable = (nombre: string) => ({ nodos: [{ tipo: 'variable' as const, nombre, funciones: [] }] });
    const filas = filasDeColumnas([
      { nombre: 'número', etiqueta: 'Número con prefijo', expresion: { nodos: [{ tipo: 'texto', valor: '51' }, { tipo: 'variable', nombre: 'telefono', funciones: [] }] } },
      { nombre: '[$MACRO1$]', etiqueta: 'Nombres del titular', expresion: variable('titular_nombres') },
      { nombre: '[$MACRO2$]', etiqueta: null, expresion: { nodos: [] } },
    ]);

    expect(filas.map((f) => f.macro)).toEqual([null, 1, 2]);
    expect(filas[1]).toMatchObject({ encabezado: '[$MACRO1$]', etiqueta: 'Nombres del titular', contenido: 'Variable: titular_nombres' });
    expect(filas[2]).toMatchObject({ etiqueta: null, contenido: 'Sin contenido' });
    // A composed text reads as the builder's list does: «Texto: …».
    expect(filas[0].contenido).toBe('Texto: 51telefono');
  });

  it('el contenido lee cada variable por la etiqueta que da quien llama, y sin ella por su nombre', () => {
    const columnas = [
      { nombre: 'número', etiqueta: null, expresion: { nodos: [{ tipo: 'texto' as const, valor: '51' }, { tipo: 'variable' as const, nombre: 'telefono', funciones: [] }] } },
      { nombre: '[$MACRO1$]', etiqueta: null, expresion: { nodos: [{ tipo: 'variable' as const, nombre: 'titular', funciones: [] }] } },
    ];
    const etiquetas: Record<string, string> = { telefono: 'Teléfono', titular: 'Titular' };

    const conEtiquetas = filasDeColumnas(columnas, (nombre) => etiquetas[nombre] ?? nombre);

    expect(conEtiquetas[0].contenido).toBe('Texto: 51Teléfono');
    expect(conEtiquetas[1].contenido).toBe('Variable: Titular');
    expect(filasDeColumnas(columnas)[1].contenido).toBe('Variable: titular');
  });

  it('las macros son las columnas menos el número, para el aviso de las cinco variables', () => {
    expect(cantidadDeMacros([])).toBe(0);
    expect(cantidadDeMacros([1])).toBe(0);
    expect(cantidadDeMacros([1, 2, 3, 4, 5, 6, 7])).toBe(6);
  });
});

describe('el pedido de crear', () => {
  const mensaje = (id: number, version: number) => ({ texto_guardado_id: id, nombre: `Mensaje ${id}`, version, deshabilitado: false });
  const previaPorSegmento = {
    campanas: [
      { segmento: 'preventivo', mensaje: mensaje(7, 3) },
      { segmento: 'tramo_2', mensaje: mensaje(8, 1) },
    ],
  } as Parameters<typeof entradaDeCreacion>[1];
  const previaGlobal = { campanas: [{ segmento: null, mensaje: mensaje(9, 2) }] } as Parameters<typeof entradaDeCreacion>[1];
  const pedido = (borrador: BorradorCampana) => entradaDePrevisualizacion(BASE, borrador)!;

  it('cada mensaje va con la versión EXACTA que devolvió la previsualización, no con «la vigente», y cada campaña con su nombre', () => {
    const borrador = conHorario({ modo: 'por_segmento', mensajesPorSegmento: { preventivo: 7, tramo_2: 8, mayores_2: null } });

    const creacion = entradaDeCreacion(pedido(borrador), previaPorSegmento, borrador, ['CUZCO (Preventivo)', 'CUZCO (Tramo 2)']);

    expect(creacion.mensajes).toEqual({ preventivo: { texto_guardado_id: 7, version: 3 }, tramo_2: { texto_guardado_id: 8, version: 1 } });
    expect(creacion.nombres).toEqual({ preventivo: 'CUZCO (Preventivo)', tramo_2: 'CUZCO (Tramo 2)' });
    expect(creacion.nombre).toBeUndefined();
    expect(creacion.mensaje).toBeUndefined();
  });

  it('en modo global manda un solo mensaje con su versión y un solo nombre', () => {
    const borrador = conHorario({ modo: 'global', mensajeGlobal: 9 });

    const creacion = entradaDeCreacion(pedido(borrador), previaGlobal, borrador, ['CUZCO especial']);

    expect(creacion.mensaje).toEqual({ texto_guardado_id: 9, version: 2 });
    expect(creacion.nombre).toBe('CUZCO especial');
    expect(creacion.mensajes).toBeUndefined();
    expect(creacion.nombres).toBeUndefined();
  });

  it('trae lo de la previsualización y suma los horarios, lo antes posible y el tipo de envío', () => {
    const borrador = conHorario({ horarios: { horario_1: true, horario_2: true }, antes: true, fechaEnvio: '2026-10-19' });

    const creacion = entradaDeCreacion(pedido(borrador), previaPorSegmento, borrador, ['a', 'b']);

    expect(creacion).toMatchObject({
      fecha_corte: '2026-09-13',
      cantidad: 1000,
      seleccion_id: 5,
      modo: 'por_segmento',
      fecha_envio: '2026-10-19',
      horarios: ['horario_1', 'horario_2'],
      lo_antes_posible: true,
      tipo_envio: 'solo_texto',
    });
  });

  it('solo manda lo del tipo de envío elegido: el archivo con «Texto + archivo» y la etiqueta con «Texto + vCard»; la foto, con cualquiera', () => {
    const lleno = { adjuntoId: 4, fotoId: 5, etiquetaVcard: '  Caja Cusco  ' };
    const de = (tipoEnvio: BorradorCampana['tipoEnvio']) => {
      const borrador = conHorario({ ...lleno, tipoEnvio });
      return entradaDeCreacion(pedido(borrador), previaPorSegmento, borrador, ['a', 'b']);
    };

    expect(de('solo_texto')).toMatchObject({ foto_id: 5 });
    expect(de('solo_texto').adjunto_id).toBeUndefined();
    expect(de('solo_texto').etiqueta_vcard).toBeUndefined();
    expect(de('archivo')).toMatchObject({ foto_id: 5, adjunto_id: 4 });
    expect(de('archivo').etiqueta_vcard).toBeUndefined();
    expect(de('vcard')).toMatchObject({ foto_id: 5, etiqueta_vcard: 'Caja Cusco' });
    expect(de('vcard').adjunto_id).toBeUndefined();
  });

  it('sin foto no manda foto_id', () => {
    const borrador = conHorario({ fotoId: null });

    expect(entradaDeCreacion(pedido(borrador), previaPorSegmento, borrador, ['a', 'b']).foto_id).toBeUndefined();
  });
});

describe('la ficha de una campaña creada', () => {
  const ficha = {
    nombre: 'CUZCO_Vencida (Preventivo) whatsapp 2026.10.29',
    fecha_envio: '2026-10-29',
    horarios: [{ nombre: 'horario_1', inicio: '08:00', fin: '14:00' }],
    lo_antes_posible: false,
    pais: 'Perú',
    foto_id: null,
    cantidad: 1520,
    tipo_envio: 'archivo',
    adjunto_id: 4,
    etiqueta_vcard: null,
    mensaje: 'Hola [$MACRO1$]\nINFO por https://wa.me/+51900000123',
    avisos: [],
  } as Parameters<typeof datosDeFicha>[0];

  it('trae cada dato del formulario en su orden, con los valores que se escriben en él', () => {
    const datos = datosDeFicha(ficha, [{ id: 4, tipo: 'imagen_jpeg' }]);

    expect(datos.map((d) => d.clave)).toEqual(['nombre', 'fecha', 'antes', 'pais', 'cantidad', 'tipo', 'mensaje']);
    expect(datos.map((d) => d.valor)).toEqual([
      'CUZCO_Vencida (Preventivo) whatsapp 2026.10.29',
      '29/10/2026 · Horario 1 (08:00 – 14:00)',
      'No',
      'Perú',
      // No thousands separator: it is typed in the field.
      '1520',
      'Texto + imagen',
      'Hola [$MACRO1$]\nINFO por https://wa.me/+51900000123',
    ]);
    expect(datos.map((d) => d.multilinea)).toEqual([false, false, false, false, false, false, true]);
    expect(datos[0].etiqueta).toBe('Nombre de campaña');
  });

  it('dos horarios van juntos y lo antes posible dice Sí', () => {
    const datos = datosDeFicha(
      { ...ficha, lo_antes_posible: true, horarios: [...ficha.horarios, { nombre: 'horario_2', inicio: '14:00', fin: '20:00' }] },
      [],
    );

    expect(datos[1].valor).toBe('29/10/2026 · Horario 1 (08:00 – 14:00) · Horario 2 (14:00 – 20:00)');
    expect(datos[2].valor).toBe('Sí');
  });

  it('el tipo de envío dice el tipo del archivo, o la etiqueta del vCard, o solo texto', () => {
    expect(datosDeFicha(ficha, [{ id: 4, tipo: 'pdf' }])[5].valor).toBe('Texto + PDF');
    expect(datosDeFicha(ficha, [{ id: 4, tipo: 'video' }])[5].valor).toBe('Texto + video');
    expect(datosDeFicha({ ...ficha, tipo_envio: 'vcard', adjunto_id: null, etiqueta_vcard: 'Caja Cusco' }, [])[5].valor).toBe('Texto + vCard · Caja Cusco');
    expect(datosDeFicha({ ...ficha, tipo_envio: 'solo_texto', adjunto_id: null }, [])[5].valor).toBe('Solo texto');
  });

  it('la fecha se escribe como la pide el formulario de WhatsMKT', () => {
    expect(fechaDeFormulario('2026-10-29')).toBe('29/10/2026');
    expect(fechaDeFormulario('2026-01-05')).toBe('05/01/2026');
  });
});

describe('lo que dice una subida desde la campaña', () => {
  it('un archivo nuevo dice que se subió y se eligió; una imagen suma que se guardó sin metadatos', () => {
    expect(textoDeSubida({ nombre: 'tarifario.pdf', tipo: 'pdf', ya_existia: false })).toBe('Subido y elegido: tarifario.pdf.');
    expect(textoDeSubida({ nombre: 'afiche.jpg', tipo: 'imagen_jpeg', ya_existia: false })).toBe(
      'Subido y elegido: afiche.jpg. Se guardó sin metadatos (EXIF, ubicación).',
    );
  });

  it('uno que ya estaba dice que se usa el mismo, sin hablar de metadatos', () => {
    expect(textoDeSubida({ nombre: 'afiche.jpg', tipo: 'imagen_jpeg', ya_existia: true })).toBe('Ya estaba en la biblioteca: se usa el mismo archivo.');
  });

  it('solo se ofrece restaurar lo que ya estaba Y está archivado', () => {
    expect(quedoArchivado({ ya_existia: true, archivado_en: '2026-10-12T15:00:00-05:00' })).toBe(true);
    expect(quedoArchivado({ ya_existia: true, archivado_en: null })).toBe(false);
    expect(quedoArchivado({ ya_existia: false, archivado_en: null })).toBe(false);
  });
});

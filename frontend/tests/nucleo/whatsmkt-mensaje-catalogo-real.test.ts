/**
 * The context `whatsmkt.mensaje` as the REAL backend gives it (T-WM-B9, T-WM-F4): `e2e/datos/catalogo-whatsmkt-mensaje.json` is the answer of
 * `GET /texto-enriquecido/catalogo?contexto=whatsmkt.mensaje`, captured from the API (two macros, one with its label, and the 4096 limit), not written
 * by hand. These tests tie what the frontend assumes to that answer: the names of the variables the conversion produces are in the catalogue, the
 * link counts as the length the counter uses, there is no «Cerca del tope» and the context takes no functions.
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import { etiquetaVariable } from '../../src/lib/campos';
import type { components } from '../../src/lib/contrato-api';
import { LARGO_ENLACE_WHATSAPP } from '../../src/lib/whatsmkt-mensaje';
import { VARIABLE_WHATSAPP, expresionDeMensaje, numeroDeMacro } from '../../src/lib/whatsmkt-mensaje-expresion';
import { setLanguageForTests } from './idioma';

const catalogo = JSON.parse(readFileSync(join(process.cwd(), 'e2e', 'datos', 'catalogo-whatsmkt-mensaje.json'), 'utf8')) as components['schemas']['CatalogoRespuesta'];
const { contexto } = catalogo;
const nombres = contexto.variables.map((v) => v.nombre);

describe('el catálogo real de whatsmkt.mensaje', () => {
  it('es el contexto del mensaje, sin funciones y sin umbral de advertencia', () => {
    expect(contexto.nombre).toBe('whatsmkt.mensaje');
    expect(contexto.admite_funciones).toBe(false);
    // No «Cerca del tope» in WhatsMKT: the context has no threshold.
    expect(contexto.umbral_advertencia).toBeNull();
    expect(contexto.limite_largo).toBe(4096);
    expect(contexto.clave_alcance).toBe('textoEnriquecido.alcance.whatsmkt.mensaje');
  });

  it('ofrece una variable macroN por columna de la definición y el enlace de WhatsApp, y nada más', () => {
    expect(nombres).toEqual(['macro1', 'macro2', VARIABLE_WHATSAPP]);
    expect(contexto.variables.every((v) => v.tipo === 'texto')).toBe(true);
  });

  it('las macros son las columnas del archivo: su tema es «archivo», y el del enlace de WhatsApp es «persona»', () => {
    const [macro1, macro2, whatsapp] = contexto.variables;
    expect([macro1.tema, macro2.tema, whatsapp.tema]).toEqual(['archivo', 'archivo', 'persona']);
  });

  it('las macros se ven con su etiqueta; el enlace, con el nombre de su clave', () => {
    setLanguageForTests('es');
    const [macro1, macro2, whatsapp] = contexto.variables;
    expect(etiquetaVariable(macro1)).toBe('MACRO1 · Nombres del titular');
    expect(etiquetaVariable(macro2)).toBe('MACRO2 · Vencimiento de la cuota');
    expect(whatsapp.etiqueta).toBeNull();
    expect(whatsapp.clave_nombre).toBe('textoEnriquecido.variable.whatsapp');
    expect(etiquetaVariable(whatsapp)).toBe('Enlace de WhatsApp');
  });

  it('el ejemplo de cada macro es su marcador y el del enlace mide lo que el contador cuenta por [whatsapp]', () => {
    const ejemplo = contexto.ejemplo as Record<string, string>;
    expect(ejemplo.macro1).toBe('[$MACRO1$]');
    expect(ejemplo.macro2).toBe('[$MACRO2$]');
    expect(ejemplo.whatsapp).toHaveLength(LARGO_ENLACE_WHATSAPP);
    // Synthetic, in the 900000xxx range: the example is not the number of the configuration.
    expect(ejemplo.whatsapp).toBe('https://wa.me/+51900000000');
  });

  it('las variables que produce la conversión son las del catálogo: una macro que existe y el enlace', () => {
    const texto = 'Hola [$MACRO1$], vence el [$MACRO2$]. INFO por [whatsapp]';
    const variables = expresionDeMensaje(texto).nodos.flatMap((nodo) => (nodo.tipo === 'variable' ? [nodo.nombre] : []));
    expect(variables).toEqual(['macro1', 'macro2', 'whatsapp']);
    for (const nombre of variables) expect(nombres).toContain(nombre);
  });

  it('una macro que la definición no tiene no está en el catálogo: el motor la dirá desconocida, y la conversión la conserva', () => {
    const [nodo] = expresionDeMensaje('[$MACRO7$]').nodos;
    expect(nodo).toMatchObject({ tipo: 'variable', nombre: 'macro7' });
    expect(nombres).not.toContain('macro7');
    expect(numeroDeMacro('macro7')).toBe(7);
    // The context has the macros it has: the largest number a text may use.
    expect(Math.max(...nombres.flatMap((n) => numeroDeMacro(n) ?? []))).toBe(2);
  });
});

/**
 * The words of a platform's rules (docs/motor-texto-enriquecido-interfaz.md §11.2 and §11.4): the
 * one-sentence summary the screen builds from the registered rules, and the text of a problem the
 * platform validation answers. The rules themselves are `plataformas.ts`.
 */

import type { ProblemaDefinicion } from './api-definiciones';
import { t } from './i18n';
import { encabezadoPorPosicion, type ReglasPlataforma } from './plataformas';

/**
 * «WhatsMKT: la 1.ª columna, «número», es fija; las siguientes se llaman por su posición,
 * [$MARCRO1$], [$MARCRO2$]…, y son de texto». Each part comes from one rule, and a rule that
 * is not set adds nothing: there are no hidden rules, so this sentence is all the screen enforces.
 */
export function fraseDeReglas(reglas: ReglasPlataforma): string {
  const fijas = reglas.columnas_fijas.map((f) =>
    t('columnas.plataforma.reglas.fijas', { posicion: f.posicion, nombre: f.nombre }),
  );
  const primera = encabezadoPorPosicion(reglas, reglas.columnas_fijas.length);
  const segunda = encabezadoPorPosicion(reglas, reglas.columnas_fijas.length + 1);
  const ejemplo = [primera, segunda].filter((e): e is string => e !== null).join(', ');
  const partes = [fijas.join('; ')];
  if (ejemplo !== '') partes[0] += `; ${t('columnas.plataforma.reglas.posicion', { ejemplo })}`;
  if (reglas.tipo_resto !== null) {
    partes.push(t('columnas.plataforma.reglas.tipo', { tipo: t(`columnas.tipo.${reglas.tipo_resto}`).toLowerCase() }));
  }
  if (!reglas.admite_mas_columnas) partes.push(t('columnas.plataforma.reglas.sinMas'));
  return `${reglas.etiqueta}: ${partes.filter((p) => p !== '').join(', ')}.`;
}

/**
 * The text of a problem: the platform's own codes carry the name of the column they are about, so
 * their sentence is the screen's (`textoEnriquecido.codigo.plataforma_*`); any other is as before.
 */
export function textoDeProblema(problema: Pick<ProblemaDefinicion, 'codigo' | 'detalle' | 'nombre'>): string {
  if (!problema.codigo.startsWith('plataforma_')) return problema.detalle;
  const clave = `textoEnriquecido.codigo.${problema.codigo}`;
  const texto = t(clave, { nombre: problema.nombre ?? '' });
  return texto === clave ? problema.detalle : texto;
}

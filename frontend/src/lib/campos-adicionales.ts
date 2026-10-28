/**
 * The additional fields on the screens that list them (RF-64 to RF-66, docs/campos-adicionales-interfaz.md §4):
 * the order of the management table and the name a person reads where the backend gives a technical one.
 * Pure: no DOM, no fetch.
 */

import type { CampoAdicional } from './api-mapeador';
import { etiquetaDeCampo } from './campos';

/** The active ones first, then the archived ones, each group by its visible name. */
export function ordenarAdicionales(campos: readonly CampoAdicional[]): CampoAdicional[] {
  const porNombre = (a: CampoAdicional, b: CampoAdicional) => a.nombre_legible.localeCompare(b.nombre_legible);
  return [...campos.filter((c) => !c.archivado).sort(porNombre), ...campos.filter((c) => c.archivado).sort(porNombre)];
}

/** «Renombrar» saves only a name that is there and is not the one it already has. */
export function puedeGuardarNombre(nuevo: string, actual: string): boolean {
  const limpio = nuevo.trim();
  return limpio !== '' && limpio !== actual;
}

/** The visible name of a field known by its technical name: the label of an additional one, the dictionary's otherwise. */
export function nombreVisibleDeCampo(nombre: string, adicionales: readonly CampoAdicional[]): string {
  const adicional = adicionales.find((c) => c.nombre === nombre);
  return adicional ? adicional.nombre_legible : etiquetaDeCampo({ nombre });
}

/** The incidences whose «Columna» carries field names (technical ones) instead of a header of the file. */
const INCIDENCIAS_CON_CAMPOS = new Set(['valor_no_convertible', 'columnas_opcionales_ausentes']);

/**
 * What the «Columna» of an incidence says: for the two codes that name fields, each name as a person reads it
 * (a list comes separated by «, »); any other code carries a header of the file and is left as it is.
 */
export function columnaDeIncidencia(codigo: string, columna: string | null, adicionales: readonly CampoAdicional[]): string | null {
  if (columna === null || !INCIDENCIAS_CON_CAMPOS.has(codigo)) return columna;
  return columna
    .split(',')
    .map((parte) => parte.trim())
    .filter((parte) => parte !== '')
    .map((nombre) => nombreVisibleDeCampo(nombre, adicionales))
    .join(', ');
}

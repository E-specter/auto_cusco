/**
 * Type-level contract between the rich-text editor and the generated API
 * models. Nothing here runs: `npm run tipos` (`tsc --noEmit`) compiles it and
 * fails if what the editor builds stops being accepted by the backend's
 * request models, or if what the backend answers stops fitting what the
 * editor reads.
 *
 * Why a file of its own: the generated request models allow extra keys (an
 * index signature), and an `interface` cannot be assigned to one. When that
 * happens on a nested type, `astro check` reports nothing; `tsc` does. This
 * file makes the assignment explicit so the regression has somewhere to fail
 * (see e207c46).
 */
import type { components } from '../../src/lib/contrato-api';
import type {
  Expresion,
  FuncionCatalogo,
  LlamadaFuncion,
  Nodo,
  Problema,
  Ubicacion,
  VariableCatalogo,
} from '../../src/lib/expresion';
import type { ProblemaDeSegmento, Segmento, Variante } from '../../src/lib/variantes';

type Esquemas = components['schemas'];

declare const expresion: Expresion;
declare const nodo: Nodo;
declare const llamada: LlamadaFuncion;
declare const variante: Variante;
declare const problemaDelBackend: Esquemas['ProblemaTextoRespuesta'];
declare const ubicacionDelBackend: Esquemas['UbicacionRespuesta'];
declare const expresionGuardada: Esquemas['ExpresionGuardadaRespuesta'];
declare const varianteGuardada: Esquemas['VarianteGuardadaRespuesta'];
declare const variableDelCatalogo: Esquemas['VariableRespuesta'];
declare const funcionDelCatalogo: Esquemas['FuncionRespuesta'];
declare const rangoDelCatalogo: Esquemas['RangoRespuesta'];

// What the editor sends must be a valid request body.
export const expresionEnviable: Esquemas['ExpresionEntrada'] = expresion;
export const nodoEnviable: Esquemas['NodoEntrada'] = nodo;
export const funcionEnviable: Esquemas['FuncionEntrada'] = llamada;
export const varianteEnviable: Esquemas['VarianteEntrada'] = variante;

// What the backend answers must fit what the editor reads.
export const problemaLegible: Problema = problemaDelBackend;
export const problemaDeSegmentoLegible: ProblemaDeSegmento = problemaDelBackend;
export const ubicacionLegible: Ubicacion = ubicacionDelBackend;
export const expresionLegible: Expresion = expresionGuardada;
export const varianteLegible: Variante = varianteGuardada;
export const variableLegible: VariableCatalogo = variableDelCatalogo;
export const funcionLegible: FuncionCatalogo = funcionDelCatalogo;
export const segmentoLegible: Segmento = rangoDelCatalogo;

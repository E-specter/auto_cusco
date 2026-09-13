/**
 * Generate the frontend's API types from the backend contract.
 *
 *   node herramientas/contrato/generar.mjs              writes src/lib/contrato-api.d.ts
 *   node herramientas/contrato/generar.mjs --comprobar  fails if that file is stale
 *
 * Source of truth: contratos/openapi.json, exported from the running FastAPI
 * app by the backend (see docs/contrato-api.md). The backend's own test fails
 * if that file drifts from the API; this script is the other half, and fails
 * if the types the frontend compiles against drift from that file.
 *
 * Two quirks shape it:
 * - It lives in its own package because openapi-typescript 7 declares a
 *   TypeScript 5 peer while the app runs TypeScript 6.
 * - The schema is read here and handed over as an object. Given a path,
 *   openapi-typescript 7.13 turns it into a URL and percent-encodes spaces,
 *   so a checkout under a folder like "ASUS 2" fails with ENOENT.
 */
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import openapiTS, { COMMENT_HEADER, astToString } from 'openapi-typescript';

const desdeAqui = (ruta) => fileURLToPath(new URL(ruta, import.meta.url));

const ENTRADA = desdeAqui('../../../contratos/openapi.json');
const SALIDA = desdeAqui('../../src/lib/contrato-api.d.ts');
const COMPROBAR = process.argv.includes('--comprobar');

// Git may check the file out with CRLF on Windows and LF on the CI runner;
// line endings are not a contract change, so they never count as drift.
const normalizar = (texto) => texto.replace(/\r\n/g, '\n');

const esquema = JSON.parse(readFileSync(ENTRADA, 'utf8'));
const tipos = normalizar(COMMENT_HEADER + astToString(await openapiTS(esquema)));

if (!COMPROBAR) {
  writeFileSync(SALIDA, tipos, 'utf8');
  console.log(`Tipos del contrato escritos en ${SALIDA}`);
  process.exit(0);
}

const actuales = existsSync(SALIDA) ? normalizar(readFileSync(SALIDA, 'utf8')) : null;

if (actuales === tipos) {
  console.log('Los tipos del frontend coinciden con contratos/openapi.json.');
  process.exit(0);
}

console.error(
  actuales === null
    ? `Falta ${SALIDA}.`
    : 'Los tipos del frontend no coinciden con contratos/openapi.json: el contrato cambió y los tipos no se regeneraron.',
);
console.error('Regenéralos desde frontend/ con `npm run contrato` y commitea el resultado junto al cambio de contrato.');
process.exit(1);

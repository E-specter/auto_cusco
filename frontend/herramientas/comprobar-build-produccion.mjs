// Fails if the production build (dist/) carries anything from the test-only
// routes. Those are injected only with AUTO_CUSCO_RUTAS_PRUEBA=1 and built to
// dist-pruebas/ (see astro.config.mjs); this is the check that the
// deployable artifact never had them. Runs after `npm run build`.
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const DIST = fileURLToPath(new URL('../dist/', import.meta.url));
// Marks the test pages carry; none may reach dist/.
const MARCAS = ['data-ruta-prueba', '/pruebas/'];

if (!existsSync(DIST)) {
  console.error('No existe dist/. Corre `npm run build` antes de esta comprobación.');
  process.exit(1);
}

if (existsSync(join(DIST, 'pruebas'))) {
  console.error('dist/ contiene la carpeta pruebas/: el build de producción incluyó rutas de prueba.');
  process.exit(1);
}

const encontrados = [];
const recorrer = (carpeta) => {
  for (const nombre of readdirSync(carpeta)) {
    const ruta = join(carpeta, nombre);
    if (statSync(ruta).isDirectory()) recorrer(ruta);
    else if (nombre.endsWith('.html')) {
      const texto = readFileSync(ruta, 'utf8');
      if (MARCAS.some((marca) => texto.includes(marca))) encontrados.push(ruta);
    }
  }
};
recorrer(DIST);

if (encontrados.length > 0) {
  console.error(`Páginas de dist/ con marcas de rutas de prueba:\n${encontrados.join('\n')}`);
  process.exit(1);
}

console.log('dist/ no contiene rutas de prueba.');

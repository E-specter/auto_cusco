// @ts-check
import { defineConfig } from 'astro/config';

// The API is a separate REST service (see docs/architecture.md). During
// development the browser talks to it through a same-origin `/api` prefix so
// no CORS headers are needed; behind a reverse proxy the same prefix holds.
// Set PUBLIC_API_URL to talk to an absolute origin instead (that origin must
// then send CORS headers).
const API_ORIGIN = process.env.API_ORIGIN ?? 'http://127.0.0.1:8000';

// Test-only routes: pages that mount a shared component on its own so
// Playwright can exercise it before any screen uses it. They exist only when
// AUTO_CUSCO_RUTAS_PRUEBA=1, which only playwright.config.ts sets, and that
// build goes to dist-pruebas/: the dist/ that gets deployed never had them.
// `herramientas/comprobar-build-produccion.mjs` checks that on every
// `npm run verificar` (docs/testing.md §4).
const RUTAS_DE_PRUEBA = process.env.AUTO_CUSCO_RUTAS_PRUEBA === '1';

/** @type {import('astro').AstroIntegration} */
const rutasDePrueba = {
  name: 'auto-cusco-rutas-de-prueba',
  hooks: {
    'astro:config:setup': ({ injectRoute }) => {
      injectRoute({
        pattern: '/pruebas/editor-texto',
        entrypoint: './src/pruebas/editor-texto.astro',
      });
      injectRoute({
        pattern: '/pruebas/mapeador',
        entrypoint: './src/pruebas/mapeador.astro',
      });
    },
  },
};

// https://astro.build/config
export default defineConfig({
  outDir: RUTAS_DE_PRUEBA ? './dist-pruebas' : './dist',
  integrations: RUTAS_DE_PRUEBA ? [rutasDePrueba] : [],
  vite: {
    server: {
      proxy: {
        '/api': {
          target: API_ORIGIN,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
  },
});

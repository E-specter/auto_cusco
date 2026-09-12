// @ts-check
import { defineConfig } from 'astro/config';

// The API is a separate REST service (see docs/architecture.md). During
// development the browser talks to it through a same-origin `/api` prefix so
// no CORS headers are needed; behind a reverse proxy the same prefix holds.
// Set PUBLIC_API_URL to talk to an absolute origin instead (that origin must
// then send CORS headers).
const API_ORIGIN = process.env.API_ORIGIN ?? 'http://127.0.0.1:8000';

// https://astro.build/config
export default defineConfig({
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

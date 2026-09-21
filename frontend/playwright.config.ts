import { defineConfig, devices } from '@playwright/test';

/**
 * End-to-end tests run against the built site, the way Astro's testing guide
 * recommends: `webServer` starts `npm run preview` and `baseURL` lets the
 * specs navigate with plain paths.
 *
 * Preview serves the static build with no dev proxy, so `/api` resolves to
 * nothing on purpose — every spec intercepts the API with `page.route`. That
 * keeps these tests off the backend and off PostgreSQL: they check what the
 * interface does with an answer, which is the only part that is ours.
 *
 * `PLAYWRIGHT_PUERTO` gives a run its own port. Several sessions verify this
 * repository at once, and on the default port one run reuses another's
 * preview — serving a different build, which reads as a wall of failures that
 * have nothing to do with the change under test. With the variable set, the
 * run owns its server and never reuses a stranger's:
 *
 *     $env:PLAYWRIGHT_PUERTO = '4331'; npm run verificar
 *
 * Without it everything behaves as before, so CI and the plain local run are
 * untouched.
 */
const PUERTO_POR_DEFECTO = 4321;
const propio = Boolean(process.env.PLAYWRIGHT_PUERTO);
const puerto = propio ? Number(process.env.PLAYWRIGHT_PUERTO) : PUERTO_POR_DEFECTO;

if (!Number.isInteger(puerto) || puerto < 1024 || puerto > 65535) {
  throw new Error(
    `PLAYWRIGHT_PUERTO debe ser un entero entre 1024 y 65535; llegó ${JSON.stringify(process.env.PLAYWRIGHT_PUERTO)}`,
  );
}

const origen = `http://localhost:${puerto}`;

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',

  use: {
    baseURL: origen,
    trace: 'on-first-retry',
  },

  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],

  webServer: {
    command: propio ? `npm run preview -- --port ${puerto}` : 'npm run preview',
    url: origen,
    timeout: 120 * 1000,
    // A run with its own port never adopts a server it did not start.
    reuseExistingServer: !process.env.CI && !propio,
    // Since Astro 7.2, `astro preview` detaches into the background when it
    // detects an AI coding agent. Playwright then sees its process exit at once,
    // reports the server as dead, and leaves an orphan on the port. Playwright
    // has to own the server's lifecycle, so the preview stays in the foreground
    // for whoever runs the tests (docs: Building Astro sites with AI tools >
    // Background mode).
    env: { ASTRO_PREVIEW_BACKGROUND: '0' },
  },
});

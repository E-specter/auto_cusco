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
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',

  use: {
    baseURL: 'http://localhost:4321',
    trace: 'on-first-retry',
  },

  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],

  webServer: {
    command: 'npm run preview',
    url: 'http://localhost:4321',
    timeout: 120 * 1000,
    reuseExistingServer: !process.env.CI,
    // Since Astro 7.2, `astro preview` detaches into the background when it
    // detects an AI coding agent. Playwright then sees its process exit at once,
    // reports the server as dead, and leaves an orphan on port 4321. Playwright
    // has to own the server's lifecycle, so the preview stays in the foreground
    // for whoever runs the tests (docs: Building Astro sites with AI tools >
    // Background mode).
    env: { ASTRO_PREVIEW_BACKGROUND: '0' },
  },
});

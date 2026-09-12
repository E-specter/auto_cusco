/// <reference types="vitest/config" />
import { getViteConfig } from 'astro/config';

/**
 * Vitest, set up the way Astro documents it: `getViteConfig()` loads the
 * project's own Astro configuration into the test environment.
 *
 * Two projects, because they need different environments. From Astro 6 a
 * component can only be rendered under `node`, so anything that touches the
 * DOM lives apart with its own `jsdom` environment (docs: Testing > Vitest).
 */
export default getViteConfig({
  test: {
    projects: [
      {
        extends: true,
        test: {
          name: 'nucleo',
          environment: 'node',
          include: ['tests/nucleo/**/*.test.ts'],
        },
      },
      {
        extends: true,
        test: {
          name: 'dom',
          environment: 'jsdom',
          include: ['tests/dom/**/*.test.ts'],
        },
      },
    ],
  },
});

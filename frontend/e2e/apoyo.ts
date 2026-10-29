/**
 * What every API fake and every spec shares: answering a route with JSON, and taking the next scripted
 * answer. No imports from the fakes, so any of them can import this without a cycle.
 */
import type { Route } from '@playwright/test';

/** Answer a route with `estado` and a JSON body. */
export const json = (route: Route, estado: number, cuerpo: unknown) =>
  route.fulfill({ status: estado, contentType: 'application/json', body: JSON.stringify(cuerpo) });

/** Take the next scripted answer, repeating the last one once exhausted. */
export function siguiente<T>(cola: T[]): T | undefined {
  return cola.length > 1 ? cola.shift() : cola[0];
}

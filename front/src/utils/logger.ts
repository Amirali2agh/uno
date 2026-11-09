/**
 * Tiny logging facade.
 *
 * Debug chatter (socket traffic, resolved player ids, …) is stripped from
 * production builds: Vite replaces `import.meta.env.DEV` with `false`, so the
 * `if` branch — and the payload strings inside it — are dropped by the minifier.
 * Real errors are always reported.
 */
const DEBUG_ENABLED = import.meta.env.DEV;

export const debug = (...args: unknown[]): void => {
  if (DEBUG_ENABLED) console.log(...args);
};

export const warn = (...args: unknown[]): void => {
  if (DEBUG_ENABLED) console.warn(...args);
};

export const error = (...args: unknown[]): void => {
  console.error(...args);
};

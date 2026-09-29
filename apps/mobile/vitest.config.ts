import { defineConfig } from 'vitest/config';

// Pure data/logic tests only; screens are exercised in the browser (docs/testing.md).
export default defineConfig({
  test: { include: ['test/**/*.test.ts'], environment: 'node' },
});

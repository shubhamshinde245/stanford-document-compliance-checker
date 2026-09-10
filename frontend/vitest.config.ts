// Excluded from tsconfig.json: @vitejs/plugin-react and vitest bundle different
// vite builds (rollup vs rolldown), so the Plugin types do not line up here.
// The tests themselves are still typechecked by `npx tsc --noEmit`.
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    restoreMocks: true,
  },
});

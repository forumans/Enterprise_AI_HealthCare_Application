/// <reference types="vitest" />
import { defineConfig, mergeConfig } from "vitest/config";
import viteConfig from "./vite.config";

// Tests reuse the app's Vite setup (React plugin) and run in a simulated browser (jsdom) so
// components can be rendered with React Testing Library. Pure-logic tests run there too.
export default mergeConfig(
  viteConfig,
  defineConfig({
    // vite.config pins NODE_ENV to "production" for builds; React's test helpers need non-production
    define: { "process.env.NODE_ENV": JSON.stringify("test") },
    test: {
      environment: "jsdom",
      setupFiles: ["./src/test/setup.ts"],
      css: false,
    },
  })
);

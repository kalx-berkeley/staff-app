import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  base: '/',
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8420',
        changeOrigin: true,
      },
      // Short links. A regex, so it doesn't also catch paths like /google
      '^/go/': {
        target: 'http://localhost:8420',
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    // Longer than the wait for findBy* and waitFor in src/test/setup.ts, so a failed
    // wait reports what it couldn't find instead of a plain timeout.
    testTimeout: 15000,
    experimental: {
      diagnostics: {
        // Vitest suggests `pool: 'vmThreads'` or `isolate: false` to avoid
        // creating jsdom once per file. Neither made this suite faster when
        // measured, and `isolate: false` would share module mocks across
        // files, so silence the hint.
        environment: false,
      },
    },
  },
})

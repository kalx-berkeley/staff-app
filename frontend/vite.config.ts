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
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
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

import { defineConfig } from 'electron-vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const root = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  main: {
    build: { rollupOptions: { input: path.join(root, 'electron/main.ts') } }
  },
  preload: {
    build: { rollupOptions: { input: path.join(root, 'electron/preload.ts') } }
  },
  renderer: {
    root,
    build: {
      rollupOptions: { input: path.join(root, 'index.html') }
    },
    plugins: [vue()]
  }
})

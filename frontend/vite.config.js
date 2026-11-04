import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Dentro de Docker, localhost apuntaría al propio contenedor de Vite.
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
    },
  },
});
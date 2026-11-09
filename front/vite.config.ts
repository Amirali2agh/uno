import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The FastAPI server owns both WebSocket endpoints (/ws/queue, /ws/room) and the
// admin surface (/admin). In development the browser talks to the Vite origin and
// Vite forwards those paths to the backend, so the client never has to know the
// backend port and no CORS setup is required.
const backendOrigin = process.env.BACKEND_ORIGIN ?? 'http://127.0.0.1:8000'

const proxy = {
  '/ws': { target: backendOrigin, ws: true, changeOrigin: true },
  '/admin': { target: backendOrigin, changeOrigin: true },
}

export default defineConfig({
  plugins: [
    react(),
    tailwindcss()
  ],
  server: {
    host: true, // reachable from phones/tablets on the same network
    port: 5173,
    proxy,
  },
  preview: {
    port: 4173,
    proxy,
  },
})

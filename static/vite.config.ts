import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
    // relative asset URLs (fonts) in the built CSS, so they resolve under Django's /static/
    base: './',
    plugins: [
        tailwindcss(),
    ],
    server: {
        watch: {
            ignored: ['!../../**/*'], // Ensure Vite watches parent folder
        }
    },
    build: {
        outDir: 'dist', // Output directory
        sourcemap: true,
        rollupOptions: {
            output: {
                entryFileNames: '[name].js',
                chunkFileNames: '[name].js',
                assetFileNames: '[name][extname]'
            }
        }
    }
})
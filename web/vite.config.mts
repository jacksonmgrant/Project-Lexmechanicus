import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, '..', '')
    const rawApiTarget = env.VITE_API_URL || env.API_URL || 'http://localhost:8765'
    const apiTarget = rawApiTarget.replace(/^http:\/\/localhost(?=[:/]|$)/, 'http://127.0.0.1')

    return {
        envDir: '..',
        define: {
            __API_BASE__: JSON.stringify(env.VITE_API_URL || ''),
        },
        plugins: [react()],
        css: {
            preprocessorOptions: {
                scss: {
                    api: 'modern-compiler',
                },
            },
        },
        server: {
            port: 4269,
            proxy: {
                '/auth': apiTarget,
                '/ask': apiTarget,
                '/search': apiTarget,
                '/uploads': apiTarget,
                '/viewer': apiTarget,
                '/health': apiTarget,
                '/robots.txt': apiTarget,
            },
        },
    }
})

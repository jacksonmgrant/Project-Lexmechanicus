import React from 'react'
import { createRoot } from 'react-dom/client'
import { HelmetProvider } from 'react-helmet-async'
import App from './App'
import './styles/app.scss'

const adsenseClient = import.meta.env.VITE_ADSENSE_CLIENT?.trim()

if (adsenseClient && typeof document !== 'undefined') {
    const existing = document.querySelector('script[data-adsense-client]')
    if (!existing) {
        const script = document.createElement('script')
        script.async = true
        script.crossOrigin = 'anonymous'
        script.dataset.adsenseClient = adsenseClient
        script.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${encodeURIComponent(adsenseClient)}`
        document.head.appendChild(script)
    }
}


createRoot(document.getElementById('root')!).render(
    <HelmetProvider>
        <App />
    </HelmetProvider>
)

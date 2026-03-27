/// <reference types="vite/client" />

interface ImportMetaEnv {
    readonly VITE_API_URL: string
    readonly VITE_ADSENSE_CLIENT: string
    readonly VITE_ADSENSE_SLOT_TOP: string
    readonly VITE_DEFAULT_GAME_SYSTEM_ID: string
    readonly VITE_DEFAULT_FOLDER_ID: string
}

interface ImportMeta {
    readonly env: ImportMetaEnv
}

declare const __API_BASE__: string

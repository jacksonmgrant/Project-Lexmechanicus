import React from 'react'
import { getOrCreateStoredValue, getStoredValue, setStoredValue } from '../lib/session'

type SessionInfo = {
    authenticated: boolean
    user: { id: number, email: string, display_name?: string | null, created_at: string | null } | null
    free_usage?: {
        limit: number
        used: number
        remaining: number
        reset_in_seconds: number
        exhausted: boolean
    }
}

export type ListedFile = {
    id: number
    title: string
    filename: string
    mime_type: string
    size_bytes: number
    is_public: boolean
    status: string
    folder_id: number
    game_system_id: number
    uploader_email: string
    chunk_count: number
    downloads: number
    views: number
}

type FileScope = 'browse' | 'mine'

type AppContextValue = {
    apiBase: string
    token: string
    guestId: string
    session: SessionInfo | null
    defaultGameSystemId: number
    defaultFolderId: number
    refreshSession: () => Promise<void>
    login: (email: string, password: string) => Promise<string>
    signup: (displayName: string, email: string, password: string) => Promise<string>
    logout: () => void
    changePassword: (currentPassword: string, newPassword: string) => Promise<string>
    listFiles: (scope: FileScope, query?: string, gameSystemId?: number) => Promise<ListedFile[]>
    uploadFile: (file: File, isPublic: boolean) => Promise<{ file_id: number, chunks: number }>
    deleteFile: (fileId: number) => Promise<void>
    streamAsk: (question: string, onToken: (token: string) => void) => Promise<void>
}

const AppContext = React.createContext<AppContextValue | null>(null)

function buildSseLines(rawEvent: string) {
    const lines = rawEvent.split(/\r?\n/)
    let eventName = 'message'
    const dataLines: string[] = []
    for (const line of lines) {
        if (line.startsWith('event:')) eventName = line.slice(6).trim()
        if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
    }
    return { eventName, data: dataLines.join('\n') }
}

export function AppProvider({ children }: { children: React.ReactNode }) {
    const apiBase = import.meta.env.VITE_API_URL || ''
    const defaultGameSystemId = Number(import.meta.env.VITE_DEFAULT_GAME_SYSTEM_ID || '1') || 1
    const defaultFolderId = Number(import.meta.env.VITE_DEFAULT_FOLDER_ID || '1') || 1
    const [token, setToken] = React.useState(() => getStoredValue('lexmechanicus.token'))
    const [guestId] = React.useState(() => getOrCreateStoredValue('lexmechanicus.guestId', () => window.crypto.randomUUID()))
    const [session, setSession] = React.useState<SessionInfo | null>(null)

    const authHeaders = React.useCallback((includeGuest = true) => {
        const headers: Record<string, string> = {}
        if (includeGuest) headers['X-Guest-Id'] = guestId
        if (token.trim()) headers.Authorization = `Bearer ${token}`
        return headers
    }, [guestId, token])

    const refreshSession = React.useCallback(async () => {
        const response = await fetch(`${apiBase}/auth/me`, { headers: authHeaders(true) })
        if (!response.ok) throw new Error('Unable to load session.')
        const payload = await response.json() as SessionInfo
        setSession(payload)
    }, [apiBase, authHeaders])

    React.useEffect(() => {
        refreshSession().catch(() => undefined)
    }, [refreshSession])

    const storeToken = React.useCallback((nextToken: string) => {
        setStoredValue('lexmechanicus.token', nextToken)
        setToken(nextToken)
    }, [])

    const authenticate = React.useCallback(async (path: '/auth/login', email: string, password: string) => {
        const response = await fetch(`${apiBase}${path}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Guest-Id': guestId,
            },
            body: JSON.stringify({ email, password }),
        })
        const payload = await response.json().catch(() => ({}))
        if (!response.ok) throw new Error(typeof payload?.detail === 'string' ? payload.detail : 'Unable to authenticate.')
        storeToken(payload.access_token || '')
        setSession({ authenticated: true, user: payload.user })
        return 'Signed in.'
    }, [apiBase, guestId, storeToken])

    const signup = React.useCallback(async (displayName: string, email: string, password: string) => {
        const response = await fetch(`${apiBase}/auth/signup`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Guest-Id': guestId,
            },
            body: JSON.stringify({ display_name: displayName, email, password }),
        })
        const payload = await response.json().catch(() => ({}))
        if (!response.ok) throw new Error(typeof payload?.detail === 'string' ? payload.detail : 'Unable to authenticate.')
        storeToken(payload.access_token || '')
        setSession({ authenticated: true, user: payload.user })
        return 'Account created.'
    }, [apiBase, guestId, storeToken])

    const listFiles = React.useCallback(async (scope: FileScope, query = '', gameSystemId?: number) => {
        const params = new URLSearchParams({ scope, q: query, limit: '50' })
        if (typeof gameSystemId === 'number') params.set('game_system_id', String(gameSystemId))
        const response = await fetch(`${apiBase}/uploads/files?${params.toString()}`, {
            headers: authHeaders(false),
        })
        const payload = await response.json().catch(() => ([]))
        if (!response.ok) throw new Error(typeof payload?.detail === 'string' ? payload.detail : 'Unable to load files.')
        return payload as ListedFile[]
    }, [apiBase, authHeaders])

    const uploadFile = React.useCallback(async (file: File, isPublic: boolean) => {
        const body = new FormData()
        body.append('folder_id', String(defaultFolderId))
        body.append('is_public', String(isPublic))
        body.append('f', file)
        const response = await fetch(`${apiBase}/uploads/`, {
            method: 'POST',
            headers: authHeaders(false),
            body,
        })
        const payload = await response.json().catch(() => ({}))
        if (!response.ok) throw new Error(typeof payload?.detail === 'string' ? payload.detail : 'Unable to upload file.')
        return payload as { file_id: number, chunks: number }
    }, [apiBase, authHeaders, defaultFolderId])

    const deleteFile = React.useCallback(async (fileId: number) => {
        const response = await fetch(`${apiBase}/uploads/${fileId}`, {
            method: 'DELETE',
            headers: authHeaders(false),
        })
        const payload = await response.json().catch(() => ({}))
        if (!response.ok) throw new Error(typeof payload?.detail === 'string' ? payload.detail : 'Unable to delete file.')
    }, [apiBase, authHeaders])

    const changePassword = React.useCallback(async (currentPassword: string, newPassword: string) => {
        const response = await fetch(`${apiBase}/auth/password`, {
            method: 'POST',
            headers: {
                ...authHeaders(false),
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
        })
        const payload = await response.json().catch(() => ({}))
        if (!response.ok) throw new Error(typeof payload?.detail === 'string' ? payload.detail : 'Unable to update password.')
        return 'Password updated.'
    }, [apiBase, authHeaders])

    const streamAsk = React.useCallback(async (question: string, onToken: (token: string) => void) => {
        const url = `${apiBase}/ask/stream?q=${encodeURIComponent(question)}&game_system_id=${defaultGameSystemId}`
        const response = await fetch(url, {
            headers: {
                ...authHeaders(true),
                Accept: 'text/event-stream',
            },
        })
        if (!response.ok || !response.body) {
            const payload = await response.json().catch(() => ({}))
            throw new Error(typeof payload?.detail === 'string' ? payload.detail : `Streaming failed with status ${response.status}.`)
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
            const { done, value } = await reader.read()
            buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
            buffer = buffer.replace(/\r\n/g, '\n').replace(/\r/g, '\n')

            let boundary = buffer.indexOf('\n\n')
            while (boundary >= 0) {
                const rawEvent = buffer.slice(0, boundary).trim()
                buffer = buffer.slice(boundary + 2)
                if (rawEvent) {
                    const { eventName, data } = buildSseLines(rawEvent)
                    if (eventName === 'token') onToken(data)
                }
                boundary = buffer.indexOf('\n\n')
            }

            if (done) break
        }

        await refreshSession().catch(() => undefined)
    }, [apiBase, authHeaders, defaultGameSystemId, refreshSession])

    const value = React.useMemo<AppContextValue>(() => ({
        apiBase,
        token,
        guestId,
        session,
        defaultGameSystemId,
        defaultFolderId,
        refreshSession,
        login: (email, password) => authenticate('/auth/login', email, password),
        signup,
        logout: () => {
            storeToken('')
            setSession((current) => current ? { authenticated: false, user: null, free_usage: current.free_usage } : null)
        },
        changePassword,
        listFiles,
        uploadFile,
        deleteFile,
        streamAsk,
    }), [
        apiBase,
        token,
        guestId,
        session,
        defaultGameSystemId,
        defaultFolderId,
        refreshSession,
        authenticate,
        signup,
        storeToken,
        changePassword,
        listFiles,
        uploadFile,
        deleteFile,
        streamAsk,
    ])

    return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useAppContext() {
    const value = React.useContext(AppContext)
    if (!value) throw new Error('useAppContext must be used within AppProvider.')
    return value
}

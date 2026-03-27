import React from 'react'
import { ApiError, apiErrorFromPayload, getErrorMessage, logApiError, readResponsePayload, requestJson, requestVoid } from '../lib/api'
import { getOrCreateStoredValue, getStoredValue, setStoredValue } from '../lib/session'

export type Tag = {
    id: number
    name: string
    slug: string
    kind: 'general'
}

export type Ruleset = {
    id: number
    name: string
    slug: string
}

type SessionInfo = {
    authenticated: boolean
    user: { id: number, email: string, display_name?: string | null, created_at: string | null } | null
    active_game_system?: Ruleset | null
    available_game_systems?: Ruleset[]
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
    description?: string | null
    filename: string
    mime_type: string
    size_bytes: number
    is_public: boolean
    status: string
    folder_id: number
    game_system_id: number
    game_system: Ruleset | null
    tags: Tag[]
    uploader_email: string
    uploader_name: string
    chunk_count: number
    downloads: number
    views: number
}

type FileScope = 'browse' | 'mine'

type CreateRulesetInput = {
    name: string
    aliases?: string[]
}

type AppContextValue = {
    apiBase: string
    token: string
    guestId: string
    session: SessionInfo | null
    sessionError: string
    defaultGameSystemId: number
    defaultFolderId: number
    activeGameSystem: Ruleset | null
    availableGameSystems: Ruleset[]
    refreshSession: () => Promise<void>
    refreshGameSystems: () => Promise<void>
    login: (email: string, password: string) => Promise<string>
    signup: (displayName: string, email: string, password: string) => Promise<string>
    logout: () => void
    changePassword: (currentPassword: string, newPassword: string) => Promise<string>
    listFiles: (scope: FileScope, query?: string, rulesetId?: number) => Promise<ListedFile[]>
    uploadFile: (file: File, isPublic: boolean, title: string, description?: string, rulesetId?: number | null, tagIds?: number[]) => Promise<{ file_id: number, chunks: number }>
    deleteFile: (fileId: number) => Promise<void>
    streamAsk: (question: string, onToken: (token: string) => void) => Promise<void>
    searchTags: (query: string, limit?: number) => Promise<Tag[]>
    createTag: (name: string) => Promise<Tag>
    updateFileTags: (fileId: number, tagIds: number[]) => Promise<Tag[]>
    searchGameSystems: (query: string, limit?: number) => Promise<Ruleset[]>
    createGameSystem: (input: CreateRulesetInput) => Promise<Ruleset>
    updateFileGameSystem: (fileId: number, rulesetId: number) => Promise<Ruleset>
    setActiveGameSystem: (rulesetId: number) => Promise<void>
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

function sleep(ms: number) {
    return new Promise((resolve) => window.setTimeout(resolve, ms))
}

export function AppProvider({ children }: { children: React.ReactNode }) {
    const apiBase = __API_BASE__ || import.meta.env.VITE_API_URL || ''
    const defaultGameSystemId = Number(import.meta.env.VITE_DEFAULT_GAME_SYSTEM_ID || '1') || 1
    const defaultFolderId = Number(import.meta.env.VITE_DEFAULT_FOLDER_ID || '1') || 1
    const [token, setToken] = React.useState(() => getStoredValue('lexmechanicus.token'))
    const [guestId] = React.useState(() => getOrCreateStoredValue('lexmechanicus.guestId', () => window.crypto.randomUUID()))
    const [session, setSession] = React.useState<SessionInfo | null>(null)
    const [sessionError, setSessionError] = React.useState('')
    const [activeGameSystem, setActiveGameSystemState] = React.useState<Ruleset | null>(null)
    const [availableGameSystems, setAvailableGameSystems] = React.useState<Ruleset[]>([])

    const applyGameSystems = React.useCallback((nextActive: Ruleset | null | undefined, nextAvailable: Ruleset[] | undefined) => {
        setActiveGameSystemState(nextActive || null)
        setAvailableGameSystems(nextAvailable || [])
    }, [])

    const authHeaders = React.useCallback((includeGuest = true) => {
        const headers: Record<string, string> = {}
        if (includeGuest) headers['X-Guest-Id'] = guestId
        if (token.trim()) headers.Authorization = `Bearer ${token}`
        return headers
    }, [guestId, token])

    const refreshSession = React.useCallback(async () => {
        try {
            const payload = await requestJson<SessionInfo>(`${apiBase}/auth/me`, {
                headers: authHeaders(true),
                operation: 'Load session',
                fallbackMessage: 'Unable to load your session.',
            })
            setSession(payload)
            applyGameSystems(payload.active_game_system, payload.available_game_systems)
            setSessionError('')
        } catch (error) {
            setSession(null)
            setSessionError(getErrorMessage(error, 'Unable to load your session.'))
            throw error
        }
    }, [apiBase, applyGameSystems, authHeaders])

    const refreshGameSystems = React.useCallback(async () => {
        const payload = await requestJson<{ active_game_system: Ruleset | null, available_game_systems: Ruleset[] }>(`${apiBase}/uploads/game-systems`, {
            headers: authHeaders(false),
            operation: 'Load game systems',
            fallbackMessage: 'Unable to load game systems.',
        })
        applyGameSystems(payload.active_game_system, payload.available_game_systems)
    }, [apiBase, applyGameSystems, authHeaders])

    React.useEffect(() => {
        let cancelled = false
        const loadSession = async () => {
            let lastError: unknown = null
            for (let attempt = 0; attempt < 5 && !cancelled; attempt += 1) {
                try {
                    await refreshSession()
                    return
                } catch (error) {
                    lastError = error
                    if (!(error instanceof ApiError) || error.status !== 0 || attempt === 4) {
                        break
                    }
                    await sleep(800)
                }
            }
            if (!cancelled && lastError) {
                console.error('Initial session load failed after retries.', lastError)
            }
        }
        loadSession().catch(() => undefined)
        return () => {
            cancelled = true
        }
    }, [refreshSession])

    const storeToken = React.useCallback((nextToken: string) => {
        setStoredValue('lexmechanicus.token', nextToken)
        setToken(nextToken)
    }, [])

    const authenticate = React.useCallback(async (path: '/auth/login', email: string, password: string) => {
        const payload = await requestJson<{ access_token: string, user: SessionInfo['user'] }>(`${apiBase}${path}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Guest-Id': guestId },
            body: JSON.stringify({ email, password }),
            operation: path === '/auth/login' ? 'Sign in' : 'Authenticate',
            fallbackMessage: 'Unable to authenticate.',
        })
        storeToken(payload.access_token || '')
        setSession({ authenticated: true, user: payload.user })
        setSessionError('')
        await refreshSession().catch(() => undefined)
        return 'Signed in.'
    }, [apiBase, guestId, refreshSession, storeToken])

    const signup = React.useCallback(async (displayName: string, email: string, password: string) => {
        const payload = await requestJson<{ access_token: string, user: SessionInfo['user'] }>(`${apiBase}/auth/signup`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Guest-Id': guestId },
            body: JSON.stringify({ display_name: displayName, email, password }),
            operation: 'Create account',
            fallbackMessage: 'Unable to create your account.',
        })
        storeToken(payload.access_token || '')
        setSession({ authenticated: true, user: payload.user })
        setSessionError('')
        await refreshSession().catch(() => undefined)
        return 'Account created.'
    }, [apiBase, guestId, refreshSession, storeToken])

    const listFiles = React.useCallback(async (scope: FileScope, query = '', rulesetId?: number) => {
        const params = new URLSearchParams({ scope, q: query, limit: '50' })
        if (typeof rulesetId === 'number') params.set('ruleset_id', String(rulesetId))
        return requestJson<ListedFile[]>(`${apiBase}/uploads/files?${params.toString()}`, {
            headers: authHeaders(false),
            operation: scope === 'mine' ? 'List my files' : 'Browse files',
            fallbackMessage: 'Unable to load files.',
        })
    }, [apiBase, authHeaders])

    const uploadFile = React.useCallback(async (file: File, isPublic: boolean, title: string, description = '', rulesetId?: number | null, tagIds: number[] = []) => {
        const body = new FormData()
        body.append('folder_id', String(defaultFolderId))
        body.append('is_public', String(isPublic))
        body.append('title', title)
        body.append('description', description)
        body.append('tag_ids', JSON.stringify(tagIds))
        if (typeof rulesetId === 'number') {
            body.append('ruleset_id', String(rulesetId))
        } else if (activeGameSystem?.id) {
            body.append('ruleset_id', String(activeGameSystem.id))
        }
        body.append('f', file)
        const result = await requestJson<{ file_id: number, chunks: number }>(`${apiBase}/uploads/`, {
            method: 'POST',
            headers: authHeaders(false),
            body,
            operation: 'Upload file',
            fallbackMessage: 'Unable to upload file.',
        })
        await refreshGameSystems().catch(() => undefined)
        return result
    }, [activeGameSystem, apiBase, authHeaders, defaultFolderId, refreshGameSystems])

    const deleteFile = React.useCallback(async (fileId: number) => {
        await requestVoid(`${apiBase}/uploads/${fileId}`, {
            method: 'DELETE',
            headers: authHeaders(false),
            operation: 'Delete file',
            fallbackMessage: 'Unable to delete file.',
        })
        await refreshGameSystems().catch(() => undefined)
    }, [apiBase, authHeaders, refreshGameSystems])

    const changePassword = React.useCallback(async (currentPassword: string, newPassword: string) => {
        await requestVoid(`${apiBase}/auth/password`, {
            method: 'POST',
            headers: { ...authHeaders(false), 'Content-Type': 'application/json' },
            body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
            operation: 'Change password',
            fallbackMessage: 'Unable to update password.',
        })
        return 'Password updated.'
    }, [apiBase, authHeaders])

    const searchTags = React.useCallback(async (query: string, limit = 12) => {
        const params = new URLSearchParams({ q: query, kind: 'general', limit: String(limit) })
        return requestJson<Tag[]>(`${apiBase}/uploads/tags?${params.toString()}`, {
            headers: authHeaders(false),
            operation: 'Search tags',
            fallbackMessage: 'Unable to load tags.',
        })
    }, [apiBase, authHeaders])

    const createTag = React.useCallback(async (name: string) => {
        return requestJson<Tag>(`${apiBase}/uploads/tags`, {
            method: 'POST',
            headers: { ...authHeaders(false), 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, kind: 'general' }),
            operation: 'Create tag',
            fallbackMessage: 'Unable to create the tag.',
        })
    }, [apiBase, authHeaders])

    const updateFileTags = React.useCallback(async (fileId: number, tagIds: number[]) => {
        const payload = await requestJson<{ tags: Tag[] }>(`${apiBase}/uploads/${fileId}/tags`, {
            method: 'PUT',
            headers: { ...authHeaders(false), 'Content-Type': 'application/json' },
            body: JSON.stringify({ tag_ids: tagIds }),
            operation: 'Update file tags',
            fallbackMessage: 'Unable to update file tags.',
        })
        return payload.tags
    }, [apiBase, authHeaders])

    const searchGameSystems = React.useCallback(async (query: string, limit = 12) => {
        const params = new URLSearchParams({ q: query, limit: String(limit) })
        return requestJson<Ruleset[]>(`${apiBase}/uploads/game-systems/search?${params.toString()}`, {
            headers: authHeaders(false),
            operation: 'Search game systems',
            fallbackMessage: 'Unable to load game systems.',
        })
    }, [apiBase, authHeaders])

    const createGameSystem = React.useCallback(async (input: CreateRulesetInput) => {
        const payload = await requestJson<Ruleset>(`${apiBase}/uploads/game-systems`, {
            method: 'POST',
            headers: { ...authHeaders(false), 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: input.name,
                aliases: input.aliases || [],
            }),
            operation: 'Create game system',
            fallbackMessage: 'Unable to create the game system.',
        })
        await refreshGameSystems().catch(() => undefined)
        return payload
    }, [apiBase, authHeaders, refreshGameSystems])

    const updateFileGameSystem = React.useCallback(async (fileId: number, rulesetId: number) => {
        const payload = await requestJson<{ game_system: Ruleset }>(`${apiBase}/uploads/${fileId}/game-system`, {
            method: 'PUT',
            headers: { ...authHeaders(false), 'Content-Type': 'application/json' },
            body: JSON.stringify({ ruleset_id: rulesetId }),
            operation: 'Update file game system',
            fallbackMessage: 'Unable to update the game system.',
        })
        await refreshGameSystems().catch(() => undefined)
        return payload.game_system
    }, [apiBase, authHeaders, refreshGameSystems])

    const setActiveGameSystem = React.useCallback(async (rulesetId: number) => {
        const payload = await requestJson<{ active_game_system: Ruleset | null, available_game_systems: Ruleset[] }>(`${apiBase}/uploads/game-systems/active`, {
            method: 'PUT',
            headers: { ...authHeaders(false), 'Content-Type': 'application/json' },
            body: JSON.stringify({ ruleset_id: rulesetId }),
            operation: 'Set active game system',
            fallbackMessage: 'Unable to set the active game system.',
        })
        applyGameSystems(payload.active_game_system, payload.available_game_systems)
    }, [apiBase, applyGameSystems, authHeaders])

    const streamAsk = React.useCallback(async (question: string, onToken: (token: string) => void) => {
        if (!activeGameSystem?.id) {
            throw new ApiError('Choose a game system before chatting.', {
                status: 422,
                code: 'RULESET_REQUIRED',
            })
        }
        const rulesetId = activeGameSystem.id
        const url = `${apiBase}/ask/stream?q=${encodeURIComponent(question)}&ruleset_id=${rulesetId}`
        let response: Response
        try {
            response = await fetch(url, {
                headers: { ...authHeaders(true), Accept: 'text/event-stream' },
            })
        } catch (error) {
            const apiError = apiErrorFromPayload(null, 0, 'Unable to reach the server. Check your connection and try again.')
            logApiError('Stream answer', apiError, { url })
            throw apiError
        }

        if (!response.ok || !response.body) {
            const payload = await readResponsePayload(response)
            const apiError = apiErrorFromPayload(payload, response.status, `Streaming failed with status ${response.status}.`)
            logApiError('Stream answer', apiError, { url, status: response.status, payload })
            throw apiError
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        try {
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
                        if (eventName === 'error') {
                            let payload: unknown = data
                            try {
                                payload = data ? JSON.parse(data) as unknown : null
                            } catch {
                                payload = data
                            }
                            const apiError = apiErrorFromPayload({ detail: payload }, response.status, 'Unable to complete the request.')
                            logApiError('Stream answer', apiError, { url, status: response.status, payload })
                            throw apiError
                        }
                    }
                    boundary = buffer.indexOf('\n\n')
                }

                if (done) break
            }
        } catch (error) {
            if (error instanceof ApiError) throw error
            const apiError = apiErrorFromPayload(
                { detail: { message: getErrorMessage(error, 'The response stream ended unexpectedly.'), code: 'STREAM_FAILED' } },
                response.status,
                'The response stream ended unexpectedly.',
            )
            logApiError('Stream answer', apiError, { url, status: response.status })
            throw apiError
        } finally {
            reader.releaseLock()
        }

        await refreshSession().catch(() => undefined)
    }, [activeGameSystem, apiBase, authHeaders, refreshSession])

    const value = React.useMemo<AppContextValue>(() => ({
        apiBase,
        token,
        guestId,
        session,
        sessionError,
        defaultGameSystemId,
        defaultFolderId,
        activeGameSystem,
        availableGameSystems,
        refreshSession,
        refreshGameSystems,
        login: (email, password) => authenticate('/auth/login', email, password),
        signup,
        logout: () => {
            storeToken('')
            setSessionError('')
            setSession((current) => current ? { authenticated: false, user: null, free_usage: current.free_usage } : null)
        },
        changePassword,
        listFiles,
        uploadFile,
        deleteFile,
        streamAsk,
        searchTags,
        createTag,
        updateFileTags,
        searchGameSystems,
        createGameSystem,
        updateFileGameSystem,
        setActiveGameSystem,
    }), [
        apiBase,
        token,
        guestId,
        session,
        sessionError,
        defaultGameSystemId,
        defaultFolderId,
        activeGameSystem,
        availableGameSystems,
        refreshSession,
        refreshGameSystems,
        authenticate,
        signup,
        storeToken,
        changePassword,
        listFiles,
        uploadFile,
        deleteFile,
        streamAsk,
        searchTags,
        createTag,
        updateFileTags,
        searchGameSystems,
        createGameSystem,
        updateFileGameSystem,
        setActiveGameSystem,
    ])

    return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useAppContext() {
    const value = React.useContext(AppContext)
    if (!value) throw new Error('useAppContext must be used within AppProvider.')
    return value
}

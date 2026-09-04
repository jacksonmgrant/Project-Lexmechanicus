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

export type Bundle = {
    id: number
    title: string
    description?: string | null
    is_public: boolean
    is_saved: boolean
    is_default: boolean
    is_owned: boolean
    file_count: number
    save_count: number
    game_system_id: number
    game_system: Ruleset | null
    owner_name: string
    preview_titles: string[]
    created_at?: string | null
}

export type ChatCitation = {
    id: string
    file_id: number
    document_title: string
    page_number: number | null
    page_anchor_ratio?: number | null
    mime_type: string
    section?: string | null
    excerpt_text?: string
}

export type ChatHistoryTurn = {
    role: 'user' | 'assistant'
    content: string
}

export type BundleDetail = {
    bundle: Bundle
    files: ListedFile[]
}

type SessionInfo = {
    authenticated: boolean
    user: {
        id: number
        email: string
        display_name?: string | null
        dmca_strike_count: number
        account_status: 'active' | 'suspended'
        dmca_suspended_at?: string | null
        dmca_suspension_reason?: string | null
        created_at: string | null
    } | null
    active_game_system?: Ruleset | null
    available_game_systems?: Ruleset[]
    active_bundle?: Bundle | null
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
    created_at?: string | null
    is_public: boolean
    is_copyright_restricted: boolean
    is_saved: boolean
    status: string
    folder_id: number
    game_system_id: number
    game_system: Ruleset | null
    tags: Tag[]
    uploader_name: string
    chunk_count: number
    save_count: number
}

type FileScope = 'browse' | 'mine' | 'saved'
type BundleScope = 'browse' | 'mine' | 'saved'

type CreateRulesetInput = {
    name: string
    aliases?: string[]
}

type CreateBundleInput = {
    title: string
    description?: string
    rulesetId: number
    fileIds: number[]
    isPublic: boolean
    publicDistributionConfirmed: boolean
}

type CopyrightTakedownInput = {
    claimantName: string
    claimantEmail: string
    claimantPhone: string
    claimantAddress: string
    copyrightOwnerName?: string
    workDescription: string
    materialLocation?: string
    infringementExplanation: string
    signature: string
    goodFaithStatementConfirmed: boolean
    accuracyStatementConfirmed: boolean
    authorityStatementConfirmed: boolean
}

type CopyrightCounterNoticeInput = {
    claimantName: string
    claimantEmail: string
    claimantPhone: string
    claimantAddress: string
    counterExplanation: string
    signature: string
    mistakeStatementConfirmed: boolean
    perjuryStatementConfirmed: boolean
    jurisdictionStatementConfirmed: boolean
}

export type CopyrightNoticeSummary = {
    id: number
    status: string
    created_at?: string | null
    disabled_at?: string | null
    review_notes?: string | null
    counter_submitted_at?: string | null
    restore_after_at?: string | null
    restore_deadline_at?: string | null
    restored_at?: string | null
    lawsuit_notice_received_at?: string | null
}

export type CopyrightStatusPayload = {
    file: {
        id: number
        title: string
        filename: string
        is_public: boolean
        is_copyright_restricted: boolean
        uploader_name: string
        viewer_url: string
    }
    latest_notice: CopyrightNoticeSummary | null
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
    activeBundle: Bundle | null
    refreshSession: () => Promise<void>
    refreshGameSystems: () => Promise<void>
    login: (email: string, password: string) => Promise<string>
    signup: (displayName: string, email: string, password: string) => Promise<string>
    logout: () => void
    updateProfile: (displayName: string) => Promise<string>
    changePassword: (currentPassword: string, newPassword: string) => Promise<string>
    listFiles: (scope: FileScope, query?: string, rulesetId?: number) => Promise<ListedFile[]>
    uploadFile: (
        file: File,
        isPublic: boolean,
        title: string,
        description?: string,
        rulesetId?: number | null,
        tagIds?: number[],
        publicDistributionConfirmed?: boolean,
    ) => Promise<{ file_id: number, chunks: number }>
    deleteFile: (fileId: number) => Promise<void>
    saveFile: (fileId: number) => Promise<void>
    unsaveFile: (fileId: number) => Promise<void>
    getCopyrightStatus: (fileId: number) => Promise<CopyrightStatusPayload>
    submitCopyrightTakedown: (fileId: number, input: CopyrightTakedownInput) => Promise<{ request_id: number, admin_notified: boolean }>
    submitCopyrightCounterNotice: (fileId: number, input: CopyrightCounterNoticeInput) => Promise<{ request_id: number, admin_notified: boolean }>
    listBundles: (scope: BundleScope, query?: string, rulesetId?: number) => Promise<Bundle[]>
    getBundle: (bundleId: number) => Promise<BundleDetail>
    createBundle: (input: CreateBundleInput) => Promise<Bundle>
    addFilesToBundle: (bundleId: number, fileIds: number[]) => Promise<BundleDetail>
    removeFileFromBundle: (bundleId: number, fileId: number) => Promise<{ deleted: boolean, bundle?: Bundle, files?: ListedFile[] }>
    deleteBundle: (bundleId: number) => Promise<void>
    updateBundleTitle: (bundleId: number, title: string) => Promise<string>
    saveBundle: (bundleId: number) => Promise<void>
    unsaveBundle: (bundleId: number) => Promise<void>
    setActiveBundle: (rulesetId: number, bundleId: number | null) => Promise<void>
    streamAsk: (question: string, history: ChatHistoryTurn[], onToken: (token: string) => void, onCitations?: (citations: ChatCitation[]) => void) => Promise<void>
    searchTags: (query: string, limit?: number) => Promise<Tag[]>
    createTag: (name: string) => Promise<Tag>
    updateFileTags: (fileId: number, tagIds: number[]) => Promise<Tag[]>
    updateFileTitle: (fileId: number, title: string) => Promise<string>
    searchGameSystems: (query: string, limit?: number) => Promise<Ruleset[]>
    createGameSystem: (input: CreateRulesetInput) => Promise<Ruleset>
    updateFileGameSystem: (fileId: number, rulesetId: number) => Promise<Ruleset>
    setActiveGameSystem: (rulesetId: number) => Promise<void>
}

const AppContext = React.createContext<AppContextValue | null>(null)

const TOKEN_STORAGE_KEY = 'rulefinder.token'
const LEGACY_TOKEN_STORAGE_KEYS = ['cogitator.token', 'lexmechanicus.token']
const GUEST_ID_STORAGE_KEY = 'rulefinder.guestId'
const LEGACY_GUEST_ID_STORAGE_KEYS = ['cogitator.guestId', 'lexmechanicus.guestId']

function getStoredValueWithLegacy(storageKey: string, legacyKeys: string[]) {
    const currentValue = getStoredValue(storageKey)
    if (currentValue.trim()) {
        return currentValue
    }

    for (const legacyKey of legacyKeys) {
        const legacyValue = getStoredValue(legacyKey)
        if (legacyValue.trim()) {
            setStoredValue(storageKey, legacyValue)
            return legacyValue
        }
    }
    return ''
}

function getOrCreateStoredValueWithLegacy(storageKey: string, legacyKeys: string[], createValue: () => string) {
    const currentValue = getStoredValue(storageKey)
    if (currentValue.trim()) {
        return currentValue
    }

    for (const legacyKey of legacyKeys) {
        const legacyValue = getStoredValue(legacyKey)
        if (legacyValue.trim()) {
            setStoredValue(storageKey, legacyValue)
            return legacyValue
        }
    }

    return getOrCreateStoredValue(storageKey, createValue)
}

function buildSseLines(rawEvent: string) {
    const lines = rawEvent.split(/\r?\n/)
    let eventName = 'message'
    const dataLines: string[] = []
    for (const line of lines) {
        if (line.startsWith('event:')) eventName = line.slice(6).trim()
        if (line.startsWith('data:')) dataLines.push(line.startsWith('data: ') ? line.slice(6) : line.slice(5))
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
    const [token, setToken] = React.useState(() => getStoredValueWithLegacy(TOKEN_STORAGE_KEY, LEGACY_TOKEN_STORAGE_KEYS))
    const [guestId] = React.useState(() => getOrCreateStoredValueWithLegacy(GUEST_ID_STORAGE_KEY, LEGACY_GUEST_ID_STORAGE_KEYS, () => window.crypto.randomUUID()))
    const [session, setSession] = React.useState<SessionInfo | null>(null)
    const [sessionError, setSessionError] = React.useState('')
    const [activeGameSystem, setActiveGameSystemState] = React.useState<Ruleset | null>(null)
    const [availableGameSystems, setAvailableGameSystems] = React.useState<Ruleset[]>([])
    const [activeBundle, setActiveBundleState] = React.useState<Bundle | null>(null)

    const applyGameSystems = React.useCallback((
        nextActive: Ruleset | null | undefined,
        nextAvailable: Ruleset[] | undefined,
        nextBundle?: Bundle | null,
    ) => {
        setActiveGameSystemState(nextActive || null)
        setAvailableGameSystems(nextAvailable || [])
        setActiveBundleState(nextBundle || null)
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
            applyGameSystems(payload.active_game_system, payload.available_game_systems, payload.active_bundle)
            setSessionError('')
        } catch (error) {
            setSession(null)
            setSessionError(getErrorMessage(error, 'Unable to load your session.'))
            throw error
        }
    }, [apiBase, applyGameSystems, authHeaders])

    const refreshGameSystems = React.useCallback(async () => {
        const payload = await requestJson<{ active_game_system: Ruleset | null, available_game_systems: Ruleset[], active_bundle?: Bundle | null }>(`${apiBase}/uploads/game-systems`, {
            headers: authHeaders(false),
            operation: 'Load game systems',
            fallbackMessage: 'Unable to load game systems.',
        })
        applyGameSystems(payload.active_game_system, payload.available_game_systems, payload.active_bundle)
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
        setStoredValue(TOKEN_STORAGE_KEY, nextToken)
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

    const updateProfile = React.useCallback(async (displayName: string) => {
        const payload = await requestJson<{ user: SessionInfo['user'] }>(`${apiBase}/auth/profile`, {
            method: 'PUT',
            headers: { ...authHeaders(false), 'Content-Type': 'application/json' },
            body: JSON.stringify({ display_name: displayName }),
            operation: 'Update profile',
            fallbackMessage: 'Unable to update your profile.',
        })
        setSession((current) => current ? { ...current, user: payload.user } : current)
        return 'Profile updated.'
    }, [apiBase, authHeaders])

    const listFiles = React.useCallback(async (scope: FileScope, query = '', rulesetId?: number) => {
        const params = new URLSearchParams({ scope, q: query, limit: '50' })
        if (typeof rulesetId === 'number') params.set('ruleset_id', String(rulesetId))
        return requestJson<ListedFile[]>(`${apiBase}/uploads/files?${params.toString()}`, {
            headers: authHeaders(false),
            operation: scope === 'mine' ? 'List my files' : (scope === 'saved' ? 'List saved files' : 'Browse files'),
            fallbackMessage: 'Unable to load files.',
        })
    }, [apiBase, authHeaders])

    const uploadFile = React.useCallback(async (
        file: File,
        isPublic: boolean,
        title: string,
        description = '',
        rulesetId?: number | null,
        tagIds: number[] = [],
        publicDistributionConfirmed = false,
    ) => {
        const body = new FormData()
        body.append('folder_id', String(defaultFolderId))
        body.append('is_public', String(isPublic))
        body.append('public_distribution_confirmed', String(publicDistributionConfirmed))
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

    const saveFile = React.useCallback(async (fileId: number) => {
        await requestVoid(`${apiBase}/uploads/${fileId}/saved`, {
            method: 'POST',
            headers: authHeaders(false),
            operation: 'Save file',
            fallbackMessage: 'Unable to save file.',
        })
    }, [apiBase, authHeaders])

    const unsaveFile = React.useCallback(async (fileId: number) => {
        await requestVoid(`${apiBase}/uploads/${fileId}/saved`, {
            method: 'DELETE',
            headers: authHeaders(false),
            operation: 'Unsave file',
            fallbackMessage: 'Unable to remove saved file.',
        })
    }, [apiBase, authHeaders])

    const getCopyrightStatus = React.useCallback(async (fileId: number) => {
        return requestJson<CopyrightStatusPayload>(`${apiBase}/uploads/${fileId}/copyright-status`, {
            headers: authHeaders(false),
            operation: 'Load copyright status',
            fallbackMessage: 'Unable to load copyright status.',
        })
    }, [apiBase, authHeaders])

    const submitCopyrightTakedown = React.useCallback(async (fileId: number, input: CopyrightTakedownInput) => {
        return requestJson<{ request_id: number, admin_notified: boolean }>(`${apiBase}/uploads/${fileId}/copyright-takedown`, {
            method: 'POST',
            headers: { ...authHeaders(false), 'Content-Type': 'application/json' },
            body: JSON.stringify({
                claimant_name: input.claimantName,
                claimant_email: input.claimantEmail,
                claimant_phone: input.claimantPhone,
                claimant_address: input.claimantAddress,
                copyright_owner_name: input.copyrightOwnerName || '',
                work_description: input.workDescription,
                material_location: input.materialLocation || '',
                infringement_explanation: input.infringementExplanation,
                signature: input.signature,
                good_faith_statement_confirmed: input.goodFaithStatementConfirmed,
                accuracy_statement_confirmed: input.accuracyStatementConfirmed,
                authority_statement_confirmed: input.authorityStatementConfirmed,
            }),
            operation: 'Submit copyright takedown',
            fallbackMessage: 'Unable to submit the copyright takedown request.',
        })
    }, [apiBase, authHeaders])

    const submitCopyrightCounterNotice = React.useCallback(async (fileId: number, input: CopyrightCounterNoticeInput) => {
        return requestJson<{ request_id: number, admin_notified: boolean }>(`${apiBase}/uploads/${fileId}/copyright-counter-notice`, {
            method: 'POST',
            headers: { ...authHeaders(false), 'Content-Type': 'application/json' },
            body: JSON.stringify({
                claimant_name: input.claimantName,
                claimant_email: input.claimantEmail,
                claimant_phone: input.claimantPhone,
                claimant_address: input.claimantAddress,
                counter_explanation: input.counterExplanation,
                signature: input.signature,
                mistake_statement_confirmed: input.mistakeStatementConfirmed,
                perjury_statement_confirmed: input.perjuryStatementConfirmed,
                jurisdiction_statement_confirmed: input.jurisdictionStatementConfirmed,
            }),
            operation: 'Submit copyright counter-notice',
            fallbackMessage: 'Unable to submit the copyright counter-notice.',
        })
    }, [apiBase, authHeaders])

    const listBundles = React.useCallback(async (scope: BundleScope, query = '', rulesetId?: number) => {
        const params = new URLSearchParams({ scope, q: query, limit: '50' })
        if (typeof rulesetId === 'number') params.set('ruleset_id', String(rulesetId))
        return requestJson<Bundle[]>(`${apiBase}/uploads/bundles?${params.toString()}`, {
            headers: authHeaders(false),
            operation: scope === 'mine' ? 'List my bundles' : (scope === 'saved' ? 'List saved bundles' : 'Browse bundles'),
            fallbackMessage: 'Unable to load bundles.',
        })
    }, [apiBase, authHeaders])

    const createBundle = React.useCallback(async (input: CreateBundleInput) => {
        return requestJson<Bundle>(`${apiBase}/uploads/bundles`, {
            method: 'POST',
            headers: { ...authHeaders(false), 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: input.title,
                description: input.description || '',
                ruleset_id: input.rulesetId,
                file_ids: input.fileIds,
                is_public: input.isPublic,
                public_distribution_confirmed: input.publicDistributionConfirmed,
            }),
            operation: 'Create bundle',
            fallbackMessage: 'Unable to create the bundle.',
        })
    }, [apiBase, authHeaders])

    const getBundle = React.useCallback(async (bundleId: number) => {
        return requestJson<BundleDetail>(`${apiBase}/uploads/bundles/${bundleId}`, {
            headers: authHeaders(false),
            operation: 'Load bundle',
            fallbackMessage: 'Unable to load the bundle.',
        })
    }, [apiBase, authHeaders])

    const addFilesToBundle = React.useCallback(async (bundleId: number, fileIds: number[]) => {
        return requestJson<BundleDetail>(`${apiBase}/uploads/bundles/${bundleId}/files`, {
            method: 'POST',
            headers: { ...authHeaders(false), 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_ids: fileIds }),
            operation: 'Add files to bundle',
            fallbackMessage: 'Unable to add files to the bundle.',
        })
    }, [apiBase, authHeaders])

    const removeFileFromBundle = React.useCallback(async (bundleId: number, fileId: number) => {
        return requestJson<{ deleted: boolean, bundle?: Bundle, files?: ListedFile[] }>(`${apiBase}/uploads/bundles/${bundleId}/files/${fileId}`, {
            method: 'DELETE',
            headers: authHeaders(false),
            operation: 'Remove file from bundle',
            fallbackMessage: 'Unable to remove that file from the bundle.',
        })
    }, [apiBase, authHeaders])

    const deleteBundle = React.useCallback(async (bundleId: number) => {
        await requestVoid(`${apiBase}/uploads/bundles/${bundleId}`, {
            method: 'DELETE',
            headers: authHeaders(false),
            operation: 'Delete bundle',
            fallbackMessage: 'Unable to delete the bundle.',
        })
        if (activeBundle?.id === bundleId) {
            setActiveBundleState(null)
        }
        await refreshGameSystems().catch(() => undefined)
    }, [activeBundle?.id, apiBase, authHeaders, refreshGameSystems])

    const updateBundleTitle = React.useCallback(async (bundleId: number, title: string) => {
        const payload = await requestJson<{ title: string }>(`${apiBase}/uploads/bundles/${bundleId}/title`, {
            method: 'PUT',
            headers: { ...authHeaders(false), 'Content-Type': 'application/json' },
            body: JSON.stringify({ title }),
            operation: 'Update bundle title',
            fallbackMessage: 'Unable to update the bundle title.',
        })
        setActiveBundleState((current) => current && current.id === bundleId ? { ...current, title: payload.title } : current)
        return payload.title
    }, [apiBase, authHeaders])

    const saveBundle = React.useCallback(async (bundleId: number) => {
        await requestVoid(`${apiBase}/uploads/bundles/${bundleId}/saved`, {
            method: 'POST',
            headers: authHeaders(false),
            operation: 'Save bundle',
            fallbackMessage: 'Unable to save bundle.',
        })
    }, [apiBase, authHeaders])

    const unsaveBundle = React.useCallback(async (bundleId: number) => {
        await requestVoid(`${apiBase}/uploads/bundles/${bundleId}/saved`, {
            method: 'DELETE',
            headers: authHeaders(false),
            operation: 'Unsave bundle',
            fallbackMessage: 'Unable to remove saved bundle.',
        })
    }, [apiBase, authHeaders])

    const setActiveBundle = React.useCallback(async (rulesetId: number, bundleId: number | null) => {
        const payload = await requestJson<{ active_bundle: Bundle | null }>(`${apiBase}/uploads/bundles/active`, {
            method: 'PUT',
            headers: { ...authHeaders(false), 'Content-Type': 'application/json' },
            body: JSON.stringify({ ruleset_id: rulesetId, bundle_id: bundleId }),
            operation: 'Set active bundle',
            fallbackMessage: 'Unable to set the active bundle.',
        })
        setActiveBundleState(payload.active_bundle || null)
    }, [apiBase, authHeaders])

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

    const updateFileTitle = React.useCallback(async (fileId: number, title: string) => {
        const payload = await requestJson<{ title: string }>(`${apiBase}/uploads/${fileId}/title`, {
            method: 'PUT',
            headers: { ...authHeaders(false), 'Content-Type': 'application/json' },
            body: JSON.stringify({ title }),
            operation: 'Update file title',
            fallbackMessage: 'Unable to update the file title.',
        })
        return payload.title
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
        const payload = await requestJson<{ active_game_system: Ruleset | null, available_game_systems: Ruleset[], active_bundle?: Bundle | null }>(`${apiBase}/uploads/game-systems/active`, {
            method: 'PUT',
            headers: { ...authHeaders(false), 'Content-Type': 'application/json' },
            body: JSON.stringify({ ruleset_id: rulesetId }),
            operation: 'Set active game system',
            fallbackMessage: 'Unable to set the active game system.',
        })
        applyGameSystems(payload.active_game_system, payload.available_game_systems, payload.active_bundle)
    }, [apiBase, applyGameSystems, authHeaders])

    const streamAsk = React.useCallback(async (question: string, history: ChatHistoryTurn[], onToken: (token: string) => void, onCitations?: (citations: ChatCitation[]) => void) => {
        if (!activeGameSystem?.id) {
            throw new ApiError('Choose a game system before chatting.', {
                status: 422,
                code: 'RULESET_REQUIRED',
            })
        }
        const rulesetId = activeGameSystem.id
        const url = `${apiBase}/ask/stream`
        const body = {
            q: question,
            ruleset_id: rulesetId,
            bundle_id: activeBundle?.id ?? null,
            history,
        }
        let response: Response
        try {
            response = await fetch(url, {
                method: 'POST',
                headers: { ...authHeaders(true), Accept: 'text/event-stream', 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
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
                        if (eventName === 'citations') {
                            try {
                                const payload = data ? JSON.parse(data) as { citations?: ChatCitation[] } : null
                                onCitations?.(Array.isArray(payload?.citations) ? payload.citations : [])
                            } catch {
                                onCitations?.([])
                            }
                        }
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
    }, [activeBundle?.id, activeGameSystem, apiBase, authHeaders, refreshSession])

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
        activeBundle,
        refreshSession,
        refreshGameSystems,
        login: (email, password) => authenticate('/auth/login', email, password),
        signup,
        logout: () => {
            storeToken('')
            setSessionError('')
            setSession((current) => current ? { authenticated: false, user: null, free_usage: current.free_usage } : null)
            setActiveBundleState(null)
        },
        updateProfile,
        changePassword,
        listFiles,
        uploadFile,
        deleteFile,
        saveFile,
        unsaveFile,
        getCopyrightStatus,
        submitCopyrightTakedown,
        submitCopyrightCounterNotice,
        listBundles,
        getBundle,
        createBundle,
        addFilesToBundle,
        removeFileFromBundle,
        deleteBundle,
        updateBundleTitle,
        saveBundle,
        unsaveBundle,
        setActiveBundle,
        streamAsk,
        searchTags,
        createTag,
        updateFileTags,
        updateFileTitle,
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
        activeBundle,
        refreshSession,
        refreshGameSystems,
        authenticate,
        signup,
        storeToken,
        updateProfile,
        changePassword,
        listFiles,
        uploadFile,
        deleteFile,
        saveFile,
        unsaveFile,
        getCopyrightStatus,
        submitCopyrightTakedown,
        submitCopyrightCounterNotice,
        listBundles,
        getBundle,
        createBundle,
        addFilesToBundle,
        removeFileFromBundle,
        deleteBundle,
        updateBundleTitle,
        saveBundle,
        unsaveBundle,
        setActiveBundle,
        streamAsk,
        searchTags,
        createTag,
        updateFileTags,
        updateFileTitle,
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

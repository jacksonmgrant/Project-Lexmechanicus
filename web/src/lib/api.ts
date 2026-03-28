export type ApiFieldError = {
    field: string
    message: string
}

type ApiErrorOptions = {
    status: number
    code?: string
    fields?: ApiFieldError[]
    detail?: unknown
}

export class ApiError extends Error {
    status: number
    code?: string
    fields: ApiFieldError[]
    detail?: unknown

    constructor(message: string, options: ApiErrorOptions) {
        super(message)
        this.name = 'ApiError'
        this.status = options.status
        this.code = options.code
        this.fields = options.fields || []
        this.detail = options.detail
    }
}

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null
}

function normalizeFields(value: unknown): ApiFieldError[] {
    if (!Array.isArray(value)) return []
    return value.flatMap((item) => {
        if (!isRecord(item) || typeof item.message !== 'string') return []
        return [{
            field: typeof item.field === 'string' ? item.field : 'request',
            message: item.message,
        }]
    })
}

function normalizeMessage(detail: unknown, fallbackMessage: string): { message: string, code?: string, fields: ApiFieldError[] } {
    if (typeof detail === 'string' && detail.trim()) {
        return { message: detail, fields: [] }
    }

    if (Array.isArray(detail)) {
        const firstIssue = detail.find((item) => isRecord(item) && typeof item.msg === 'string')
        if (firstIssue && isRecord(firstIssue) && typeof firstIssue.msg === 'string') {
            return { message: firstIssue.msg, fields: [] }
        }
    }

    if (isRecord(detail)) {
        const fields = normalizeFields(detail.fields)
        const message = typeof detail.message === 'string' && detail.message.trim()
            ? detail.message
            : (fields[0]?.message || fallbackMessage)
        return {
            message,
            code: typeof detail.code === 'string' ? detail.code : undefined,
            fields,
        }
    }

    return { message: fallbackMessage, fields: [] }
}

export function apiErrorFromPayload(payload: unknown, status: number, fallbackMessage: string): ApiError {
    const detail = isRecord(payload) && 'detail' in payload ? payload.detail : payload
    const normalized = normalizeMessage(detail, fallbackMessage)
    return new ApiError(normalized.message, {
        status,
        code: normalized.code,
        fields: normalized.fields,
        detail,
    })
}

export async function readResponsePayload(response: Response): Promise<unknown> {
    const raw = await response.text()
    if (!raw) return null
    try {
        return JSON.parse(raw) as unknown
    } catch {
        return raw
    }
}

export function logApiError(operation: string, error: unknown, extra?: Record<string, unknown>) {
    console.error(`[API] ${operation} failed`, {
        ...extra,
        error,
    })
}

type RequestJsonOptions = RequestInit & {
    operation: string
    fallbackMessage: string
}

export async function requestJson<T>(url: string, { operation, fallbackMessage, ...options }: RequestJsonOptions): Promise<T> {
    let response: Response

    try {
        response = await fetch(url, options)
    } catch (error) {
        const apiError = new ApiError('Unable to reach the server. Check your connection and try again.', {
            status: 0,
            code: 'NETWORK_ERROR',
            detail: error,
        })
        logApiError(operation, apiError, { url })
        throw apiError
    }

    const payload = await readResponsePayload(response)
    if (!response.ok) {
        const apiError = apiErrorFromPayload(payload, response.status, fallbackMessage)
        logApiError(operation, apiError, { url, status: response.status, payload })
        throw apiError
    }

    return payload as T
}

export async function requestVoid(url: string, options: RequestJsonOptions): Promise<void> {
    await requestJson<unknown>(url, options)
}

export function getErrorMessage(error: unknown, fallbackMessage: string): string {
    if (error instanceof ApiError) {
        return error.fields[0]?.message || error.message || fallbackMessage
    }
    if (error instanceof Error && error.message) {
        return error.message
    }
    return fallbackMessage
}

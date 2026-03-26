export function getStoredValue(key: string, fallback = '') {
    if (typeof window === 'undefined') return fallback
    return window.localStorage.getItem(key) || fallback
}

export function setStoredValue(key: string, value: string) {
    if (typeof window === 'undefined') return
    if (value) {
        window.localStorage.setItem(key, value)
        return
    }
    window.localStorage.removeItem(key)
}

export function getStoredNumber(key: string, fallback: number) {
    const raw = getStoredValue(key, String(fallback))
    const parsed = Number(raw)
    return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

export function setStoredNumber(key: string, value: number) {
    setStoredValue(key, String(value))
}

export function getOrCreateStoredValue(key: string, fallbackFactory: () => string) {
    const existing = getStoredValue(key)
    if (existing) return existing
    const created = fallbackFactory()
    setStoredValue(key, created)
    return created
}

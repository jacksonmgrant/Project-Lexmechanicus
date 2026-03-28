import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, Search } from 'lucide-react'
import { useAppContext, type Bundle } from '../context/AppContext'
import { getErrorMessage } from '../lib/api'

function matchesQuery(bundle: Bundle, query: string) {
    const normalizedQuery = query.trim().toLowerCase()
    if (!normalizedQuery) return true
    return [
        bundle.title,
        bundle.description || '',
        bundle.owner_name,
        ...bundle.preview_titles,
    ].join(' ').toLowerCase().includes(normalizedQuery)
}

export function ActiveBundleDropdown() {
    const { activeBundle, activeGameSystem, listBundles, session, setActiveBundle } = useAppContext()
    const [open, setOpen] = useState(false)
    const [query, setQuery] = useState('')
    const [bundles, setBundles] = useState<Bundle[]>([])
    const [error, setError] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const [isUpdating, setIsUpdating] = useState(false)
    const rootRef = useRef<HTMLDivElement | null>(null)
    const searchInputRef = useRef<HTMLInputElement | null>(null)

    useEffect(() => {
        if (!open) return
        const handlePointerDown = (event: MouseEvent) => {
            if (!rootRef.current?.contains(event.target as Node)) {
                setOpen(false)
            }
        }
        document.addEventListener('mousedown', handlePointerDown)
        return () => document.removeEventListener('mousedown', handlePointerDown)
    }, [open])

    useEffect(() => {
        if (!open) return
        const timeoutId = window.setTimeout(() => {
            searchInputRef.current?.focus()
            searchInputRef.current?.select()
        }, 0)
        return () => window.clearTimeout(timeoutId)
    }, [open])

    useEffect(() => {
        if (!session?.authenticated || !activeGameSystem?.id) {
            setBundles([])
            return
        }

        let cancelled = false
        setIsLoading(true)
        Promise.all([
            listBundles('mine', '', activeGameSystem.id),
            listBundles('saved', '', activeGameSystem.id),
        ])
            .then(([myBundles, savedBundles]) => {
                if (cancelled) return
                const merged = new Map<number, Bundle>()
                for (const bundle of [...myBundles, ...savedBundles]) {
                    merged.set(bundle.id, bundle)
                }
                if (activeBundle) {
                    merged.set(activeBundle.id, activeBundle)
                }
                setBundles(Array.from(merged.values()).sort((left, right) => left.title.localeCompare(right.title)))
                setError('')
            })
            .catch((err) => {
                if (cancelled) return
                setBundles(activeBundle ? [activeBundle] : [])
                setError(getErrorMessage(err, 'Unable to load bundles.'))
            })
            .finally(() => {
                if (!cancelled) setIsLoading(false)
            })

        return () => {
            cancelled = true
        }
    }, [activeBundle, activeGameSystem?.id, listBundles, session?.authenticated])

    const visibleBundles = useMemo(
        () => bundles.filter((bundle) => matchesQuery(bundle, query)),
        [bundles, query],
    )

    if (!session?.authenticated || !activeGameSystem?.id) {
        return null
    }

    const handleSelect = async (bundle: Bundle | null) => {
        try {
            setIsUpdating(true)
            await setActiveBundle(activeGameSystem.id, bundle?.id || null)
            setError('')
            setOpen(false)
            setQuery('')
        } catch (err) {
            setError(getErrorMessage(err, 'Unable to change the active bundle.'))
        } finally {
            setIsUpdating(false)
        }
    }

    return (
        <div ref={rootRef} className="active-bundle">
            <div className="dropdown dropdown--compact">
                <button
                    type="button"
                    className="tag-badge tag-badge--interactive tag-badge--bundle"
                    onClick={() => setOpen((current) => !current)}
                    aria-expanded={open}
                    title={activeBundle?.title || 'All files for this system'}
                    disabled={isUpdating}
                >
                    <span className="dropdown-trigger__label">{activeBundle?.title || 'All Files For System'}</span>
                    <ChevronDown className="dropdown-trigger__icon" size={14} />
                </button>

                {open && (
                    <div className="dropdown__menu dropdown__menu--left">
                        <div className="search-field search-field--compact">
                            <Search className="search-field__icon" size={16} />
                            <input
                                ref={searchInputRef}
                                className="text-input text-input--with-icon"
                                placeholder="Search bundles"
                                value={query}
                                onChange={(event) => setQuery(event.target.value)}
                                maxLength={120}
                            />
                        </div>

                        <div className={`dropdown__options${visibleBundles.length > 5 ? ' is-scrollable' : ''}`}>
                            <button
                                type="button"
                                className={`dropdown__option${activeBundle == null ? ' is-active' : ''}`}
                                onClick={() => void handleSelect(null)}
                            >
                                All Files For System
                            </button>
                            {visibleBundles.map((bundle) => (
                                <button
                                    key={bundle.id}
                                    type="button"
                                    className={`dropdown__option${activeBundle?.id === bundle.id ? ' is-active' : ''}`}
                                    onClick={() => void handleSelect(bundle)}
                                >
                                    {bundle.title}
                                </button>
                            ))}
                            {!visibleBundles.length && !isLoading && (
                                <div className="dropdown__empty">No bundles found for this system.</div>
                            )}
                        </div>

                        {error && (
                            <div className="notice notice--error" role="alert">
                                <p>{error}</p>
                            </div>
                        )}
                    </div>
                )}
            </div>
            {error && !open && <p className="active-bundle__error">{error}</p>}
        </div>
    )
}

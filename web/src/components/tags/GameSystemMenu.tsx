import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, Plus, Search } from 'lucide-react'
import { useAppContext, type Ruleset } from '../../context/AppContext'
import { getErrorMessage } from '../../lib/api'
import { useDebouncedValue } from '../../lib/useDebouncedValue'
import { GameSystemCreateModal } from './GameSystemCreateModal'

type GameSystemMenuProps = {
    selectedGameSystem: Ruleset | null
    onSelect: (ruleset: Ruleset) => Promise<void> | void
    allowCreate?: boolean
    searchAll?: boolean
    options?: Ruleset[]
    placeholder?: string
    align?: 'left' | 'right'
    className?: string
    compact?: boolean
}

function matchesQuery(ruleset: Ruleset, query: string) {
    return ruleset.name.toLowerCase().includes(query.trim().toLowerCase())
}

export function GameSystemMenu({
    selectedGameSystem,
    onSelect,
    allowCreate = false,
    searchAll = false,
    options,
    placeholder = 'Select a Game System',
    align = 'left',
    className = '',
    compact = false,
}: GameSystemMenuProps) {
    const { availableGameSystems, searchGameSystems } = useAppContext()
    const [open, setOpen] = useState(false)
    const [isCreateOpen, setIsCreateOpen] = useState(false)
    const [query, setQuery] = useState('')
    const debouncedQuery = useDebouncedValue(query, 300)
    const [results, setResults] = useState<Ruleset[]>(options || availableGameSystems)
    const [error, setError] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const rootRef = useRef<HTMLDivElement | null>(null)
    const searchInputRef = useRef<HTMLInputElement | null>(null)

    const sourceOptions = useMemo(
        () => [selectedGameSystem, ...(options || availableGameSystems)]
            .filter((ruleset): ruleset is Ruleset => !!ruleset)
            .filter((ruleset, index, array) => array.findIndex((item) => item.id === ruleset.id) === index),
        [availableGameSystems, options, selectedGameSystem],
    )
    const shouldShowSearch = allowCreate || sourceOptions.length > 5 || !!debouncedQuery.trim()

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
        if (!open || !shouldShowSearch) return
        const timeoutId = window.setTimeout(() => {
            searchInputRef.current?.focus()
            searchInputRef.current?.select()
        }, 0)
        return () => window.clearTimeout(timeoutId)
    }, [open, shouldShowSearch])

    useEffect(() => {
        if (!open) return
        const normalizedQuery = debouncedQuery.trim().toLowerCase()
        if (!normalizedQuery) {
            setResults(sourceOptions)
            setError('')
            setIsLoading(false)
            return
        }

        if (!searchAll) {
            setResults(sourceOptions.filter((ruleset) => matchesQuery(ruleset, debouncedQuery)))
            setError('')
            setIsLoading(false)
            return
        }

        let cancelled = false
        setIsLoading(true)
        searchGameSystems(debouncedQuery, 20)
            .then((rulesets) => {
                if (cancelled) return
                const merged = [...sourceOptions, ...rulesets].filter((ruleset, index, array) => array.findIndex((item) => item.id === ruleset.id) === index)
                setResults(merged.filter((ruleset) => matchesQuery(ruleset, debouncedQuery)))
                setError('')
            })
            .catch((err) => {
                if (cancelled) return
                setResults(sourceOptions.filter((ruleset) => matchesQuery(ruleset, debouncedQuery)))
                setError(getErrorMessage(err, 'Unable to load game systems.'))
            })
            .finally(() => {
                if (!cancelled) setIsLoading(false)
            })
        return () => {
            cancelled = true
        }
    }, [debouncedQuery, open, searchAll, searchGameSystems, sourceOptions])

    const handleSelect = async (ruleset: Ruleset) => {
        await onSelect(ruleset)
        setOpen(false)
        setQuery('')
    }

    return (
        <div ref={rootRef} className={`dropdown${compact ? ' dropdown--compact' : ''}`}>
            <button
                type="button"
                className={className || 'tag-badge tag-badge--game-system tag-badge--interactive'}
                onClick={() => setOpen((current) => !current)}
                aria-expanded={open}
                title={selectedGameSystem?.name || placeholder}
            >
                <span className="dropdown-trigger__label">{selectedGameSystem?.name || placeholder}</span>
                <ChevronDown className="dropdown-trigger__icon" size={14} />
            </button>

            {open && (
                <div className={`dropdown__menu dropdown__menu--${align}`}>
                    {shouldShowSearch && (
                        <div className="search-field search-field--compact">
                            <Search className="search-field__icon" size={16} />
                            <input
                                ref={searchInputRef}
                                className="text-input text-input--with-icon"
                                placeholder="Search systems"
                                value={query}
                                onChange={(event) => setQuery(event.target.value)}
                                maxLength={120}
                            />
                        </div>
                    )}

                    <div className={`dropdown__options${results.length > 5 ? ' is-scrollable' : ''}`}>
                        {results.map((ruleset) => (
                            <button
                                key={ruleset.id}
                                type="button"
                                className={`dropdown__option${selectedGameSystem?.id === ruleset.id ? ' is-active' : ''}`}
                                onClick={() => handleSelect(ruleset)}
                            >
                                {ruleset.name}
                            </button>
                        ))}
                        {!results.length && !isLoading && (
                            <div className="dropdown__empty">No game systems found.</div>
                        )}
                    </div>

                    {allowCreate && (
                        <div className="dropdown__footer">
                            <button
                                type="button"
                                className="secondary-button dropdown__create dropdown__create--small"
                                onClick={() => {
                                    setOpen(false)
                                    setIsCreateOpen(true)
                                }}
                            >
                                <Plus size={14} />
                                <span>New System</span>
                            </button>
                        </div>
                    )}

                    {error && (
                        <div className="notice notice--error" role="alert">
                            <p>{error}</p>
                        </div>
                    )}
                </div>
            )}

            <GameSystemCreateModal
                open={isCreateOpen}
                initialQuery={query.trim()}
                onClose={() => setIsCreateOpen(false)}
                onSelect={async (ruleset) => {
                    setError('')
                    await onSelect(ruleset)
                    setQuery('')
                }}
            />
        </div>
    )
}

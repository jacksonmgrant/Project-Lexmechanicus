import { useEffect, useState } from 'react'
import { X } from 'lucide-react'
import { useAppContext, type Ruleset } from '../../context/AppContext'
import { getErrorMessage } from '../../lib/api'
import { useDebouncedValue } from '../../lib/useDebouncedValue'

type GameSystemCreateModalProps = {
    open: boolean
    initialQuery?: string
    onClose: () => void
    onSelect: (ruleset: Ruleset) => Promise<void> | void
}

function normalizeText(value: string) {
    return value.trim().replace(/\s+/g, ' ')
}

function normalizeKey(value: string) {
    return normalizeText(value).toLowerCase()
}

export function GameSystemCreateModal({ open, initialQuery = '', onClose, onSelect }: GameSystemCreateModalProps) {
    const { createGameSystem, searchGameSystems } = useAppContext()
    const [name, setName] = useState(initialQuery)
    const [matches, setMatches] = useState<Ruleset[]>([])
    const [error, setError] = useState('')
    const [isSaving, setIsSaving] = useState(false)
    const [isLoadingMatches, setIsLoadingMatches] = useState(false)

    const canonicalName = normalizeText(name)
    const debouncedCanonicalName = useDebouncedValue(canonicalName, 300)

    useEffect(() => {
        if (!open) return
        setName(initialQuery)
        setMatches([])
        setError('')
        setIsSaving(false)
    }, [initialQuery, open])

    useEffect(() => {
        if (!open || !debouncedCanonicalName) {
            setMatches([])
            setIsLoadingMatches(false)
            return
        }
        let cancelled = false
        setIsLoadingMatches(true)
        searchGameSystems(debouncedCanonicalName, 8)
            .then((rulesets) => {
                if (cancelled) return
                setMatches(rulesets)
                setError('')
            })
            .catch((err) => {
                if (cancelled) return
                setMatches([])
                setError(getErrorMessage(err, 'Unable to load matching game systems.'))
            })
            .finally(() => {
                if (!cancelled) setIsLoadingMatches(false)
            })
        return () => {
            cancelled = true
        }
    }, [debouncedCanonicalName, open, searchGameSystems])

    if (!open) return null

    const exactDuplicate = !!canonicalName && matches.some((ruleset) => normalizeKey(ruleset.name) === normalizeKey(canonicalName))
    const canCreate = !!canonicalName && !exactDuplicate

    const handleCreate = async () => {
        if (!canCreate || isSaving) return
        setIsSaving(true)
        try {
            const created = await createGameSystem({ name: canonicalName })
            await onSelect(created)
            onClose()
        } catch (err) {
            setError(getErrorMessage(err, 'Unable to create that game system.'))
        } finally {
            setIsSaving(false)
        }
    }

    const handleUseExisting = async (ruleset: Ruleset) => {
        if (isSaving) return
        setIsSaving(true)
        try {
            await onSelect(ruleset)
            onClose()
        } catch (err) {
            setError(getErrorMessage(err, 'Unable to use that game system.'))
        } finally {
            setIsSaving(false)
        }
    }

    return (
        <div className="modal" role="dialog" aria-modal="true">
            <button className="modal__overlay" type="button" aria-label="Close game system creator" onClick={onClose} />
            <div className="modal__panel">
                <div className="modal__header">
                    <div>
                        <h2>Create Game System</h2>
                        <p>Each edition should be its own game system. Existing systems appear as you type so duplicates are easier to catch.</p>
                    </div>
                    <button className="icon-button icon-button--ghost" type="button" onClick={onClose} aria-label="Close game system creator">
                        <X size={18} />
                    </button>
                </div>

                <div className="field-group">
                    <label htmlFor="game-system-name">Game System Name</label>
                    <input
                        id="game-system-name"
                        className="text-input"
                        placeholder="Warhammer 40,000 10th Edition"
                        value={name}
                        onChange={(event) => setName(event.target.value)}
                        maxLength={160}
                    />
                </div>

                <div className="tag-section">
                    <span className="tag-section__label">Similar Existing Systems</span>
                    <div className="tag-picker-results">
                        {matches.map((ruleset) => (
                            <button
                                key={ruleset.id}
                                type="button"
                                className={`tag-picker-option${exactDuplicate && normalizeKey(ruleset.name) === normalizeKey(canonicalName) ? ' is-selected' : ''}`}
                                onClick={() => handleUseExisting(ruleset)}
                            >
                                <span>{ruleset.name}</span>
                                <span>Use Existing</span>
                            </button>
                        ))}
                        {!matches.length && !isLoadingMatches && (
                            <div className="tag-picker-empty">No close matches yet.</div>
                        )}
                    </div>
                </div>

                {exactDuplicate && (
                    <div className="notice notice--error" role="alert">
                        <p>An exact game system with that name already exists. Use the existing system instead of creating a duplicate.</p>
                    </div>
                )}

                {error && (
                    <div className="notice notice--error" role="alert">
                        <p>{error}</p>
                    </div>
                )}

                <div className="modal__footer">
                    <button type="button" className="secondary-button" onClick={onClose}>
                        Cancel
                    </button>
                    <button type="button" className="primary-button" onClick={handleCreate} disabled={!canCreate || isSaving}>
                        {isSaving ? 'Saving...' : 'Create Game System'}
                    </button>
                </div>
            </div>
        </div>
    )
}

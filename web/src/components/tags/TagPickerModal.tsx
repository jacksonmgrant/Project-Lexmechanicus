import { useEffect, useState } from 'react'
import { Plus, Search, X } from 'lucide-react'
import { useAppContext, type Tag } from '../../context/AppContext'
import { getErrorMessage } from '../../lib/api'
import { useDebouncedValue } from '../../lib/useDebouncedValue'

type TagPickerModalProps = {
    open: boolean
    title: string
    initialTags: Tag[]
    onClose: () => void
    onSave: (tags: Tag[]) => Promise<void> | void
}

function mergeUniqueTags(primary: Tag[], secondary: Tag[]) {
    const seen = new Set<number>()
    const merged: Tag[] = []
    for (const tag of [...primary, ...secondary]) {
        if (seen.has(tag.id)) continue
        merged.push(tag)
        seen.add(tag.id)
    }
    return merged
}

export function TagPickerModal({ open, title, initialTags, onClose, onSave }: TagPickerModalProps) {
    const { createTag, searchTags } = useAppContext()
    const [selectedTags, setSelectedTags] = useState<Tag[]>(initialTags)
    const [query, setQuery] = useState('')
    const debouncedQuery = useDebouncedValue(query, 300)
    const [results, setResults] = useState<Tag[]>([])
    const [error, setError] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const [isSaving, setIsSaving] = useState(false)
    const [isCreating, setIsCreating] = useState(false)

    useEffect(() => {
        if (!open) return
        setSelectedTags(initialTags)
        setQuery('')
        setError('')
    }, [initialTags, open])

    useEffect(() => {
        if (!open) return
        let cancelled = false
        setIsLoading(true)
        searchTags(debouncedQuery, 20)
            .then((tags) => {
                if (cancelled) return
                setResults(tags)
                setError('')
            })
            .catch((err) => {
                if (cancelled) return
                setResults([])
                setError(getErrorMessage(err, 'Unable to load tags.'))
            })
            .finally(() => {
                if (!cancelled) setIsLoading(false)
            })
        return () => {
            cancelled = true
        }
    }, [debouncedQuery, open, searchTags])

    if (!open) return null

    const normalizedQuery = query.trim().toLowerCase()
    const allVisibleTags = mergeUniqueTags(selectedTags, results)
    const exactMatch = allVisibleTags.some((tag) => tag.name.toLowerCase() === normalizedQuery)

    const toggleTag = (tag: Tag) => {
        setSelectedTags((current) => current.some((item) => item.id === tag.id)
            ? current.filter((item) => item.id !== tag.id)
            : [...current, tag])
    }

    const handleCreate = async () => {
        const nextName = query.trim()
        if (!nextName || isCreating) return
        setIsCreating(true)
        try {
            const tag = await createTag(nextName)
            setSelectedTags((current) => current.some((item) => item.id === tag.id) ? current : [...current, tag])
            setResults((current) => mergeUniqueTags([tag], current))
            setQuery('')
            setError('')
        } catch (err) {
            setError(getErrorMessage(err, 'Unable to create that tag.'))
        } finally {
            setIsCreating(false)
        }
    }

    const handleSave = async () => {
        if (isSaving) return
        setIsSaving(true)
        try {
            await onSave(selectedTags)
            onClose()
        } catch (err) {
            setError(getErrorMessage(err, 'Unable to save tags.'))
        } finally {
            setIsSaving(false)
        }
    }

    return (
        <div className="modal" role="dialog" aria-modal="true">
            <button className="modal__overlay" type="button" aria-label="Close tag picker" onClick={onClose} />
            <div className="modal__panel">
                <div className="modal__header">
                    <div>
                        <h2>{title}</h2>
                        <p>Select existing tags or create a new one.</p>
                    </div>
                    <button className="icon-button icon-button--ghost" type="button" onClick={onClose} aria-label="Close tag picker">
                        <X size={18} />
                    </button>
                </div>

                <div className="search-field search-field--compact">
                    <Search className="search-field__icon" size={18} />
                    <input
                        className="text-input text-input--with-icon"
                        placeholder="Search tags"
                        value={query}
                        onChange={(event) => setQuery(event.target.value)}
                        maxLength={120}
                    />
                </div>

                {selectedTags.length > 0 && (
                    <div className="tag-section">
                        <span className="tag-section__label">Selected</span>
                        <div className="tag-list">
                            {selectedTags.map((tag) => (
                                <button key={tag.id} type="button" className="tag-badge tag-badge--interactive tag-badge--selected" onClick={() => toggleTag(tag)}>
                                    {tag.name}
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                <div className="tag-section">
                    <span className="tag-section__label">Suggestions</span>
                    <div className="tag-picker-results">
                        {allVisibleTags.map((tag) => {
                            const isSelected = selectedTags.some((item) => item.id === tag.id)
                            return (
                                <button
                                    key={tag.id}
                                    type="button"
                                    className={`tag-picker-option${isSelected ? ' is-selected' : ''}`}
                                    onClick={() => toggleTag(tag)}
                                >
                                    <span>{tag.name}</span>
                                    {isSelected && <span>Selected</span>}
                                </button>
                            )
                        })}
                        {!allVisibleTags.length && !isLoading && (
                            <div className="tag-picker-empty">No matching tags yet.</div>
                        )}
                    </div>
                </div>

                {!!normalizedQuery && !exactMatch && (
                    <button type="button" className="secondary-button tag-create-button" onClick={handleCreate} disabled={isCreating}>
                        <Plus size={16} />
                        <span>{isCreating ? 'Creating...' : `Create "${query.trim()}"`}</span>
                    </button>
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
                    <button type="button" className="primary-button" onClick={handleSave} disabled={isSaving}>
                        {isSaving ? 'Saving...' : 'Save Tags'}
                    </button>
                </div>
            </div>
        </div>
    )
}

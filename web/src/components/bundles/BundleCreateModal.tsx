import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, X } from 'lucide-react'
import { type ListedFile, type Ruleset } from '../../context/AppContext'
import { getErrorMessage } from '../../lib/api'
import { GameSystemMenu } from '../tags/GameSystemMenu'

type BundleCreateModalProps = {
    open: boolean
    availableFiles: ListedFile[]
    editableFileIds: number[]
    defaultRuleset: Ruleset | null
    onRenameFile: (fileId: number, title: string) => Promise<void> | void
    onClose: () => void
    onSave: (input: {
        title: string
        description: string
        fileIds: number[]
        isPublic: boolean
        rulesetId: number
        publicDistributionConfirmed: boolean
    }) => Promise<void> | void
}

const ALL_SYSTEMS_SLUG = 'all-systems'

export function BundleCreateModal({ open, availableFiles, editableFileIds, defaultRuleset, onRenameFile, onClose, onSave }: BundleCreateModalProps) {
    const [title, setTitle] = useState('')
    const [description, setDescription] = useState('')
    const [query, setQuery] = useState('')
    const [selectedFileIds, setSelectedFileIds] = useState<number[]>([])
    const [draftTitles, setDraftTitles] = useState<Record<number, string>>({})
    const [selectedRuleset, setSelectedRuleset] = useState<Ruleset | null>(defaultRuleset)
    const [isPublic, setIsPublic] = useState(false)
    const [publicDistributionConfirmed, setPublicDistributionConfirmed] = useState(false)
    const [error, setError] = useState('')
    const [isSaving, setIsSaving] = useState(false)
    const editableFileIdSet = useMemo(() => new Set(editableFileIds), [editableFileIds])

    useEffect(() => {
        if (!open) return
        setTitle('')
        setDescription('')
        setQuery('')
        setSelectedFileIds([])
        setDraftTitles(Object.fromEntries(availableFiles.map((file) => [file.id, file.title])))
        setSelectedRuleset(defaultRuleset)
        setIsPublic(false)
        setPublicDistributionConfirmed(false)
        setError('')
    }, [defaultRuleset, open])

    useEffect(() => {
        if (!open) return
        setDraftTitles((current) => {
            const next: Record<number, string> = {}
            for (const file of availableFiles) {
                next[file.id] = current[file.id] ?? file.title
            }
            return next
        })
    }, [availableFiles, open])

    const selectedRulesetIsAllSystems = selectedRuleset?.slug === ALL_SYSTEMS_SLUG

    const rulesetFiles = useMemo(() => {
        if (!selectedRuleset?.id || selectedRulesetIsAllSystems) return []
        return availableFiles.filter((file) => file.game_system_id === selectedRuleset.id)
    }, [availableFiles, selectedRuleset?.id, selectedRulesetIsAllSystems])

    const visibleFiles = useMemo(() => {
        const normalizedQuery = query.trim().toLowerCase()
        if (!normalizedQuery) return rulesetFiles
        return rulesetFiles.filter((file) => {
            const haystack = [
                draftTitles[file.id] || file.title,
                file.description || '',
                file.filename,
                file.uploader_name,
                ...file.tags.map((tag) => tag.name),
            ].join(' ').toLowerCase()
            return haystack.includes(normalizedQuery)
        })
    }, [draftTitles, query, rulesetFiles])

    const updateDraftTitle = (fileId: number, nextTitle: string) => {
        setDraftTitles((current) => ({ ...current, [fileId]: nextTitle }))
    }

    if (!open) return null

    const toggleFile = (fileId: number) => {
        setSelectedFileIds((current) => current.includes(fileId)
            ? current.filter((id) => id !== fileId)
            : [...current, fileId])
    }

    const handleSave = async () => {
        if (isSaving) return
        if (!selectedRuleset) {
            setError('Choose a game system for this bundle.')
            return
        }
        if (selectedRulesetIsAllSystems) {
            setError('Bundles cannot be created for All Systems. Choose a specific game system.')
            return
        }
        if (isPublic && !publicDistributionConfirmed) {
            setError('Confirm that you have the right to distribute every file before making the bundle public.')
            return
        }

        for (const fileId of selectedFileIds) {
            if (!editableFileIdSet.has(fileId)) continue
            const normalizedTitle = (draftTitles[fileId] || '').trim()
            if (!normalizedTitle) {
                setError('Each selected document needs a title.')
                return
            }
            if (normalizedTitle.length > 120) {
                setError('Keep each document title under 120 characters.')
                return
            }
        }

        setIsSaving(true)
        try {
            for (const fileId of selectedFileIds) {
                if (!editableFileIdSet.has(fileId)) continue
                const file = availableFiles.find((item) => item.id === fileId)
                const normalizedTitle = (draftTitles[fileId] || '').trim()
                if (!file || normalizedTitle === file.title) continue
                await onRenameFile(fileId, normalizedTitle)
            }

            await onSave({
                title: title.trim(),
                description: description.trim(),
                fileIds: selectedFileIds,
                isPublic,
                rulesetId: selectedRuleset.id,
                publicDistributionConfirmed,
            })
            onClose()
        } catch (err) {
            setError(getErrorMessage(err, 'Unable to create the bundle.'))
        } finally {
            setIsSaving(false)
        }
    }

    return (
        <div className="modal" role="dialog" aria-modal="true">
            <button className="modal__overlay" type="button" aria-label="Close bundle creator" onClick={onClose} />
            <div className="modal__panel">
                <div className="modal__header">
                    <div>
                        <h2>Create Bundle</h2>
                        <p>Build a reusable file set for one specific game system.</p>
                    </div>
                    <button className="icon-button icon-button--ghost" type="button" onClick={onClose} aria-label="Close bundle creator">
                        <X size={18} />
                    </button>
                </div>

                <div className="form-stack">
                    <div className="field-group">
                        <label>Game system</label>
                        <GameSystemMenu
                            selectedGameSystem={selectedRuleset}
                            allowCreate
                            searchAll
                            onSelect={(ruleset) => {
                                setSelectedRuleset(ruleset)
                                setSelectedFileIds([])
                                setError('')
                            }}
                            placeholder="Select a game system"
                        />
                    </div>

                    <div className="field-group">
                        <label htmlFor="bundle-title">Bundle title</label>
                        <input
                            id="bundle-title"
                            className="text-input"
                            value={title}
                            onChange={(event) => setTitle(event.target.value)}
                            placeholder="40k Core Rules"
                            maxLength={160}
                        />
                    </div>

                    <div className="field-group">
                        <label htmlFor="bundle-description">Description</label>
                        <textarea
                            id="bundle-description"
                            className="text-area"
                            value={description}
                            onChange={(event) => setDescription(event.target.value)}
                            placeholder="Core books and references I use for standard games."
                            maxLength={1000}
                        />
                    </div>

                    <label className="toggle-row" htmlFor="bundle-public">
                        <div>
                            <p className="toggle-row__title">Public bundle</p>
                            <p className="toggle-row__description">Public bundles can be discovered and saved by other users.</p>
                        </div>
                        <input
                            id="bundle-public"
                            className="checkbox-input"
                            type="checkbox"
                            checked={isPublic}
                            onChange={(event) => {
                                setIsPublic(event.target.checked)
                                if (!event.target.checked) {
                                    setPublicDistributionConfirmed(false)
                                }
                            }}
                        />
                    </label>

                    <div className="notice" role="note">
                        <p>Only make a bundle public if you have the right to publish every file inside it. See the <Link className="inline-link" to="/legal/terms">Terms</Link> and <Link className="inline-link" to="/legal/copyright">Copyright Policy</Link>.</p>
                    </div>

                    {isPublic && (
                        <div className="notice notice--error" role="alert">
                            <p>Public bundles are discoverable by other users and are subject to DMCA takedown and repeat-infringer enforcement.</p>
                        </div>
                    )}

                    {isPublic && (
                        <label className="checkbox-row" htmlFor="bundle-public-confirmed">
                            <input
                                id="bundle-public-confirmed"
                                className="checkbox-input"
                                type="checkbox"
                                checked={publicDistributionConfirmed}
                                onChange={(event) => setPublicDistributionConfirmed(event.target.checked)}
                            />
                            <span>I have the legal right to distribute every file in this public bundle.</span>
                        </label>
                    )}

                    <div className="search-field search-field--compact">
                        <Search className="search-field__icon" size={18} />
                        <input
                            className="text-input text-input--with-icon"
                            placeholder="Search files to include"
                            value={query}
                            onChange={(event) => setQuery(event.target.value)}
                            maxLength={200}
                        />
                    </div>

                    <div className="bundle-picker">
                        {visibleFiles.map((file) => {
                            const isSelected = selectedFileIds.includes(file.id)
                            const isEditable = editableFileIdSet.has(file.id)
                            return (
                                <div
                                    key={file.id}
                                    className={`bundle-picker__option${isSelected ? ' is-selected' : ''}`}
                                >
                                    <button
                                        type="button"
                                        className="bundle-picker__toggle"
                                        onClick={() => toggleFile(file.id)}
                                    >
                                        <div className="bundle-picker__body">
                                            <strong>{draftTitles[file.id] || file.title}</strong>
                                            <span>{file.filename}</span>
                                            <span>{file.uploader_name}</span>
                                        </div>
                                        <span>{isSelected ? 'Selected' : 'Add'}</span>
                                    </button>
                                    {isEditable && isSelected && (
                                        <div className="bundle-picker__editor">
                                            <label htmlFor={`bundle-file-title-${file.id}`}>Document title</label>
                                            <input
                                                id={`bundle-file-title-${file.id}`}
                                                className="text-input"
                                                value={draftTitles[file.id] || ''}
                                                onChange={(event) => updateDraftTitle(file.id, event.target.value)}
                                                maxLength={120}
                                            />
                                        </div>
                                    )}
                                </div>
                            )
                        })}
                        {!visibleFiles.length && (
                            <div className="bundle-picker__empty">
                                {selectedRulesetIsAllSystems
                                    ? 'Choose a specific game system to add files.'
                                    : rulesetFiles.length
                                        ? 'No files match that search.'
                                        : 'Save or upload files in this game system first.'}
                            </div>
                        )}
                    </div>

                    <p className="field-help">{selectedFileIds.length} file{selectedFileIds.length === 1 ? '' : 's'} selected.</p>
                </div>

                {selectedRulesetIsAllSystems && (
                    <div className="notice notice--error" role="alert">
                        <p>Bundles cannot be created for All Systems. Choose a specific game system.</p>
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
                    <button
                        type="button"
                        className="primary-button"
                        onClick={handleSave}
                        disabled={isSaving || !selectedRuleset || selectedRulesetIsAllSystems || !title.trim() || selectedFileIds.length === 0}
                    >
                        {isSaving ? 'Creating...' : 'Create Bundle'}
                    </button>
                </div>
            </div>
        </div>
    )
}

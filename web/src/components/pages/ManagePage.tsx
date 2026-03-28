import { useEffect, useMemo, useState } from 'react'
import { Check, Download, FileText, Layers, Pencil, Plus, Star, Trash2, Upload as UploadIcon, X } from 'lucide-react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAppContext, type Bundle, type ListedFile, type Ruleset, type Tag } from '../../context/AppContext'
import { getErrorMessage } from '../../lib/api'
import { BundleCreateModal } from '../bundles/BundleCreateModal'
import { GameSystemMenu } from '../tags/GameSystemMenu'
import { TagPickerModal } from '../tags/TagPickerModal'

type TabValue = 'uploaded' | 'saved' | 'bundles'

export function ManagePage() {
    const {
        activeBundle,
        activeGameSystem,
        apiBase,
        availableGameSystems,
        createBundle,
        deleteBundle,
        deleteFile,
        listBundles,
        listFiles,
        session,
        setActiveBundle,
        unsaveBundle,
        unsaveFile,
        updateBundleTitle,
        updateFileGameSystem,
        updateFileTitle,
        updateFileTags,
    } = useAppContext()
    const location = useLocation()
    const navigate = useNavigate()
    const [activeTab, setActiveTab] = useState<TabValue>('uploaded')
    const [uploaded, setUploaded] = useState<ListedFile[]>([])
    const [saved, setSaved] = useState<ListedFile[]>([])
    const [myBundles, setMyBundles] = useState<Bundle[]>([])
    const [savedBundles, setSavedBundles] = useState<Bundle[]>([])
    const [editingTagsForFile, setEditingTagsForFile] = useState<ListedFile | null>(null)
    const [creatingBundle, setCreatingBundle] = useState(false)
    const [activatingBundleId, setActivatingBundleId] = useState<number | null>(null)
    const [editingFileTitleId, setEditingFileTitleId] = useState<number | null>(null)
    const [draftFileTitle, setDraftFileTitle] = useState('')
    const [savingFileTitleId, setSavingFileTitleId] = useState<number | null>(null)
    const [editingBundleTitleId, setEditingBundleTitleId] = useState<number | null>(null)
    const [draftBundleTitle, setDraftBundleTitle] = useState('')
    const [savingBundleTitleId, setSavingBundleTitleId] = useState<number | null>(null)
    const [error, setError] = useState('')
    const [successMessage, setSuccessMessage] = useState('')

    useEffect(() => {
        const nextMessage = typeof location.state === 'object' && location.state && 'successMessage' in location.state
            ? location.state.successMessage
            : ''
        if (typeof nextMessage === 'string' && nextMessage) {
            setSuccessMessage(nextMessage)
            navigate(location.pathname, { replace: true, state: null })
        }
    }, [location.pathname, location.state, navigate])

    useEffect(() => {
        if (!session?.authenticated) {
            setUploaded([])
            setSaved([])
            setMyBundles([])
            setSavedBundles([])
            return
        }

        listFiles('mine')
            .then((files) => {
                setUploaded(files)
                setError('')
            })
            .catch((err) => {
                setUploaded([])
                setError(getErrorMessage(err, 'Unable to load your uploads.'))
            })
    }, [listFiles, session])

    useEffect(() => {
        if (!session?.authenticated) {
            setSaved([])
            return
        }

        listFiles('saved')
            .then((files) => {
                setSaved(files)
                setError('')
            })
            .catch((err) => {
                setSaved([])
                setError(getErrorMessage(err, 'Unable to load your saved files.'))
            })
    }, [listFiles, session])

    useEffect(() => {
        if (!session?.authenticated) {
            setMyBundles([])
            setSavedBundles([])
            return
        }

        listBundles('mine')
            .then((bundles) => {
                setMyBundles(bundles)
                setError('')
            })
            .catch((err) => {
                setMyBundles([])
                setError(getErrorMessage(err, 'Unable to load your bundles.'))
            })

        listBundles('saved')
            .then((bundles) => {
                setSavedBundles(bundles)
                setError('')
            })
            .catch((err) => {
                setSavedBundles([])
                setError(getErrorMessage(err, 'Unable to load saved bundles.'))
            })
    }, [listBundles, session])

    const totalStorage = useMemo(() => uploaded.reduce((sum, file) => sum + file.size_bytes, 0), [uploaded])

    const bundleSourceFiles = useMemo(() => {
        const merged = new Map<number, ListedFile>()
        for (const file of [...uploaded, ...saved]) {
            merged.set(file.id, file)
        }
        return Array.from(merged.values()).sort((left, right) => left.title.localeCompare(right.title))
    }, [saved, uploaded])

    const replaceFile = (fileId: number, updater: (file: ListedFile) => ListedFile) => {
        setUploaded((current) => current.map((file) => file.id === fileId ? updater(file) : file))
    }

    const replaceAnyFile = (fileId: number, updater: (file: ListedFile) => ListedFile) => {
        setUploaded((current) => current.map((file) => file.id === fileId ? updater(file) : file))
        setSaved((current) => current.map((file) => file.id === fileId ? updater(file) : file))
    }

    const handleDelete = async (id: number) => {
        try {
            await deleteFile(id)
            setUploaded((prev) => prev.filter((file) => file.id !== id))
            setError('')
        } catch (err) {
            setError(getErrorMessage(err, 'Unable to delete that file.'))
        }
    }

    const handleGameSystemChange = async (fileId: number, ruleset: Ruleset) => {
        try {
            const updatedGameSystem = await updateFileGameSystem(fileId, ruleset.id)
            replaceFile(fileId, (file) => ({ ...file, game_system: updatedGameSystem, game_system_id: updatedGameSystem.id }))
            setError('')
        } catch (err) {
            setError(getErrorMessage(err, 'Unable to update the game system.'))
        }
    }

    const handleTagSave = async (fileId: number, tags: Tag[]) => {
        const updatedTags = await updateFileTags(fileId, tags.map((tag) => tag.id))
        replaceFile(fileId, (file) => ({ ...file, tags: updatedTags }))
        setEditingTagsForFile(null)
        setError('')
    }

    const handleUnsave = async (fileId: number) => {
        try {
            await unsaveFile(fileId)
            setSaved((current) => current.filter((file) => file.id !== fileId))
            setError('')
        } catch (err) {
            setError(getErrorMessage(err, 'Unable to remove that saved file.'))
        }
    }

    const handleRenameFile = async (fileId: number, nextTitle: string) => {
        const title = await updateFileTitle(fileId, nextTitle)
        replaceAnyFile(fileId, (file) => ({ ...file, title }))
        setError('')
    }

    const replaceAnyBundle = (bundleId: number, updater: (bundle: Bundle) => Bundle) => {
        setMyBundles((current) => current.map((bundle) => bundle.id === bundleId ? updater(bundle) : bundle))
        setSavedBundles((current) => current.map((bundle) => bundle.id === bundleId ? updater(bundle) : bundle))
    }

    const startEditingFileTitle = (file: ListedFile) => {
        setEditingFileTitleId(file.id)
        setDraftFileTitle(file.title)
        setError('')
    }

    const cancelEditingFileTitle = () => {
        setEditingFileTitleId(null)
        setDraftFileTitle('')
    }

    const saveFileTitle = async (file: ListedFile) => {
        const normalizedTitle = draftFileTitle.trim()
        if (!normalizedTitle) {
            setError('Enter a file title before saving.')
            return
        }
        if (normalizedTitle.length > 120) {
            setError('Keep the file title under 120 characters.')
            return
        }
        if (normalizedTitle === file.title) {
            cancelEditingFileTitle()
            return
        }
        try {
            setSavingFileTitleId(file.id)
            await handleRenameFile(file.id, normalizedTitle)
            setSuccessMessage('File title updated.')
            cancelEditingFileTitle()
        } catch (err) {
            setError(getErrorMessage(err, 'Unable to update the file title.'))
        } finally {
            setSavingFileTitleId(null)
        }
    }

    const startEditingBundleTitle = (bundle: Bundle) => {
        setEditingBundleTitleId(bundle.id)
        setDraftBundleTitle(bundle.title)
        setError('')
    }

    const cancelEditingBundleTitle = () => {
        setEditingBundleTitleId(null)
        setDraftBundleTitle('')
    }

    const saveBundleTitle = async (bundle: Bundle) => {
        const normalizedTitle = draftBundleTitle.trim()
        if (!normalizedTitle) {
            setError('Enter a bundle title before saving.')
            return
        }
        if (normalizedTitle.length > 160) {
            setError('Keep the bundle title under 160 characters.')
            return
        }
        if (normalizedTitle === bundle.title) {
            cancelEditingBundleTitle()
            return
        }
        try {
            setSavingBundleTitleId(bundle.id)
            const title = await updateBundleTitle(bundle.id, normalizedTitle)
            replaceAnyBundle(bundle.id, (item) => ({ ...item, title }))
            setSuccessMessage('Bundle title updated.')
            setError('')
            cancelEditingBundleTitle()
        } catch (err) {
            setError(getErrorMessage(err, 'Unable to update the bundle title.'))
        } finally {
            setSavingBundleTitleId(null)
        }
    }

    const handleCreateBundle = async (input: { title: string, description: string, fileIds: number[], isPublic: boolean, rulesetId: number }) => {
        const bundle = await createBundle({
            title: input.title,
            description: input.description,
            fileIds: input.fileIds,
            isPublic: input.isPublic,
            rulesetId: input.rulesetId,
        })
        setMyBundles((current) => [bundle, ...current])
        setSuccessMessage(`Created bundle "${bundle.title}".`)
        setError('')
    }

    const handleDeleteBundle = async (bundleId: number) => {
        try {
            await deleteBundle(bundleId)
            setMyBundles((current) => current.filter((bundle) => bundle.id !== bundleId))
            setSavedBundles((current) => current.filter((bundle) => bundle.id !== bundleId))
            setSuccessMessage('Bundle deleted.')
            setError('')
        } catch (err) {
            setError(getErrorMessage(err, 'Unable to delete that bundle.'))
        }
    }

    const handleUnsaveBundle = async (bundleId: number) => {
        try {
            await unsaveBundle(bundleId)
            setSavedBundles((current) => current.filter((bundle) => bundle.id !== bundleId))
            setError('')
        } catch (err) {
            setError(getErrorMessage(err, 'Unable to remove that saved bundle.'))
        }
    }

    const handleActivateBundle = async (bundle: Bundle | null) => {
        if (!activeGameSystem?.id) return
        try {
            setActivatingBundleId(bundle?.id || 0)
            await setActiveBundle(activeGameSystem.id, bundle?.id || null)
            setMyBundles((current) => current.map((item) => ({ ...item, is_default: bundle?.id === item.id })))
            setSavedBundles((current) => current.map((item) => ({ ...item, is_default: bundle?.id === item.id })))
            setSuccessMessage(bundle ? `Using "${bundle.title}" in chat.` : 'Chat bundle cleared for this game system.')
            setError('')
        } catch (err) {
            setError(getErrorMessage(err, 'Unable to update the active bundle.'))
        } finally {
            setActivatingBundleId(null)
        }
    }

    const renderEditableTitle = ({
        value,
        draftValue,
        isEditing,
        isSaving,
        inputId,
        onDraftChange,
        onStartEdit,
        onCancelEdit,
        onSave,
        editLabel,
    }: {
        value: string
        draftValue: string
        isEditing: boolean
        isSaving: boolean
        inputId: string
        onDraftChange: (value: string) => void
        onStartEdit: () => void
        onCancelEdit: () => void
        onSave: () => void
        editLabel: string
    }) => (
        <div className="editable-title">
            {isEditing ? (
                <>
                    <input
                        id={inputId}
                        className="text-input editable-title__input"
                        value={draftValue}
                        onChange={(event) => onDraftChange(event.target.value)}
                        onKeyDown={(event) => {
                            if (event.key === 'Enter') {
                                event.preventDefault()
                                onSave()
                            }
                            if (event.key === 'Escape') {
                                event.preventDefault()
                                onCancelEdit()
                            }
                        }}
                        autoFocus
                    />
                    <div className="editable-title__actions">
                        <button
                            type="button"
                            className="icon-button icon-button--ghost"
                            onClick={onSave}
                            disabled={isSaving}
                            aria-label={`Save ${editLabel}`}
                        >
                            <Check size={16} />
                        </button>
                        <button
                            type="button"
                            className="icon-button icon-button--ghost"
                            onClick={onCancelEdit}
                            disabled={isSaving}
                            aria-label={`Cancel editing ${editLabel}`}
                        >
                            <X size={16} />
                        </button>
                    </div>
                </>
            ) : (
                <>
                    <h3>{value}</h3>
                    <button
                        type="button"
                        className="icon-button icon-button--ghost"
                        onClick={onStartEdit}
                        aria-label={`Edit ${editLabel}`}
                    >
                        <Pencil size={16} />
                    </button>
                </>
            )}
        </div>
    )

    const renderBundleCard = (bundle: Bundle, canDelete: boolean) => (
        <article key={bundle.id} className="surface-card manage-card">
            <div className="manage-card__icon">
                <Layers size={32} />
            </div>
            <div className="manage-card__main">
                <div className="manage-card__header">
                    <div>
                        {canDelete ? renderEditableTitle({
                            value: bundle.title,
                            draftValue: editingBundleTitleId === bundle.id ? draftBundleTitle : bundle.title,
                            isEditing: editingBundleTitleId === bundle.id,
                            isSaving: savingBundleTitleId === bundle.id,
                            inputId: `bundle-title-${bundle.id}`,
                            onDraftChange: setDraftBundleTitle,
                            onStartEdit: () => startEditingBundleTitle(bundle),
                            onCancelEdit: cancelEditingBundleTitle,
                            onSave: () => void saveBundleTitle(bundle),
                            editLabel: `bundle title for ${bundle.title}`,
                        }) : <h3>{bundle.title}</h3>}
                        <p className="body-muted">{bundle.owner_name}</p>
                    </div>
                    <div className="button-row">
                        <button
                            type="button"
                            className={bundle.is_default ? 'secondary-button' : 'primary-button'}
                            onClick={() => void handleActivateBundle(bundle)}
                            disabled={activatingBundleId === bundle.id || bundle.is_default}
                        >
                            {bundle.is_default ? 'Using in Chat' : 'Use in Chat'}
                        </button>
                        {canDelete && (
                            <Link className="secondary-button" to={`/manage/bundles/${bundle.id}`}>
                                Edit Bundle
                            </Link>
                        )}
                        {!canDelete && (
                            <button
                                type="button"
                                className="secondary-button"
                                onClick={() => void handleUnsaveBundle(bundle.id)}
                            >
                                Remove Saved
                            </button>
                        )}
                        {canDelete && (
                            <button
                                type="button"
                                className="icon-button icon-button--ghost icon-button--danger"
                                onClick={() => void handleDeleteBundle(bundle.id)}
                                aria-label={`Delete ${bundle.title}`}
                            >
                                <Trash2 size={16} />
                            </button>
                        )}
                    </div>
                </div>

                {bundle.description && (
                    <p className="manage-card__description">{bundle.description}</p>
                )}

                <div className="tag-list">
                    {bundle.game_system && (
                        <span className="tag-badge tag-badge--game-system">{bundle.game_system.name}</span>
                    )}
                    <span className="tag-badge">{bundle.file_count} file{bundle.file_count === 1 ? '' : 's'}</span>
                    <span className="tag-badge">{bundle.is_public ? 'Public' : 'Private'}</span>
                    {bundle.is_default && <span className="tag-badge tag-badge--selected">Active in Chat</span>}
                </div>

                {!!bundle.preview_titles.length && (
                    <p className="bundle-preview">
                        Includes: {bundle.preview_titles.join(', ')}
                    </p>
                )}
            </div>
        </article>
    )

    return (
        <div className="page-scroll">
            <div className="page-container page-container--wide">
                <div className="page-header page-header--with-actions">
                    <div>
                        <h1>Manage Files</h1>
                        <p>View your uploads, curate saved material, and assemble reusable bundles for each game system.</p>
                    </div>
                    <Link className="primary-button primary-button--inline" to="/upload">Upload Files</Link>
                </div>

                <div className="tabs">
                    <div className="tabs__list tabs__list--triple">
                        <button type="button" className={`tabs__trigger${activeTab === 'uploaded' ? ' is-active' : ''}`} onClick={() => setActiveTab('uploaded')}>
                            My Uploads
                        </button>
                        <button type="button" className={`tabs__trigger${activeTab === 'saved' ? ' is-active' : ''}`} onClick={() => setActiveTab('saved')}>
                            Saved Files
                        </button>
                        <button type="button" className={`tabs__trigger${activeTab === 'bundles' ? ' is-active' : ''}`} onClick={() => setActiveTab('bundles')}>
                            Bundles
                        </button>
                    </div>

                    {activeTab === 'uploaded' && (
                        <div className="page-section-stack">
                            {!session?.authenticated ? (
                                <div className="surface-card empty-card">
                                    <UploadIcon className="muted-icon" size={48} />
                                    <p className="empty-card__text">Sign in to manage your uploaded files</p>
                                    <Link className="primary-button primary-button--inline" to="/account">Open Account</Link>
                                </div>
                            ) : uploaded.length === 0 ? (
                                <div className="surface-card empty-card">
                                    <UploadIcon className="muted-icon" size={48} />
                                    <p className="empty-card__text">No uploaded files yet</p>
                                    <Link className="primary-button primary-button--inline" to="/upload">Upload Your First File</Link>
                                </div>
                            ) : (
                                uploaded.map((file) => (
                                    <article key={file.id} className="surface-card manage-card">
                                        <div className="manage-card__icon">
                                            <FileText size={32} />
                                        </div>
                                        <div className="manage-card__main">
                                            <div className="manage-card__header">
                                                <div>
                                                    {renderEditableTitle({
                                                        value: file.title,
                                                        draftValue: editingFileTitleId === file.id ? draftFileTitle : file.title,
                                                        isEditing: editingFileTitleId === file.id,
                                                        isSaving: savingFileTitleId === file.id,
                                                        inputId: `file-title-${file.id}`,
                                                        onDraftChange: setDraftFileTitle,
                                                        onStartEdit: () => startEditingFileTitle(file),
                                                        onCancelEdit: cancelEditingFileTitle,
                                                        onSave: () => void saveFileTitle(file),
                                                        editLabel: `file title for ${file.title}`,
                                                    })}
                                                    <p className="body-muted">{file.filename}</p>
                                                </div>
                                                <div className="icon-action-row">
                                                    <a className="icon-button icon-button--ghost" href={`${apiBase}/viewer/${file.id}`} target="_blank" rel="noreferrer" aria-label={`Download ${file.title}`}>
                                                        <Download size={16} />
                                                    </a>
                                                    <button type="button" className="icon-button icon-button--ghost icon-button--danger" onClick={() => handleDelete(file.id)} aria-label={`Delete ${file.title}`}>
                                                        <Trash2 size={16} />
                                                    </button>
                                                </div>
                                            </div>

                                            {file.description && (
                                                <p className="manage-card__description">{file.description}</p>
                                            )}

                                            <div className="tag-list tag-list--editable">
                                                <GameSystemMenu
                                                    selectedGameSystem={file.game_system}
                                                    allowCreate
                                                    searchAll
                                                    onSelect={(tag) => handleGameSystemChange(file.id, tag)}
                                                />
                                                {file.tags.map((tag) => (
                                                    <span key={tag.id} className="tag-badge">{tag.name}</span>
                                                ))}
                                                <button
                                                    type="button"
                                                    className="tag-add-button"
                                                    onClick={() => setEditingTagsForFile(file)}
                                                    aria-label={`Add tags to ${file.title}`}
                                                >
                                                    <Plus size={16} />
                                                </button>
                                            </div>

                                            <div className="meta-row">
                                                <span>{(file.size_bytes / (1024 * 1024)).toFixed(1)} MB</span>
                                                <span className="meta-dot">•</span>
                                                <span className={`status-badge${file.status === 'ready' ? ' is-primary' : ''}`}>{file.status === 'ready' ? 'Ready' : file.status}</span>
                                                {file.is_public && <span className="status-badge status-badge--outline">Public</span>}
                                            </div>
                                        </div>
                                    </article>
                                ))
                            )}
                        </div>
                    )}

                    {activeTab === 'saved' && (
                        <div className="page-section-stack">
                            {!session?.authenticated ? (
                                <div className="surface-card empty-card">
                                    <Star className="muted-icon" size={48} />
                                    <p className="empty-card__text">Sign in to keep a saved list of game files</p>
                                    <Link className="primary-button primary-button--inline" to="/account">Open Account</Link>
                                </div>
                            ) : saved.length === 0 ? (
                                <div className="surface-card empty-card">
                                    <Star className="muted-icon" size={48} />
                                    <p className="empty-card__text">No saved files yet</p>
                                    <Link className="primary-button primary-button--inline" to="/browse">Browse Files</Link>
                                </div>
                            ) : (
                                saved.map((file) => (
                                    <article key={file.id} className="surface-card manage-card">
                                        <div className="manage-card__icon">
                                            <FileText size={32} />
                                        </div>
                                        <div className="manage-card__main">
                                            <div className="manage-card__header">
                                                <div>
                                                    <h3>{file.title}</h3>
                                                    <p className="body-muted">{file.filename}</p>
                                                </div>
                                                <div className="icon-action-row">
                                                    <a className="icon-button icon-button--ghost" href={`${apiBase}/viewer/${file.id}`} target="_blank" rel="noreferrer" aria-label={`Open ${file.title}`}>
                                                        <Download size={16} />
                                                    </a>
                                                    <button
                                                        type="button"
                                                        className="icon-button icon-button--ghost icon-button--selected"
                                                        onClick={() => void handleUnsave(file.id)}
                                                        aria-label={`Remove ${file.title} from saved files`}
                                                    >
                                                        <Star size={16} fill="currentColor" />
                                                    </button>
                                                </div>
                                            </div>

                                            {file.description && (
                                                <p className="manage-card__description">{file.description}</p>
                                            )}

                                            <div className="tag-list">
                                                {file.game_system && (
                                                    <span className="tag-badge tag-badge--game-system">{file.game_system.name}</span>
                                                )}
                                                {file.tags.map((tag) => (
                                                    <span key={tag.id} className="tag-badge">{tag.name}</span>
                                                ))}
                                                <span className="tag-badge">{file.is_public ? 'Public' : 'Private'}</span>
                                                <span className={`status-badge${file.status === 'ready' ? ' is-primary' : ''}`}>{file.status === 'ready' ? 'Ready' : file.status}</span>
                                            </div>

                                            <div className="meta-row">
                                                <span>By {file.uploader_name}</span>
                                                <span className="meta-dot">•</span>
                                                <span>{(file.size_bytes / (1024 * 1024)).toFixed(1)} MB</span>
                                            </div>
                                        </div>
                                    </article>
                                ))
                            )}
                        </div>
                    )}

                    {activeTab === 'bundles' && (
                        <div className="page-section-stack">
                            {!session?.authenticated ? (
                                <div className="surface-card empty-card">
                                    <Layers className="muted-icon" size={48} />
                                    <p className="empty-card__text">Sign in to create and save bundles</p>
                                    <Link className="primary-button primary-button--inline" to="/account">Open Account</Link>
                                </div>
                            ) : (
                                <>
                                    <div className="surface-card bundle-toolbar">
                                        <div>
                                            <h3>Create a Bundle</h3>
                                            <p className="body-muted">
                                                Build from your uploaded and saved files in {activeGameSystem?.name || 'the current game system'}.
                                            </p>
                                        </div>
                                        <div className="button-row">
                                            {activeBundle && activeGameSystem?.id && (
                                                <button
                                                    type="button"
                                                    className="secondary-button"
                                                    onClick={() => void handleActivateBundle(null)}
                                                    disabled={activatingBundleId === 0}
                                                >
                                                    Clear Active Bundle
                                                </button>
                                            )}
                                            <button
                                                type="button"
                                                className="primary-button"
                                                onClick={() => setCreatingBundle(true)}
                                                disabled={!availableGameSystems.length || bundleSourceFiles.length === 0}
                                            >
                                                New Bundle
                                            </button>
                                        </div>
                                    </div>

                                    {activeBundle && (
                                        <div className="notice notice--success" role="status">
                                            <p>Chat is currently using "{activeBundle.title}" for {activeGameSystem?.name || 'this game system'}.</p>
                                        </div>
                                    )}

                                    <section>
                                        <div className="section-header">
                                            <Layers className="accent-icon" size={20} />
                                            <h2>My Bundles</h2>
                                        </div>
                                        <div className="page-section-stack">
                                            {myBundles.length === 0 ? (
                                                <div className="surface-card empty-card">
                                                    <Layers className="muted-icon" size={40} />
                                                    <p className="empty-card__text">No bundles yet for your account.</p>
                                                </div>
                                            ) : (
                                                myBundles.map((bundle) => renderBundleCard(bundle, true))
                                            )}
                                        </div>
                                    </section>

                                    <section>
                                        <div className="section-header">
                                            <Star className="accent-icon" size={20} />
                                            <h2>Saved Bundles</h2>
                                        </div>
                                        <div className="page-section-stack">
                                            {savedBundles.length === 0 ? (
                                                <div className="surface-card empty-card">
                                                    <Star className="muted-icon" size={40} />
                                                    <p className="empty-card__text">No saved bundles yet.</p>
                                                    <Link className="primary-button primary-button--inline" to="/browse">Browse Bundles</Link>
                                                </div>
                                            ) : (
                                                savedBundles.map((bundle) => renderBundleCard(bundle, false))
                                            )}
                                        </div>
                                    </section>
                                </>
                            )}
                        </div>
                    )}
                </div>

                {!!error && (
                    <div className="notice notice--error" role="alert">
                        <p>{error}</p>
                    </div>
                )}

                {!!successMessage && (
                    <div className="notice notice--success" role="status">
                        <p>{successMessage}</p>
                    </div>
                )}

                {session?.authenticated && uploaded.length > 0 && (
                    <div className="storage-summary">
                        <span>Total managed storage</span>
                        <strong>{(totalStorage / (1024 * 1024)).toFixed(1)} MB</strong>
                    </div>
                )}
            </div>

            <TagPickerModal
                open={!!editingTagsForFile}
                title={editingTagsForFile ? `Tags for ${editingTagsForFile.title}` : 'Add Tags'}
                initialTags={editingTagsForFile?.tags || []}
                onClose={() => setEditingTagsForFile(null)}
                onSave={async (tags) => {
                    if (!editingTagsForFile) return
                    await handleTagSave(editingTagsForFile.id, tags)
                }}
            />

            <BundleCreateModal
                open={creatingBundle}
                availableFiles={bundleSourceFiles}
                editableFileIds={uploaded.map((file) => file.id)}
                defaultRuleset={activeGameSystem}
                onRenameFile={handleRenameFile}
                onClose={() => setCreatingBundle(false)}
                onSave={handleCreateBundle}
            />
        </div>
    )
}

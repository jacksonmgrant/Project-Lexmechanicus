import { useEffect, useMemo, useState } from 'react'
import { Download, FileText, Plus, Star, Trash2, Upload as UploadIcon } from 'lucide-react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAppContext, type ListedFile, type Ruleset, type Tag } from '../../context/AppContext'
import { getErrorMessage } from '../../lib/api'
import { GameSystemMenu } from '../tags/GameSystemMenu'
import { TagPickerModal } from '../tags/TagPickerModal'

type TabValue = 'uploaded' | 'saved'

export function ManagePage() {
    const { apiBase, deleteFile, listFiles, session, updateFileGameSystem, updateFileTags } = useAppContext()
    const location = useLocation()
    const navigate = useNavigate()
    const [activeTab, setActiveTab] = useState<TabValue>('uploaded')
    const [uploaded, setUploaded] = useState<ListedFile[]>([])
    const [editingTagsForFile, setEditingTagsForFile] = useState<ListedFile | null>(null)
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

    const totalStorage = useMemo(() => uploaded.reduce((sum, file) => sum + file.size_bytes, 0), [uploaded])

    const replaceFile = (fileId: number, updater: (file: ListedFile) => ListedFile) => {
        setUploaded((current) => current.map((file) => file.id === fileId ? updater(file) : file))
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

    return (
        <div className="page-scroll">
            <div className="page-container page-container--wide">
                <div className="page-header page-header--with-actions">
                    <div>
                        <h1>Manage Files</h1>
                        <p>View your uploads, adjust tags, and keep each document attached to the right game system.</p>
                    </div>
                    <Link className="primary-button primary-button--inline" to="/upload">Upload Files</Link>
                </div>

                <div className="tabs">
                    <div className="tabs__list">
                        <button type="button" className={`tabs__trigger${activeTab === 'uploaded' ? ' is-active' : ''}`} onClick={() => setActiveTab('uploaded')}>
                            My Uploads
                        </button>
                        <button type="button" className={`tabs__trigger${activeTab === 'saved' ? ' is-active' : ''}`} onClick={() => setActiveTab('saved')}>
                            Saved Files
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
                                                    <h3>{file.title}</h3>
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
                            <div className="surface-card empty-card">
                                <Star className="muted-icon" size={48} />
                                <p className="empty-card__text">Saved files are not available from the backend yet</p>
                                <Link className="primary-button primary-button--inline" to="/browse">Browse Files</Link>
                            </div>
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
        </div>
    )
}

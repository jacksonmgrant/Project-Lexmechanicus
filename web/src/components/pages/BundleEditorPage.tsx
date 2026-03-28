import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowLeft, Check, Download, Pencil, Plus, Search, Upload, X } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useAppContext, type BundleDetail, type ListedFile } from '../../context/AppContext'
import { getErrorMessage } from '../../lib/api'

type UploadStatus = 'queued' | 'uploading' | 'complete'

type PendingUpload = {
    id: string
    name: string
    title: string
    size: number
    status: UploadStatus
    source: File
}

const MAX_UPLOAD_SIZE_BYTES = 75 * 1024 * 1024
const ALLOWED_EXTENSIONS = new Set(['pdf', 'txt', 'md'])

function buildDefaultFileTitle(file: File) {
    const stripped = file.name.replace(/\.[^.]+$/, '')
    const normalized = stripped.replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim()
    return normalized || file.name
}

function formatFileSize(bytes: number) {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function BundleEditorPage() {
    const {
        apiBase,
        addFilesToBundle,
        getBundle,
        listFiles,
        session,
        removeFileFromBundle,
        updateFileTitle,
        uploadFile,
    } = useAppContext()
    const navigate = useNavigate()
    const params = useParams()
    const bundleId = Number(params.bundleId || '0')
    const [bundleDetail, setBundleDetail] = useState<BundleDetail | null>(null)
    const [availableFiles, setAvailableFiles] = useState<ListedFile[]>([])
    const [ownedFileIds, setOwnedFileIds] = useState<number[]>([])
    const [search, setSearch] = useState('')
    const [selectedFileIds, setSelectedFileIds] = useState<number[]>([])
    const [pendingUploads, setPendingUploads] = useState<PendingUpload[]>([])
    const [uploadDescription, setUploadDescription] = useState('')
    const [uploadIsPublic, setUploadIsPublic] = useState(false)
    const [isLoading, setIsLoading] = useState(true)
    const [isAddingFiles, setIsAddingFiles] = useState(false)
    const [removingFileId, setRemovingFileId] = useState<number | null>(null)
    const [editingFileTitleId, setEditingFileTitleId] = useState<number | null>(null)
    const [draftFileTitle, setDraftFileTitle] = useState('')
    const [savingFileTitleId, setSavingFileTitleId] = useState<number | null>(null)
    const [isUploading, setIsUploading] = useState(false)
    const [error, setError] = useState('')
    const [successMessage, setSuccessMessage] = useState('')

    const loadBundleEditor = useCallback(async () => {
        if (!Number.isFinite(bundleId) || bundleId < 1) {
            setError('Choose a valid bundle to edit.')
            setIsLoading(false)
            return
        }

        setIsLoading(true)
        try {
            const detail = await getBundle(bundleId)
            const [uploadedFiles, savedFiles] = await Promise.all([
                listFiles('mine', '', detail.bundle.game_system_id),
                listFiles('saved', '', detail.bundle.game_system_id),
            ])
            const mergedFiles = new Map<number, ListedFile>()
            for (const file of [...uploadedFiles, ...savedFiles]) {
                mergedFiles.set(file.id, file)
            }
            setBundleDetail(detail)
            setAvailableFiles(Array.from(mergedFiles.values()).sort((left, right) => left.title.localeCompare(right.title)))
            setOwnedFileIds(uploadedFiles.map((file) => file.id))
            setError('')
        } catch (err) {
            setError(getErrorMessage(err, 'Unable to load that bundle.'))
        } finally {
            setIsLoading(false)
        }
    }, [bundleId, getBundle, listFiles])

    useEffect(() => {
        if (!session?.authenticated) {
            setIsLoading(false)
            return
        }
        void loadBundleEditor()
    }, [loadBundleEditor, session])

    const ownedFileIdSet = useMemo(() => new Set(ownedFileIds), [ownedFileIds])

    const visibleFilesToAdd = useMemo(() => {
        if (!bundleDetail) return []
        const normalizedQuery = search.trim().toLowerCase()
        const existingFileIds = new Set(bundleDetail.files.map((file) => file.id))
        return availableFiles
            .filter((file) => !existingFileIds.has(file.id))
            .filter((file) => {
                if (!normalizedQuery) return true
                const haystack = [
                    file.title,
                    file.description || '',
                    file.filename,
                    file.uploader_name,
                    ...file.tags.map((tag) => tag.name),
                ].join(' ').toLowerCase()
                return haystack.includes(normalizedQuery)
            })
    }, [availableFiles, bundleDetail, search])

    const toggleSelectedFile = (fileId: number) => {
        setSelectedFileIds((current) => current.includes(fileId)
            ? current.filter((id) => id !== fileId)
            : [...current, fileId])
    }

    const handleAddExistingFiles = async () => {
        if (!bundleDetail || isAddingFiles || selectedFileIds.length === 0) return
        try {
            setIsAddingFiles(true)
            const payload = await addFilesToBundle(bundleDetail.bundle.id, selectedFileIds)
            setBundleDetail(payload)
            setSelectedFileIds([])
            setSuccessMessage(`${payload.files.length === 1 ? 'Bundle updated.' : 'Files added to bundle.'}`)
            setError('')
        } catch (err) {
            setError(getErrorMessage(err, 'Unable to add files to the bundle.'))
        } finally {
            setIsAddingFiles(false)
        }
    }

    const handleRemoveFile = async (file: ListedFile) => {
        if (!bundleDetail || removingFileId === file.id) return
        try {
            setRemovingFileId(file.id)
            const payload = await removeFileFromBundle(bundleDetail.bundle.id, file.id)
            if (payload.deleted) {
                navigate('/manage', {
                    replace: true,
                    state: { successMessage: 'Bundle deleted because it no longer contained any files.' },
                })
                return
            }
            setBundleDetail({
                bundle: payload.bundle || bundleDetail.bundle,
                files: payload.files || bundleDetail.files.filter((item) => item.id !== file.id),
            })
            setSuccessMessage('File removed from bundle.')
            setError('')
        } catch (err) {
            setError(getErrorMessage(err, 'Unable to remove that file from the bundle.'))
        } finally {
            setRemovingFileId(null)
        }
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
            const title = await updateFileTitle(file.id, normalizedTitle)
            setBundleDetail((current) => current ? {
                ...current,
                files: current.files.map((item) => item.id === file.id ? { ...item, title } : item),
            } : current)
            setAvailableFiles((current) => current.map((item) => item.id === file.id ? { ...item, title } : item))
            setSuccessMessage('File title updated.')
            setError('')
            cancelEditingFileTitle()
        } catch (err) {
            setError(getErrorMessage(err, 'Unable to update the file title.'))
        } finally {
            setSavingFileTitleId(null)
        }
    }

    const renderEditableTitle = (file: ListedFile) => {
        const isEditing = editingFileTitleId === file.id
        const isSaving = savingFileTitleId === file.id
        return (
            <div className="editable-title">
                {isEditing ? (
                    <>
                        <input
                            id={`bundle-file-title-${file.id}`}
                            className="text-input editable-title__input"
                            value={draftFileTitle}
                            onChange={(event) => setDraftFileTitle(event.target.value)}
                            onKeyDown={(event) => {
                                if (event.key === 'Enter') {
                                    event.preventDefault()
                                    void saveFileTitle(file)
                                }
                                if (event.key === 'Escape') {
                                    event.preventDefault()
                                    cancelEditingFileTitle()
                                }
                            }}
                            autoFocus
                        />
                        <div className="editable-title__actions">
                            <button
                                type="button"
                                className="icon-button icon-button--ghost"
                                onClick={() => void saveFileTitle(file)}
                                disabled={isSaving}
                                aria-label={`Save file title for ${file.title}`}
                            >
                                <Check size={16} />
                            </button>
                            <button
                                type="button"
                                className="icon-button icon-button--ghost"
                                onClick={cancelEditingFileTitle}
                                disabled={isSaving}
                                aria-label={`Cancel editing file title for ${file.title}`}
                            >
                                <X size={16} />
                            </button>
                        </div>
                    </>
                ) : (
                    <>
                        <h3>{file.title}</h3>
                        <button
                            type="button"
                            className="icon-button icon-button--ghost"
                            onClick={() => startEditingFileTitle(file)}
                            aria-label={`Edit file title for ${file.title}`}
                        >
                            <Pencil size={16} />
                        </button>
                    </>
                )}
            </div>
        )
    }

    const handlePendingUploadChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFiles = Array.from(event.target.files || [])
        const nextUploads: PendingUpload[] = []
        const failures: string[] = []

        for (const selectedFile of selectedFiles) {
            const extension = selectedFile.name.split('.').pop()?.toLowerCase() || ''
            if (!ALLOWED_EXTENSIONS.has(extension)) {
                failures.push(`${selectedFile.name}: unsupported file type. Upload PDF, TXT, or Markdown files only.`)
                continue
            }
            if (selectedFile.size > MAX_UPLOAD_SIZE_BYTES) {
                failures.push(`${selectedFile.name}: larger than 75 MB.`)
                continue
            }
            nextUploads.push({
                id: Math.random().toString(36).slice(2),
                name: selectedFile.name,
                title: buildDefaultFileTitle(selectedFile),
                size: selectedFile.size,
                status: 'queued',
                source: selectedFile,
            })
        }

        if (nextUploads.length) {
            setPendingUploads((current) => [...current, ...nextUploads])
            setError('')
        }
        if (failures.length) {
            setError(failures.join(' '))
        }

        event.target.value = ''
    }

    const updatePendingUploadTitle = (id: string, nextTitle: string) => {
        setPendingUploads((current) => current.map((file) => file.id === id ? { ...file, title: nextTitle } : file))
    }

    const removePendingUpload = (id: string) => {
        setPendingUploads((current) => current.filter((file) => file.id !== id))
    }

    const handleUploadToBundle = async () => {
        if (!bundleDetail || isUploading || pendingUploads.length === 0) return
        const invalidPendingFile = pendingUploads.find((file) => !file.title.trim() || file.title.trim().length > 120)
        if (invalidPendingFile) {
            setError(!invalidPendingFile.title.trim()
                ? `Enter a title for ${invalidPendingFile.name}.`
                : `Keep the title for ${invalidPendingFile.name} under 120 characters.`)
            return
        }
        if (uploadDescription.trim().length > 1000) {
            setError('Keep the upload description under 1000 characters.')
            return
        }

        setIsUploading(true)
        const uploadedFileIds: number[] = []
        const failures: string[] = []

        for (const file of pendingUploads) {
            setPendingUploads((current) => current.map((item) => item.id === file.id ? { ...item, status: 'uploading' } : item))
            try {
                const result = await uploadFile(
                    file.source,
                    bundleDetail.bundle.is_public || uploadIsPublic,
                    file.title.trim(),
                    uploadDescription.trim(),
                    bundleDetail.bundle.game_system_id,
                    [],
                )
                uploadedFileIds.push(result.file_id)
                setPendingUploads((current) => current.map((item) => item.id === file.id ? { ...item, status: 'complete' } : item))
            } catch (err) {
                setPendingUploads((current) => current.map((item) => item.id === file.id ? { ...item, status: 'queued' } : item))
                failures.push(`${file.name}: ${getErrorMessage(err, 'Unable to upload this file.')}`)
            }
        }

        try {
            if (uploadedFileIds.length) {
                await addFilesToBundle(bundleDetail.bundle.id, uploadedFileIds)
                await loadBundleEditor()
                setPendingUploads((current) => current.filter((file) => file.status !== 'complete'))
                setUploadDescription('')
                setUploadIsPublic(false)
            }

            if (failures.length) {
                setError(failures.join(' '))
                if (uploadedFileIds.length) {
                    setSuccessMessage('Some files were uploaded and added to the bundle, but others failed.')
                }
            } else {
                setSuccessMessage('Files uploaded into the bundle.')
                setError('')
                setPendingUploads([])
            }
        } catch (err) {
            setError(getErrorMessage(err, 'Files uploaded, but could not be added to the bundle.'))
        } finally {
            setIsUploading(false)
        }
    }

    if (!session?.authenticated) {
        return (
            <div className="page-scroll">
                <div className="page-container page-container--wide">
                    <div className="surface-card empty-card">
                        <Upload className="muted-icon" size={48} />
                        <p className="empty-card__text">Sign in to edit your bundles</p>
                        <Link className="primary-button primary-button--inline" to="/account">Open Account</Link>
                    </div>
                </div>
            </div>
        )
    }

    return (
        <div className="page-scroll">
            <div className="page-container page-container--wide">
                <div className="page-header page-header--with-actions">
                    <div>
                        <Link className="page-caption" to="/manage">Back to Manage</Link>
                        <h1>{bundleDetail?.bundle.title || 'Edit Bundle'}</h1>
                        <p>{bundleDetail?.bundle.description || 'Manage the files included in this bundle and add new uploads directly into it.'}</p>
                    </div>
                    <Link className="secondary-button primary-button--inline" to="/manage">
                        <ArrowLeft size={16} />
                        <span>Manage Bundles</span>
                    </Link>
                </div>

                {bundleDetail && (
                    <div className="tag-list">
                        {bundleDetail.bundle.game_system && (
                            <span className="tag-badge tag-badge--game-system">{bundleDetail.bundle.game_system.name}</span>
                        )}
                        <span className="tag-badge">{bundleDetail.files.length} file{bundleDetail.files.length === 1 ? '' : 's'}</span>
                        <span className="tag-badge">{bundleDetail.bundle.is_public ? 'Public' : 'Private'}</span>
                    </div>
                )}

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

                {isLoading ? (
                    <div className="surface-card empty-card">
                        <p className="empty-card__text">Loading bundle...</p>
                    </div>
                ) : bundleDetail ? (
                    <div className="page-section-stack">
                        <section className="surface-card">
                            <div className="section-header">
                                <Upload className="accent-icon" size={20} />
                                <h2>Files in Bundle</h2>
                            </div>
                            <div className="page-section-stack bundle-editor-files">
                                {bundleDetail.files.map((file) => (
                                    <article key={file.id} className="bundle-editor-file">
                                        <div className="bundle-editor-file__main">
                                            {ownedFileIdSet.has(file.id) ? renderEditableTitle(file) : <h3>{file.title}</h3>}
                                            <p className="body-muted">{file.filename}</p>
                                            <div className="tag-list">
                                                {file.tags.map((tag) => (
                                                    <span key={tag.id} className="tag-badge">{tag.name}</span>
                                                ))}
                                                <span className="tag-badge">{formatFileSize(file.size_bytes)}</span>
                                            </div>
                                        </div>
                                        <div className="icon-action-row">
                                            <a className="icon-button icon-button--ghost" href={`${apiBase}/viewer/${file.id}`} target="_blank" rel="noreferrer" aria-label={`Open ${file.title}`}>
                                                <Download size={16} />
                                            </a>
                                            <button
                                                type="button"
                                                className="icon-button icon-button--ghost icon-button--danger"
                                                onClick={() => void handleRemoveFile(file)}
                                                disabled={removingFileId === file.id}
                                                aria-label={`Remove ${file.title} from this bundle`}
                                                title="Remove from bundle"
                                            >
                                                <X size={16} />
                                            </button>
                                        </div>
                                    </article>
                                ))}
                            </div>
                        </section>

                        <section className="surface-card">
                            <div className="section-header">
                                <Plus className="accent-icon" size={20} />
                                <h2>Add Existing Files</h2>
                            </div>
                            <div className="search-field search-field--compact">
                                <Search className="search-field__icon" size={18} />
                                <input
                                    className="text-input text-input--with-icon"
                                    placeholder="Search your uploaded or saved files"
                                    value={search}
                                    onChange={(event) => setSearch(event.target.value)}
                                    maxLength={200}
                                />
                            </div>
                            <div className="bundle-picker">
                                {visibleFilesToAdd.map((file) => {
                                    const isSelected = selectedFileIds.includes(file.id)
                                    return (
                                        <button
                                            key={file.id}
                                            type="button"
                                            className={`bundle-picker__option${isSelected ? ' is-selected' : ''}`}
                                            onClick={() => toggleSelectedFile(file.id)}
                                        >
                                            <div className="bundle-picker__body">
                                                <strong>{file.title}</strong>
                                                <span>{file.filename}</span>
                                                <span>{file.uploader_name}</span>
                                            </div>
                                            <span>{isSelected ? 'Selected' : 'Add'}</span>
                                        </button>
                                    )
                                })}
                                {!visibleFilesToAdd.length && (
                                    <div className="bundle-picker__empty">No additional files are available for this bundle yet.</div>
                                )}
                            </div>
                            <div className="button-row">
                                <button
                                    type="button"
                                    className="primary-button"
                                    onClick={() => void handleAddExistingFiles()}
                                    disabled={isAddingFiles || selectedFileIds.length === 0}
                                >
                                    {isAddingFiles ? 'Adding...' : `Add ${selectedFileIds.length || ''} File${selectedFileIds.length === 1 ? '' : 's'}`}
                                </button>
                            </div>
                        </section>

                        <section className="surface-card">
                            <div className="section-header">
                                <Upload className="accent-icon" size={20} />
                                <h2>Upload New Files to Bundle</h2>
                            </div>
                            <div className="form-stack">
                                <label htmlFor="bundle-upload-input" className="upload-dropzone">
                                    <Upload className="muted-icon" size={48} />
                                    <span className="upload-dropzone__title">Click to upload or drag and drop</span>
                                    <span className="upload-dropzone__subtitle">PDF, TXT, or Markdown (max 75MB per file)</span>
                                </label>
                                <input
                                    id="bundle-upload-input"
                                    type="file"
                                    multiple
                                    accept=".pdf,.txt,.md"
                                    onChange={handlePendingUploadChange}
                                    className="visually-hidden"
                                />

                                {!!pendingUploads.length && (
                                    <div className="form-stack">
                                        {pendingUploads.map((file) => (
                                            <div key={file.id} className="bundle-editor-upload">
                                                <div className="field-group">
                                                    <label htmlFor={`bundle-upload-title-${file.id}`}>{file.name}</label>
                                                    <input
                                                        id={`bundle-upload-title-${file.id}`}
                                                        className="text-input"
                                                        value={file.title}
                                                        onChange={(event) => updatePendingUploadTitle(file.id, event.target.value)}
                                                        maxLength={120}
                                                    />
                                                    <p className="field-help">{formatFileSize(file.size)} • {file.status}</p>
                                                </div>
                                                <button
                                                    type="button"
                                                    className="icon-button icon-button--ghost icon-button--danger"
                                                    onClick={() => removePendingUpload(file.id)}
                                                    aria-label={`Remove ${file.name} from upload queue`}
                                                >
                                                    <X size={16} />
                                                </button>
                                            </div>
                                        ))}
                                    </div>
                                )}

                                <div className="field-group">
                                    <label htmlFor="bundle-upload-description">Shared File Description (Optional)</label>
                                    <textarea
                                        id="bundle-upload-description"
                                        className="text-area"
                                        value={uploadDescription}
                                        onChange={(event) => setUploadDescription(event.target.value)}
                                        maxLength={1000}
                                        placeholder="Optional description applied to every uploaded file."
                                    />
                                </div>

                                <label className="toggle-row" htmlFor="bundle-upload-public">
                                    <div>
                                        <p className="toggle-row__title">Upload files as public</p>
                                        <p className="toggle-row__description">
                                            {bundleDetail.bundle.is_public
                                                ? 'This bundle is public, so uploaded files must also be public.'
                                                : 'Turn this on if the new files should be browsable by other users.'}
                                        </p>
                                    </div>
                                    <input
                                        id="bundle-upload-public"
                                        type="checkbox"
                                        className="checkbox-input"
                                        checked={bundleDetail.bundle.is_public || uploadIsPublic}
                                        disabled={bundleDetail.bundle.is_public}
                                        onChange={(event) => setUploadIsPublic(event.target.checked)}
                                    />
                                </label>

                                <div className="button-row">
                                    <button
                                        type="button"
                                        className="primary-button"
                                        onClick={() => void handleUploadToBundle()}
                                        disabled={isUploading || pendingUploads.length === 0}
                                    >
                                        {isUploading ? 'Uploading...' : 'Upload into Bundle'}
                                    </button>
                                </div>
                            </div>
                        </section>
                    </div>
                ) : (
                    <div className="surface-card empty-card">
                        <p className="empty-card__text">That bundle could not be loaded.</p>
                    </div>
                )}
            </div>
        </div>
    )
}

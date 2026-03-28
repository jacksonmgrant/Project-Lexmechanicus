import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, File, Plus, Upload, X } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAppContext, type Ruleset, type Tag } from '../../context/AppContext'
import { getErrorMessage } from '../../lib/api'
import { GameSystemMenu } from '../tags/GameSystemMenu'
import { TagPickerModal } from '../tags/TagPickerModal'

type UploadStatus = 'queued' | 'uploading' | 'complete'

type UploadedFile = {
    id: string
    name: string
    title: string
    size: number
    status: UploadStatus
    source: File
}

const MAX_UPLOAD_SIZE_BYTES = 75 * 1024 * 1024
const ALLOWED_EXTENSIONS = new Set(['pdf', 'txt', 'md'])
const ALL_SYSTEMS_SLUG = 'all-systems'

function buildDefaultFileTitle(file: File) {
    const stripped = file.name.replace(/\.[^.]+$/, '')
    const normalized = stripped.replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim()
    return normalized || file.name
}

export function UploadPage() {
    const { activeGameSystem, createBundle, uploadFile } = useAppContext()
    const navigate = useNavigate()
    const [files, setFiles] = useState<UploadedFile[]>([])
    const [draftSingleFileTitle, setDraftSingleFileTitle] = useState('')
    const [sharedDescription, setSharedDescription] = useState('')
    const [bundleTitle, setBundleTitle] = useState('')
    const [bundleDescription, setBundleDescription] = useState('')
    const [createBundleFromUploads, setCreateBundleFromUploads] = useState(false)
    const [isPublic, setIsPublic] = useState(false)
    const [selectedTags, setSelectedTags] = useState<Tag[]>([])
    const [selectedGameSystem, setSelectedGameSystem] = useState<Ruleset | null>(activeGameSystem)
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [isTagModalOpen, setIsTagModalOpen] = useState(false)
    const [error, setError] = useState('')
    const [fileFailures, setFileFailures] = useState<string[]>([])

    useEffect(() => {
        setSelectedGameSystem((current) => current || activeGameSystem || null)
    }, [activeGameSystem])

    const isAllSystemsSelected = selectedGameSystem?.slug === ALL_SYSTEMS_SLUG
    const singleFile = files.length === 1
    const shouldCreateBundle = files.length > 1 && createBundleFromUploads
    const showBundleToggle = files.length > 1
    const showSingleTitleInput = files.length <= 1
    const showMultipleFileTitles = files.length > 1
    const totalSizeBytes = useMemo(() => files.reduce((sum, file) => sum + file.size, 0), [files])

    useEffect(() => {
        if (files.length === 1) {
            setDraftSingleFileTitle(files[0].title)
        }
        if (files.length === 0) {
            setCreateBundleFromUploads(false)
        }
        if (files.length === 1) {
            setCreateBundleFromUploads(false)
        }
    }, [files])

    const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFiles = Array.from(event.target.files || [])
        const validFiles: UploadedFile[] = []
        const selectionFailures: string[] = []

        for (const selectedFile of selectedFiles) {
            const extension = selectedFile.name.split('.').pop()?.toLowerCase() || ''
            if (!ALLOWED_EXTENSIONS.has(extension)) {
                selectionFailures.push(`${selectedFile.name}: unsupported file type. Upload PDF, TXT, or Markdown files only.`)
                continue
            }
            if (selectedFile.size > MAX_UPLOAD_SIZE_BYTES) {
                selectionFailures.push(`${selectedFile.name}: larger than 75 MB.`)
                continue
            }

            validFiles.push({
                id: Math.random().toString(36).slice(2),
                name: selectedFile.name,
                title: buildDefaultFileTitle(selectedFile),
                size: selectedFile.size,
                status: 'queued',
                source: selectedFile,
            })
        }

        if (validFiles.length) {
            const nextFiles = [...files, ...validFiles]
            if (files.length === 0 && nextFiles.length === 1 && draftSingleFileTitle.trim()) {
                nextFiles[0] = { ...nextFiles[0], title: draftSingleFileTitle.trim() }
            }
            setFiles(nextFiles)
            if (files.length <= 1 && nextFiles.length > 1) {
                setCreateBundleFromUploads(true)
            }
            setError('')
        }
        setFileFailures(selectionFailures)
        if (!validFiles.length && selectionFailures.length) {
            setError('Some files could not be added.')
        }

        event.target.value = ''
    }

    const removeFile = (id: string) => {
        setFiles((prev) => {
            const nextFiles = prev.filter((file) => file.id !== id)
            if (nextFiles.length === 1) {
                setDraftSingleFileTitle(nextFiles[0].title)
            }
            return nextFiles
        })
    }

    const updateSingleFileTitle = (nextTitle: string) => {
        setDraftSingleFileTitle(nextTitle)
        setFiles((current) => current.length === 1 ? [{ ...current[0], title: nextTitle }] : current)
    }

    const updateFileTitle = (id: string, nextTitle: string) => {
        setFiles((current) => current.map((file) => (file.id === id ? { ...file, title: nextTitle } : file)))
    }

    const formatFileSize = (bytes: number) => {
        if (bytes < 1024) return `${bytes} B`
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    }

    const handleSubmit = async () => {
        const normalizedSharedDescription = sharedDescription.trim()
        const normalizedBundleTitle = bundleTitle.trim()
        const normalizedBundleDescription = bundleDescription.trim()

        if (isSubmitting) return
        if (files.length === 0) {
            setError('Select at least one file to upload.')
            return
        }
        if (showSingleTitleInput) {
            const normalizedSingleTitle = (singleFile ? files[0]?.title : draftSingleFileTitle).trim()
            if (!normalizedSingleTitle) {
                setFileFailures([])
                setError('Enter a title before uploading.')
                return
            }
            if (normalizedSingleTitle.length > 120) {
                setFileFailures([])
                setError('Keep the title under 120 characters.')
                return
            }
        }
        if (showMultipleFileTitles) {
            const invalidFile = files.find((file) => !file.title.trim() || file.title.trim().length > 120)
            if (invalidFile) {
                setFileFailures([])
                setError(!invalidFile.title.trim()
                    ? `Enter a title for ${invalidFile.name}.`
                    : `Keep the title for ${invalidFile.name} under 120 characters.`)
                return
            }
        }
        if (normalizedSharedDescription.length > 1000) {
            setFileFailures([])
            setError('Keep the file description under 1000 characters.')
            return
        }
        if (normalizedBundleTitle.length > 160) {
            setFileFailures([])
            setError('Keep the bundle title under 160 characters.')
            return
        }
        if (normalizedBundleDescription.length > 1000) {
            setFileFailures([])
            setError('Keep the bundle description under 1000 characters.')
            return
        }
        if (!selectedGameSystem) {
            setFileFailures([])
            setError('Choose a game system before uploading.')
            return
        }
        if (shouldCreateBundle && isAllSystemsSelected) {
            setFileFailures([])
            setError('Choose a specific game system before creating a bundle.')
            return
        }
        if (shouldCreateBundle && !normalizedBundleTitle) {
            setFileFailures([])
            setError('Enter a bundle title before uploading.')
            return
        }

        setError('')
        setFileFailures([])
        setIsSubmitting(true)

        const uploadedFileIds: number[] = []
        const uploadFailures: string[] = []
        for (const file of files) {
            setFiles((prev) => prev.map((item) => (item.id === file.id ? { ...item, status: 'uploading' } : item)))
            try {
                const result = await uploadFile(
                    file.source,
                    isPublic,
                    file.title.trim(),
                    normalizedSharedDescription,
                    selectedGameSystem.id,
                    selectedTags.map((tag) => tag.id),
                )
                uploadedFileIds.push(result.file_id)
                setFiles((prev) => prev.map((item) => (item.id === file.id ? { ...item, status: 'complete' } : item)))
            } catch (err) {
                setFiles((prev) => prev.map((item) => (item.id === file.id ? { ...item, status: 'queued' } : item)))
                uploadFailures.push(`${file.name}: ${getErrorMessage(err, 'Unable to upload this file.')}`)
            }
        }

        if (uploadFailures.length > 0) {
            setFileFailures(uploadFailures)
            setError(shouldCreateBundle
                ? 'Some files failed to upload, so the bundle was not created.'
                : 'Some files failed to upload.')
            setIsSubmitting(false)
            return
        }

        if (shouldCreateBundle) {
            try {
                await createBundle({
                    title: normalizedBundleTitle,
                    description: normalizedBundleDescription,
                    rulesetId: selectedGameSystem.id,
                    fileIds: uploadedFileIds,
                    isPublic,
                })
            } catch (err) {
                setError(getErrorMessage(err, 'Files uploaded, but the bundle could not be created. You can create it later from Manage Bundles.'))
                setIsSubmitting(false)
                return
            }
        }

        const nextSuccessMessage = shouldCreateBundle
            ? (files.length === 1 ? 'File uploaded and bundle created successfully.' : 'Files uploaded and bundle created successfully.')
            : (files.length === 1 ? 'File uploaded successfully.' : 'Files uploaded successfully.')

        setFiles([])
        setDraftSingleFileTitle('')
        setSharedDescription('')
        setBundleTitle('')
        setBundleDescription('')
        setCreateBundleFromUploads(false)
        setIsPublic(false)
        setSelectedTags([])
        setSelectedGameSystem(activeGameSystem || selectedGameSystem)
        setFileFailures([])
        setIsSubmitting(false)
        navigate('/manage', { state: { successMessage: nextSuccessMessage } })
    }

    return (
        <div className="page-scroll">
            <div className="page-container page-container--narrow">
                <div className="page-header">
                    <h1>Upload Game Rules</h1>
                    <p>Start with a single-file upload, or add multiple files to switch into bundle upload mode automatically.</p>
                </div>

                <div className="page-section-stack">
                    <section className="surface-card">
                        <label htmlFor="file-upload" className="upload-dropzone">
                            <Upload className="muted-icon" size={48} />
                            <span className="upload-dropzone__title">Click to upload or drag and drop</span>
                            <span className="upload-dropzone__subtitle">PDF, TXT, or Markdown (max 75MB per file)</span>
                        </label>
                        <input
                            id="file-upload"
                            type="file"
                            multiple
                            accept=".pdf,.txt,.md"
                            className="visually-hidden"
                            onChange={handleFileChange}
                        />
                    </section>

                    {files.length > 0 && (
                        <section className="surface-card">
                            <div className="section-header">
                                <File className="accent-icon" size={20} />
                                <h2>Files ({files.length})</h2>
                            </div>
                            <div className="surface-list">
                                {files.map((file) => (
                                    <div key={file.id} className="surface-list__item">
                                        <File className="subtle-icon" size={20} />
                                        <div className="surface-list__body">
                                            <p className="surface-list__title">{file.name}</p>
                                            <p className="surface-list__meta">
                                                {file.title} • {formatFileSize(file.size)}
                                            </p>
                                        </div>
                                        {file.status === 'uploading' ? (
                                            <div className="spinner" aria-hidden="true" />
                                        ) : file.status === 'complete' ? (
                                            <CheckCircle2 className="success-icon" size={20} />
                                        ) : (
                                            <span className="status-badge status-badge--outline">Ready</span>
                                        )}
                                        <button
                                            type="button"
                                            className="icon-button icon-button--ghost"
                                            onClick={() => removeFile(file.id)}
                                            aria-label={`Remove ${file.name}`}
                                            disabled={isSubmitting}
                                        >
                                            <X size={16} />
                                        </button>
                                    </div>
                                ))}
                            </div>
                            <div className="storage-summary">
                                <span>Total selected</span>
                                <strong>{formatFileSize(totalSizeBytes)}</strong>
                            </div>
                        </section>
                    )}

                    <section className="surface-card">
                        <div className="form-stack">
                            {showBundleToggle && (
                                <label className="toggle-row" htmlFor="create-bundle">
                                    <div>
                                        <p className="toggle-row__title">Create a bundle from these uploads</p>
                                        <p className="toggle-row__description">Multiple file uploads switch here automatically, but you can toggle back to upload standalone files.</p>
                                    </div>
                                    <input
                                        type="checkbox"
                                        id="create-bundle"
                                        checked={createBundleFromUploads}
                                        onChange={(event) => setCreateBundleFromUploads(event.target.checked)}
                                        className="checkbox-input"
                                    />
                                </label>
                            )}

                            {showSingleTitleInput && (
                                <div className="field-group">
                                    <label htmlFor="file-title">Title</label>
                                    <input
                                        id="file-title"
                                        placeholder="e.g., Warhammer 40K Core Rules 10th Edition"
                                        value={singleFile ? files[0]?.title || '' : draftSingleFileTitle}
                                        onChange={(event) => updateSingleFileTitle(event.target.value)}
                                        className="text-input"
                                        maxLength={120}
                                    />
                                </div>
                            )}

                            {showMultipleFileTitles && (
                                <div className="field-group">
                                    <label>File Titles</label>
                                    <div className="form-stack">
                                        {files.map((file) => (
                                            <div key={file.id} className="field-group">
                                                <label htmlFor={`file-title-${file.id}`}>{file.name}</label>
                                                <input
                                                    id={`file-title-${file.id}`}
                                                    value={file.title}
                                                    onChange={(event) => updateFileTitle(file.id, event.target.value)}
                                                    className="text-input"
                                                    maxLength={120}
                                                />
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {shouldCreateBundle && (
                                <>
                                    <div className="field-group">
                                        <label htmlFor="bundle-title">Bundle Title</label>
                                        <input
                                            id="bundle-title"
                                            placeholder="e.g., Warhammer 40K Core Rules Set"
                                            value={bundleTitle}
                                            onChange={(event) => setBundleTitle(event.target.value)}
                                            className="text-input"
                                            maxLength={160}
                                        />
                                    </div>
                                    <div className="field-group">
                                        <label htmlFor="bundle-description">Bundle Description (Optional)</label>
                                        <textarea
                                            id="bundle-description"
                                            placeholder="Add notes about how these files belong together..."
                                            value={bundleDescription}
                                            onChange={(event) => setBundleDescription(event.target.value)}
                                            className="text-area"
                                            maxLength={1000}
                                        />
                                    </div>
                                </>
                            )}

                            <div className="field-group">
                                <label htmlFor="shared-description">File Description (Optional)</label>
                                <textarea
                                    id="shared-description"
                                    placeholder="Optional description applied to each uploaded file."
                                    value={sharedDescription}
                                    onChange={(event) => setSharedDescription(event.target.value)}
                                    className="text-area"
                                    maxLength={1000}
                                />
                                <p className="field-help">
                                    {showMultipleFileTitles
                                        ? 'This description is applied to every uploaded file in the batch.'
                                        : 'This description is applied to the uploaded file.'}
                                </p>
                            </div>

                            <div className="field-group">
                                <label>Game System</label>
                                <GameSystemMenu
                                    selectedGameSystem={selectedGameSystem}
                                    allowCreate
                                    searchAll
                                    onSelect={async (ruleset) => {
                                        setSelectedGameSystem(ruleset)
                                        setError('')
                                    }}
                                />
                                <p className="field-help">
                                    New uploads default to your current active game system. Bundle creation requires a specific system, not All Systems.
                                </p>
                            </div>

                            <div className="field-group">
                                <label>Tags</label>
                                <div className="tag-list tag-list--editable">
                                    {selectedTags.map((tag) => (
                                        <span key={tag.id} className="tag-badge">{tag.name}</span>
                                    ))}
                                    <button type="button" className="tag-add-button" onClick={() => setIsTagModalOpen(true)} aria-label="Add tags">
                                        <Plus size={16} />
                                    </button>
                                </div>
                                <p className="field-help">Selected tags are applied to every uploaded file in this batch.</p>
                            </div>

                            <div className="checkbox-row">
                                <input
                                    type="checkbox"
                                    id="public"
                                    checked={isPublic}
                                    onChange={(event) => setIsPublic(event.target.checked)}
                                    className="checkbox-input"
                                />
                                <label htmlFor="public">
                                    Make uploaded files {shouldCreateBundle ? 'and the new bundle ' : ''}publicly browsable
                                </label>
                            </div>
                        </div>
                    </section>

                    {!!error && (
                        <div className="notice notice--error" role="alert">
                            <p>{error}</p>
                            {fileFailures.length > 0 && (
                                <ul className="notice__list">
                                    {fileFailures.map((failure) => (
                                        <li key={failure}>{failure}</li>
                                    ))}
                                </ul>
                            )}
                        </div>
                    )}

                    <button type="button" onClick={handleSubmit} disabled={files.length === 0 || isSubmitting} className="primary-button primary-button--full">
                        {isSubmitting
                            ? (shouldCreateBundle ? 'Uploading Files and Creating Bundle...' : 'Uploading Files...')
                            : (shouldCreateBundle ? 'Upload Files and Create Bundle' : 'Upload Files')}
                    </button>
                </div>
            </div>

            <TagPickerModal
                open={isTagModalOpen}
                title="Add Tags"
                initialTags={selectedTags}
                onClose={() => setIsTagModalOpen(false)}
                onSave={async (tags) => {
                    setSelectedTags(tags)
                    setError('')
                }}
            />
        </div>
    )
}

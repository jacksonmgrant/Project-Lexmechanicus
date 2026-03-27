import { useEffect, useState } from 'react'
import { CheckCircle2, File, Plus, Upload, X } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAppContext, type Ruleset, type Tag } from '../../context/AppContext'
import { getErrorMessage } from '../../lib/api'
import { GameSystemMenu } from '../tags/GameSystemMenu'
import { TagPickerModal } from '../tags/TagPickerModal'

type UploadedFile = {
    id: string
    name: string
    size: number
    status: 'uploading' | 'complete'
    source: File
}

const MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024
const ALLOWED_EXTENSIONS = new Set(['pdf', 'txt', 'md'])

export function UploadPage() {
    const { activeGameSystem, uploadFile } = useAppContext()
    const navigate = useNavigate()
    const [files, setFiles] = useState<UploadedFile[]>([])
    const [title, setTitle] = useState('')
    const [description, setDescription] = useState('')
    const [isPublic, setIsPublic] = useState(false)
    const [selectedTags, setSelectedTags] = useState<Tag[]>([])
    const [selectedGameSystem, setSelectedGameSystem] = useState<Ruleset | null>(activeGameSystem)
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [isTagModalOpen, setIsTagModalOpen] = useState(false)
    const [error, setError] = useState('')

    useEffect(() => {
        setSelectedGameSystem((current) => current || activeGameSystem || null)
    }, [activeGameSystem])

    const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFiles = Array.from(event.target.files || [])
        const validFiles: UploadedFile[] = []

        for (const selectedFile of selectedFiles) {
            const extension = selectedFile.name.split('.').pop()?.toLowerCase() || ''
            if (!ALLOWED_EXTENSIONS.has(extension)) {
                setError(`Unsupported file type for ${selectedFile.name}. Upload PDF, TXT, or Markdown files only.`)
                continue
            }
            if (selectedFile.size > MAX_UPLOAD_SIZE_BYTES) {
                setError(`${selectedFile.name} is larger than 10 MB.`)
                continue
            }

            validFiles.push({
                id: Math.random().toString(36).slice(2),
                name: selectedFile.name,
                size: selectedFile.size,
                status: 'complete',
                source: selectedFile,
            })
        }

        if (validFiles.length) {
            setError('')
        }

        setFiles((prev) => [...prev, ...validFiles])
        event.target.value = ''
    }

    const removeFile = (id: string) => {
        setFiles((prev) => prev.filter((file) => file.id !== id))
    }

    const formatFileSize = (bytes: number) => {
        if (bytes < 1024) return `${bytes} B`
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    }

    const handleSubmit = async () => {
        const normalizedTitle = title.trim()
        const normalizedDescription = description.trim()
        if (isSubmitting) return
        if (files.length === 0) {
            setError('Select at least one file to upload.')
            return
        }
        if (!normalizedTitle) {
            setError('Enter a title before uploading.')
            return
        }
        if (normalizedTitle.length > 120) {
            setError('Keep the title under 120 characters.')
            return
        }
        if (normalizedDescription.length > 1000) {
            setError('Keep the description under 1000 characters.')
            return
        }
        if (!selectedGameSystem) {
            setError('Choose a game system before uploading.')
            return
        }

        setError('')
        setIsSubmitting(true)
        for (const file of files) {
            setFiles((prev) => prev.map((item) => (item.id === file.id ? { ...item, status: 'uploading' } : item)))
            try {
                await uploadFile(
                    file.source,
                    isPublic,
                    normalizedTitle,
                    normalizedDescription,
                    selectedGameSystem.id,
                    selectedTags.map((tag) => tag.id),
                )
                setFiles((prev) => prev.map((item) => (item.id === file.id ? { ...item, status: 'complete' } : item)))
            } catch (err) {
                setFiles((prev) => prev.map((item) => (item.id === file.id ? { ...item, status: 'complete' } : item)))
                setError(getErrorMessage(err, `Unable to upload ${file.name}.`))
                setIsSubmitting(false)
                return
            }
        }
        const nextSuccessMessage = files.length === 1 ? 'File uploaded successfully.' : 'Files uploaded successfully.'
        setTitle('')
        setDescription('')
        setFiles([])
        setIsPublic(false)
        setSelectedTags([])
        setSelectedGameSystem(activeGameSystem || selectedGameSystem)
        setIsSubmitting(false)
        navigate('/manage', { state: { successMessage: nextSuccessMessage } })
    }

    return (
        <div className="page-scroll">
            <div className="page-container page-container--narrow">
                <div className="page-header">
                    <h1>Upload Game Rules</h1>
                    <p>Upload rulebooks, FAQs, or other game-related documents and organize them with tags as you go.</p>
                </div>

                <div className="page-section-stack">
                    <section className="surface-card">
                        <label htmlFor="file-upload" className="upload-dropzone">
                            <Upload className="muted-icon" size={48} />
                            <span className="upload-dropzone__title">Click to upload or drag and drop</span>
                            <span className="upload-dropzone__subtitle">PDF, TXT, or Markdown (max 10MB)</span>
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
                            <h3>Files ({files.length})</h3>
                            <div className="surface-list">
                                {files.map((file) => (
                                    <div key={file.id} className="surface-list__item">
                                        <File className="subtle-icon" size={20} />
                                        <div className="surface-list__body">
                                            <p className="surface-list__title">{file.name}</p>
                                            <p className="surface-list__meta">{formatFileSize(file.size)}</p>
                                        </div>
                                        {file.status === 'complete' ? (
                                            <CheckCircle2 className="success-icon" size={20} />
                                        ) : (
                                            <div className="spinner" aria-hidden="true" />
                                        )}
                                        <button type="button" className="icon-button icon-button--ghost" onClick={() => removeFile(file.id)} aria-label={`Remove ${file.name}`}>
                                            <X size={16} />
                                        </button>
                                    </div>
                                ))}
                            </div>
                        </section>
                    )}

                    <section className="surface-card">
                        <div className="form-stack">
                            <div className="field-group">
                                <label htmlFor="title">Title</label>
                                <input
                                    id="title"
                                    placeholder="e.g., Warhammer 40K Core Rules 10th Edition"
                                    value={title}
                                    onChange={(event) => setTitle(event.target.value)}
                                    className="text-input"
                                    maxLength={120}
                                />
                            </div>
                            <div className="field-group">
                                <label htmlFor="description">Description (Optional)</label>
                                <textarea
                                    id="description"
                                    placeholder="Add notes about this ruleset..."
                                    value={description}
                                    onChange={(event) => setDescription(event.target.value)}
                                    className="text-area"
                                    maxLength={1000}
                                />
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
                                <p className="field-help">New uploads default to your current active game system, but you can change it here.</p>
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
                            </div>
                            <div className="checkbox-row">
                                <input
                                    type="checkbox"
                                    id="public"
                                    checked={isPublic}
                                    onChange={(event) => setIsPublic(event.target.checked)}
                                    className="checkbox-input"
                                />
                                <label htmlFor="public">Make this publicly browsable</label>
                            </div>
                        </div>
                    </section>

                    {!!error && (
                        <div className="notice notice--error" role="alert">
                            <p>{error}</p>
                        </div>
                    )}

                    <button type="button" onClick={handleSubmit} disabled={files.length === 0 || isSubmitting} className="primary-button primary-button--full">
                        {isSubmitting ? 'Uploading Files...' : 'Upload Files'}
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

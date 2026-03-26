import { useState } from 'react'
import { CheckCircle2, File, Upload, X } from 'lucide-react'
import { useAppContext } from '../../context/AppContext'

type UploadedFile = {
    id: string
    name: string
    size: number
    status: 'uploading' | 'complete'
    source: File
}

export function UploadPage() {
    const { uploadFile } = useAppContext()
    const [files, setFiles] = useState<UploadedFile[]>([])
    const [title, setTitle] = useState('')
    const [description, setDescription] = useState('')
    const [isPublic, setIsPublic] = useState(false)
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [error, setError] = useState('')

    const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFiles = Array.from(event.target.files || [])
        const newFiles: UploadedFile[] = selectedFiles.map((file) => ({
            id: Math.random().toString(36).slice(2),
            name: file.name,
            size: file.size,
            status: 'complete',
            source: file,
        }))
        setFiles((prev) => [...prev, ...newFiles])
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
        if (files.length === 0 || !title || isSubmitting) return

        setError('')
        setIsSubmitting(true)
        for (const file of files) {
            setFiles((prev) => prev.map((item) => (item.id === file.id ? { ...item, status: 'uploading' } : item)))
            try {
                await uploadFile(file.source, isPublic)
                setFiles((prev) => prev.map((item) => (item.id === file.id ? { ...item, status: 'complete' } : item)))
            } catch (err) {
                setFiles((prev) => prev.map((item) => (item.id === file.id ? { ...item, status: 'complete' } : item)))
                setError(err instanceof Error ? err.message : `Unable to upload ${file.name}.`)
                setIsSubmitting(false)
                return
            }
        }
        setTitle('')
        setDescription('')
        setFiles([])
        setIsPublic(false)
        setIsSubmitting(false)
    }

    return (
        <div className="page-scroll">
            <div className="page-container page-container--narrow">
                <div className="page-header">
                    <h1>Upload Game Rules</h1>
                    <p>Upload rulebooks, FAQs, or other game-related documents to enhance the AI&apos;s knowledge base.</p>
                </div>

                <div className="page-section-stack">
                    <section className="surface-card">
                        <label htmlFor="file-upload" className="upload-dropzone">
                            <Upload className="muted-icon" size={48} />
                            <span className="upload-dropzone__title">Click to upload or drag and drop</span>
                            <span className="upload-dropzone__subtitle">PDF, TXT, DOCX (max 10MB)</span>
                        </label>
                        <input
                            id="file-upload"
                            type="file"
                            multiple
                            accept=".pdf,.txt,.doc,.docx,.md"
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
                                />
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
                        <div className="empty-state">
                            <p>{error}</p>
                        </div>
                    )}

                    <button type="button" onClick={handleSubmit} disabled={files.length === 0 || !title || isSubmitting} className="primary-button primary-button--full">
                        {isSubmitting ? 'Uploading Files...' : 'Upload Files'}
                    </button>
                </div>
            </div>
        </div>
    )
}

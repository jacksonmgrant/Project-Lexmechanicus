import { useEffect, useMemo, useState } from 'react'
import { Download, FileText, Star, Trash2, Upload as UploadIcon } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAppContext, type ListedFile } from '../../context/AppContext'

type TabValue = 'uploaded' | 'saved'

export function ManagePage() {
    const { apiBase, deleteFile, listFiles, session } = useAppContext()
    const [activeTab, setActiveTab] = useState<TabValue>('uploaded')
    const [uploaded, setUploaded] = useState<ListedFile[]>([])
    const [error, setError] = useState('')

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
                setError(err instanceof Error ? err.message : 'Unable to load your uploads.')
            })
    }, [listFiles, session])

    const totalStorage = useMemo(() => uploaded.reduce((sum, file) => sum + file.size_bytes, 0), [uploaded])

    const handleDelete = async (id: number) => {
        try {
            await deleteFile(id)
            setUploaded((prev) => prev.filter((file) => file.id !== id))
            setError('')
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unable to delete that file.')
        }
    }

    return (
        <div className="page-scroll">
            <div className="page-container page-container--wide">
                <div className="page-header">
                    <h1>Manage Files</h1>
                    <p>View and manage your uploaded files and saved references.</p>
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
                                                <h3>{file.title}</h3>
                                                <div className="icon-action-row">
                                                    <a className="icon-button icon-button--ghost" href={`${apiBase}/viewer/${file.id}`} target="_blank" rel="noreferrer" aria-label={`Download ${file.title}`}>
                                                        <Download size={16} />
                                                    </a>
                                                    <button type="button" className="icon-button icon-button--ghost icon-button--danger" onClick={() => handleDelete(file.id)} aria-label={`Delete ${file.title}`}>
                                                        <Trash2 size={16} />
                                                    </button>
                                                </div>
                                            </div>
                                            <div className="meta-row">
                                                <span>File #{file.id}</span>
                                                <span className="meta-dot">•</span>
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
                    <div className="empty-state">
                        <p>{error}</p>
                    </div>
                )}

                {session?.authenticated && uploaded.length > 0 && (
                    <div className="storage-summary">
                        <span>Total managed storage</span>
                        <strong>{(totalStorage / (1024 * 1024)).toFixed(1)} MB</strong>
                    </div>
                )}
            </div>
        </div>
    )
}

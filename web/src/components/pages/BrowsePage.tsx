import { useEffect, useState } from 'react'
import { Download, Eye, Search } from 'lucide-react'
import { useAppContext, type ListedFile } from '../../context/AppContext'

export function BrowsePage() {
    const { listFiles, defaultGameSystemId, apiBase } = useAppContext()
    const [search, setSearch] = useState('')
    const [filteredRules, setFilteredRules] = useState<ListedFile[]>([])
    const [error, setError] = useState('')

    useEffect(() => {
        listFiles('browse', search, defaultGameSystemId)
            .then((files) => {
                setFilteredRules(files)
                setError('')
            })
            .catch((err) => {
                setFilteredRules([])
                setError(err instanceof Error ? err.message : 'Unable to load files.')
            })
    }, [defaultGameSystemId, listFiles, search])

    return (
        <div className="page-scroll">
            <div className="page-container page-container--wide">
                <div className="page-header">
                    <h1>Browse Game Rules</h1>
                    <p>Explore rulebooks and documents uploaded by the community.</p>
                </div>

                <div className="search-field">
                    <Search className="search-field__icon" size={20} />
                    <input
                        placeholder="Search by title, description, or tags..."
                        value={search}
                        onChange={(event) => setSearch(event.target.value)}
                        className="text-input text-input--with-icon"
                    />
                </div>

                <div className="page-section-stack">
                    {filteredRules.map((rule) => (
                        <article key={rule.id} className="surface-card browse-card">
                            <div className="browse-card__main">
                                <h3>{rule.title}</h3>
                                <p className="browse-card__description">
                                    {rule.mime_type} document from folder {rule.folder_id} with {rule.chunk_count} indexed chunks.
                                </p>
                                <div className="tag-list">
                                    <span className="tag-badge">Game System {rule.game_system_id}</span>
                                    <span className="tag-badge">{rule.is_public ? 'Public' : 'Private'}</span>
                                    <span className="tag-badge">{rule.status}</span>
                                </div>
                                <div className="meta-row">
                                    <span>By {rule.uploader_email}</span>
                                    <span className="meta-dot">•</span>
                                    <span>File #{rule.id}</span>
                                </div>
                            </div>
                            <div className="browse-card__side">
                                <div className="stat-row">
                                    <div className="stat-item">
                                        <Download size={16} />
                                        <span>{rule.downloads}</span>
                                    </div>
                                    <div className="stat-item">
                                        <Eye size={16} />
                                        <span>{rule.views}</span>
                                    </div>
                                </div>
                                <a className="primary-button primary-button--inline" href={`${apiBase}/viewer/${rule.id}`} target="_blank" rel="noreferrer">
                                    View Details
                                </a>
                            </div>
                        </article>
                    ))}
                </div>

                {error && (
                    <div className="empty-state">
                        <p>{error}</p>
                    </div>
                )}

                {!filteredRules.length && !error && (
                    <div className="empty-state">
                        <p>No rules found matching your search.</p>
                    </div>
                )}
            </div>
        </div>
    )
}

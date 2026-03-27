import { useEffect, useState } from 'react'
import { Download, Eye, Search } from 'lucide-react'
import { useAppContext, type ListedFile } from '../../context/AppContext'
import { getErrorMessage } from '../../lib/api'
import { useDebouncedValue } from '../../lib/useDebouncedValue'

export function BrowsePage() {
    const { listFiles, activeGameSystem, apiBase } = useAppContext()
    const [search, setSearch] = useState('')
    const debouncedSearch = useDebouncedValue(search, 300)
    const [filteredRules, setFilteredRules] = useState<ListedFile[]>([])
    const [error, setError] = useState('')

    useEffect(() => {
        if (!activeGameSystem?.id) {
            setFilteredRules([])
            return
        }
        listFiles('browse', debouncedSearch, activeGameSystem?.id)
            .then((files) => {
                setFilteredRules(files)
                setError('')
            })
            .catch((err) => {
                setFilteredRules([])
                setError(getErrorMessage(err, 'Unable to load files.'))
            })
    }, [activeGameSystem?.id, debouncedSearch, listFiles])

    return (
        <div className="page-scroll">
            <div className="page-container page-container--wide">
                <div className="page-header">
                    <h1>Browse Game Rules</h1>
                    <p>Explore rulebooks and documents for {activeGameSystem?.name || 'your selected game system'}.</p>
                </div>

                <div className="search-field">
                    <Search className="search-field__icon" size={20} />
                    <input
                        placeholder="Search by title, description, or tags..."
                        value={search}
                        onChange={(event) => setSearch(event.target.value)}
                        className="text-input text-input--with-icon"
                        maxLength={200}
                    />
                </div>

                <div className="page-section-stack">
                    {filteredRules.map((rule) => (
                        <article key={rule.id} className="surface-card browse-card">
                            <div className="browse-card__main">
                                <h3>{rule.title}</h3>
                                <p className="browse-card__description">
                                    {rule.description || rule.filename}
                                </p>
                                <div className="tag-list">
                                    {rule.game_system && (
                                        <span className="tag-badge tag-badge--game-system">{rule.game_system.name}</span>
                                    )}
                                    {rule.tags.map((tag) => (
                                        <span key={tag.id} className="tag-badge">{tag.name}</span>
                                    ))}
                                    <span className="tag-badge">{rule.is_public ? 'Public' : 'Private'}</span>
                                    <span className="tag-badge">{rule.status}</span>
                                </div>
                                <div className="meta-row">
                                    <span>By {rule.uploader_name}</span>
                                    <span className="meta-dot">•</span>
                                    <span>{(rule.size_bytes / (1024 * 1024)).toFixed(1)} MB</span>
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
                    <div className="notice notice--error" role="alert">
                        <p>{error}</p>
                    </div>
                )}

                {!activeGameSystem && !error && (
                    <div className="empty-state">
                        <p>Select a game system to browse matching files.</p>
                    </div>
                )}

                {!filteredRules.length && !error && activeGameSystem && (
                    <div className="empty-state">
                        <p>No rules found matching your search.</p>
                    </div>
                )}
            </div>
        </div>
    )
}

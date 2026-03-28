import { useEffect, useState } from 'react'
import { Search, Star } from 'lucide-react'
import { useAppContext, type Bundle, type ListedFile } from '../../context/AppContext'
import { getErrorMessage } from '../../lib/api'
import { useDebouncedValue } from '../../lib/useDebouncedValue'

type BrowseView = 'files' | 'bundles'

export function BrowsePage() {
    const {
        listFiles,
        listBundles,
        activeGameSystem,
        activeBundle,
        apiBase,
        saveFile,
        saveBundle,
        setActiveBundle,
        session,
        unsaveFile,
        unsaveBundle,
    } = useAppContext()
    const [view, setView] = useState<BrowseView>('files')
    const [search, setSearch] = useState('')
    const debouncedSearch = useDebouncedValue(search, 300)
    const [filteredRules, setFilteredRules] = useState<ListedFile[]>([])
    const [filteredBundles, setFilteredBundles] = useState<Bundle[]>([])
    const [error, setError] = useState('')
    const [savingKey, setSavingKey] = useState('')
    const [activatingBundleId, setActivatingBundleId] = useState<number | null>(null)

    useEffect(() => {
        if (!activeGameSystem?.id) {
            setFilteredRules([])
            setFilteredBundles([])
            return
        }

        const load = view === 'files'
            ? listFiles('browse', debouncedSearch, activeGameSystem.id).then((files) => {
                setFilteredRules(files)
                setFilteredBundles([])
            })
            : listBundles('browse', debouncedSearch, activeGameSystem.id).then((bundles) => {
                setFilteredBundles(bundles)
                setFilteredRules([])
            })

        load
            .then(() => setError(''))
            .catch((err) => {
                setFilteredRules([])
                setFilteredBundles([])
                setError(getErrorMessage(err, `Unable to load ${view}.`))
            })
    }, [activeGameSystem?.id, debouncedSearch, listBundles, listFiles, view])

    const toggleSavedFile = async (rule: ListedFile) => {
        try {
            setSavingKey(`file:${rule.id}`)
            if (rule.is_saved) {
                await unsaveFile(rule.id)
            } else {
                await saveFile(rule.id)
            }
            setFilteredRules((current) => current.map((file) => (
                file.id === rule.id
                    ? { ...file, is_saved: !rule.is_saved, save_count: Math.max(0, file.save_count + (rule.is_saved ? -1 : 1)) }
                    : file
            )))
            setError('')
        } catch (err) {
            setError(getErrorMessage(err, rule.is_saved ? 'Unable to remove saved file.' : 'Unable to save file.'))
        } finally {
            setSavingKey('')
        }
    }

    const toggleSavedBundle = async (bundle: Bundle) => {
        try {
            setSavingKey(`bundle:${bundle.id}`)
            if (bundle.is_saved) {
                await unsaveBundle(bundle.id)
            } else {
                await saveBundle(bundle.id)
            }
            setFilteredBundles((current) => current.map((item) => (
                item.id === bundle.id
                    ? { ...item, is_saved: !bundle.is_saved, save_count: Math.max(0, item.save_count + (bundle.is_saved ? -1 : 1)) }
                    : item
            )))
            setError('')
        } catch (err) {
            setError(getErrorMessage(err, bundle.is_saved ? 'Unable to remove saved bundle.' : 'Unable to save bundle.'))
        } finally {
            setSavingKey('')
        }
    }

    const handleActivateBundle = async (bundle: Bundle) => {
        if (!activeGameSystem?.id) return
        try {
            setActivatingBundleId(bundle.id)
            await setActiveBundle(activeGameSystem.id, bundle.id)
            setFilteredBundles((current) => current.map((item) => ({ ...item, is_default: item.id === bundle.id })))
            setError('')
        } catch (err) {
            setError(getErrorMessage(err, 'Unable to use that bundle for chat.'))
        } finally {
            setActivatingBundleId(null)
        }
    }

    const isBundleActive = (bundle: Bundle) => activeBundle?.id === bundle.id

    return (
        <div className="page-scroll">
            <div className="page-container page-container--wide">
                <div className="page-header">
                    <h1>Browse Game Rules</h1>
                    <p>Explore rulebooks and community bundles for {activeGameSystem?.name || 'your selected game system'}.</p>
                </div>

                <div className="tabs">
                    <div className="tabs__list tabs__list--compact">
                        <button type="button" className={`tabs__trigger${view === 'files' ? ' is-active' : ''}`} onClick={() => setView('files')}>
                            Files
                        </button>
                        <button type="button" className={`tabs__trigger${view === 'bundles' ? ' is-active' : ''}`} onClick={() => setView('bundles')}>
                            Bundles
                        </button>
                    </div>
                </div>

                <div className="search-field">
                    <Search className="search-field__icon" size={20} />
                    <input
                        placeholder={view === 'files' ? 'Search by title, description, or tags...' : 'Search bundles or included files...'}
                        value={search}
                        onChange={(event) => setSearch(event.target.value)}
                        className="text-input text-input--with-icon"
                        maxLength={200}
                    />
                </div>

                <div className="page-section-stack">
                    {view === 'files' && filteredRules.map((rule) => (
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
                                <div className="browse-card__actions">
                                    {session?.authenticated && (
                                        <button
                                            type="button"
                                            className={`icon-button icon-button--ghost${rule.is_saved ? ' icon-button--selected' : ''}`}
                                            onClick={() => void toggleSavedFile(rule)}
                                            disabled={savingKey === `file:${rule.id}`}
                                            aria-label={rule.is_saved ? `Remove ${rule.title} from saved files` : `Save ${rule.title}`}
                                            title={rule.is_saved ? 'Saved' : 'Save file'}
                                        >
                                            <Star size={16} fill={rule.is_saved ? 'currentColor' : 'none'} />
                                        </button>
                                    )}
                                    <div className="stat-row">
                                        <div className="stat-item">
                                            <span>{rule.save_count} save{rule.save_count === 1 ? '' : 's'}</span>
                                        </div>
                                    </div>
                                </div>
                                <a className="primary-button primary-button--inline" href={`${apiBase}/viewer/${rule.id}`} target="_blank" rel="noreferrer">
                                    View File
                                </a>
                            </div>
                        </article>
                    ))}

                    {view === 'bundles' && filteredBundles.map((bundle) => (
                        <article key={bundle.id} className="surface-card browse-card">
                            <div className="browse-card__main">
                                <h3>{bundle.title}</h3>
                                <p className="browse-card__description">
                                    {bundle.description || `${bundle.file_count} file${bundle.file_count === 1 ? '' : 's'} in this bundle.`}
                                </p>
                                <div className="tag-list">
                                    {bundle.game_system && (
                                        <span className="tag-badge tag-badge--game-system">{bundle.game_system.name}</span>
                                    )}
                                    <span className="tag-badge">{bundle.file_count} file{bundle.file_count === 1 ? '' : 's'}</span>
                                    <span className="tag-badge">{bundle.is_public ? 'Public' : 'Private'}</span>
                                    {bundle.is_owned && <span className="tag-badge">Yours</span>}
                                    {isBundleActive(bundle) && <span className="tag-badge tag-badge--selected">Active in Chat</span>}
                                </div>
                                {!!bundle.preview_titles.length && (
                                    <p className="bundle-preview">
                                        Includes: {bundle.preview_titles.join(', ')}
                                    </p>
                                )}
                                <div className="meta-row">
                                    <span>By {bundle.owner_name}</span>
                                </div>
                            </div>
                            <div className="browse-card__side">
                                <div className="browse-card__actions">
                                    {session?.authenticated && (
                                        <button
                                            type="button"
                                            className={`icon-button icon-button--ghost${bundle.is_saved ? ' icon-button--selected' : ''}`}
                                            onClick={() => void toggleSavedBundle(bundle)}
                                            disabled={savingKey === `bundle:${bundle.id}`}
                                            aria-label={bundle.is_saved ? `Remove ${bundle.title} from saved bundles` : `Save ${bundle.title}`}
                                            title={bundle.is_saved ? 'Saved bundle' : 'Save bundle'}
                                        >
                                            <Star size={16} fill={bundle.is_saved ? 'currentColor' : 'none'} />
                                        </button>
                                    )}
                                    <div className="stat-row">
                                        <div className="stat-item">
                                            <span>{bundle.save_count} save{bundle.save_count === 1 ? '' : 's'}</span>
                                        </div>
                                    </div>
                                </div>
                                {session?.authenticated && (
                                    <button
                                        type="button"
                                        className={isBundleActive(bundle) ? 'secondary-button primary-button--inline' : 'primary-button primary-button--inline'}
                                        onClick={() => void handleActivateBundle(bundle)}
                                        disabled={activatingBundleId === bundle.id || isBundleActive(bundle)}
                                    >
                                        {isBundleActive(bundle) ? 'Using in Chat' : 'Use in Chat'}
                                    </button>
                                )}
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
                        <p>Select a game system to browse matching content.</p>
                    </div>
                )}

                {!filteredRules.length && !error && activeGameSystem && view === 'files' && (
                    <div className="empty-state">
                        <p>No files found matching your search.</p>
                    </div>
                )}

                {!filteredBundles.length && !error && activeGameSystem && view === 'bundles' && (
                    <div className="empty-state">
                        <p>No bundles found matching your search.</p>
                    </div>
                )}
            </div>
        </div>
    )
}

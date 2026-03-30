import { useEffect, useState } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'
import { FileText, FolderOpen, Menu, MessageSquare, User, X } from 'lucide-react'
import { useAppContext } from '../context/AppContext'

const navigation = [
    { name: 'Chat', path: '/', icon: MessageSquare },
    { name: 'Browse', path: '/browse', icon: FolderOpen },
    { name: 'Manage', path: '/manage', icon: FileText },
    { name: 'Account', path: '/account', icon: User },
]

export function Root() {
    const { session, sessionError } = useAppContext()
    const location = useLocation()
    const [open, setOpen] = useState(false)

    useEffect(() => {
        setOpen(false)
    }, [location.pathname])

    return (
        <div className="template-shell">
            <div className="template-mobile-header">
                <div className="template-brand-cluster">
                    <h1 className="template-brand-title">Cogitator</h1>
                </div>
                <button className="icon-button icon-button--ghost" type="button" onClick={() => setOpen(true)} aria-label="Open menu">
                    <Menu size={20} />
                </button>
            </div>

            {open && (
                <div className="sheet" role="dialog" aria-modal="true">
                    <button className="sheet__overlay" type="button" aria-label="Close menu" onClick={() => setOpen(false)} />
                    <aside className="sheet__panel">
                        <div className="sheet__header">
                            <h2>Menu</h2>
                            <button className="icon-button icon-button--ghost" type="button" onClick={() => setOpen(false)} aria-label="Close menu">
                                <X size={18} />
                            </button>
                        </div>
                        <nav className="template-nav-list">
                            {navigation.map((item) => {
                                const Icon = item.icon
                                const isActive = item.path === '/'
                                    ? location.pathname === item.path
                                    : (location.pathname === item.path || location.pathname.startsWith(`${item.path}/`))
                                return (
                                    <Link
                                        key={item.path}
                                        to={item.path}
                                        onClick={() => setOpen(false)}
                                        className={`template-nav-link${isActive ? ' is-active' : ''}`}
                                    >
                                        <Icon size={20} />
                                        <span>{item.name}</span>
                                    </Link>
                                )
                            })}
                        </nav>
                    </aside>
                </div>
            )}

            <div className="template-desktop-header">
                <div className="template-desktop-header__inner">
                    <div className="template-brand-cluster">
                        <h1 className="template-brand-title">Cogitator</h1>
                    </div>
                    <nav className="template-desktop-nav">
                        {navigation.map((item) => {
                            const Icon = item.icon
                            const isActive = item.path === '/'
                                ? location.pathname === item.path
                                : (location.pathname === item.path || location.pathname.startsWith(`${item.path}/`))
                            return (
                                <Link key={item.path} to={item.path} className={`template-nav-tab${isActive ? ' is-active' : ''}`}>
                                    <Icon size={16} />
                                    <span>{item.name}</span>
                                </Link>
                            )
                        })}
                    </nav>
                </div>
            </div>

            <div className="template-shell__content">
                {sessionError && (
                    <div className="page-container">
                        <div className="notice notice--error" role="alert">
                            <p>{sessionError}</p>
                        </div>
                    </div>
                )}
                {session?.user?.account_status === 'suspended' && (
                    <div className="page-container">
                        <div className="notice notice--warning" role="alert">
                            <p>{session.user.dmca_suspension_reason || 'This account is suspended under the repeat copyright infringer policy.'}</p>
                        </div>
                    </div>
                )}
                <Outlet />
            </div>
            <footer className="template-footer">
                <div className="template-footer__inner">
                    <p>Operate responsibly: only publish material you are authorized to distribute.</p>
                    <div className="template-footer__links">
                        <Link to="/legal/terms">Terms</Link>
                        <Link to="/legal/copyright">Copyright Policy</Link>
                    </div>
                </div>
            </footer>
        </div>
    )
}

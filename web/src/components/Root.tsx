import { useState } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'
import { FileText, FolderOpen, Menu, MessageSquare, Upload, User, X } from 'lucide-react'

const navigation = [
    { name: 'Chat', path: '/', icon: MessageSquare },
    { name: 'Upload', path: '/upload', icon: Upload },
    { name: 'Browse', path: '/browse', icon: FolderOpen },
    { name: 'Manage', path: '/manage', icon: FileText },
    { name: 'Account', path: '/account', icon: User },
]

export function Root() {
    const location = useLocation()
    const [open, setOpen] = useState(false)

    return (
        <div className="template-shell">
            <div className="template-mobile-header">
                <h1 className="template-brand-title">Lexmechanicus</h1>
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
                                const isActive = location.pathname === item.path
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
                    <h1 className="template-brand-title">Lexmechanicus</h1>
                    <nav className="template-desktop-nav">
                        {navigation.map((item) => {
                            const Icon = item.icon
                            const isActive = location.pathname === item.path
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
                <Outlet />
            </div>
        </div>
    )
}

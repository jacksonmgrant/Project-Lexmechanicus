import { useEffect, useState } from 'react'
import { Bell, Database, Key, User } from 'lucide-react'
import { useAppContext } from '../../context/AppContext'

export function AccountPage() {
    const { changePassword, listFiles, login, logout, session, signup } = useAppContext()
    const [email, setEmail] = useState(session?.user?.email || '')
    const [authPassword, setAuthPassword] = useState('')
    const [mode, setMode] = useState<'login' | 'signup'>('login')
    const [currentPassword, setCurrentPassword] = useState('')
    const [newPassword, setNewPassword] = useState('')
    const [confirmPassword, setConfirmPassword] = useState('')
    const [notifications, setNotifications] = useState(true)
    const [message, setMessage] = useState('')
    const [storageBytes, setStorageBytes] = useState(0)

    useEffect(() => {
        if (!session?.authenticated) {
            setStorageBytes(0)
            return
        }
        listFiles('mine')
            .then((files) => setStorageBytes(files.reduce((sum, file) => sum + file.size_bytes, 0)))
            .catch(() => undefined)
    }, [listFiles, session])

    useEffect(() => {
        if (!session?.authenticated) return
        setEmail(session.user?.email || '')
    }, [session])

    const handleAuth = async () => {
        try {
            const result = mode === 'login' ? await login(email, authPassword) : await signup(email, authPassword)
            setMessage(result)
            setAuthPassword('')
        } catch (error) {
            setMessage(error instanceof Error ? error.message : 'Unable to authenticate.')
        }
    }

    const handlePasswordUpdate = async () => {
        if (newPassword !== confirmPassword) {
            setMessage('New passwords do not match.')
            return
        }
        try {
            const result = await changePassword(currentPassword, newPassword)
            setMessage(result)
            setCurrentPassword('')
            setNewPassword('')
            setConfirmPassword('')
        } catch (error) {
            setMessage(error instanceof Error ? error.message : 'Unable to update your password.')
        }
    }

    return (
        <div className="page-scroll">
            <div className="page-container page-container--narrow">
                <div className="page-header">
                    <h1>Account Settings</h1>
                    <p>Manage your profile and application preferences.</p>
                </div>

                <div className="page-section-stack">
                    {!session?.authenticated && (
                        <section className="surface-card">
                            <div className="section-header">
                                <User className="accent-icon" size={20} />
                                <h2>{mode === 'login' ? 'Sign In' : 'Create Account'}</h2>
                            </div>
                            <div className="form-stack">
                                <div className="field-group">
                                    <label htmlFor="account-email">Email Address</label>
                                    <input id="account-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} className="text-input" />
                                </div>
                                <div className="field-group">
                                    <label htmlFor="account-password">Password</label>
                                    <input id="account-password" type="password" value={authPassword} onChange={(event) => setAuthPassword(event.target.value)} className="text-input" />
                                </div>
                                <div className="button-row">
                                    <button type="button" className="primary-button primary-button--inline" onClick={handleAuth}>
                                        {mode === 'login' ? 'Sign In' : 'Create Account'}
                                    </button>
                                    <button type="button" className="secondary-button secondary-button--inline" onClick={() => setMode((current) => current === 'login' ? 'signup' : 'login')}>
                                        {mode === 'login' ? 'Need an account?' : 'Already have an account?'}
                                    </button>
                                </div>
                            </div>
                        </section>
                    )}

                    {session?.authenticated && (
                        <section className="surface-card">
                            <div className="section-header">
                                <User className="accent-icon" size={20} />
                                <h2>Profile Information</h2>
                            </div>
                            <div className="form-stack">
                                <div className="field-group">
                                    <label htmlFor="name">Display Name</label>
                                    <input id="name" value={session.user?.email?.split('@')[0] || 'User'} readOnly className="text-input" />
                                </div>
                                <div className="field-group">
                                    <label htmlFor="email">Email Address</label>
                                    <input id="email" type="email" value={session.user?.email || ''} readOnly className="text-input" />
                                </div>
                                <div className="button-row">
                                    <button type="button" className="primary-button primary-button--inline" onClick={logout}>Sign Out</button>
                                </div>
                            </div>
                        </section>
                    )}

                    <section className="surface-card">
                        <div className="section-header">
                            <Key className="accent-icon" size={20} />
                            <h2>Security</h2>
                        </div>
                        <div className="form-stack">
                            <div className="field-group">
                                <label htmlFor="current-password">Current Password</label>
                                <input id="current-password" type="password" placeholder="••••••••" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} className="text-input" />
                            </div>
                            <div className="field-group">
                                <label htmlFor="new-password">New Password</label>
                                <input id="new-password" type="password" placeholder="••••••••" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} className="text-input" />
                            </div>
                            <div className="field-group">
                                <label htmlFor="confirm-password">Confirm New Password</label>
                                <input id="confirm-password" type="password" placeholder="••••••••" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} className="text-input" />
                            </div>
                            <button type="button" className="primary-button primary-button--inline" onClick={handlePasswordUpdate} disabled={!session?.authenticated}>
                                Update Password
                            </button>
                        </div>
                    </section>

                    <section className="surface-card">
                        <div className="section-header">
                            <Bell className="accent-icon" size={20} />
                            <h2>Notifications</h2>
                        </div>
                        <div className="toggle-row">
                            <div>
                                <p className="toggle-row__title">Email Notifications</p>
                                <p className="toggle-row__description">Receive updates about new rule uploads and system changes</p>
                            </div>
                            <input type="checkbox" checked={notifications} onChange={(event) => setNotifications(event.target.checked)} className="checkbox-input" />
                        </div>
                    </section>

                    <section className="surface-card">
                        <div className="section-header">
                            <Database className="accent-icon" size={20} />
                            <h2>Storage</h2>
                        </div>
                        <div className="form-stack">
                            <div>
                                <div className="storage-meter__label">
                                    <span>Used Storage</span>
                                    <span>{(storageBytes / (1024 * 1024)).toFixed(1)} MB / 1 GB</span>
                                </div>
                                <div className="storage-meter">
                                    <div className="storage-meter__fill" style={{ width: `${Math.min((storageBytes / (1024 * 1024 * 1024)) * 100, 100)}%` }} />
                                </div>
                            </div>
                            <p className="body-muted">You have plenty of space available for uploading game rules.</p>
                        </div>
                    </section>

                    <section className="surface-card surface-card--danger">
                        <h2 className="danger-title">Danger Zone</h2>
                        <div className="form-stack">
                            <p className="body-muted">Account deletion is not exposed by the backend yet. Sign out from the profile section to end your current session.</p>
                            <button type="button" className="danger-button" disabled>
                                Delete Account
                            </button>
                        </div>
                    </section>

                    {!!message && (
                        <div className="empty-state">
                            <p>{message}</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}

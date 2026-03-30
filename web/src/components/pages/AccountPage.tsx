import { useEffect, useState } from 'react'
import { Bell, Database, Key, User } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAppContext } from '../../context/AppContext'
import { getErrorMessage } from '../../lib/api'

function EyeIcon({ hidden }: { hidden: boolean }) {
    return hidden ? (
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path
                fill="currentColor"
                d="M2,5.27L3.28,4L20,20.72L18.73,22L15.65,18.92C14.5,19.3 13.28,19.5 12,19.5C7,19.5 2.73,16.39 1,12C1.69,10.24 2.79,8.69 4.19,7.46L2,5.27M12,9A3,3 0 0,1 15,12C15,12.35 14.94,12.69 14.83,13L11,9.17C11.31,9.06 11.65,9 12,9M12,4.5C17,4.5 21.27,7.61 23,12C22.44,13.43 21.6,14.69 20.57,15.75L16.58,11.76C16.86,8.8 14.68,6.14 11.72,5.85C10.2,5.71 8.7,6.2 7.56,7.19L5.6,5.23C7.38,4.76 9.18,4.5 12,4.5Z"
            />
        </svg>
    ) : (
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path
                fill="currentColor"
                d="M12,4.5C17,4.5 21.27,7.61 23,12C21.27,16.39 17,19.5 12,19.5C7,19.5 2.73,16.39 1,12C2.73,7.61 7,4.5 12,4.5M12,7A5,5 0 0,0 7,12A5,5 0 0,0 12,17A5,5 0 0,0 17,12A5,5 0 0,0 12,7M12,9A3,3 0 0,1 15,12A3,3 0 0,1 12,15A3,3 0 0,1 9,12A3,3 0 0,1 12,9Z"
            />
        </svg>
    )
}

type PasswordFieldProps = {
    id: string
    label: string
    value: string
    hidden: boolean
    placeholder?: string
    onChange: (value: string) => void
    onToggle: () => void
}

function PasswordField({ id, label, value, hidden, placeholder, onChange, onToggle }: PasswordFieldProps) {
    return (
        <div className="field-group">
            <label htmlFor={id}>{label}</label>
            <div className="password-input-wrap">
                <input
                    id={id}
                    type={hidden ? 'password' : 'text'}
                    placeholder={placeholder}
                    value={value}
                    onChange={(event) => onChange(event.target.value)}
                    className="text-input text-input--with-password-toggle"
                    minLength={8}
                    maxLength={200}
                />
                <button
                    type="button"
                    className="password-toggle"
                    onClick={onToggle}
                    aria-label={hidden ? `Show ${label.toLowerCase()}` : `Hide ${label.toLowerCase()}`}
                    aria-pressed={!hidden}
                >
                    <EyeIcon hidden={hidden} />
                </button>
            </div>
        </div>
    )
}

export function AccountPage() {
    const { changePassword, listFiles, login, logout, session, signup, updateProfile } = useAppContext()
    const [email, setEmail] = useState(session?.user?.email || '')
    const [displayName, setDisplayName] = useState(session?.user?.display_name || '')
    const [authPassword, setAuthPassword] = useState('')
    const [isAuthPasswordHidden, setIsAuthPasswordHidden] = useState(true)
    const [mode, setMode] = useState<'login' | 'signup'>('login')
    const [currentPassword, setCurrentPassword] = useState('')
    const [isCurrentPasswordHidden, setIsCurrentPasswordHidden] = useState(true)
    const [newPassword, setNewPassword] = useState('')
    const [isNewPasswordHidden, setIsNewPasswordHidden] = useState(true)
    const [confirmPassword, setConfirmPassword] = useState('')
    const [isConfirmPasswordHidden, setIsConfirmPasswordHidden] = useState(true)
    const [notifications, setNotifications] = useState(false)
    const [message, setMessage] = useState('')
    const [messageType, setMessageType] = useState<'error' | 'success'>('success')
    const [storageBytes, setStorageBytes] = useState(0)
    const [isSavingProfile, setIsSavingProfile] = useState(false)

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
        setDisplayName(session.user?.display_name || '')
    }, [session])

    const validateEmail = (value: string) => /\S+@\S+\.\S+/.test(value.trim())
    const hasProfileChanges = session?.authenticated && displayName.trim() !== (session.user?.display_name || '')

    const handleAuth = async () => {
        const normalizedEmail = email.trim()
        const normalizedDisplayName = displayName.trim()
        if (!validateEmail(normalizedEmail)) {
            setMessageType('error')
            setMessage('Enter a valid email address.')
            return
        }
        if (authPassword.length < 8) {
            setMessageType('error')
            setMessage('Passwords must be at least 8 characters long.')
            return
        }
        if (mode === 'signup' && !normalizedDisplayName) {
            setMessageType('error')
            setMessage('Enter a display name to create your account.')
            return
        }

        try {
            const result = mode === 'login'
                ? await login(normalizedEmail, authPassword)
                : await signup(normalizedDisplayName, normalizedEmail, authPassword)
            setMessageType('success')
            setMessage(result)
            setAuthPassword('')
        } catch (error) {
            setMessageType('error')
            setMessage(getErrorMessage(error, 'Unable to authenticate.'))
        }
    }

    const handlePasswordUpdate = async () => {
        if (!session?.authenticated) {
            setMessageType('error')
            setMessage('Sign in before updating your password.')
            return
        }
        if (!currentPassword || !newPassword || !confirmPassword) {
            setMessageType('error')
            setMessage('Fill in all password fields before updating your password.')
            return
        }
        if (newPassword.length < 8) {
            setMessageType('error')
            setMessage('New passwords must be at least 8 characters long.')
            return
        }
        if (newPassword !== confirmPassword) {
            setMessageType('error')
            setMessage('New passwords do not match.')
            return
        }
        if (newPassword === currentPassword) {
            setMessageType('error')
            setMessage('Choose a new password that is different from your current password.')
            return
        }
        try {
            const result = await changePassword(currentPassword, newPassword)
            setMessageType('success')
            setMessage(result)
            setCurrentPassword('')
            setNewPassword('')
            setConfirmPassword('')
        } catch (error) {
            setMessageType('error')
            setMessage(getErrorMessage(error, 'Unable to update your password.'))
        }
    }

    const handleProfileUpdate = async () => {
        if (!session?.authenticated) {
            setMessageType('error')
            setMessage('Sign in before updating your profile.')
            return
        }
        try {
            setIsSavingProfile(true)
            const result = await updateProfile(displayName)
            setMessageType('success')
            setMessage(result)
        } catch (error) {
            setMessageType('error')
            setMessage(getErrorMessage(error, 'Unable to update your profile.'))
        } finally {
            setIsSavingProfile(false)
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
                    {session?.user?.account_status === 'suspended' && (
                        <div className="notice notice--warning" role="alert">
                            <p>{session.user.dmca_suspension_reason || 'This account is suspended under the repeat copyright infringer policy.'}</p>
                        </div>
                    )}

                    {!session?.authenticated && (
                        <section className="surface-card">
                            <div className="section-header">
                                <User className="accent-icon" size={20} />
                                <h2>{mode === 'login' ? 'Sign In' : 'Create Account'}</h2>
                            </div>
                            <div className="form-stack">
                                {mode === 'signup' && (
                                    <div className="field-group">
                                        <label htmlFor="account-display-name">Display Name</label>
                                        <input
                                            id="account-display-name"
                                            type="text"
                                            value={displayName}
                                            onChange={(event) => setDisplayName(event.target.value)}
                                            className="text-input"
                                            maxLength={120}
                                        />
                                    </div>
                                )}
                                <div className="field-group">
                                    <label htmlFor="account-email">Email Address</label>
                                    <input id="account-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} className="text-input" maxLength={255} />
                                </div>
                                <PasswordField
                                    id="account-password"
                                    label="Password"
                                    value={authPassword}
                                    hidden={isAuthPasswordHidden}
                                    onChange={setAuthPassword}
                                    onToggle={() => setIsAuthPasswordHidden((current) => !current)}
                                />
                                <div className="button-row">
                                    <button type="button" className="primary-button primary-button--inline" onClick={handleAuth}>
                                        {mode === 'login' ? 'Sign In' : 'Create Account'}
                                    </button>
                                    <button type="button" className="secondary-button secondary-button--inline" onClick={() => setMode((current) => current === 'login' ? 'signup' : 'login')}>
                                        {mode === 'login' ? 'Need an account?' : 'Already have an account?'}
                                    </button>
                                </div>
                                {mode === 'signup' && (
                                    <p className="field-help">
                                        By creating an account, you agree to the <Link className="inline-link" to="/legal/terms">Terms</Link> and understand the <Link className="inline-link" to="/legal/copyright">Copyright Policy</Link>.
                                    </p>
                                )}
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
                                    <input
                                        id="name"
                                        value={displayName}
                                        onChange={(event) => setDisplayName(event.target.value)}
                                        className="text-input"
                                        maxLength={120}
                                        placeholder="Anonymous"
                                    />
                                </div>
                                <div className="field-group">
                                    <label htmlFor="email">Email Address</label>
                                    <input id="email" type="email" value={session.user?.email || ''} readOnly className="text-input" />
                                </div>
                                <div className="button-row">
                                    <button
                                        type="button"
                                        className="secondary-button secondary-button--inline"
                                        onClick={handleProfileUpdate}
                                        disabled={!hasProfileChanges || isSavingProfile}
                                    >
                                        {isSavingProfile ? 'Saving...' : 'Save Profile'}
                                    </button>
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
                            <PasswordField
                                id="current-password"
                                label="Current Password"
                                value={currentPassword}
                                hidden={isCurrentPasswordHidden}
                                placeholder="••••••••"
                                onChange={setCurrentPassword}
                                onToggle={() => setIsCurrentPasswordHidden((current) => !current)}
                            />
                            <PasswordField
                                id="new-password"
                                label="New Password"
                                value={newPassword}
                                hidden={isNewPasswordHidden}
                                placeholder="••••••••"
                                onChange={setNewPassword}
                                onToggle={() => setIsNewPasswordHidden((current) => !current)}
                            />
                            <PasswordField
                                id="confirm-password"
                                label="Confirm New Password"
                                value={confirmPassword}
                                hidden={isConfirmPasswordHidden}
                                placeholder="••••••••"
                                onChange={setConfirmPassword}
                                onToggle={() => setIsConfirmPasswordHidden((current) => !current)}
                            />
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
                        <div className={`notice ${messageType === 'error' ? 'notice--error' : 'notice--success'}`} role={messageType === 'error' ? 'alert' : 'status'}>
                            <p>{message}</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}

import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useAppContext } from '../../context/AppContext'
import { getErrorMessage, requestJson } from '../../lib/api'

type LegalInfo = {
    service_provider: {
        legal_name: string
        address?: string | null
        alternate_names: string[]
    }
    dmca_agent: {
        name?: string | null
        organization?: string | null
        email?: string | null
        phone?: string | null
        address?: string | null
        configured: boolean
    }
    repeat_infringer_threshold: number
    terms_version: string
    last_updated: string
}

type NoticeForm = {
    claimantName: string
    claimantEmail: string
    claimantPhone: string
    claimantAddress: string
    copyrightOwnerName: string
    workDescription: string
    materialLocation: string
    infringementExplanation: string
    signature: string
    goodFaithStatementConfirmed: boolean
    accuracyStatementConfirmed: boolean
    authorityStatementConfirmed: boolean
}

type CounterForm = {
    claimantName: string
    claimantEmail: string
    claimantPhone: string
    claimantAddress: string
    counterExplanation: string
    signature: string
    mistakeStatementConfirmed: boolean
    perjuryStatementConfirmed: boolean
    jurisdictionStatementConfirmed: boolean
}

function buildNoticeForm(session: ReturnType<typeof useAppContext>['session']): NoticeForm {
    return {
        claimantName: session?.user?.display_name || '',
        claimantEmail: session?.user?.email || '',
        claimantPhone: '',
        claimantAddress: '',
        copyrightOwnerName: '',
        workDescription: '',
        materialLocation: '',
        infringementExplanation: '',
        signature: session?.user?.display_name || '',
        goodFaithStatementConfirmed: false,
        accuracyStatementConfirmed: false,
        authorityStatementConfirmed: false,
    }
}

function buildCounterForm(session: ReturnType<typeof useAppContext>['session']): CounterForm {
    return {
        claimantName: session?.user?.display_name || '',
        claimantEmail: session?.user?.email || '',
        claimantPhone: '',
        claimantAddress: '',
        counterExplanation: '',
        signature: session?.user?.display_name || '',
        mistakeStatementConfirmed: false,
        perjuryStatementConfirmed: false,
        jurisdictionStatementConfirmed: false,
    }
}

export function CopyrightPolicyPage() {
    const {
        apiBase,
        session,
        getCopyrightStatus,
        submitCopyrightCounterNotice,
        submitCopyrightTakedown,
    } = useAppContext()
    const [params] = useSearchParams()
    const [legalInfo, setLegalInfo] = useState<LegalInfo | null>(null)
    const [statusError, setStatusError] = useState('')
    const [legalError, setLegalError] = useState('')
    const [successMessage, setSuccessMessage] = useState('')
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [copyrightStatus, setCopyrightStatus] = useState<Awaited<ReturnType<typeof getCopyrightStatus>> | null>(null)
    const [noticeForm, setNoticeForm] = useState<NoticeForm>(() => buildNoticeForm(session))
    const [counterForm, setCounterForm] = useState<CounterForm>(() => buildCounterForm(session))

    const fileId = Number(params.get('file_id') || '')
    const mode = params.get('mode') === 'counter' ? 'counter' : 'notice'
    const hasFileId = Number.isInteger(fileId) && fileId > 0

    useEffect(() => {
        setNoticeForm((current) => ({
            ...buildNoticeForm(session),
            materialLocation: current.materialLocation || copyrightStatus?.file.viewer_url || '',
        }))
        setCounterForm(buildCounterForm(session))
    }, [copyrightStatus?.file.viewer_url, session])

    useEffect(() => {
        requestJson<LegalInfo>(`${apiBase}/legal/info`, {
            operation: 'Load legal info',
            fallbackMessage: 'Unable to load legal information.',
        })
            .then((payload) => {
                setLegalInfo(payload)
                setLegalError('')
            })
            .catch((err) => {
                setLegalError(getErrorMessage(err, 'Unable to load legal information.'))
            })
    }, [apiBase])

    useEffect(() => {
        if (!hasFileId) {
            setCopyrightStatus(null)
            setStatusError('')
            return
        }
        getCopyrightStatus(fileId)
            .then((payload) => {
                setCopyrightStatus(payload)
                setNoticeForm((current) => ({
                    ...current,
                    materialLocation: current.materialLocation || payload.file.viewer_url,
                }))
                setStatusError('')
            })
            .catch((err) => {
                setCopyrightStatus(null)
                setStatusError(getErrorMessage(err, 'Unable to load the selected file.'))
            })
    }, [fileId, getCopyrightStatus, hasFileId])

    const pageTitle = useMemo(() => mode === 'counter' ? 'DMCA Counter-Notice' : 'DMCA Takedown Notice', [mode])

    const handleNoticeSubmit = async () => {
        if (!hasFileId || isSubmitting) return
        try {
            setIsSubmitting(true)
            const result = await submitCopyrightTakedown(fileId, noticeForm)
            setSuccessMessage(
                result.admin_notified
                    ? 'Your DMCA notice has been sent to the admin team for review.'
                    : 'Your DMCA notice was recorded, but the admin notification email could not be sent automatically.',
            )
            setStatusError('')
        } catch (err) {
            setStatusError(getErrorMessage(err, 'Unable to submit the DMCA notice.'))
        } finally {
            setIsSubmitting(false)
        }
    }

    const handleCounterSubmit = async () => {
        if (!hasFileId || isSubmitting) return
        try {
            setIsSubmitting(true)
            const result = await submitCopyrightCounterNotice(fileId, counterForm)
            setSuccessMessage(
                result.admin_notified
                    ? 'Your counter-notice has been sent to the admin team for review.'
                    : 'Your counter-notice was recorded, but the admin notification email could not be sent automatically.',
            )
            setStatusError('')
        } catch (err) {
            setStatusError(getErrorMessage(err, 'Unable to submit the counter-notice.'))
        } finally {
            setIsSubmitting(false)
        }
    }

    const latestNotice = copyrightStatus?.latest_notice

    return (
        <div className="page-scroll">
            <div className="page-container page-container--narrow">
                <div className="page-header">
                    <h1>Copyright Policy</h1>
                    <p>Submit a formal DMCA notice for public content or a counter-notice for disabled content you uploaded.</p>
                </div>

                <div className="tabs">
                    <div className="tabs__list tabs__list--compact">
                        <Link className={`tabs__trigger${mode === 'notice' ? ' is-active' : ''}`} to={hasFileId ? `/legal/copyright?file_id=${fileId}&mode=notice` : '/legal/copyright?mode=notice'}>
                            Notice
                        </Link>
                        <Link className={`tabs__trigger${mode === 'counter' ? ' is-active' : ''}`} to={hasFileId ? `/legal/copyright?file_id=${fileId}&mode=counter` : '/legal/copyright?mode=counter'}>
                            Counter-Notice
                        </Link>
                    </div>
                </div>

                {legalError && (
                    <div className="notice notice--error" role="alert">
                        <p>{legalError}</p>
                    </div>
                )}

                {statusError && (
                    <div className="notice notice--error" role="alert">
                        <p>{statusError}</p>
                    </div>
                )}

                {successMessage && (
                    <div className="notice notice--success" role="status">
                        <p>{successMessage}</p>
                    </div>
                )}

                {legalInfo && !legalInfo.dmca_agent.configured && (
                    <div className="notice notice--warning" role="alert">
                        <p>The designated DMCA agent details are not fully configured yet. Set and register them before operating the public service.</p>
                    </div>
                )}

                <div className="page-section-stack">
                    {copyrightStatus && (
                        <section className="surface-card legal-card">
                            <h2>Selected File</h2>
                            <p><strong>{copyrightStatus.file.title}</strong></p>
                            <p>{copyrightStatus.file.filename}</p>
                            <p>Uploader: {copyrightStatus.file.uploader_name}</p>
                            <p>Viewer URL: <a className="inline-link" href={copyrightStatus.file.viewer_url} target="_blank" rel="noreferrer">{copyrightStatus.file.viewer_url}</a></p>
                            {latestNotice && (
                                <p>Latest claim status: {latestNotice.status}</p>
                            )}
                        </section>
                    )}

                    {!hasFileId && (
                        <section className="surface-card legal-card">
                            <h2>{pageTitle}</h2>
                            <p>Open this page from a file card so the notice can be attached to a specific hosted file. You can still use the agent contact details below for offline or manual notices.</p>
                        </section>
                    )}

                    {mode === 'notice' && hasFileId && (
                        <section className="surface-card legal-card">
                            <h2>Submit DMCA Notice</h2>
                            <div className="form-stack">
                                <div className="field-group">
                                    <label htmlFor="notice-name">Your full legal name</label>
                                    <input id="notice-name" className="text-input" value={noticeForm.claimantName} onChange={(event) => setNoticeForm((current) => ({ ...current, claimantName: event.target.value }))} maxLength={120} />
                                </div>
                                <div className="field-group">
                                    <label htmlFor="notice-email">Email address</label>
                                    <input id="notice-email" className="text-input" type="email" value={noticeForm.claimantEmail} onChange={(event) => setNoticeForm((current) => ({ ...current, claimantEmail: event.target.value }))} maxLength={255} />
                                </div>
                                <div className="field-group">
                                    <label htmlFor="notice-phone">Phone number</label>
                                    <input id="notice-phone" className="text-input" value={noticeForm.claimantPhone} onChange={(event) => setNoticeForm((current) => ({ ...current, claimantPhone: event.target.value }))} maxLength={40} />
                                </div>
                                <div className="field-group">
                                    <label htmlFor="notice-address">Mailing address</label>
                                    <textarea id="notice-address" className="text-area" value={noticeForm.claimantAddress} onChange={(event) => setNoticeForm((current) => ({ ...current, claimantAddress: event.target.value }))} maxLength={1000} />
                                </div>
                                <div className="field-group">
                                    <label htmlFor="copyright-owner-name">Copyright owner name</label>
                                    <input id="copyright-owner-name" className="text-input" value={noticeForm.copyrightOwnerName} onChange={(event) => setNoticeForm((current) => ({ ...current, copyrightOwnerName: event.target.value }))} maxLength={160} />
                                </div>
                                <div className="field-group">
                                    <label htmlFor="work-description">Identify the copyrighted work</label>
                                    <textarea id="work-description" className="text-area" value={noticeForm.workDescription} onChange={(event) => setNoticeForm((current) => ({ ...current, workDescription: event.target.value }))} maxLength={2000} />
                                </div>
                                <div className="field-group">
                                    <label htmlFor="material-location">Location of the reported material</label>
                                    <textarea id="material-location" className="text-area" value={noticeForm.materialLocation} onChange={(event) => setNoticeForm((current) => ({ ...current, materialLocation: event.target.value }))} maxLength={1000} />
                                </div>
                                <div className="field-group">
                                    <label htmlFor="infringement-explanation">Additional explanation</label>
                                    <textarea id="infringement-explanation" className="text-area" value={noticeForm.infringementExplanation} onChange={(event) => setNoticeForm((current) => ({ ...current, infringementExplanation: event.target.value }))} maxLength={4000} />
                                </div>
                                <div className="field-group">
                                    <label htmlFor="notice-signature">Electronic signature</label>
                                    <input id="notice-signature" className="text-input" value={noticeForm.signature} onChange={(event) => setNoticeForm((current) => ({ ...current, signature: event.target.value }))} maxLength={255} />
                                </div>
                                <label className="checkbox-row" htmlFor="good-faith-confirmed">
                                    <input id="good-faith-confirmed" className="checkbox-input" type="checkbox" checked={noticeForm.goodFaithStatementConfirmed} onChange={(event) => setNoticeForm((current) => ({ ...current, goodFaithStatementConfirmed: event.target.checked }))} />
                                    <span>I have a good-faith belief that this use is not authorized by the copyright owner, its agent, or the law.</span>
                                </label>
                                <label className="checkbox-row" htmlFor="accuracy-confirmed">
                                    <input id="accuracy-confirmed" className="checkbox-input" type="checkbox" checked={noticeForm.accuracyStatementConfirmed} onChange={(event) => setNoticeForm((current) => ({ ...current, accuracyStatementConfirmed: event.target.checked }))} />
                                    <span>The information in this notice is accurate, and under penalty of perjury I am authorized to act on behalf of the copyright owner.</span>
                                </label>
                                <label className="checkbox-row" htmlFor="authority-confirmed">
                                    <input id="authority-confirmed" className="checkbox-input" type="checkbox" checked={noticeForm.authorityStatementConfirmed} onChange={(event) => setNoticeForm((current) => ({ ...current, authorityStatementConfirmed: event.target.checked }))} />
                                    <span>I am the copyright owner or am authorized to act on the copyright owner's behalf.</span>
                                </label>
                                <button type="button" className="primary-button" disabled={isSubmitting} onClick={() => void handleNoticeSubmit()}>
                                    {isSubmitting ? 'Submitting...' : 'Submit DMCA Notice'}
                                </button>
                            </div>
                        </section>
                    )}

                    {mode === 'counter' && (
                        <section className="surface-card legal-card">
                            <h2>Submit Counter-Notice</h2>
                            {!session?.authenticated ? (
                                <p>Sign in to the account that uploaded the file before submitting a counter-notice.</p>
                            ) : !hasFileId ? (
                                <p>Open this page from a file in your Manage view so the counter-notice can be attached to the disabled upload.</p>
                            ) : latestNotice?.status !== 'disabled' ? (
                                <p>This file does not currently have an active disabled DMCA claim that accepts a counter-notice.</p>
                            ) : (
                                <div className="form-stack">
                                    <div className="field-group">
                                        <label htmlFor="counter-name">Your full legal name</label>
                                        <input id="counter-name" className="text-input" value={counterForm.claimantName} onChange={(event) => setCounterForm((current) => ({ ...current, claimantName: event.target.value }))} maxLength={120} />
                                    </div>
                                    <div className="field-group">
                                        <label htmlFor="counter-email">Email address</label>
                                        <input id="counter-email" className="text-input" type="email" value={counterForm.claimantEmail} onChange={(event) => setCounterForm((current) => ({ ...current, claimantEmail: event.target.value }))} maxLength={255} />
                                    </div>
                                    <div className="field-group">
                                        <label htmlFor="counter-phone">Phone number</label>
                                        <input id="counter-phone" className="text-input" value={counterForm.claimantPhone} onChange={(event) => setCounterForm((current) => ({ ...current, claimantPhone: event.target.value }))} maxLength={40} />
                                    </div>
                                    <div className="field-group">
                                        <label htmlFor="counter-address">Mailing address</label>
                                        <textarea id="counter-address" className="text-area" value={counterForm.claimantAddress} onChange={(event) => setCounterForm((current) => ({ ...current, claimantAddress: event.target.value }))} maxLength={1000} />
                                    </div>
                                    <div className="field-group">
                                        <label htmlFor="counter-explanation">Explain why the material was removed by mistake or misidentification</label>
                                        <textarea id="counter-explanation" className="text-area" value={counterForm.counterExplanation} onChange={(event) => setCounterForm((current) => ({ ...current, counterExplanation: event.target.value }))} maxLength={4000} />
                                    </div>
                                    <div className="field-group">
                                        <label htmlFor="counter-signature">Electronic signature</label>
                                        <input id="counter-signature" className="text-input" value={counterForm.signature} onChange={(event) => setCounterForm((current) => ({ ...current, signature: event.target.value }))} maxLength={255} />
                                    </div>
                                    <label className="checkbox-row" htmlFor="mistake-confirmed">
                                        <input id="mistake-confirmed" className="checkbox-input" type="checkbox" checked={counterForm.mistakeStatementConfirmed} onChange={(event) => setCounterForm((current) => ({ ...current, mistakeStatementConfirmed: event.target.checked }))} />
                                        <span>I consent to removal being reversed because the material was removed or disabled by mistake or misidentification.</span>
                                    </label>
                                    <label className="checkbox-row" htmlFor="perjury-confirmed">
                                        <input id="perjury-confirmed" className="checkbox-input" type="checkbox" checked={counterForm.perjuryStatementConfirmed} onChange={(event) => setCounterForm((current) => ({ ...current, perjuryStatementConfirmed: event.target.checked }))} />
                                        <span>Under penalty of perjury, I believe the material was removed or disabled as a result of mistake or misidentification.</span>
                                    </label>
                                    <label className="checkbox-row" htmlFor="jurisdiction-confirmed">
                                        <input id="jurisdiction-confirmed" className="checkbox-input" type="checkbox" checked={counterForm.jurisdictionStatementConfirmed} onChange={(event) => setCounterForm((current) => ({ ...current, jurisdictionStatementConfirmed: event.target.checked }))} />
                                        <span>I consent to the jurisdiction of the appropriate federal district court and will accept service of process from the claimant or their agent.</span>
                                    </label>
                                    <button type="button" className="primary-button" disabled={isSubmitting} onClick={() => void handleCounterSubmit()}>
                                        {isSubmitting ? 'Submitting...' : 'Submit Counter-Notice'}
                                    </button>
                                </div>
                            )}
                        </section>
                    )}

                    <section className="surface-card legal-card">
                        <h2>Designated DMCA Agent</h2>
                        <p>{legalInfo?.dmca_agent.organization || legalInfo?.service_provider.legal_name || 'RuleFinder'}</p>
                        {legalInfo?.dmca_agent.name && <p>{legalInfo.dmca_agent.name}</p>}
                        {legalInfo?.dmca_agent.email && <p>Email: <a className="inline-link" href={`mailto:${legalInfo.dmca_agent.email}`}>{legalInfo.dmca_agent.email}</a></p>}
                        {legalInfo?.dmca_agent.phone && <p>Phone: {legalInfo.dmca_agent.phone}</p>}
                        {legalInfo?.dmca_agent.address && <p>{legalInfo.dmca_agent.address}</p>}
                        <p>Last updated: {legalInfo?.last_updated || '2026-03-27'}</p>
                    </section>
                </div>
            </div>
        </div>
    )
}

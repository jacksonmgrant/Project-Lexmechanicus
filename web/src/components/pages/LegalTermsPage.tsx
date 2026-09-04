import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
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

export function LegalTermsPage() {
    const { apiBase } = useAppContext()
    const [legalInfo, setLegalInfo] = useState<LegalInfo | null>(null)
    const [error, setError] = useState('')

    useEffect(() => {
        requestJson<LegalInfo>(`${apiBase}/legal/info`, {
            operation: 'Load legal info',
            fallbackMessage: 'Unable to load legal information.',
        })
            .then((payload) => {
                setLegalInfo(payload)
                setError('')
            })
            .catch((err) => {
                setError(getErrorMessage(err, 'Unable to load legal information.'))
            })
    }, [apiBase])

    return (
        <div className="page-scroll">
            <div className="page-container page-container--narrow">
                <div className="page-header">
                    <h1>Terms of Use</h1>
                    <p>These terms explain the publishing rules and copyright expectations for RuleFinder.</p>
                </div>

                {error && (
                    <div className="notice notice--error" role="alert">
                        <p>{error}</p>
                    </div>
                )}

                {legalInfo && !legalInfo.dmca_agent.configured && (
                    <div className="notice notice--warning" role="alert">
                        <p>The designated DMCA agent details are not fully configured yet. Set and register them before operating the public service.</p>
                    </div>
                )}

                <div className="page-section-stack">
                    <section className="surface-card legal-card">
                        <h2>Publishing Rules</h2>
                        <p>Only upload material you own, are licensed to use, that is in the public domain, or that you otherwise have a clear legal right to store and share.</p>
                        <p>Do not make copyrighted material public unless you have the right to distribute it. Public uploads and public bundles may be disabled without warning when a valid copyright complaint is received.</p>
                    </section>

                    <section className="surface-card legal-card">
                        <h2>Copyright Policy</h2>
                        <p>RuleFinder responds to DMCA notices and counter-notices for public content hosted through the service.</p>
                        <p>Use the <Link className="inline-link" to="/legal/copyright">Copyright Policy</Link> page to submit a formal notice, review the required statements, and learn how counter-notices are handled.</p>
                    </section>

                    <section className="surface-card legal-card">
                        <h2>Repeat Infringer Policy</h2>
                        <p>Accounts may be suspended or terminated in appropriate circumstances when repeated approved copyright claims are recorded against them.</p>
                        <p>The current suspension threshold is {Math.max(1, legalInfo?.repeat_infringer_threshold || 0)} approved DMCA notice{Math.max(1, legalInfo?.repeat_infringer_threshold || 0) === 1 ? '' : 's'}.</p>
                    </section>

                    <section className="surface-card legal-card">
                        <h2>Service Provider</h2>
                        <p>{legalInfo?.service_provider.legal_name || 'RuleFinder'}</p>
                        {legalInfo?.service_provider.address && <p>{legalInfo.service_provider.address}</p>}
                        {!!legalInfo?.service_provider.alternate_names.length && (
                            <p>Alternate names: {legalInfo.service_provider.alternate_names.join(', ')}</p>
                        )}
                        <p>Terms version: {legalInfo?.terms_version || '2026-03-27'}</p>
                        <p>Last updated: {legalInfo?.last_updated || '2026-03-27'}</p>
                    </section>
                </div>
            </div>
        </div>
    )
}

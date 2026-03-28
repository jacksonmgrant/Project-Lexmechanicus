import type { ChatCitation } from '../context/AppContext'


type CitationPreviewCardProps = {
    citation: ChatCitation
    onOpenCitation: (citation: ChatCitation) => void
}


export function CitationPreviewCard({
    citation,
    onOpenCitation,
}: CitationPreviewCardProps) {
    return (
        <button
            type="button"
            className="citation-preview-card"
            onClick={() => onOpenCitation(citation)}
            title={`Open ${citation.document_title} page ${citation.page_number || 1}`}
        >
            <div className="citation-preview-card__body">
                <p className="citation-preview-card__meta">
                    <strong>{citation.document_title}</strong>
                    <span>Page {citation.page_number || 1}</span>
                </p>
                {citation.section && <p className="citation-preview-card__section">{citation.section}</p>}
                {citation.excerpt_text && <p className="citation-preview-card__excerpt">"{citation.excerpt_text}"</p>}
            </div>
        </button>
    )
}

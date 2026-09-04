import { useEffect, useRef, useState } from 'react'
import { Send, X } from 'lucide-react'
import { ChatCitation, ChatHistoryTurn, useAppContext } from '../../context/AppContext'
import { apiErrorFromPayload, getErrorMessage, readResponsePayload } from '../../lib/api'
import { ActiveGameSystemDropdown } from '../ActiveGameSystemDropdown'
import { ActiveBundleDropdown } from '../ActiveBundleDropdown'
import { CitationPreviewCard } from '../CitationPreviewCard'

type Message = {
    id: string
    role: 'user' | 'assistant'
    content: string
    citations?: ChatCitation[]
}

function normalizeAssistantText(content: string): string {
    return content
        .replace(/([a-zA-Z])(\d)/g, '$1 $2')
        .replace(/(\d)([a-zA-Z])/g, '$1 $2')
        .replace(/\s+([.,!?;:])/g, '$1')
        .replace(/ {2,}/g, ' ')
        .replace(/\n{3,}/g, '\n\n')
}

function getReferencedCitations(content: string, citations: ChatCitation[]): ChatCitation[] {
    const citedIds = Array.from(content.matchAll(/\[\[(c\d+)\]\]/g), (match) => match[1])
    if (!citedIds.length) {
        return citations
    }

    const citationsById = new Map(citations.map((citation) => [citation.id, citation]))
    const ordered: ChatCitation[] = []
    for (const citationId of citedIds) {
        const citation = citationsById.get(citationId)
        if (!citation || ordered.some((item) => item.id === citation.id)) {
            continue
        }
        ordered.push(citation)
    }
    return ordered
}

function renderAssistantMessage(content: string): React.ReactNode {
    const prepared = content
        .replace(/(\S)(\[\[c\d+\]\])/g, '$1 $2')
        .replace(/(\[\[c\d+\]\])(?=\S)/g, ' ')
        .replace(/\[\[c\d+\]\]/g, '')
        .trim()

    return normalizeAssistantText(prepared)
}

function buildThreadHistory(messages: Message[]): ChatHistoryTurn[] {
    return messages
        .filter((message) => message.id !== '1')
        .filter((message) => message.content.trim())
        .slice(-6)
        .map((message) => ({
            role: message.role,
            content: message.content,
        }))
}

export function ChatPage() {
    const { activeBundle, activeGameSystem, apiBase, guestId, session, streamAsk, token } = useAppContext()
    const [messages, setMessages] = useState<Message[]>([
        {
            id: '1',
            role: 'assistant',
            content: "Hello! Welcome to RuleFinder. Ask me anything about the files tied to your current game system.",
            citations: [],
        },
    ])
    const [input, setInput] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState('')
    const [viewerCitation, setViewerCitation] = useState<ChatCitation | null>(null)
    const [viewerUrl, setViewerUrl] = useState('')
    const [viewerLoading, setViewerLoading] = useState(false)
    const [viewerError, setViewerError] = useState('')
    const scrollRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight
        }
    }, [messages])

    useEffect(() => {
        if (!viewerCitation) {
            setViewerUrl('')
            setViewerError('')
            setViewerLoading(false)
            return
        }

        let cancelled = false
        let objectUrl = ''

        const loadDocument = async () => {
            setViewerLoading(true)
            setViewerError('')
            setViewerUrl('')

            try {
                const headers: Record<string, string> = {}
                if (guestId.trim()) headers['X-Guest-Id'] = guestId
                if (token.trim()) headers.Authorization = `Bearer ${token}`
                const response = await fetch(`${apiBase}/viewer/${viewerCitation.file_id}`, { headers })
                if (!response.ok) {
                    const payload = await readResponsePayload(response)
                    throw apiErrorFromPayload(payload, response.status, 'Unable to load the cited document.')
                }

                const blob = await response.blob()
                objectUrl = URL.createObjectURL(blob)
                if (!cancelled) {
                    setViewerUrl(objectUrl)
                }
            } catch (nextError) {
                if (!cancelled) {
                    setViewerError(getErrorMessage(nextError, 'Unable to load the cited document.'))
                }
            } finally {
                if (!cancelled) {
                    setViewerLoading(false)
                }
            }
        }

        loadDocument().catch(() => undefined)

        return () => {
            cancelled = true
            if (objectUrl) {
                URL.revokeObjectURL(objectUrl)
            }
        }
    }, [apiBase, guestId, token, viewerCitation])

    const handleSend = async () => {
        const normalizedInput = input.trim()
        if (isLoading) return
        if (!normalizedInput) {
            setError('Enter a question before sending.')
            return
        }
        if (!activeGameSystem) {
            setError('Choose a game system before chatting.')
            return
        }
        if (normalizedInput.length > 500) {
            setError('Keep your question under 500 characters.')
            return
        }

        const userMessage: Message = {
            id: Date.now().toString(),
            role: 'user',
            content: normalizedInput,
        }
        const threadHistory = buildThreadHistory(messages)

        const assistantId = (Date.now() + 1).toString()
        let latestCitations: ChatCitation[] = []
        setMessages((prev) => [...prev, userMessage])
        setInput('')
        setError('')
        setIsLoading(true)

        try {
            await streamAsk(
                userMessage.content,
                threadHistory,
                (delta) => {
                    setMessages((prev) => {
                        const assistantMessage = prev.find((message) => message.id === assistantId)
                        if (!assistantMessage) {
                            return [...prev, { id: assistantId, role: 'assistant', content: delta, citations: latestCitations }]
                        }

                        return prev.map((message) =>
                            message.id === assistantId
                                ? { ...message, content: message.content + delta }
                                : message,
                        )
                    })
                },
                (citations) => {
                    latestCitations = citations
                    setMessages((prev) => {
                        const assistantMessage = prev.find((message) => message.id === assistantId)
                        if (!assistantMessage) {
                            return prev
                        }

                        return prev.map((message) =>
                            message.id === assistantId
                                ? { ...message, citations }
                                : message,
                        )
                    })
                },
            )
            setMessages((prev) => {
                const assistantMessage = prev.find((message) => message.id === assistantId)
                if (assistantMessage) return prev
                return [...prev, { id: assistantId, role: 'assistant', content: 'No answer was returned for that question.', citations: [] }]
            })
        } catch (nextError) {
            const detail = getErrorMessage(nextError, 'Unable to complete the request.')
            setError(detail)
            setMessages((prev) => {
                const assistantMessage = prev.find((message) => message.id === assistantId)
                if (!assistantMessage) {
                    return [...prev, { id: assistantId, role: 'assistant', content: detail, citations: [] }]
                }

                return prev.map((message) =>
                    message.id === assistantId ? { ...message, content: detail } : message,
                )
            })
        } finally {
            setIsLoading(false)
        }
    }

    const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault()
            handleSend()
        }
    }

    return (
        <div className="page-chat">
            <div className="chat-topbar">
                <div className="chat-topbar__inner">
                    <div className="chat-topbar__controls">
                        <div>
                            <p className="chat-topbar__eyebrow">Current Game System</p>
                            <ActiveGameSystemDropdown />
                        </div>
                        <div>
                            <p className="chat-topbar__eyebrow">Reading Bundle</p>
                            <ActiveBundleDropdown />
                        </div>
                    </div>
                </div>
            </div>
            <div className="page-chat__messages" ref={scrollRef}>
                <div className="message-stack">
                    {messages.map((message) => (
                        <div key={message.id} className={`message-row message-row--${message.role}`}>
                            <div className={`message-bubble message-bubble--${message.role}`}>
                                <p>
                                    {message.role === 'assistant'
                                        ? renderAssistantMessage(message.content)
                                        : message.content}
                                </p>
                                {message.role === 'assistant' && getReferencedCitations(message.content, message.citations || []).length > 0 && (
                                    <div className="citation-preview-strip">
                                        {getReferencedCitations(message.content, message.citations || []).map((citation) => (
                                            <CitationPreviewCard
                                                key={citation.id}
                                                citation={citation}
                                                onOpenCitation={setViewerCitation}
                                            />
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                    {isLoading && (
                        <div className="message-row message-row--assistant">
                            <div className="message-bubble message-bubble--assistant message-bubble--loading">
                                <div className="typing-dots">
                                    <span />
                                    <span />
                                    <span />
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            <div className="chat-input-bar">
                <div className="chat-input-bar__inner">
                    <div className="chat-input-wrap">
                        <textarea
                            value={input}
                            onChange={(event) => setInput(event.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder="Ask about game rules..."
                            className="chat-textarea"
                            rows={1}
                            maxLength={500}
                        />
                        <button
                            type="button"
                            onClick={handleSend}
                            disabled={!input.trim() || isLoading}
                            className="icon-button icon-button--primary"
                            aria-label="Send"
                        >
                            <Send size={16} />
                        </button>
                    </div>
                    <p className="page-caption">
                        {activeBundle
                            ? `Using bundle "${activeBundle.title}" for ${activeGameSystem?.name || 'your selected game system'}`
                            : session?.authenticated
                                ? `Using your uploaded and saved files for ${activeGameSystem?.name || 'your selected game system'}`
                                : `Using public files for ${activeGameSystem?.name || 'your selected game system'}`}
                    </p>
                    {error && (
                        <div className="notice notice--error" role="alert">
                            <p>{error}</p>
                        </div>
                    )}
                </div>
            </div>

            {viewerCitation && (
                <div className="viewer-sheet" role="dialog" aria-modal="true">
                    <button className="viewer-sheet__overlay" type="button" aria-label="Close citation viewer" onClick={() => setViewerCitation(null)} />
                    <div className="viewer-sheet__panel">
                        <div className="viewer-sheet__header">
                            <div>
                                <h2>{viewerCitation.document_title}</h2>
                                <p>Page {viewerCitation.page_number || 1}</p>
                            </div>
                            <button className="icon-button icon-button--ghost" type="button" onClick={() => setViewerCitation(null)} aria-label="Close citation viewer">
                                <X size={18} />
                            </button>
                        </div>
                        <div className="viewer-sheet__body">
                            {viewerLoading && <p className="page-caption">Loading document...</p>}
                            {viewerError && (
                                <div className="notice notice--error" role="alert">
                                    <p>{viewerError}</p>
                                </div>
                            )}
                            {!viewerLoading && !viewerError && viewerUrl && (
                                <iframe
                                    className="viewer-sheet__frame"
                                    src={viewerCitation.mime_type === 'application/pdf'
                                        ? `${viewerUrl}#page=${viewerCitation.page_number || 1}`
                                        : viewerUrl}
                                    title={`${viewerCitation.document_title} page ${viewerCitation.page_number || 1}`}
                                />
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}

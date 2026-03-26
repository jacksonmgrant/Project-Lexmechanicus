import { useEffect, useRef, useState } from 'react'
import { Send } from 'lucide-react'
import { useAppContext } from '../../context/AppContext'

type Message = {
    id: string
    role: 'user' | 'assistant'
    content: string
}

export function ChatPage() {
    const { streamAsk, session } = useAppContext()
    const [messages, setMessages] = useState<Message[]>([
        {
            id: '1',
            role: 'assistant',
            content: "Hello! Welcome to Lexmechanicus, your assistant for game rules. Ask me anything about game rules from uploaded documents.",
        },
    ])
    const [input, setInput] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const scrollRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight
        }
    }, [messages])

    const handleSend = async () => {
        if (!input.trim() || isLoading) return

        const userMessage: Message = {
            id: Date.now().toString(),
            role: 'user',
            content: input,
        }

        const assistantId = (Date.now() + 1).toString()
        setMessages((prev) => [...prev, userMessage])
        setInput('')
        setIsLoading(true)

        try {
            await streamAsk(userMessage.content, (delta) => {
                setMessages((prev) => {
                    const assistantMessage = prev.find((message) => message.id === assistantId)
                    if (!assistantMessage) {
                        return [...prev, { id: assistantId, role: 'assistant', content: delta }]
                    }

                    return prev.map((message) =>
                        message.id === assistantId
                            ? { ...message, content: message.content + delta }
                            : message,
                    )
                })
            })
            setMessages((prev) => {
                const assistantMessage = prev.find((message) => message.id === assistantId)
                if (assistantMessage) return prev
                return [...prev, { id: assistantId, role: 'assistant', content: 'No answer was returned for that question.' }]
            })
        } catch (error) {
            const detail = error instanceof Error ? error.message : 'Unable to complete the request.'
            setMessages((prev) => {
                const assistantMessage = prev.find((message) => message.id === assistantId)
                if (!assistantMessage) {
                    return [...prev, { id: assistantId, role: 'assistant', content: detail }]
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
            <div className="page-chat__messages" ref={scrollRef}>
                <div className="message-stack">
                    {messages.map((message) => (
                        <div key={message.id} className={`message-row message-row--${message.role}`}>
                            <div className={`message-bubble message-bubble--${message.role}`}>
                                <p>{message.content}</p>
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
                        {session?.authenticated
                            ? 'Ask questions about game rules from your uploaded documents'
                            : 'Ask questions as a guest or create an account for upload and search features'}
                    </p>
                </div>
            </div>
        </div>
    )
}

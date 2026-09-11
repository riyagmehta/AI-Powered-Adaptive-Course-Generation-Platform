import { type FormEvent, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { apiUrl } from '../lib/api'
import { streamSSE } from '../lib/sse'

export interface DoubtHistoryItem {
  doubtId: number
  question: string
  answer: string
  cacheHit: boolean
}

interface DoubtDrawerProps {
  moduleId: number
  isOpen: boolean
  onClose: () => void
  history: DoubtHistoryItem[]
  onNewDoubt: (item: DoubtHistoryItem) => void
}

export function DoubtDrawer({ moduleId, isOpen, onClose, history, onNewDoubt }: DoubtDrawerProps) {
  const [question, setQuestion] = useState('')
  const [draftAnswer, setDraftAnswer] = useState('')
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const q = question.trim()
    if (!q || isStreaming) return

    setError(null)
    setPendingQuestion(q)
    setDraftAnswer('')
    setQuestion('')
    setIsStreaming(true)

    let answer = ''
    try {
      await streamSSE(apiUrl('/doubts'), {
        method: 'POST',
        body: { module_id: moduleId, question: q },
        onEvent: ({ event, data }) => {
          if (event === 'chunk') {
            answer += data.delta as string
            setDraftAnswer(answer)
          } else if (event === 'done') {
            onNewDoubt({
              doubtId: data.doubt_id as number,
              question: q,
              answer,
              cacheHit: data.cache_hit as boolean,
            })
          } else if (event === 'error') {
            setError(data.detail as string)
          }
        },
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get an answer.')
    } finally {
      setIsStreaming(false)
      setPendingQuestion(null)
      setDraftAnswer('')
    }
  }

  return (
    <div
      className={`fixed inset-y-0 right-0 z-40 flex w-full max-w-md transform flex-col border-l border-slate-200 bg-white shadow-xl transition-transform ${
        isOpen ? 'translate-x-0' : 'translate-x-full'
      }`}
    >
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <h2 className="font-medium text-slate-900">Ask a doubt</h2>
        <button onClick={onClose} className="text-slate-400 hover:text-slate-700">
          ✕
        </button>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {history.length === 0 && !pendingQuestion && (
          <p className="text-sm text-slate-400">Ask anything about this module's content.</p>
        )}
        {history.map((item) => (
          <div key={item.doubtId} className="space-y-1">
            <p className="text-sm font-medium text-slate-800">{item.question}</p>
            <div className="prose-content text-sm text-slate-600">
              <ReactMarkdown>{item.answer}</ReactMarkdown>
            </div>
            {item.cacheHit && <span className="text-xs text-slate-400">(cached answer)</span>}
          </div>
        ))}
        {pendingQuestion && (
          <div className="space-y-1">
            <p className="text-sm font-medium text-slate-800">{pendingQuestion}</p>
            <div className="prose-content text-sm text-slate-600">
              <ReactMarkdown>{draftAnswer}</ReactMarkdown>
              <span className="ml-0.5 inline-block h-3 w-1.5 animate-pulse bg-slate-400 align-text-bottom" />
            </div>
          </div>
        )}
        {error && <p className="text-sm text-red-600">{error}</p>}
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2 border-t border-slate-200 p-3">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question…"
          disabled={isStreaming}
          className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={isStreaming || !question.trim()}
          className="rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          Ask
        </button>
      </form>
    </div>
  )
}

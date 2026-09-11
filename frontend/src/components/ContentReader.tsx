import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface ContentReaderProps {
  content: string
  isGenerating: boolean
  error: string | null
  onRetry: () => void
}

export function ContentReader({ content, isGenerating, error, onRetry }: ContentReaderProps) {
  if (error) {
    return (
      <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">
        <p className="mb-2">{error}</p>
        <button
          onClick={onRetry}
          className="rounded-md border border-red-300 bg-white px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-100"
        >
          Retry
        </button>
      </div>
    )
  }

  if (isGenerating) {
    return (
      <div className="flex items-center gap-2 text-slate-500">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
        Generating lesson content&hellip; this runs as a background job and usually takes a few seconds.
      </div>
    )
  }

  if (!content) {
    return <p className="text-slate-400">Select a module to view its content.</p>
  }

  return (
    <div className="prose-content max-w-none">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  )
}

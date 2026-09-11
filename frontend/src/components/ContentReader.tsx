import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface ContentReaderProps {
  content: string
  isStreaming: boolean
  error: string | null
}

export function ContentReader({ content, isStreaming, error }: ContentReaderProps) {
  if (error) {
    return <p className="rounded-md bg-red-50 p-4 text-sm text-red-700">{error}</p>
  }

  if (!content && isStreaming) {
    return (
      <div className="flex items-center gap-2 text-slate-500">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
        Generating lesson content&hellip;
      </div>
    )
  }

  if (!content) {
    return <p className="text-slate-400">Select a module to view its content.</p>
  }

  return (
    <div className="prose-content max-w-none">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      {isStreaming && <span className="ml-0.5 inline-block h-4 w-2 animate-pulse bg-slate-400 align-text-bottom" />}
    </div>
  )
}

import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ContentReader } from '../components/ContentReader'
import { DoubtDrawer, type DoubtHistoryItem } from '../components/DoubtDrawer'
import { ModuleSidebar } from '../components/ModuleSidebar'
import { NavBar } from '../components/NavBar'
import { api, apiUrl } from '../lib/api'
import { SSEHttpError, streamSSE } from '../lib/sse'
import type { CourseDetail } from '../types/api'

export function CoursePage() {
  const { courseId } = useParams<{ courseId: string }>()
  const [course, setCourse] = useState<CourseDetail | null>(null)
  const [selectedModuleId, setSelectedModuleId] = useState<number | null>(null)
  const [content, setContent] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamError, setStreamError] = useState<string | null>(null)
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)
  const [doubtHistory, setDoubtHistory] = useState<Record<number, DoubtHistoryItem[]>>({})
  const abortRef = useRef<AbortController | null>(null)

  const fetchCourse = useCallback(async () => {
    const { data } = await api.get<CourseDetail>(`/courses/${courseId}`)
    setCourse(data)
    return data
  }, [courseId])

  useEffect(() => {
    fetchCourse().then((data) => {
      if (data.modules.length > 0) {
        setSelectedModuleId(data.modules[0].id)
      }
    })
  }, [fetchCourse])

  useEffect(() => {
    if (selectedModuleId === null) return

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    let pollTimer: ReturnType<typeof setTimeout> | undefined

    setContent('')
    setStreamError(null)
    setIsStreaming(true)

    // A background task on the server may already be generating the first
    // module of a freshly created course. If so, the stream endpoint returns
    // 409 — fall back to polling the course until that generation finishes.
    async function pollUntilReady() {
      while (!controller.signal.aborted) {
        const data = await fetchCourse()
        const module = data.modules.find((m) => m.id === selectedModuleId)
        if (!module) return
        if (module.status === 'completed') {
          setContent(module.content ?? '')
          setIsStreaming(false)
          return
        }
        if (module.status === 'failed') {
          setStreamError('Module generation failed. Please try again.')
          setIsStreaming(false)
          return
        }
        await new Promise<void>((resolve) => {
          pollTimer = setTimeout(resolve, 1500)
        })
      }
    }

    async function run() {
      try {
        await streamSSE(apiUrl(`/modules/${selectedModuleId}/stream`), {
          signal: controller.signal,
          onEvent: ({ event, data }) => {
            if (event === 'chunk') {
              setContent((prev) => prev + (data.delta as string))
            } else if (event === 'done') {
              setIsStreaming(false)
              fetchCourse()
            } else if (event === 'error') {
              setStreamError(data.detail as string)
              setIsStreaming(false)
            }
          },
        })
      } catch (err) {
        if (controller.signal.aborted) return
        if (err instanceof SSEHttpError && err.status === 409) {
          await pollUntilReady()
          return
        }
        setStreamError(err instanceof Error ? err.message : 'Failed to load content.')
        setIsStreaming(false)
      }
    }

    run()

    return () => {
      controller.abort()
      if (pollTimer) clearTimeout(pollTimer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedModuleId])

  if (!course) {
    return (
      <div className="min-h-screen bg-slate-50">
        <NavBar />
        <p className="p-8 text-slate-500">Loading course&hellip;</p>
      </div>
    )
  }

  const selectedModule = course.modules.find((m) => m.id === selectedModuleId) ?? null

  return (
    <div className="min-h-screen bg-slate-50">
      <NavBar />

      <div className="border-b border-slate-200 bg-white px-6 py-4">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-slate-900">{course.title}</h1>
            <p className="text-sm text-slate-500">{course.description}</p>
          </div>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium capitalize text-slate-600">
            {course.current_difficulty}
          </span>
        </div>
      </div>

      <div className="mx-auto flex max-w-6xl">
        <ModuleSidebar modules={course.modules} selectedModuleId={selectedModuleId} onSelect={setSelectedModuleId} />

        <main className="flex-1 px-8 py-6">
          {selectedModule && (
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-semibold text-slate-900">{selectedModule.title}</h2>
              <div className="flex gap-2">
                <button
                  onClick={() => setIsDrawerOpen(true)}
                  disabled={selectedModule.status !== 'completed'}
                  className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100 disabled:opacity-40"
                >
                  Ask a doubt
                </button>
                {selectedModule.status === 'completed' ? (
                  <Link
                    to={`/courses/${course.id}/modules/${selectedModule.id}/quiz`}
                    className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800"
                  >
                    Take quiz
                  </Link>
                ) : (
                  <button
                    disabled
                    className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white opacity-40"
                  >
                    Take quiz
                  </button>
                )}
              </div>
            </div>
          )}

          <ContentReader content={content} isStreaming={isStreaming} error={streamError} />
        </main>
      </div>

      {selectedModuleId !== null && (
        <DoubtDrawer
          moduleId={selectedModuleId}
          isOpen={isDrawerOpen}
          onClose={() => setIsDrawerOpen(false)}
          history={doubtHistory[selectedModuleId] ?? []}
          onNewDoubt={(item) =>
            setDoubtHistory((prev) => ({
              ...prev,
              [selectedModuleId]: [...(prev[selectedModuleId] ?? []), item],
            }))
          }
        />
      )}
    </div>
  )
}

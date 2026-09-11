import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ContentReader } from '../components/ContentReader'
import { DoubtDrawer, type DoubtHistoryItem } from '../components/DoubtDrawer'
import { ModuleSidebar } from '../components/ModuleSidebar'
import { NavBar } from '../components/NavBar'
import { api } from '../lib/api'
import { extractErrorMessage } from '../store/authStore'
import { toast } from '../store/toastStore'
import type { CourseDetail, GenerationJobRead } from '../types/api'

const POLL_INTERVAL_MS = 1500

export function CoursePage() {
  const { courseId } = useParams<{ courseId: string }>()
  const [course, setCourse] = useState<CourseDetail | null>(null)
  const [selectedModuleId, setSelectedModuleId] = useState<number | null>(null)
  const [content, setContent] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [generationError, setGenerationError] = useState<string | null>(null)
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)
  const [doubtHistory, setDoubtHistory] = useState<Record<number, DoubtHistoryItem[]>>({})
  const cancelledRef = useRef(false)

  const fetchCourse = useCallback(async () => {
    const { data } = await api.get<CourseDetail>(`/courses/${courseId}`)
    setCourse(data)
    return data
  }, [courseId])

  // Content generation is a durable background job (see backend/app/worker.py),
  // not something tied to this request/connection — so instead of streaming
  // tokens live, we kick off (or join) a job and poll GET /modules/{id}/status
  // until it's done, then fetch the finished content.
  const pollUntilDone = useCallback(
    async (moduleId: number) => {
      while (!cancelledRef.current) {
        const { data: job } = await api.get<GenerationJobRead>(`/modules/${moduleId}/status`)
        if (cancelledRef.current) return

        if (job.status === 'succeeded') {
          const data = await fetchCourse()
          const module = data.modules.find((m) => m.id === moduleId)
          setContent(module?.content ?? '')
          setIsGenerating(false)
          return
        }
        if (job.status === 'failed') {
          await fetchCourse() // refresh the sidebar badge to "failed" too
          setGenerationError(job.last_error ?? 'Module generation failed.')
          toast.error('Module generation failed.')
          setIsGenerating(false)
          return
        }

        // Keep the sidebar's status badge (pending/generating) in sync while
        // we wait, not just at the very end.
        await fetchCourse()
        await new Promise<void>((resolve) => setTimeout(resolve, POLL_INTERVAL_MS))
      }
    },
    [fetchCourse],
  )

  const startGeneration = useCallback(
    async (moduleId: number) => {
      setGenerationError(null)
      setIsGenerating(true)
      try {
        // Idempotent: a no-op if a job is already queued/running/succeeded.
        await api.post(`/modules/${moduleId}/generate`)
      } catch (err) {
        if (cancelledRef.current) return
        const message = extractErrorMessage(err)
        setGenerationError(message)
        toast.error(message)
        setIsGenerating(false)
        return
      }
      await pollUntilDone(moduleId)
    },
    [pollUntilDone],
  )

  useEffect(() => {
    fetchCourse().then((data) => {
      if (data.modules.length > 0) {
        setSelectedModuleId(data.modules[0].id)
      }
    })
  }, [fetchCourse])

  useEffect(() => {
    if (selectedModuleId === null) return

    cancelledRef.current = false
    setContent('')
    setGenerationError(null)
    setIsGenerating(false)

    fetchCourse().then((data) => {
      if (cancelledRef.current) return
      const module = data.modules.find((m) => m.id === selectedModuleId)
      if (!module) return

      if (module.status === 'completed') {
        setContent(module.content ?? '')
        return
      }
      startGeneration(selectedModuleId)
    })

    return () => {
      cancelledRef.current = true
    }
  }, [selectedModuleId, fetchCourse, startGeneration])

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

          <ContentReader
            content={content}
            isGenerating={isGenerating}
            error={generationError}
            onRetry={() => selectedModuleId !== null && startGeneration(selectedModuleId)}
          />
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

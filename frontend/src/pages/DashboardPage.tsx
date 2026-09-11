import { type FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { NavBar } from '../components/NavBar'
import { api } from '../lib/api'
import { extractErrorMessage } from '../store/authStore'
import { toast } from '../store/toastStore'
import type { CourseDetail, CourseRead } from '../types/api'

export function DashboardPage() {
  const [courses, setCourses] = useState<CourseRead[] | null>(null)
  const [topic, setTopic] = useState('')
  const [numModules, setNumModules] = useState(5)
  const [isCreating, setIsCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    api.get<CourseRead[]>('/courses').then((res) => setCourses(res.data))
  }, [])

  async function handleCreate(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setIsCreating(true)
    try {
      const { data: course } = await api.post<CourseDetail>('/courses', {
        topic: topic.trim() || undefined,
        num_modules: numModules,
      })
      toast.success(`Course "${course.title}" created!`)
      navigate(`/courses/${course.id}`)
    } catch (err) {
      setError(extractErrorMessage(err))
      setIsCreating(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <NavBar />
      <main className="mx-auto max-w-4xl px-4 py-8">
        <h1 className="mb-6 text-2xl font-semibold text-slate-900">Your courses</h1>

        {courses === null && <p className="text-slate-500">Loading&hellip;</p>}

        {courses !== null && courses.length === 0 && (
          <p className="mb-6 text-slate-500">You don't have any courses yet — create one below.</p>
        )}

        {courses !== null && courses.length > 0 && (
          <ul className="mb-8 space-y-3">
            {courses.map((course) => {
              const completedCount = course.modules.filter((m) => m.status === 'completed').length
              return (
                <li key={course.id}>
                  <Link
                    to={`/courses/${course.id}`}
                    className="block rounded-lg border border-slate-200 bg-white p-4 shadow-sm transition hover:border-slate-300"
                  >
                    <div className="flex items-center justify-between">
                      <h2 className="font-medium text-slate-900">{course.title}</h2>
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium capitalize text-slate-600">
                        {course.current_difficulty}
                      </span>
                    </div>
                    {course.description && <p className="mt-1 text-sm text-slate-500">{course.description}</p>}
                    <p className="mt-2 text-xs text-slate-400">
                      {completedCount} / {course.modules.length} modules completed
                    </p>
                  </Link>
                </li>
              )
            })}
          </ul>
        )}

        <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-3 font-medium text-slate-900">Start a new course</h2>
          <form onSubmit={handleCreate} className="space-y-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                Topic <span className="font-normal text-slate-400">(optional — falls back to your learning goal)</span>
              </label>
              <input
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="e.g. Introduction to Bayesian Statistics"
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Number of modules</label>
              <input
                type="number"
                min={3}
                max={8}
                value={numModules}
                onChange={(e) => setNumModules(Number(e.target.value))}
                className="w-24 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
              />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <button
              type="submit"
              disabled={isCreating}
              className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
            >
              {isCreating ? 'Generating outline…' : 'Create course'}
            </button>
          </form>
        </div>
      </main>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { NavBar } from '../components/NavBar'
import { api } from '../lib/api'
import { extractErrorMessage } from '../store/authStore'
import type { QuizAttemptRead, QuizRead } from '../types/api'

export function QuizPage() {
  const { courseId, moduleId } = useParams<{ courseId: string; moduleId: string }>()
  const [quiz, setQuiz] = useState<QuizRead | null>(null)
  const [answers, setAnswers] = useState<number[]>([])
  const [attempt, setAttempt] = useState<QuizAttemptRead | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isGenerating, setIsGenerating] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .get<QuizRead>(`/modules/${moduleId}/quiz`)
      .then((res) => {
        setQuiz(res.data)
        setAnswers(new Array(res.data.questions.length).fill(-1))
      })
      .catch(() => {
        // No quiz yet — the user can generate one.
      })
      .finally(() => setIsLoading(false))
  }, [moduleId])

  async function handleGenerate() {
    setError(null)
    setIsGenerating(true)
    try {
      const { data } = await api.post<QuizRead>(`/modules/${moduleId}/quiz`)
      setQuiz(data)
      setAnswers(new Array(data.questions.length).fill(-1))
      setAttempt(null)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setIsGenerating(false)
    }
  }

  async function handleSubmit() {
    if (!quiz) return
    setError(null)
    setIsSubmitting(true)
    try {
      const { data } = await api.post<QuizAttemptRead>(`/quizzes/${quiz.id}/attempt`, { answers })
      setAttempt(data)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setIsSubmitting(false)
    }
  }

  const allAnswered = answers.length > 0 && answers.every((a) => a >= 0)

  return (
    <div className="min-h-screen bg-slate-50">
      <NavBar />
      <main className="mx-auto max-w-3xl px-4 py-8">
        <Link to={`/courses/${courseId}`} className="mb-4 inline-block text-sm text-slate-500 hover:text-slate-800">
          ← Back to course
        </Link>

        {isLoading && <p className="text-slate-500">Loading&hellip;</p>}

        {!isLoading && !quiz && (
          <div className="rounded-lg border border-slate-200 bg-white p-6 text-center shadow-sm">
            <p className="mb-4 text-slate-600">No quiz has been generated for this module yet.</p>
            <button
              onClick={handleGenerate}
              disabled={isGenerating}
              className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
            >
              {isGenerating ? 'Generating quiz…' : 'Generate quiz'}
            </button>
            {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
          </div>
        )}

        {quiz && !attempt && (
          <div>
            <div className="mb-4 flex items-center justify-between">
              <h1 className="text-xl font-semibold text-slate-900">Quiz</h1>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium capitalize text-slate-600">
                {quiz.difficulty}
              </span>
            </div>

            <div className="space-y-4">
              {quiz.questions.map((q, qIndex) => (
                <div key={qIndex} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                  <p className="mb-3 font-medium text-slate-900">
                    {qIndex + 1}. {q.question}
                  </p>
                  <div className="space-y-2">
                    {q.options.map((option, oIndex) => (
                      <label
                        key={oIndex}
                        className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm ${
                          answers[qIndex] === oIndex ? 'border-slate-900 bg-slate-50' : 'border-slate-200'
                        }`}
                      >
                        <input
                          type="radio"
                          name={`question-${qIndex}`}
                          checked={answers[qIndex] === oIndex}
                          onChange={() =>
                            setAnswers((prev) => prev.map((a, i) => (i === qIndex ? oIndex : a)))
                          }
                        />
                        {option}
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

            <button
              onClick={handleSubmit}
              disabled={!allAnswered || isSubmitting}
              className="mt-6 w-full rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
            >
              {isSubmitting ? 'Submitting…' : 'Submit quiz'}
            </button>
          </div>
        )}

        {attempt && (
          <div>
            <div className="mb-6 rounded-lg border border-slate-200 bg-white p-6 text-center shadow-sm">
              <p className="text-sm text-slate-500">Your score</p>
              <p className="text-4xl font-bold text-slate-900">{attempt.score.toFixed(0)}%</p>
              {attempt.new_difficulty !== attempt.difficulty_at_attempt ? (
                <p className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-sm font-medium text-amber-800">
                  Difficulty changed: <span className="capitalize">{attempt.difficulty_at_attempt}</span> →{' '}
                  <span className="capitalize">{attempt.new_difficulty}</span>
                </p>
              ) : (
                <p className="mt-3 text-sm text-slate-500">
                  Difficulty stays at <span className="capitalize">{attempt.new_difficulty}</span>
                </p>
              )}
            </div>

            <div className="space-y-4">
              {attempt.results.map((r, i) => (
                <div key={i} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                  <p className="mb-2 font-medium text-slate-900">
                    {i + 1}. {r.question}
                  </p>
                  <div className="mb-2 space-y-1">
                    {r.options.map((option, oIndex) => {
                      const isCorrectOption = oIndex === r.correct_index
                      const isSelectedOption = oIndex === r.selected_index
                      return (
                        <div
                          key={oIndex}
                          className={`rounded-md border px-3 py-1.5 text-sm ${
                            isCorrectOption
                              ? 'border-emerald-400 bg-emerald-50 text-emerald-800'
                              : isSelectedOption
                                ? 'border-red-400 bg-red-50 text-red-800'
                                : 'border-slate-200 text-slate-600'
                          }`}
                        >
                          {option}
                          {isCorrectOption && ' ✓'}
                          {isSelectedOption && !isCorrectOption && ' (your answer)'}
                        </div>
                      )
                    })}
                  </div>
                  <p className="text-sm text-slate-500">{r.explanation}</p>
                </div>
              ))}
            </div>

            <div className="mt-6 flex gap-2">
              <button
                onClick={handleGenerate}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-100"
              >
                Generate a new quiz
              </button>
              <Link
                to={`/courses/${courseId}`}
                className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
              >
                Back to course
              </Link>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

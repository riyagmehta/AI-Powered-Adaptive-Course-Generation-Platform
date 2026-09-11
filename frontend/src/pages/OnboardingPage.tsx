import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { extractErrorMessage, useAuthStore } from '../store/authStore'
import { toast } from '../store/toastStore'
import type { CourseDetail } from '../types/api'

const EXPERIENCE_LEVELS = [
  { value: 'beginner', label: 'Beginner', description: "I'm new to this subject" },
  { value: 'intermediate', label: 'Intermediate', description: 'I know the basics' },
  { value: 'advanced', label: 'Advanced', description: 'I have solid working knowledge' },
]

const PACE_OPTIONS = [
  { value: 'slow', label: 'Slow & thorough', description: 'Explain everything in depth' },
  { value: 'moderate', label: 'Moderate', description: 'Balance depth and speed' },
  { value: 'fast', label: 'Fast-paced', description: 'Keep it brief, move quickly' },
]

export function OnboardingPage() {
  const [step, setStep] = useState(1)
  const [learningGoal, setLearningGoal] = useState('')
  const [experienceLevel, setExperienceLevel] = useState('')
  const [preferredPace, setPreferredPace] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { completeOnboarding } = useAuthStore()
  const navigate = useNavigate()

  async function handleFinish() {
    setError(null)
    setIsGenerating(true)
    try {
      await completeOnboarding({
        learning_goal: learningGoal,
        experience_level: experienceLevel,
        preferred_pace: preferredPace,
        onboarding_completed: true,
      })
      const { data: course } = await api.post<CourseDetail>('/courses', {})
      toast.success(`Welcome! Your course "${course.title}" is ready.`)
      navigate(`/courses/${course.id}`)
    } catch (err) {
      setError(extractErrorMessage(err))
      setIsGenerating(false)
    }
  }

  if (isGenerating) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-slate-50 px-4 text-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-300 border-t-slate-900" />
        <p className="text-slate-700">Generating your course outline&hellip;</p>
        <p className="max-w-sm text-sm text-slate-500">
          This calls GPT-4 to design a curriculum tailored to your goal — it can take a few seconds.
        </p>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-lg rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <div className="mb-6 flex items-center gap-2">
          {[1, 2, 3].map((s) => (
            <div key={s} className={`h-1.5 flex-1 rounded-full ${s <= step ? 'bg-slate-900' : 'bg-slate-200'}`} />
          ))}
        </div>

        {step === 1 && (
          <div>
            <h1 className="mb-1 text-lg font-semibold text-slate-900">What do you want to learn?</h1>
            <p className="mb-4 text-sm text-slate-500">Describe your learning goal in a sentence or two.</p>
            <textarea
              autoFocus
              value={learningGoal}
              onChange={(e) => setLearningGoal(e.target.value)}
              rows={4}
              placeholder="e.g. I want to understand Bayesian statistics well enough to apply it to A/B testing at work."
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
            />
            <button
              disabled={!learningGoal.trim()}
              onClick={() => setStep(2)}
              className="mt-4 w-full rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
            >
              Continue
            </button>
          </div>
        )}

        {step === 2 && (
          <div>
            <h1 className="mb-1 text-lg font-semibold text-slate-900">What's your experience level?</h1>
            <p className="mb-4 text-sm text-slate-500">This sets the starting difficulty for your content.</p>
            <div className="space-y-2">
              {EXPERIENCE_LEVELS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setExperienceLevel(opt.value)}
                  className={`w-full rounded-md border px-4 py-3 text-left text-sm transition ${
                    experienceLevel === opt.value
                      ? 'border-slate-900 bg-slate-900 text-white'
                      : 'border-slate-300 hover:border-slate-400'
                  }`}
                >
                  <div className="font-medium">{opt.label}</div>
                  <div className={experienceLevel === opt.value ? 'text-slate-300' : 'text-slate-500'}>
                    {opt.description}
                  </div>
                </button>
              ))}
            </div>
            <div className="mt-4 flex gap-2">
              <button
                onClick={() => setStep(1)}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-100"
              >
                Back
              </button>
              <button
                disabled={!experienceLevel}
                onClick={() => setStep(3)}
                className="flex-1 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
              >
                Continue
              </button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div>
            <h1 className="mb-1 text-lg font-semibold text-slate-900">Preferred learning style?</h1>
            <p className="mb-4 text-sm text-slate-500">How should lessons be paced?</p>
            <div className="space-y-2">
              {PACE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setPreferredPace(opt.value)}
                  className={`w-full rounded-md border px-4 py-3 text-left text-sm transition ${
                    preferredPace === opt.value
                      ? 'border-slate-900 bg-slate-900 text-white'
                      : 'border-slate-300 hover:border-slate-400'
                  }`}
                >
                  <div className="font-medium">{opt.label}</div>
                  <div className={preferredPace === opt.value ? 'text-slate-300' : 'text-slate-500'}>
                    {opt.description}
                  </div>
                </button>
              ))}
            </div>

            {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

            <div className="mt-4 flex gap-2">
              <button
                onClick={() => setStep(2)}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-100"
              >
                Back
              </button>
              <button
                disabled={!preferredPace}
                onClick={handleFinish}
                className="flex-1 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
              >
                Generate my course
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

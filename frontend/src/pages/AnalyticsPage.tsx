import { useEffect, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { NavBar } from '../components/NavBar'
import { api } from '../lib/api'
import type { AnalyticsSummary } from '../types/api'

export function AnalyticsPage() {
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null)

  useEffect(() => {
    api.get<AnalyticsSummary>('/analytics/me').then((res) => setAnalytics(res.data))
  }, [])

  if (!analytics) {
    return (
      <div className="min-h-screen bg-slate-50">
        <NavBar />
        <p className="p-8 text-slate-500">Loading&hellip;</p>
      </div>
    )
  }

  const trendData = analytics.score_trend.map((point, index) => ({
    attempt: index + 1,
    score: point.score,
    date: new Date(point.created_at).toLocaleDateString(),
  }))

  const moduleData = analytics.average_score_by_module.map((stat) => ({
    module: stat.module_title,
    average_score: Math.round(stat.average_score),
    attempts: stat.attempts_count,
  }))

  return (
    <div className="min-h-screen bg-slate-50">
      <NavBar />
      <main className="mx-auto max-w-4xl px-4 py-8">
        <h1 className="mb-6 text-2xl font-semibold text-slate-900">Your analytics</h1>

        <div className="mb-6 grid grid-cols-2 gap-4">
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-sm text-slate-500">Modules completed</p>
            <p className="text-2xl font-bold text-slate-900">
              {analytics.modules_completed} / {analytics.modules_total}
            </p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-sm text-slate-500">Quiz attempts</p>
            <p className="text-2xl font-bold text-slate-900">{analytics.score_trend.length}</p>
          </div>
        </div>

        <div className="mb-6 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="mb-3 font-medium text-slate-900">Score trend over time</h2>
          {trendData.length === 0 ? (
            <p className="text-sm text-slate-400">No quiz attempts yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="attempt" tick={{ fontSize: 12 }} label={{ value: 'Attempt #', position: 'insideBottom', offset: -4, fontSize: 12 }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                <Tooltip formatter={(value) => [`${value}%`, 'Score']} labelFormatter={(label, payload) => payload[0]?.payload.date ?? label} />
                <Line type="monotone" dataKey="score" stroke="#0f172a" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="mb-3 font-medium text-slate-900">Average score per module</h2>
          {moduleData.length === 0 ? (
            <p className="text-sm text-slate-400">No quiz attempts yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={moduleData} layout="vertical" margin={{ left: 24 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 12 }} />
                <YAxis type="category" dataKey="module" width={160} tick={{ fontSize: 12 }} />
                <Tooltip formatter={(value) => [`${value}%`, 'Average score']} />
                <Bar dataKey="average_score" fill="#0f172a" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </main>
    </div>
  )
}

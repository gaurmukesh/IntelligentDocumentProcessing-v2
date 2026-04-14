import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getApplications, triggerVerification } from '../api'
import { StatusBadge, DecisionBadge } from '../components/StatusBadge'

const STATUS_OPTIONS = ['All', 'DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'COMPLETED', 'REJECTED']

export default function Applications() {
  const [apps, setApps]         = useState([])
  const [filter, setFilter]     = useState('All')
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState('')
  const [triggering, setTrig]   = useState(null)
  const navigate = useNavigate()

  async function load(status) {
    setLoading(true)
    setError('')
    try {
      const data = await getApplications(status === 'All' ? null : status)
      setApps(data)
    } catch (err) {
      setError('Could not reach Spring Boot ERP. Make sure it is running on port 8080.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(filter) }, [filter])

  async function handleTrigger(appId) {
    setTrig(appId)
    try {
      await triggerVerification(appId)
    } finally {
      setTrig(null)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Applications</h2>
        <button onClick={() => load(filter)}
          className="text-sm px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50">
          Refresh
        </button>
      </div>

      {/* Filter */}
      <div className="flex gap-2 mb-4 flex-wrap">
        {STATUS_OPTIONS.map((s) => (
          <button key={s} onClick={() => setFilter(s)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              filter === s ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}>
            {s}
          </button>
        ))}
      </div>

      {error && <div className="p-3 bg-red-50 text-red-700 rounded-md text-sm mb-4">{error}</div>}

      {loading ? (
        <p className="text-gray-400 text-sm">Loading...</p>
      ) : apps.length === 0 ? (
        <p className="text-gray-400 text-sm">No applications found.</p>
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {['Application ID', 'Student', 'Course', 'Status', 'Decision', 'Score', 'Created', 'Actions'].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {apps.map((app) => (
                <tr key={app.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-xs text-gray-600">{app.id}</td>
                  <td className="px-4 py-3 text-gray-800">{app.studentName || '—'}</td>
                  <td className="px-4 py-3 text-gray-600">{app.courseApplied || '—'}</td>
                  <td className="px-4 py-3"><StatusBadge status={app.status} /></td>
                  <td className="px-4 py-3"><DecisionBadge decision={app.verificationDecision || 'PENDING'} /></td>
                  <td className="px-4 py-3 text-gray-600">
                    {app.verificationScore != null ? `${(app.verificationScore * 100).toFixed(0)}%` : '—'}
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {app.createdAt ? app.createdAt.slice(0, 10) : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleTrigger(app.id)}
                        disabled={triggering === app.id}
                        className="text-xs px-2 py-1 bg-blue-50 text-blue-700 rounded hover:bg-blue-100 disabled:opacity-50">
                        {triggering === app.id ? '...' : 'Verify'}
                      </button>
                      <button onClick={() => navigate(`/pipeline-status/${app.id}`)}
                        className="text-xs px-2 py-1 bg-gray-50 text-gray-700 rounded hover:bg-gray-100">
                        Pipeline
                      </button>
                      <button onClick={() => navigate(`/report/${app.id}`)}
                        className="text-xs px-2 py-1 bg-gray-50 text-gray-700 rounded hover:bg-gray-100">
                        Report
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-4 py-3 border-t border-gray-100 text-xs text-gray-500">
            {apps.length} application(s) found
          </div>
        </div>
      )}
    </div>
  )
}

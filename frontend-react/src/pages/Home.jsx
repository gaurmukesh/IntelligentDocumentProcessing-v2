import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { healthCheck } from '../api'

const cards = [
  { to: '/new-application',  title: 'New Application',     desc: 'Register a student and upload documents for verification.' },
  { to: '/applications',     title: 'Applications',        desc: 'View all applications and their current verification status.' },
  { to: '/pipeline-status',  title: 'Pipeline Status',     desc: 'Track real-time progress of AI document processing.' },
  { to: '/report',           title: 'Verification Report', desc: 'View the full AI verification report with all checks.' },
]

export default function Home() {
  const [online, setOnline] = useState(null)

  useEffect(() => {
    healthCheck().then(setOnline)
  }, [])

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-900">Intelligent Document Processing</h2>
      <p className="mt-1 text-gray-500">Automated admission document verification powered by AI</p>

      {/* Health indicator */}
      <div className="mt-4">
        {online === null && (
          <span className="text-sm text-gray-400">Checking AI service...</span>
        )}
        {online === true && (
          <span className="inline-flex items-center gap-1.5 text-sm text-green-700 bg-green-50 px-3 py-1 rounded-full">
            <span className="w-2 h-2 bg-green-500 rounded-full"></span>
            AI Service (FastAPI) is online
          </span>
        )}
        {online === false && (
          <span className="inline-flex items-center gap-1.5 text-sm text-red-700 bg-red-50 px-3 py-1 rounded-full">
            <span className="w-2 h-2 bg-red-500 rounded-full"></span>
            AI Service is offline
          </span>
        )}
      </div>

      {/* Navigation cards */}
      <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 gap-4">
        {cards.map(({ to, title, desc }) => (
          <Link
            key={to}
            to={to}
            className="block p-6 bg-white rounded-lg border border-gray-200 hover:border-blue-400 hover:shadow-sm transition-all"
          >
            <h3 className="text-base font-semibold text-gray-900">{title}</h3>
            <p className="mt-1 text-sm text-gray-500">{desc}</p>
          </Link>
        ))}
      </div>
    </div>
  )
}

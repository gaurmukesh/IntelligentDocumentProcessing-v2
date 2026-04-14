import { useState, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getPipelineStatus } from '../api'

const STAGE_CONFIG = {
  UPLOADING:  { label: 'Uploading',  desc: 'Documents are being uploaded.',                       color: 'blue'   },
  EXTRACTING: { label: 'Extracting', desc: 'AI is extracting data from documents…',               color: 'yellow' },
  VALIDATING: { label: 'Validating', desc: 'Running validation and RAG eligibility check…',       color: 'yellow' },
  COMPLETE:   { label: 'Complete',   desc: 'Verification pipeline finished.',                      color: 'green'  },
  FAILED:     { label: 'Failed',     desc: 'One or more documents failed to process.',             color: 'red'    },
}

const STAGE_ORDER = ['UPLOADING', 'EXTRACTING', 'VALIDATING', 'COMPLETE']

const DOC_LABELS = {
  MARKSHEET_10TH: '10th Marksheet',
  MARKSHEET_12TH: '12th Marksheet',
  AADHAR:         'Aadhar Card',
}

const STATUS_ICONS = {
  PENDING:    '⏳',
  EXTRACTING: '⚙️',
  EXTRACTED:  '✅',
  FAILED:     '❌',
}

const DECISION_STYLES = {
  APPROVED:      'bg-green-50 border-green-300 text-green-800',
  REJECTED:      'bg-red-50 border-red-300 text-red-800',
  MANUAL_REVIEW: 'bg-yellow-50 border-yellow-300 text-yellow-800',
}

function confidenceColor(c) {
  if (c >= 0.8) return 'bg-green-500'
  if (c >= 0.6) return 'bg-yellow-400'
  return 'bg-red-500'
}

export default function PipelineStatus() {
  const { appId: paramId } = useParams()
  const [appId, setAppId]       = useState(paramId || '')
  const [data, setData]         = useState(null)
  const [error, setError]       = useState('')
  const [autoRefresh, setAuto]  = useState(false)
  const timerRef = useRef(null)

  async function fetchStatus(id) {
    if (!id) return
    setError('')
    try {
      const res = await getPipelineStatus(id)
      setData(res)
    } catch (err) {
      setError(err.response?.status === 404 ? 'Application not found.' : `Error: ${err.message}`)
      setData(null)
    }
  }

  useEffect(() => {
    if (paramId) fetchStatus(paramId)
  }, [paramId])

  useEffect(() => {
    if (autoRefresh && data) {
      const stage = data.pipeline_stage
      if (stage !== 'COMPLETE' && stage !== 'FAILED') {
        timerRef.current = setInterval(() => fetchStatus(appId), 5000)
      }
    }
    return () => clearInterval(timerRef.current)
  }, [autoRefresh, data, appId])

  const stage      = data?.pipeline_stage || ''
  const stageInfo  = STAGE_CONFIG[stage] || { label: stage, desc: '', color: 'gray' }
  const stageIdx   = STAGE_ORDER.indexOf(stage)
  const progress   = stageIdx >= 0 ? stageIdx / (STAGE_ORDER.length - 1) : 0

  const stageBanner = {
    green:  'bg-green-50 text-green-800 border border-green-200',
    red:    'bg-red-50 text-red-800 border border-red-200',
    yellow: 'bg-yellow-50 text-yellow-800 border border-yellow-200',
    blue:   'bg-blue-50 text-blue-800 border border-blue-200',
    gray:   'bg-gray-50 text-gray-700 border border-gray-200',
  }[stageInfo.color] || ''

  return (
    <div className="max-w-3xl">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Pipeline Status</h2>

      {/* ID Input */}
      <div className="flex gap-3 mb-6">
        <input
          value={appId}
          onChange={(e) => setAppId(e.target.value)}
          placeholder="Paste application ID here"
          className="flex-1 border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button onClick={() => fetchStatus(appId)}
          className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700">
          Check
        </button>
        <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
          <input type="checkbox" checked={autoRefresh} onChange={(e) => setAuto(e.target.checked)} />
          Auto-refresh (5s)
        </label>
      </div>

      {!appId && <p className="text-gray-400 text-sm">Enter an Application ID to track its pipeline progress.</p>}
      {error  && <div className="p-3 bg-red-50 text-red-700 rounded-md text-sm mb-4">{error}</div>}

      {data && (
        <div className="space-y-6">
          {/* Stage banner */}
          <div className={`p-4 rounded-lg ${stageBanner}`}>
            <p className="font-semibold">{stageInfo.label}</p>
            <p className="text-sm mt-0.5">{stageInfo.desc}</p>
          </div>

          {/* Progress bar */}
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-500 h-2 rounded-full transition-all duration-500"
              style={{ width: `${progress * 100}%` }}
            />
          </div>

          {/* Documents */}
          <div>
            <h3 className="font-semibold text-gray-800 mb-3">Documents</h3>
            <div className="grid grid-cols-3 gap-4">
              {(data.documents || []).map((doc) => {
                const label = DOC_LABELS[doc.doc_type] || doc.doc_type
                const icon  = STATUS_ICONS[doc.upload_status] || '⬜'
                return (
                  <div key={doc.doc_type} className="bg-white border border-gray-200 rounded-lg p-4">
                    <p className="text-sm font-medium text-gray-800">{icon} {label}</p>
                    <p className="text-xs text-gray-500 mt-1">{doc.upload_status}</p>
                    {doc.confidence_score != null && (
                      <>
                        <div className="mt-2 w-full bg-gray-100 rounded-full h-1.5">
                          <div
                            className={`h-1.5 rounded-full ${confidenceColor(doc.confidence_score)}`}
                            style={{ width: `${doc.confidence_score * 100}%` }}
                          />
                        </div>
                        <p className="text-xs text-gray-500 mt-1">{(doc.confidence_score * 100).toFixed(0)}% confidence</p>
                      </>
                    )}
                    {doc.extraction_error && (
                      <p className="text-xs text-red-600 mt-1">{doc.extraction_error}</p>
                    )}
                  </div>
                )
              })}
            </div>
          </div>

          {/* Verification result */}
          {data.verification && (() => {
            const v       = data.verification
            const decision= v.decision || ''
            const style   = DECISION_STYLES[decision] || 'bg-gray-50 border-gray-200 text-gray-700'
            const label   = { APPROVED: '✅ APPROVED', REJECTED: '❌ REJECTED', MANUAL_REVIEW: '🔍 MANUAL REVIEW' }[decision] || decision
            return (
              <div>
                <h3 className="font-semibold text-gray-800 mb-3">Verification Result</h3>
                <div className={`p-4 rounded-lg border ${style}`}>
                  <p className="font-bold text-lg">{label}</p>
                  {v.overall_score != null && (
                    <p className="text-sm mt-1">Overall Score: {(v.overall_score * 100).toFixed(0)}%</p>
                  )}
                  {v.decision_reason && (
                    <p className="text-sm mt-1">{v.decision_reason}</p>
                  )}
                  <Link to={`/report/${appId}`}
                    className="inline-block mt-3 text-sm font-medium underline">
                    View Full Report →
                  </Link>
                </div>
              </div>
            )
          })()}
        </div>
      )}
    </div>
  )
}

import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { getVerificationReport } from '../api'

const DOC_LABELS = {
  MARKSHEET_10TH: '10th Marksheet',
  MARKSHEET_12TH: '12th Marksheet',
  AADHAR:         'Aadhar Card',
}

const FIELD_LABELS = {
  student_name:  'Student Name',
  date_of_birth: 'Date of Birth',
  board:         'Board',
  stream:        'Stream',
  exam_year:     'Exam Year',
  percentage:    'Percentage',
  result:        'Result',
  aadhar_number: 'Aadhar Number',
  gender:        'Gender',
  father_name:   "Father's Name",
  address:       'Address',
}

const CHECK_ICONS  = { PASS: '✅', FAIL: '❌', WARNING: '⚠️' }
const CHECK_STYLES = {
  PASS:    'border-green-200 bg-green-50',
  FAIL:    'border-red-200 bg-red-50',
  WARNING: 'border-yellow-200 bg-yellow-50',
}

function confidenceColor(c) {
  if (c >= 0.8) return 'bg-green-500'
  if (c >= 0.6) return 'bg-yellow-400'
  return 'bg-red-500'
}

function confidenceText(c) {
  if (c >= 0.8) return 'text-green-700'
  if (c >= 0.6) return 'text-yellow-700'
  return 'text-red-700'
}

export default function VerificationReport() {
  const { appId: paramId } = useParams()
  const [appId, setAppId]   = useState(paramId || '')
  const [report, setReport] = useState(null)
  const [error, setError]   = useState('')
  const [loading, setLoad]  = useState(false)
  const [activeTab, setTab] = useState(0)

  async function load(id) {
    if (!id) return
    setLoad(true)
    setError('')
    try {
      const r = await getVerificationReport(id)
      setReport(r)
      setTab(0)
    } catch (err) {
      if (err.response?.status === 404) {
        setError('Report not available yet. The verification pipeline may still be running.')
      } else {
        setError(`Could not fetch report: ${err.message}`)
      }
      setReport(null)
    } finally {
      setLoad(false)
    }
  }

  useEffect(() => { if (paramId) load(paramId) }, [paramId])

  const decision  = report?.status || ''
  const score     = report?.overall_score
  const reason    = report?.decision_reason || ''
  const checks    = report?.validation?.checks || []
  const documents = report?.documents || []

  const decisionStyle = {
    APPROVED:      { banner: 'bg-green-50 border-green-300 text-green-900', label: '✅ APPROVED' },
    REJECTED:      { banner: 'bg-red-50 border-red-300 text-red-900',       label: '❌ REJECTED' },
    MANUAL_REVIEW: { banner: 'bg-yellow-50 border-yellow-300 text-yellow-900', label: '🔍 MANUAL REVIEW REQUIRED' },
  }[decision] || { banner: 'bg-gray-50 border-gray-200 text-gray-700', label: decision || 'Pending' }

  const ragCheck = checks.find((c) => c.check_name === 'rag_eligibility_check')

  return (
    <div className="max-w-4xl">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Verification Report</h2>

      {/* ID Input */}
      <div className="flex gap-3 mb-6">
        <input
          value={appId}
          onChange={(e) => setAppId(e.target.value)}
          placeholder="Paste application ID here"
          className="flex-1 border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button onClick={() => load(appId)}
          className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700">
          Load Report
        </button>
      </div>

      {!appId  && <p className="text-gray-400 text-sm">Enter an Application ID to view its verification report.</p>}
      {loading && <p className="text-gray-400 text-sm">Loading...</p>}
      {error   && <div className="p-3 bg-yellow-50 text-yellow-800 rounded-md text-sm mb-4">{error}</div>}

      {report && (
        <div className="space-y-6">
          {/* Decision banner */}
          <div className={`p-5 rounded-lg border ${decisionStyle.banner}`}>
            <p className="text-2xl font-bold">{decisionStyle.label}</p>
            <div className="mt-3 flex items-start gap-8">
              {score != null && (
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide opacity-70">Overall Score</p>
                  <p className="text-3xl font-bold">{(score * 100).toFixed(0)}%</p>
                </div>
              )}
              {reason && (
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide opacity-70">Decision Reason</p>
                  <p className="text-sm mt-1">{reason}</p>
                </div>
              )}
            </div>
          </div>

          {/* Validation Checks */}
          {checks.length > 0 && (
            <div>
              <h3 className="font-semibold text-gray-800 mb-3">Validation Checks</h3>
              <div className="space-y-2">
                {checks.map((check) => {
                  const name  = (check.check_name || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
                  const icon  = CHECK_ICONS[check.status] || '⬜'
                  const style = CHECK_STYLES[check.status] || 'border-gray-200 bg-gray-50'
                  return (
                    <details key={check.check_name}
                      open={check.status === 'FAIL'}
                      className={`border rounded-lg ${style}`}>
                      <summary className="px-4 py-3 cursor-pointer text-sm font-medium select-none">
                        {icon} {name} — <span className="font-bold">{check.status}</span>
                      </summary>
                      <div className="px-4 pb-3 text-sm text-gray-700">
                        <p>{check.detail}</p>
                        {check.confidence != null && (
                          <div className="mt-2">
                            <div className="flex justify-between text-xs text-gray-500 mb-1">
                              <span>Confidence</span>
                              <span>{(check.confidence * 100).toFixed(0)}%</span>
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-1.5">
                              <div className={`h-1.5 rounded-full ${confidenceColor(check.confidence)}`}
                                style={{ width: `${check.confidence * 100}%` }} />
                            </div>
                          </div>
                        )}
                      </div>
                    </details>
                  )
                })}
              </div>
            </div>
          )}

          {/* Extracted Document Data — tabs */}
          {documents.length > 0 && (
            <div>
              <h3 className="font-semibold text-gray-800 mb-3">Extracted Document Data</h3>
              <div className="flex gap-1 mb-4 border-b border-gray-200">
                {documents.map((doc, i) => (
                  <button key={i} onClick={() => setTab(i)}
                    className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                      activeTab === i
                        ? 'border-blue-600 text-blue-600'
                        : 'border-transparent text-gray-500 hover:text-gray-700'
                    }`}>
                    {DOC_LABELS[doc.doc_type] || doc.doc_type}
                  </button>
                ))}
              </div>

              {documents[activeTab] && (() => {
                const doc = documents[activeTab]
                if (doc.error_message) {
                  return <p className="text-red-600 text-sm">{doc.error_message}</p>
                }
                const extracted = doc.extracted_data || {}
                return (
                  <div>
                    {doc.confidence_score != null && (
                      <div className="mb-4 flex items-center gap-3">
                        <span className="text-sm text-gray-600">Overall confidence:</span>
                        <span className={`text-sm font-bold ${confidenceText(doc.confidence_score)}`}>
                          {(doc.confidence_score * 100).toFixed(0)}%
                        </span>
                        <div className="flex-1 bg-gray-200 rounded-full h-1.5">
                          <div className={`h-1.5 rounded-full ${confidenceColor(doc.confidence_score)}`}
                            style={{ width: `${doc.confidence_score * 100}%` }} />
                        </div>
                      </div>
                    )}
                    <div className="bg-white border border-gray-200 rounded-lg divide-y divide-gray-100">
                      {Object.entries(extracted).map(([key, fieldData]) => {
                        const label     = FIELD_LABELS[key] || key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
                        const value     = typeof fieldData === 'object' ? fieldData?.value : fieldData
                        const fieldConf = typeof fieldData === 'object' ? fieldData?.confidence : null
                        return (
                          <div key={key} className="flex items-center px-4 py-2.5 text-sm">
                            <span className="w-40 font-medium text-gray-700 shrink-0">{label}</span>
                            <span className="flex-1 text-gray-600">{value != null ? String(value) : '—'}</span>
                            {fieldConf != null && (
                              <span className={`text-xs font-medium ${confidenceText(fieldConf)}`}>
                                {(fieldConf * 100).toFixed(0)}%
                              </span>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )
              })()}
            </div>
          )}

          {/* RAG Eligibility */}
          {ragCheck && (
            <div>
              <h3 className="font-semibold text-gray-800 mb-3">RAG Eligibility Check</h3>
              <div className={`p-4 rounded-lg border ${CHECK_STYLES[ragCheck.status] || 'border-gray-200 bg-gray-50'}`}>
                <p className="font-semibold text-sm">
                  {ragCheck.status === 'PASS' ? 'Eligible' : ragCheck.status === 'FAIL' ? 'Not Eligible' : 'Uncertain'}
                </p>
                <p className="text-sm mt-1 text-gray-700">{ragCheck.detail}</p>
                {ragCheck.confidence != null && (
                  <p className="text-sm mt-2 font-medium">
                    RAG Confidence: {(ragCheck.confidence * 100).toFixed(0)}%
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

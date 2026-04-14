import { useState } from 'react'
import { createStudent, createApplication, uploadDocument, triggerVerification } from '../api'

const COURSES = ['B.Tech', 'B.Sc', 'B.Com', 'BBA', 'BA', 'MBA', 'M.Tech']

const DOC_TYPES = {
  MARKSHEET_10TH: '10th Grade Marksheet',
  MARKSHEET_12TH: '12th Grade Marksheet',
  AADHAR:         'Aadhar Card (Front Side)',
}

const STEPS = ['Student Details', 'Upload Documents', 'Submit & Verify']

function StepIndicator({ current }) {
  return (
    <div className="flex items-center gap-2 mb-8">
      {STEPS.map((label, i) => {
        const step = i + 1
        const done    = step < current
        const active  = step === current
        return (
          <div key={step} className="flex items-center gap-2">
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium ${
              done   ? 'bg-green-100 text-green-700' :
              active ? 'bg-blue-100 text-blue-700'  :
                       'bg-gray-100 text-gray-400'
            }`}>
              {done ? '✓' : step}. {label}
            </div>
            {i < STEPS.length - 1 && <span className="text-gray-300">→</span>}
          </div>
        )
      })}
    </div>
  )
}

export default function NewApplication() {
  const [step, setStep]           = useState(1)
  const [student, setStudent]     = useState(null)
  const [application, setApp]     = useState(null)
  const [uploadedDocs, setDocs]   = useState({})
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState('')
  const [success, setSuccess]     = useState('')

  // Step 1 form state
  const [form, setForm] = useState({
    fullName: '', email: '', phone: '',
    dateOfBirth: '2003-01-01', courseApplied: COURSES[0],
  })

  const handleField = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  // ── Step 1: Create Student ──────────────────────────────────────
  async function handleStudentSubmit(e) {
    e.preventDefault()
    setError('')
    if (!form.fullName || !form.email || !form.phone) {
      setError('Please fill in all required fields.')
      return
    }
    setLoading(true)
    try {
      const s   = await createStudent(form)
      const app = await createApplication(s.id)
      setStudent(s)
      setApp(app)
      setStep(2)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }

  // ── Step 2: Upload Documents ────────────────────────────────────
  async function handleUpload(docType, file) {
    setError('')
    try {
      const result = await uploadDocument(application.id, docType, file)
      setDocs((prev) => ({ ...prev, [docType]: result }))
    } catch (err) {
      setError(`Upload failed for ${DOC_TYPES[docType]}: ${err.response?.data?.detail || err.message}`)
    }
  }

  // ── Step 3: Trigger Verification ────────────────────────────────
  async function handleVerify() {
    setError('')
    setLoading(true)
    try {
      const ok = await triggerVerification(application.id)
      if (ok) {
        setSuccess(`Verification started! Application ID: ${application.id}`)
        setTimeout(() => {
          setStep(1); setStudent(null); setApp(null); setDocs({})
          setForm({ fullName:'', email:'', phone:'', dateOfBirth:'2003-01-01', courseApplied: COURSES[0] })
          setSuccess('')
        }, 3000)
      } else {
        setError('Failed to trigger verification. Please try again.')
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">New Application</h2>
      <StepIndicator current={step} />

      {error   && <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-md text-sm">{error}</div>}
      {success && <div className="mb-4 p-3 bg-green-50 text-green-700 rounded-md text-sm">{success}</div>}

      {/* ── Step 1 ── */}
      {step === 1 && (
        <form onSubmit={handleStudentSubmit} className="bg-white border border-gray-200 rounded-lg p-6 space-y-4">
          <h3 className="font-semibold text-gray-800">Student Details</h3>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Full Name *</label>
              <input name="fullName" value={form.fullName} onChange={handleField}
                placeholder="e.g. Rahul Sharma"
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email *</label>
              <input name="email" type="email" value={form.email} onChange={handleField}
                placeholder="rahul@example.com"
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Phone *</label>
              <input name="phone" value={form.phone} onChange={handleField}
                placeholder="9876543210"
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Date of Birth *</label>
              <input name="dateOfBirth" type="date" value={form.dateOfBirth} onChange={handleField}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Course Applied *</label>
              <select name="courseApplied" value={form.courseApplied} onChange={handleField}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                {COURSES.map((c) => <option key={c}>{c}</option>)}
              </select>
            </div>
          </div>

          <button type="submit" disabled={loading}
            className="w-full bg-blue-600 text-white py-2 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors">
            {loading ? 'Saving...' : 'Save & Continue →'}
          </button>
        </form>
      )}

      {/* ── Step 2 ── */}
      {step === 2 && (
        <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-5">
          <h3 className="font-semibold text-gray-800">Upload Documents</h3>
          <div className="p-3 bg-blue-50 rounded-md text-sm text-blue-800">
            <strong>Application ID:</strong> {application.id} &nbsp;|&nbsp;
            <strong>Student:</strong> {student.fullName} &nbsp;|&nbsp;
            <strong>Course:</strong> {student.courseApplied}
          </div>

          {Object.entries(DOC_TYPES).map(([docType, label]) => (
            <div key={docType} className="border-b border-gray-100 pb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">{label}</label>
              {uploadedDocs[docType] ? (
                <span className="text-sm text-green-600">✓ Uploaded</span>
              ) : (
                <input type="file" accept=".pdf,.jpg,.jpeg,.png"
                  onChange={(e) => e.target.files[0] && handleUpload(docType, e.target.files[0])}
                  className="text-sm text-gray-600" />
              )}
            </div>
          ))}

          <p className="text-sm text-gray-500">
            {Object.keys(uploadedDocs).length} / {Object.keys(DOC_TYPES).length} documents uploaded
          </p>

          <div className="flex gap-3">
            <button onClick={() => { setStep(1); setDocs({}) }}
              className="flex-1 border border-gray-300 text-gray-700 py-2 rounded-md text-sm font-medium hover:bg-gray-50">
              ← Back
            </button>
            <button
              disabled={Object.keys(uploadedDocs).length < Object.keys(DOC_TYPES).length}
              onClick={() => setStep(3)}
              className="flex-[3] bg-blue-600 text-white py-2 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-40 transition-colors">
              Continue →
            </button>
          </div>
        </div>
      )}

      {/* ── Step 3 ── */}
      {step === 3 && (
        <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-5">
          <h3 className="font-semibold text-gray-800">Submit for Verification</h3>

          <div className="grid grid-cols-2 gap-6 text-sm">
            <div>
              <p className="font-medium text-gray-700 mb-2">Student</p>
              <p className="text-gray-600">Name: {student.fullName}</p>
              <p className="text-gray-600">Email: {student.email}</p>
              <p className="text-gray-600">Course: {student.courseApplied}</p>
            </div>
            <div>
              <p className="font-medium text-gray-700 mb-2">Application</p>
              <p className="text-gray-600 font-mono text-xs">ID: {application.id}</p>
              <p className="text-gray-600">Status: {application.status}</p>
              {Object.entries(DOC_TYPES).map(([dt, label]) => (
                uploadedDocs[dt] && <p key={dt} className="text-green-600">✓ {label}</p>
              ))}
            </div>
          </div>

          <div className="flex gap-3">
            <button onClick={() => setStep(2)}
              className="flex-1 border border-gray-300 text-gray-700 py-2 rounded-md text-sm font-medium hover:bg-gray-50">
              ← Back
            </button>
            <button onClick={handleVerify} disabled={loading}
              className="flex-[3] bg-green-600 text-white py-2 rounded-md text-sm font-medium hover:bg-green-700 disabled:opacity-50 transition-colors">
              {loading ? 'Starting...' : 'Start AI Verification'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

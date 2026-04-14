import axios from 'axios'

const erp = axios.create({ baseURL: '/api/erp', timeout: 15000 })
const ai  = axios.create({ baseURL: '/api/fastapi', timeout: 30000 })

// ── Spring Boot ERP ───────────────────────────────────────────────

export async function createStudent(payload) {
  const { data } = await erp.post('/api/students', payload)
  return data
}

export async function createApplication(studentId) {
  const { data } = await erp.post('/api/applications', { studentId })
  return data
}

export async function getApplications(status = null) {
  const params = status ? { status } : {}
  const { data } = await erp.get('/api/applications', { params })
  return data
}

export async function getApplication(appId) {
  const { data } = await erp.get(`/api/applications/${appId}`)
  return data
}

export async function triggerVerification(appId) {
  const res = await erp.post(`/api/applications/${appId}/trigger-verification`)
  return res.status === 200 || res.status === 202
}

// ── FastAPI AI Service ────────────────────────────────────────────

export async function uploadDocument(appId, docType, file) {
  const form = new FormData()
  form.append('file', file)
  form.append('application_id', appId)
  form.append('doc_type', docType)
  const { data } = await ai.post('/documents/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function getPipelineStatus(appId) {
  const { data } = await ai.get(`/applications/${appId}/pipeline-status`)
  return data
}

export async function getVerificationReport(appId) {
  const { data } = await ai.get(`/verify/${appId}/report`)
  return data
}

export async function healthCheck() {
  try {
    const res = await ai.get('/health', { timeout: 5000 })
    return res.status === 200
  } catch {
    return false
  }
}

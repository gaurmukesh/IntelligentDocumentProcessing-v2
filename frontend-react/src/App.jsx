import { HashRouter as BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import NewApplication from './pages/NewApplication'
import Applications from './pages/Applications'
import PipelineStatus from './pages/PipelineStatus'
import VerificationReport from './pages/VerificationReport'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="new-application" element={<NewApplication />} />
          <Route path="applications" element={<Applications />} />
          <Route path="pipeline-status" element={<PipelineStatus />} />
          <Route path="pipeline-status/:appId" element={<PipelineStatus />} />
          <Route path="report" element={<VerificationReport />} />
          <Route path="report/:appId" element={<VerificationReport />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

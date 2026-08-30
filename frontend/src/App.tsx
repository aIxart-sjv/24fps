import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { TooltipProvider } from '@/components/ui/Tooltip'
import { ToastProvider } from '@/hooks/useToast'
import { AppLayout } from '@/layouts/AppLayout'
import { Landing } from '@/pages/Landing'
import { Login } from '@/pages/Login'
import { Dashboard } from '@/pages/Dashboard'
import { Cases } from '@/pages/Cases'
import { CaseDetails } from '@/pages/CaseDetails'
import { EvidenceList } from '@/pages/EvidenceList'
import { EvidenceDetails } from '@/pages/EvidenceDetails'
import { Devices } from '@/pages/Devices'
import { MediaAnalysis } from '@/pages/MediaAnalysis'
import { AIInsights } from '@/pages/AIInsights'
import { Timeline } from '@/pages/Timeline'
import { Integrity } from '@/pages/Integrity'
import { ActivityLog } from '@/pages/ActivityLog'
import { Reports } from '@/pages/Reports'
import { ReportView } from '@/pages/ReportView'
import { Settings } from '@/pages/Settings'
import { Acquisition } from '@/pages/Acquisition'
import { Recovery } from '@/pages/Recovery'
import { Correlation } from '@/pages/Correlation'
import { Validation } from '@/pages/Validation'
import { Vendors } from '@/pages/Vendors'
import { Admin } from '@/pages/Admin'
import { NotFound } from '@/pages/NotFound'

function App() {
  return (
    <TooltipProvider>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route element={<AppLayout />}>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/cases" element={<Cases />} />
              <Route path="/cases/:caseId" element={<CaseDetails />} />
              <Route path="/evidence" element={<EvidenceList />} />
              <Route path="/evidence/:evidenceId" element={<EvidenceDetails />} />
              <Route path="/devices" element={<Devices />} />
              <Route path="/acquisition" element={<Acquisition />} />
              <Route path="/recovery" element={<Recovery />} />
              <Route path="/analysis" element={<MediaAnalysis />} />
              <Route path="/correlation" element={<Correlation />} />
              <Route path="/insights" element={<AIInsights />} />
              <Route path="/timeline" element={<Timeline />} />
              <Route path="/integrity" element={<Integrity />} />
              <Route path="/validation" element={<Validation />} />
              <Route path="/vendors" element={<Vendors />} />
              <Route path="/activity" element={<ActivityLog />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/reports/:reportId" element={<ReportView />} />
              <Route path="/admin" element={<Admin />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </TooltipProvider>
  )
}

export default App

import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { Sidebar } from '@/components/layout/Sidebar'
import { Header } from '@/components/layout/Header'
import { PageContainer } from '@/components/layout/PageContainer'
import { getSession } from '@/lib/auth'

export function AppLayout() {
  const location = useLocation()

  // Frontend-only mock auth gate — no backend involved. Without a session,
  // the platform routes redirect to /login rather than rendering directly.
  if (!getSession()) {
    return <Navigate to="/login" replace />
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header />
        <main className="flex-1 overflow-y-auto">
          <PageContainer key={location.pathname} className="animate-fade-in">
            <Outlet />
          </PageContainer>
        </main>
      </div>
    </div>
  )
}

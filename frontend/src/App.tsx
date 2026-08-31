/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { AppProvider, useApp } from './context/AppContext';
import { LandingPage } from './components/landing/LandingPage';
import { LoginPage } from './components/auth/LoginPage';
import { PoliceLayout } from './components/police/PoliceLayout';
import { AdminLayout } from './components/admin/AdminLayout';
import { ToastContainer, LoadingState } from './components/common/CommonUI';
import { uiRoleFor } from './types';

const AppContent: React.FC = () => {
  const { activeRoute, navigateTo, currentUser, authLoading } = useApp();

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-neutral-950">
        <LoadingState label="Connecting to 24FPS backend…" />
      </div>
    );
  }

  // An unauthenticated visitor can never reach a workspace route, and an
  // authenticated one can only reach the workspace matching their real
  // backend role -- never both, regardless of what `activeRoute` says.
  let effectiveRoute = activeRoute;
  if (!currentUser && (activeRoute === '/police' || activeRoute === '/admin')) {
    effectiveRoute = '/login';
  } else if (currentUser) {
    const homeRoute = uiRoleFor(currentUser) === 'admin' ? '/admin' : '/police';
    if (activeRoute === '/police' || activeRoute === '/admin') {
      effectiveRoute = homeRoute;
    }
  }

  return (
    <div className="min-h-screen bg-neutral-900 text-neutral-100 font-sans antialiased selection:bg-yellow-400 selection:text-black">
      {effectiveRoute === '/' && <LandingPage onEnter={() => navigateTo('/login')} onNavigate={navigateTo} />}
      {effectiveRoute === '/login' && (
        <LoginPage
          onSuccess={(role) => navigateTo(role === 'admin' ? '/admin' : '/police')}
          onBackToLanding={() => navigateTo('/')}
          onNavigate={navigateTo}
        />
      )}
      {effectiveRoute === '/police' && currentUser && <PoliceLayout onNavigate={navigateTo} />}
      {effectiveRoute === '/admin' && currentUser && <AdminLayout onNavigate={navigateTo} />}

      <ToastContainer />
    </div>
  );
};

export default function App() {
  return (
    <AppProvider>
      <AppContent />
    </AppProvider>
  );
}

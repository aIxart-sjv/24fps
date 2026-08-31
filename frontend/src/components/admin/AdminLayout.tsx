import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';
import { TopBar } from '../common/TopBar';
import { AdminDashboard } from './AdminDashboard';
import { AdminCases } from './AdminCases';
import { AdminUsers } from './AdminUsers';
import { AdminAccessControl } from './AdminAccessControl';
import { AdminAuditLog } from './AdminAuditLog';
import { AdminSecurityEvents } from './AdminSecurityEvents';
import { AdminServices } from './AdminServices';
import { AdminMLMonitoring } from './AdminMLMonitoring';
import { AdminStorageMonitoring } from './AdminStorageMonitoring';
import { AdminOemSupport } from './AdminOemSupport';
import {
  LayoutDashboard,
  FolderLock,
  Users,
  Key,
  ShieldCheck,
  Clock,
  ShieldAlert,
  Server,
  Sparkles,
  HardDrive,
  Menu,
  ChevronRight,
} from 'lucide-react';
import { AdminSection } from '../../types';

interface AdminLayoutProps {
  onNavigate: (path: string) => void;
}

export const AdminLayout: React.FC<AdminLayoutProps> = ({ onNavigate }) => {
  const { activeAdminSection, setActiveAdminSection, isSidebarOpen, toggleSidebar } = useApp();

  const navigationGroups = [
    {
      groupTitle: 'OVERVIEW',
      items: [
        { id: 'dashboard' as AdminSection, label: 'Dashboard', icon: <LayoutDashboard className="w-4 h-4" /> },
      ],
    },
    {
      groupTitle: 'INVESTIGATIONS',
      items: [
        {
          id: 'cases' as AdminSection,
          label: 'Case Directory',
          icon: <FolderLock className="w-4 h-4" />,
        },
      ],
    },
    {
      groupTitle: 'ACCESS',
      items: [
        { id: 'users' as AdminSection, label: 'Users & Personnel', icon: <Users className="w-4 h-4" /> },
        { id: 'access' as AdminSection, label: 'Clearance & Matrix', icon: <Key className="w-4 h-4" /> },
      ],
    },
    {
      groupTitle: 'SECURITY',
      items: [
        { id: 'audit' as AdminSection, label: 'Audit Log', icon: <Clock className="w-4 h-4" /> },
        {
          id: 'security' as AdminSection,
          label: 'Security Events',
          icon: <ShieldAlert className="w-4 h-4" />,
        },
      ],
    },
    {
      groupTitle: 'SYSTEM',
      items: [
        { id: 'system' as AdminSection, label: 'Services & Daemons', icon: <Server className="w-4 h-4" /> },
        { id: 'oem' as AdminSection, label: 'OEM Support', icon: <HardDrive className="w-4 h-4" /> },
        { id: 'ml' as AdminSection, label: 'ML Monitoring', icon: <Sparkles className="w-4 h-4" /> },
        { id: 'storage' as AdminSection, label: 'Storage & WORM', icon: <HardDrive className="w-4 h-4" /> },
      ],
    },
  ];

  return (
    <div className="min-h-screen w-full flex flex-col bg-neutral-900 text-neutral-100 font-sans">
      <TopBar onNavigate={onNavigate} />

      <div className="flex-1 flex min-h-0 overflow-hidden relative">
        {/* Backdrop for mobile when sidebar is open */}
        {isSidebarOpen && (
          <div
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-xs md:hidden"
            onClick={toggleSidebar}
          />
        )}

        {/* SIDEBAR NAVIGATION (Grouped, Responsive) */}
        <aside
          className={`shrink-0 bg-neutral-950 border-r border-neutral-800 flex flex-col justify-between overflow-y-auto z-40 transition-all duration-200 ${
            isSidebarOpen
              ? 'fixed inset-y-14 left-0 w-64 shadow-2xl md:relative md:inset-y-auto md:shadow-none'
              : 'hidden'
          }`}
        >
          <div className="p-4 space-y-6">
            <div className="text-[11px] font-mono font-bold text-yellow-400 uppercase tracking-widest px-2 pb-2 border-b border-neutral-850">
              COMMAND CENTER
            </div>

            {navigationGroups.map((grp) => (
              <div key={grp.groupTitle} className="space-y-1">
                <div className="text-[10px] font-mono font-bold text-neutral-400 uppercase tracking-wider px-2">
                  {grp.groupTitle}
                </div>
                <div className="space-y-0.5 pt-1">
                  {grp.items.map((item) => {
                    const isActive = activeAdminSection === item.id;
                    return (
                      <button
                        key={item.id}
                        onClick={() => {
                          setActiveAdminSection(item.id);
                          if (window.innerWidth < 768) {
                            toggleSidebar();
                          }
                        }}
                        className={`w-full text-left px-3 py-2 rounded text-xs font-mono font-medium flex items-center justify-between transition-colors cursor-pointer ${
                          isActive
                            ? 'bg-yellow-400 text-black font-bold shadow-sm'
                            : 'text-neutral-300 hover:bg-neutral-900 hover:text-white'
                        }`}
                      >
                        <div className="flex items-center gap-2.5">
                          {item.icon}
                          <span>{item.label}</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          <div className="p-4 border-t border-neutral-850 font-mono text-[11px] text-neutral-400">
            <div>24FPS FORENSICS v2.4.0</div>
            <div className="text-emerald-400 mt-0.5">● CLUSTER OPERATIONAL</div>
          </div>
        </aside>

        {/* MAIN ADMIN WORKSPACE */}
        <main className="flex-1 flex flex-col min-h-0 bg-neutral-900 overflow-y-auto p-4 sm:p-6">
          {/* Mobile Section Header with Dropdown */}
          <div className="md:hidden mb-4 bg-neutral-950 border border-neutral-800 rounded p-3 flex items-center justify-between">
            <span className="font-mono text-xs font-bold text-yellow-400 uppercase">
              SECTION: {activeAdminSection}
            </span>
            <select
              aria-label="Admin Navigation Section"
              value={activeAdminSection}
              onChange={(e) => setActiveAdminSection(e.target.value as AdminSection)}
              className="bg-neutral-900 border border-neutral-700 text-xs font-mono text-neutral-200 rounded p-1"
            >
              <option value="dashboard">Dashboard</option>
              <option value="cases">Case Directory</option>
              <option value="users">Users</option>
              <option value="access">Clearance & Matrix</option>
              <option value="audit">Audit Log</option>
              <option value="security">Security Events</option>
              <option value="system">Services</option>
              <option value="oem">OEM Support</option>
              <option value="ml">ML Engine</option>
              <option value="storage">Storage</option>
            </select>
          </div>

          {/* Render Active Admin View */}
          {activeAdminSection === 'dashboard' && (
            <AdminDashboard onNavigateSection={(sec) => setActiveAdminSection(sec)} />
          )}
          {activeAdminSection === 'cases' && <AdminCases />}
          {activeAdminSection === 'users' && <AdminUsers />}
          {activeAdminSection === 'access' && <AdminAccessControl />}
          {activeAdminSection === 'audit' && <AdminAuditLog />}
          {activeAdminSection === 'security' && <AdminSecurityEvents />}
          {activeAdminSection === 'system' && <AdminServices />}
          {activeAdminSection === 'oem' && <AdminOemSupport />}
          {activeAdminSection === 'ml' && <AdminMLMonitoring />}
          {activeAdminSection === 'storage' && <AdminStorageMonitoring />}
        </main>
      </div>
    </div>
  );
};

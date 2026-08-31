import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';
import { Logo24FPS, LogoCBI } from '../Logos';
import { Menu, Sun, Moon, LogOut, Bell, CheckCheck } from 'lucide-react';

interface TopBarProps {
  onNavigate?: (path: string) => void;
  title?: string;
  subtitle?: string;
}

export const TopBar: React.FC<TopBarProps> = ({ onNavigate, title, subtitle }) => {
  const {
    currentUser,
    logout,
    theme,
    toggleTheme,
    toggleSidebar,
    notifications,
    unreadNotificationCount,
    markNotificationRead,
    navigateTo,
    setActiveCaseId,
    setActiveCaseTab,
  } = useApp();

  const [showNotifications, setShowNotifications] = useState(false);

  const severityDot: Record<string, string> = {
    critical: 'bg-red-500',
    high: 'bg-red-400',
    medium: 'bg-amber-400',
    low: 'bg-neutral-400',
    info: 'bg-cyan-400',
  };

  return (
    <header className="h-14 border-b border-neutral-800 bg-neutral-950 text-neutral-100 flex items-center justify-between px-3 md:px-5 sticky top-0 z-40 select-none">
      <div className="flex items-center gap-3 md:gap-5">
        <button
          onClick={toggleSidebar}
          aria-label="Toggle navigation sidebar"
          className="p-1.5 rounded hover:bg-neutral-800 text-neutral-300 hover:text-yellow-400 transition-colors"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div
          onClick={() => onNavigate?.(currentUser?.role === 'admin' ? '/admin' : '/police')}
          className="flex items-center gap-3 cursor-pointer group"
        >
          <Logo24FPS variant={theme === 'dark' ? 'dark' : 'light'} className="h-7 w-auto" />
          <span className="h-4 w-px bg-neutral-800" />
          <LogoCBI className="h-7 w-auto" />
        </div>

        <div className="hidden lg:flex items-center gap-2 pl-2 border-l border-neutral-800 text-xs">
          {title ? (
            <div className="flex flex-col">
              <span className="font-semibold text-neutral-200 tracking-tight">{title}</span>
              {subtitle && <span className="text-[10px] text-neutral-400 font-mono">{subtitle}</span>}
            </div>
          ) : (
            <span className="font-mono text-neutral-400 text-xs tracking-wider">
              {currentUser?.role === 'admin' ? 'SYSTEM COMMAND CENTER' : 'INVESTIGATION WORKSPACE'}
            </span>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3 md:gap-4">
        {currentUser && (
          <div className="relative">
            <button
              onClick={() => setShowNotifications((prev) => !prev)}
              className="relative p-1.5 rounded hover:bg-neutral-800 text-neutral-400 hover:text-yellow-400 transition-colors"
              aria-label="Notifications"
            >
              <Bell className="w-4 h-4" />
              {unreadNotificationCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-red-500 text-white text-[9px] font-bold flex items-center justify-center">
                  {unreadNotificationCount > 9 ? '9+' : unreadNotificationCount}
                </span>
              )}
            </button>

            {showNotifications && (
              <div className="absolute right-0 mt-2 w-80 max-h-96 overflow-y-auto bg-neutral-900 border border-neutral-800 rounded shadow-2xl z-50">
                <div className="px-3 py-2 border-b border-neutral-800 flex items-center justify-between">
                  <span className="text-[10px] font-mono uppercase font-bold text-neutral-300">
                    Notifications
                  </span>
                  <span className="text-[10px] font-mono text-neutral-400">
                    {unreadNotificationCount} unread
                  </span>
                </div>
                {notifications.length === 0 ? (
                  <div className="p-4 text-center text-[11px] font-mono text-neutral-400">
                    No findings requiring attention.
                  </div>
                ) : (
                  notifications.slice(0, 20).map((n) => (
                    <button
                      key={n.id}
                      onClick={() => {
                        if (n.read_at === null) markNotificationRead(n.id);
                        setActiveCaseId(n.finding.case_id);
                        setActiveCaseTab('findings');
                        navigateTo('/police');
                        setShowNotifications(false);
                      }}
                      className={`w-full text-left px-3 py-2.5 border-b border-neutral-850 hover:bg-neutral-850 transition-colors flex gap-2 ${
                        n.read_at === null ? 'bg-neutral-900' : 'bg-neutral-950/40 opacity-70'
                      }`}
                    >
                      <span
                        className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${severityDot[n.finding.severity] ?? 'bg-neutral-500'}`}
                      />
                      <div className="min-w-0">
                        <div className="text-[11px] font-semibold text-neutral-100 truncate">
                          {n.finding.title}
                        </div>
                        <div className="text-[10px] font-mono text-neutral-400 uppercase mt-0.5">
                          {n.finding.severity} · {n.finding.finding_type.replace(/_/g, ' ')}
                        </div>
                      </div>
                      {n.read_at === null && <CheckCheck className="w-3 h-3 text-yellow-400 shrink-0 ml-auto" />}
                    </button>
                  ))
                )}
              </div>
            )}
          </div>
        )}

        {currentUser && (
          <div className="flex items-center gap-2.5 bg-neutral-900 border border-neutral-800 rounded px-2.5 py-1">
            <div className="flex flex-col text-right">
              <span className="font-mono text-xs font-bold text-yellow-400">
                {currentUser.display_name}
              </span>
              <span className="text-[10px] text-neutral-400 uppercase">{currentUser.role}</span>
            </div>
          </div>
        )}

        <button
          onClick={toggleTheme}
          aria-label="Toggle theme"
          className="p-1.5 rounded hover:bg-neutral-800 text-neutral-400 hover:text-neutral-200 transition-colors"
          title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`}
        >
          {theme === 'dark' ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-neutral-300" />}
        </button>

        <button
          onClick={() => {
            logout();
            onNavigate?.('/login');
          }}
          aria-label="Sign out"
          className="flex items-center gap-1.5 p-1.5 md:px-2.5 md:py-1 rounded bg-neutral-900 hover:bg-neutral-800 text-neutral-400 hover:text-red-400 border border-neutral-800 transition-colors text-xs font-mono"
        >
          <LogOut className="w-3.5 h-3.5" />
          <span className="hidden md:inline">EXIT</span>
        </button>
      </div>
    </header>
  );
};

import React, { createContext, useContext, useState, useEffect, useMemo, useCallback } from 'react';
import { authApi, getStoredToken, notificationsApi, setStoredToken } from '../lib/api';
import type { NotificationResponse, UserResponse } from '../lib/apiTypes';
import { AdminSection, CaseTab } from '../types';

export interface ToastMessage {
  id: string;
  title: string;
  description?: string;
  type: 'success' | 'error' | 'warning' | 'info';
}

/** How often the notification inbox is polled while the app is open.
 * No websocket/SSE mechanism exists in the backend (Phase 22's own gap
 * assessment confirmed this) -- polling is the documented, sanctioned
 * fallback (task Phase 23 scope, "Polling / Long-Running Jobs": "Do not
 * fake real-time state. Do not hammer the backend continuously."). */
const NOTIFICATION_POLL_INTERVAL_MS = 20_000;

interface AppContextType {
  // Auth
  currentUser: UserResponse | null;
  authLoading: boolean;
  login: (
    username: string,
    password: string
  ) => Promise<{ ok: boolean; error?: string; role?: UserResponse['role'] }>;
  logout: () => void;

  // Theme
  theme: 'dark' | 'light';
  setTheme: (theme: 'dark' | 'light') => void;
  toggleTheme: () => void;

  // Navigation
  activeRoute: string;
  setActiveRoute: (route: string) => void;
  navigateTo: (route: string) => void;
  activeCaseId: number | null;
  setActiveCaseId: (id: number | null) => void;
  activeCaseTab: CaseTab;
  setActiveCaseTab: (tab: CaseTab) => void;
  activeAdminSection: AdminSection;
  setActiveAdminSection: (section: AdminSection) => void;
  isSidebarOpen: boolean;
  setIsSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;

  // Video/recording selection (cross-view: Timeline "view footage" jumps
  // the Evidence tab to a specific recording and playback offset).
  activeRecordingId: number | null;
  setActiveRecordingId: (id: number | null) => void;
  pendingSeekSeconds: number | null;
  requestSeek: (recordingId: number, seconds: number) => void;
  consumePendingSeek: () => void;

  // Search-result -> video-overlay highlight (task: "visual highlighting"
  // fix). `highlightedAiResultIds` is the specific set of AIResult rows a
  // natural-language search result matched -- the evidence player uses it
  // to draw only that detection's bounding box instead of every detection
  // on the current frame. Cleared by any *plain* `requestSeek` (Timeline/
  // AI-tab navigation) or explicitly via `clearHighlight`, so a stale
  // highlight never lingers once the officer leaves the search flow.
  highlightedAiResultIds: number[] | null;
  highlightedQuery: string | null;
  // `seconds: null` means the exact frame/timestamp for this result could
  // not be honestly resolved (no backend timestamp and no recording fps)
  // -- the recording/highlight still navigates, but no seek is attempted
  // (task: "Do not invent a timestamp... do not silently use 0").
  requestSeekWithHighlight: (
    recordingId: number,
    seconds: number | null,
    aiResultIds: number[],
    query: string
  ) => void;
  clearHighlight: () => void;

  // Notifications (real, polled)
  notifications: NotificationResponse[];
  unreadNotificationCount: number;
  refreshNotifications: () => void;
  markNotificationRead: (id: number) => Promise<void>;

  // Toasts
  toasts: ToastMessage[];
  addToast: (toast: Omit<ToastMessage, 'id'>) => void;
  removeToast: (id: string) => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
      root.classList.remove('light');
    } else {
      root.classList.add('light');
      root.classList.remove('dark');
    }
  }, [theme]);

  const toggleTheme = () => setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));

  // ---- Auth: real session, resolved from a stored bearer token via
  // GET /auth/me on load -- never a client-invented identity.
  const [currentUser, setCurrentUser] = useState<UserResponse | null>(null);
  const [authLoading, setAuthLoading] = useState<boolean>(true);

  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);
  const addToast = useCallback(
    (toast: Omit<ToastMessage, 'id'>) => {
      const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
      setToasts((prev) => [...prev, { ...toast, id }]);
      setTimeout(() => removeToast(id), 4500);
    },
    [removeToast]
  );

  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      setAuthLoading(false);
      return;
    }
    authApi
      .me()
      .then((me) =>
        setCurrentUser({
          id: me.user_id,
          username: me.username,
          display_name: me.display_name,
          role: me.role as UserResponse['role'],
          is_active: true,
          created_at: '',
        })
      )
      .catch(() => {
        // Stored token is invalid/expired -- discard it silently, the
        // officer simply sees the login screen again.
        setStoredToken(null);
      })
      .finally(() => setAuthLoading(false));
  }, []);

  const login = useCallback(
    async (username: string, password: string) => {
      try {
        const result = await authApi.login(username, password);
        setStoredToken(result.token);
        setCurrentUser({
          id: result.user_id,
          username: result.username,
          display_name: result.display_name,
          role: result.role,
          is_active: true,
          created_at: '',
        });
        addToast({
          title: 'Authentication Successful',
          description: `Signed in as ${result.display_name} (${result.role.toUpperCase()})`,
          type: 'success',
        });
        return { ok: true, role: result.role };
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Login failed.';
        return { ok: false, error: message };
      }
    },
    [addToast]
  );

  const logout = useCallback(() => {
    authApi.logout().catch(() => {
      // Best-effort server-side revocation -- the client-side token is
      // discarded regardless so the officer is never stuck logged in.
    });
    setStoredToken(null);
    setCurrentUser(null);
    addToast({ title: 'Session Terminated', description: 'You have been logged out.', type: 'info' });
  }, [addToast]);

  // ---- Navigation
  const [activeRoute, setActiveRoute] = useState<string>('/');
  const navigateTo = useCallback((path: string) => setActiveRoute(path), []);
  const [activeCaseId, setActiveCaseId] = useState<number | null>(null);
  const [activeCaseTab, setActiveCaseTab] = useState<CaseTab>('overview');
  const [activeAdminSection, setActiveAdminSection] = useState<AdminSection>('dashboard');
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true);
  const toggleSidebar = useCallback(() => setIsSidebarOpen((prev) => !prev), []);

  // ---- Video/recording selection
  const [activeRecordingId, setActiveRecordingId] = useState<number | null>(null);
  const [pendingSeekSeconds, setPendingSeekSeconds] = useState<number | null>(null);
  const [highlightedAiResultIds, setHighlightedAiResultIds] = useState<number[] | null>(null);
  const [highlightedQuery, setHighlightedQuery] = useState<string | null>(null);

  const clearHighlight = useCallback(() => {
    setHighlightedAiResultIds(null);
    setHighlightedQuery(null);
  }, []);

  const requestSeek = useCallback(
    (recordingId: number, seconds: number) => {
      setActiveRecordingId(recordingId);
      setPendingSeekSeconds(seconds);
      // Plain navigation (Timeline/AI tab) never carries a search
      // highlight -- any previous one is stale and must not linger.
      clearHighlight();
    },
    [clearHighlight]
  );
  const requestSeekWithHighlight = useCallback(
    (recordingId: number, seconds: number | null, aiResultIds: number[], query: string) => {
      setActiveRecordingId(recordingId);
      setPendingSeekSeconds(seconds);
      setHighlightedAiResultIds(aiResultIds);
      setHighlightedQuery(query);
    },
    []
  );
  const consumePendingSeek = useCallback(() => setPendingSeekSeconds(null), []);

  // ---- Notifications: real, polled while authenticated.
  const [notifications, setNotifications] = useState<NotificationResponse[]>([]);
  const refreshNotifications = useCallback(() => {
    if (!currentUser) return;
    notificationsApi
      .list()
      .then(setNotifications)
      .catch(() => {
        // A transient failure to poll notifications should not disrupt
        // whatever the officer is doing -- it will simply retry next tick.
      });
  }, [currentUser]);

  useEffect(() => {
    if (!currentUser) {
      setNotifications([]);
      return;
    }
    refreshNotifications();
    const interval = setInterval(refreshNotifications, NOTIFICATION_POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [currentUser, refreshNotifications]);

  const markNotificationRead = useCallback(async (id: number) => {
    const updated = await notificationsApi.update(id, { read: true });
    setNotifications((prev) => prev.map((n) => (n.id === id ? updated : n)));
  }, []);

  const unreadNotificationCount = useMemo(
    () => notifications.filter((n) => n.read_at === null).length,
    [notifications]
  );

  const value = useMemo<AppContextType>(
    () => ({
      currentUser,
      authLoading,
      login,
      logout,
      theme,
      setTheme,
      toggleTheme,
      activeRoute,
      setActiveRoute,
      navigateTo,
      activeCaseId,
      setActiveCaseId,
      activeCaseTab,
      setActiveCaseTab,
      activeAdminSection,
      setActiveAdminSection,
      isSidebarOpen,
      setIsSidebarOpen,
      toggleSidebar,
      activeRecordingId,
      setActiveRecordingId,
      pendingSeekSeconds,
      requestSeek,
      consumePendingSeek,
      highlightedAiResultIds,
      highlightedQuery,
      requestSeekWithHighlight,
      clearHighlight,
      notifications,
      unreadNotificationCount,
      refreshNotifications,
      markNotificationRead,
      toasts,
      addToast,
      removeToast,
    }),
    [
      currentUser,
      authLoading,
      login,
      logout,
      theme,
      activeRoute,
      navigateTo,
      activeCaseId,
      activeCaseTab,
      activeAdminSection,
      isSidebarOpen,
      toggleSidebar,
      activeRecordingId,
      pendingSeekSeconds,
      requestSeek,
      consumePendingSeek,
      highlightedAiResultIds,
      highlightedQuery,
      requestSeekWithHighlight,
      clearHighlight,
      notifications,
      unreadNotificationCount,
      refreshNotifications,
      markNotificationRead,
      toasts,
      addToast,
      removeToast,
    ]
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};

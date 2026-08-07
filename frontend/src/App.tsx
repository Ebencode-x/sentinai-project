import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ToastProvider } from "@/components/Toast";
import { ThemeProvider } from "@/hooks/useTheme";
import Layout from "@/components/Layout";
import Dashboard from "@/pages/Dashboard";
import IncidentTimeline from "@/pages/IncidentTimeline";
import AuditExplorer from "@/pages/AuditExplorer";
import PolicyEditor from "@/pages/PolicyEditor";
import DiffViewer from "@/pages/DiffViewer";
import Settings from "@/pages/Settings";
import LoginPage from "@/pages/LoginPage";
import { useAuth, AuthProvider } from "@/hooks/useAuth";
import { useEffect, useRef } from "react";
import { startPolling, stopPolling } from "@/store/sentinai";

function PollingManager() {
  const { isAuthenticated } = useAuth();
  const started = useRef(false);
  useEffect(() => {
    if (!isAuthenticated) {
      stopPolling();
      started.current = false;
      return;
    }
    if (started.current) return;
    started.current = true;
    startPolling(15_000);
    return () => {
      stopPolling();
      started.current = false;
    };
  }, [isAuthenticated]);
  return null;
}

function AppRoutes() {
  const { isAuthenticated, logout } = useAuth();

  useEffect(() => {
    const id = setInterval(() => {
      const exp = localStorage.getItem("sentinai_session_expiry");
      if (exp && Date.now() > new Date(exp).getTime()) logout();
    }, 60_000);
    return () => clearInterval(id);
  }, [logout]);

  return (
    <BrowserRouter>
      <PollingManager />
      <Routes>
        <Route path="/login" element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <LoginPage />} />
        <Route path="/" element={isAuthenticated ? <Layout /> : <Navigate to="/login" replace />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="incidents" element={<IncidentTimeline />} />
          <Route path="audit" element={<AuditExplorer />} />
          <Route path="policy" element={<PolicyEditor />} />
          <Route path="diff" element={<DiffViewer />} />
          <Route path="settings" element={<Settings />} />
        </Route>
        <Route path="*" element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}

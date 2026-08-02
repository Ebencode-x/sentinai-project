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
import { useApiKey, ApiKeyProvider } from "@/hooks/useApiKey";
import { useEffect, useRef } from "react";
import { startPolling, stopPolling } from "@/store/sentinai";

function PollingManager() {
  const { hasKey } = useApiKey();
  const started = useRef(false);
  useEffect(() => {
    if (!hasKey) { stopPolling(); started.current = false; return; }
    if (started.current) return;
    started.current = true;
    startPolling(15_000);
    return () => { stopPolling(); started.current = false; };
  }, [hasKey]);
  return null;
}

function AppRoutes() {
  const { hasKey, clearKey } = useApiKey();

  useEffect(() => {
    const id = setInterval(() => {
      const exp = localStorage.getItem("sentinai_key_expiry");
      if (exp && Date.now() > parseInt(exp, 10)) clearKey();
    }, 60_000);
    return () => clearInterval(id);
  }, [clearKey]);

  return (
    <BrowserRouter>
      <PollingManager />
      <Routes>
        <Route
          path="/login"
          element={hasKey ? <Navigate to="/dashboard" replace /> : <LoginPage />}
        />
        <Route
          path="/"
          element={hasKey ? <Layout /> : <Navigate to="/login" replace />}
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="incidents" element={<IncidentTimeline />} />
          <Route path="audit"     element={<AuditExplorer />} />
          <Route path="policy"    element={<PolicyEditor />} />
          <Route path="diff"      element={<DiffViewer />} />
          <Route path="settings"  element={<Settings />} />
        </Route>
        <Route path="*" element={<Navigate to={hasKey ? "/dashboard" : "/login"} replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <ApiKeyProvider>
          <AppRoutes />
        </ApiKeyProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}

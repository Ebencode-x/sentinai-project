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
import { useApiKey } from "@/hooks/useApiKey";
import { useEffect } from "react";

function AuthGuard() {
  const { hasKey, clearKey } = useApiKey();
  useEffect(() => {
    const id = setInterval(() => {
      const exp = localStorage.getItem("sentinai_key_expiry");
      if (exp && Date.now() > parseInt(exp, 10)) clearKey();
    }, 60_000);
    return () => clearInterval(id);
  }, [clearKey]);

  if (!hasKey) return <LoginPage />;

  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="incidents" element={<IncidentTimeline />} />
        <Route path="audit"     element={<AuditExplorer />} />
        <Route path="policy"    element={<PolicyEditor />} />
        <Route path="diff"      element={<DiffViewer />} />
        <Route path="settings"  element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

function AppRoutes() {
  return (
    <BrowserRouter>
      <AuthGuard />
    </BrowserRouter>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <AppRoutes />
      </ToastProvider>
    </ThemeProvider>
  );
}

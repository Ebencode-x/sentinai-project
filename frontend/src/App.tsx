import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ToastProvider }  from "@/components/Toast";
import { ThemeProvider }  from "@/hooks/useTheme";
import Layout             from "@/components/Layout";
import LoginPage          from "@/pages/LoginPage";
import Dashboard          from "@/pages/Dashboard";
import IncidentTimeline   from "@/pages/IncidentTimeline";
import AuditExplorer      from "@/pages/AuditExplorer";
import PolicyEditor       from "@/pages/PolicyEditor";
import DiffViewer         from "@/pages/DiffViewer";
import { useApiKey }      from "@/hooks/useApiKey";
import { useEffect }       from "react";

export default function App() {
  const { hasKey, clearKey } = useApiKey();
  useEffect(() => {
    const id = setInterval(() => {
      const exp = localStorage.getItem("sentinai_key_expiry");
      if (exp && Date.now() > parseInt(exp, 10)) {
        clearKey();
      }
    }, 60_000); // check every minute
    return () => clearInterval(id);
  }, [clearKey]);

  if (!hasKey) {
    return (
      <ThemeProvider>
        <ToastProvider>
          <LoginPage />
        </ToastProvider>
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index                  element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard"       element={<Dashboard />} />
              <Route path="incidents"       element={<IncidentTimeline />} />
              <Route path="audit"           element={<AuditExplorer />} />
              <Route path="policy"          element={<PolicyEditor />} />
              <Route path="diff"            element={<DiffViewer />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </ThemeProvider>
  );
}

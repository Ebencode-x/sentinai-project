import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Layout from "@/components/Layout";
import LoginPage from "@/pages/LoginPage";
import IncidentTimeline from "@/pages/IncidentTimeline";
import AuditExplorer from "@/pages/AuditExplorer";
import PolicyEditor from "@/pages/PolicyEditor";
import DiffViewer from "@/pages/DiffViewer";
import { useApiKey } from "@/hooks/useApiKey";

export default function App() {
  const { hasKey } = useApiKey();

  if (!hasKey) return <LoginPage />;

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/incidents" replace />} />
          <Route path="incidents"  element={<IncidentTimeline />} />
          <Route path="audit"      element={<AuditExplorer />} />
          <Route path="policy"     element={<PolicyEditor />} />
          <Route path="diff"       element={<DiffViewer />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

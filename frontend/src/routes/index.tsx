// Route tree for the PEIARS application.
//
// Public route:  /login
// Protected routes (wrapped in <RequireAuth>): the six workspaces.
// Default redirect: / -> /overview
// 404: a minimal NotFoundPage with a link back to /overview.

import { Navigate, Route, Routes } from "react-router-dom";
import { RequireAuth } from "@/routes/RequireAuth";
import { AppShell } from "@/layout/AppShell";
import { LoginPage } from "@/pages/LoginPage";
import { OverviewPage } from "@/pages/OverviewPage";
import { DataPage } from "@/pages/DataPage";
import { AnalysisPage } from "@/pages/AnalysisPage";
import { InvestigationsPage } from "@/pages/InvestigationsPage";
import { DomainsPage } from "@/pages/DomainsPage";
import { ResearchPage } from "@/pages/ResearchPage";
import { NotFoundPage } from "@/pages/NotFoundPage";

export function AppRoutes(): JSX.Element {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route path="/overview" element={<OverviewPage />} />
        <Route path="/data" element={<DataPage />} />
        <Route path="/analysis" element={<AnalysisPage />} />
        <Route path="/investigations" element={<InvestigationsPage />} />
        <Route path="/domains" element={<DomainsPage />} />
        <Route path="/research" element={<ResearchPage />} />
      </Route>
      <Route path="/" element={<Navigate to="/overview" replace />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

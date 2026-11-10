// Route guard: renders the protected layout only when authenticated.
//
// - status === "loading"     → full-page Loading screen (no sidebar/header)
// - status === "anonymous"   → redirect to /login?next=<current>
// - status === "unknown"     → full-page connectivity-uncertainty panel
// - status === "authenticated" → render <AppShell /> with nested routes

import { useEffect } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import { Loading } from "@/components/Loading";
import { ConnectivityUncertaintyPanel } from "@/components/ConnectivityUncertaintyPanel";

export function RequireAuth({ children }: { children: React.ReactNode }): JSX.Element {
  const { status, restore } = useAuth();
  const location = useLocation();

  // Trigger session restoration on mount (idempotent — the AuthProvider
  // guards against duplicate calls).
  useEffect(() => {
    void restore();
  }, [restore]);

  if (status === "loading") {
    return (
      <div className="fullpage-loading" role="status" aria-busy="true">
        <Loading label="Loading…" />
      </div>
    );
  }

  if (status === "anonymous") {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }

  if (status === "unknown") {
    return <ConnectivityUncertaintyPanel />;
  }

  // status === "authenticated"
  return <>{children ?? <Outlet />}</>;
}

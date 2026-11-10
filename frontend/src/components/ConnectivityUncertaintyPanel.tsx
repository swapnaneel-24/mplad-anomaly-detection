// ConnectivityUncertaintyPanel: full-bleed panel shown when /auth/me
// fails with a network error or timeout (status === "unknown").
//
// This is NOT a logout. The user might still be authenticated; we just
// cannot reach the server to confirm. The panel shows the sanitized error
// and a Retry button that re-runs restore().

import { useAuth } from "@/auth/AuthContext";
import { ErrorPanel } from "@/components/ErrorPanel";
import { Loading } from "@/components/Loading";

export function ConnectivityUncertaintyPanel(): JSX.Element {
  const { lastError, restore, status } = useAuth();

  return (
    <div className="connectivity-uncertainty" role="alert" aria-live="polite">
      <div className="connectivity-uncertainty__card">
        <h1 className="connectivity-uncertainty__title">Cannot reach the API</h1>
        <p className="connectivity-uncertainty__lede editorial-muted">
          The API could not be reached to verify your session. Your session has
          not been cleared — you have not been logged out. Check your
          connection and retry.
        </p>
        {status === "loading" ? (
          <Loading label="Retrying…" />
        ) : (
          <ErrorPanel
            error={lastError}
            onRetry={() => void restore()}
            title="Connection problem"
          />
        )}
        <p className="connectivity-uncertainty__hint mono">
          If the problem persists, the backend may be starting up or temporarily
          unavailable.
        </p>
      </div>
    </div>
  );
}
